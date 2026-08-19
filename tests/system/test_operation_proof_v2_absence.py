from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_receipt_v2 import (
    EFFECT_RECORDED,
    EXECUTION_SUCCEEDED,
    NOT_EVALUATED,
    ExecutionReceiptV2,
)
from voodoo_product.github_read_provider import GitHubRefObservation
from voodoo_product.operation_proof_v2 import OPERATION_PROOF_V2_TYPE, OperationProofV2Denied
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
    OBSERVED_STATE_MATCH,
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


def _receipt(**changes: Any) -> ExecutionReceiptV2:
    claims: dict[str, Any] = {
        "execution_id": "exec_f6b",
        "request_id": "req_f6b",
        "environment": "staging",
        "capability": "github.delete-exact-created-ref/v1",
        "target_digest": D1,
        "authorization_snapshot_digest": D2,
        "execution_grant_digest": D3,
        "execution_capsule_digest": D4,
        "grant_consumption_witness_digest": D5,
        "dispatch_envelope_digest": D6,
        "dispatch_admission_digest": D7,
        "execution_lease_digest": D8,
        "runner_identity_digest": DA,
        "runner_boundary_digest": DB,
        "credential_access_decision_digest": DC,
        "runtime_activation_digest": DD,
        "write_effect_preflight_digest": DE,
        "provider_operation": "DELETE_REF",
        "provider_request_digest": DF,
        "provider_response_digest": D4,
        "provider_mutation_performed": True,
        "provider_mutation_count": 1,
        "automatic_retry_performed": False,
        "rollback_performed": True,
        "durable_completion_outcome": "COMPLETED",
        "durable_completion_digest": D4,
        "execution_status": EXECUTION_SUCCEEDED,
        "effect_status": EFFECT_RECORDED,
        "verification_status": NOT_EVALUATED,
        "recording_clock_witness_digest": D5,
        "recorded_at": "2026-08-18T11:59:00.000+00:00",
    }
    claims.update(changes)
    return ExecutionReceiptV2.create(
        receipt_revision="execution-receipt/f6b-absence-test-r1",
        **claims,
    )


def _absence_runner() -> GitHubRefAbsenceObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "github-ref-absence-observation/v1",
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/vone-canary/f6b-test",
        "target_digest": D1,
        "provider": "github",
        "provider_instance_id": "gha:f6b-runner:test",
        "runner_id": D2,
        "runner_identity_digest": D3,
        "runner_boundary_digest": D4,
        "execution_id": "exec_f6b",
        "execution_epoch": 1,
        "source_identity": "github-api-runner-readback/f6b-test-r1",
        "http_status": 404,
        "presence": "ABSENT",
        "observed_at": "2026-08-18T12:00:00.000+00:00",
        "observation_revision": "github-ref-absence-observation/f6b-test-r1",
    }
    return GitHubRefAbsenceObservation(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(claims),
    )


def _absence_boundary(
    runner: GitHubRefAbsenceObservation,
) -> IndependentVerificationBoundaryV2:
    claims: dict[str, Any] = {
        "schema_version": 2,
        "boundary_type": "independent-verification-boundary/v2",
        "verifier_id": D5,
        "verifier_identity_digest": D6,
        "verifier_provider_instance_id": "gha:f6b-verifier:test",
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
        "boundary_revision": "independent-verification-boundary/f6b-test-r1",
    }
    return IndependentVerificationBoundaryV2(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "boundary_type"}
        },
        boundary_digest=_digest(claims),
    )


def _absence_verifier(
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
        "source_identity": "github-api-independent-verifier/f6b-test-r1",
        "http_status": 404,
        "presence": "ABSENT",
        "observed_at": "2026-08-18T12:01:00.000+00:00",
        "observation_revision": "verifier-github-ref-absence-observation/f6b-test-r1",
    }
    return VerifierGitHubRefAbsenceObservation(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(claims),
    )


def _absence_bundle() -> tuple[
    GitHubRefAbsenceObservation,
    VerifierGitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    ObservedPostState,
    VerificationStrength,
    VerificationResult,
]:
    runner = _absence_runner()
    boundary = _absence_boundary(runner)
    verifier = _absence_verifier(runner, boundary)
    state, strength, result = verify_github_ref_absence(
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state_revision="observed-post-state/f6b-test-r1",
        strength_revision="verification-strength/f6b-test-r1",
        result_revision="verification-result/f6b-test-r1",
    )
    return runner, verifier, boundary, state, strength, result


def _presence_runner() -> GitHubRefObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "github-ref-observation/v1",
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/main",
        "commit_sha": "a" * 40,
        "target_digest": D1,
        "provider": "github-actions",
        "provider_instance_id": "gha:runner:presence",
        "runner_id": D2,
        "runner_boundary_digest": D3,
        "credential_decision_digest": D4,
        "runtime_activation_digest": D5,
        "lease_id": D6,
        "lease_digest": D7,
        "execution_id": "exec_f6b",
        "execution_epoch": 1,
        "execution_capsule_digest": D8,
        "capability_definition_identity": DA,
        "source_identity": "github-api/git-ref/v1",
        "clock_source_identity": "trusted-clock/presence",
        "clock_witness_digest": DB,
        "observed_at": "2026-08-18T12:00:00.000+00:00",
        "observation_revision": "github-ref-observation/presence-test-r1",
    }
    return GitHubRefObservation(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(claims),
    )


def _proof(
    *,
    receipt: ExecutionReceiptV2 | None = None,
    verification: VerificationResult | None = None,
):
    resolved_receipt = receipt or _receipt()
    runner, verifier, boundary, state, strength, result = _absence_bundle()
    return create_operation_proof_v2_from_absence(
        receipt=resolved_receipt,
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state=state,
        verification_strength=strength,
        verification=verification or result,
        proof_revision="operation-proof/f6b-absence-test-r1",
    )


def test_operation_proof_v2_absence_is_deterministic_and_round_trippable() -> None:
    proof = _proof()

    assert proof.to_dict()["proof_type"] == OPERATION_PROOF_V2_TYPE
    assert proof.final_verdict == VERIFIED
    assert proof.rollback_performed is True
    assert proof.provider_operation == "DELETE_REF"
    assert type(proof).from_dict(proof.to_dict()) == proof
    assert _proof().proof_digest == proof.proof_digest


def test_operation_proof_v2_absence_binds_canonical_absence_roots() -> None:
    runner, verifier, boundary, state, strength, result = _absence_bundle()
    proof = create_operation_proof_v2_from_absence(
        receipt=_receipt(),
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state=state,
        verification_strength=strength,
        verification=result,
        proof_revision="operation-proof/f6b-absence-test-r1",
    )

    assert proof.runner_observation_digest == runner.observation_digest
    assert proof.verifier_observation_digest == verifier.observation_digest
    assert proof.verification_boundary_digest == boundary.boundary_digest
    assert proof.observed_post_state_digest == state.state_digest
    assert proof.verification_strength_digest == strength.strength_digest
    assert proof.verification_result_digest == result.result_digest


def test_operation_proof_v2_absence_rejects_forged_verified_result() -> None:
    receipt = _receipt()
    forged = VerificationResult.create(
        execution_id=receipt.execution_id,
        execution_epoch=1,
        target_digest=receipt.target_digest,
        runner_observation_digest=DF,
        verifier_observation_digest=DF,
        observed_post_state_digest=DF,
        verification_boundary_digest=DF,
        verifier_id=DF,
        verifier_identity_digest=DF,
        verification_strength_digest=DF,
        verification_strength_class=INDEPENDENT_PROVIDER_READBACK,
        verdict=VERIFIED,
        reason=OBSERVED_STATE_MATCH,
        checked_at="2026-08-18T12:01:00.000+00:00",
        result_revision="verification-result/forged-absence-r1",
    )

    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_VERIFICATION_RESULT_MISMATCH",
    ):
        _proof(receipt=receipt, verification=forged)


def test_operation_proof_v2_absence_rejects_presence_runner_cross_lineage_substitution() -> None:
    _, verifier, boundary, state, strength, result = _absence_bundle()

    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_ABSENCE_RUNNER_OBSERVATION_REQUIRED",
    ):
        create_operation_proof_v2_from_absence(
            receipt=_receipt(),
            runner_observation=_presence_runner(),  # type: ignore[arg-type]
            verifier_observation=verifier,
            boundary=boundary,
            observed_post_state=state,
            verification_strength=strength,
            verification=result,
            proof_revision="operation-proof/f6b-cross-lineage-test-r1",
        )


def test_operation_proof_v2_absence_rejects_execution_substitution() -> None:
    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_EXECUTION_MISMATCH",
    ):
        _proof(receipt=_receipt(execution_id="exec_other"))


def test_operation_proof_v2_absence_rejects_target_substitution() -> None:
    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_TARGET_MISMATCH",
    ):
        _proof(receipt=_receipt(target_digest=DE))


def test_operation_proof_v2_absence_rejects_verification_before_receipt() -> None:
    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_VERIFICATION_PRECEDES_RECEIPT",
    ):
        _proof(receipt=_receipt(recorded_at="2026-08-18T12:02:00.000+00:00"))


def test_operation_proof_v2_absence_contains_no_raw_authority_or_secret_material() -> None:
    value = _proof().to_dict()
    forbidden_exact_fields = {
        "token",
        "secret",
        "authorization_snapshot",
        "execution_grant",
        "execution_receipt",
        "provider_request",
        "provider_response",
        "credential",
    }

    assert forbidden_exact_fields.isdisjoint(value)
    assert value["provider_mutation_count"] == 1
    assert value["automatic_retry_performed"] is False
