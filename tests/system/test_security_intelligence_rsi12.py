from __future__ import annotations

import pytest

from voodoo_product.security_intelligence import (
    AuthorityDisposition,
    EffectClass,
    RiskClass,
    SkillStatus,
)
from voodoo_product.security_intelligence_normalization import (
    DiscoveryLevel,
    ExternalCapability,
    ExternalSkill,
    ExternalSkillNormalizer,
    FrameworkMapping,
    MappingStatus,
    NormalizationStatus,
    ProgressiveDiscovery,
)


def _discovery(
    *,
    source: str = "github:mukul975/Anthropic-Cybersecurity-Skills",
    content: bool = False,
) -> ProgressiveDiscovery:
    return ProgressiveDiscovery.create(
        source=source,
        source_skill_ref="skills/example-skill",
        index_ref="repo:skills-index",
        metadata_ref="skills/example-skill:frontmatter",
        content_ref="skills/example-skill/SKILL.md" if content else None,
    )


def _mapping(
    *,
    framework: str = "MITRE ATT&CK",
    evidence_refs: tuple[str, ...] = ("source:frontmatter",),
) -> FrameworkMapping:
    return FrameworkMapping.create(
        framework=framework,
        external_id="T1059",
        evidence_refs=evidence_refs,
    )


def _capability(
    *,
    effect_class: str = "READ",
    risk_class: str = "MEDIUM",
    sandbox_constraints: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = ("source:capability",),
) -> ExternalCapability:
    return ExternalCapability(
        capability_id="security.external.example/v1",
        source_capability="analyze external security evidence",
        effect_class=effect_class,
        risk_class=risk_class,
        resource_scope="metadata-only",
        sandbox_constraints=sandbox_constraints,
        evidence_refs=evidence_refs,
    )


def _external(
    *,
    source: str = "github:mukul975/Anthropic-Cybersecurity-Skills",
    discovery: ProgressiveDiscovery | None = None,
    capabilities: tuple[ExternalCapability, ...] | None = None,
    mappings: tuple[FrameworkMapping, ...] | None = None,
    evidence_refs: tuple[str, ...] = ("source:skill",),
) -> ExternalSkill:
    return ExternalSkill(
        source=source,
        skill_id="external.security.example",
        version="1",
        domain="security",
        content_ref="skills/example-skill/SKILL.md",
        discovery=discovery or _discovery(source=source),
        capabilities=capabilities or (_capability(),),
        framework_mappings=mappings or (_mapping(),),
        evidence_refs=evidence_refs,
    )


def test_supported_framework_with_evidence_normalizes() -> None:
    mapping = _mapping()

    assert mapping.status is MappingStatus.NORMALIZED
    assert mapping.to_reference() == "MITRE ATT&CK:T1059"


def test_unknown_framework_remains_unknown() -> None:
    mapping = _mapping(framework="UNRECOGNIZED FRAMEWORK")

    assert mapping.status is MappingStatus.UNKNOWN
    assert mapping.to_reference() == "UNKNOWN:T1059"


def test_framework_without_evidence_remains_unknown() -> None:
    mapping = _mapping(evidence_refs=())

    assert mapping.status is MappingStatus.UNKNOWN


def test_progressive_discovery_index_only() -> None:
    discovery = ProgressiveDiscovery.create(
        source="github:example/repo",
        source_skill_ref="skill-a",
        index_ref="index",
    )

    assert discovery.level is DiscoveryLevel.INDEX
    assert discovery.metadata_ref is None
    assert discovery.content_ref is None


def test_progressive_discovery_metadata_without_content() -> None:
    discovery = ProgressiveDiscovery.create(
        source="github:example/repo",
        source_skill_ref="skill-a",
        index_ref="index",
        metadata_ref="frontmatter",
    )

    assert discovery.level is DiscoveryLevel.METADATA
    assert discovery.content_ref is None


def test_progressive_discovery_content_requires_progression() -> None:
    discovery = ProgressiveDiscovery.create(
        source="github:example/repo",
        source_skill_ref="skill-a",
        index_ref="index",
        metadata_ref="frontmatter",
        content_ref="SKILL.md",
    )

    assert discovery.level is DiscoveryLevel.CONTENT


def test_external_skill_is_always_proposed() -> None:
    result = ExternalSkillNormalizer().normalize(_external())

    assert result.skill_manifest.status is SkillStatus.PROPOSED


def test_normalization_never_creates_execution_authority_or_runtime_binding() -> None:
    result = ExternalSkillNormalizer().normalize(_external())

    assert result.requires_vop_evaluation is True
    assert result.creates_execution_authority is False
    assert result.creates_runtime_binding is False


def test_fully_evidenced_metadata_normalizes() -> None:
    result = ExternalSkillNormalizer().normalize(_external())

    assert result.status is NormalizationStatus.NORMALIZED
    assert result.capability_manifests[0].normalization_status == "NORMALIZED"


def test_missing_skill_evidence_keeps_result_unknown() -> None:
    result = ExternalSkillNormalizer().normalize(_external(evidence_refs=()))

    assert result.status is NormalizationStatus.UNKNOWN


def test_missing_capability_evidence_keeps_capability_unknown() -> None:
    result = ExternalSkillNormalizer().normalize(
        _external(
            capabilities=(
                _capability(evidence_refs=()),
            )
        )
    )

    assert result.status is NormalizationStatus.UNKNOWN
    assert result.capability_manifests[0].normalization_status == "UNKNOWN"


def test_unknown_effect_fails_closed() -> None:
    result = ExternalSkillNormalizer().normalize(
        _external(
            capabilities=(
                _capability(effect_class="MAGIC"),
            )
        )
    )
    capability = result.capability_manifests[0]

    assert capability.effect_class is EffectClass.UNKNOWN
    assert capability.required_authority.approval_required is True
    assert result.status is NormalizationStatus.UNKNOWN


def test_active_effect_without_sandbox_constraints_fails_closed() -> None:
    result = ExternalSkillNormalizer().normalize(
        _external(
            capabilities=(
                _capability(effect_class="NETWORK"),
            )
        )
    )
    capability = result.capability_manifests[0]

    assert capability.effect_class is EffectClass.UNKNOWN
    assert capability.normalization_status == "UNKNOWN"
    assert result.status is NormalizationStatus.UNKNOWN


def test_active_effect_with_constraints_can_normalize_metadata() -> None:
    result = ExternalSkillNormalizer().normalize(
        _external(
            capabilities=(
                _capability(
                    effect_class="NETWORK",
                    sandbox_constraints=("network-egress-policy-required",),
                ),
            )
        )
    )
    capability = result.capability_manifests[0]

    assert capability.effect_class is EffectClass.NETWORK
    assert capability.normalization_status == "NORMALIZED"
    assert capability.required_authority.execution_grant_required is True
    assert capability.required_authority.isolated_runner_required is True


def test_unknown_framework_makes_overall_normalization_unknown() -> None:
    result = ExternalSkillNormalizer().normalize(
        _external(
            mappings=(
                _mapping(framework="UNRECOGNIZED FRAMEWORK"),
            )
        )
    )

    assert result.status is NormalizationStatus.UNKNOWN
    assert result.skill_manifest.framework_mappings == ("UNKNOWN:T1059",)


def test_critical_risk_preserves_deny_policy() -> None:
    result = ExternalSkillNormalizer().normalize(
        _external(
            capabilities=(
                _capability(risk_class="CRITICAL"),
            )
        )
    )
    capability = result.capability_manifests[0]

    assert capability.risk_class is RiskClass.CRITICAL
    assert capability.required_authority.default_disposition is AuthorityDisposition.DENY


def test_content_discovery_rejects_content_ref_mismatch() -> None:
    discovery = ProgressiveDiscovery.create(
        source="github:mukul975/Anthropic-Cybersecurity-Skills",
        source_skill_ref="skills/example-skill",
        index_ref="repo:skills-index",
        metadata_ref="skills/example-skill:frontmatter",
        content_ref="skills/example-skill/DIFFERENT.md",
    )

    with pytest.raises(ValueError, match="content_ref provenance mismatch"):
        ExternalSkillNormalizer().normalize(_external(discovery=discovery))


def test_source_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="discovery source mismatch"):
        ExternalSkillNormalizer().normalize(
            _external(
                discovery=_discovery(source="github:different/repo"),
            )
        )


def test_external_skill_without_capabilities_is_rejected() -> None:
    external = ExternalSkill(
        source="github:example/repo",
        skill_id="external.security.example",
        version="1",
        domain="security",
        content_ref="SKILL.md",
        discovery=ProgressiveDiscovery.create(
            source="github:example/repo",
            source_skill_ref="skill-a",
            index_ref="index",
            metadata_ref="frontmatter",
        ),
        capabilities=(),
        evidence_refs=("source:skill",),
    )

    with pytest.raises(ValueError, match="at least one capability"):
        ExternalSkillNormalizer().normalize(external)


def test_normalization_identity_is_deterministic() -> None:
    normalizer = ExternalSkillNormalizer()

    first = normalizer.normalize(_external())
    second = normalizer.normalize(_external())

    assert first.result_identity == second.result_identity
    assert first.to_dict() == second.to_dict()
