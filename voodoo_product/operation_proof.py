from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from .authorization_snapshot import AuthorizationSnapshot
from .evidence_primitives import canonical_json
from .execution_contract import ExecutionGrant, ExecutionReceipt
from .operation_semantics import OperationSemantics

SCHEMA_VERSION = 1
INDEPENDENT_VERIFICATION_TYPE = "independent-verification/v1"
OPERATION_PROOF_TYPE = "operation-proof/v1"

VERIFIED = "VERIFIED"
NOT_VERIFIED = "NOT_VERIFIED"
INDETERMINATE = "INDETERMINATE"

_VERDICTS = frozenset({VERIFIED, NOT_VERIFIED, INDETERMINATE})


class OperationProofError(ValueError):
    """Fail-closed error for one V-One operation-proof invariant."""


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


@dataclass(frozen=True, slots=True)
class IndependentVerification:
    verifier_id: str
    execution_id: str
    target_digest: str
    observed_output_digest: str
    observed_postcondition_digest: str
    verdict: str
    checked_at: str
    evidence_digest: str
    verification_digest: str

    def __post_init__(self) -> None:
        for field in ("verifier_id", "execution_id", "checked_at"):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "observed_output_digest",
            "observed_postcondition_digest",
            "evidence_digest",
            "verification_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.verdict not in _VERDICTS:
            raise ValueError("verification verdict is invalid")
        if self.verification_digest != _digest(self._claims_without_digest()):
            raise ValueError("verification_digest does not match verification claims")

    @classmethod
    def create(
        cls,
        *,
        verifier_id: str,
        execution_id: str,
        target_digest: str,
        observed_output_digest: str,
        observed_postcondition_digest: str,
        verdict: str,
        checked_at: str,
        evidence_digest: str,
    ) -> Self:
        claims = {
            "schema_version": SCHEMA_VERSION,
            "verification_type": INDEPENDENT_VERIFICATION_TYPE,
            "verifier_id": verifier_id,
            "execution_id": execution_id,
            "target_digest": target_digest,
            "observed_output_digest": observed_output_digest,
            "observed_postcondition_digest": observed_postcondition_digest,
            "verdict": verdict,
            "checked_at": checked_at,
            "evidence_digest": evidence_digest,
        }
        return cls(
            verifier_id=verifier_id,
            execution_id=execution_id,
            target_digest=target_digest,
            observed_output_digest=observed_output_digest,
            observed_postcondition_digest=observed_postcondition_digest,
            verdict=verdict,
            checked_at=checked_at,
            evidence_digest=evidence_digest,
            verification_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "verification_type",
                "verifier_id",
                "execution_id",
                "target_digest",
                "observed_output_digest",
                "observed_postcondition_digest",
                "verdict",
                "checked_at",
                "evidence_digest",
                "verification_digest",
            }
        )
        _require_exact_fields(
            value,
            expected,
            contract=INDEPENDENT_VERIFICATION_TYPE,
        )
        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError("schema_version is unsupported")
        if value["verification_type"] != INDEPENDENT_VERIFICATION_TYPE:
            raise ValueError("verification_type is unsupported")
        created = cls.create(
            verifier_id=value["verifier_id"],
            execution_id=value["execution_id"],
            target_digest=value["target_digest"],
            observed_output_digest=value["observed_output_digest"],
            observed_postcondition_digest=value["observed_postcondition_digest"],
            verdict=value["verdict"],
            checked_at=value["checked_at"],
            evidence_digest=value["evidence_digest"],
        )
        if value["verification_digest"] != created.verification_digest:
            raise ValueError("verification_digest does not match verification claims")
        return created

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "verification_type": INDEPENDENT_VERIFICATION_TYPE,
            "verifier_id": self.verifier_id,
            "execution_id": self.execution_id,
            "target_digest": self.target_digest,
            "observed_output_digest": self.observed_output_digest,
            "observed_postcondition_digest": self.observed_postcondition_digest,
            "verdict": self.verdict,
            "checked_at": self.checked_at,
            "evidence_digest": self.evidence_digest,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["verification_digest"] = self.verification_digest
        return payload


@dataclass(frozen=True, slots=True)
class OperationProof:
    proof_id: str
    operation_id: str
    capability: str
    semantics_digest: str
    snapshot_digest: str
    grant_digest: str
    receipt_digest: str
    verification_digest: str
    final_verdict: str
    proof_digest: str

    def __post_init__(self) -> None:
        for field in ("proof_id", "operation_id", "capability"):
            _require_text(getattr(self, field), field=field)
        for field in (
            "semantics_digest",
            "snapshot_digest",
            "grant_digest",
            "receipt_digest",
            "verification_digest",
            "proof_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.final_verdict not in _VERDICTS:
            raise ValueError("final_verdict is invalid")
        if self.proof_digest != _digest(self._claims_without_digest()):
            raise ValueError("proof_digest does not match operation proof")

    @classmethod
    def create(
        cls,
        *,
        proof_id: str,
        semantics: OperationSemantics,
        snapshot: AuthorizationSnapshot,
        grant: ExecutionGrant,
        receipt: ExecutionReceipt,
        verification: IndependentVerification,
    ) -> Self:
        validate_operation_invariants(
            semantics=semantics,
            snapshot=snapshot,
            grant=grant,
            receipt=receipt,
            verification=verification,
        )
        final_verdict = _final_verdict(receipt=receipt, verification=verification)
        claims = {
            "schema_version": SCHEMA_VERSION,
            "proof_type": OPERATION_PROOF_TYPE,
            "proof_id": proof_id,
            "operation_id": semantics.operation_id,
            "capability": semantics.capability,
            "semantics_digest": semantics.semantics_digest,
            "snapshot_digest": snapshot.snapshot_digest,
            "grant_digest": grant.grant_digest,
            "receipt_digest": receipt.receipt_digest,
            "verification_digest": verification.verification_digest,
            "final_verdict": final_verdict,
        }
        return cls(
            proof_id=proof_id,
            operation_id=semantics.operation_id,
            capability=semantics.capability,
            semantics_digest=semantics.semantics_digest,
            snapshot_digest=snapshot.snapshot_digest,
            grant_digest=grant.grant_digest,
            receipt_digest=receipt.receipt_digest,
            verification_digest=verification.verification_digest,
            final_verdict=final_verdict,
            proof_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "proof_type",
                "proof_id",
                "operation_id",
                "capability",
                "semantics_digest",
                "snapshot_digest",
                "grant_digest",
                "receipt_digest",
                "verification_digest",
                "final_verdict",
                "proof_digest",
            }
        )
        _require_exact_fields(value, expected, contract=OPERATION_PROOF_TYPE)
        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError("schema_version is unsupported")
        if value["proof_type"] != OPERATION_PROOF_TYPE:
            raise ValueError("proof_type is unsupported")
        created = cls(
            proof_id=value["proof_id"],
            operation_id=value["operation_id"],
            capability=value["capability"],
            semantics_digest=value["semantics_digest"],
            snapshot_digest=value["snapshot_digest"],
            grant_digest=value["grant_digest"],
            receipt_digest=value["receipt_digest"],
            verification_digest=value["verification_digest"],
            final_verdict=value["final_verdict"],
            proof_digest=value["proof_digest"],
        )
        return created

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "proof_type": OPERATION_PROOF_TYPE,
            "proof_id": self.proof_id,
            "operation_id": self.operation_id,
            "capability": self.capability,
            "semantics_digest": self.semantics_digest,
            "snapshot_digest": self.snapshot_digest,
            "grant_digest": self.grant_digest,
            "receipt_digest": self.receipt_digest,
            "verification_digest": self.verification_digest,
            "final_verdict": self.final_verdict,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["proof_digest"] = self.proof_digest
        return payload


def validate_operation_invariants(
    *,
    semantics: OperationSemantics,
    snapshot: AuthorizationSnapshot,
    grant: ExecutionGrant,
    receipt: ExecutionReceipt,
    verification: IndependentVerification,
) -> None:
    """Enforce the critical V-One operation invariants as pure contract checks."""

    if not isinstance(semantics, OperationSemantics):
        raise OperationProofError("semantics must be operation-semantics/v1")
    if not isinstance(snapshot, AuthorizationSnapshot):
        raise OperationProofError("snapshot must be authorization-snapshot/v1")
    if not isinstance(grant, ExecutionGrant):
        raise OperationProofError("grant must be execution-grant/v1")
    if not isinstance(receipt, ExecutionReceipt):
        raise OperationProofError("receipt must be execution-receipt/v1")
    if not isinstance(verification, IndependentVerification):
        raise OperationProofError("verification must be independent-verification/v1")

    snapshot_bindings = {
        "operation_id": (semantics.operation_id, snapshot.request_id),
        "capability": (semantics.capability, snapshot.capability),
    }
    grant_bindings = {
        "execution_id": (snapshot.execution_id, grant.execution_id),
        "request_id": (snapshot.request_id, grant.request_id),
        "actor_id": (snapshot.actor_id, grant.actor_id),
        "workspace_id": (snapshot.workspace_id, grant.workspace_id),
        "environment": (snapshot.environment, grant.environment),
        "capability": (snapshot.capability, grant.capability),
        "target_digest": (snapshot.target_digest, grant.target_digest),
        "payload_digest": (snapshot.payload_digest, grant.payload_digest),
        "approval_set_digest": (snapshot.approval_set_digest, grant.approval_set_digest),
        "policy_version": (snapshot.policy_version, grant.policy_version),
    }
    receipt_bindings = {
        "grant_digest": (grant.grant_digest, receipt.grant_digest),
        "grant_id": (grant.grant_id, receipt.grant_id),
        "execution_id": (grant.execution_id, receipt.execution_id),
    }
    verification_bindings = {
        "execution_id": (receipt.execution_id, verification.execution_id),
        "target_digest": (grant.target_digest, verification.target_digest),
        "output_digest": (receipt.output_digest, verification.observed_output_digest),
        "postcondition_digest": (
            receipt.postcondition_digest,
            verification.observed_postcondition_digest,
        ),
    }
    mismatches = _mismatches(
        {
            **snapshot_bindings,
            **grant_bindings,
            **receipt_bindings,
            **verification_bindings,
        }
    )
    if mismatches:
        raise OperationProofError(f"operation invariant mismatch: {mismatches}")

    approver_ids = {
        approval.approver_id
        for approval in snapshot.approval_evidence.approvals
    }
    if grant.actor_id in approver_ids:
        raise OperationProofError("NoSelfApproval violated")
    if receipt.runner_id == verification.verifier_id:
        raise OperationProofError("independent verification requires a distinct verifier")
    if grant.actor_id == verification.verifier_id:
        raise OperationProofError("actor cannot verify its own operation")
    if receipt.outcome == "EXPECTED_EFFECT_VERIFIED" and verification.verdict != VERIFIED:
        raise OperationProofError("runner success requires independent verification")


def _final_verdict(
    *,
    receipt: ExecutionReceipt,
    verification: IndependentVerification,
) -> str:
    if (
        receipt.status == "SUCCEEDED"
        and receipt.outcome == "EXPECTED_EFFECT_VERIFIED"
        and receipt.postcondition_status == "PASSED"
        and verification.verdict == VERIFIED
    ):
        return VERIFIED
    if verification.verdict == INDETERMINATE or receipt.outcome == "INDETERMINATE":
        return INDETERMINATE
    return NOT_VERIFIED


def _mismatches(bindings: Mapping[str, tuple[object, object]]) -> list[str]:
    return sorted(name for name, (actual, expected) in bindings.items() if actual != expected)
