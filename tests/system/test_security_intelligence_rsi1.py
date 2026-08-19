from __future__ import annotations

from dataclasses import replace

import pytest

from voodoo_product.security_intelligence import (
    AuthorityDisposition,
    AuthorityRequirement,
    CapabilityManifest,
    EffectClass,
    RiskClass,
    SkillManifest,
    SkillStatus,
)


def skill_manifest() -> SkillManifest:
    return SkillManifest.create(
        skill_id="external-security-review",
        version="1.0.0",
        source="github:example/security-skill@abc123",
        domain="application-security",
        capability_ids=(
            "security.inspect-config/v1",
            "security.read-source/v1",
        ),
        risk_class=RiskClass.MEDIUM,
        authority_requirements=("vop-policy-evaluation",),
        framework_mappings=("owasp-asvs",),
        evidence_requirements=("source-provenance",),
        verification_requirements=("evidence-binding",),
        content_ref="github:example/security-skill@abc123:skill.md",
    )


def test_skill_manifest_is_deterministic_and_proposed_by_default() -> None:
    first = skill_manifest()
    second = SkillManifest.create(
        skill_id="external-security-review",
        version="1.0.0",
        source="github:example/security-skill@abc123",
        domain="application-security",
        capability_ids=tuple(reversed(first.capability_ids)),
        risk_class=RiskClass.MEDIUM,
        authority_requirements=("vop-policy-evaluation",),
        framework_mappings=("owasp-asvs",),
        evidence_requirements=("source-provenance",),
        verification_requirements=("evidence-binding",),
        content_ref="github:example/security-skill@abc123:skill.md",
    )

    assert first == second
    assert first.status is SkillStatus.PROPOSED


def test_skill_manifest_contract_supports_governed_lifecycle_states() -> None:
    blocked = SkillManifest.create(
        skill_id="external-security-review",
        version="1.0.0",
        source="github:example/security-skill@abc123",
        domain="application-security",
        capability_ids=("security.read-source/v1",),
        risk_class=RiskClass.HIGH,
        authority_requirements=("human-approval",),
        framework_mappings=(),
        evidence_requirements=("source-provenance",),
        verification_requirements=("evidence-binding",),
        content_ref="github:example/security-skill@abc123:skill.md",
        status=SkillStatus.BLOCKED,
    )

    assert blocked.status is SkillStatus.BLOCKED


def test_effect_vocabulary_matches_rsi1_contract() -> None:
    assert {effect.value for effect in EffectClass if effect is not EffectClass.UNKNOWN} == {
        "READ",
        "COMPUTE",
        "NETWORK",
        "WRITE",
        "EXECUTE",
    }


def test_unknown_capability_classification_fails_closed() -> None:
    requirement = AuthorityRequirement.classify(
        risk_class=RiskClass.UNKNOWN,
        effect_class=EffectClass.UNKNOWN,
    )

    assert requirement.default_disposition is AuthorityDisposition.UNKNOWN
    assert requirement.approval_required is True


def test_low_risk_read_is_distinct_from_active_execution() -> None:
    requirement = AuthorityRequirement.classify(
        risk_class=RiskClass.LOW,
        effect_class=EffectClass.READ,
    )

    assert requirement.default_disposition is AuthorityDisposition.REQUIRE_VOP_EVALUATION
    assert requirement.execution_grant_required is False
    assert requirement.isolated_runner_required is False
    assert requirement.independent_verification_required is False


def test_network_capability_requires_grant_and_isolated_runner() -> None:
    requirement = AuthorityRequirement.classify(
        risk_class=RiskClass.MEDIUM,
        effect_class=EffectClass.NETWORK,
    )

    assert requirement.execution_grant_required is True
    assert requirement.isolated_runner_required is True


def test_write_capability_requires_human_and_verification() -> None:
    requirement = AuthorityRequirement.classify(
        risk_class=RiskClass.HIGH,
        effect_class=EffectClass.WRITE,
    )

    assert requirement.default_disposition is AuthorityDisposition.REQUIRE_HUMAN
    assert requirement.approval_required is True
    assert requirement.execution_grant_required is True
    assert requirement.isolated_runner_required is True
    assert requirement.independent_verification_required is True


def test_critical_capability_defaults_to_deny() -> None:
    requirement = AuthorityRequirement.classify(
        risk_class=RiskClass.CRITICAL,
        effect_class=EffectClass.EXECUTE,
    )

    assert requirement.default_disposition is AuthorityDisposition.DENY


def test_evidence_less_read_capability_remains_unknown() -> None:
    manifest = CapabilityManifest.create(
        capability_id="security.inspect-config/v1",
        skill_id="external-security-review",
        source_capability="inspect configuration",
        effect_class=EffectClass.READ,
        resource_scope="repository:configuration",
        risk_class=RiskClass.MEDIUM,
    )

    assert manifest.normalization_status == "UNKNOWN"
    assert manifest.evidence_refs == ()


def test_normalized_capability_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence-less"):
        CapabilityManifest.create(
            capability_id="security.inspect-config/v1",
            skill_id="external-security-review",
            source_capability="inspect configuration",
            effect_class=EffectClass.READ,
            resource_scope="repository:configuration",
            risk_class=RiskClass.MEDIUM,
            normalization_status="NORMALIZED",
        )


def test_active_capability_requires_sandbox_constraints() -> None:
    with pytest.raises(ValueError, match="sandbox constraints"):
        CapabilityManifest.create(
            capability_id="security.network-query/v1",
            skill_id="external-security-review",
            source_capability="query approved endpoint",
            effect_class=EffectClass.NETWORK,
            resource_scope="network:approved-endpoint",
            risk_class=RiskClass.MEDIUM,
            evidence_refs=("source:skill.md",),
            normalization_status="NORMALIZED",
        )


def test_normalized_capability_binds_required_authority() -> None:
    manifest = CapabilityManifest.create(
        capability_id="security.network-query/v1",
        skill_id="external-security-review",
        source_capability="query approved endpoint",
        effect_class=EffectClass.NETWORK,
        resource_scope="network:approved-endpoint",
        risk_class=RiskClass.MEDIUM,
        sandbox_constraints=("network-allowlist-required",),
        evidence_refs=("source:skill.md",),
        normalization_status="NORMALIZED",
    )

    assert manifest.required_authority.effect_class is EffectClass.NETWORK
    assert manifest.required_authority.execution_grant_required is True


def test_tampered_skill_manifest_identity_is_rejected() -> None:
    manifest = skill_manifest()

    with pytest.raises(ValueError, match="manifest_identity"):
        replace(manifest, manifest_identity="0" * 64)
