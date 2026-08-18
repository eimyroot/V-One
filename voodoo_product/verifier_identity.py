from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Self

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json
from .github_read_provider import GitHubRefObservation
from .runner_identity import (
    DENY_ALL_NETWORK_DEFAULT,
    READ_ONLY_EFFECT_CLASS,
    RunnerBoundary,
    RunnerIdentity,
)

VERIFIER_IDENTITY_TYPE: Final = "verifier-identity/v1"
VERIFIER_LOGICAL_IDENTITY_TYPE: Final = "verifier-logical-identity/v1"
INDEPENDENT_VERIFICATION_BOUNDARY_TYPE: Final = "independent-verification-boundary/v1"
INDEPENDENCE_CLASS: Final = "SEPARATE_IDENTITY_INSTANCE_CREDENTIAL"

_VERIFIER_IDENTITY_FIELDS = frozenset(
    {
        "schema_version",
        "identity_type",
        "verifier_id",
        "verifier_class",
        "provider",
        "provider_instance_id",
        "environment",
        "credential_class",
        "rootfs_digest",
        "resource_limit_profile_digest",
        "network_policy_digest",
        "identity_revision",
        "identity_digest",
    }
)
_VERIFICATION_BOUNDARY_FIELDS = frozenset(
    {
        "schema_version",
        "boundary_type",
        "verifier_id",
        "verifier_identity_digest",
        "verifier_class",
        "verifier_provider",
        "verifier_provider_instance_id",
        "verifier_credential_class",
        "runner_id",
        "runner_identity_digest",
        "runner_boundary_digest",
        "runner_provider_instance_id",
        "runner_credential_class",
        "execution_id",
        "execution_epoch",
        "target_digest",
        "runner_observation_digest",
        "environment",
        "effect_ceiling",
        "network_egress_default",
        "provider_mutation_allowed",
        "independence_class",
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


class IndependentVerificationBoundaryDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class VerifierIdentity:
    """Content-addressed identity for one independent Phase-E verifier runtime.

    VerifierIdentity is descriptive evidence only. It carries no execution grant, lease,
    provider token or permission. A later Phase-E slice must authenticate the concrete
    verifier runtime and deliver a separate READ-only credential out of band.
    """

    verifier_id: str
    verifier_class: str
    provider: str
    provider_instance_id: str
    environment: str
    credential_class: str
    rootfs_digest: str
    resource_limit_profile_digest: str
    network_policy_digest: str
    identity_revision: str
    identity_digest: str

    def __post_init__(self) -> None:
        for field in (
            "verifier_id",
            "rootfs_digest",
            "resource_limit_profile_digest",
            "network_policy_digest",
            "identity_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "verifier_class",
            "provider",
            "provider_instance_id",
            "credential_class",
            "identity_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        if self.verifier_id != self._logical_identity():
            raise ValueError("verifier_id does not match logical Verifier identity")
        if self.identity_digest != _digest(self._claims_without_digest()):
            raise ValueError("identity_digest does not match VerifierIdentity")

    @classmethod
    def create(
        cls,
        *,
        verifier_class: str,
        provider: str,
        provider_instance_id: str,
        environment: str,
        credential_class: str,
        rootfs_digest: str,
        resource_limit_profile_digest: str,
        network_policy_digest: str,
        identity_revision: str,
    ) -> Self:
        logical_claims = {
            "identity_type": VERIFIER_LOGICAL_IDENTITY_TYPE,
            "verifier_class": verifier_class,
            "provider": provider,
            "provider_instance_id": provider_instance_id,
            "environment": environment,
            "credential_class": credential_class,
        }
        verifier_id = _digest(logical_claims)
        claims = {
            "schema_version": 1,
            "identity_type": VERIFIER_IDENTITY_TYPE,
            "verifier_id": verifier_id,
            "verifier_class": verifier_class,
            "provider": provider,
            "provider_instance_id": provider_instance_id,
            "environment": environment,
            "credential_class": credential_class,
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
        _require_exact_fields(value, _VERIFIER_IDENTITY_FIELDS, contract=VERIFIER_IDENTITY_TYPE)
        if value["schema_version"] != 1 or value["identity_type"] != VERIFIER_IDENTITY_TYPE:
            raise ValueError("verifier-identity/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _VERIFIER_IDENTITY_FIELDS
                if key not in {"schema_version", "identity_type"}
            }
        )

    def _logical_identity(self) -> str:
        return _digest(
            {
                "identity_type": VERIFIER_LOGICAL_IDENTITY_TYPE,
                "verifier_class": self.verifier_class,
                "provider": self.provider,
                "provider_instance_id": self.provider_instance_id,
                "environment": self.environment,
                "credential_class": self.credential_class,
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "identity_type": VERIFIER_IDENTITY_TYPE,
            "verifier_id": self.verifier_id,
            "verifier_class": self.verifier_class,
            "provider": self.provider,
            "provider_instance_id": self.provider_instance_id,
            "environment": self.environment,
            "credential_class": self.credential_class,
            "rootfs_digest": self.rootfs_digest,
            "resource_limit_profile_digest": self.resource_limit_profile_digest,
            "network_policy_digest": self.network_policy_digest,
            "identity_revision": self.identity_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "identity_digest": self.identity_digest}


@dataclass(frozen=True, slots=True)
class IndependentVerificationBoundary:
    """Minimum fail-closed independence boundary between Runner and Verifier.

    The boundary binds one verifier identity to one already-produced runner observation.
    It proves separation of identity namespace, concrete provider instance and credential
    class. It does not perform verification and is not a VerificationResult or OperationProof.
    """

    verifier_id: str
    verifier_identity_digest: str
    verifier_class: str
    verifier_provider: str
    verifier_provider_instance_id: str
    verifier_credential_class: str
    runner_id: str
    runner_identity_digest: str
    runner_boundary_digest: str
    runner_provider_instance_id: str
    runner_credential_class: str
    execution_id: str
    execution_epoch: int
    target_digest: str
    runner_observation_digest: str
    environment: str
    effect_ceiling: str
    network_egress_default: str
    provider_mutation_allowed: bool
    independence_class: str
    boundary_revision: str
    boundary_digest: str

    def __post_init__(self) -> None:
        for field in (
            "verifier_id",
            "verifier_identity_digest",
            "runner_id",
            "runner_identity_digest",
            "runner_boundary_digest",
            "target_digest",
            "runner_observation_digest",
            "boundary_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "verifier_class",
            "verifier_provider",
            "verifier_provider_instance_id",
            "verifier_credential_class",
            "runner_provider_instance_id",
            "runner_credential_class",
            "execution_id",
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
            raise ValueError("Phase-E verifier effect ceiling must be READ_ONLY")
        if self.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise ValueError("Phase-E verifier network default must be DENY_ALL")
        if self.provider_mutation_allowed is not False:
            raise ValueError("Phase-E verifier cannot mutate providers")
        if self.independence_class != INDEPENDENCE_CLASS:
            raise ValueError("independence_class is unsupported")
        if self.verifier_id == self.runner_id:
            raise ValueError("VerifierIdentity must differ from RunnerIdentity")
        if self.verifier_provider_instance_id == self.runner_provider_instance_id:
            raise ValueError("Verifier provider instance must differ from Runner provider instance")
        if self.verifier_credential_class == self.runner_credential_class:
            raise ValueError("Verifier credential class must differ from Runner credential class")
        if self.boundary_digest != _digest(self._claims_without_digest()):
            raise ValueError("boundary_digest does not match IndependentVerificationBoundary")

    @classmethod
    def create(
        cls,
        *,
        verifier: VerifierIdentity,
        runner_identity: RunnerIdentity,
        runner_boundary: RunnerBoundary,
        runner_observation: GitHubRefObservation,
        boundary_revision: str,
    ) -> Self:
        if not isinstance(verifier, VerifierIdentity):
            raise ValueError("verifier must be VerifierIdentity")
        if not isinstance(runner_identity, RunnerIdentity):
            raise ValueError("runner_identity must be RunnerIdentity")
        if not isinstance(runner_boundary, RunnerBoundary):
            raise ValueError("runner_boundary must be RunnerBoundary")
        if not isinstance(runner_observation, GitHubRefObservation):
            raise ValueError("runner_observation must be GitHubRefObservation")
        _require_text(boundary_revision, field="boundary_revision")

        _assert_runner_evidence_bound(
            runner_identity=runner_identity,
            runner_boundary=runner_boundary,
            runner_observation=runner_observation,
        )
        if verifier.environment != runner_boundary.environment:
            raise IndependentVerificationBoundaryDenied("VERIFIER_ENVIRONMENT_MISMATCH")
        if verifier.verifier_id == runner_identity.runner_id:
            raise IndependentVerificationBoundaryDenied("VERIFIER_IDENTITY_NOT_INDEPENDENT")
        if verifier.identity_digest == runner_identity.identity_digest:
            raise IndependentVerificationBoundaryDenied("VERIFIER_IDENTITY_NOT_INDEPENDENT")
        if verifier.provider_instance_id == runner_identity.provider_instance_id:
            raise IndependentVerificationBoundaryDenied("VERIFIER_PROVIDER_INSTANCE_NOT_INDEPENDENT")
        if verifier.credential_class == runner_boundary.credential_class:
            raise IndependentVerificationBoundaryDenied("VERIFIER_CREDENTIAL_CLASS_NOT_INDEPENDENT")

        claims = {
            "schema_version": 1,
            "boundary_type": INDEPENDENT_VERIFICATION_BOUNDARY_TYPE,
            "verifier_id": verifier.verifier_id,
            "verifier_identity_digest": verifier.identity_digest,
            "verifier_class": verifier.verifier_class,
            "verifier_provider": verifier.provider,
            "verifier_provider_instance_id": verifier.provider_instance_id,
            "verifier_credential_class": verifier.credential_class,
            "runner_id": runner_identity.runner_id,
            "runner_identity_digest": runner_identity.identity_digest,
            "runner_boundary_digest": runner_boundary.boundary_digest,
            "runner_provider_instance_id": runner_identity.provider_instance_id,
            "runner_credential_class": runner_boundary.credential_class,
            "execution_id": runner_observation.execution_id,
            "execution_epoch": runner_observation.execution_epoch,
            "target_digest": runner_observation.target_digest,
            "runner_observation_digest": runner_observation.observation_digest,
            "environment": runner_boundary.environment,
            "effect_ceiling": READ_ONLY_EFFECT_CLASS,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "provider_mutation_allowed": False,
            "independence_class": INDEPENDENCE_CLASS,
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
        _require_exact_fields(
            value,
            _VERIFICATION_BOUNDARY_FIELDS,
            contract=INDEPENDENT_VERIFICATION_BOUNDARY_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["boundary_type"] != INDEPENDENT_VERIFICATION_BOUNDARY_TYPE
        ):
            raise ValueError("independent-verification-boundary/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _VERIFICATION_BOUNDARY_FIELDS
                if key not in {"schema_version", "boundary_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "boundary_type": INDEPENDENT_VERIFICATION_BOUNDARY_TYPE,
            "verifier_id": self.verifier_id,
            "verifier_identity_digest": self.verifier_identity_digest,
            "verifier_class": self.verifier_class,
            "verifier_provider": self.verifier_provider,
            "verifier_provider_instance_id": self.verifier_provider_instance_id,
            "verifier_credential_class": self.verifier_credential_class,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "runner_boundary_digest": self.runner_boundary_digest,
            "runner_provider_instance_id": self.runner_provider_instance_id,
            "runner_credential_class": self.runner_credential_class,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "target_digest": self.target_digest,
            "runner_observation_digest": self.runner_observation_digest,
            "environment": self.environment,
            "effect_ceiling": self.effect_ceiling,
            "network_egress_default": self.network_egress_default,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "independence_class": self.independence_class,
            "boundary_revision": self.boundary_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "boundary_digest": self.boundary_digest}


def _assert_runner_evidence_bound(
    *,
    runner_identity: RunnerIdentity,
    runner_boundary: RunnerBoundary,
    runner_observation: GitHubRefObservation,
) -> None:
    if runner_boundary.runner_id != runner_identity.runner_id:
        raise IndependentVerificationBoundaryDenied("RUNNER_IDENTITY_BINDING_MISMATCH")
    if runner_boundary.runner_identity_digest != runner_identity.identity_digest:
        raise IndependentVerificationBoundaryDenied("RUNNER_IDENTITY_BINDING_MISMATCH")
    if runner_boundary.environment != runner_identity.environment:
        raise IndependentVerificationBoundaryDenied("RUNNER_ENVIRONMENT_BINDING_MISMATCH")
    if runner_observation.runner_id != runner_identity.runner_id:
        raise IndependentVerificationBoundaryDenied("RUNNER_OBSERVATION_IDENTITY_MISMATCH")
    if runner_observation.runner_boundary_digest != runner_boundary.boundary_digest:
        raise IndependentVerificationBoundaryDenied("RUNNER_OBSERVATION_BOUNDARY_MISMATCH")
    if runner_observation.provider_instance_id != runner_identity.provider_instance_id:
        raise IndependentVerificationBoundaryDenied("RUNNER_OBSERVATION_INSTANCE_MISMATCH")
    if runner_observation.execution_id != runner_boundary.execution_id:
        raise IndependentVerificationBoundaryDenied("RUNNER_OBSERVATION_EXECUTION_MISMATCH")
    if runner_observation.execution_epoch != runner_boundary.execution_epoch:
        raise IndependentVerificationBoundaryDenied("RUNNER_OBSERVATION_EPOCH_MISMATCH")
    if runner_observation.execution_capsule_digest != runner_boundary.execution_capsule_digest:
        raise IndependentVerificationBoundaryDenied("RUNNER_OBSERVATION_CAPSULE_MISMATCH")
    if (
        runner_observation.capability_definition_identity
        != runner_boundary.capability_definition_identity
    ):
        raise IndependentVerificationBoundaryDenied("RUNNER_OBSERVATION_CAPABILITY_MISMATCH")
