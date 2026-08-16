from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from . import approval_evidence_statements as approval_sql
from . import statements as sql
from .evidence_primitives import canonical_json
from .execution_contract import ApprovalEvidenceSet, ApprovalRecord, ExecutionTarget
from .persistence import DatabaseConnection, DatabaseRow
from .policy_authority import PolicyRevision
from .trusted_clock import ClockWitness

PAYLOAD_BINDING_TYPE = "request-payload/v1"
PAYLOAD_BINDING_SCHEMA_VERSION = 1


def _decode_canonical_payload(value: DatabaseRow) -> dict[str, Any]:
    raw_payload = str(value["payload_json"])
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("change request payload is not valid canonical JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("change request payload must be a JSON object")
    if raw_payload != canonical_json(payload):
        raise RuntimeError("change request payload is not canonical")
    return payload


def _review_content_sha256(value: DatabaseRow, *, payload: dict[str, Any]) -> str:
    subject = {
        "schema": "change-request-review/v1",
        "workspace_id": str(value["workspace_id"]),
        "title": str(value["title"]),
        "description": str(value["description"]),
        "risk": str(value["risk"]),
        "environment": str(value["environment"]),
        "adapter": str(value["adapter"]),
        "payload": payload,
        "requested_by": str(value["requested_by"]),
    }
    return hashlib.sha256(canonical_json(subject).encode("utf-8")).hexdigest()


def _payload_digest(payload: dict[str, Any]) -> str:
    binding = {
        "schema_version": PAYLOAD_BINDING_SCHEMA_VERSION,
        "binding_type": PAYLOAD_BINDING_TYPE,
        "payload": payload,
    }
    return hashlib.sha256(canonical_json(binding).encode("utf-8")).hexdigest()


def _canonical_datetime(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if value != canonical:
        raise RuntimeError(f"{field} must use canonical UTC millisecond form")
    return parsed.astimezone(UTC)


def load_approval_evidence_on_connection(
    connection: DatabaseConnection,
    *,
    request_id: str,
    capability: str,
    execution_target: ExecutionTarget,
    policy_revision: PolicyRevision,
    clock_witness: ClockWitness,
) -> ApprovalEvidenceSet:
    """Resolve exact persisted approvals without opening or committing a transaction."""

    if not isinstance(execution_target, ExecutionTarget):
        raise ValueError("execution_target is invalid")
    if not isinstance(policy_revision, PolicyRevision):
        raise ValueError("policy_revision is invalid")
    if not isinstance(clock_witness, ClockWitness):
        raise ValueError("clock_witness is invalid")

    request_row = connection.execute(
        sql.SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT,
        (request_id,),
    ).fetchone()
    if request_row is None:
        raise LookupError("change request not found")

    environment = str(request_row["environment"])
    workspace_environment = str(request_row["workspace_environment"])
    if environment != workspace_environment:
        raise RuntimeError("change request environment does not match workspace")
    if clock_witness.environment != environment:
        raise RuntimeError("clock witness environment does not match change request")
    if str(request_row["status"]) != "APPROVED":
        raise RuntimeError("change request is not in approved state")

    payload = _decode_canonical_payload(request_row)
    persisted_review_digest = request_row["review_content_sha256"]
    if persisted_review_digest is None:
        raise RuntimeError("change request review content binding is missing")
    persisted_review_digest = str(persisted_review_digest)
    if _review_content_sha256(request_row, payload=payload) != persisted_review_digest:
        raise RuntimeError("change request review content binding does not match persisted content")

    approval_rows = connection.execute(
        approval_sql.SELECT_APPROVAL_EVIDENCE,
        (request_id,),
    ).fetchall()
    if not approval_rows:
        raise RuntimeError("approved change request has no approval evidence")

    requester_id = str(request_row["requested_by"])
    authorization_time = _canonical_datetime(
        clock_witness.observed_at,
        field="clock_witness.observed_at",
    )
    approvals: list[ApprovalRecord] = []
    validity_deadlines: list[datetime] = []

    for row in approval_rows:
        if str(row["decision"]) != "APPROVED":
            raise RuntimeError("approval evidence contains a non-approved decision")
        approval_review_digest = row["review_content_sha256"]
        if approval_review_digest is None or str(approval_review_digest) != persisted_review_digest:
            raise RuntimeError("approval evidence review content binding mismatch")

        approver_id = str(row["approver_id"])
        if approver_id == requester_id:
            raise PermissionError("requester approval cannot satisfy authorization evidence")

        approved_at = str(row["created_at"])
        approved_at_value = _canonical_datetime(approved_at, field="approval.created_at")
        if approved_at_value > authorization_time:
            raise RuntimeError("approval evidence occurs after authorization time")

        approvals.append(
            ApprovalRecord(
                approval_id=str(row["id"]),
                approver_id=approver_id,
                decision="APPROVED",
                approved_at=approved_at,
            )
        )
        validity_deadlines.append(
            approved_at_value + timedelta(seconds=policy_revision.approval_validity_seconds)
        )

    required_approvals = policy_revision.required_approvals_for(environment)
    if len({approval.approver_id for approval in approvals}) < required_approvals:
        raise PermissionError("approval evidence does not satisfy policy quorum")

    approval_valid_until_value = min(validity_deadlines)
    if approval_valid_until_value <= authorization_time:
        raise PermissionError("approval evidence is expired")
    approval_valid_until = approval_valid_until_value.astimezone(UTC).isoformat(
        timespec="milliseconds"
    )

    return ApprovalEvidenceSet.create(
        request_id=request_id,
        payload_digest=_payload_digest(payload),
        target_digest=execution_target.target_digest,
        capability=capability,
        policy_version=policy_revision.policy_version,
        approvals=approvals,
        approval_valid_until=approval_valid_until,
    )
