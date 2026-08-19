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

_CELL_FIELDS = frozenset(
    {
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
    """Stable content-addressed atom over one already-proven operation lifecycle.

    The serialized cell stays provider- and verification-lineage-neutral. Trusted cell
    creation happens through a lineage-specific composer that revalidates OperationProof/v2
    from its retained canonical evidence before freezing these immutable indexing claims.
    """

    execution_id: str
    execution_epoch: int
    request_id: str
    environment: str
    capability: str
    target_digest: str
    proof_type: str
    operation_proof_digest: str
    final_verdict: str
    verification_strength_class: str
    cell_revision: str
    cell_digest: str

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "request_id",
            "environment",
            "capability",
            "proof_type",
            "final_verdict",
            "verification_strength_class",
            "cell_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "operation_proof_digest",
            "cell_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.proof_type != OPERATION_PROOF_V2_TYPE:
            raise ValueError("OperationCell/v1 requires operation-proof/v2")
        if self.final_verdict != VERIFIED:
            raise ValueError("OperationCell/v1 may only freeze VERIFIED operations")
        if self.verification_strength_class != INDEPENDENT_PROVIDER_READBACK:
            raise ValueError("OperationCell/v1 R1 requires independent provider readback")
        if self.cell_digest != _digest(self._claims_without_digest()):
            raise ValueError("cell_digest does not match OperationCell/v1")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        """Parse the exact serialized cell shape.

        This validates schema and self-integrity only. Provenance trust is established by a
        lineage-specific composer such as ``create_operation_cell_v1_from_absence``.
        """
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
        return cls(
            **{
                key: value[key]
                for key in _CELL_FIELDS
                if key not in {"schema_version", "cell_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "cell_type": OPERATION_CELL_V1_TYPE,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "request_id": self.request_id,
            "environment": self.environment,
            "capability": self.capability,
            "target_digest": self.target_digest,
            "proof_type": self.proof_type,
            "operation_proof_digest": self.operation_proof_digest,
            "final_verdict": self.final_verdict,
            "verification_strength_class": self.verification_strength_class,
            "cell_revision": self.cell_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "cell_digest": self.cell_digest}


def create_operation_cell_v1_from_absence(
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
) -> OperationCellV1:
    """Freeze one rollback-absence operation after canonical proof recomputation."""
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
        "execution_id": recomputed_proof.execution_id,
        "execution_epoch": recomputed_proof.execution_epoch,
        "request_id": recomputed_proof.request_id,
        "environment": recomputed_proof.environment,
        "capability": recomputed_proof.capability,
        "target_digest": recomputed_proof.target_digest,
        "proof_type": OPERATION_PROOF_V2_TYPE,
        "operation_proof_digest": recomputed_proof.proof_digest,
        "final_verdict": recomputed_proof.final_verdict,
        "verification_strength_class": recomputed_proof.verification_strength_class,
        "cell_revision": cell_revision,
    }
    return OperationCellV1(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "cell_type"}
        },
        cell_digest=_digest(claims),
    )
