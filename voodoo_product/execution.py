from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import statements as sql
from .adapters import AdapterContext, AdapterError, execute_adapter
from .audit import AuditLedger
from .config import ProductConfig
from .evidence_primitives import canonical_json, new_id, utc_now
from .operational_safety import OperationalSafetyService
from .persistence import DatabaseRow, ProductDatabaseAdapter
from .receipt import ReceiptLedger

AdapterExecutor = Callable[..., dict[str, Any]]
IdFactory = Callable[[str], str]
Clock = Callable[[], str]
LeaseDeadline = Callable[[str, int], str]
LeaseExpired = Callable[..., bool]


def timestamp_after(value: str, seconds: int) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("timestamp has no timezone")
    except ValueError as exc:
        raise RuntimeError("execution timestamp is invalid") from exc
    return (parsed + timedelta(seconds=seconds)).astimezone(UTC).isoformat(timespec="milliseconds")


def timestamp_expired(value: str, *, now: str) -> bool:
    try:
        expires_at = datetime.fromisoformat(value)
        current = datetime.fromisoformat(now)
        if expires_at.tzinfo is None or current.tzinfo is None:
            raise ValueError("timestamp has no timezone")
    except ValueError as exc:
        raise RuntimeError("execution lease timestamp is invalid") from exc
    return expires_at <= current


class ExecutionService:
    """Database-bound execution lifecycle, adapter invocation, and recovery boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        config: ProductConfig,
        audit_ledger: AuditLedger,
        receipt_ledger: ReceiptLedger,
        operational_safety_service: OperationalSafetyService,
        adapter_executor: AdapterExecutor = execute_adapter,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
        lease_deadline: LeaseDeadline = timestamp_after,
        lease_expired: LeaseExpired = timestamp_expired,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("execution service audit ledger must use its database")
        if receipt_ledger.db is not database:
            raise ValueError("execution service receipt ledger must use its database")
        if operational_safety_service.db is not database:
            raise ValueError("execution operational safety service must use its database")
        if operational_safety_service.audit_ledger is not audit_ledger:
            raise ValueError(
                "execution operational safety service must use its audit ledger"
            )
        self.db = database
        self.config = config
        self.audit_ledger = audit_ledger
        self.receipt_ledger = receipt_ledger
        self.operational_safety_service = operational_safety_service
        self._adapter_executor = adapter_executor
        self._id_factory = id_factory
        self._clock = clock
        self._lease_deadline = lease_deadline
        self._lease_expired = lease_expired

    def execute_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str | None,
        repository_root: Path,
    ) -> dict[str, Any]:
        existing_execution_id: str | None = None
        request_row: DatabaseRow | None = None
        with self.db.transaction() as connection:
            if idempotency_key:
                existing = connection.execute(
                    sql.SELECT_EXECUTION_BY_IDEMPOTENCY_KEY,
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    if str(existing["request_id"]) != request_id:
                        raise RuntimeError("idempotency key is bound to another request")
                    existing_execution_id = str(existing["id"])

            if existing_execution_id is None:
                if self.operational_safety_service.is_active(connection):
                    raise PermissionError("emergency stop is active")
                request_row = connection.execute(
                    sql.SELECT_CHANGE_REQUEST_FOR_EXECUTION,
                    (request_id,),
                ).fetchone()
                if request_row is None:
                    raise LookupError("change request not found")
                self._require_workspace_environment(request_row)
                if request_row["status"] != "APPROVED":
                    raise PermissionError("change request is not approved")
                if (
                    request_row["environment"] == "production"
                    and not self.config.production_effects_enabled
                ):
                    raise PermissionError("production effects remain disabled")
                execution_id = self._id_factory("exec")
                execution_fence = 1
                now = self._clock()
                lease_expires_at = self._lease_deadline(
                    now,
                    self.config.execution_lease_seconds,
                )
                connection.execute(
                    sql.INSERT_EXECUTION,
                    (
                        execution_id,
                        request_id,
                        request_row["adapter"],
                        idempotency_key,
                        now,
                        lease_expires_at,
                    ),
                )
                connection.execute(
                    sql.MARK_CHANGE_REQUEST_RUNNING,
                    (now, request_id),
                )
                self.audit_ledger.append(
                    connection,
                    actor_id=actor_id,
                    action="execution.start",
                    target_type="execution",
                    target_id=execution_id,
                    payload={"request_id": request_id, "adapter": request_row["adapter"]},
                )

        if existing_execution_id is not None:
            return self.get_execution(existing_execution_id)
        if request_row is None:
            raise RuntimeError("execution start transaction did not produce a request")

        try:
            output = self._adapter_executor(
                str(request_row["adapter"]),
                json.loads(str(request_row["payload_json"])),
                context=AdapterContext(
                    workspace_id=str(request_row["workspace_id"]),
                    repository_root=repository_root.resolve(),
                    sandbox_root=self.config.sandbox_root,
                    timeout_seconds=self.config.execution_timeout_seconds,
                ),
            )
            if output.get("success") is False:
                raise AdapterError("validation adapter returned non-zero status")
            status = "SUCCEEDED"
            error = None
        except Exception as exc:
            output = {"error_type": type(exc).__name__}
            status = "FAILED"
            error = str(exc)[:2000]

        with self.db.transaction() as connection:
            completed_at = self._clock()
            completed = connection.execute(
                sql.COMPLETE_EXECUTION,
                (
                    status,
                    canonical_json(output),
                    error,
                    completed_at,
                    execution_id,
                    execution_fence,
                ),
            ).fetchone()
            if completed is not None:
                request_status = "COMPLETED" if status == "SUCCEEDED" else "FAILED"
                connection.execute(
                    sql.MARK_CHANGE_REQUEST_COMPLETED,
                    (request_status, completed_at, request_id),
                )
                receipt = self.receipt_ledger.append(
                    connection,
                    execution_id=execution_id,
                    payload={
                        "execution_id": execution_id,
                        "request_id": request_id,
                        "workspace_id": request_row["workspace_id"],
                        "actor_id": actor_id,
                        "adapter": request_row["adapter"],
                        "risk": request_row["risk"],
                        "environment": request_row["environment"],
                        "status": status,
                        "output_digest": hashlib.sha256(
                            canonical_json(output).encode("utf-8")
                        ).hexdigest(),
                        "completed_at": completed_at,
                    },
                )
                self.audit_ledger.append(
                    connection,
                    actor_id=actor_id,
                    action=f"execution.{status.lower()}",
                    target_type="execution",
                    target_id=execution_id,
                    payload={
                        "request_id": request_id,
                        "receipt_id": receipt["id"],
                        "error": error,
                    },
                )
        return self.get_execution(execution_id)

    def recover_execution(
        self,
        *,
        actor_id: str,
        execution_id: str,
        reason: str,
    ) -> dict[str, Any]:
        normalized_reason = reason.strip()
        if not 3 <= len(normalized_reason) <= 2_000:
            raise ValueError("recovery reason must contain 3 to 2000 characters")

        with self.db.transaction() as connection:
            if not self.operational_safety_service.is_active(connection):
                raise PermissionError("emergency stop must be active for execution recovery")
            execution = connection.execute(
                sql.SELECT_EXECUTION_FOR_RECOVERY,
                (execution_id,),
            ).fetchone()
            if execution is None:
                raise LookupError("execution not found")
            if execution["status"] != "RUNNING":
                raise RuntimeError("execution is not running")

            now = self._clock()
            raw_lease = execution["lease_expires_at"]
            lease_expires_at = str(raw_lease) if raw_lease is not None else None
            if lease_expires_at is not None and not self._lease_expired(
                lease_expires_at,
                now=now,
            ):
                raise RuntimeError("execution lease has not expired")

            output = {"error_type": "ExecutionInterrupted", "outcome": "INDETERMINATE"}
            error = "execution outcome is indeterminate after lease expiry"
            interrupted = connection.execute(
                sql.INTERRUPT_EXECUTION,
                (
                    canonical_json(output),
                    error,
                    now,
                    execution_id,
                    int(execution["fence"]),
                    lease_expires_at,
                ),
            ).fetchone()
            if interrupted is None:
                raise RuntimeError("execution changed during recovery")

            request_id = str(execution["request_id"])
            connection.execute(
                sql.MARK_CHANGE_REQUEST_COMPLETED,
                ("FAILED", now, request_id),
            )
            receipt = self.receipt_ledger.append(
                connection,
                execution_id=execution_id,
                payload={
                    "execution_id": execution_id,
                    "request_id": request_id,
                    "workspace_id": execution["workspace_id"],
                    "actor_id": actor_id,
                    "adapter": execution["adapter"],
                    "risk": execution["risk"],
                    "environment": execution["environment"],
                    "status": "INTERRUPTED",
                    "outcome": "INDETERMINATE",
                    "output_digest": hashlib.sha256(
                        canonical_json(output).encode("utf-8")
                    ).hexdigest(),
                    "completed_at": now,
                },
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="execution.interrupted",
                target_type="execution",
                target_id=execution_id,
                payload={
                    "request_id": request_id,
                    "receipt_id": receipt["id"],
                    "outcome": "INDETERMINATE",
                    "reason": normalized_reason,
                },
            )
        return self.get_execution(execution_id)

    def list_executions(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_EXECUTIONS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode_execution(dict(row)) for row in rows]

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.GET_EXECUTION,
                (execution_id,),
            ).fetchone()
        if row is None:
            raise LookupError("execution not found")
        return self._decode_execution(dict(row))

    @staticmethod
    def _require_workspace_environment(value: DatabaseRow) -> None:
        request_environment = str(value["environment"])
        workspace_environment = str(value["workspace_environment"])
        valid_environments = {"local", "development", "staging", "production"}
        if (
            request_environment not in valid_environments
            or workspace_environment not in valid_environments
        ):
            raise RuntimeError("change request environment boundary is invalid")
        if request_environment != workspace_environment:
            raise RuntimeError("change request environment does not match workspace")

    @staticmethod
    def _decode_execution(value: dict[str, Any]) -> dict[str, Any]:
        value["output"] = json.loads(value.pop("output_json"))
        value.pop("fence", None)
        return value
