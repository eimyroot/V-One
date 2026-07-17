from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import canonical_json, new_id, utc_now
from .persistence import DatabaseIntegrityError, DatabaseRow, ProductDatabaseAdapter

IdFactory = Callable[[str], str]
Clock = Callable[[], str]

VALID_RISKS = {"R0", "R1", "R2", "R3", "R4"}
VALID_ENVIRONMENTS = {"local", "development", "staging", "production"}
VALID_ADAPTERS = {"echo", "write_artifact", "run_validation"}
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
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("change request audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock

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
            now = self._clock()
            connection.execute(
                sql.MARK_CHANGE_REQUEST_SUBMITTED,
                (now, request_id),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="change_request.submit",
                target_type="change_request",
                target_id=request_id,
                payload={},
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
            if request_row["status"] not in {"REVIEW_REQUIRED", "APPROVED"}:
                raise RuntimeError("request is not awaiting review")
            if request_row["requested_by"] == actor_id:
                raise PermissionError("requester cannot approve their own change")
            approval_id = self._id_factory("appr")
            now = self._clock()
            try:
                connection.execute(
                    sql.INSERT_APPROVAL,
                    (approval_id, request_id, actor_id, decision, reason.strip(), now),
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
                required = 2 if request_row["environment"] == "production" else 1
                next_status = "APPROVED" if int(approved_count) >= required else "REVIEW_REQUIRED"
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
                payload={"reason": reason, "resulting_status": next_status},
            )
        return self.get_change_request(request_id)

    def list_approvals(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_PENDING_APPROVALS if pending_only else sql.LIST_APPROVALS
            ).fetchall()
        return [dict(row) for row in rows]

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
