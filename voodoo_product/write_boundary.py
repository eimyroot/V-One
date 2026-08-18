from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Self

from .capability_registry import CapabilityDefinition
from .controlled_write import (
    CREATE_REF_OPERATION,
    DELETE_EXACT_CREATED_REF_ROLLBACK,
    GITHUB_CREATE_REF_CAPABILITY,
    GITHUB_CREATE_REF_HANDLER,
    MAX_PROVIDER_MUTATIONS_R1,
    MUTATION_REVERSIBLE_EFFECT_CLASS,
    STAGING_ENVIRONMENT,
    ControlledWriteRequirement,
    GitHubCreateRefConditionContract,
)
from .evidence_primitives import canonical_json
from .execution_capsule import ExecutionCapsule
from .execution_conformance import HandlerConformanceEvidence
from .execution_lease import ExecutionLease
from .precondition_witness import ATOMIC_PROVIDER_CONDITION
from .runner_identity import DENY_ALL_NETWORK_DEFAULT, RunnerIdentity

RUNNER_BOUNDARY_V2_TYPE: Final = "runner-boundary/v2"
CREDENTIAL_BROKER_POLICY_V2_TYPE: Final = "credential-broker-policy/v2"
CREDENTIAL_ACCESS_DECISION_V2_TYPE: Final = "credential-access-decision/v2"
CREDENTIAL_ACCESS_DECISION_IDENTITY_V2_TYPE: Final = "credential-access-decision-id/v2"

WRITE_BOUNDED_ACCESS_MODE: Final = "WRITE_BOUNDED"
WRITE_RUNNER_CLASS: Final = "github-actions.docker-isolated-write/v1"
GITHUB_CREATE_REF_CREDENTIAL_CLASS: Final = "github.create-ref/scoped-v1"
GITHUB_PROVIDER: Final = "github"
GITHUB_API_AUDIENCE: Final = "api.github.com"
MAX_WRITE_CREDENTIAL_TTL_SECONDS: Final = 300

_BOUNDARY_FIELDS = frozenset(
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
        "controlled_write_requirement_digest",
        "atomic_provider_condition_contract_identity",
        "verification_contract_identity",
        "environment",
        "runner_class",
        "credential_class",
        "effect_ceiling",
        "network_egress_default",
        "provider_mutation_allowed",
        "max_provider_mutations",
        "rollback_strategy",
        "boundary_revision",
        "boundary_digest",
    }
)
_POLICY_FIELDS = frozenset(
    {
        "schema_version",
        "policy_type",
        "credential_class",
        "provider",
        "audience",
        "capability_definition_identity",
        "controlled_write_requirement_digest",
        "atomic_provider_condition_contract_identity",
        "environment",
        "access_mode",
        "provider_operation",
        "provider_mutation_allowed",
        "max_provider_mutations",
        "max_ttl_seconds",
        "policy_revision",
        "policy_digest",
    }
)
_DECISION_FIELDS = frozenset(
    {
        "schema_version",
        "decision_type",
        "decision_id",
        "runner_boundary_digest",
        "runner_id",
        "runner_identity_digest",
        "lease_id",
        "lease_digest",
        "execution_id",
        "execution_epoch",
        "execution_capsule_digest",
        "capability_definition_identity",
        "controlled_write_requirement_digest",
        "atomic_provider_condition_contract_identity",
        "credential_class",
        "provider",
        "audience",
        "environment",
        "access_mode",
        "provider_operation",
        "provider_mutation_allowed",
        "max_provider_mutations",
        "valid_from",
        "expires_at",
        "policy_digest",
        "policy_revision",
        "decision_revision",
        "decision_digest",
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


def _require_timestamp(value: object, *, field: str) -> tuple[str, datetime]:
    text = _require_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return canonical, parsed.astimezone(UTC)


def _require_exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], *, contract: str
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


class WriteBoundaryDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class WriteCredentialDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class RunnerBoundaryV2:
    """F2 write-specific RunnerBoundary.

    This is a candidate safety ceiling, not execution authority and not runtime activation. It binds
    one current C4 lease and concrete Runner identity to the exact F1 controlled-write chain without
    changing the released READ-only runner-boundary/v1 semantics.
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
    controlled_write_requirement_digest: str
    atomic_provider_condition_contract_identity: str
    verification_contract_identity: str
    environment: str
    runner_class: str
    credential_class: str
    effect_ceiling: str
    network_egress_default: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    rollback_strategy: str
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
            "controlled_write_requirement_digest",
            "atomic_provider_condition_contract_identity",
            "verification_contract_identity",
            "boundary_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "execution_id",
            "environment",
            "runner_class",
            "credential_class",
            "effect_ceiling",
            "network_egress_default",
            "rollback_strategy",
            "boundary_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.execution_epoch < 1 or isinstance(self.execution_epoch, bool):
            raise ValueError("execution_epoch must be an integer >= 1")
        if self.environment != STAGING_ENVIRONMENT:
            raise ValueError("F2 write boundary is staging-only")
        if self.runner_class != WRITE_RUNNER_CLASS:
            raise ValueError("F2 write runner class is invalid")
        if self.credential_class != GITHUB_CREATE_REF_CREDENTIAL_CLASS:
            raise ValueError("F2 credential class is invalid")
        if self.effect_ceiling != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise ValueError("F2 effect ceiling must be mutation.reversible")
        if self.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise ValueError("F2 network default must be DENY_ALL")
        if self.provider_mutation_allowed is not True:
            raise ValueError("F2 write boundary must explicitly permit the bounded mutation")
        if self.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise ValueError("F2 write boundary allows exactly one provider mutation")
        if self.rollback_strategy != DELETE_EXACT_CREATED_REF_ROLLBACK:
            raise ValueError("F2 rollback strategy is unsupported")
        if self.boundary_digest != _digest(self._claims_without_digest()):
            raise ValueError("boundary_digest does not match runner-boundary/v2")

    @classmethod
    def create(
        cls,
        *,
        identity: RunnerIdentity,
        lease: ExecutionLease,
        capsule: ExecutionCapsule,
        definition: CapabilityDefinition,
        handler_evidence: HandlerConformanceEvidence,
        provider_condition: GitHubCreateRefConditionContract,
        requirement: ControlledWriteRequirement,
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
        if not isinstance(handler_evidence, HandlerConformanceEvidence):
            raise ValueError("handler_evidence must be HandlerConformanceEvidence")
        if not isinstance(provider_condition, GitHubCreateRefConditionContract):
            raise ValueError("provider_condition must be GitHubCreateRefConditionContract")
        if not isinstance(requirement, ControlledWriteRequirement):
            raise ValueError("requirement must be ControlledWriteRequirement")
        _require_text(boundary_revision, field="boundary_revision")

        identity.assert_bound_to_lease(lease)
        if identity.runner_class != WRITE_RUNNER_CLASS:
            raise WriteBoundaryDenied("F2_RUNNER_CLASS_NOT_WRITE_SPECIFIC")
        if lease.environment != STAGING_ENVIRONMENT:
            raise WriteBoundaryDenied("F2_ENVIRONMENT_NOT_STAGING")
        if capsule.capsule_digest != lease.execution_capsule_digest:
            raise WriteBoundaryDenied("F2_EXECUTION_CAPSULE_MISMATCH")
        if capsule.runner_class != lease.runner_class:
            raise WriteBoundaryDenied("F2_CAPSULE_RUNNER_CLASS_MISMATCH")
        if identity.rootfs_digest != capsule.rootfs_digest:
            raise WriteBoundaryDenied("F2_RUNNER_ROOTFS_MISMATCH")
        if identity.resource_limit_profile_digest != capsule.resource_limit_profile_digest:
            raise WriteBoundaryDenied("F2_RUNNER_RESOURCE_PROFILE_MISMATCH")
        if identity.network_policy_digest != capsule.network_policy_digest:
            raise WriteBoundaryDenied("F2_RUNNER_NETWORK_POLICY_MISMATCH")
        if definition.capability != GITHUB_CREATE_REF_CAPABILITY:
            raise WriteBoundaryDenied("F2_CAPABILITY_NOT_CREATE_REF")
        if definition.definition_identity != capsule.capability_definition_identity:
            raise WriteBoundaryDenied("F2_CAPABILITY_DEFINITION_MISMATCH")
        if definition.handler_id != GITHUB_CREATE_REF_HANDLER or definition.handler_id != capsule.handler_id:
            raise WriteBoundaryDenied("F2_HANDLER_MISMATCH")
        if definition.effect_class != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise WriteBoundaryDenied("F2_EFFECT_NOT_REVERSIBLE_MUTATION")
        if definition.production_eligible or definition.supported_environments != (STAGING_ENVIRONMENT,):
            raise WriteBoundaryDenied("F2_CAPABILITY_NOT_STAGING_ONLY")
        if capsule.precondition_enforcement_class != ATOMIC_PROVIDER_CONDITION:
            raise WriteBoundaryDenied("F2_ATOMIC_PROVIDER_CONDITION_REQUIRED")
        if capsule.credential_class != GITHUB_CREATE_REF_CREDENTIAL_CLASS:
            raise WriteBoundaryDenied("F2_CREDENTIAL_CLASS_MISMATCH")

        expected_requirement = {
            "capability_definition_identity": definition.definition_identity,
            "execution_capsule_digest": capsule.capsule_digest,
            "handler_conformance_evidence_digest": handler_evidence.evidence_digest,
            "atomic_provider_condition_contract_identity": provider_condition.contract_digest,
            "verification_contract_identity": capsule.verification_contract_identity,
            "effect_class": MUTATION_REVERSIBLE_EFFECT_CLASS,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "rollback_strategy": DELETE_EXACT_CREATED_REF_ROLLBACK,
            "provider_mutation_allowed": True,
        }
        actual_requirement = {
            "capability_definition_identity": requirement.capability_definition_identity,
            "execution_capsule_digest": requirement.execution_capsule_digest,
            "handler_conformance_evidence_digest": requirement.handler_conformance_evidence_digest,
            "atomic_provider_condition_contract_identity": requirement.atomic_provider_condition_contract_identity,
            "verification_contract_identity": requirement.verification_contract_identity,
            "effect_class": requirement.effect_class,
            "max_provider_mutations": requirement.max_provider_mutations,
            "rollback_strategy": requirement.rollback_strategy,
            "provider_mutation_allowed": requirement.provider_mutation_allowed,
        }
        if actual_requirement != expected_requirement:
            raise WriteBoundaryDenied("F2_CONTROLLED_WRITE_REQUIREMENT_MISMATCH")
        if handler_evidence.execution_capsule_digest != capsule.capsule_digest:
            raise WriteBoundaryDenied("F2_HANDLER_EVIDENCE_CAPSULE_MISMATCH")
        if handler_evidence.atomic_provider_condition_contract_identity != provider_condition.contract_digest:
            raise WriteBoundaryDenied("F2_PROVIDER_CONDITION_MISMATCH")

        claims = {
            "schema_version": 2,
            "boundary_type": RUNNER_BOUNDARY_V2_TYPE,
            "runner_id": identity.runner_id,
            "runner_identity_digest": identity.identity_digest,
            "lease_id": lease.lease_id,
            "lease_digest": lease.lease_digest,
            "admission_id": lease.admission_id,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "execution_capsule_digest": capsule.capsule_digest,
            "capability_definition_identity": definition.definition_identity,
            "controlled_write_requirement_digest": requirement.requirement_digest,
            "atomic_provider_condition_contract_identity": provider_condition.contract_digest,
            "verification_contract_identity": capsule.verification_contract_identity,
            "environment": lease.environment,
            "runner_class": identity.runner_class,
            "credential_class": capsule.credential_class,
            "effect_ceiling": MUTATION_REVERSIBLE_EFFECT_CLASS,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "provider_mutation_allowed": True,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "rollback_strategy": requirement.rollback_strategy,
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
        _require_exact_fields(value, _BOUNDARY_FIELDS, contract=RUNNER_BOUNDARY_V2_TYPE)
        if value["schema_version"] != 2 or value["boundary_type"] != RUNNER_BOUNDARY_V2_TYPE:
            raise ValueError("runner-boundary/v2 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _BOUNDARY_FIELDS
                if key not in {"schema_version", "boundary_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "boundary_type": RUNNER_BOUNDARY_V2_TYPE,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "lease_id": self.lease_id,
            "lease_digest": self.lease_digest,
            "admission_id": self.admission_id,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "controlled_write_requirement_digest": self.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": self.atomic_provider_condition_contract_identity,
            "verification_contract_identity": self.verification_contract_identity,
            "environment": self.environment,
            "runner_class": self.runner_class,
            "credential_class": self.credential_class,
            "effect_ceiling": self.effect_ceiling,
            "network_egress_default": self.network_egress_default,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "max_provider_mutations": self.max_provider_mutations,
            "rollback_strategy": self.rollback_strategy,
            "boundary_revision": self.boundary_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "boundary_digest": self.boundary_digest}


@dataclass(frozen=True, slots=True)
class CredentialBrokerPolicyV2:
    """Exact F2 policy for out-of-band delivery of one bounded create-ref credential."""

    credential_class: str
    provider: str
    audience: str
    capability_definition_identity: str
    controlled_write_requirement_digest: str
    atomic_provider_condition_contract_identity: str
    environment: str
    access_mode: str
    provider_operation: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    max_ttl_seconds: int
    policy_revision: str
    policy_digest: str

    def __post_init__(self) -> None:
        for field in (
            "credential_class",
            "provider",
            "audience",
            "environment",
            "access_mode",
            "provider_operation",
            "policy_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "capability_definition_identity",
            "controlled_write_requirement_digest",
            "atomic_provider_condition_contract_identity",
            "policy_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.credential_class != GITHUB_CREATE_REF_CREDENTIAL_CLASS:
            raise ValueError("F2 policy credential class is invalid")
        if self.provider != GITHUB_PROVIDER or self.audience != GITHUB_API_AUDIENCE:
            raise ValueError("F2 policy provider or audience is invalid")
        if self.environment != STAGING_ENVIRONMENT:
            raise ValueError("F2 policy is staging-only")
        if self.access_mode != WRITE_BOUNDED_ACCESS_MODE:
            raise ValueError("F2 policy access mode must be WRITE_BOUNDED")
        if self.provider_operation != CREATE_REF_OPERATION:
            raise ValueError("F2 policy operation must be CREATE_REF")
        if self.provider_mutation_allowed is not True:
            raise ValueError("F2 policy must explicitly permit the bounded mutation")
        if self.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise ValueError("F2 policy allows exactly one provider mutation")
        if (
            isinstance(self.max_ttl_seconds, bool)
            or not isinstance(self.max_ttl_seconds, int)
            or self.max_ttl_seconds < 1
            or self.max_ttl_seconds > MAX_WRITE_CREDENTIAL_TTL_SECONDS
        ):
            raise ValueError("F2 policy max_ttl_seconds is invalid")
        if self.policy_digest != _digest(self._claims_without_digest()):
            raise ValueError("policy_digest does not match credential-broker-policy/v2")

    @classmethod
    def create(
        cls,
        *,
        boundary: RunnerBoundaryV2,
        max_ttl_seconds: int,
        policy_revision: str,
    ) -> Self:
        if not isinstance(boundary, RunnerBoundaryV2):
            raise ValueError("boundary must be RunnerBoundaryV2")
        _require_text(policy_revision, field="policy_revision")
        claims = {
            "schema_version": 2,
            "policy_type": CREDENTIAL_BROKER_POLICY_V2_TYPE,
            "credential_class": boundary.credential_class,
            "provider": GITHUB_PROVIDER,
            "audience": GITHUB_API_AUDIENCE,
            "capability_definition_identity": boundary.capability_definition_identity,
            "controlled_write_requirement_digest": boundary.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": boundary.atomic_provider_condition_contract_identity,
            "environment": boundary.environment,
            "access_mode": WRITE_BOUNDED_ACCESS_MODE,
            "provider_operation": CREATE_REF_OPERATION,
            "provider_mutation_allowed": True,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "max_ttl_seconds": max_ttl_seconds,
            "policy_revision": policy_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "policy_type"}
        }
        return cls(**values, policy_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _POLICY_FIELDS, contract=CREDENTIAL_BROKER_POLICY_V2_TYPE)
        if value["schema_version"] != 2 or value["policy_type"] != CREDENTIAL_BROKER_POLICY_V2_TYPE:
            raise ValueError("credential-broker-policy/v2 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _POLICY_FIELDS
                if key not in {"schema_version", "policy_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "policy_type": CREDENTIAL_BROKER_POLICY_V2_TYPE,
            "credential_class": self.credential_class,
            "provider": self.provider,
            "audience": self.audience,
            "capability_definition_identity": self.capability_definition_identity,
            "controlled_write_requirement_digest": self.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": self.atomic_provider_condition_contract_identity,
            "environment": self.environment,
            "access_mode": self.access_mode,
            "provider_operation": self.provider_operation,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "max_provider_mutations": self.max_provider_mutations,
            "max_ttl_seconds": self.max_ttl_seconds,
            "policy_revision": self.policy_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "policy_digest": self.policy_digest}


@dataclass(frozen=True, slots=True)
class CredentialAccessDecisionV2:
    """Authorization metadata for one bounded write credential delivered out of band.

    The decision contains no credential bytes or secret handle. It narrows delivery to one exact F2
    boundary, lease, F1 requirement, create-ref operation and bounded lifetime.
    """

    decision_id: str
    runner_boundary_digest: str
    runner_id: str
    runner_identity_digest: str
    lease_id: str
    lease_digest: str
    execution_id: str
    execution_epoch: int
    execution_capsule_digest: str
    capability_definition_identity: str
    controlled_write_requirement_digest: str
    atomic_provider_condition_contract_identity: str
    credential_class: str
    provider: str
    audience: str
    environment: str
    access_mode: str
    provider_operation: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    valid_from: str
    expires_at: str
    policy_digest: str
    policy_revision: str
    decision_revision: str
    decision_digest: str

    def __post_init__(self) -> None:
        for field in (
            "decision_id",
            "runner_boundary_digest",
            "runner_id",
            "runner_identity_digest",
            "lease_id",
            "lease_digest",
            "execution_capsule_digest",
            "capability_definition_identity",
            "controlled_write_requirement_digest",
            "atomic_provider_condition_contract_identity",
            "policy_digest",
            "decision_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "execution_id",
            "credential_class",
            "provider",
            "audience",
            "environment",
            "access_mode",
            "provider_operation",
            "policy_revision",
            "decision_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.execution_epoch < 1 or isinstance(self.execution_epoch, bool):
            raise ValueError("execution_epoch must be an integer >= 1")
        _, valid_from = _require_timestamp(self.valid_from, field="valid_from")
        _, expires_at = _require_timestamp(self.expires_at, field="expires_at")
        if expires_at <= valid_from:
            raise ValueError("credential decision expiry must be after valid_from")
        if self.credential_class != GITHUB_CREATE_REF_CREDENTIAL_CLASS:
            raise ValueError("F2 decision credential class is invalid")
        if self.provider != GITHUB_PROVIDER or self.audience != GITHUB_API_AUDIENCE:
            raise ValueError("F2 decision provider or audience is invalid")
        if self.environment != STAGING_ENVIRONMENT:
            raise ValueError("F2 decision is staging-only")
        if self.access_mode != WRITE_BOUNDED_ACCESS_MODE:
            raise ValueError("F2 decision access mode must be WRITE_BOUNDED")
        if self.provider_operation != CREATE_REF_OPERATION:
            raise ValueError("F2 decision operation must be CREATE_REF")
        if self.provider_mutation_allowed is not True:
            raise ValueError("F2 decision must explicitly permit the bounded mutation")
        if self.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise ValueError("F2 decision allows exactly one provider mutation")
        if self.decision_id != self._logical_identity():
            raise ValueError("decision_id does not match credential-access-decision/v2 identity")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise ValueError("decision_digest does not match credential-access-decision/v2")

    @classmethod
    def create(
        cls,
        *,
        boundary: RunnerBoundaryV2,
        lease: ExecutionLease,
        policy: CredentialBrokerPolicyV2,
        decision_revision: str,
    ) -> Self:
        if not isinstance(boundary, RunnerBoundaryV2):
            raise ValueError("boundary must be RunnerBoundaryV2")
        if not isinstance(lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")
        if not isinstance(policy, CredentialBrokerPolicyV2):
            raise ValueError("policy must be CredentialBrokerPolicyV2")
        _require_text(decision_revision, field="decision_revision")

        if boundary.lease_id != lease.lease_id or boundary.lease_digest != lease.lease_digest:
            raise WriteCredentialDenied("F2_CREDENTIAL_LEASE_BINDING_MISMATCH")
        if boundary.execution_id != lease.execution_id or boundary.execution_epoch != lease.execution_epoch:
            raise WriteCredentialDenied("F2_CREDENTIAL_EXECUTION_BINDING_MISMATCH")
        if boundary.execution_capsule_digest != lease.execution_capsule_digest:
            raise WriteCredentialDenied("F2_CREDENTIAL_CAPSULE_BINDING_MISMATCH")
        expected_policy = {
            "credential_class": boundary.credential_class,
            "capability_definition_identity": boundary.capability_definition_identity,
            "controlled_write_requirement_digest": boundary.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": boundary.atomic_provider_condition_contract_identity,
            "environment": boundary.environment,
            "access_mode": WRITE_BOUNDED_ACCESS_MODE,
            "provider_operation": CREATE_REF_OPERATION,
            "provider_mutation_allowed": True,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
        }
        actual_policy = {
            "credential_class": policy.credential_class,
            "capability_definition_identity": policy.capability_definition_identity,
            "controlled_write_requirement_digest": policy.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": policy.atomic_provider_condition_contract_identity,
            "environment": policy.environment,
            "access_mode": policy.access_mode,
            "provider_operation": policy.provider_operation,
            "provider_mutation_allowed": policy.provider_mutation_allowed,
            "max_provider_mutations": policy.max_provider_mutations,
        }
        if actual_policy != expected_policy:
            raise WriteCredentialDenied("F2_CREDENTIAL_POLICY_BINDING_MISMATCH")

        valid_from_text, valid_from = _require_timestamp(lease.acquired_at, field="lease.acquired_at")
        _, lease_expires = _require_timestamp(lease.expires_at, field="lease.expires_at")
        policy_expires = valid_from + timedelta(seconds=policy.max_ttl_seconds)
        expires = min(lease_expires, policy_expires)
        expires_at = expires.isoformat(timespec="milliseconds")
        if expires <= valid_from:
            raise WriteCredentialDenied("F2_CREDENTIAL_LIFETIME_INVALID")

        decision_id = _digest(
            {
                "identity_type": CREDENTIAL_ACCESS_DECISION_IDENTITY_V2_TYPE,
                "runner_boundary_digest": boundary.boundary_digest,
                "lease_digest": lease.lease_digest,
                "policy_digest": policy.policy_digest,
            }
        )
        claims = {
            "schema_version": 2,
            "decision_type": CREDENTIAL_ACCESS_DECISION_V2_TYPE,
            "decision_id": decision_id,
            "runner_boundary_digest": boundary.boundary_digest,
            "runner_id": boundary.runner_id,
            "runner_identity_digest": boundary.runner_identity_digest,
            "lease_id": lease.lease_id,
            "lease_digest": lease.lease_digest,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "execution_capsule_digest": boundary.execution_capsule_digest,
            "capability_definition_identity": boundary.capability_definition_identity,
            "controlled_write_requirement_digest": boundary.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": boundary.atomic_provider_condition_contract_identity,
            "credential_class": boundary.credential_class,
            "provider": policy.provider,
            "audience": policy.audience,
            "environment": boundary.environment,
            "access_mode": WRITE_BOUNDED_ACCESS_MODE,
            "provider_operation": CREATE_REF_OPERATION,
            "provider_mutation_allowed": True,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "valid_from": valid_from_text,
            "expires_at": expires_at,
            "policy_digest": policy.policy_digest,
            "policy_revision": policy.policy_revision,
            "decision_revision": decision_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "decision_type"}
        }
        return cls(**values, decision_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _DECISION_FIELDS, contract=CREDENTIAL_ACCESS_DECISION_V2_TYPE)
        if value["schema_version"] != 2 or value["decision_type"] != CREDENTIAL_ACCESS_DECISION_V2_TYPE:
            raise ValueError("credential-access-decision/v2 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _DECISION_FIELDS
                if key not in {"schema_version", "decision_type"}
            }
        )

    def assert_bound_to(
        self,
        *,
        boundary: RunnerBoundaryV2,
        lease: ExecutionLease,
        policy: CredentialBrokerPolicyV2,
    ) -> None:
        expected = CredentialAccessDecisionV2.create(
            boundary=boundary,
            lease=lease,
            policy=policy,
            decision_revision=self.decision_revision,
        )
        if self != expected:
            raise WriteCredentialDenied("F2_CREDENTIAL_DECISION_BINDING_MISMATCH")

    def _logical_identity(self) -> str:
        return _digest(
            {
                "identity_type": CREDENTIAL_ACCESS_DECISION_IDENTITY_V2_TYPE,
                "runner_boundary_digest": self.runner_boundary_digest,
                "lease_digest": self.lease_digest,
                "policy_digest": self.policy_digest,
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "decision_type": CREDENTIAL_ACCESS_DECISION_V2_TYPE,
            "decision_id": self.decision_id,
            "runner_boundary_digest": self.runner_boundary_digest,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "lease_id": self.lease_id,
            "lease_digest": self.lease_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "controlled_write_requirement_digest": self.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": self.atomic_provider_condition_contract_identity,
            "credential_class": self.credential_class,
            "provider": self.provider,
            "audience": self.audience,
            "environment": self.environment,
            "access_mode": self.access_mode,
            "provider_operation": self.provider_operation,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "max_provider_mutations": self.max_provider_mutations,
            "valid_from": self.valid_from,
            "expires_at": self.expires_at,
            "policy_digest": self.policy_digest,
            "policy_revision": self.policy_revision,
            "decision_revision": self.decision_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "decision_digest": self.decision_digest}
