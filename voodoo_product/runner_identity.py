from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Self

from .approval_policy import VALID_ENVIRONMENTS
from .capability_registry import CapabilityDefinition
from .evidence_primitives import canonical_json
from .execution_capsule import ExecutionCapsule
from .execution_lease import ExecutionLease

RUNNER_IDENTITY_TYPE: Final = "runner-identity/v1"
RUNNER_LOGICAL_IDENTITY_TYPE: Final = "runner-logical-identity/v1"
RUNNER_BOUNDARY_TYPE: Final = "runner-boundary/v1"
READ_ONLY_EFFECT_CLASS: Final = "READ_ONLY"
DENY_ALL_NETWORK_DEFAULT: Final = "DENY_ALL"

_RUNNER_IDENTITY_FIELDS = frozenset(
    {
        "schema_version",
        "identity_type",
        "runner_id",
        "runner_class",
        "provider",
        "provider_instance_id",
        "environment",
        "rootfs_digest",
        "resource_limit_profile_digest",
        "network_policy_digest",
        "identity_revision",
        "identity_digest",
    }
)
_RUNNER_BOUNDARY_FIELDS = frozenset(
    {
        "schema_version",
        "boundary_type",
        "runner_id",
        "runner_identity_digest",
        "lease_id",
        "lease_digest",
        "admission_id",
        "execution_id",
        "execution_epoch",
        "execution_capsule_digest",
        "capability_definition_identity",
        "environment",
        "runner_class",
        "credential_class",
        "effect_ceiling",
        "network_egress_default",
        "provider_mutation_allowed",
        "boundary_revision",
        "boundary_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


class RunnerBoundaryDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class RunnerIdentity:
    """Concrete Phase-D Runner identity bound to exact runtime profile digests.

    RunnerIdentity is descriptive evidence, never execution authority or runtime attestation by
    itself. Later SandCloud adapters must establish how provider identity and profile claims are
    authenticated. D1 only freezes the exact contract and lease/capsule binding semantics.
    """

    runner_id: str
    runner_class: str
    provider: str
    provider_instance_id: str
    environment: str
    rootfs_digest: str
    resource_limit_profile_digest: str
    network_policy_digest: str
    identity_revision: str
    identity_digest: str

    def __post_init__(self) -> None:
        for field in (
            "runner_id",
            "rootfs_digest",
            "resource_limit_profile_digest",
            "network_policy_digest",
            "identity_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "runner_class",
            "provider",
            "provider_instance_id",
            "identity_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        if self.runner_id != self._logical_identity():
            raise ValueError("runner_id does not match logical Runner identity")
        if self.identity_digest != _digest(self._claims_without_digest()):
            raise ValueError("identity_digest does not match RunnerIdentity")

    @classmethod
    def create(
        cls,
        *,
        runner_class: str,
        provider: str,
        provider_instance_id: str,
        environment: str,
        rootfs_digest: str,
        resource_limit_profile_digest: str,
        network_policy_digest: str,
        identity_revision: str,
    ) -> Self:
        logical_claims = {
            "identity_type": RUNNER_LOGICAL_IDENTITY_TYPE,
            "runner_class": runner_class,
            "provider": provider,
            "provider_instance_id": provider_instance_id,
            "environment": environment,
        }
        runner_id = _digest(logical_claims)
        claims = {
            "schema_version": 1,
            "identity_type": RUNNER_IDENTITY_TYPE,
            "runner_id": runner_id,
            "runner_class": runner_class,
            "provider": provider,
            "provider_instance_id": provider_instance_id,
            "environment": environment,
            "rootfs_digest": rootfs_digest,
            "resource_limit_profile_digest": resource_limit_profile_digest,
            "network_policy_digest": network_policy_digest,
            "identity_revision": identity_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "identity_type"}
        }
        return cls(**values, identity_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _RUNNER_IDENTITY_FIELDS, contract=RUNNER_IDENTITY_TYPE)
        if value["schema_version"] != 1 or value["identity_type"] != RUNNER_IDENTITY_TYPE:
            raise ValueError("runner-identity/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _RUNNER_IDENTITY_FIELDS
                if key not in {"schema_version", "identity_type"}
            }
        )

    def _logical_identity(self) -> str:
        return _digest(
            {
                "identity_type": RUNNER_LOGICAL_IDENTITY_TYPE,
                "runner_class": self.runner_class,
                "provider": self.provider,
                "provider_instance_id": self.provider_instance_id,
                "environment": self.environment,
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "identity_type": RUNNER_IDENTITY_TYPE,
            "runner_id": self.runner_id,
            "runner_class": self.runner_class,
            "provider": self.provider,
            "provider_instance_id": self.provider_instance_id,
            "environment": self.environment,
            "rootfs_digest": self.rootfs_digest,
            "resource_limit_profile_digest": self.resource_limit_profile_digest,
            "network_policy_digest": self.network_policy_digest,
            "identity_revision": self.identity_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "identity_digest": self.identity_digest}

    def assert_bound_to_lease(self, lease: ExecutionLease) -> None:
        if not isinstance(lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")
        if lease.runner_class != self.runner_class:
            raise RunnerBoundaryDenied("RUNNER_CLASS_MISMATCH")
        if lease.environment != self.environment:
            raise RunnerBoundaryDenied("RUNNER_ENVIRONMENT_MISMATCH")


@dataclass(frozen=True, slots=True)
class RunnerBoundary:
    """Phase-D safety ceiling binding one current lease to one concrete Runner identity.

    The boundary is not authority and does not execute anything. It proves only that a candidate
    Runner identity, exact C4 lease, exact ExecutionCapsule and immutable CapabilityDefinition are
    mutually bound and that the capability effect class is READ_ONLY. Runtime enforcement and
    provider identity attestation are later Phase-D slices.
    """

    runner_id: str
    runner_identity_digest: str
    lease_id: str
    lease_digest: str
    admission_id: str
    execution_id: str
    execution_epoch: int
    execution_capsule_digest: str
    capability_definition_identity: str
    environment: str
    runner_class: str
    credential_class: str
    effect_ceiling: str
    network_egress_default: str
    provider_mutation_allowed: bool
    boundary_revision: str
    boundary_digest: str

    def __post_init__(self) -> None:
        for field in (
            "runner_id",
            "runner_identity_digest",
            "lease_id",
            "lease_digest",
            "admission_id",
            "execution_capsule_digest",
            "capability_definition_identity",
            "boundary_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "execution_id",
            "environment",
            "runner_class",
            "credential_class",
            "boundary_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        if isinstance(self.execution_epoch, bool) or not isinstance(self.execution_epoch, int):
            raise ValueError("execution_epoch must be an integer")
        if self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.effect_ceiling != READ_ONLY_EFFECT_CLASS:
            raise ValueError("Phase-D effect ceiling must be READ_ONLY")
        if self.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise ValueError("Phase-D network default must be DENY_ALL")
        if self.provider_mutation_allowed is not False:
            raise ValueError("Phase-D provider mutation must remain disabled")
        if self.boundary_digest != _digest(self._claims_without_digest()):
            raise ValueError("boundary_digest does not match RunnerBoundary")

    @classmethod
    def create(
        cls,
        *,
        identity: RunnerIdentity,
        lease: ExecutionLease,
        capsule: ExecutionCapsule,
        definition: CapabilityDefinition,
        boundary_revision: str,
    ) -> Self:
        if not isinstance(identity, RunnerIdentity):
            raise ValueError("identity must be RunnerIdentity")
        if not isinstance(lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")
        if not isinstance(capsule, ExecutionCapsule):
            raise ValueError("capsule must be ExecutionCapsule")
        if not isinstance(definition, CapabilityDefinition):
            raise ValueError("definition must be CapabilityDefinition")
        _require_text(boundary_revision, field="boundary_revision")

        identity.assert_bound_to_lease(lease)
        if capsule.capsule_digest != lease.execution_capsule_digest:
            raise RunnerBoundaryDenied("EXECUTION_CAPSULE_MISMATCH")
        if capsule.runner_class != lease.runner_class:
            raise RunnerBoundaryDenied("CAPSULE_RUNNER_CLASS_MISMATCH")
        if identity.rootfs_digest != capsule.rootfs_digest:
            raise RunnerBoundaryDenied("RUNNER_ROOTFS_MISMATCH")
        if identity.resource_limit_profile_digest != capsule.resource_limit_profile_digest:
            raise RunnerBoundaryDenied("RUNNER_RESOURCE_PROFILE_MISMATCH")
        if identity.network_policy_digest != capsule.network_policy_digest:
            raise RunnerBoundaryDenied("RUNNER_NETWORK_POLICY_MISMATCH")
        if definition.definition_identity != capsule.capability_definition_identity:
            raise RunnerBoundaryDenied("CAPABILITY_DEFINITION_MISMATCH")
        if definition.target_kind != capsule.target_kind:
            raise RunnerBoundaryDenied("CAPABILITY_TARGET_KIND_MISMATCH")
        if definition.handler_id != capsule.handler_id:
            raise RunnerBoundaryDenied("CAPABILITY_HANDLER_MISMATCH")
        if definition.effect_class != READ_ONLY_EFFECT_CLASS:
            raise RunnerBoundaryDenied("PHASE_D_EFFECT_NOT_READ_ONLY")
        if lease.environment not in definition.supported_environments:
            raise RunnerBoundaryDenied("CAPABILITY_ENVIRONMENT_MISMATCH")

        claims = {
            "schema_version": 1,
            "boundary_type": RUNNER_BOUNDARY_TYPE,
            "runner_id": identity.runner_id,
            "runner_identity_digest": identity.identity_digest,
            "lease_id": lease.lease_id,
            "lease_digest": lease.lease_digest,
            "admission_id": lease.admission_id,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "execution_capsule_digest": capsule.capsule_digest,
            "capability_definition_identity": definition.definition_identity,
            "environment": lease.environment,
            "runner_class": lease.runner_class,
            "credential_class": capsule.credential_class,
            "effect_ceiling": READ_ONLY_EFFECT_CLASS,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "provider_mutation_allowed": False,
            "boundary_revision": boundary_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "boundary_type"}
        }
        return cls(**values, boundary_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _RUNNER_BOUNDARY_FIELDS, contract=RUNNER_BOUNDARY_TYPE)
        if value["schema_version"] != 1 or value["boundary_type"] != RUNNER_BOUNDARY_TYPE:
            raise ValueError("runner-boundary/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _RUNNER_BOUNDARY_FIELDS
                if key not in {"schema_version", "boundary_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "boundary_type": RUNNER_BOUNDARY_TYPE,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "lease_id": self.lease_id,
            "lease_digest": self.lease_digest,
            "admission_id": self.admission_id,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "environment": self.environment,
            "runner_class": self.runner_class,
            "credential_class": self.credential_class,
            "effect_ceiling": self.effect_ceiling,
            "network_egress_default": self.network_egress_default,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "boundary_revision": self.boundary_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "boundary_digest": self.boundary_digest}
