from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from . import statements as sql
from .approval_policy import (
    VALID_ENVIRONMENTS,
    VALID_RISKS,
    ApprovalPolicyDecision,
    ApprovalPolicyEvaluator,
    ApprovalPolicyInput,
    evaluate_current_approval_policy,
    resolve_current_approval_policy,
)
from .audit import AuditLedger
from .evidence_primitives import canonical_json, new_id, utc_now
from .persistence import DatabaseIntegrityError, DatabaseRow, ProductDatabaseAdapter

IdFactory = Callable[[str], str]
Clock = Callable[[], str]

VALID_ADAPTERS = {"echo", "write_artifact", "run_validation", "github-create-ref"}
MAX_CHANGE_PAYLOAD_BYTES = 65_536


class ChangeRequestService:
    """Database-bound change-request and approval lifecycle boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
        approval_policy_compatibility_enabled: bool = False,
        approval_policy_evaluator: ApprovalPolicyEvaluator = evaluate_current_approval_policy,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("change request audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock
        self.approval_policy_compatibility_enabled = approval_policy_compatibility_enabled
        self._approval_policy_evaluator = approval_policy_evaluator

    def create_change_request(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        title: str,
        description: str,
        risk: str,
        environment: str,
        adapter: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if risk not in VALID_RISKS:
            raise ValueError("unknown risk")
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        if adapter not in VALID_ADAPTERS:
            raise ValueError("adapter is not registered")
        encoded_payload = canonical_json(payload)
        if len(encoded_payload.encode("utf-8")) > MAX_CHANGE_PAYLOAD_BYTES:
            raise ValueError("change request payload exceeds the governed limit")
        request_id = self._id_factory("cr")
        now = self._clock()
        with self.db.transaction() as connection:
            workspace = connection.execute(
                sql.SELECT_WORKSPACE_CONTEXT,
                (workspace_id,),
            ).fetchone()
            if workspace is None:
                raise LookupError("workspace not found")
            if str(workspace["environment"]) != environment:
                raise ValueError("change request environment must match workspace environment")
            connection.execute(
                sql.INSERT_CHANGE_REQUEST,
                (
                    request_id,
                    workspace_id,
                    title.strip(),
                    description.strip(),
                    risk,
                    environment,
                    adapter,
                    encoded_payload,
                    actor_id,
                    now,
                    now,
                ),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="change_request.create",
                target_type="change_request",
                target_id=request_id,
                payload={"risk": risk, "environment": environment, "adapter": adapter},
            )
        return self.get_change_request(request_id)

    def list_change_requests(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_CHANGE_REQUESTS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode_change_request(dict(row)) for row in rows]

    def get_change_request(self, request_id: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.GET_CHANGE_REQUEST,
                (request_id,),
            ).fetchone()
        if row is None:
            raise LookupError("change request not found")
        return self._decode_change_request(dict(row))

    def submit_change_request(self, *, actor_id: str, request_id: str) -> dict[str, Any]:
        with self.db.transaction() as connection:
            row = connection.execute(sql.SELECT_CHANGE_REQUEST_STATUS, (request_id,)).fetchone()
            if row is None:
                raise LookupError("change request not found")
            self._require_workspace_environment(row)
            if row["status"] != "DRAFT":
                raise RuntimeError("only a draft can be submitted")
            if row["review_content_sha256"] is not None:
                raise RuntimeError("draft review content binding must be empty")
            review_content_sha256 = self._review_content_sha256(row)
            now = self._clock()
            connection.execute(
                sql.MARK_CHANGE_REQUEST_SUBMITTED,
                (review_content_sha256, now, request_id),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="change_request.submit",
                target_type="change_request",
                target_id=request_id,
                payload={"review_content_sha256": review_content_sha256},
            )
        return self.get_change_request(request_id)

    def approve_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        decision: str,
        reason: str,
    ) -> dict[str, Any]:
        decision = decision.upper()
        if decision not in {"APPROVED", "DENIED"}:
            raise ValueError("decision must be APPROVED or DENIED")
        with self.db.transaction() as connection:
            request_row = connection.execute(
                sql.SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT,
                (request_id,),
            ).fetchone()
            if request_row is None:
                raise LookupError("change request not found")
            self._require_workspace_environment(request_row)
            if request_row["status"] != "REVIEW_REQUIRED":
                raise RuntimeError("request is not awaiting review")
            if request_row["requested_by"] == actor_id:
                raise PermissionError("requester cannot approve their own change")
            review_content_sha256 = request_row["review_content_sha256"]
            if review_content_sha256 is None:
                raise RuntimeError("request review content binding is missing")
            review_content_sha256 = str(review_content_sha256)
            if self._review_content_sha256(request_row) != review_content_sha256:
                raise RuntimeError("request review content binding does not match persisted content")
            policy_decision = (
                self._approval_policy_decision(request_row)
                if decision == "APPROVED"
                else None
            )
            required_approvals = (
                policy_decision.required_approvals
                if policy_decision is not None
                else None
            )
            approval_id = self._id_factory("appr")
            now = self._clock()
            try:
                connection.execute(
                    sql.INSERT_APPROVAL,
                    (
                        approval_id,
                        request_id,
                        actor_id,
                        decision,
                        reason.strip(),
                        review_content_sha256,
                        now,
                    ),
                )
            except DatabaseIntegrityError as exc:
                raise RuntimeError("approver already decided this request") from exc

            if decision == "DENIED":
                next_status = "DENIED"
            else:
                approved_count = connection.execute(
                    sql.COUNT_APPROVED,
                    (request_id,),
                ).fetchone()["count"]
                next_status = (
                    "APPROVED"
                    if required_approvals is not None and int(approved_count) >= required_approvals
                    else "REVIEW_REQUIRED"
                )
            connection.execute(
                sql.UPDATE_CHANGE_REQUEST_STATUS,
                (next_status, now, request_id),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action=f"change_request.{decision.lower()}",
                target_type="change_request",
                target_id=request_id,
                payload={
                    "reason": reason,
                    "resulting_status": next_status,
                    "review_content_sha256": review_content_sha256,
                    **(
                        {"approval_policy": policy_decision.to_dict()}
                        if policy_decision is not None
                        else {}
                    ),
                },
            )
        return self.get_change_request(request_id)

    def list_approvals(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_PENDING_APPROVALS if pending_only else sql.LIST_APPROVALS
            ).fetchall()
        approvals = [dict(row) for row in rows]
        for approval in approvals:
            approval["required_count"] = self._required_approvals(approval)
        return approvals

    def _required_approvals(self, value: DatabaseRow | dict[str, Any]) -> int:
        return self._approval_policy_decision(value).required_approvals

    def _approval_policy_decision(
        self,
        value: DatabaseRow | dict[str, Any],
    ) -> ApprovalPolicyDecision:
        policy_input = ApprovalPolicyInput(
            environment=str(value["environment"]),
            risk=str(value["risk"]),
        )
        if not self.approval_policy_compatibility_enabled:
            return evaluate_current_approval_policy(policy_input)
        return resolve_current_approval_policy(
            policy_input,
            evaluator=self._approval_policy_evaluator,
        )

    @staticmethod
    def _review_content_sha256(value: DatabaseRow | dict[str, Any]) -> str:
        try:
            payload = json.loads(str(value["payload_json"]))
        except json.JSONDecodeError as exc:
            raise RuntimeError("change request payload is not valid canonical JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("change request payload must be a JSON object")
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

    @staticmethod
    def _require_workspace_environment(value: DatabaseRow) -> None:
        request_environment = str(value["environment"])
        workspace_environment = str(value["workspace_environment"])
        if (
            request_environment not in VALID_ENVIRONMENTS
            or workspace_environment not in VALID_ENVIRONMENTS
        ):
            raise RuntimeError("change request environment boundary is invalid")
        if request_environment != workspace_environment:
            raise RuntimeError("change request environment does not match workspace")

    @staticmethod
    def _decode_change_request(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value
