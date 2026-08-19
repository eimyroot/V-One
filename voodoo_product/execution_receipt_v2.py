from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .evidence_primitives import canonical_json

EXECUTION_RECEIPT_V2_TYPE: Final = "execution-receipt/v2"
EXECUTION_SUCCEEDED: Final = "SUCCEEDED"
EFFECT_RECORDED: Final = "EFFECT_RECORDED"
NOT_EVALUATED: Final = "NOT_EVALUATED"

_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "receipt_type",
        "execution_id",
        "request_id",
        "environment",
        "capability",
        "target_digest",
        "authorization_snapshot_digest",
        "execution_grant_digest",
        "execution_capsule_digest",
        "grant_consumption_witness_digest",
        "dispatch_envelope_digest",
        "dispatch_admission_digest",
        "execution_lease_digest",
        "runner_identity_digest",
        "runner_boundary_digest",
        "credential_access_decision_digest",
        "runtime_activation_digest",
        "write_effect_preflight_digest",
        "provider_operation",
        "provider_request_digest",
        "provider_response_digest",
        "provider_mutation_performed",
        "provider_mutation_count",
        "automatic_retry_performed",
        "rollback_performed",
        "durable_completion_outcome",
        "durable_completion_digest",
        "execution_status",
        "effect_status",
        "verification_status",
        "recording_clock_witness_digest",
        "recorded_at",
        "receipt_revision",
        "receipt_digest",
    }
)


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


def _require_timestamp(value: object, *, field: str) -> str:
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
    return canonical


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _same(actual: object, expected: object, *, reason: str) -> None:
    if actual != expected:
        raise PermissionError(reason)


@dataclass(frozen=True, slots=True)
class ExecutionReceiptV2:
    """Canonical effect receipt for the current VOP execution lineage.

    The receipt records execution/effect evidence only. It deliberately cannot carry a VERIFIED
    verdict; independent verification remains a separate VerificationResult contract.
    """

    execution_id: str
    request_id: str
    environment: str
    capability: str
    target_digest: str
    authorization_snapshot_digest: str
    execution_grant_digest: str
    execution_capsule_digest: str
    grant_consumption_witness_digest: str
    dispatch_envelope_digest: str
    dispatch_admission_digest: str
    execution_lease_digest: str
    runner_identity_digest: str
    runner_boundary_digest: str
    credential_access_decision_digest: str
    runtime_activation_digest: str
    write_effect_preflight_digest: str
    provider_operation: str
    provider_request_digest: str
    provider_response_digest: str
    provider_mutation_performed: bool
    provider_mutation_count: int
    automatic_retry_performed: bool
    rollback_performed: bool
    durable_completion_outcome: str
    durable_completion_digest: str
    execution_status: str
    effect_status: str
    verification_status: str
    recording_clock_witness_digest: str
    recorded_at: str
    receipt_revision: str
    receipt_digest: str

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "request_id",
            "environment",
            "capability",
            "provider_operation",
            "durable_completion_outcome",
            "execution_status",
            "effect_status",
            "verification_status",
            "receipt_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "authorization_snapshot_digest",
            "execution_grant_digest",
            "execution_capsule_digest",
            "grant_consumption_witness_digest",
            "dispatch_envelope_digest",
            "dispatch_admission_digest",
            "execution_lease_digest",
            "runner_identity_digest",
            "runner_boundary_digest",
            "credential_access_decision_digest",
            "runtime_activation_digest",
            "write_effect_preflight_digest",
            "provider_request_digest",
            "provider_response_digest",
            "durable_completion_digest",
            "recording_clock_witness_digest",
            "receipt_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        _require_timestamp(self.recorded_at, field="recorded_at")
        if type(self.provider_mutation_performed) is not bool:
            raise ValueError("provider_mutation_performed must be bool")
        if type(self.automatic_retry_performed) is not bool:
            raise ValueError("automatic_retry_performed must be bool")
        if type(self.rollback_performed) is not bool:
            raise ValueError("rollback_performed must be bool")
        if type(self.provider_mutation_count) is not int or self.provider_mutation_count < 0:
            raise ValueError("provider_mutation_count must be a non-negative integer")
        if self.execution_status != EXECUTION_SUCCEEDED:
            raise ValueError("execution-receipt/v2 R1 records only successful bounded effects")
        if self.effect_status != EFFECT_RECORDED:
            raise ValueError("successful execution-receipt/v2 must record an effect")
        if self.verification_status != NOT_EVALUATED:
            raise ValueError("ExecutionReceipt must not manufacture a verification verdict")
        if self.provider_mutation_performed is not True or self.provider_mutation_count != 1:
            raise ValueError("successful bounded-write receipt must record exactly one provider mutation")
        if self.automatic_retry_performed is not False:
            raise ValueError("R1 bounded-write receipt forbids automatic mutation retry")
        if self.durable_completion_outcome != "COMPLETED":
            raise ValueError("successful receipt requires durable completion")
        if self.durable_completion_digest != self.provider_response_digest:
            raise ValueError("durable completion must bind the exact provider response digest")
        if self.receipt_digest != _digest(self._claims_without_digest()):
            raise ValueError("receipt_digest does not match execution-receipt/v2")

    @classmethod
    def create(cls, *, receipt_revision: str, **claims: Any) -> Self:
        _require_text(receipt_revision, field="receipt_revision")
        payload = {
            "schema_version": 2,
            "receipt_type": EXECUTION_RECEIPT_V2_TYPE,
            **claims,
            "receipt_revision": receipt_revision,
        }
        values = {
            key: value
            for key, value in payload.items()
            if key not in {"schema_version", "receipt_type"}
        }
        return cls(**values, receipt_digest=_digest(payload))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        if frozenset(value) != _RECEIPT_FIELDS:
            raise ValueError("execution-receipt/v2 fields are invalid")
        if value["schema_version"] != 2 or value["receipt_type"] != EXECUTION_RECEIPT_V2_TYPE:
            raise ValueError("execution-receipt/v2 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _RECEIPT_FIELDS
                if key not in {"schema_version", "receipt_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "receipt_type": EXECUTION_RECEIPT_V2_TYPE,
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "environment": self.environment,
            "capability": self.capability,
            "target_digest": self.target_digest,
            "authorization_snapshot_digest": self.authorization_snapshot_digest,
            "execution_grant_digest": self.execution_grant_digest,
            "execution_capsule_digest": self.execution_capsule_digest,
            "grant_consumption_witness_digest": self.grant_consumption_witness_digest,
            "dispatch_envelope_digest": self.dispatch_envelope_digest,
            "dispatch_admission_digest": self.dispatch_admission_digest,
            "execution_lease_digest": self.execution_lease_digest,
            "runner_identity_digest": self.runner_identity_digest,
            "runner_boundary_digest": self.runner_boundary_digest,
            "credential_access_decision_digest": self.credential_access_decision_digest,
            "runtime_activation_digest": self.runtime_activation_digest,
            "write_effect_preflight_digest": self.write_effect_preflight_digest,
            "provider_operation": self.provider_operation,
            "provider_request_digest": self.provider_request_digest,
            "provider_response_digest": self.provider_response_digest,
            "provider_mutation_performed": self.provider_mutation_performed,
            "provider_mutation_count": self.provider_mutation_count,
            "automatic_retry_performed": self.automatic_retry_performed,
            "rollback_performed": self.rollback_performed,
            "durable_completion_outcome": self.durable_completion_outcome,
            "durable_completion_digest": self.durable_completion_digest,
            "execution_status": self.execution_status,
            "effect_status": self.effect_status,
            "verification_status": self.verification_status,
            "recording_clock_witness_digest": self.recording_clock_witness_digest,
            "recorded_at": self.recorded_at,
            "receipt_revision": self.receipt_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["receipt_digest"] = self.receipt_digest
        return payload


def compose_write_execution_receipt_v2(
    *,
    write_result: Mapping[str, Any],
    recording_clock_witness_digest: str,
    recorded_at: str,
    receipt_revision: str,
) -> ExecutionReceiptV2:
    """Fail-closed projection of one completed governed write into ExecutionReceipt/v2."""

    result = _mapping(write_result, field="write_result")
    _same(result.get("status"), "EFFECT_RECORDED_NOT_VERIFIED", reason="RECEIPT_WRITER_STATUS_INVALID")
    _same(result.get("provider_mutation_performed"), True, reason="RECEIPT_PROVIDER_EFFECT_MISSING")
    _same(result.get("provider_mutation_count"), 1, reason="RECEIPT_PROVIDER_MUTATION_COUNT_INVALID")
    _same(result.get("automatic_retry_performed"), False, reason="RECEIPT_AUTOMATIC_RETRY_FORBIDDEN")

    target = _mapping(result.get("target"), field="target")
    grant = _mapping(result.get("execution_grant"), field="execution_grant")
    consumption = _mapping(result.get("grant_consumption"), field="grant_consumption")
    envelope = _mapping(result.get("dispatch_envelope"), field="dispatch_envelope")
    admission = _mapping(result.get("dispatch_admission"), field="dispatch_admission")
    lease = _mapping(result.get("execution_lease"), field="execution_lease")
    identity = _mapping(result.get("runner_identity"), field="runner_identity")
    boundary = _mapping(result.get("runner_boundary"), field="runner_boundary")
    decision = _mapping(result.get("credential_decision"), field="credential_decision")
    activation = _mapping(result.get("runtime_activation"), field="runtime_activation")
    preflight = _mapping(result.get("write_effect_preflight"), field="write_effect_preflight")
    request = _mapping(result.get("create_ref_request"), field="provider_request")
    response = _mapping(result.get("provider_response"), field="provider_response")
    completion = _mapping(result.get("durable_completion"), field="durable_completion")

    execution_id = _require_text(grant.get("execution_id"), field="execution_id")
    grant_digest = _require_digest(grant.get("grant_digest"), field="grant_digest")
    target_digest = _require_digest(target.get("target_digest"), field="target_digest")
    snapshot_digest = _require_digest(
        result.get("authorization_snapshot_digest"), field="authorization_snapshot_digest"
    )
    capsule_digest = _require_digest(
        grant.get("execution_capsule_digest"), field="execution_capsule_digest"
    )
    consumption_digest = _require_digest(
        consumption.get("witness_digest"), field="grant_consumption_witness_digest"
    )
    envelope_digest = _require_digest(envelope.get("envelope_digest"), field="dispatch_envelope_digest")
    admission_digest = _require_digest(admission.get("admission_digest"), field="dispatch_admission_digest")
    lease_digest = _require_digest(lease.get("lease_digest"), field="execution_lease_digest")
    identity_digest = _require_digest(identity.get("identity_digest"), field="runner_identity_digest")
    boundary_digest = _require_digest(boundary.get("boundary_digest"), field="runner_boundary_digest")
    decision_digest = _require_digest(decision.get("decision_digest"), field="credential_access_decision_digest")
    activation_digest = _require_digest(activation.get("activation_digest"), field="runtime_activation_digest")
    preflight_digest = _require_digest(preflight.get("preflight_digest"), field="write_effect_preflight_digest")
    request_digest = _require_digest(request.get("request_digest"), field="provider_request_digest")
    response_digest = _require_digest(response.get("response_digest"), field="provider_response_digest")

    # Exact lineage checks. Downstream evidence may narrow or record an effect; it may not rebind it.
    _same(grant.get("target_digest"), target_digest, reason="RECEIPT_GRANT_TARGET_MISMATCH")
    _same(grant.get("authorization_snapshot_digest"), snapshot_digest, reason="RECEIPT_GRANT_SNAPSHOT_MISMATCH")
    _same(consumption.get("grant_digest"), grant_digest, reason="RECEIPT_CONSUMPTION_GRANT_MISMATCH")
    _same(consumption.get("execution_id"), execution_id, reason="RECEIPT_CONSUMPTION_EXECUTION_MISMATCH")
    _same(envelope.get("grant_digest"), grant_digest, reason="RECEIPT_ENVELOPE_GRANT_MISMATCH")
    _same(envelope.get("execution_id"), execution_id, reason="RECEIPT_ENVELOPE_EXECUTION_MISMATCH")
    _same(envelope.get("consumption_witness_digest"), consumption_digest, reason="RECEIPT_ENVELOPE_CONSUMPTION_MISMATCH")
    _same(admission.get("envelope_digest"), envelope_digest, reason="RECEIPT_ADMISSION_ENVELOPE_MISMATCH")
    _same(admission.get("execution_id"), execution_id, reason="RECEIPT_ADMISSION_EXECUTION_MISMATCH")
    _same(lease.get("admission_digest"), admission_digest, reason="RECEIPT_LEASE_ADMISSION_MISMATCH")
    _same(lease.get("execution_id"), execution_id, reason="RECEIPT_LEASE_EXECUTION_MISMATCH")
    _same(boundary.get("runner_identity_digest"), identity_digest, reason="RECEIPT_BOUNDARY_IDENTITY_MISMATCH")
    _same(boundary.get("lease_digest"), lease_digest, reason="RECEIPT_BOUNDARY_LEASE_MISMATCH")
    _same(boundary.get("execution_id"), execution_id, reason="RECEIPT_BOUNDARY_EXECUTION_MISMATCH")
    _same(decision.get("runner_boundary_digest"), boundary_digest, reason="RECEIPT_DECISION_BOUNDARY_MISMATCH")
    _same(decision.get("execution_id"), execution_id, reason="RECEIPT_DECISION_EXECUTION_MISMATCH")
    _same(activation.get("runner_boundary_digest"), boundary_digest, reason="RECEIPT_ACTIVATION_BOUNDARY_MISMATCH")
    _same(activation.get("credential_decision_digest"), decision_digest, reason="RECEIPT_ACTIVATION_DECISION_MISMATCH")
    _same(activation.get("execution_id"), execution_id, reason="RECEIPT_ACTIVATION_EXECUTION_MISMATCH")
    _same(preflight.get("grant_digest"), grant_digest, reason="RECEIPT_PREFLIGHT_GRANT_MISMATCH")
    _same(preflight.get("consumption_witness_digest"), consumption_digest, reason="RECEIPT_PREFLIGHT_CONSUMPTION_MISMATCH")
    _same(preflight.get("dispatch_envelope_digest"), envelope_digest, reason="RECEIPT_PREFLIGHT_ENVELOPE_MISMATCH")
    _same(preflight.get("admission_digest"), admission_digest, reason="RECEIPT_PREFLIGHT_ADMISSION_MISMATCH")
    _same(preflight.get("lease_digest"), lease_digest, reason="RECEIPT_PREFLIGHT_LEASE_MISMATCH")
    _same(preflight.get("runner_identity_digest"), identity_digest, reason="RECEIPT_PREFLIGHT_IDENTITY_MISMATCH")
    _same(preflight.get("runner_boundary_digest"), boundary_digest, reason="RECEIPT_PREFLIGHT_BOUNDARY_MISMATCH")
    _same(preflight.get("credential_decision_digest"), decision_digest, reason="RECEIPT_PREFLIGHT_DECISION_MISMATCH")
    _same(preflight.get("runtime_activation_digest"), activation_digest, reason="RECEIPT_PREFLIGHT_ACTIVATION_MISMATCH")
    _same(preflight.get("target_digest"), target_digest, reason="RECEIPT_PREFLIGHT_TARGET_MISMATCH")
    _same(preflight.get("request_digest"), request_digest, reason="RECEIPT_PREFLIGHT_REQUEST_MISMATCH")
    _same(preflight.get("execution_id"), execution_id, reason="RECEIPT_PREFLIGHT_EXECUTION_MISMATCH")
    _same(request.get("target_digest"), target_digest, reason="RECEIPT_REQUEST_TARGET_MISMATCH")
    _same(request.get("runner_boundary_digest"), boundary_digest, reason="RECEIPT_REQUEST_BOUNDARY_MISMATCH")
    _same(request.get("credential_decision_digest"), decision_digest, reason="RECEIPT_REQUEST_DECISION_MISMATCH")
    _same(completion.get("completion_digest"), response_digest, reason="RECEIPT_COMPLETION_RESPONSE_MISMATCH")
    _same(completion.get("outcome"), "COMPLETED", reason="RECEIPT_COMPLETION_OUTCOME_INVALID")

    return ExecutionReceiptV2.create(
        execution_id=execution_id,
        request_id=_require_text(grant.get("request_id"), field="request_id"),
        environment=_require_text(grant.get("environment"), field="environment"),
        capability=_require_text(grant.get("capability"), field="capability"),
        target_digest=target_digest,
        authorization_snapshot_digest=snapshot_digest,
        execution_grant_digest=grant_digest,
        execution_capsule_digest=capsule_digest,
        grant_consumption_witness_digest=consumption_digest,
        dispatch_envelope_digest=envelope_digest,
        dispatch_admission_digest=admission_digest,
        execution_lease_digest=lease_digest,
        runner_identity_digest=identity_digest,
        runner_boundary_digest=boundary_digest,
        credential_access_decision_digest=decision_digest,
        runtime_activation_digest=activation_digest,
        write_effect_preflight_digest=preflight_digest,
        provider_operation=_require_text(result.get("provider_operation"), field="provider_operation"),
        provider_request_digest=request_digest,
        provider_response_digest=response_digest,
        provider_mutation_performed=True,
        provider_mutation_count=1,
        automatic_retry_performed=False,
        rollback_performed=bool(result.get("rollback_performed")),
        durable_completion_outcome="COMPLETED",
        durable_completion_digest=response_digest,
        execution_status=EXECUTION_SUCCEEDED,
        effect_status=EFFECT_RECORDED,
        verification_status=NOT_EVALUATED,
        recording_clock_witness_digest=_require_digest(
            recording_clock_witness_digest, field="recording_clock_witness_digest"
        ),
        recorded_at=_require_timestamp(recorded_at, field="recorded_at"),
        receipt_revision=receipt_revision,
    )
