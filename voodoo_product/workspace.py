from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from . import statements as sql
from . import workspace_membership_statements as membership_sql
from .audit import AuditLedger
from .evidence_primitives import new_id, utc_now
from .persistence import DatabaseConnection, ProductDatabaseAdapter

IdFactory = Callable[[str], str]
Clock = Callable[[], str]

VALID_ENVIRONMENTS = {"local", "development", "staging", "production"}
WORKSPACE_OWNER: Final = "owner"
WORKSPACE_MEMBER: Final = "member"


class WorkspaceService:
    """Database-bound workspace lifecycle and membership boundary."""

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
            actor = connection.execute(sql.SELECT_ACTIVE_USER, (actor_id,)).fetchone()
            if actor is None or not int(actor["active"]):
                raise PermissionError("workspace creator must be an active user")
            connection.execute(
                sql.INSERT_WORKSPACE,
                (workspace_id, name.strip(), environment, now),
            )
            connection.execute(
                membership_sql.INSERT_WORKSPACE_MEMBERSHIP,
                (workspace_id, actor_id, WORKSPACE_OWNER, actor_id, now),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="workspace.create",
                target_type="workspace",
                target_id=workspace_id,
                payload={"name": name, "environment": environment},
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="workspace.member.add",
                target_type="workspace_membership",
                target_id=f"{workspace_id}:{actor_id}",
                payload={
                    "workspace_id": workspace_id,
                    "user_id": actor_id,
                    "membership_role": WORKSPACE_OWNER,
                },
            )
        return {
            "id": workspace_id,
            "name": name,
            "environment": environment,
            "created_at": now,
        }

    def _require_membership_manager(
        self,
        connection: DatabaseConnection,
        *,
        actor_id: str,
        workspace_id: str,
    ) -> None:
        actor = connection.execute(sql.SELECT_ACTIVE_USER, (actor_id,)).fetchone()
        if actor is None or not int(actor["active"]):
            raise PermissionError("workspace membership actor must be active")
        membership = connection.execute(
            membership_sql.SELECT_WORKSPACE_MEMBERSHIP,
            (workspace_id, actor_id),
        ).fetchone()
        if str(actor["role"]) == "administrator":
            return
        if membership is None or str(membership["membership_role"]) != WORKSPACE_OWNER:
            raise PermissionError("workspace membership changes require owner or administrator")

    def add_member(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        user_id: str,
        membership_role: str = WORKSPACE_MEMBER,
    ) -> dict[str, Any]:
        if membership_role not in {WORKSPACE_OWNER, WORKSPACE_MEMBER}:
            raise ValueError("unknown workspace membership role")
        now = self._clock()
        with self.db.transaction() as connection:
            workspace = connection.execute(
                sql.SELECT_WORKSPACE_CONTEXT,
                (workspace_id,),
            ).fetchone()
            if workspace is None:
                raise LookupError("workspace not found")
            self._require_membership_manager(
                connection,
                actor_id=actor_id,
                workspace_id=workspace_id,
            )
            user = connection.execute(sql.SELECT_ACTIVE_USER, (user_id,)).fetchone()
            if user is None or not int(user["active"]):
                raise PermissionError("workspace member must be an active user")
            existing = connection.execute(
                membership_sql.SELECT_WORKSPACE_MEMBERSHIP,
                (workspace_id, user_id),
            ).fetchone()
            if existing is not None:
                raise ValueError("workspace membership already exists")
            connection.execute(
                membership_sql.INSERT_WORKSPACE_MEMBERSHIP,
                (workspace_id, user_id, membership_role, actor_id, now),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="workspace.member.add",
                target_type="workspace_membership",
                target_id=f"{workspace_id}:{user_id}",
                payload={
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "membership_role": membership_role,
                },
            )
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "membership_role": membership_role,
            "created_by": actor_id,
            "created_at": now,
        }

    def remove_member(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        user_id: str,
    ) -> None:
        with self.db.transaction() as connection:
            self._require_membership_manager(
                connection,
                actor_id=actor_id,
                workspace_id=workspace_id,
            )
            membership = connection.execute(
                membership_sql.SELECT_WORKSPACE_MEMBERSHIP,
                (workspace_id, user_id),
            ).fetchone()
            if membership is None:
                raise LookupError("workspace membership not found")
            if str(membership["membership_role"]) == WORKSPACE_OWNER:
                owner_count = connection.execute(
                    membership_sql.COUNT_WORKSPACE_OWNERS,
                    (workspace_id,),
                ).fetchone()
                if owner_count is None or int(owner_count["count"]) <= 1:
                    raise PermissionError("cannot remove the last workspace owner")
            deleted = connection.execute(
                membership_sql.DELETE_WORKSPACE_MEMBERSHIP,
                (workspace_id, user_id),
            ).fetchone()
            if deleted is None:
                raise LookupError("workspace membership not found")
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="workspace.member.remove",
                target_type="workspace_membership",
                target_id=f"{workspace_id}:{user_id}",
                payload={"workspace_id": workspace_id, "user_id": user_id},
            )

    def list_members(self, *, workspace_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            workspace = connection.execute(
                sql.SELECT_WORKSPACE_CONTEXT,
                (workspace_id,),
            ).fetchone()
            if workspace is None:
                raise LookupError("workspace not found")
            rows = connection.execute(
                membership_sql.LIST_WORKSPACE_MEMBERS,
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]
