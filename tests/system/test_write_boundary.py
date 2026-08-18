from __future__ import annotations

import ast
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.controlled_write import (
    GITHUB_CREATE_REF_CAPABILITY,
    GITHUB_CREATE_REF_HANDLER,
    MUTATION_REVERSIBLE_EFFECT_CLASS,
    ControlledWriteRequirement,
    GitHubCreateRefConditionContract,
)
from voodoo_product.credential_broker import (
    CREDENTIAL_ACCESS_DECISION_TYPE,
    READ_ONLY_ACCESS_MODE,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_conformance import HandlerConformanceEvidence
from voodoo_product.execution_lease import ExecutionLease
from voodoo_product.precondition_witness import ATOMIC_PROVIDER_CONDITION
from voodoo_product.runner_identity import (
    READ_ONLY_EFFECT_CLASS,
    RUNNER_BOUNDARY_TYPE,
    RunnerIdentity,
)
from voodoo_product.write_boundary import (
    CREDENTIAL_ACCESS_DECISION_V2_TYPE,
    CREDENTIAL_BROKER_POLICY_V2_TYPE,
    GITHUB_CREATE_REF_CREDENTIAL_CLASS,
    MAX_WRITE_CREDENTIAL_TTL_SECONDS,
    RUNNER_BOUNDARY_V2_TYPE,
    WRITE_BOUNDED_ACCESS_MODE,
    WRITE_RUNNER_CLASS,
    CredentialAccessDecisionV2,
    CredentialBrokerPolicyV2,
    RunnerBoundaryV2,
    WriteBoundaryDenied,
    WriteCredentialDenied,
)

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
    "dispatch": "a" * 64,
    "admission": "b" * 64,
    "admission_digest": "c" * 64,
    "clock": "d" * 64,
}


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _definition() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability=GITHUB_CREATE_REF_CAPABILITY,
        target_kind="git_ref",
        binder_id="github-create-ref-target/v1",
        handler_id=GITHUB_CREATE_REF_HANDLER,
        effect_class=MUTATION_REVERSIBLE_EFFECT_CLASS,
        verification_class="provider-read/v1",
        supported_environments=("staging",),
        required_permissions=("execution.run",),
        production_eligible=False,
    )


def _capsule(definition: CapabilityDefinition) -> ExecutionCapsule:
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
        credential_class=GITHUB_CREATE_REF_CREDENTIAL_CLASS,
        runner_class=WRITE_RUNNER_CLASS,
        precondition_enforcement_class=ATOMIC_PROVIDER_CONDITION,
        verification_class=definition.verification_class,
        verification_contract_identity=DIGESTS["verification"],
        capsule_revision="f2-write-capsule-r1",
    )


def _condition() -> GitHubCreateRefConditionContract:
    return GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f2-r1"
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
        atomic_provider_condition_contract_identity=condition.contract_digest,
        evidence_revision="f2-handler-conformance-r1",
    )


def _requirement(
    definition: CapabilityDefinition,
    capsule: ExecutionCapsule,
    evidence: HandlerConformanceEvidence,
    condition: GitHubCreateRefConditionContract,
) -> ControlledWriteRequirement:
    return ControlledWriteRequirement.create(
        definition=definition,
        capsule=capsule,
        handler_evidence=evidence,
        provider_condition=condition,
        requirement_revision="controlled-write-requirement/f2-r1",
    )


def _lease(capsule: ExecutionCapsule) -> ExecutionLease:
    epoch = 1
    admission_id = DIGESTS["admission"]
    lease_id = _digest(
        {
            "identity_type": "execution-lease-id/v1",
            "admission_id": admission_id,
            "execution_epoch": epoch,
        }
    )
    claims: dict[str, object] = {
        "schema_version": 1,
        "lease_type": "execution-lease/v1",
        "lease_id": lease_id,
        "dispatch_id": DIGESTS["dispatch"],
        "admission_id": admission_id,
        "admission_digest": DIGESTS["admission_digest"],
        "execution_id": "exec_f2_write",
        "workspace_id": "wrk_f2",
        "environment": "staging",
        "execution_capsule_digest": capsule.capsule_digest,
        "runner_class": capsule.runner_class,
        "execution_epoch": epoch,
        "acquired_at": "2026-08-18T17:00:00.000+00:00",
        "expires_at": "2026-08-18T17:10:00.000+00:00",
        "clock_witness_digest": DIGESTS["clock"],
        "lease_revision": "execution-lease/f2-test-r1",
    }
    values = {
        key: item
        for key, item in claims.items()
        if key not in {"schema_version", "lease_type"}
    }
    return ExecutionLease(**values, lease_digest=_digest(claims))  # type: ignore[arg-type]


def _identity(capsule: ExecutionCapsule) -> RunnerIdentity:
    return RunnerIdentity.create(
        runner_class=WRITE_RUNNER_CLASS,
        provider="github-actions",
        provider_instance_id="gha:f2-write:1",
        environment="staging",
        rootfs_digest=capsule.rootfs_digest,
        resource_limit_profile_digest=capsule.resource_limit_profile_digest,
        network_policy_digest=capsule.network_policy_digest,
        identity_revision="runner-identity/f2-write-r1",
    )


def _bundle() -> tuple[
    RunnerBoundaryV2,
    ExecutionLease,
    CredentialBrokerPolicyV2,
]:
    definition = _definition()
    capsule = _capsule(definition)
    condition = _condition()
    evidence = _evidence(capsule, condition)
    requirement = _requirement(definition, capsule, evidence, condition)
    lease = _lease(capsule)
    identity = _identity(capsule)
    boundary = RunnerBoundaryV2.create(
        identity=identity,
        lease=lease,
        capsule=capsule,
        definition=definition,
        handler_evidence=evidence,
        provider_condition=condition,
        requirement=requirement,
        boundary_revision="runner-boundary/f2-r1",
    )
    policy = CredentialBrokerPolicyV2.create(
        boundary=boundary,
        max_ttl_seconds=120,
        policy_revision="credential-broker-policy/f2-r1",
    )
    return boundary, lease, policy


def test_runner_boundary_v2_binds_exact_f1_write_chain() -> None:
    boundary, _, _ = _bundle()

    assert boundary.effect_ceiling == MUTATION_REVERSIBLE_EFFECT_CLASS
    assert boundary.provider_mutation_allowed is True
    assert boundary.max_provider_mutations == 1
    assert boundary.environment == "staging"
    assert boundary.runner_class == WRITE_RUNNER_CLASS
    assert boundary.credential_class == GITHUB_CREATE_REF_CREDENTIAL_CLASS
    assert RunnerBoundaryV2.from_dict(boundary.to_dict()) == boundary
    assert boundary.to_dict()["boundary_type"] == RUNNER_BOUNDARY_V2_TYPE


def test_f2_does_not_reinterpret_released_read_only_v1_contracts() -> None:
    assert RUNNER_BOUNDARY_TYPE == "runner-boundary/v1"
    assert READ_ONLY_EFFECT_CLASS == "READ_ONLY"
    assert CREDENTIAL_ACCESS_DECISION_TYPE == "credential-access-decision/v1"
    assert READ_ONLY_ACCESS_MODE == "READ_ONLY"

    runner_source = Path("voodoo_product/runner_identity.py").read_text(encoding="utf-8")
    credential_source = Path("voodoo_product/credential_broker.py").read_text(encoding="utf-8")
    assert "Phase-D provider mutation must remain disabled" in runner_source
    assert "Phase-D credential decision cannot allow provider mutation" in credential_source


def test_write_boundary_rejects_non_write_specific_runner_class() -> None:
    definition = _definition()
    capsule = _capsule(definition)
    condition = _condition()
    evidence = _evidence(capsule, condition)
    requirement = _requirement(definition, capsule, evidence, condition)
    lease = _lease(capsule)
    identity = RunnerIdentity.create(
        runner_class="github-actions.docker-isolated/v1",
        provider="github-actions",
        provider_instance_id="gha:f2-wrong-runner:1",
        environment="staging",
        rootfs_digest=capsule.rootfs_digest,
        resource_limit_profile_digest=capsule.resource_limit_profile_digest,
        network_policy_digest=capsule.network_policy_digest,
        identity_revision="runner-identity/f2-wrong-r1",
    )

    with pytest.raises(Exception, match="RUNNER_CLASS_MISMATCH"):
        RunnerBoundaryV2.create(
            identity=identity,
            lease=lease,
            capsule=capsule,
            definition=definition,
            handler_evidence=evidence,
            provider_condition=condition,
            requirement=requirement,
            boundary_revision="runner-boundary/f2-r1",
        )


def test_write_boundary_rejects_substituted_f1_requirement() -> None:
    definition = _definition()
    capsule = _capsule(definition)
    condition = _condition()
    evidence = _evidence(capsule, condition)
    requirement = _requirement(definition, capsule, evidence, condition)
    altered = requirement.to_dict()
    altered["verification_contract_identity"] = "f" * 64
    altered_without_digest = {
        key: value for key, value in altered.items() if key != "requirement_digest"
    }
    altered["requirement_digest"] = _digest(altered_without_digest)
    substituted = ControlledWriteRequirement.from_dict(altered)

    with pytest.raises(WriteBoundaryDenied, match="F2_CONTROLLED_WRITE_REQUIREMENT_MISMATCH"):
        RunnerBoundaryV2.create(
            identity=_identity(capsule),
            lease=_lease(capsule),
            capsule=capsule,
            definition=definition,
            handler_evidence=evidence,
            provider_condition=condition,
            requirement=substituted,
            boundary_revision="runner-boundary/f2-r1",
        )


def test_write_policy_and_decision_are_exact_bounded_and_round_trippable() -> None:
    boundary, lease, policy = _bundle()
    decision = CredentialAccessDecisionV2.create(
        boundary=boundary,
        lease=lease,
        policy=policy,
        decision_revision="credential-access-decision/f2-r1",
    )

    assert policy.access_mode == WRITE_BOUNDED_ACCESS_MODE
    assert policy.provider_operation == "CREATE_REF"
    assert policy.provider_mutation_allowed is True
    assert policy.max_provider_mutations == 1
    assert CredentialBrokerPolicyV2.from_dict(policy.to_dict()) == policy
    assert policy.to_dict()["policy_type"] == CREDENTIAL_BROKER_POLICY_V2_TYPE

    assert decision.access_mode == WRITE_BOUNDED_ACCESS_MODE
    assert decision.provider_operation == "CREATE_REF"
    assert decision.provider_mutation_allowed is True
    assert decision.max_provider_mutations == 1
    assert decision.controlled_write_requirement_digest == boundary.controlled_write_requirement_digest
    assert CredentialAccessDecisionV2.from_dict(decision.to_dict()) == decision
    assert decision.to_dict()["decision_type"] == CREDENTIAL_ACCESS_DECISION_V2_TYPE
    decision.assert_bound_to(boundary=boundary, lease=lease, policy=policy)


def test_write_credential_decision_ttl_is_clamped_below_lease() -> None:
    boundary, lease, _ = _bundle()
    policy = CredentialBrokerPolicyV2.create(
        boundary=boundary,
        max_ttl_seconds=120,
        policy_revision="credential-broker-policy/f2-r1",
    )
    decision = CredentialAccessDecisionV2.create(
        boundary=boundary,
        lease=lease,
        policy=policy,
        decision_revision="credential-access-decision/f2-r1",
    )

    valid_from = datetime.fromisoformat(decision.valid_from).astimezone(UTC)
    expires_at = datetime.fromisoformat(decision.expires_at).astimezone(UTC)
    lease_expires = datetime.fromisoformat(lease.expires_at).astimezone(UTC)
    assert expires_at - valid_from == timedelta(seconds=120)
    assert expires_at < lease_expires


def test_write_policy_rejects_unbounded_ttl() -> None:
    boundary, _, _ = _bundle()

    with pytest.raises(ValueError, match="max_ttl_seconds"):
        CredentialBrokerPolicyV2.create(
            boundary=boundary,
            max_ttl_seconds=MAX_WRITE_CREDENTIAL_TTL_SECONDS + 1,
            policy_revision="credential-broker-policy/f2-invalid-r1",
        )


def test_write_decision_rejects_policy_substitution() -> None:
    boundary, lease, policy = _bundle()
    wrong_payload = policy.to_dict()
    wrong_payload["controlled_write_requirement_digest"] = "e" * 64
    without_digest = {key: value for key, value in wrong_payload.items() if key != "policy_digest"}
    wrong_payload["policy_digest"] = _digest(without_digest)
    wrong_policy = CredentialBrokerPolicyV2.from_dict(wrong_payload)

    with pytest.raises(WriteCredentialDenied, match="F2_CREDENTIAL_POLICY_BINDING_MISMATCH"):
        CredentialAccessDecisionV2.create(
            boundary=boundary,
            lease=lease,
            policy=wrong_policy,
            decision_revision="credential-access-decision/f2-r1",
        )


def test_f2_contracts_contain_no_secret_material_or_provider_transport() -> None:
    boundary, lease, policy = _bundle()
    decision = CredentialAccessDecisionV2.create(
        boundary=boundary,
        lease=lease,
        policy=policy,
        decision_revision="credential-access-decision/f2-r1",
    )
    forbidden_fields = {"token", "secret", "credential", "handle", "environment_variable"}
    decision_fields = set(CredentialAccessDecisionV2.__dataclass_fields__)
    assert not {field for field in decision_fields if field in forbidden_fields}

    source = Path("voodoo_product/write_boundary.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert not imported_roots.intersection({"httpx", "requests", "subprocess", "urllib"})
    assert "github.token" not in source
    assert "GITHUB_TOKEN" not in source
    assert decision.provider == "github"
