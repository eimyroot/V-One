from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedgerWriter
from .config import ProductConfig
from .persistence import ProductDatabaseAdapter
from .workspace import INSERT_WORKSPACE_MEMBERSHIP, WORKSPACE_OWNER

VALID_BOOTSTRAP_ENVIRONMENTS = {"local", "development", "staging", "production"}


class BootstrapService:
    """Own the one-time, atomic first-administrator provisioning workflow."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        config: ProductConfig,
        audit_ledger: AuditLedgerWriter,
        id_factory: Callable[[str], str],
        clock: Callable[[], str],
        password_hasher: Callable[[str], str],
        token_comparator: Callable[[str, str], bool] = secrets.compare_digest,
    ) -> None:
        self.db = database
        self.config = config
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock
        self._password_hasher = password_hasher
        self._token_comparator = token_comparator

    def has_users(self) -> bool:
        with self.db.connect() as connection:
            row = connection.execute(sql.COUNT_USERS).fetchone()
        return bool(row and int(row["count"]) > 0)

    def bootstrap_admin(self, *, username: str, password: str, token: str) -> dict[str, Any]:
        if not self._token_comparator(token, self.config.bootstrap_token):
            raise PermissionError("invalid bootstrap token")

        with self.db.transaction() as connection:
            count = connection.execute(sql.COUNT_USERS).fetchone()
            if count and int(count["count"]) > 0:
                raise RuntimeError("bootstrap is already closed")

            user_id = self._id_factory("usr")
            workspace_id = self._id_factory("wrk")
            workspace_environment = (
                self.config.environment
                if self.config.environment in VALID_BOOTSTRAP_ENVIRONMENTS
                else "local"
            )
            now = self._clock()

            connection.execute(
                sql.INSERT_USER,
                (
                    user_id,
                    username.strip(),
                    self._password_hasher(password),
                    "administrator",
                    now,
                ),
            )
            connection.execute(
                sql.INSERT_WORKSPACE,
                (
                    workspace_id,
                    f"VOODOO {workspace_environment.title()}",
                    workspace_environment,
                    now,
                ),
            )
            connection.execute(
                INSERT_WORKSPACE_MEMBERSHIP,
                (workspace_id, user_id, WORKSPACE_OWNER, user_id, now),
            )
            self.audit_ledger.append(
                connection,
                actor_id=user_id,
                action="system.bootstrap",
                target_type="workspace",
                target_id=workspace_id,
                payload={
                    "username": username,
                    "role": "administrator",
                    "workspace_environment": workspace_environment,
                    "workspace_membership_role": WORKSPACE_OWNER,
                },
            )

            return {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "workspace_environment": workspace_environment,
                "role": "administrator",
            }
