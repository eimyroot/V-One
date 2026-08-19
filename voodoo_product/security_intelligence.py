from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Self

from .evidence_primitives import canonical_json

SKILL_MANIFEST_TYPE: Final = "security-intelligence-skill-manifest/v1"
CAPABILITY_MANIFEST_TYPE: Final = "security-intelligence-capability-manifest/v1"
AUTHORITY_REQUIREMENT_TYPE: Final = "security-intelligence-authority-requirement/v1"

_SKILL_ID_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*")
_CAPABILITY_ID_PATTERN = re.compile(
    r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*/v[1-9][0-9]*"
)


class RiskClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class EffectClass(StrEnum):
    READ = "READ"
    COMPUTE = "COMPUTE"
    NETWORK = "NETWORK"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    UNKNOWN = "UNKNOWN"


class SkillStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    DEPRECATED = "DEPRECATED"


class AuthorityDisposition(StrEnum):
    REQUIRE_VOP_EVALUATION = "REQUIRE_VOP_EVALUATION"
    REQUIRE_HUMAN = "REQUIRE_HUMAN"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


_ACTIVE_EFFECTS: Final = frozenset(
    {
        EffectClass.COMPUTE,
        EffectClass.NETWORK,
        EffectClass.WRITE,
        EffectClass.EXECUTE,
    }
)

_MUTATION_EFFECTS: Final = frozenset(
    {
        EffectClass.WRITE,
        EffectClass.EXECUTE,
    }
)


def _digest(value: dict[str, object]) -> str:
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
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_sorted_unique_text(
    values: tuple[str, ...],
    *,
    field: str,
    allow_empty: bool = False,
) -> None:
    if not allow_empty and not values:
        raise ValueError(f"{field} must not be empty")
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{field} must be sorted and unique")
    for value in values:
        _require_text(value, field=field)


@dataclass(frozen=True, slots=True)
class AuthorityRequirement:
    risk_class: RiskClass
    effect_class: EffectClass
    policy_evaluation_required: bool
    approval_required: bool
    execution_grant_required: bool
    isolated_runner_required: bool
    independent_verification_required: bool
    default_disposition: AuthorityDisposition
    requirement_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.risk_class, RiskClass):
            raise ValueError("risk_class is invalid")
        if not isinstance(self.effect_class, EffectClass):
            raise ValueError("effect_class is invalid")
        if not isinstance(self.default_disposition, AuthorityDisposition):
            raise ValueError("default_disposition is invalid")

        for field in (
            "policy_evaluation_required",
            "approval_required",
            "execution_grant_required",
            "isolated_runner_required",
            "independent_verification_required",
        ):
            if type(getattr(self, field)) is not bool:
                raise ValueError(f"{field} must be boolean")

        if not self.policy_evaluation_required:
            raise ValueError("VOP policy evaluation is mandatory")

        unknown = (
            self.risk_class is RiskClass.UNKNOWN
            or self.effect_class is EffectClass.UNKNOWN
        )

        if (
            unknown
            and self.default_disposition is not AuthorityDisposition.UNKNOWN
        ):
            raise ValueError("unknown classification must remain UNKNOWN")

        if unknown and not self.approval_required:
            raise ValueError("unknown classification must fail closed")

        if (
            self.risk_class is RiskClass.CRITICAL
            and not unknown
            and self.default_disposition is not AuthorityDisposition.DENY
        ):
            raise ValueError("CRITICAL risk must default to DENY")

        if self.effect_class in _ACTIVE_EFFECTS and (
            not self.execution_grant_required
            or not self.isolated_runner_required
        ):
            raise ValueError(
                "active capability requires canonical grant and isolated Runner"
            )

        if self.effect_class in _MUTATION_EFFECTS and (
            not self.approval_required
            or not self.independent_verification_required
        ):
            raise ValueError(
                "WRITE/EXECUTE requires approval and independent verification"
            )

        if self.effect_class in _MUTATION_EFFECTS and self.default_disposition not in {
            AuthorityDisposition.REQUIRE_HUMAN,
            AuthorityDisposition.DENY,
        }:
            raise ValueError("WRITE/EXECUTE must require human review or deny")

        _require_digest(self.requirement_identity, field="requirement_identity")
        if self.requirement_identity != _digest(self._claims_without_identity()):
            raise ValueError("requirement_identity does not match claims")

    @classmethod
    def classify(
        cls,
        *,
        risk_class: RiskClass,
        effect_class: EffectClass,
    ) -> Self:
        if not isinstance(risk_class, RiskClass):
            raise ValueError("risk_class is invalid")
        if not isinstance(effect_class, EffectClass):
            raise ValueError("effect_class is invalid")

        unknown = (
            risk_class is RiskClass.UNKNOWN
            or effect_class is EffectClass.UNKNOWN
        )
        active = effect_class in _ACTIVE_EFFECTS
        mutation = effect_class in _MUTATION_EFFECTS

        if unknown:
            disposition = AuthorityDisposition.UNKNOWN
            approval_required = True
        elif risk_class is RiskClass.CRITICAL:
            disposition = AuthorityDisposition.DENY
            approval_required = True
        elif mutation or risk_class is RiskClass.HIGH:
            disposition = AuthorityDisposition.REQUIRE_HUMAN
            approval_required = True
        else:
            disposition = AuthorityDisposition.REQUIRE_VOP_EVALUATION
            approval_required = False

        claims: dict[str, object] = {
            "requirement_type": AUTHORITY_REQUIREMENT_TYPE,
            "risk_class": risk_class.value,
            "effect_class": effect_class.value,
            "policy_evaluation_required": True,
            "approval_required": approval_required,
            "execution_grant_required": active,
            "isolated_runner_required": active,
            "independent_verification_required": mutation,
            "default_disposition": disposition.value,
        }

        return cls(
            risk_class=risk_class,
            effect_class=effect_class,
            policy_evaluation_required=True,
            approval_required=approval_required,
            execution_grant_required=active,
            isolated_runner_required=active,
            independent_verification_required=mutation,
            default_disposition=disposition,
            requirement_identity=_digest(claims),
        )

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "requirement_type": AUTHORITY_REQUIREMENT_TYPE,
            "risk_class": self.risk_class.value,
            "effect_class": self.effect_class.value,
            "policy_evaluation_required": self.policy_evaluation_required,
            "approval_required": self.approval_required,
            "execution_grant_required": self.execution_grant_required,
            "isolated_runner_required": self.isolated_runner_required,
            "independent_verification_required": self.independent_verification_required,
            "default_disposition": self.default_disposition.value,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._claims_without_identity()
        payload["requirement_identity"] = self.requirement_identity
        return payload


@dataclass(frozen=True, slots=True)
class SkillManifest:
    skill_id: str
    version: str
    source: str
    domain: str
    capability_ids: tuple[str, ...]
    risk_class: RiskClass
    authority_requirements: tuple[str, ...]
    framework_mappings: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    verification_requirements: tuple[str, ...]
    content_ref: str
    status: SkillStatus
    manifest_identity: str

    def __post_init__(self) -> None:
        if _SKILL_ID_PATTERN.fullmatch(self.skill_id) is None:
            raise ValueError("skill_id is invalid")

        for field in ("version", "source", "domain", "content_ref"):
            _require_text(getattr(self, field), field=field)

        if not isinstance(self.risk_class, RiskClass):
            raise ValueError("risk_class is invalid")
        if not isinstance(self.status, SkillStatus):
            raise ValueError("status is invalid")

        _require_sorted_unique_text(self.capability_ids, field="capability_ids")
        for capability_id in self.capability_ids:
            if _CAPABILITY_ID_PATTERN.fullmatch(capability_id) is None:
                raise ValueError("capability_id is invalid")

        _require_sorted_unique_text(
            self.authority_requirements,
            field="authority_requirements",
        )
        _require_sorted_unique_text(
            self.framework_mappings,
            field="framework_mappings",
            allow_empty=True,
        )
        _require_sorted_unique_text(
            self.evidence_requirements,
            field="evidence_requirements",
        )
        _require_sorted_unique_text(
            self.verification_requirements,
            field="verification_requirements",
        )

        _require_digest(self.manifest_identity, field="manifest_identity")
        if self.manifest_identity != _digest(self._claims_without_identity()):
            raise ValueError("manifest_identity does not match skill manifest")

    @classmethod
    def create(
        cls,
        *,
        skill_id: str,
        version: str,
        source: str,
        domain: str,
        capability_ids: tuple[str, ...],
        risk_class: RiskClass,
        authority_requirements: tuple[str, ...],
        framework_mappings: tuple[str, ...],
        evidence_requirements: tuple[str, ...],
        verification_requirements: tuple[str, ...],
        content_ref: str,
        status: SkillStatus = SkillStatus.PROPOSED,
    ) -> Self:
        capabilities = tuple(sorted(set(capability_ids)))
        authorities = tuple(sorted(set(authority_requirements)))
        mappings = tuple(sorted(set(framework_mappings)))
        evidence = tuple(sorted(set(evidence_requirements)))
        verification = tuple(sorted(set(verification_requirements)))

        claims: dict[str, object] = {
            "manifest_type": SKILL_MANIFEST_TYPE,
            "skill_id": skill_id,
            "version": version,
            "source": source,
            "domain": domain,
            "capability_ids": list(capabilities),
            "risk_class": risk_class.value,
            "authority_requirements": list(authorities),
            "framework_mappings": list(mappings),
            "evidence_requirements": list(evidence),
            "verification_requirements": list(verification),
            "content_ref": content_ref,
            "status": status.value,
        }

        return cls(
            skill_id=skill_id,
            version=version,
            source=source,
            domain=domain,
            capability_ids=capabilities,
            risk_class=risk_class,
            authority_requirements=authorities,
            framework_mappings=mappings,
            evidence_requirements=evidence,
            verification_requirements=verification,
            content_ref=content_ref,
            status=status,
            manifest_identity=_digest(claims),
        )

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "manifest_type": SKILL_MANIFEST_TYPE,
            "skill_id": self.skill_id,
            "version": self.version,
            "source": self.source,
            "domain": self.domain,
            "capability_ids": list(self.capability_ids),
            "risk_class": self.risk_class.value,
            "authority_requirements": list(self.authority_requirements),
            "framework_mappings": list(self.framework_mappings),
            "evidence_requirements": list(self.evidence_requirements),
            "verification_requirements": list(self.verification_requirements),
            "content_ref": self.content_ref,
            "status": self.status.value,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._claims_without_identity()
        payload["manifest_identity"] = self.manifest_identity
        return payload


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    capability_id: str
    skill_id: str
    source_capability: str
    effect_class: EffectClass
    resource_scope: str
    risk_class: RiskClass
    required_authority: AuthorityRequirement
    sandbox_constraints: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    normalization_status: str
    manifest_identity: str

    def __post_init__(self) -> None:
        if _CAPABILITY_ID_PATTERN.fullmatch(self.capability_id) is None:
            raise ValueError("capability_id is invalid")
        if _SKILL_ID_PATTERN.fullmatch(self.skill_id) is None:
            raise ValueError("skill_id is invalid")

        _require_text(self.source_capability, field="source_capability")
        _require_text(self.resource_scope, field="resource_scope")

        if not isinstance(self.effect_class, EffectClass):
            raise ValueError("effect_class is invalid")
        if not isinstance(self.risk_class, RiskClass):
            raise ValueError("risk_class is invalid")
        if not isinstance(self.required_authority, AuthorityRequirement):
            raise ValueError("required_authority is invalid")

        if self.required_authority.effect_class is not self.effect_class:
            raise ValueError("required authority effect_class mismatch")
        if self.required_authority.risk_class is not self.risk_class:
            raise ValueError("required authority risk_class mismatch")

        _require_sorted_unique_text(
            self.sandbox_constraints,
            field="sandbox_constraints",
            allow_empty=True,
        )
        _require_sorted_unique_text(
            self.evidence_refs,
            field="evidence_refs",
            allow_empty=True,
        )

        if self.effect_class in _ACTIVE_EFFECTS and not self.sandbox_constraints:
            raise ValueError("active capability requires sandbox constraints")

        if self.normalization_status not in {"NORMALIZED", "UNKNOWN"}:
            raise ValueError("normalization_status is invalid")

        if not self.evidence_refs and self.normalization_status != "UNKNOWN":
            raise ValueError("evidence-less capability must remain UNKNOWN")

        _require_digest(self.manifest_identity, field="manifest_identity")
        if self.manifest_identity != _digest(self._claims_without_identity()):
            raise ValueError("manifest_identity does not match capability manifest")

    @classmethod
    def create(
        cls,
        *,
        capability_id: str,
        skill_id: str,
        source_capability: str,
        effect_class: EffectClass,
        resource_scope: str,
        risk_class: RiskClass,
        sandbox_constraints: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
        normalization_status: str = "UNKNOWN",
    ) -> Self:
        constraints = tuple(sorted(set(sandbox_constraints)))
        evidence = tuple(sorted(set(evidence_refs)))
        authority = AuthorityRequirement.classify(
            risk_class=risk_class,
            effect_class=effect_class,
        )

        claims: dict[str, object] = {
            "manifest_type": CAPABILITY_MANIFEST_TYPE,
            "capability_id": capability_id,
            "skill_id": skill_id,
            "source_capability": source_capability,
            "effect_class": effect_class.value,
            "resource_scope": resource_scope,
            "risk_class": risk_class.value,
            "required_authority": authority.to_dict(),
            "sandbox_constraints": list(constraints),
            "evidence_refs": list(evidence),
            "normalization_status": normalization_status,
        }

        return cls(
            capability_id=capability_id,
            skill_id=skill_id,
            source_capability=source_capability,
            effect_class=effect_class,
            resource_scope=resource_scope,
            risk_class=risk_class,
            required_authority=authority,
            sandbox_constraints=constraints,
            evidence_refs=evidence,
            normalization_status=normalization_status,
            manifest_identity=_digest(claims),
        )

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "manifest_type": CAPABILITY_MANIFEST_TYPE,
            "capability_id": self.capability_id,
            "skill_id": self.skill_id,
            "source_capability": self.source_capability,
            "effect_class": self.effect_class.value,
            "resource_scope": self.resource_scope,
            "risk_class": self.risk_class.value,
            "required_authority": self.required_authority.to_dict(),
            "sandbox_constraints": list(self.sandbox_constraints),
            "evidence_refs": list(self.evidence_refs),
            "normalization_status": self.normalization_status,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._claims_without_identity()
        payload["manifest_identity"] = self.manifest_identity
        return payload
