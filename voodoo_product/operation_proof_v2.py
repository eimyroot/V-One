from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .evidence_primitives import canonical_json
from .execution_receipt_v2 import NOT_EVALUATED, ExecutionReceiptV2
from .github_read_provider import GitHubRefObservation
from .verification_result import (
    INDEPENDENT_PROVIDER_READBACK,
    OBSERVED_STATE_MATCH,
    VERIFIED,
    ObservedPostState,
    VerificationResult,
    VerificationStrength,
    verify_github_ref_readback,
)
from .verifier_identity import IndependentVerificationBoundary
from .verifier_observation import VerifierGitHubRefObservation

OPERATION_PROOF_V2_TYPE: Final = "operation-proof/v2"

_PROOF_FIELDS = frozenset(
    {
        "schema_version",
        "proof_type",
        "execution_id",
        "execution_epoch",
        "request_id",
        "environment",
        "capability",
        "target_digest",
        "authorization_snapshot_digest",
        "execution_grant_digest",
        "execution_receipt_digest",
        "provider_operation",
        "provider_response_digest",
        "provider_mutation_count",
        "automatic_retry_performed",
        "rollback_performed",
        "runner_observation_digest",
        "verifier_observation_digest",
        "observed_post_state_digest",
        "verification_boundary_digest",
        "verifier_id",
        "verifier_identity_digest",
        "verification_strength_digest",
        "verification_strength_class",
        "verification_result_digest",
        "receipt_recorded_at",
        "verification_checked_at",
        "final_verdict",
        "proof_revision",
        "proof_digest",
    }
)


class OperationProofV2Denied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


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


def _validate_verification_lineage(
    *,
    runner_observation: GitHubRefObservation,
    verifier_observation: VerifierGitHubRefObservation,
    boundary: IndependentVerificationBoundary,
    observed_post_state: ObservedPostState,
    verification_strength: VerificationStrength,
    verification: VerificationResult,
) -> None:
    if not isinstance(observed_post_state, ObservedPostState):
        raise TypeError("observed_post_state must be ObservedPostState")
    if not isinstance(verification_strength, VerificationStrength):
        raise TypeError("verification_strength must be VerificationStrength")
    if not isinstance(verification, VerificationResult):
        raise TypeError("verification must be VerificationResult")

    recomputed_state, recomputed_strength, recomputed_result = verify_github_ref_readback(
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


@dataclass(frozen=True, slots=True)
class OperationProofV2:
    """Deterministic proof binding one ExecutionReceipt/v2 to independent verification.

    This contract is evidence-only. It performs no I/O, carries no credential material,
    and derives VERIFIED only by recomputing the retained read-only verification chain.
    """

    execution_id: str
    execution_epoch: int
    request_id: str
    environment: str
    capability: str
    target_digest: str
    authorization_snapshot_digest: str
    execution_grant_digest: str
    execution_receipt_digest: str
    provider_operation: str
    provider_response_digest: str
    provider_mutation_count: int
    automatic_retry_performed: bool
    rollback_performed: bool
    runner_observation_digest: str
    verifier_observation_digest: str
    observed_post_state_digest: str
    verification_boundary_digest: str
    verifier_id: str
    verifier_identity_digest: str
    verification_strength_digest: str
    verification_strength_class: str
    verification_result_digest: str
    receipt_recorded_at: str
    verification_checked_at: str
    final_verdict: str
    proof_revision: str
    proof_digest: str

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "request_id",
            "environment",
            "capability",
            "provider_operation",
            "verification_strength_class",
            "final_verdict",
            "proof_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "authorization_snapshot_digest",
            "execution_grant_digest",
            "execution_receipt_digest",
            "provider_response_digest",
            "runner_observation_digest",
            "verifier_observation_digest",
            "observed_post_state_digest",
            "verification_boundary_digest",
            "verifier_id",
            "verifier_identity_digest",
            "verification_strength_digest",
            "verification_result_digest",
            "proof_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if type(self.provider_mutation_count) is not int or self.provider_mutation_count != 1:
            raise ValueError("OperationProof/v2 requires exactly one bounded provider mutation")
        if type(self.automatic_retry_performed) is not bool:
            raise ValueError("automatic_retry_performed must be bool")
        if self.automatic_retry_performed is not False:
            raise ValueError("OperationProof/v2 forbids automatic mutation retry")
        if type(self.rollback_performed) is not bool:
            raise ValueError("rollback_performed must be bool")
        recorded_at = _require_timestamp(self.receipt_recorded_at, field="receipt_recorded_at")
        checked_at = _require_timestamp(
            self.verification_checked_at,
            field="verification_checked_at",
        )
        if checked_at < recorded_at:
            raise ValueError("verification must not precede the recorded execution receipt")
        if self.verification_strength_class != INDEPENDENT_PROVIDER_READBACK:
            raise ValueError("OperationProof/v2 requires independent provider readback")
        if self.final_verdict != VERIFIED:
            raise ValueError("OperationProof/v2 may only represent VERIFIED operations")
        if self.proof_digest != _digest(self._claims_without_digest()):
            raise ValueError("proof_digest does not match OperationProof/v2")

    @classmethod
    def create(
        cls,
        *,
        receipt: ExecutionReceiptV2,
        runner_observation: GitHubRefObservation,
        verifier_observation: VerifierGitHubRefObservation,
        boundary: IndependentVerificationBoundary,
        observed_post_state: ObservedPostState,
        verification_strength: VerificationStrength,
        verification: VerificationResult,
        proof_revision: str,
    ) -> Self:
        if not isinstance(receipt, ExecutionReceiptV2):
            raise TypeError("receipt must be ExecutionReceiptV2")
        _require_text(proof_revision, field="proof_revision")

        _validate_verification_lineage(
            runner_observation=runner_observation,
            verifier_observation=verifier_observation,
            boundary=boundary,
            observed_post_state=observed_post_state,
            verification_strength=verification_strength,
            verification=verification,
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
        checked_at = _require_timestamp(verification.checked_at, field="verification.checked_at")
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
        return cls(
            **{
                key: value
                for key, value in claims.items()
                if key not in {"schema_version", "proof_type"}
            },
            proof_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        if not isinstance(value, Mapping):
            raise ValueError("operation-proof/v2 must be an object")
        actual = frozenset(value)
        if actual != _PROOF_FIELDS:
            raise ValueError(
                "operation-proof/v2 fields are invalid; "
                f"missing={sorted(_PROOF_FIELDS - actual)}, "
                f"unknown={sorted(actual - _PROOF_FIELDS)}"
            )
        if value["schema_version"] != 2 or value["proof_type"] != OPERATION_PROOF_V2_TYPE:
            raise ValueError("operation-proof/v2 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _PROOF_FIELDS
                if key not in {"schema_version", "proof_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "proof_type": OPERATION_PROOF_V2_TYPE,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "request_id": self.request_id,
            "environment": self.environment,
            "capability": self.capability,
            "target_digest": self.target_digest,
            "authorization_snapshot_digest": self.authorization_snapshot_digest,
            "execution_grant_digest": self.execution_grant_digest,
            "execution_receipt_digest": self.execution_receipt_digest,
            "provider_operation": self.provider_operation,
            "provider_response_digest": self.provider_response_digest,
            "provider_mutation_count": self.provider_mutation_count,
            "automatic_retry_performed": self.automatic_retry_performed,
            "rollback_performed": self.rollback_performed,
            "runner_observation_digest": self.runner_observation_digest,
            "verifier_observation_digest": self.verifier_observation_digest,
            "observed_post_state_digest": self.observed_post_state_digest,
            "verification_boundary_digest": self.verification_boundary_digest,
            "verifier_id": self.verifier_id,
            "verifier_identity_digest": self.verifier_identity_digest,
            "verification_strength_digest": self.verification_strength_digest,
            "verification_strength_class": self.verification_strength_class,
            "verification_result_digest": self.verification_result_digest,
            "receipt_recorded_at": self.receipt_recorded_at,
            "verification_checked_at": self.verification_checked_at,
            "final_verdict": self.final_verdict,
            "proof_revision": self.proof_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "proof_digest": self.proof_digest}
