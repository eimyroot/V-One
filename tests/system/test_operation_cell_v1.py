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
    ROLLBACK_ABSENCE_LINEAGE_V1,
    OperationCellV1,
    OperationCellV1Denied,
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


def _receipt() -> ExecutionReceiptV2:
    return ExecutionReceiptV2.create(
        execution_id="exec_f6b_cell",
        request_id="req_f6b_cell",
        environment="staging",
        capability="github.delete-exact-created-ref/v1",
        target_digest=D1,
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
        recorded_at="2026-08-18T11:59:00.000+00:00",
        receipt_revision="execution-receipt/f6b-cell-test-r1",
    )


def _runner() -> GitHubRefAbsenceObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "github-ref-absence-observation/v1",
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/vone-canary/f6b-cell-test",
        "target_digest": D1,
        "provider": "github",
        "provider_instance_id": "gha:f6b-cell-runner:test",
        "runner_id": D2,
        "runner_identity_digest": D3,
        "runner_boundary_digest": D4,
        "execution_id": "exec_f6b_cell",
        "execution_epoch": 1,
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


def _boundary(runner: GitHubRefAbsenceObservation) -> IndependentVerificationBoundaryV2:
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
        "environment": "staging",
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


def _bundle() -> tuple[
    ExecutionReceiptV2,
    GitHubRefAbsenceObservation,
    VerifierGitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    ObservedPostState,
    VerificationStrength,
    VerificationResult,
    OperationProofV2,
]:
    receipt = _receipt()
    runner = _runner()
    boundary = _boundary(runner)
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


def _cell() -> tuple[
    OperationCellV1,
    ExecutionReceiptV2,
    GitHubRefAbsenceObservation,
    VerifierGitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    ObservedPostState,
    VerificationStrength,
    VerificationResult,
    OperationProofV2,
]:
    receipt, runner, verifier, boundary, state, strength, result, proof = _bundle()
    cell = OperationCellV1.create_from_absence(
        proof=proof,
        receipt=receipt,
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state=state,
        verification_strength=strength,
        verification=result,
        cell_revision="operation-cell/f6b-test-r1",
    )
    return cell, receipt, runner, verifier, boundary, state, strength, result, proof


def test_operation_cell_v1_is_deterministic_and_provenance_round_trippable() -> None:
    cell, receipt, runner, verifier, boundary, state, strength, result, proof = _cell()

    parsed = OperationCellV1.from_dict(
        cell.to_dict(),
        proof=proof,
        receipt=receipt,
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state=state,
        verification_strength=strength,
        verification=result,
    )

    assert parsed == cell
    assert cell.to_dict()["cell_type"] == OPERATION_CELL_V1_TYPE
    assert cell.verification_lineage == ROLLBACK_ABSENCE_LINEAGE_V1
    assert cell.final_verdict == VERIFIED
    assert _cell()[0].cell_digest == cell.cell_digest


def test_operation_cell_v1_binds_lifecycle_trust_roots_to_proof() -> None:
    cell, _, _, _, _, _, _, _, proof = _cell()

    assert cell.authorization_snapshot_digest == proof.authorization_snapshot_digest
    assert cell.execution_grant_digest == proof.execution_grant_digest
    assert cell.execution_receipt_digest == proof.execution_receipt_digest
    assert cell.verification_result_digest == proof.verification_result_digest
    assert cell.operation_proof_digest == proof.proof_digest
    assert cell.execution_id == proof.execution_id
    assert cell.target_digest == proof.target_digest


def test_operation_cell_v1_rejects_standalone_forged_verified_proof() -> None:
    receipt, runner, verifier, boundary, state, strength, result, proof = _bundle()
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
        OperationCellV1.create_from_absence(
            proof=forged,
            receipt=receipt,
            runner_observation=runner,
            verifier_observation=verifier,
            boundary=boundary,
            observed_post_state=state,
            verification_strength=strength,
            verification=result,
            cell_revision="operation-cell/f6b-forged-proof-test-r1",
        )


def test_operation_cell_v1_rejects_rehashed_serialized_metadata_substitution() -> None:
    cell, receipt, runner, verifier, boundary, state, strength, result, proof = _cell()
    value = deepcopy(cell.to_dict())
    value["environment"] = "production"
    claims = {key: item for key, item in value.items() if key != "cell_digest"}
    value["cell_digest"] = _digest(claims)

    with pytest.raises(
        OperationCellV1Denied,
        match="OPERATION_CELL_V1_EVIDENCE_BINDING_MISMATCH",
    ):
        OperationCellV1.from_dict(
            value,
            proof=proof,
            receipt=receipt,
            runner_observation=runner,
            verifier_observation=verifier,
            boundary=boundary,
            observed_post_state=state,
            verification_strength=strength,
            verification=result,
        )


def test_operation_cell_v1_rejects_unknown_serialized_fields() -> None:
    cell, receipt, runner, verifier, boundary, state, strength, result, proof = _cell()
    value = deepcopy(cell.to_dict())
    value["unexpected"] = "field"

    with pytest.raises(ValueError, match="operation-cell/v1 fields are invalid"):
        OperationCellV1.from_dict(
            value,
            proof=proof,
            receipt=receipt,
            runner_observation=runner,
            verifier_observation=verifier,
            boundary=boundary,
            observed_post_state=state,
            verification_strength=strength,
            verification=result,
        )


def test_operation_cell_v1_contains_no_raw_authority_or_secret_material() -> None:
    cell = _cell()[0]
    value = cell.to_dict()
    forbidden_exact_fields = {
        "token",
        "secret",
        "authorization_snapshot",
        "execution_grant",
        "execution_receipt",
        "provider_request",
        "provider_response",
        "credential",
        "operation_proof",
        "verification_result",
    }

    assert forbidden_exact_fields.isdisjoint(value)
    assert value["provider_mutation_count"] == 1
    assert value["rollback_performed"] is True
