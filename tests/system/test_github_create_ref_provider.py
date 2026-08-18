from __future__ import annotations

import ast
import hashlib
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
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_conformance import HandlerConformanceEvidence
from voodoo_product.execution_lease import ExecutionLease
from voodoo_product.github_create_ref_provider import (
    GITHUB_CREATE_REF_BINDER_ID,
    GITHUB_CREATE_REF_SOURCE_IDENTITY,
    GitHubCreateRefDenied,
    GitHubCreateRefHandlerContract,
    GitHubCreateRefProviderResponse,
    GitHubCreateRefRequest,
    GitHubCreateRefTargetBinder,
)
from voodoo_product.precondition_witness import ATOMIC_PROVIDER_CONDITION
from voodoo_product.runner_identity import RunnerIdentity
from voodoo_product.target_binding import TargetBinderRegistry
from voodoo_product.write_boundary import (
    GITHUB_CREATE_REF_CREDENTIAL_CLASS,
    WRITE_RUNNER_CLASS,
    CredentialAccessDecisionV2,
    CredentialBrokerPolicyV2,
    RunnerBoundaryV2,
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
COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"
REPOSITORY = "nulleimy/V-One"
REF = "refs/heads/vone-canary/f3-contract-test"


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _definition() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability=GITHUB_CREATE_REF_CAPABILITY,
        target_kind="git_ref",
        binder_id=GITHUB_CREATE_REF_BINDER_ID,
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
        capsule_revision="f3-write-capsule-r1",
    )


def _condition() -> GitHubCreateRefConditionContract:
    return GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f3-r1"
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
        evidence_revision="f3-handler-conformance-r1",
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
        requirement_revision="controlled-write-requirement/f3-r1",
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
        "execution_id": "exec_f3_write",
        "workspace_id": "wrk_f3",
        "environment": "staging",
        "execution_capsule_digest": capsule.capsule_digest,
        "runner_class": capsule.runner_class,
        "execution_epoch": epoch,
        "acquired_at": "2026-08-18T17:00:00.000+00:00",
        "expires_at": "2026-08-18T17:10:00.000+00:00",
        "clock_witness_digest": DIGESTS["clock"],
        "lease_revision": "execution-lease/f3-test-r1",
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
        provider_instance_id="gha:f3-write:contract-only",
        environment="staging",
        rootfs_digest=capsule.rootfs_digest,
        resource_limit_profile_digest=capsule.resource_limit_profile_digest,
        network_policy_digest=capsule.network_policy_digest,
        identity_revision="runner-identity/f3-write-r1",
    )


def _f2_bundle() -> tuple[RunnerBoundaryV2, ExecutionLease, CredentialAccessDecisionV2]:
    definition = _definition()
    capsule = _capsule(definition)
    condition = _condition()
    evidence = _evidence(capsule, condition)
    requirement = _requirement(definition, capsule, evidence, condition)
    lease = _lease(capsule)
    boundary = RunnerBoundaryV2.create(
        identity=_identity(capsule),
        lease=lease,
        capsule=capsule,
        definition=definition,
        handler_evidence=evidence,
        provider_condition=condition,
        requirement=requirement,
        boundary_revision="runner-boundary/f3-r1",
    )
    policy = CredentialBrokerPolicyV2.create(
        boundary=boundary,
        max_ttl_seconds=120,
        policy_revision="credential-broker-policy/f3-r1",
    )
    decision = CredentialAccessDecisionV2.create(
        boundary=boundary,
        lease=lease,
        policy=policy,
        decision_revision="credential-access-decision/f3-r1",
    )
    return boundary, lease, decision


def _target_binding():
    definition = _definition()
    registry = TargetBinderRegistry(
        {GITHUB_CREATE_REF_BINDER_ID: GitHubCreateRefTargetBinder()}
    )
    return registry.bind(
        definition=definition,
        approved_payload={
            "repository": REPOSITORY,
            "ref": REF,
            "commit_sha": COMMIT_SHA,
        },
    )


def _request() -> GitHubCreateRefRequest:
    boundary, _, decision = _f2_bundle()
    handler = GitHubCreateRefHandlerContract(request_revision="github-create-ref-request/f3-r1")
    return handler.prepare_request(
        target_binding=_target_binding(),
        boundary=boundary,
        decision=decision,
    )


def test_create_ref_target_binder_binds_exact_repository_ref_and_commit() -> None:
    binding = _target_binding()

    assert binding.binder_id == GITHUB_CREATE_REF_BINDER_ID
    assert binding.target.target_kind == "git_ref"
    assert binding.target.target_claims == {
        "repository": REPOSITORY,
        "ref": REF,
        "commit_sha": COMMIT_SHA,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"repository": REPOSITORY, "ref": REF},
        {"repository": REPOSITORY, "ref": "refs/heads/main", "commit_sha": COMMIT_SHA},
        {"repository": REPOSITORY, "ref": REF, "commit_sha": COMMIT_SHA.upper()},
        {
            "repository": REPOSITORY,
            "ref": REF,
            "commit_sha": COMMIT_SHA,
            "force": True,
        },
    ],
)
def test_create_ref_target_binder_rejects_non_exact_or_non_canary_targets(
    payload: dict[str, object],
) -> None:
    with pytest.raises(GitHubCreateRefDenied):
        GitHubCreateRefTargetBinder().bind(approved_payload=payload)


def test_handler_prepares_content_addressed_request_bound_to_f2_metadata() -> None:
    boundary, _, decision = _f2_bundle()
    binding = _target_binding()
    handler = GitHubCreateRefHandlerContract(request_revision="github-create-ref-request/f3-r1")

    request = handler.prepare_request(
        target_binding=binding,
        boundary=boundary,
        decision=decision,
    )

    assert request.repository == REPOSITORY
    assert request.ref == REF
    assert request.sha == COMMIT_SHA
    assert request.target_digest == binding.target.target_digest
    assert request.target_binding_digest == binding.binding_digest
    assert request.runner_boundary_digest == boundary.boundary_digest
    assert request.credential_decision_digest == decision.decision_digest
    assert request.operation == "CREATE_REF"
    assert request.create_semantics == "CREATE_ONLY"
    assert request.max_provider_mutations == 1
    assert GitHubCreateRefRequest.from_dict(request.to_dict()) == request


@pytest.mark.parametrize("status_code", [409, 422])
def test_negative_overwrite_provider_rejections_fail_closed_without_fallback(
    status_code: int,
) -> None:
    request = _request()
    handler = GitHubCreateRefHandlerContract(request_revision="github-create-ref-request/f3-r1")
    response = GitHubCreateRefProviderResponse.rejected(
        status_code=status_code,
        source_identity=GITHUB_CREATE_REF_SOURCE_IDENTITY,
        response_revision="github-create-ref-response/f3-r1",
    )

    with pytest.raises(
        GitHubCreateRefDenied,
        match="F3_CREATE_REF_PROVIDER_REJECTED_CREATE_ONLY",
    ):
        handler.interpret_response(request=request, response=response)


def test_success_response_must_echo_exact_ref_and_commit() -> None:
    request = _request()
    handler = GitHubCreateRefHandlerContract(request_revision="github-create-ref-request/f3-r1")
    good = GitHubCreateRefProviderResponse.created(
        ref=request.ref,
        object_sha=request.sha,
        source_identity=GITHUB_CREATE_REF_SOURCE_IDENTITY,
        response_revision="github-create-ref-response/f3-r1",
    )
    assert handler.interpret_response(request=request, response=good) == good
    assert GitHubCreateRefProviderResponse.from_dict(good.to_dict()) == good

    wrong_ref = GitHubCreateRefProviderResponse.created(
        ref="refs/heads/vone-canary/other-target",
        object_sha=request.sha,
        source_identity=GITHUB_CREATE_REF_SOURCE_IDENTITY,
        response_revision="github-create-ref-response/f3-r1",
    )
    with pytest.raises(GitHubCreateRefDenied, match="RESPONSE_REF_MISMATCH"):
        handler.interpret_response(request=request, response=wrong_ref)

    wrong_sha = GitHubCreateRefProviderResponse.created(
        ref=request.ref,
        object_sha="f" * 40,
        source_identity=GITHUB_CREATE_REF_SOURCE_IDENTITY,
        response_revision="github-create-ref-response/f3-r1",
    )
    with pytest.raises(GitHubCreateRefDenied, match="RESPONSE_OBJECT_MISMATCH"):
        handler.interpret_response(request=request, response=wrong_sha)


def test_f3_exposes_no_update_delete_force_or_live_http_implementation() -> None:
    source = Path("voodoo_product/github_create_ref_provider.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    protocol = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "GitHubCreateRefTransport"
    )
    transport_methods = [
        node.name
        for node in protocol.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert transport_methods == ["create_ref"]

    handler = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "GitHubCreateRefHandlerContract"
    )
    handler_methods = {
        node.name
        for node in handler.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert handler_methods == {"__init__", "prepare_request", "interpret_response"}

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert not imported_roots.intersection(
        {"httpx", "requests", "subprocess", "urllib", "socket"}
    )
    assert "GITHUB_TOKEN" not in source
    assert "Authorization: Bearer" not in source
    assert "update_ref" not in source
    assert "force_update" not in source


def test_f3_handler_identity_is_exact() -> None:
    definition = _definition()
    assert definition.capability == GITHUB_CREATE_REF_CAPABILITY
    assert definition.handler_id == GITHUB_CREATE_REF_HANDLER
