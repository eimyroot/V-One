from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Self

from .evidence_primitives import canonical_json
from .execution_receipt_v2 import ExecutionReceiptV2
from .operation_proof_v2 import OPERATION_PROOF_V2_TYPE, OperationProofV2
from .operation_proof_v2_absence import create_operation_proof_v2_from_absence
from .rollback_verification import (
    GitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    VerifierGitHubRefAbsenceObservation,
)
from .verification_result import (
    INDEPENDENT_PROVIDER_READBACK,
    VERIFIED,
    ObservedPostState,
    VerificationResult,
    VerificationStrength,
)

OPERATION_CELL_V1_TYPE: Final = "operation-cell/v1"
ROLLBACK_ABSENCE_LINEAGE_V1: Final = "rollback-absence/v1"

_CELL_FIELDS = frozenset(
    {
        "schema_version",
        "cell_type",
        "verification_lineage",
        "operation_proof_type",
        "operation_proof_digest",
        "execution_id",
        "execution_epoch",
        "request_id",
        "environment",
        "capability",
        "target_digest",
        "authorization_snapshot_digest",
        "execution_grant_digest",
        "execution_receipt_digest",
        "verification_result_digest",
        "provider_operation",
        "provider_mutation_count",
        "rollback_performed",
        "verification_strength_class",
        "final_verdict",
        "proof_revision",
        "cell_revision",
        "cell_digest",
    }
)


class OperationCellV1Denied(PermissionError):
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


def _same(actual: object, expected: object, *, reason: str) -> None:
    if actual != expected:
        raise OperationCellV1Denied(reason)


@dataclass(frozen=True, slots=True)
class OperationCellV1:
    """Compact trust envelope rooted in one canonically recomputed OperationProof/v2.

    OperationCell/v1 is evidence-only. It performs no I/O, grants no authority, and does
    not accept a standalone proof as provenance. The current composer supports the
    rollback-absence lineage used by historical F6b and requires recomputation of that
    proof from its retained canonical evidence roots before the cell may be created.
    """

    verification_lineage: str
    operation_proof_type: str
    operation_proof_digest: str
    execution_id: str
    execution_epoch: int
    request_id: str
    environment: str
    capability: str
    target_digest: str
    authorization_snapshot_digest: str
    execution_grant_digest: str
    execution_receipt_digest: str
    verification_result_digest: str
    provider_operation: str
    provider_mutation_count: int
    rollback_performed: bool
    verification_strength_class: str
    final_verdict: str
    proof_revision: str
    cell_revision: str
    cell_digest: str

    def __post_init__(self) -> None:
        for field in (
            "verification_lineage",
            "operation_proof_type",
            "execution_id",
            "request_id",
            "environment",
            "capability",
            "provider_operation",
            "verification_strength_class",
            "final_verdict",
            "proof_revision",
            "cell_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "operation_proof_digest",
            "target_digest",
            "authorization_snapshot_digest",
            "execution_grant_digest",
            "execution_receipt_digest",
            "verification_result_digest",
            "cell_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.verification_lineage != ROLLBACK_ABSENCE_LINEAGE_V1:
            raise ValueError("OperationCell/v1 current composer requires rollback-absence/v1")
        if self.operation_proof_type != OPERATION_PROOF_V2_TYPE:
            raise ValueError("OperationCell/v1 requires operation-proof/v2")
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if type(self.provider_mutation_count) is not int or self.provider_mutation_count != 1:
            raise ValueError("OperationCell/v1 requires exactly one bounded provider mutation")
        if type(self.rollback_performed) is not bool or self.rollback_performed is not True:
            raise ValueError("OperationCell/v1 rollback-absence lineage requires rollback")
        if self.verification_strength_class != INDEPENDENT_PROVIDER_READBACK:
            raise ValueError("OperationCell/v1 requires independent provider readback")
        if self.final_verdict != VERIFIED:
            raise ValueError("OperationCell/v1 may only represent VERIFIED operations")
        if self.cell_digest != _digest(self._claims_without_digest()):
            raise ValueError("cell_digest does not match OperationCell/v1")

    @classmethod
    def create_from_absence(
        cls,
        *,
        proof: OperationProofV2,
        receipt: ExecutionReceiptV2,
        runner_observation: GitHubRefAbsenceObservation,
        verifier_observation: VerifierGitHubRefAbsenceObservation,
        boundary: IndependentVerificationBoundaryV2,
        observed_post_state: ObservedPostState,
        verification_strength: VerificationStrength,
        verification: VerificationResult,
        cell_revision: str,
    ) -> Self:
        if not isinstance(proof, OperationProofV2):
            raise TypeError("proof must be OperationProofV2")
        _require_text(cell_revision, field="cell_revision")

        recomputed_proof = create_operation_proof_v2_from_absence(
            receipt=receipt,
            runner_observation=runner_observation,
            verifier_observation=verifier_observation,
            boundary=boundary,
            observed_post_state=observed_post_state,
            verification_strength=verification_strength,
            verification=verification,
            proof_revision=proof.proof_revision,
        )
        _same(
            proof,
            recomputed_proof,
            reason="OPERATION_CELL_V1_OPERATION_PROOF_MISMATCH",
        )

        claims = {
            "schema_version": 1,
            "cell_type": OPERATION_CELL_V1_TYPE,
            "verification_lineage": ROLLBACK_ABSENCE_LINEAGE_V1,
            "operation_proof_type": OPERATION_PROOF_V2_TYPE,
            "operation_proof_digest": proof.proof_digest,
            "execution_id": proof.execution_id,
            "execution_epoch": proof.execution_epoch,
            "request_id": proof.request_id,
            "environment": proof.environment,
            "capability": proof.capability,
            "target_digest": proof.target_digest,
            "authorization_snapshot_digest": proof.authorization_snapshot_digest,
            "execution_grant_digest": proof.execution_grant_digest,
            "execution_receipt_digest": proof.execution_receipt_digest,
            "verification_result_digest": proof.verification_result_digest,
            "provider_operation": proof.provider_operation,
            "provider_mutation_count": proof.provider_mutation_count,
            "rollback_performed": proof.rollback_performed,
            "verification_strength_class": proof.verification_strength_class,
            "final_verdict": proof.final_verdict,
            "proof_revision": proof.proof_revision,
            "cell_revision": cell_revision,
        }
        return cls(
            **{
                key: value
                for key, value in claims.items()
                if key not in {"schema_version", "cell_type"}
            },
            cell_digest=_digest(claims),
        )

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        proof: OperationProofV2,
        receipt: ExecutionReceiptV2,
        runner_observation: GitHubRefAbsenceObservation,
        verifier_observation: VerifierGitHubRefAbsenceObservation,
        boundary: IndependentVerificationBoundaryV2,
        observed_post_state: ObservedPostState,
        verification_strength: VerificationStrength,
        verification: VerificationResult,
    ) -> Self:
        if not isinstance(value, Mapping):
            raise ValueError("operation-cell/v1 must be an object")
        actual = frozenset(value)
        if actual != _CELL_FIELDS:
            raise ValueError(
                "operation-cell/v1 fields are invalid; "
                f"missing={sorted(_CELL_FIELDS - actual)}, "
                f"unknown={sorted(actual - _CELL_FIELDS)}"
            )
        if value["schema_version"] != 1 or value["cell_type"] != OPERATION_CELL_V1_TYPE:
            raise ValueError("operation-cell/v1 schema or type is unsupported")

        parsed = cls(
            **{
                key: value[key]
                for key in _CELL_FIELDS
                if key not in {"schema_version", "cell_type"}
            }
        )
        expected = cls.create_from_absence(
            proof=proof,
            receipt=receipt,
            runner_observation=runner_observation,
            verifier_observation=verifier_observation,
            boundary=boundary,
            observed_post_state=observed_post_state,
            verification_strength=verification_strength,
            verification=verification,
            cell_revision=parsed.cell_revision,
        )
        _same(
            parsed,
            expected,
            reason="OPERATION_CELL_V1_EVIDENCE_BINDING_MISMATCH",
        )
        return parsed

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "cell_type": OPERATION_CELL_V1_TYPE,
            "verification_lineage": self.verification_lineage,
            "operation_proof_type": self.operation_proof_type,
            "operation_proof_digest": self.operation_proof_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "request_id": self.request_id,
            "environment": self.environment,
            "capability": self.capability,
            "target_digest": self.target_digest,
            "authorization_snapshot_digest": self.authorization_snapshot_digest,
            "execution_grant_digest": self.execution_grant_digest,
            "execution_receipt_digest": self.execution_receipt_digest,
            "verification_result_digest": self.verification_result_digest,
            "provider_operation": self.provider_operation,
            "provider_mutation_count": self.provider_mutation_count,
            "rollback_performed": self.rollback_performed,
            "verification_strength_class": self.verification_strength_class,
            "final_verdict": self.final_verdict,
            "proof_revision": self.proof_revision,
            "cell_revision": self.cell_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "cell_digest": self.cell_digest}
