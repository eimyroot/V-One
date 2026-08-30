from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Self

from .evidence_primitives import canonical_json
from .security_intelligence import (
    CapabilityManifest,
    EffectClass,
    RiskClass,
    SkillManifest,
    SkillStatus,
)

FRAMEWORK_MAPPING_TYPE: Final = "security-intelligence-framework-mapping/v1"
PROGRESSIVE_DISCOVERY_TYPE: Final = "security-intelligence-progressive-discovery/v1"
NORMALIZATION_RESULT_TYPE: Final = "security-intelligence-normalization-result/v1"

SUPPORTED_FRAMEWORKS: Final = frozenset(
    {
        "MITRE ATT&CK",
        "MITRE ATLAS",
        "MITRE D3FEND",
        "MITRE F3",
        "NIST AI RMF",
        "NIST CSF 2.0",
    }
)

_ACTIVE_EFFECTS: Final = frozenset(
    {
        EffectClass.COMPUTE,
        EffectClass.NETWORK,
        EffectClass.WRITE,
        EffectClass.EXECUTE,
    }
)

_RISK_ORDER: Final = {
    RiskClass.LOW: 1,
    RiskClass.MEDIUM: 2,
    RiskClass.HIGH: 3,
    RiskClass.CRITICAL: 4,
    RiskClass.UNKNOWN: 5,
}


class MappingStatus(StrEnum):
    NORMALIZED = "NORMALIZED"
    UNKNOWN = "UNKNOWN"


class DiscoveryLevel(StrEnum):
    INDEX = "INDEX"
    METADATA = "METADATA"
    CONTENT = "CONTENT"


class NormalizationStatus(StrEnum):
    NORMALIZED = "NORMALIZED"
    UNKNOWN = "UNKNOWN"


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


def _require_optional_text(value: object, *, field: str) -> None:
    if value is not None:
        _require_text(value, field=field)


def _sorted_unique(values: tuple[str, ...], *, field: str) -> tuple[str, ...]:
    normalized = tuple(sorted(set(values)))
    for value in normalized:
        _require_text(value, field=field)
    return normalized


def _parse_risk(value: str) -> RiskClass:
    try:
        return RiskClass(value.upper())
    except ValueError:
        return RiskClass.UNKNOWN


def _parse_effect(value: str) -> EffectClass:
    try:
        return EffectClass(value.upper())
    except ValueError:
        return EffectClass.UNKNOWN


@dataclass(frozen=True, slots=True)
class FrameworkMapping:
    framework: str
    external_id: str
    evidence_refs: tuple[str, ...]
    status: MappingStatus
    mapping_identity: str

    def __post_init__(self) -> None:
        _require_text(self.framework, field="framework")
        _require_text(self.external_id, field="external_id")
        if self.evidence_refs != _sorted_unique(
            self.evidence_refs,
            field="evidence_ref",
        ):
            raise ValueError("evidence_refs must be sorted and unique")
        if not isinstance(self.status, MappingStatus):
            raise ValueError("status is invalid")
        if (
            self.framework not in SUPPORTED_FRAMEWORKS
            and self.status is not MappingStatus.UNKNOWN
        ):
            raise ValueError("unknown framework must remain UNKNOWN")
        if not self.evidence_refs and self.status is not MappingStatus.UNKNOWN:
            raise ValueError("evidence-less mapping must remain UNKNOWN")
        if self.mapping_identity != _digest(self._claims_without_identity()):
            raise ValueError("mapping_identity does not match claims")

    @classmethod
    def create(
        cls,
        *,
        framework: str,
        external_id: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> Self:
        _require_text(framework, field="framework")
        _require_text(external_id, field="external_id")
        evidence = _sorted_unique(evidence_refs, field="evidence_ref")
        status = (
            MappingStatus.NORMALIZED
            if framework in SUPPORTED_FRAMEWORKS and evidence
            else MappingStatus.UNKNOWN
        )
        claims: dict[str, object] = {
            "mapping_type": FRAMEWORK_MAPPING_TYPE,
            "framework": framework,
            "external_id": external_id,
            "evidence_refs": list(evidence),
            "status": status.value,
        }
        return cls(
            framework=framework,
            external_id=external_id,
            evidence_refs=evidence,
            status=status,
            mapping_identity=_digest(claims),
        )

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "mapping_type": FRAMEWORK_MAPPING_TYPE,
            "framework": self.framework,
            "external_id": self.external_id,
            "evidence_refs": list(self.evidence_refs),
            "status": self.status.value,
        }

    def to_reference(self) -> str:
        prefix = self.framework if self.status is MappingStatus.NORMALIZED else "UNKNOWN"
        return f"{prefix}:{self.external_id}"

    def to_dict(self) -> dict[str, object]:
        payload = self._claims_without_identity()
        payload["mapping_identity"] = self.mapping_identity
        return payload


@dataclass(frozen=True, slots=True)
class ProgressiveDiscovery:
    source: str
    source_skill_ref: str
    index_ref: str
    metadata_ref: str | None
    content_ref: str | None
    level: DiscoveryLevel
    discovery_identity: str

    def __post_init__(self) -> None:
        _require_text(self.source, field="source")
        _require_text(self.source_skill_ref, field="source_skill_ref")
        _require_text(self.index_ref, field="index_ref")
        _require_optional_text(self.metadata_ref, field="metadata_ref")
        _require_optional_text(self.content_ref, field="content_ref")
        if not isinstance(self.level, DiscoveryLevel):
            raise ValueError("level is invalid")
        if (
            self.level in {DiscoveryLevel.METADATA, DiscoveryLevel.CONTENT}
            and self.metadata_ref is None
        ):
            raise ValueError("metadata discovery requires metadata_ref")
        if self.level is DiscoveryLevel.CONTENT and self.content_ref is None:
            raise ValueError("content discovery requires content_ref")
        if self.level is DiscoveryLevel.INDEX and (
            self.metadata_ref is not None or self.content_ref is not None
        ):
            raise ValueError("INDEX discovery cannot claim deeper refs")
        if self.level is DiscoveryLevel.METADATA and self.content_ref is not None:
            raise ValueError("METADATA discovery cannot claim content_ref")
        if self.discovery_identity != _digest(self._claims_without_identity()):
            raise ValueError("discovery_identity does not match claims")

    @classmethod
    def create(
        cls,
        *,
        source: str,
        source_skill_ref: str,
        index_ref: str,
        metadata_ref: str | None = None,
        content_ref: str | None = None,
    ) -> Self:
        if content_ref is not None:
            level = DiscoveryLevel.CONTENT
        elif metadata_ref is not None:
            level = DiscoveryLevel.METADATA
        else:
            level = DiscoveryLevel.INDEX
        claims: dict[str, object] = {
            "discovery_type": PROGRESSIVE_DISCOVERY_TYPE,
            "source": source,
            "source_skill_ref": source_skill_ref,
            "index_ref": index_ref,
            "metadata_ref": metadata_ref,
            "content_ref": content_ref,
            "level": level.value,
        }
        return cls(
            source=source,
            source_skill_ref=source_skill_ref,
            index_ref=index_ref,
            metadata_ref=metadata_ref,
            content_ref=content_ref,
            level=level,
            discovery_identity=_digest(claims),
        )

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "discovery_type": PROGRESSIVE_DISCOVERY_TYPE,
            "source": self.source,
            "source_skill_ref": self.source_skill_ref,
            "index_ref": self.index_ref,
            "metadata_ref": self.metadata_ref,
            "content_ref": self.content_ref,
            "level": self.level.value,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._claims_without_identity()
        payload["discovery_identity"] = self.discovery_identity
        return payload


@dataclass(frozen=True, slots=True)
class ExternalCapability:
    capability_id: str
    source_capability: str
    effect_class: str
    risk_class: str
    resource_scope: str
    sandbox_constraints: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExternalSkill:
    source: str
    skill_id: str
    version: str
    domain: str
    content_ref: str
    discovery: ProgressiveDiscovery
    capabilities: tuple[ExternalCapability, ...]
    framework_mappings: tuple[FrameworkMapping, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    skill_manifest: SkillManifest
    capability_manifests: tuple[CapabilityManifest, ...]
    framework_mappings: tuple[FrameworkMapping, ...]
    discovery: ProgressiveDiscovery
    status: NormalizationStatus
    requires_vop_evaluation: bool
    creates_execution_authority: bool
    creates_runtime_binding: bool
    result_identity: str

    def __post_init__(self) -> None:
        if self.skill_manifest.status is not SkillStatus.PROPOSED:
            raise ValueError("external skill must remain PROPOSED")
        if not self.requires_vop_evaluation:
            raise ValueError("normalization must require VOP evaluation")
        if self.creates_execution_authority:
            raise ValueError("normalization cannot create execution authority")
        if self.creates_runtime_binding:
            raise ValueError("normalization cannot create runtime binding")
        if not isinstance(self.status, NormalizationStatus):
            raise ValueError("status is invalid")
        if self.result_identity != _digest(self._claims_without_identity()):
            raise ValueError("result_identity does not match claims")

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "result_type": NORMALIZATION_RESULT_TYPE,
            "skill_manifest_identity": self.skill_manifest.manifest_identity,
            "capability_manifest_identities": [
                capability.manifest_identity
                for capability in self.capability_manifests
            ],
            "framework_mapping_identities": [
                mapping.mapping_identity for mapping in self.framework_mappings
            ],
            "discovery_identity": self.discovery.discovery_identity,
            "status": self.status.value,
            "requires_vop_evaluation": self.requires_vop_evaluation,
            "creates_execution_authority": self.creates_execution_authority,
            "creates_runtime_binding": self.creates_runtime_binding,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._claims_without_identity()
        payload["result_identity"] = self.result_identity
        return payload


class ExternalSkillNormalizer:
    "Normalize untrusted external skill metadata without creating execution authority."

    def normalize(self, external: ExternalSkill) -> NormalizationResult:
        if not isinstance(external, ExternalSkill):
            raise ValueError("external skill is invalid")
        if external.discovery.source != external.source:
            raise ValueError("discovery source mismatch")
        if not external.capabilities:
            raise ValueError("external skill requires at least one capability")

        mappings = tuple(
            sorted(
                external.framework_mappings,
                key=lambda item: (
                    item.framework,
                    item.external_id,
                    item.mapping_identity,
                ),
            )
        )
        evidence = _sorted_unique(external.evidence_refs, field="evidence_ref")

        manifests: list[CapabilityManifest] = []
        capability_risks: list[RiskClass] = []
        all_capabilities_normalized = True

        for item in sorted(
            external.capabilities,
            key=lambda value: value.capability_id,
        ):
            if not isinstance(item, ExternalCapability):
                raise ValueError("capability is invalid")

            risk = _parse_risk(item.risk_class)
            effect = _parse_effect(item.effect_class)
            constraints = _sorted_unique(
                item.sandbox_constraints,
                field="sandbox_constraint",
            )
            capability_evidence = _sorted_unique(
                item.evidence_refs,
                field="evidence_ref",
            )

            normalized = (
                risk is not RiskClass.UNKNOWN
                and effect is not EffectClass.UNKNOWN
                and bool(capability_evidence)
                and (effect not in _ACTIVE_EFFECTS or bool(constraints))
            )

            if not normalized:
                all_capabilities_normalized = False

            manifest_effect = effect
            if effect in _ACTIVE_EFFECTS and not constraints:
                manifest_effect = EffectClass.UNKNOWN

            manifest = CapabilityManifest.create(
                capability_id=item.capability_id,
                skill_id=external.skill_id,
                source_capability=item.source_capability,
                effect_class=manifest_effect,
                resource_scope=item.resource_scope,
                risk_class=risk,
                sandbox_constraints=constraints,
                evidence_refs=capability_evidence,
                normalization_status=(
                    NormalizationStatus.NORMALIZED.value
                    if normalized
                    else NormalizationStatus.UNKNOWN.value
                ),
            )
            manifests.append(manifest)
            capability_risks.append(risk)

        skill_risk = max(capability_risks, key=_RISK_ORDER.__getitem__)
        mappings_normalized = all(
            mapping.status is MappingStatus.NORMALIZED for mapping in mappings
        )

        status = (
            NormalizationStatus.NORMALIZED
            if evidence
            and all_capabilities_normalized
            and mappings_normalized
            and external.discovery.level
            in {DiscoveryLevel.METADATA, DiscoveryLevel.CONTENT}
            else NormalizationStatus.UNKNOWN
        )

        framework_refs = tuple(
            sorted(mapping.to_reference() for mapping in mappings)
        )
        capability_ids = tuple(
            manifest.capability_id for manifest in manifests
        )

        skill_manifest = SkillManifest.create(
            skill_id=external.skill_id,
            version=external.version,
            source=external.source,
            domain=external.domain,
            capability_ids=capability_ids,
            risk_class=skill_risk,
            authority_requirements=("vop-policy-evaluation",),
            framework_mappings=framework_refs,
            evidence_requirements=("source-evidence",),
            verification_requirements=(
                "independent-verification-before-activation",
            ),
            content_ref=external.content_ref,
            status=SkillStatus.PROPOSED,
        )

        claims: dict[str, object] = {
            "result_type": NORMALIZATION_RESULT_TYPE,
            "skill_manifest_identity": skill_manifest.manifest_identity,
            "capability_manifest_identities": [
                capability.manifest_identity for capability in manifests
            ],
            "framework_mapping_identities": [
                mapping.mapping_identity for mapping in mappings
            ],
            "discovery_identity": external.discovery.discovery_identity,
            "status": status.value,
            "requires_vop_evaluation": True,
            "creates_execution_authority": False,
            "creates_runtime_binding": False,
        }

        return NormalizationResult(
            skill_manifest=skill_manifest,
            capability_manifests=tuple(manifests),
            framework_mappings=mappings,
            discovery=external.discovery,
            status=status,
            requires_vop_evaluation=True,
            creates_execution_authority=False,
            creates_runtime_binding=False,
            result_identity=_digest(claims),
        )
