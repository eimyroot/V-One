from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import statements as sql
from .adapters import AdapterContext, AdapterError, execute_adapter
from .config import ProductConfig
from .db import create_product_database
from .persistence import (
    DatabaseConnection,
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseRow,
    ProductDatabaseAdapter,
)
from .security import hash_password, verify_password

VALID_ROLES = {
    "viewer",
    "developer",
    "operator",
    "security_reviewer",
    "auditor",
    "administrator",
}
VALID_RISKS = {"R0", "R1", "R2", "R3", "R4"}
VALID_ENVIRONMENTS = {"local", "development", "staging", "production"}
VALID_ADAPTERS = {"echo", "write_artifact", "run_validation"}
MAX_CHANGE_PAYLOAD_BYTES = 65_536


class AuthRateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__("authentication temporarily rate limited")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


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


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chained_hash(previous_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(f"{previous_hash}\n{canonical_json(payload)}".encode()).hexdigest()


def row_dict(row: DatabaseRow | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class ProductService:
    def __init__(
        self,
        config: ProductConfig,
        *,
        database: ProductDatabaseAdapter | None = None,
    ):
        self.config = config
        self.db = (
            database
            if database is not None
            else create_product_database(
                backend=self.config.database_backend,
                path=self.config.database_path,
            )
        )
        self.db.initialize()
        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)
        self._dummy_password_hash = hash_password(
            f"VOODOO-invalid-account-{secrets.token_urlsafe(32)}"
        )

    def has_users(self) -> bool:
        with self.db.connect() as connection:
            row = connection.execute(sql.COUNT_USERS).fetchone()
            return bool(row and int(row["count"]) > 0)

    def bootstrap_admin(self, *, username: str, password: str, token: str) -> dict[str, Any]:
        if not secrets.compare_digest(token, self.config.bootstrap_token):
            raise PermissionError("invalid bootstrap token")
        with self.db.transaction() as connection:
            count = connection.execute(sql.COUNT_USERS).fetchone()
            if count and int(count["count"]) > 0:
                raise RuntimeError("bootstrap is already closed")
            user_id = new_id("usr")
            workspace_id = new_id("wrk")
            now = utc_now()
            connection.execute(
                sql.INSERT_USER,
                (user_id, username.strip(), hash_password(password), "administrator", now),
            )
            connection.execute(
                sql.INSERT_WORKSPACE,
                (workspace_id, "VOODOO Production", "production", now),
            )
            self._append_audit(
                connection,
                actor_id=user_id,
                action="system.bootstrap",
                target_type="workspace",
                target_id=workspace_id,
                payload={"username": username, "role": "administrator"},
            )
            return {"user_id": user_id, "workspace_id": workspace_id, "role": "administrator"}

    def enforce_login_rate_limit(self, *, username: str, source: str) -> None:
        self._enforce_auth_rate_limits(self._login_rate_limit_keys(username, source))

    def record_login_failure(self, *, username: str, source: str) -> None:
        self._record_auth_failure(self._login_rate_limit_keys(username, source))

    def clear_login_rate_limit(self, *, username: str, source: str) -> None:
        self._clear_auth_rate_limits(self._login_rate_limit_keys(username, source))

    def enforce_bootstrap_rate_limit(self, *, source: str) -> None:
        self._enforce_auth_rate_limits(self._bootstrap_rate_limit_keys(source))

    def record_bootstrap_failure(self, *, source: str) -> None:
        self._record_auth_failure(self._bootstrap_rate_limit_keys(source))

    def clear_bootstrap_rate_limit(self, *, source: str) -> None:
        self._clear_auth_rate_limits(self._bootstrap_rate_limit_keys(source))

    def authenticate(self, *, username: str, password: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_USER_FOR_AUTH,
                (username.strip(),),
            ).fetchone()
        encoded_password = (
            str(row["password_hash"]) if row is not None else self._dummy_password_hash
        )
        password_valid = verify_password(password, encoded_password)
        if row is None or not int(row["active"]) or not password_valid:
            raise PermissionError("invalid credentials")
        return {"id": row["id"], "username": row["username"], "role": row["role"]}

    def _login_rate_limit_keys(
        self, username: str, source: str
    ) -> tuple[tuple[str, str, int], ...]:
        return (
            ("login.account", username, self.config.auth_max_failures),
            ("login.source", source, self.config.auth_source_max_failures),
        )

    def _bootstrap_rate_limit_keys(self, source: str) -> tuple[tuple[str, str, int], ...]:
        return (("bootstrap.source", source, self.config.auth_max_failures),)

    def _auth_rate_limit_key(self, *, scope: str, value: str) -> str:
        normalized = value.strip().casefold()
        return hmac.new(
            self.config.session_signing_secret.encode("utf-8"),
            f"{scope}\0{normalized}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def _enforce_auth_rate_limits(self, entries: tuple[tuple[str, str, int], ...]) -> None:
        now = int(time.time())
        retry_after = 0
        with self.db.transaction() as connection:
            for scope, value, _ in entries:
                key_hash = self._auth_rate_limit_key(scope=scope, value=value)
                row = connection.execute(
                    sql.SELECT_AUTH_RATE_LIMIT,
                    (scope, key_hash),
                ).fetchone()
                if row is None:
                    continue
                blocked_until = int(row["blocked_until"])
                if blocked_until > now:
                    retry_after = max(retry_after, blocked_until - now)
                    continue
                window_expired = now - int(row["window_started_at"]) >= (
                    self.config.auth_window_seconds
                )
                if blocked_until > 0 or window_expired:
                    connection.execute(
                        sql.DELETE_AUTH_RATE_LIMIT,
                        (scope, key_hash),
                    )
        if retry_after:
            raise AuthRateLimitExceeded(retry_after)

    def _record_auth_failure(self, entries: tuple[tuple[str, str, int], ...]) -> None:
        now = int(time.time())
        retry_after = 0
        retention = max(self.config.auth_window_seconds, self.config.auth_lockout_seconds) * 2
        with self.db.transaction() as connection:
            connection.execute(
                sql.DELETE_EXPIRED_AUTH_RATE_LIMITS,
                (now - retention,),
            )
            for scope, value, maximum in entries:
                key_hash = self._auth_rate_limit_key(scope=scope, value=value)
                row = connection.execute(
                    sql.SELECT_AUTH_RATE_LIMIT,
                    (scope, key_hash),
                ).fetchone()
                if row is not None and int(row["blocked_until"]) > now:
                    retry_after = max(retry_after, int(row["blocked_until"]) - now)
                    continue
                if (
                    row is None
                    or int(row["blocked_until"]) > 0
                    or now - int(row["window_started_at"]) >= self.config.auth_window_seconds
                ):
                    failure_count = 1
                    window_started_at = now
                else:
                    failure_count = int(row["failure_count"]) + 1
                    window_started_at = int(row["window_started_at"])
                blocked_until = (
                    now + self.config.auth_lockout_seconds if failure_count >= maximum else 0
                )
                connection.execute(
                    sql.UPSERT_AUTH_RATE_LIMIT,
                    (scope, key_hash, failure_count, window_started_at, blocked_until, now),
                )
                if blocked_until > now:
                    retry_after = max(retry_after, blocked_until - now)
        if retry_after:
            raise AuthRateLimitExceeded(retry_after)

    def _clear_auth_rate_limits(self, entries: tuple[tuple[str, str, int], ...]) -> None:
        with self.db.transaction() as connection:
            for scope, value, _ in entries:
                connection.execute(
                    sql.DELETE_AUTH_RATE_LIMIT,
                    (scope, self._auth_rate_limit_key(scope=scope, value=value)),
                )

    def get_active_user(self, user_id: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_ACTIVE_USER,
                (user_id,),
            ).fetchone()
        if row is None or not int(row["active"]):
            raise PermissionError("account is inactive")
        if str(row["role"]) not in VALID_ROLES:
            raise PermissionError("account role is invalid")
        return {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
        }

    def create_user(
        self, *, actor_id: str, username: str, password: str, role: str
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise ValueError("unknown role")
        user_id = new_id("usr")
        now = utc_now()
        with self.db.transaction() as connection:
            try:
                connection.execute(
                    sql.INSERT_USER,
                    (user_id, username.strip(), hash_password(password), role, now),
                )
            except DatabaseIntegrityError as exc:
                raise ValueError("username already exists") from exc
            self._append_audit(
                connection,
                actor_id=actor_id,
                action="user.create",
                target_type="user",
                target_id=user_id,
                payload={"username": username, "role": role},
            )
        return {"id": user_id, "username": username, "role": role, "active": True}

    def list_workspaces(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_WORKSPACES).fetchall()
        return [dict(row) for row in rows]

    def create_workspace(self, *, actor_id: str, name: str, environment: str) -> dict[str, Any]:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        workspace_id = new_id("wrk")
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                sql.INSERT_WORKSPACE,
                (workspace_id, name.strip(), environment, now),
            )
            self._append_audit(
                connection,
                actor_id=actor_id,
                action="workspace.create",
                target_type="workspace",
                target_id=workspace_id,
                payload={"name": name, "environment": environment},
            )
        return {"id": workspace_id, "name": name, "environment": environment, "created_at": now}

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
        request_id = new_id("cr")
        now = utc_now()
        with self.db.transaction() as connection:
            workspace = connection.execute(sql.SELECT_WORKSPACE_ID, (workspace_id,)).fetchone()
            if workspace is None:
                raise LookupError("workspace not found")
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
            self._append_audit(
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
            if row["status"] != "DRAFT":
                raise RuntimeError("only a draft can be submitted")
            now = utc_now()
            connection.execute(
                sql.MARK_CHANGE_REQUEST_SUBMITTED,
                (now, request_id),
            )
            self._append_audit(
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
            if request_row["status"] not in {"REVIEW_REQUIRED", "APPROVED"}:
                raise RuntimeError("request is not awaiting review")
            if request_row["requested_by"] == actor_id:
                raise PermissionError("requester cannot approve their own change")
            approval_id = new_id("appr")
            now = utc_now()
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
            self._append_audit(
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
                if self._emergency_stop(connection):
                    raise PermissionError("emergency stop is active")
                request_row = connection.execute(
                    sql.SELECT_CHANGE_REQUEST_FOR_EXECUTION, (request_id,)
                ).fetchone()
                if request_row is None:
                    raise LookupError("change request not found")
                if request_row["status"] != "APPROVED":
                    raise PermissionError("change request is not approved")
                if (
                    request_row["environment"] == "production"
                    and not self.config.production_effects_enabled
                ):
                    raise PermissionError("production effects remain disabled")
                execution_id = new_id("exec")
                execution_fence = 1
                now = utc_now()
                lease_expires_at = timestamp_after(now, self.config.execution_lease_seconds)
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
                self._append_audit(
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
            output = execute_adapter(
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
            completed_at = utc_now()
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
                receipt = self._append_receipt(
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
                self._append_audit(
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
            if not self._emergency_stop(connection):
                raise PermissionError("emergency stop must be active for execution recovery")
            execution = connection.execute(
                sql.SELECT_EXECUTION_FOR_RECOVERY,
                (execution_id,),
            ).fetchone()
            if execution is None:
                raise LookupError("execution not found")
            if execution["status"] != "RUNNING":
                raise RuntimeError("execution is not running")

            now = utc_now()
            raw_lease = execution["lease_expires_at"]
            lease_expires_at = str(raw_lease) if raw_lease is not None else None
            if lease_expires_at is not None and not timestamp_expired(lease_expires_at, now=now):
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
            receipt = self._append_receipt(
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
            self._append_audit(
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

    def list_receipts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_RECEIPTS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode_receipt(dict(row)) for row in rows]

    def verify_receipt_chain(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_RECEIPTS_FOR_VERIFICATION).fetchall()
        previous_hash = "GENESIS"
        for expected_sequence, row in enumerate(rows, start=1):
            payload = json.loads(row["payload_json"])
            expected = chained_hash(previous_hash, payload)
            if (
                int(row["sequence"]) != expected_sequence
                or row["previous_hash"] != previous_hash
                or row["receipt_hash"] != expected
            ):
                return {
                    "valid": False,
                    "count": len(rows),
                    "broken_at": expected_sequence,
                    "sequence": row["sequence"],
                    "receipt_id": row["id"],
                }
            previous_hash = row["receipt_hash"]
        return {"valid": True, "count": len(rows), "head": previous_hash}

    def list_audit_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_AUDIT_EVENTS,
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [self._decode_audit(dict(row)) for row in rows]

    def verify_audit_chain(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_AUDIT_EVENTS_FOR_VERIFICATION).fetchall()
        previous_hash = "GENESIS"
        for row in rows:
            payload = {
                "id": row["id"],
                "actor_id": row["actor_id"],
                "action": row["action"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            expected = chained_hash(previous_hash, payload)
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                return {"valid": False, "sequence": row["sequence"], "event_id": row["id"]}
            previous_hash = row["event_hash"]
        return {"valid": True, "count": len(rows), "head": previous_hash}

    def command_center(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            statuses = {
                row["status"]: row["count"]
                for row in connection.execute(sql.COUNT_CHANGE_REQUESTS_BY_STATUS).fetchall()
            }
            executions = {
                row["status"]: row["count"]
                for row in connection.execute(sql.COUNT_EXECUTIONS_BY_STATUS).fetchall()
            }
            risks = {
                row["risk"]: row["count"]
                for row in connection.execute(sql.COUNT_CHANGE_REQUESTS_BY_RISK).fetchall()
            }
            stop = self._emergency_stop(connection)
        receipts = self.verify_receipt_chain()
        audit = self.verify_audit_chain()
        health = "INCIDENT" if stop or not receipts["valid"] or not audit["valid"] else "HEALTHY"
        return {
            "trust_state": health,
            "emergency_stop": stop,
            "change_requests": statuses,
            "executions": executions,
            "risk": risks,
            "pending_approvals": statuses.get("REVIEW_REQUIRED", 0),
            "receipt_integrity": receipts,
            "audit_integrity": audit,
            "production_effects_enabled": self.config.production_effects_enabled,
            "environment": self.config.environment,
        }

    def set_emergency_stop(self, *, actor_id: str, active: bool, reason: str) -> dict[str, Any]:
        with self.db.transaction() as connection:
            now = utc_now()
            connection.execute(
                sql.UPSERT_EMERGENCY_STOP,
                ("true" if active else "false", actor_id, now),
            )
            self._append_audit(
                connection,
                actor_id=actor_id,
                action="system.emergency_stop.activate"
                if active
                else "system.emergency_stop.clear",
                target_type="system",
                target_id="runtime",
                payload={"reason": reason},
            )
        return {"emergency_stop": active, "reason": reason, "updated_at": now}

    def health(self) -> dict[str, Any]:
        try:
            with self.db.connect() as connection:
                connection.execute(sql.HEALTH_CHECK).fetchone()
                stop = self._emergency_stop(connection)
            return {
                "status": "EMERGENCY_STOP" if stop else "HEALTHY",
                "database": "HEALTHY",
                "database_backend": self.db.backend_name,
                "schema_version": self.db.schema_version(),
                "evidence_integrity": "NOT_CHECKED_BY_LIVENESS",
                "production_effects": "ENABLED"
                if self.config.production_effects_enabled
                else "DISABLED",
            }
        except DatabaseError:
            return {
                "status": "UNAVAILABLE",
                "database": "UNAVAILABLE",
                "database_backend": self.db.backend_name,
            }

    def _append_audit(
        self,
        connection: DatabaseConnection,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last = connection.execute(sql.SELECT_AUDIT_HEAD).fetchone()
        previous_hash = str(last["event_hash"]) if last else "GENESIS"
        event = {
            "id": new_id("aud"),
            "actor_id": actor_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload,
            "created_at": utc_now(),
        }
        event_hash = chained_hash(previous_hash, event)
        connection.execute(
            sql.INSERT_AUDIT_EVENT,
            (
                event["id"],
                actor_id,
                action,
                target_type,
                target_id,
                canonical_json(payload),
                previous_hash,
                event_hash,
                event["created_at"],
            ),
        )
        return {**event, "previous_hash": previous_hash, "event_hash": event_hash}

    def _append_receipt(
        self,
        connection: DatabaseConnection,
        *,
        execution_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last = connection.execute(sql.SELECT_RECEIPT_HEAD).fetchone()
        previous_hash = str(last["receipt_hash"]) if last else "GENESIS"
        receipt_hash = chained_hash(previous_hash, payload)
        receipt = {
            "id": new_id("rcpt"),
            "execution_id": execution_id,
            "payload": payload,
            "previous_hash": previous_hash,
            "receipt_hash": receipt_hash,
            "created_at": utc_now(),
        }
        connection.execute(
            sql.INSERT_RECEIPT,
            (
                receipt["id"],
                execution_id,
                canonical_json(payload),
                previous_hash,
                receipt_hash,
                receipt["created_at"],
            ),
        )
        return receipt

    @staticmethod
    def _emergency_stop(connection: DatabaseConnection) -> bool:
        row = connection.execute(sql.SELECT_EMERGENCY_STOP).fetchone()
        return bool(row and str(row["value"]).lower() == "true")

    @staticmethod
    def _decode_change_request(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value

    @staticmethod
    def _decode_execution(value: dict[str, Any]) -> dict[str, Any]:
        value["output"] = json.loads(value.pop("output_json"))
        value.pop("fence", None)
        return value

    @staticmethod
    def _decode_receipt(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value

    @staticmethod
    def _decode_audit(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value
