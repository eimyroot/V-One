from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .evidence_primitives import canonical_json
from .execution_receipt_v2 import NOT_EVALUATED, ExecutionReceiptV2
from .operation_proof_v2 import (
    OPERATION_PROOF_V2_TYPE,
    OperationProofV2,
    OperationProofV2Denied,
)
from .rollback_verification import (
    GitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    VerifierGitHubRefAbsenceObservation,
    verify_github_ref_absence,
)
from .verification_result import (
    INDEPENDENT_PROVIDER_READBACK,
    OBSERVED_STATE_MATCH,
    VERIFIED,
    ObservedPostState,
    VerificationResult,
    VerificationStrength,
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _require_timestamp(value: object, *, field: str) -> datetime:
    text = _require_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return parsed.astimezone(UTC)


def _same(actual: object, expected: object, *, reason: str) -> None:
    if actual != expected:
        raise OperationProofV2Denied(reason)


def create_operation_proof_v2_from_absence(
    *,
    receipt: ExecutionReceiptV2,
    runner_observation: GitHubRefAbsenceObservation,
    verifier_observation: VerifierGitHubRefAbsenceObservation,
    boundary: IndependentVerificationBoundaryV2,
    observed_post_state: ObservedPostState,
    verification_strength: VerificationStrength,
    verification: VerificationResult,
    proof_revision: str,
) -> OperationProofV2:
    """Compose OperationProof/v2 from the canonical rollback absence lineage.

    The composer is evidence-only: it performs no I/O and creates no authority.
    The retained absence state, strength, and result must exactly match a fresh
    deterministic recomputation through ``verify_github_ref_absence``.
    """

    if not isinstance(receipt, ExecutionReceiptV2):
        raise TypeError("receipt must be ExecutionReceiptV2")
    if not isinstance(runner_observation, GitHubRefAbsenceObservation):
        raise OperationProofV2Denied(
            "OPERATION_PROOF_V2_ABSENCE_RUNNER_OBSERVATION_REQUIRED"
        )
    if not isinstance(verifier_observation, VerifierGitHubRefAbsenceObservation):
        raise OperationProofV2Denied(
            "OPERATION_PROOF_V2_ABSENCE_VERIFIER_OBSERVATION_REQUIRED"
        )
    if not isinstance(boundary, IndependentVerificationBoundaryV2):
        raise OperationProofV2Denied(
            "OPERATION_PROOF_V2_ABSENCE_VERIFICATION_BOUNDARY_REQUIRED"
        )
    if not isinstance(observed_post_state, ObservedPostState):
        raise TypeError("observed_post_state must be ObservedPostState")
    if not isinstance(verification_strength, VerificationStrength):
        raise TypeError("verification_strength must be VerificationStrength")
    if not isinstance(verification, VerificationResult):
        raise TypeError("verification must be VerificationResult")
    _require_text(proof_revision, field="proof_revision")

    recomputed_state, recomputed_strength, recomputed_result = verify_github_ref_absence(
        runner_observation=runner_observation,
        verifier_observation=verifier_observation,
        boundary=boundary,
        observed_post_state_revision=observed_post_state.state_revision,
        strength_revision=verification_strength.strength_revision,
        result_revision=verification.result_revision,
    )
    _same(
        observed_post_state,
        recomputed_state,
        reason="OPERATION_PROOF_V2_OBSERVED_POST_STATE_MISMATCH",
    )
    _same(
        verification_strength,
        recomputed_strength,
        reason="OPERATION_PROOF_V2_VERIFICATION_STRENGTH_MISMATCH",
    )
    _same(
        verification,
        recomputed_result,
        reason="OPERATION_PROOF_V2_VERIFICATION_RESULT_MISMATCH",
    )

    _same(
        receipt.execution_id,
        verification.execution_id,
        reason="OPERATION_PROOF_V2_EXECUTION_MISMATCH",
    )
    _same(
        receipt.target_digest,
        verification.target_digest,
        reason="OPERATION_PROOF_V2_TARGET_MISMATCH",
    )
    _same(
        receipt.verification_status,
        NOT_EVALUATED,
        reason="OPERATION_PROOF_V2_RECEIPT_VERIFICATION_SEPARATION_REQUIRED",
    )
    _same(
        verification.verdict,
        VERIFIED,
        reason="OPERATION_PROOF_V2_INDEPENDENT_VERIFICATION_REQUIRED",
    )
    _same(
        verification.reason,
        OBSERVED_STATE_MATCH,
        reason="OPERATION_PROOF_V2_VERIFICATION_REASON_INVALID",
    )
    _same(
        verification.verification_strength_class,
        INDEPENDENT_PROVIDER_READBACK,
        reason="OPERATION_PROOF_V2_VERIFICATION_STRENGTH_INVALID",
    )

    recorded_at = _require_timestamp(receipt.recorded_at, field="receipt.recorded_at")
    checked_at = _require_timestamp(
        verification.checked_at,
        field="verification.checked_at",
    )
    if checked_at < recorded_at:
        raise OperationProofV2Denied("OPERATION_PROOF_V2_VERIFICATION_PRECEDES_RECEIPT")

    claims = {
        "schema_version": 2,
        "proof_type": OPERATION_PROOF_V2_TYPE,
        "execution_id": receipt.execution_id,
        "execution_epoch": verification.execution_epoch,
        "request_id": receipt.request_id,
        "environment": receipt.environment,
        "capability": receipt.capability,
        "target_digest": receipt.target_digest,
        "authorization_snapshot_digest": receipt.authorization_snapshot_digest,
        "execution_grant_digest": receipt.execution_grant_digest,
        "execution_receipt_digest": receipt.receipt_digest,
        "provider_operation": receipt.provider_operation,
        "provider_response_digest": receipt.provider_response_digest,
        "provider_mutation_count": receipt.provider_mutation_count,
        "automatic_retry_performed": receipt.automatic_retry_performed,
        "rollback_performed": receipt.rollback_performed,
        "runner_observation_digest": verification.runner_observation_digest,
        "verifier_observation_digest": verification.verifier_observation_digest,
        "observed_post_state_digest": observed_post_state.state_digest,
        "verification_boundary_digest": boundary.boundary_digest,
        "verifier_id": verification.verifier_id,
        "verifier_identity_digest": verification.verifier_identity_digest,
        "verification_strength_digest": verification_strength.strength_digest,
        "verification_strength_class": verification.verification_strength_class,
        "verification_result_digest": verification.result_digest,
        "receipt_recorded_at": receipt.recorded_at,
        "verification_checked_at": verification.checked_at,
        "final_verdict": VERIFIED,
        "proof_revision": proof_revision,
    }
    return OperationProofV2.from_dict(
        {
            **claims,
            "proof_digest": _digest(claims),
        }
    )
