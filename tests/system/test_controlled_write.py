from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.controlled_write import (
    CONTROLLED_WRITE_REQUIREMENT_TYPE,
    GITHUB_CREATE_REF_CAPABILITY,
    GITHUB_CREATE_REF_CONDITION_TYPE,
    GITHUB_CREATE_REF_HANDLER,
    MUTATION_REVERSIBLE_EFFECT_CLASS,
    PROVIDER_READ_VERIFICATION_CLASS,
    ControlledWriteDenied,
    ControlledWriteRequirement,
    GitHubCreateRefConditionContract,
)
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_conformance import HandlerConformanceEvidence
from voodoo_product.precondition_witness import ATOMIC_PROVIDER_CONDITION, READ_THEN_COMPARE
from voodoo_product.runner_identity import READ_ONLY_EFFECT_CLASS, RUNNER_BOUNDARY_TYPE

DIGESTS = {
    "handler": "1" * 64,
    "module": "2" * 64,
    "artifact": "3" * 64,
    "rootfs": "4" * 64,
    "lock": "5" * 64,
    "sbom": "6" * 64,
    "network": "7" * 64,
    "resources": "8" * 64,
    "verification": "9" * 64,
}


def _definition(
    *,
    effect_class: str = MUTATION_REVERSIBLE_EFFECT_CLASS,
    supported_environments: tuple[str, ...] = ("staging",),
    production_eligible: bool = False,
) -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability=GITHUB_CREATE_REF_CAPABILITY,
        target_kind="git_ref",
        binder_id="github-create-ref-target/v1",
        handler_id=GITHUB_CREATE_REF_HANDLER,
        effect_class=effect_class,
        verification_class=PROVIDER_READ_VERIFICATION_CLASS,
        supported_environments=supported_environments,
        required_permissions=("execution.run",),
        production_eligible=production_eligible,
    )


def _capsule(
    definition: CapabilityDefinition,
    *,
    enforcement: str = ATOMIC_PROVIDER_CONDITION,
) -> ExecutionCapsule:
    return ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest=DIGESTS["handler"],
        module_manifest_digest=DIGESTS["module"],
        artifact_kind="oci-image",
        artifact_digest=DIGESTS["artifact"],
        rootfs_digest=DIGESTS["rootfs"],
        dependency_lock_digest=DIGESTS["lock"],
        sbom_digest=DIGESTS["sbom"],
        network_policy_digest=DIGESTS["network"],
        resource_limit_profile_digest=DIGESTS["resources"],
        credential_class="github.create-ref/scoped-v1",
        runner_class="github-actions.docker-isolated-write/v1",
        precondition_enforcement_class=enforcement,
        verification_class=definition.verification_class,
        verification_contract_identity=DIGESTS["verification"],
        capsule_revision="f1-controlled-write-capsule-r1",
    )


def _evidence(
    capsule: ExecutionCapsule,
    condition: GitHubCreateRefConditionContract,
) -> HandlerConformanceEvidence:
    return HandlerConformanceEvidence.create(
        capability_definition_identity=capsule.capability_definition_identity,
        execution_capsule_digest=capsule.capsule_digest,
        handler_id=capsule.handler_id,
        handler_digest=capsule.handler_digest,
        runner_class=capsule.runner_class,
        credential_class=capsule.credential_class,
        precondition_enforcement_class=capsule.precondition_enforcement_class,
        verification_contract_identity=capsule.verification_contract_identity,
        atomic_provider_condition_contract_identity=(
            condition.contract_digest
            if capsule.precondition_enforcement_class == ATOMIC_PROVIDER_CONDITION
            else None
        ),
        evidence_revision="f1-handler-conformance-r1",
    )


def _requirement() -> ControlledWriteRequirement:
    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r1"
    )
    definition = _definition()
    capsule = _capsule(definition)
    evidence = _evidence(capsule, condition)
    return ControlledWriteRequirement.create(
        definition=definition,
        capsule=capsule,
        handler_evidence=evidence,
        provider_condition=condition,
        requirement_revision="controlled-write-requirement/f1-r1",
    )


def test_github_create_ref_condition_is_create_only_and_round_trippable() -> None:
    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r1"
    )

    assert condition.create_semantics == "CREATE_ONLY"
    assert condition.overwrite_existing_ref_allowed is False
    assert condition.force_update_allowed is False
    assert condition.ref_namespace_prefix == "refs/heads/vone-canary/"
    assert condition.rollback_strategy == "DELETE_EXACT_CREATED_REF"
    assert GitHubCreateRefConditionContract.from_dict(condition.to_dict()) == condition
    assert condition.to_dict()["condition_type"] == GITHUB_CREATE_REF_CONDITION_TYPE


def test_controlled_write_requirement_binds_exact_capsule_handler_and_condition() -> None:
    requirement = _requirement()

    assert requirement.effect_class == MUTATION_REVERSIBLE_EFFECT_CLASS
    assert requirement.max_provider_mutations == 1
    assert requirement.provider_mutation_allowed is True
    assert requirement.rollback_strategy == "DELETE_EXACT_CREATED_REF"
    assert ControlledWriteRequirement.from_dict(requirement.to_dict()) == requirement
    assert requirement.to_dict()["requirement_type"] == CONTROLLED_WRITE_REQUIREMENT_TYPE


def test_f1_denies_read_only_capability() -> None:
    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r1"
    )
    definition = _definition(effect_class=READ_ONLY_EFFECT_CLASS)
    capsule = _capsule(definition)
    evidence = _evidence(capsule, condition)

    with pytest.raises(ControlledWriteDenied, match="F1_EFFECT_NOT_REVERSIBLE_MUTATION"):
        ControlledWriteRequirement.create(
            definition=definition,
            capsule=capsule,
            handler_evidence=evidence,
            provider_condition=condition,
            requirement_revision="controlled-write-requirement/f1-r1",
        )


def test_f1_denies_read_then_compare_for_provider_mutation() -> None:
    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r1"
    )
    definition = _definition()
    capsule = _capsule(definition, enforcement=READ_THEN_COMPARE)
    evidence = _evidence(capsule, condition)

    with pytest.raises(ControlledWriteDenied, match="F1_CAPSULE_BINDING_MISMATCH"):
        ControlledWriteRequirement.create(
            definition=definition,
            capsule=capsule,
            handler_evidence=evidence,
            provider_condition=condition,
            requirement_revision="controlled-write-requirement/f1-r1",
        )


def test_f1_denies_production_eligible_capability() -> None:
    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r1"
    )
    definition = _definition(
        supported_environments=("production", "staging"),
        production_eligible=True,
    )
    capsule = _capsule(definition)
    evidence = _evidence(capsule, condition)

    with pytest.raises(ControlledWriteDenied, match="F1_PRODUCTION_ELIGIBILITY_FORBIDDEN"):
        ControlledWriteRequirement.create(
            definition=definition,
            capsule=capsule,
            handler_evidence=evidence,
            provider_condition=condition,
            requirement_revision="controlled-write-requirement/f1-r1",
        )


def test_f1_denies_atomic_provider_contract_substitution() -> None:
    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r1"
    )
    other_condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r2"
    )
    definition = _definition()
    capsule = _capsule(definition)
    evidence = _evidence(capsule, other_condition)

    with pytest.raises(ControlledWriteDenied, match="F1_ATOMIC_PROVIDER_CONDITION_MISMATCH"):
        ControlledWriteRequirement.create(
            definition=definition,
            capsule=capsule,
            handler_evidence=evidence,
            provider_condition=condition,
            requirement_revision="controlled-write-requirement/f1-r1",
        )


def test_condition_and_requirement_reject_unknown_or_tampered_fields() -> None:
    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f1-r1"
    )
    condition_payload = condition.to_dict()
    condition_payload["force_update_allowed"] = True
    with pytest.raises(ValueError, match="must not force-update"):
        GitHubCreateRefConditionContract.from_dict(condition_payload)

    requirement_payload = _requirement().to_dict()
    requirement_payload["unknown"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        ControlledWriteRequirement.from_dict(requirement_payload)


def test_f1_adds_no_provider_transport_or_secret_delivery() -> None:
    source = Path("voodoo_product/controlled_write.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert not imported_roots.intersection({"httpx", "requests", "subprocess", "urllib"})
    assert "token" not in ControlledWriteRequirement.__dataclass_fields__
    assert "secret" not in ControlledWriteRequirement.__dataclass_fields__


def test_phase_d_runner_boundary_v1_remains_frozen_read_only() -> None:
    assert RUNNER_BOUNDARY_TYPE == "runner-boundary/v1"
    assert READ_ONLY_EFFECT_CLASS == "READ_ONLY"

    text = Path("voodoo_product/runner_identity.py").read_text(encoding="utf-8")
    assert 'RUNNER_BOUNDARY_TYPE: Final = "runner-boundary/v1"' in text
    assert 'READ_ONLY_EFFECT_CLASS: Final = "READ_ONLY"' in text
    assert "Phase-D provider mutation must remain disabled" in text
