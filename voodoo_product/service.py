from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import Any

from . import statements as sql
from .adapters import execute_adapter
from .audit import AuditLedger
from .auth_rate_limit import AuthenticationRateLimitService, AuthRateLimitExceeded
from .bootstrap import BootstrapService
from .change_request import ChangeRequestService
from .config import ProductConfig
from .db import create_product_database
from .evidence_primitives import canonical_json, chained_hash, new_id, utc_now
from .execution import ExecutionService, timestamp_after, timestamp_expired
from .operational_safety import OperationalSafetyService
from .persistence import DatabaseConnection, DatabaseRow, ProductDatabaseAdapter
from .platform_status import PlatformStatusService
from .receipt import ReceiptLedger
from .security import hash_password, verify_password
from .user_account import UserAccountService
from .workspace import WorkspaceService

__all__ = [
    "AuthRateLimitExceeded",
    "ProductService",
    "canonical_json",
    "chained_hash",
    "new_id",
    "utc_now",
]

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


def row_dict(row: DatabaseRow | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class ProductService:
    def __init__(
        self,
        config: ProductConfig,
        *,
        database: ProductDatabaseAdapter | None = None,
        authentication_rate_limit_service: AuthenticationRateLimitService | None = None,
        bootstrap_service: BootstrapService | None = None,
        audit_ledger: AuditLedger | None = None,
        user_account_service: UserAccountService | None = None,
        workspace_service: WorkspaceService | None = None,
        change_request_service: ChangeRequestService | None = None,
        receipt_ledger: ReceiptLedger | None = None,
        operational_safety_service: OperationalSafetyService | None = None,
        execution_service: ExecutionService | None = None,
        platform_status_service: PlatformStatusService | None = None,
    ) -> None:
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
        resolved_authentication_rate_limit_service = (
            authentication_rate_limit_service
            or AuthenticationRateLimitService(
                database=self.db,
                config=self.config,
                clock=lambda: time.time(),
            )
        )
        if resolved_authentication_rate_limit_service.db is not self.db:
            raise ValueError(
                "authentication rate-limit service must use the product service database"
            )
        if resolved_authentication_rate_limit_service.config is not self.config:
            raise ValueError(
                "authentication rate-limit service must use the product service configuration"
            )
        self.authentication_rate_limit_service = resolved_authentication_rate_limit_service
        resolved_audit_ledger = audit_ledger or AuditLedger(self.db)
        if resolved_audit_ledger.db is not self.db:
            raise ValueError("audit ledger must use the product service database")
        self.audit_ledger = resolved_audit_ledger
        resolved_bootstrap_service = bootstrap_service or BootstrapService(
            database=self.db,
            config=self.config,
            audit_ledger=self.audit_ledger,
            id_factory=lambda prefix: new_id(prefix),
            clock=lambda: utc_now(),
            password_hasher=lambda password: hash_password(password),
            token_comparator=lambda supplied, expected: secrets.compare_digest(
                supplied,
                expected,
            ),
        )
        if resolved_bootstrap_service.db is not self.db:
            raise ValueError("bootstrap service must use the product service database")
        if resolved_bootstrap_service.config is not self.config:
            raise ValueError("bootstrap service must use the product service configuration")
        if resolved_bootstrap_service.audit_ledger is not self.audit_ledger:
            raise ValueError("bootstrap service must use the product service audit ledger")
        self.bootstrap_service = resolved_bootstrap_service
        resolved_user_account_service = user_account_service or UserAccountService(
            database=self.db,
            audit_ledger=self.audit_ledger,
            id_factory=lambda prefix: new_id(prefix),
            clock=lambda: utc_now(),
            password_hasher=lambda password: hash_password(password),
        )
        if resolved_user_account_service.db is not self.db:
            raise ValueError(
                "user account service must use the product service database"
            )
        if resolved_user_account_service.audit_ledger is not self.audit_ledger:
            raise ValueError(
                "user account service must use the product service audit ledger"
            )
        self.user_account_service = resolved_user_account_service
        resolved_workspace_service = workspace_service or WorkspaceService(
            database=self.db,
            audit_ledger=self.audit_ledger,
            id_factory=lambda prefix: new_id(prefix),
            clock=lambda: utc_now(),
        )
        if resolved_workspace_service.db is not self.db:
            raise ValueError(
                "workspace service must use the product service database"
            )
        if resolved_workspace_service.audit_ledger is not self.audit_ledger:
            raise ValueError(
                "workspace service must use the product service audit ledger"
            )
        self.workspace_service = resolved_workspace_service
        resolved_change_request_service = (
            change_request_service
            or ChangeRequestService(
                database=self.db,
                audit_ledger=self.audit_ledger,
                id_factory=lambda prefix: new_id(prefix),
                clock=lambda: utc_now(),
            )
        )
        if resolved_change_request_service.db is not self.db:
            raise ValueError(
                "change request service must use the product service database"
            )
        if resolved_change_request_service.audit_ledger is not self.audit_ledger:
            raise ValueError(
                "change request service must use the product service audit ledger"
            )
        self.change_request_service = resolved_change_request_service
        resolved_operational_safety_service = (
            operational_safety_service
            or OperationalSafetyService(
                database=self.db,
                audit_ledger=self.audit_ledger,
                clock=lambda: utc_now(),
            )
        )
        if resolved_operational_safety_service.db is not self.db:
            raise ValueError(
                "operational safety service must use the product service database"
            )
        if resolved_operational_safety_service.audit_ledger is not self.audit_ledger:
            raise ValueError(
                "operational safety service must use the product service audit ledger"
            )
        self.operational_safety_service = resolved_operational_safety_service
        resolved_receipt_ledger = receipt_ledger or ReceiptLedger(self.db)
        if resolved_receipt_ledger.db is not self.db:
            raise ValueError("receipt ledger must use the product service database")
        self.receipt_ledger = resolved_receipt_ledger
        resolved_execution_service = execution_service or ExecutionService(
            database=self.db,
            config=self.config,
            audit_ledger=self.audit_ledger,
            receipt_ledger=self.receipt_ledger,
            operational_safety_service=self.operational_safety_service,
            adapter_executor=lambda adapter, payload, *, context: execute_adapter(
                adapter,
                payload,
                context=context,
            ),
            id_factory=lambda prefix: new_id(prefix),
            clock=lambda: utc_now(),
            lease_deadline=lambda value, seconds: timestamp_after(value, seconds),
            lease_expired=lambda value, *, now: timestamp_expired(value, now=now),
        )
        if resolved_execution_service.db is not self.db:
            raise ValueError("execution service must use the product service database")
        if resolved_execution_service.config is not self.config:
            raise ValueError("execution service must use the product service configuration")
        if resolved_execution_service.audit_ledger is not self.audit_ledger:
            raise ValueError("execution service must use the product service audit ledger")
        if resolved_execution_service.receipt_ledger is not self.receipt_ledger:
            raise ValueError("execution service must use the product service receipt ledger")
        if (
            resolved_execution_service.operational_safety_service
            is not self.operational_safety_service
        ):
            raise ValueError(
                "execution service must use the product operational safety service"
            )
        self.execution_service = resolved_execution_service
        resolved_platform_status_service = platform_status_service or PlatformStatusService(
            database=self.db,
            config=self.config,
            audit_ledger=self.audit_ledger,
            receipt_ledger=self.receipt_ledger,
            operational_safety_service=self.operational_safety_service,
        )
        if resolved_platform_status_service.db is not self.db:
            raise ValueError("platform status service must use the product service database")
        if resolved_platform_status_service.config is not self.config:
            raise ValueError("platform status service must use the product service configuration")
        if resolved_platform_status_service.audit_ledger is not self.audit_ledger:
            raise ValueError("platform status service must use the product service audit ledger")
        if resolved_platform_status_service.receipt_ledger is not self.receipt_ledger:
            raise ValueError("platform status service must use the product service receipt ledger")
        if (
            resolved_platform_status_service.operational_safety_service
            is not self.operational_safety_service
        ):
            raise ValueError(
                "platform status service must use the product operational safety service"
            )
        self.platform_status_service = resolved_platform_status_service
        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)
        self._dummy_password_hash = hash_password(
            f"VOODOO-invalid-account-{secrets.token_urlsafe(32)}"
        )

    def has_users(self) -> bool:
        return self.bootstrap_service.has_users()

    def bootstrap_admin(self, *, username: str, password: str, token: str) -> dict[str, Any]:
        return self.bootstrap_service.bootstrap_admin(
            username=username,
            password=password,
            token=token,
        )

    def enforce_login_rate_limit(self, *, username: str, source: str) -> None:
        self.authentication_rate_limit_service.enforce_login_rate_limit(
            username=username,
            source=source,
        )

    def record_login_failure(self, *, username: str, source: str) -> None:
        self.authentication_rate_limit_service.record_login_failure(
            username=username,
            source=source,
        )

    def clear_login_rate_limit(self, *, username: str, source: str) -> None:
        self.authentication_rate_limit_service.clear_login_rate_limit(
            username=username,
            source=source,
        )

    def enforce_bootstrap_rate_limit(self, *, source: str) -> None:
        self.authentication_rate_limit_service.enforce_bootstrap_rate_limit(source=source)

    def record_bootstrap_failure(self, *, source: str) -> None:
        self.authentication_rate_limit_service.record_bootstrap_failure(source=source)

    def clear_bootstrap_rate_limit(self, *, source: str) -> None:
        self.authentication_rate_limit_service.clear_bootstrap_rate_limit(source=source)

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

    def get_active_user(self, user_id: str) -> dict[str, Any]:
        return self.user_account_service.get_active_user(user_id)

    def create_user(
        self, *, actor_id: str, username: str, password: str, role: str
    ) -> dict[str, Any]:
        return self.user_account_service.create_user(
            actor_id=actor_id,
            username=username,
            password=password,
            role=role,
        )

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self.workspace_service.list_workspaces()

    def create_workspace(self, *, actor_id: str, name: str, environment: str) -> dict[str, Any]:
        return self.workspace_service.create_workspace(
            actor_id=actor_id,
            name=name,
            environment=environment,
        )

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
        return self.change_request_service.create_change_request(
            actor_id=actor_id,
            workspace_id=workspace_id,
            title=title,
            description=description,
            risk=risk,
            environment=environment,
            adapter=adapter,
            payload=payload,
        )

    def list_change_requests(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.change_request_service.list_change_requests(limit=limit)

    def get_change_request(self, request_id: str) -> dict[str, Any]:
        return self.change_request_service.get_change_request(request_id)

    def submit_change_request(self, *, actor_id: str, request_id: str) -> dict[str, Any]:
        return self.change_request_service.submit_change_request(
            actor_id=actor_id,
            request_id=request_id,
        )

    def approve_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        decision: str,
        reason: str,
    ) -> dict[str, Any]:
        return self.change_request_service.approve_change_request(
            actor_id=actor_id,
            request_id=request_id,
            decision=decision,
            reason=reason,
        )

    def list_approvals(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        return self.change_request_service.list_approvals(pending_only=pending_only)

    def execute_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str | None,
        repository_root: Path,
    ) -> dict[str, Any]:
        return self.execution_service.execute_change_request(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            repository_root=repository_root,
        )

    def recover_execution(
        self,
        *,
        actor_id: str,
        execution_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return self.execution_service.recover_execution(
            actor_id=actor_id,
            execution_id=execution_id,
            reason=reason,
        )

    def list_executions(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.execution_service.list_executions(limit=limit)

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        return self.execution_service.get_execution(execution_id)

    def list_receipts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.receipt_ledger.list_receipts(limit=limit)

    def verify_receipt_chain(self) -> dict[str, Any]:
        return self.receipt_ledger.verify()

    def list_audit_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        return self.audit_ledger.list_events(limit=limit)

    def verify_audit_chain(self) -> dict[str, Any]:
        return self.audit_ledger.verify()

    def command_center(self) -> dict[str, Any]:
        return self.platform_status_service.command_center()

    def set_emergency_stop(self, *, actor_id: str, active: bool, reason: str) -> dict[str, Any]:
        return self.operational_safety_service.set_emergency_stop(
            actor_id=actor_id,
            active=active,
            reason=reason,
        )

    def health(self) -> dict[str, Any]:
        return self.platform_status_service.health()

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
        return self.audit_ledger.append(
            connection,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )

    def _append_receipt(
        self,
        connection: DatabaseConnection,
        *,
        execution_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.receipt_ledger.append(
            connection,
            execution_id=execution_id,
            payload=payload,
        )
