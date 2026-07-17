from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import new_id, utc_now
from .persistence import DatabaseIntegrityError, ProductDatabaseAdapter
from .security import hash_password

IdFactory = Callable[[str], str]
Clock = Callable[[], str]
PasswordHasher = Callable[[str], str]

VALID_ROLES = {
    "viewer",
    "developer",
    "operator",
    "security_reviewer",
    "auditor",
    "administrator",
}


class UserAccountService:
    """Database-bound active-user lookup and ordinary user creation boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
        password_hasher: PasswordHasher = hash_password,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("user account audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock
        self._password_hasher = password_hasher

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
        self,
        *,
        actor_id: str,
        username: str,
        password: str,
        role: str,
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise ValueError("unknown role")
        user_id = self._id_factory("usr")
        now = self._clock()
        with self.db.transaction() as connection:
            try:
                connection.execute(
                    sql.INSERT_USER,
                    (
                        user_id,
                        username.strip(),
                        self._password_hasher(password),
                        role,
                        now,
                    ),
                )
            except DatabaseIntegrityError as exc:
                raise ValueError("username already exists") from exc
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="user.create",
                target_type="user",
                target_id=user_id,
                payload={"username": username, "role": role},
            )
        return {
            "id": user_id,
            "username": username,
            "role": role,
            "active": True,
        }
