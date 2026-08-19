from __future__ import annotations

from copy import deepcopy

import pytest

from voodoo_product.execution_receipt_v2 import (
    EFFECT_RECORDED,
    EXECUTION_SUCCEEDED,
    NOT_EVALUATED,
    ExecutionReceiptV2,
)
from voodoo_product.operation_proof_v2 import (
    OPERATION_PROOF_V2_TYPE,
    OperationProofV2,
    OperationProofV2Denied,
)
from voodoo_product.verification_result import (
    INDEPENDENT_PROVIDER_READBACK,
    NOT_VERIFIED,
    OBSERVED_STATE_MATCH,
    OBSERVED_STATE_MISMATCH,
    VERIFIED,
    VerificationResult,
)

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


def _receipt(**changes) -> ExecutionReceiptV2:
    claims = {
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
        "recorded_at": "2026-08-19T03:53:16.635+00:00",
    }
    claims.update(changes)
    return ExecutionReceiptV2.create(
        receipt_revision="execution-receipt/f6b-test-r1",
        **claims,
    )


def _verification(
    receipt: ExecutionReceiptV2,
    *,
    verdict: str = VERIFIED,
    reason: str = OBSERVED_STATE_MATCH,
    **changes,
) -> VerificationResult:
    claims = {
        "execution_id": receipt.execution_id,
        "execution_epoch": 1,
        "target_digest": receipt.target_digest,
        "runner_observation_digest": D6,
        "verifier_observation_digest": D7,
        "observed_post_state_digest": D8,
        "verification_boundary_digest": DA,
        "verifier_id": DB,
        "verifier_identity_digest": DC,
        "verification_strength_digest": DD,
        "verification_strength_class": INDEPENDENT_PROVIDER_READBACK,
        "verdict": verdict,
        "reason": reason,
        "checked_at": "2026-08-19T03:53:39.757+00:00",
        "result_revision": "verification-result/f6b-test-r1",
    }
    claims.update(changes)
    return VerificationResult.create(**claims)


def _proof(
    receipt: ExecutionReceiptV2 | None = None,
    verification: VerificationResult | None = None,
) -> OperationProofV2:
    resolved_receipt = receipt or _receipt()
    resolved_verification = verification or _verification(resolved_receipt)
    return OperationProofV2.create(
        receipt=resolved_receipt,
        verification=resolved_verification,
        proof_revision="operation-proof/f6b-test-r1",
    )


def test_operation_proof_v2_is_deterministic_and_round_trippable() -> None:
    proof = _proof()

    assert proof.to_dict()["proof_type"] == OPERATION_PROOF_V2_TYPE
    assert proof.final_verdict == VERIFIED
    assert OperationProofV2.from_dict(proof.to_dict()) == proof
    assert _proof().proof_digest == proof.proof_digest


def test_operation_proof_v2_rejects_execution_substitution() -> None:
    receipt = _receipt()
    verification = _verification(receipt, execution_id="exec_other")

    with pytest.raises(OperationProofV2Denied, match="OPERATION_PROOF_V2_EXECUTION_MISMATCH"):
        _proof(receipt, verification)


def test_operation_proof_v2_rejects_target_substitution() -> None:
    receipt = _receipt()
    verification = _verification(receipt, target_digest=DE)

    with pytest.raises(OperationProofV2Denied, match="OPERATION_PROOF_V2_TARGET_MISMATCH"):
        _proof(receipt, verification)


def test_operation_proof_v2_rejects_non_verified_result() -> None:
    receipt = _receipt()
    verification = _verification(
        receipt,
        verdict=NOT_VERIFIED,
        reason=OBSERVED_STATE_MISMATCH,
    )

    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_INDEPENDENT_VERIFICATION_REQUIRED",
    ):
        _proof(receipt, verification)


def test_operation_proof_v2_rejects_verification_before_receipt() -> None:
    receipt = _receipt()
    verification = _verification(
        receipt,
        checked_at="2026-08-19T03:53:16.000+00:00",
    )

    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_VERIFICATION_PRECEDES_RECEIPT",
    ):
        _proof(receipt, verification)


def test_operation_proof_v2_rejects_tampered_serialized_proof() -> None:
    value = deepcopy(_proof().to_dict())
    value["execution_receipt_digest"] = DE

    with pytest.raises(ValueError, match="proof_digest does not match"):
        OperationProofV2.from_dict(value)


def test_operation_proof_v2_contains_no_raw_authority_or_secret_material() -> None:
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
