from __future__ import annotations

import hashlib
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_receipt_v2 import (
    EFFECT_RECORDED,
    EXECUTION_SUCCEEDED,
    NOT_EVALUATED,
    ExecutionReceiptV2,
)
from voodoo_product.operation_cell_v1 import (
    OPERATION_CELL_V1_TYPE,
    OperationCellV1,
    OperationCellV1Denied,
    create_operation_cell_v1_from_absence,
)
from voodoo_product.operation_proof_v2 import OperationProofV2
from voodoo_product.operation_proof_v2_absence import (
    create_operation_proof_v2_from_absence,
)
from voodoo_product.rollback_verification import (
    GitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    VerifierGitHubRefAbsenceObservation,
    verify_github_ref_absence,
)
from voodoo_product.verification_result import (
    INDEPENDENT_PROVIDER_READBACK,
    VERIFIED,
    ObservedPostState,
    VerificationResult,
    VerificationStrength,
)
from voodoo_product.verifier_identity import INDEPENDENCE_CLASS

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
D6 = "6" * 64
D7 = "7" * 64
D8 = "8" * 64
DA = "a" * 64
DB = "b" * 64
DC = "c" * 64
DD = "d" * 64
DE = "e" * 64
DF = "f" * 64


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _receipt(
    *,
    execution_id: str,
    request_id: str,
    environment: str,
    capability: str,
    target_digest: str,
    recorded_at: str = "2026-08-18T11:59:00.000+00:00",
) -> ExecutionReceiptV2:
    return ExecutionReceiptV2.create(
        execution_id=execution_id,
        request_id=request_id,
        environment=environment,
        capability=capability,
        target_digest=target_digest,
        authorization_snapshot_digest=D2,
        execution_grant_digest=D3,
        execution_capsule_digest=D4,
        grant_consumption_witness_digest=D5,
        dispatch_envelope_digest=D6,
        dispatch_admission_digest=D7,
        execution_lease_digest=D8,
        runner_identity_digest=DA,
        runner_boundary_digest=DB,
        credential_access_decision_digest=DC,
        runtime_activation_digest=DD,
        write_effect_preflight_digest=DE,
        provider_operation="DELETE_REF",
        provider_request_digest=DF,
        provider_response_digest=D4,
        provider_mutation_performed=True,
        provider_mutation_count=1,
        automatic_retry_performed=False,
        rollback_performed=True,
        durable_completion_outcome="COMPLETED",
        durable_completion_digest=D4,
        execution_status=EXECUTION_SUCCEEDED,
        effect_status=EFFECT_RECORDED,
        verification_status=NOT_EVALUATED,
        recording_clock_witness_digest=D5,
        recorded_at=recorded_at,
        receipt_revision="execution-receipt/f6b-cell-test-r1",
    )


def _runner(
    *,
    execution_id: str,
    execution_epoch: int,
    target_digest: str,
) -> GitHubRefAbsenceObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "github-ref-absence-observation/v1",
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/vone-canary/f6b-cell-test",
        "target_digest": target_digest,
        "provider": "github",
        "provider_instance_id": "gha:f6b-cell-runner:test",
        "runner_id": D2,
        "runner_identity_digest": D3,
        "runner_boundary_digest": D4,
        "execution_id": execution_id,
        "execution_epoch": execution_epoch,
        "source_identity": "github-api-runner-readback/f6b-cell-test-r1",
        "http_status": 404,
        "presence": "ABSENT",
        "observed_at": "2026-08-18T12:00:00.000+00:00",
        "observation_revision": "github-ref-absence-observation/f6b-cell-test-r1",
    }
    return GitHubRefAbsenceObservation(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(claims),
    )


def _boundary(
    runner: GitHubRefAbsenceObservation,
    *,
    environment: str,
) -> IndependentVerificationBoundaryV2:
    claims: dict[str, Any] = {
        "schema_version": 2,
        "boundary_type": "independent-verification-boundary/v2",
        "verifier_id": D5,
        "verifier_identity_digest": D6,
        "verifier_provider_instance_id": "gha:f6b-cell-verifier:test",
        "verifier_credential_class": "github.actions-token.verifier-read/v1",
        "runner_id": runner.runner_id,
        "runner_identity_digest": runner.runner_identity_digest,
        "runner_boundary_digest": runner.runner_boundary_digest,
        "runner_provider_instance_id": runner.provider_instance_id,
        "runner_credential_class": "github.delete-ref/scoped-v1",
        "execution_id": runner.execution_id,
        "execution_epoch": runner.execution_epoch,
        "target_digest": runner.target_digest,
        "runner_observation_digest": runner.observation_digest,
        "environment": environment,
        "provider_mutation_allowed": False,
        "independence_class": INDEPENDENCE_CLASS,
        "boundary_revision": "independent-verification-boundary/f6b-cell-test-r1",
    }
    return IndependentVerificationBoundaryV2(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "boundary_type"}
        },
        boundary_digest=_digest(claims),
    )


def _verifier(
    runner: GitHubRefAbsenceObservation,
    boundary: IndependentVerificationBoundaryV2,
) -> VerifierGitHubRefAbsenceObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "verifier-github-ref-absence-observation/v1",
        "repository": runner.repository,
        "ref": runner.ref,
        "target_digest": runner.target_digest,
        "provider": "github",
        "provider_instance_id": boundary.verifier_provider_instance_id,
        "verifier_id": boundary.verifier_id,
        "verifier_identity_digest": boundary.verifier_identity_digest,
        "verification_boundary_digest": boundary.boundary_digest,
        "verifier_credential_decision_digest": D7,
        "runner_observation_digest": runner.observation_digest,
        "execution_id": runner.execution_id,
        "execution_epoch": runner.execution_epoch,
        "source_identity": "github-api-independent-verifier/f6b-cell-test-r1",
        "http_status": 404,
        "presence": "ABSENT",
        "observed_at": "2026-08-18T12:01:00.000+00:00",
        "observation_revision": "verifier-github-ref-absence-observation/f6b-cell-test-r1",
    }
    return VerifierGitHubRefAbsenceObservation(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(claims),
    )


def _bundle(
    *,
    execution_id: str = "exec_f6b_cell",
    execution_epoch: int = 1,
    request_id: str = "req_f6b_cell",
    environment: str = "staging",
    capability: str = "github.delete-exact-created-ref/v1",
    target_digest: str = D1,
    recorded_at: str = "2026-08-18T11:59:00.000+00:00",
) -> tuple[
    ExecutionReceiptV2,
    GitHubRefAbsenceObservation,
    VerifierGitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    ObservedPostState,
    VerificationStrength,
    VerificationResult,
    OperationProofV2,
]:
    receipt = _receipt(
        execution_id=execution_id,
        request_id=request_id,
        environment=environment,
        capability=capability,
        target_digest=target_digest,
        recorded_at=recorded_at,
    )
    runner = _runner(
        execution_id=execution_id,
        execution_epoch=execution_epoch,
        target_digest=target_digest,
    )
    boundary = _boundary(runner, environment=environment)
    verifier = _verifier(runner, boundary)
    state, strength, result = verify_github_ref_absence(
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state_revision="observed-post-state/f6b-cell-test-r1",
        strength_revision="verification-strength/f6b-cell-test-r1",
        result_revision="verification-result/f6b-cell-test-r1",
    )
    proof = create_operation_proof_v2_from_absence(
        receipt=receipt,
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state=state,
        verification_strength=strength,
        verification=result,
        proof_revision="operation-proof/f6b-cell-test-r1",
    )
    return receipt, runner, verifier, boundary, state, strength, result, proof


def _compose(
    source: tuple[
        ExecutionReceiptV2,
        GitHubRefAbsenceObservation,
        VerifierGitHubRefAbsenceObservation,
        IndependentVerificationBoundaryV2,
        ObservedPostState,
        VerificationStrength,
        VerificationResult,
        OperationProofV2,
    ],
    *,
    proof: OperationProofV2 | None = None,
    receipt: ExecutionReceiptV2 | None = None,
) -> OperationCellV1:
    canonical_receipt, runner, verifier, boundary, state, strength, result, canonical_proof = source
    return create_operation_cell_v1_from_absence(
        proof=proof or canonical_proof,
        receipt=receipt or canonical_receipt,
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state=state,
        verification_strength=strength,
        verification=result,
        cell_revision="operation-cell/f6b-test-r1",
    )


def test_operation_cell_v1_is_minimal_deterministic_and_round_trippable() -> None:
    source = _bundle()
    cell = _compose(source)
    value = cell.to_dict()

    assert frozenset(value) == {
        "schema_version",
        "cell_type",
        "execution_id",
        "execution_epoch",
        "request_id",
        "environment",
        "capability",
        "target_digest",
        "proof_type",
        "operation_proof_digest",
        "final_verdict",
        "verification_strength_class",
        "cell_revision",
        "cell_digest",
    }
    assert value["cell_type"] == OPERATION_CELL_V1_TYPE
    assert OperationCellV1.from_dict(value) == cell
    assert _compose(_bundle()).cell_digest == cell.cell_digest


def test_operation_cell_v1_freezes_only_proof_indexing_claims() -> None:
    source = _bundle()
    proof = source[-1]
    cell = _compose(source)

    assert cell.execution_id == proof.execution_id
    assert cell.execution_epoch == proof.execution_epoch
    assert cell.request_id == proof.request_id
    assert cell.environment == proof.environment
    assert cell.capability == proof.capability
    assert cell.target_digest == proof.target_digest
    assert cell.proof_type == "operation-proof/v2"
    assert cell.operation_proof_digest == proof.proof_digest
    assert cell.final_verdict == VERIFIED
    assert cell.verification_strength_class == INDEPENDENT_PROVIDER_READBACK


@pytest.mark.parametrize(
    "other_source",
    [
        _bundle(execution_id="exec_other"),
        _bundle(execution_epoch=2),
        _bundle(request_id="req_other"),
        _bundle(environment="production"),
        _bundle(capability="github.other-capability/v1"),
        _bundle(target_digest=DE),
    ],
    ids=["execution", "epoch", "request", "environment", "capability", "target"],
)
def test_operation_cell_v1_rejects_proof_identity_substitution(other_source: tuple[Any, ...]) -> None:
    canonical = _bundle()
    other_proof = other_source[-1]

    with pytest.raises(
        OperationCellV1Denied,
        match="OPERATION_CELL_V1_OPERATION_PROOF_MISMATCH",
    ):
        _compose(canonical, proof=other_proof)


def test_operation_cell_v1_rejects_self_consistent_forged_verified_proof() -> None:
    source = _bundle()
    proof = source[-1]
    forged_value = deepcopy(proof.to_dict())
    forged_value["verification_result_digest"] = DE
    forged_claims = {
        key: value for key, value in forged_value.items() if key != "proof_digest"
    }
    forged_value["proof_digest"] = _digest(forged_claims)
    forged = OperationProofV2.from_dict(forged_value)

    with pytest.raises(
        OperationCellV1Denied,
        match="OPERATION_CELL_V1_OPERATION_PROOF_MISMATCH",
    ):
        _compose(source, proof=forged)


def test_operation_cell_v1_rejects_receipt_execution_substitution() -> None:
    source = _bundle()
    substituted = _receipt(
        execution_id="exec_other",
        request_id="req_f6b_cell",
        environment="staging",
        capability="github.delete-exact-created-ref/v1",
        target_digest=D1,
    )

    with pytest.raises(PermissionError, match="OPERATION_PROOF_V2_EXECUTION_MISMATCH"):
        _compose(source, receipt=substituted)


def test_operation_cell_v1_rejects_receipt_target_substitution() -> None:
    source = _bundle()
    substituted = _receipt(
        execution_id="exec_f6b_cell",
        request_id="req_f6b_cell",
        environment="staging",
        capability="github.delete-exact-created-ref/v1",
        target_digest=DE,
    )

    with pytest.raises(PermissionError, match="OPERATION_PROOF_V2_TARGET_MISMATCH"):
        _compose(source, receipt=substituted)


def test_operation_cell_v1_rejects_chronology_mismatch() -> None:
    source = _bundle()
    late_receipt = _receipt(
        execution_id="exec_f6b_cell",
        request_id="req_f6b_cell",
        environment="staging",
        capability="github.delete-exact-created-ref/v1",
        target_digest=D1,
        recorded_at="2026-08-18T12:02:00.000+00:00",
    )

    with pytest.raises(PermissionError, match="OPERATION_PROOF_V2_VERIFICATION_PRECEDES_RECEIPT"):
        _compose(source, receipt=late_receipt)


def test_operation_cell_v1_rejects_tampered_serialized_cell() -> None:
    value = deepcopy(_compose(_bundle()).to_dict())
    value["operation_proof_digest"] = DE

    with pytest.raises(ValueError, match="cell_digest does not match"):
        OperationCellV1.from_dict(value)


def test_operation_cell_v1_rejects_unknown_or_missing_serialized_fields() -> None:
    value = _compose(_bundle()).to_dict()
    unknown = {**value, "unexpected": "field"}
    missing = {key: item for key, item in value.items() if key != "target_digest"}

    with pytest.raises(ValueError, match="operation-cell/v1 fields are invalid"):
        OperationCellV1.from_dict(unknown)
    with pytest.raises(ValueError, match="operation-cell/v1 fields are invalid"):
        OperationCellV1.from_dict(missing)


def test_operation_cell_v1_rejects_weaker_or_non_verified_serialized_claims() -> None:
    value = _compose(_bundle()).to_dict()

    for field, replacement, message in (
        ("verification_strength_class", "SELF_ATTESTED", "independent provider readback"),
        ("final_verdict", "FAILED", "may only freeze VERIFIED"),
    ):
        changed = deepcopy(value)
        changed[field] = replacement
        claims = {key: item for key, item in changed.items() if key != "cell_digest"}
        changed["cell_digest"] = _digest(claims)
        with pytest.raises(ValueError, match=message):
            OperationCellV1.from_dict(changed)


def test_operation_cell_v1_contains_no_duplicated_raw_or_nested_evidence() -> None:
    value = _compose(_bundle()).to_dict()
    forbidden_fields = {
        "authorization_snapshot_digest",
        "execution_grant_digest",
        "execution_receipt_digest",
        "verification_result_digest",
        "runner_observation_digest",
        "verifier_observation_digest",
        "verification_boundary_digest",
        "provider_operation",
        "provider_response_digest",
        "token",
        "secret",
        "credential",
        "operation_proof",
    }

    assert forbidden_fields.isdisjoint(value)
