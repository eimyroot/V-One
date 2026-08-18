from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Self

from .capability_registry import CapabilityDefinition
from .evidence_primitives import canonical_json
from .execution_capsule import ExecutionCapsule
from .execution_conformance import HandlerConformanceEvidence
from .github_read_provider import GITHUB_REF_TARGET_KIND
from .precondition_witness import ATOMIC_PROVIDER_CONDITION

CONTROLLED_WRITE_REQUIREMENT_TYPE: Final = "controlled-write-requirement/v1"
GITHUB_CREATE_REF_CONDITION_TYPE: Final = "github-create-ref-condition/v1"

GITHUB_CREATE_REF_CAPABILITY: Final = "github.create-ref/v1"
GITHUB_CREATE_REF_HANDLER: Final = "github-create-ref-handler/v1"
MUTATION_REVERSIBLE_EFFECT_CLASS: Final = "mutation.reversible"
PROVIDER_READ_VERIFICATION_CLASS: Final = "provider-read/v1"
STAGING_ENVIRONMENT: Final = "staging"

CREATE_REF_OPERATION: Final = "CREATE_REF"
CREATE_ONLY_SEMANTICS: Final = "CREATE_ONLY"
DELETE_EXACT_CREATED_REF_ROLLBACK: Final = "DELETE_EXACT_CREATED_REF"
VONE_CANARY_REF_PREFIX: Final = "refs/heads/vone-canary/"
MAX_PROVIDER_MUTATIONS_R1: Final = 1

_CONDITION_FIELDS = frozenset(
    {
        "schema_version",
        "condition_type",
        "provider",
        "operation",
        "target_kind",
        "ref_namespace_prefix",
        "create_semantics",
        "overwrite_existing_ref_allowed",
        "force_update_allowed",
        "rollback_strategy",
        "verification_class",
        "contract_revision",
        "contract_digest",
    }
)
_REQUIREMENT_FIELDS = frozenset(
    {
        "schema_version",
        "requirement_type",
        "capability_definition_identity",
        "execution_capsule_digest",
        "handler_conformance_evidence_digest",
        "atomic_provider_condition_contract_identity",
        "verification_contract_identity",
        "effect_class",
        "max_provider_mutations",
        "rollback_strategy",
        "provider_mutation_allowed",
        "requirement_revision",
        "requirement_digest",
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


class ControlledWriteDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class GitHubCreateRefConditionContract:
    """Provider condition for the first bounded V-One write capability.

    This contract describes create-only semantics. It performs no provider call and grants no
    authority. The future handler must fail if the exact ref already exists and may never reinterpret
    this contract as update-ref or force-update authority.
    """

    provider: str
    operation: str
    target_kind: str
    ref_namespace_prefix: str
    create_semantics: str
    overwrite_existing_ref_allowed: bool
    force_update_allowed: bool
    rollback_strategy: str
    verification_class: str
    contract_revision: str
    contract_digest: str

    def __post_init__(self) -> None:
        for field in (
            "provider",
            "operation",
            "target_kind",
            "ref_namespace_prefix",
            "create_semantics",
            "rollback_strategy",
            "verification_class",
            "contract_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.provider != "github":
            raise ValueError("F1 provider must be github")
        if self.operation != CREATE_REF_OPERATION:
            raise ValueError("F1 operation must be CREATE_REF")
        if self.target_kind != GITHUB_REF_TARGET_KIND:
            raise ValueError("F1 target kind must be git_ref")
        if self.ref_namespace_prefix != VONE_CANARY_REF_PREFIX:
            raise ValueError("F1 ref namespace must be the V-One canary namespace")
        if self.create_semantics != CREATE_ONLY_SEMANTICS:
            raise ValueError("F1 create semantics must be CREATE_ONLY")
        if self.overwrite_existing_ref_allowed is not False:
            raise ValueError("F1 must not overwrite an existing ref")
        if self.force_update_allowed is not False:
            raise ValueError("F1 must not force-update a ref")
        if self.rollback_strategy != DELETE_EXACT_CREATED_REF_ROLLBACK:
            raise ValueError("F1 rollback strategy is unsupported")
        if self.verification_class != PROVIDER_READ_VERIFICATION_CLASS:
            raise ValueError("F1 verification class must use provider readback")
        _require_digest(self.contract_digest, field="contract_digest")
        if self.contract_digest != _digest(self._claims_without_digest()):
            raise ValueError("contract_digest does not match GitHub create-ref condition")

    @classmethod
    def create(cls, *, contract_revision: str) -> Self:
        _require_text(contract_revision, field="contract_revision")
        claims = {
            "schema_version": 1,
            "condition_type": GITHUB_CREATE_REF_CONDITION_TYPE,
            "provider": "github",
            "operation": CREATE_REF_OPERATION,
            "target_kind": GITHUB_REF_TARGET_KIND,
            "ref_namespace_prefix": VONE_CANARY_REF_PREFIX,
            "create_semantics": CREATE_ONLY_SEMANTICS,
            "overwrite_existing_ref_allowed": False,
            "force_update_allowed": False,
            "rollback_strategy": DELETE_EXACT_CREATED_REF_ROLLBACK,
            "verification_class": PROVIDER_READ_VERIFICATION_CLASS,
            "contract_revision": contract_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "condition_type"}
        }
        return cls(**values, contract_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _CONDITION_FIELDS, contract=GITHUB_CREATE_REF_CONDITION_TYPE)
        if (
            value["schema_version"] != 1
            or value["condition_type"] != GITHUB_CREATE_REF_CONDITION_TYPE
        ):
            raise ValueError("github-create-ref-condition/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _CONDITION_FIELDS
                if key not in {"schema_version", "condition_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "condition_type": GITHUB_CREATE_REF_CONDITION_TYPE,
            "provider": self.provider,
            "operation": self.operation,
            "target_kind": self.target_kind,
            "ref_namespace_prefix": self.ref_namespace_prefix,
            "create_semantics": self.create_semantics,
            "overwrite_existing_ref_allowed": self.overwrite_existing_ref_allowed,
            "force_update_allowed": self.force_update_allowed,
            "rollback_strategy": self.rollback_strategy,
            "verification_class": self.verification_class,
            "contract_revision": self.contract_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "contract_digest": self.contract_digest}


@dataclass(frozen=True, slots=True)
class ControlledWriteRequirement:
    """F1 eligibility evidence for a future controlled provider mutation.

    It is not an ExecutionGrant, Runner boundary, credential decision, provider transport, execution
    receipt, VerificationResult or OperationProof. It only proves that the immutable execution
    definition is structurally eligible for the first bounded write design.
    """

    capability_definition_identity: str
    execution_capsule_digest: str
    handler_conformance_evidence_digest: str
    atomic_provider_condition_contract_identity: str
    verification_contract_identity: str
    effect_class: str
    max_provider_mutations: int
    rollback_strategy: str
    provider_mutation_allowed: bool
    requirement_revision: str
    requirement_digest: str

    def __post_init__(self) -> None:
        for field in (
            "capability_definition_identity",
            "execution_capsule_digest",
            "handler_conformance_evidence_digest",
            "atomic_provider_condition_contract_identity",
            "verification_contract_identity",
            "requirement_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in ("effect_class", "rollback_strategy", "requirement_revision"):
            _require_text(getattr(self, field), field=field)
        if self.effect_class != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise ValueError("F1 effect class must be mutation.reversible")
        if self.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise ValueError("F1 allows exactly one provider mutation")
        if self.rollback_strategy != DELETE_EXACT_CREATED_REF_ROLLBACK:
            raise ValueError("F1 rollback strategy is unsupported")
        if self.provider_mutation_allowed is not True:
            raise ValueError("F1 requirement must describe an explicitly write-capable candidate")
        if self.requirement_digest != _digest(self._claims_without_digest()):
            raise ValueError("requirement_digest does not match controlled write requirement")

    @classmethod
    def create(
        cls,
        *,
        definition: CapabilityDefinition,
        capsule: ExecutionCapsule,
        handler_evidence: HandlerConformanceEvidence,
        provider_condition: GitHubCreateRefConditionContract,
        requirement_revision: str,
    ) -> Self:
        if not isinstance(definition, CapabilityDefinition):
            raise ValueError("definition must be CapabilityDefinition")
        if not isinstance(capsule, ExecutionCapsule):
            raise ValueError("capsule must be ExecutionCapsule")
        if not isinstance(handler_evidence, HandlerConformanceEvidence):
            raise ValueError("handler_evidence must be HandlerConformanceEvidence")
        if not isinstance(provider_condition, GitHubCreateRefConditionContract):
            raise ValueError("provider_condition must be GitHubCreateRefConditionContract")
        _require_text(requirement_revision, field="requirement_revision")

        if definition.capability != GITHUB_CREATE_REF_CAPABILITY:
            raise ControlledWriteDenied("F1_CAPABILITY_NOT_GITHUB_CREATE_REF")
        if definition.target_kind != GITHUB_REF_TARGET_KIND:
            raise ControlledWriteDenied("F1_TARGET_KIND_MISMATCH")
        if definition.handler_id != GITHUB_CREATE_REF_HANDLER:
            raise ControlledWriteDenied("F1_HANDLER_MISMATCH")
        if definition.effect_class != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise ControlledWriteDenied("F1_EFFECT_NOT_REVERSIBLE_MUTATION")
        if definition.verification_class != PROVIDER_READ_VERIFICATION_CLASS:
            raise ControlledWriteDenied("F1_VERIFICATION_CLASS_MISMATCH")
        if definition.production_eligible:
            raise ControlledWriteDenied("F1_PRODUCTION_ELIGIBILITY_FORBIDDEN")
        if definition.supported_environments != (STAGING_ENVIRONMENT,):
            raise ControlledWriteDenied("F1_ENVIRONMENT_NOT_STAGING_ONLY")

        exact_capsule = {
            "capability_definition_identity": capsule.capability_definition_identity,
            "target_kind": capsule.target_kind,
            "handler_id": capsule.handler_id,
            "precondition_enforcement_class": capsule.precondition_enforcement_class,
            "verification_class": capsule.verification_class,
        }
        expected_capsule = {
            "capability_definition_identity": definition.definition_identity,
            "target_kind": definition.target_kind,
            "handler_id": definition.handler_id,
            "precondition_enforcement_class": ATOMIC_PROVIDER_CONDITION,
            "verification_class": definition.verification_class,
        }
        if exact_capsule != expected_capsule:
            raise ControlledWriteDenied("F1_CAPSULE_BINDING_MISMATCH")

        exact_evidence = {
            "capability_definition_identity": handler_evidence.capability_definition_identity,
            "execution_capsule_digest": handler_evidence.execution_capsule_digest,
            "handler_id": handler_evidence.handler_id,
            "handler_digest": handler_evidence.handler_digest,
            "runner_class": handler_evidence.runner_class,
            "credential_class": handler_evidence.credential_class,
            "precondition_enforcement_class": handler_evidence.precondition_enforcement_class,
            "verification_contract_identity": handler_evidence.verification_contract_identity,
        }
        expected_evidence = {
            "capability_definition_identity": capsule.capability_definition_identity,
            "execution_capsule_digest": capsule.capsule_digest,
            "handler_id": capsule.handler_id,
            "handler_digest": capsule.handler_digest,
            "runner_class": capsule.runner_class,
            "credential_class": capsule.credential_class,
            "precondition_enforcement_class": capsule.precondition_enforcement_class,
            "verification_contract_identity": capsule.verification_contract_identity,
        }
        if exact_evidence != expected_evidence:
            raise ControlledWriteDenied("F1_HANDLER_EVIDENCE_BINDING_MISMATCH")
        if (
            handler_evidence.atomic_provider_condition_contract_identity
            != provider_condition.contract_digest
        ):
            raise ControlledWriteDenied("F1_ATOMIC_PROVIDER_CONDITION_MISMATCH")
        if capsule.verification_contract_identity != handler_evidence.verification_contract_identity:
            raise ControlledWriteDenied("F1_VERIFICATION_CONTRACT_MISMATCH")

        claims = {
            "schema_version": 1,
            "requirement_type": CONTROLLED_WRITE_REQUIREMENT_TYPE,
            "capability_definition_identity": definition.definition_identity,
            "execution_capsule_digest": capsule.capsule_digest,
            "handler_conformance_evidence_digest": handler_evidence.evidence_digest,
            "atomic_provider_condition_contract_identity": provider_condition.contract_digest,
            "verification_contract_identity": capsule.verification_contract_identity,
            "effect_class": MUTATION_REVERSIBLE_EFFECT_CLASS,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "rollback_strategy": provider_condition.rollback_strategy,
            "provider_mutation_allowed": True,
            "requirement_revision": requirement_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "requirement_type"}
        }
        return cls(**values, requirement_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _REQUIREMENT_FIELDS, contract=CONTROLLED_WRITE_REQUIREMENT_TYPE)
        if (
            value["schema_version"] != 1
            or value["requirement_type"] != CONTROLLED_WRITE_REQUIREMENT_TYPE
        ):
            raise ValueError("controlled-write-requirement/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _REQUIREMENT_FIELDS
                if key not in {"schema_version", "requirement_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "requirement_type": CONTROLLED_WRITE_REQUIREMENT_TYPE,
            "capability_definition_identity": self.capability_definition_identity,
            "execution_capsule_digest": self.execution_capsule_digest,
            "handler_conformance_evidence_digest": self.handler_conformance_evidence_digest,
            "atomic_provider_condition_contract_identity": self.atomic_provider_condition_contract_identity,
            "verification_contract_identity": self.verification_contract_identity,
            "effect_class": self.effect_class,
            "max_provider_mutations": self.max_provider_mutations,
            "rollback_strategy": self.rollback_strategy,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "requirement_revision": self.requirement_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "requirement_digest": self.requirement_digest}
