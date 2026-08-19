from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Self

from .capability_registry import CapabilityDefinition
from .controlled_write import (
    MAX_PROVIDER_MUTATIONS_R1,
    MUTATION_REVERSIBLE_EFFECT_CLASS,
    PROVIDER_READ_VERIFICATION_CLASS,
    STAGING_ENVIRONMENT,
    VONE_CANARY_REF_PREFIX,
)
from .evidence_primitives import canonical_json
from .execution_capsule import ExecutionCapsule
from .execution_conformance import HandlerConformanceEvidence
from .execution_contract import ExecutionTarget
from .execution_lease import ExecutionLease
from .github_read_provider import GITHUB_REF_TARGET_KIND
from .precondition_witness import READ_THEN_COMPARE
from .runner_identity import DENY_ALL_NETWORK_DEFAULT, RunnerIdentity

ROLLBACK_WRITE_REQUIREMENT_TYPE: Final = "rollback-write-requirement/v1"
GITHUB_DELETE_REF_CONDITION_TYPE: Final = "github-delete-exact-created-ref-condition/v1"
RUNNER_BOUNDARY_V3_TYPE: Final = "runner-boundary/v3"
CREDENTIAL_BROKER_POLICY_V3_TYPE: Final = "credential-broker-policy/v3"
CREDENTIAL_ACCESS_DECISION_V3_TYPE: Final = "credential-access-decision/v3"
CREDENTIAL_ACCESS_DECISION_IDENTITY_V3_TYPE: Final = "credential-access-decision-id/v3"
GITHUB_DELETE_REF_REQUEST_TYPE: Final = "github-delete-exact-created-ref-request/v1"
GITHUB_DELETE_REF_RESPONSE_TYPE: Final = "github-delete-ref-provider-response/v1"

GITHUB_DELETE_REF_CAPABILITY: Final = "github.delete-exact-created-ref/v1"
GITHUB_DELETE_REF_BINDER_ID: Final = "github-delete-exact-created-ref-target-binder/v1"
GITHUB_DELETE_REF_HANDLER: Final = "github-delete-exact-created-ref-handler/v1"
GITHUB_DELETE_REF_CREDENTIAL_CLASS: Final = "github.delete-ref/scoped-v1"
WRITE_RUNNER_CLASS: Final = "github-actions.docker-isolated-write/v1"
WRITE_BOUNDED_ACCESS_MODE: Final = "WRITE_BOUNDED"
GITHUB_PROVIDER: Final = "github"
GITHUB_API_AUDIENCE: Final = "api.github.com"
DELETE_REF_OPERATION: Final = "DELETE_REF"
READ_THEN_DELETE_NON_ATOMIC: Final = "READ_THEN_DELETE_NON_ATOMIC"
DELETE_EXACT_TARGET_ONLY: Final = "DELETE_EXACT_TARGET_ONLY"
RECREATE_EXACT_DELETED_REF_SEPARATE_AUTHORITY: Final = (
    "RECREATE_EXACT_DELETED_REF_SEPARATE_AUTHORITY"
)
MAX_WRITE_CREDENTIAL_TTL_SECONDS: Final = 300

_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_SHA1 = re.compile(r"[0-9a-f]{40}")


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _hex_digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if len(text) != 64 or text.casefold() != text or any(c not in "0123456789abcdef" for c in text):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _sha1(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _SHA1.fullmatch(text) is None:
        raise ValueError(f"{field} must be a lowercase 40-character Git object id")
    return text


def _repository(value: object) -> str:
    text = _text(value, field="repository")
    if _REPOSITORY.fullmatch(text) is None:
        raise ValueError("repository must use owner/name form")
    return text


def _canary_ref(value: object) -> str:
    ref = _text(value, field="ref")
    if not ref.startswith(VONE_CANARY_REF_PREFIX):
        raise ValueError("rollback ref must remain inside V-One canary namespace")
    suffix = ref.removeprefix(VONE_CANARY_REF_PREFIX)
    if (
        not suffix
        or suffix.startswith("/")
        or suffix.endswith("/")
        or "//" in suffix
        or ".." in suffix
        or "@{" in suffix
        or "\\" in suffix
        or any(ch.isspace() or ord(ch) < 32 or ch in "~^:?*[" for ch in suffix)
    ):
        raise ValueError("rollback ref is invalid")
    return ref


def _timestamp(value: object, *, field: str) -> datetime:
    text = _text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class GitHubDeleteRefConditionContract:
    repository: str
    ref: str
    expected_sha: str
    original_create_response_digest: str
    original_verification_result_digest: str
    provider: str
    operation: str
    target_kind: str
    temporal_model: str
    delete_semantics: str
    verification_class: str
    contract_revision: str
    contract_digest: str

    def __post_init__(self) -> None:
        _repository(self.repository)
        _canary_ref(self.ref)
        _sha1(self.expected_sha, field="expected_sha")
        _hex_digest(self.original_create_response_digest, field="original_create_response_digest")
        _hex_digest(self.original_verification_result_digest, field="original_verification_result_digest")
        for field in ("provider", "operation", "target_kind", "temporal_model", "delete_semantics", "verification_class", "contract_revision"):
            _text(getattr(self, field), field=field)
        if self.provider != GITHUB_PROVIDER or self.operation != DELETE_REF_OPERATION:
            raise ValueError("rollback provider operation must be GitHub DELETE_REF")
        if self.target_kind != GITHUB_REF_TARGET_KIND:
            raise ValueError("rollback target kind must be git_ref")
        if self.temporal_model != READ_THEN_DELETE_NON_ATOMIC:
            raise ValueError("rollback must disclose READ_THEN_DELETE_NON_ATOMIC semantics")
        if self.delete_semantics != DELETE_EXACT_TARGET_ONLY:
            raise ValueError("rollback delete semantics are unsupported")
        if self.verification_class != PROVIDER_READ_VERIFICATION_CLASS:
            raise ValueError("rollback verification must use provider readback")
        if self.contract_digest != _digest(self._claims()):
            raise ValueError("contract_digest does not match delete-ref condition")

    @classmethod
    def create(
        cls,
        *,
        repository: str,
        ref: str,
        expected_sha: str,
        original_create_response_digest: str,
        original_verification_result_digest: str,
        contract_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "condition_type": GITHUB_DELETE_REF_CONDITION_TYPE,
            "repository": _repository(repository),
            "ref": _canary_ref(ref),
            "expected_sha": _sha1(expected_sha, field="expected_sha"),
            "original_create_response_digest": _hex_digest(original_create_response_digest, field="original_create_response_digest"),
            "original_verification_result_digest": _hex_digest(original_verification_result_digest, field="original_verification_result_digest"),
            "provider": GITHUB_PROVIDER,
            "operation": DELETE_REF_OPERATION,
            "target_kind": GITHUB_REF_TARGET_KIND,
            "temporal_model": READ_THEN_DELETE_NON_ATOMIC,
            "delete_semantics": DELETE_EXACT_TARGET_ONLY,
            "verification_class": PROVIDER_READ_VERIFICATION_CLASS,
            "contract_revision": _text(contract_revision, field="contract_revision"),
        }
        values = {k: v for k, v in claims.items() if k not in {"schema_version", "condition_type"}}
        return cls(**values, contract_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "condition_type": GITHUB_DELETE_REF_CONDITION_TYPE,
            "repository": self.repository,
            "ref": self.ref,
            "expected_sha": self.expected_sha,
            "original_create_response_digest": self.original_create_response_digest,
            "original_verification_result_digest": self.original_verification_result_digest,
            "provider": self.provider,
            "operation": self.operation,
            "target_kind": self.target_kind,
            "temporal_model": self.temporal_model,
            "delete_semantics": self.delete_semantics,
            "verification_class": self.verification_class,
            "contract_revision": self.contract_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "contract_digest": self.contract_digest}


class GitHubDeleteRefTargetBinder:
    binder_id = GITHUB_DELETE_REF_BINDER_ID
    target_kind = GITHUB_REF_TARGET_KIND

    def bind(self, *, approved_payload: Mapping[str, Any]) -> ExecutionTarget:
        if not isinstance(approved_payload, Mapping):
            raise ValueError("approved_payload must be an object")
        expected = {
            "repository",
            "ref",
            "expected_sha",
            "original_create_response_digest",
            "original_verification_result_digest",
        }
        if set(approved_payload) != expected:
            raise ValueError("rollback approved payload fields are invalid")
        return ExecutionTarget.create(
            target_kind=GITHUB_REF_TARGET_KIND,
            target_claims={
                "repository": _repository(approved_payload["repository"]),
                "ref": _canary_ref(approved_payload["ref"]),
                "expected_sha": _sha1(approved_payload["expected_sha"], field="expected_sha"),
                "original_create_response_digest": _hex_digest(approved_payload["original_create_response_digest"], field="original_create_response_digest"),
                "original_verification_result_digest": _hex_digest(approved_payload["original_verification_result_digest"], field="original_verification_result_digest"),
            },
        )


@dataclass(frozen=True, slots=True)
class RollbackWriteRequirement:
    capability_definition_identity: str
    execution_capsule_digest: str
    handler_conformance_evidence_digest: str
    condition_contract_digest: str
    verification_contract_identity: str
    effect_class: str
    precondition_enforcement_class: str
    temporal_model: str
    max_provider_mutations: int
    provider_mutation_allowed: bool
    rollback_strategy: str
    requirement_revision: str
    requirement_digest: str

    def __post_init__(self) -> None:
        for field in ("capability_definition_identity", "execution_capsule_digest", "handler_conformance_evidence_digest", "condition_contract_digest", "verification_contract_identity", "requirement_digest"):
            _hex_digest(getattr(self, field), field=field)
        for field in ("effect_class", "precondition_enforcement_class", "temporal_model", "rollback_strategy", "requirement_revision"):
            _text(getattr(self, field), field=field)
        if self.effect_class != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise ValueError("rollback effect class must be mutation.reversible")
        if self.precondition_enforcement_class != READ_THEN_COMPARE:
            raise ValueError("rollback requires READ_THEN_COMPARE")
        if self.temporal_model != READ_THEN_DELETE_NON_ATOMIC:
            raise ValueError("rollback must be explicitly non-atomic")
        if self.max_provider_mutations != 1 or self.provider_mutation_allowed is not True:
            raise ValueError("rollback allows exactly one provider mutation")
        if self.rollback_strategy != RECREATE_EXACT_DELETED_REF_SEPARATE_AUTHORITY:
            raise ValueError("rollback-of-rollback strategy is unsupported")
        if self.requirement_digest != _digest(self._claims()):
            raise ValueError("requirement_digest does not match rollback requirement")

    @classmethod
    def create(
        cls,
        *,
        definition: CapabilityDefinition,
        capsule: ExecutionCapsule,
        handler_evidence: HandlerConformanceEvidence,
        condition: GitHubDeleteRefConditionContract,
        requirement_revision: str,
    ) -> Self:
        if definition.capability != GITHUB_DELETE_REF_CAPABILITY:
            raise PermissionError("ROLLBACK_CAPABILITY_MISMATCH")
        if definition.target_kind != GITHUB_REF_TARGET_KIND or definition.binder_id != GITHUB_DELETE_REF_BINDER_ID:
            raise PermissionError("ROLLBACK_TARGET_BINDING_MISMATCH")
        if definition.handler_id != GITHUB_DELETE_REF_HANDLER:
            raise PermissionError("ROLLBACK_HANDLER_MISMATCH")
        if definition.effect_class != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise PermissionError("ROLLBACK_EFFECT_CLASS_MISMATCH")
        if definition.verification_class != PROVIDER_READ_VERIFICATION_CLASS:
            raise PermissionError("ROLLBACK_VERIFICATION_CLASS_MISMATCH")
        if definition.production_eligible or definition.supported_environments != (STAGING_ENVIRONMENT,):
            raise PermissionError("ROLLBACK_ENVIRONMENT_NOT_STAGING_ONLY")
        if capsule.capability_definition_identity != definition.definition_identity:
            raise PermissionError("ROLLBACK_CAPSULE_DEFINITION_MISMATCH")
        if capsule.handler_id != definition.handler_id or capsule.target_kind != definition.target_kind:
            raise PermissionError("ROLLBACK_CAPSULE_BINDING_MISMATCH")
        if capsule.precondition_enforcement_class != READ_THEN_COMPARE:
            raise PermissionError("ROLLBACK_CAPSULE_MUST_READ_THEN_COMPARE")
        if handler_evidence.execution_capsule_digest != capsule.capsule_digest:
            raise PermissionError("ROLLBACK_HANDLER_EVIDENCE_CAPSULE_MISMATCH")
        if handler_evidence.precondition_enforcement_class != READ_THEN_COMPARE:
            raise PermissionError("ROLLBACK_HANDLER_EVIDENCE_MUST_READ_THEN_COMPARE")
        if handler_evidence.atomic_provider_condition_contract_identity is not None:
            raise PermissionError("ROLLBACK_MUST_NOT_CLAIM_ATOMIC_PROVIDER_CONDITION")
        claims = {
            "schema_version": 1,
            "requirement_type": ROLLBACK_WRITE_REQUIREMENT_TYPE,
            "capability_definition_identity": definition.definition_identity,
            "execution_capsule_digest": capsule.capsule_digest,
            "handler_conformance_evidence_digest": handler_evidence.evidence_digest,
            "condition_contract_digest": condition.contract_digest,
            "verification_contract_identity": capsule.verification_contract_identity,
            "effect_class": MUTATION_REVERSIBLE_EFFECT_CLASS,
            "precondition_enforcement_class": READ_THEN_COMPARE,
            "temporal_model": READ_THEN_DELETE_NON_ATOMIC,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "provider_mutation_allowed": True,
            "rollback_strategy": RECREATE_EXACT_DELETED_REF_SEPARATE_AUTHORITY,
            "requirement_revision": _text(requirement_revision, field="requirement_revision"),
        }
        values = {k: v for k, v in claims.items() if k not in {"schema_version", "requirement_type"}}
        return cls(**values, requirement_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "requirement_type": ROLLBACK_WRITE_REQUIREMENT_TYPE,
            "capability_definition_identity": self.capability_definition_identity,
            "execution_capsule_digest": self.execution_capsule_digest,
            "handler_conformance_evidence_digest": self.handler_conformance_evidence_digest,
            "condition_contract_digest": self.condition_contract_digest,
            "verification_contract_identity": self.verification_contract_identity,
            "effect_class": self.effect_class,
            "precondition_enforcement_class": self.precondition_enforcement_class,
            "temporal_model": self.temporal_model,
            "max_provider_mutations": self.max_provider_mutations,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "rollback_strategy": self.rollback_strategy,
            "requirement_revision": self.requirement_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "requirement_digest": self.requirement_digest}


@dataclass(frozen=True, slots=True)
class RunnerBoundaryV3:
    runner_id: str
    runner_identity_digest: str
    lease_id: str
    lease_digest: str
    admission_id: str
    execution_id: str
    execution_epoch: int
    execution_capsule_digest: str
    capability_definition_identity: str
    rollback_requirement_digest: str
    condition_contract_digest: str
    verification_contract_identity: str
    environment: str
    runner_class: str
    credential_class: str
    effect_ceiling: str
    network_egress_default: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    temporal_model: str
    boundary_revision: str
    boundary_digest: str

    def __post_init__(self) -> None:
        for field in ("runner_id", "runner_identity_digest", "lease_id", "lease_digest", "admission_id", "execution_capsule_digest", "capability_definition_identity", "rollback_requirement_digest", "condition_contract_digest", "verification_contract_identity", "boundary_digest"):
            _hex_digest(getattr(self, field), field=field)
        for field in ("execution_id", "environment", "runner_class", "credential_class", "effect_ceiling", "network_egress_default", "temporal_model", "boundary_revision"):
            _text(getattr(self, field), field=field)
        if self.execution_epoch < 1 or isinstance(self.execution_epoch, bool):
            raise ValueError("execution_epoch must be >= 1")
        if self.environment != STAGING_ENVIRONMENT or self.runner_class != WRITE_RUNNER_CLASS:
            raise ValueError("rollback runner boundary is staging write-runtime only")
        if self.credential_class != GITHUB_DELETE_REF_CREDENTIAL_CLASS:
            raise ValueError("rollback credential class is invalid")
        if self.effect_ceiling != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise ValueError("rollback effect ceiling is invalid")
        if self.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise ValueError("rollback network default must be DENY_ALL")
        if self.provider_mutation_allowed is not True or self.max_provider_mutations != 1:
            raise ValueError("rollback boundary allows exactly one mutation")
        if self.temporal_model != READ_THEN_DELETE_NON_ATOMIC:
            raise ValueError("rollback boundary must disclose non-atomic temporal model")
        if self.boundary_digest != _digest(self._claims()):
            raise ValueError("boundary_digest does not match runner-boundary/v3")

    @classmethod
    def create(cls, *, identity: RunnerIdentity, lease: ExecutionLease, capsule: ExecutionCapsule, definition: CapabilityDefinition, requirement: RollbackWriteRequirement, condition: GitHubDeleteRefConditionContract, boundary_revision: str) -> Self:
        identity.assert_bound_to_lease(lease)
        if identity.runner_class != WRITE_RUNNER_CLASS:
            raise PermissionError("ROLLBACK_RUNNER_CLASS_MISMATCH")
        if lease.environment != STAGING_ENVIRONMENT or capsule.capsule_digest != lease.execution_capsule_digest:
            raise PermissionError("ROLLBACK_LEASE_CAPSULE_MISMATCH")
        if capsule.credential_class != GITHUB_DELETE_REF_CREDENTIAL_CLASS or capsule.precondition_enforcement_class != READ_THEN_COMPARE:
            raise PermissionError("ROLLBACK_CAPSULE_RUNTIME_MISMATCH")
        if definition.definition_identity != capsule.capability_definition_identity:
            raise PermissionError("ROLLBACK_DEFINITION_CAPSULE_MISMATCH")
        if requirement.capability_definition_identity != definition.definition_identity or requirement.execution_capsule_digest != capsule.capsule_digest:
            raise PermissionError("ROLLBACK_REQUIREMENT_BINDING_MISMATCH")
        if requirement.condition_contract_digest != condition.contract_digest:
            raise PermissionError("ROLLBACK_CONDITION_BINDING_MISMATCH")
        claims = {
            "schema_version": 3,
            "boundary_type": RUNNER_BOUNDARY_V3_TYPE,
            "runner_id": identity.runner_id,
            "runner_identity_digest": identity.identity_digest,
            "lease_id": lease.lease_id,
            "lease_digest": lease.lease_digest,
            "admission_id": lease.admission_id,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "execution_capsule_digest": capsule.capsule_digest,
            "capability_definition_identity": definition.definition_identity,
            "rollback_requirement_digest": requirement.requirement_digest,
            "condition_contract_digest": condition.contract_digest,
            "verification_contract_identity": capsule.verification_contract_identity,
            "environment": lease.environment,
            "runner_class": identity.runner_class,
            "credential_class": capsule.credential_class,
            "effect_ceiling": MUTATION_REVERSIBLE_EFFECT_CLASS,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "provider_mutation_allowed": True,
            "max_provider_mutations": 1,
            "temporal_model": READ_THEN_DELETE_NON_ATOMIC,
            "boundary_revision": _text(boundary_revision, field="boundary_revision"),
        }
        values = {k: v for k, v in claims.items() if k not in {"schema_version", "boundary_type"}}
        return cls(**values, boundary_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {"schema_version": 3, "boundary_type": RUNNER_BOUNDARY_V3_TYPE, **{field: getattr(self, field) for field in self.__dataclass_fields__ if field != "boundary_digest"}}

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "boundary_digest": self.boundary_digest}


@dataclass(frozen=True, slots=True)
class CredentialBrokerPolicyV3:
    credential_class: str
    provider: str
    audience: str
    capability_definition_identity: str
    rollback_requirement_digest: str
    environment: str
    access_mode: str
    provider_operation: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    max_ttl_seconds: int
    policy_revision: str
    policy_digest: str

    def __post_init__(self) -> None:
        for field in ("capability_definition_identity", "rollback_requirement_digest", "policy_digest"):
            _hex_digest(getattr(self, field), field=field)
        if self.credential_class != GITHUB_DELETE_REF_CREDENTIAL_CLASS or self.provider != GITHUB_PROVIDER or self.audience != GITHUB_API_AUDIENCE:
            raise ValueError("rollback credential policy provider/class/audience is invalid")
        if self.environment != STAGING_ENVIRONMENT or self.access_mode != WRITE_BOUNDED_ACCESS_MODE or self.provider_operation != DELETE_REF_OPERATION:
            raise ValueError("rollback credential policy scope is invalid")
        if self.provider_mutation_allowed is not True or self.max_provider_mutations != 1:
            raise ValueError("rollback credential policy allows exactly one mutation")
        if type(self.max_ttl_seconds) is not int or not 1 <= self.max_ttl_seconds <= MAX_WRITE_CREDENTIAL_TTL_SECONDS:
            raise ValueError("rollback credential policy TTL is invalid")
        _text(self.policy_revision, field="policy_revision")
        if self.policy_digest != _digest(self._claims()):
            raise ValueError("policy_digest does not match credential-broker-policy/v3")

    @classmethod
    def create(cls, *, definition: CapabilityDefinition, requirement: RollbackWriteRequirement, max_ttl_seconds: int, policy_revision: str) -> Self:
        if definition.definition_identity != requirement.capability_definition_identity:
            raise PermissionError("ROLLBACK_POLICY_DEFINITION_MISMATCH")
        claims = {
            "schema_version": 3,
            "policy_type": CREDENTIAL_BROKER_POLICY_V3_TYPE,
            "credential_class": GITHUB_DELETE_REF_CREDENTIAL_CLASS,
            "provider": GITHUB_PROVIDER,
            "audience": GITHUB_API_AUDIENCE,
            "capability_definition_identity": definition.definition_identity,
            "rollback_requirement_digest": requirement.requirement_digest,
            "environment": STAGING_ENVIRONMENT,
            "access_mode": WRITE_BOUNDED_ACCESS_MODE,
            "provider_operation": DELETE_REF_OPERATION,
            "provider_mutation_allowed": True,
            "max_provider_mutations": 1,
            "max_ttl_seconds": max_ttl_seconds,
            "policy_revision": _text(policy_revision, field="policy_revision"),
        }
        values = {k: v for k, v in claims.items() if k not in {"schema_version", "policy_type"}}
        return cls(**values, policy_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {"schema_version": 3, "policy_type": CREDENTIAL_BROKER_POLICY_V3_TYPE, **{field: getattr(self, field) for field in self.__dataclass_fields__ if field != "policy_digest"}}

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "policy_digest": self.policy_digest}


@dataclass(frozen=True, slots=True)
class CredentialAccessDecisionV3:
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
    rollback_requirement_digest: str
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
        for field in ("decision_id", "runner_boundary_digest", "runner_id", "runner_identity_digest", "lease_id", "lease_digest", "execution_capsule_digest", "capability_definition_identity", "rollback_requirement_digest", "policy_digest", "decision_digest"):
            _hex_digest(getattr(self, field), field=field)
        for field in ("execution_id", "credential_class", "provider", "audience", "environment", "access_mode", "provider_operation", "policy_revision", "decision_revision"):
            _text(getattr(self, field), field=field)
        if self.execution_epoch < 1 or isinstance(self.execution_epoch, bool):
            raise ValueError("execution_epoch must be >= 1")
        start, end = _timestamp(self.valid_from, field="valid_from"), _timestamp(self.expires_at, field="expires_at")
        if end <= start:
            raise ValueError("rollback credential decision expiry is invalid")
        if self.credential_class != GITHUB_DELETE_REF_CREDENTIAL_CLASS or self.provider != GITHUB_PROVIDER or self.audience != GITHUB_API_AUDIENCE:
            raise ValueError("rollback credential decision provider/class/audience is invalid")
        if self.environment != STAGING_ENVIRONMENT or self.access_mode != WRITE_BOUNDED_ACCESS_MODE or self.provider_operation != DELETE_REF_OPERATION:
            raise ValueError("rollback credential decision scope is invalid")
        if self.provider_mutation_allowed is not True or self.max_provider_mutations != 1:
            raise ValueError("rollback credential decision allows exactly one mutation")
        if self.decision_digest != _digest(self._claims()):
            raise ValueError("decision_digest does not match credential-access-decision/v3")

    @classmethod
    def create(cls, *, boundary: RunnerBoundaryV3, policy: CredentialBrokerPolicyV3, valid_from: str, expires_at: str, decision_revision: str) -> Self:
        start, end = _timestamp(valid_from, field="valid_from"), _timestamp(expires_at, field="expires_at")
        if end <= start or end - start > timedelta(seconds=policy.max_ttl_seconds):
            raise PermissionError("ROLLBACK_CREDENTIAL_TTL_EXCEEDS_POLICY")
        if boundary.capability_definition_identity != policy.capability_definition_identity or boundary.rollback_requirement_digest != policy.rollback_requirement_digest:
            raise PermissionError("ROLLBACK_CREDENTIAL_POLICY_BINDING_MISMATCH")
        if boundary.credential_class != policy.credential_class:
            raise PermissionError("ROLLBACK_CREDENTIAL_CLASS_MISMATCH")
        base = {
            "runner_boundary_digest": boundary.boundary_digest,
            "runner_id": boundary.runner_id,
            "runner_identity_digest": boundary.runner_identity_digest,
            "lease_id": boundary.lease_id,
            "lease_digest": boundary.lease_digest,
            "execution_id": boundary.execution_id,
            "execution_epoch": boundary.execution_epoch,
            "execution_capsule_digest": boundary.execution_capsule_digest,
            "capability_definition_identity": boundary.capability_definition_identity,
            "rollback_requirement_digest": boundary.rollback_requirement_digest,
            "credential_class": policy.credential_class,
            "provider": policy.provider,
            "audience": policy.audience,
            "environment": policy.environment,
            "access_mode": policy.access_mode,
            "provider_operation": policy.provider_operation,
            "provider_mutation_allowed": True,
            "max_provider_mutations": 1,
            "valid_from": valid_from,
            "expires_at": expires_at,
            "policy_digest": policy.policy_digest,
            "policy_revision": policy.policy_revision,
            "decision_revision": _text(decision_revision, field="decision_revision"),
        }
        decision_id = _digest({"decision_type": CREDENTIAL_ACCESS_DECISION_IDENTITY_V3_TYPE, "runner_boundary_digest": boundary.boundary_digest, "policy_digest": policy.policy_digest, "valid_from": valid_from, "expires_at": expires_at})
        claims = {"schema_version": 3, "decision_type": CREDENTIAL_ACCESS_DECISION_V3_TYPE, "decision_id": decision_id, **base}
        return cls(decision_id=decision_id, **base, decision_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {"schema_version": 3, "decision_type": CREDENTIAL_ACCESS_DECISION_V3_TYPE, **{field: getattr(self, field) for field in self.__dataclass_fields__ if field != "decision_digest"}}

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "decision_digest": self.decision_digest}


@dataclass(frozen=True, slots=True)
class GitHubDeleteRefRequest:
    repository: str
    ref: str
    expected_sha: str
    target_digest: str
    runner_boundary_digest: str
    credential_decision_digest: str
    condition_contract_digest: str
    request_revision: str
    request_digest: str

    def __post_init__(self) -> None:
        _repository(self.repository)
        _canary_ref(self.ref)
        _sha1(self.expected_sha, field="expected_sha")
        for field in ("target_digest", "runner_boundary_digest", "credential_decision_digest", "condition_contract_digest", "request_digest"):
            _hex_digest(getattr(self, field), field=field)
        _text(self.request_revision, field="request_revision")
        if self.request_digest != _digest(self._claims()):
            raise ValueError("request_digest does not match delete-ref request")

    @classmethod
    def create(cls, *, target: ExecutionTarget, boundary: RunnerBoundaryV3, decision: CredentialAccessDecisionV3, condition: GitHubDeleteRefConditionContract, request_revision: str) -> Self:
        claims = target.target_claims
        expected = {"repository", "ref", "expected_sha", "original_create_response_digest", "original_verification_result_digest"}
        if target.target_kind != GITHUB_REF_TARGET_KIND or set(claims) != expected:
            raise PermissionError("ROLLBACK_REQUEST_TARGET_INVALID")
        if claims["repository"] != condition.repository or claims["ref"] != condition.ref or claims["expected_sha"] != condition.expected_sha:
            raise PermissionError("ROLLBACK_REQUEST_CONDITION_TARGET_MISMATCH")
        if claims["original_create_response_digest"] != condition.original_create_response_digest or claims["original_verification_result_digest"] != condition.original_verification_result_digest:
            raise PermissionError("ROLLBACK_REQUEST_PROVENANCE_MISMATCH")
        if boundary.condition_contract_digest != condition.contract_digest or decision.runner_boundary_digest != boundary.boundary_digest:
            raise PermissionError("ROLLBACK_REQUEST_AUTHORITY_BINDING_MISMATCH")
        payload = {
            "schema_version": 1,
            "request_type": GITHUB_DELETE_REF_REQUEST_TYPE,
            "repository": condition.repository,
            "ref": condition.ref,
            "expected_sha": condition.expected_sha,
            "target_digest": target.target_digest,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_digest": decision.decision_digest,
            "condition_contract_digest": condition.contract_digest,
            "request_revision": _text(request_revision, field="request_revision"),
        }
        values = {k: v for k, v in payload.items() if k not in {"schema_version", "request_type"}}
        return cls(**values, request_digest=_digest(payload))

    def _claims(self) -> dict[str, Any]:
        return {"schema_version": 1, "request_type": GITHUB_DELETE_REF_REQUEST_TYPE, **{field: getattr(self, field) for field in self.__dataclass_fields__ if field != "request_digest"}}

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "request_digest": self.request_digest}


@dataclass(frozen=True, slots=True)
class GitHubDeleteRefProviderResponse:
    http_status: int
    deleted_ref: str
    expected_sha: str
    source_identity: str
    response_revision: str
    response_digest: str

    def __post_init__(self) -> None:
        if self.http_status != 204:
            raise ValueError("successful delete-ref response must be HTTP 204")
        _canary_ref(self.deleted_ref)
        _sha1(self.expected_sha, field="expected_sha")
        _text(self.source_identity, field="source_identity")
        _text(self.response_revision, field="response_revision")
        if self.response_digest != _digest(self._claims()):
            raise ValueError("response_digest does not match delete-ref response")

    @classmethod
    def deleted(cls, *, ref: str, expected_sha: str, source_identity: str, response_revision: str) -> Self:
        claims = {"schema_version": 1, "response_type": GITHUB_DELETE_REF_RESPONSE_TYPE, "http_status": 204, "deleted_ref": _canary_ref(ref), "expected_sha": _sha1(expected_sha, field="expected_sha"), "source_identity": _text(source_identity, field="source_identity"), "response_revision": _text(response_revision, field="response_revision")}
        values = {k: v for k, v in claims.items() if k not in {"schema_version", "response_type"}}
        return cls(**values, response_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {"schema_version": 1, "response_type": GITHUB_DELETE_REF_RESPONSE_TYPE, "http_status": self.http_status, "deleted_ref": self.deleted_ref, "expected_sha": self.expected_sha, "source_identity": self.source_identity, "response_revision": self.response_revision}

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "response_digest": self.response_digest}


class GitHubDeleteRefHandlerContract:
    def prepare_request(self, *, target: ExecutionTarget, boundary: RunnerBoundaryV3, decision: CredentialAccessDecisionV3, condition: GitHubDeleteRefConditionContract, request_revision: str) -> GitHubDeleteRefRequest:
        return GitHubDeleteRefRequest.create(target=target, boundary=boundary, decision=decision, condition=condition, request_revision=request_revision)

    def interpret_response(self, *, request: GitHubDeleteRefRequest, response: GitHubDeleteRefProviderResponse) -> GitHubDeleteRefProviderResponse:
        if response.deleted_ref != request.ref or response.expected_sha != request.expected_sha:
            raise PermissionError("ROLLBACK_PROVIDER_RESPONSE_MISMATCH")
        return response