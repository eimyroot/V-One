from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import new_id, utc_now
from .persistence import ProductDatabaseAdapter

IdFactory = Callable[[str], str]
Clock = Callable[[], str]

VALID_ENVIRONMENTS = {"local", "development", "staging", "production"}


class WorkspaceService:
    """Database-bound workspace lifecycle boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("workspace audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock

    def list_workspaces(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_WORKSPACES).fetchall()
        return [dict(row) for row in rows]

    def create_workspace(
        self,
        *,
        actor_id: str,
        name: str,
        environment: str,
    ) -> dict[str, Any]:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        workspace_id = self._id_factory("wrk")
        now = self._clock()
        with self.db.transaction() as connection:
            connection.execute(
                sql.INSERT_WORKSPACE,
                (workspace_id, name.strip(), environment, now),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="workspace.create",
                target_type="workspace",
                target_id=workspace_id,
                payload={"name": name, "environment": environment},
            )
        return {
            "id": workspace_id,
            "name": name,
            "environment": environment,
            "created_at": now,
        }
