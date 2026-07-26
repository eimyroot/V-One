from __future__ import annotations

import re
import time
from collections.abc import Callable

from . import statements as sql
from .audit import AuditLedger
from .persistence import DatabaseIntegrityError, ProductDatabaseAdapter

Clock = Callable[[], float]
SessionReferenceFactory = Callable[[str], str]

_SESSION_REFERENCE_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SessionLifecycleService:
    """Own the persistent allowlist and revocation of local bearer sessions."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        session_reference_factory: SessionReferenceFactory,
        clock: Clock = time.time,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("session lifecycle audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._session_reference_factory = session_reference_factory
        self._clock = clock

    def register_session(
        self,
        *,
        session_id: str,
        user_id: str,
        issued_at: int,
        expires_at: int,
    ) -> None:
        if expires_at <= issued_at:
            raise ValueError("session lifetime is invalid")
        reference = self._reference(session_id)
        now = int(self._clock())
        with self.db.transaction() as connection:
            connection.execute(sql.DELETE_EXPIRED_ACTIVE_SESSIONS, (now,))
            try:
                connection.execute(
                    sql.INSERT_ACTIVE_SESSION,
                    (reference, user_id, issued_at, expires_at),
                )
            except DatabaseIntegrityError as exc:
                raise RuntimeError("session registration failed") from exc
            self.audit_ledger.append(
                connection,
                actor_id=user_id,
                action="session.issue",
                target_type="session",
                target_id=reference,
                payload={"expires_at": expires_at, "provider": "local"},
            )

    def require_active_session(
        self,
        *,
        session_id: str,
        user_id: str,
        issued_at: int,
        expires_at: int,
    ) -> None:
        reference = self._reference(session_id)
        now = int(self._clock())
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_ACTIVE_SESSION,
                (reference, now),
            ).fetchone()
        if (
            row is None
            or str(row["user_id"]) != user_id
            or int(row["issued_at"]) != issued_at
            or int(row["expires_at"]) != expires_at
        ):
            raise PermissionError("authentication session is inactive")

    def revoke_session(
        self,
        *,
        session_id: str,
        user_id: str,
        actor_id: str,
        reason: str,
    ) -> None:
        if actor_id != user_id:
            raise PermissionError("session owner mismatch")
        normalized_reason = reason.strip()
        if not 3 <= len(normalized_reason) <= 200:
            raise ValueError("session revocation reason is invalid")
        reference = self._reference(session_id)
        with self.db.transaction() as connection:
            removed = connection.execute(
                sql.DELETE_ACTIVE_SESSION,
                (reference, user_id),
            ).fetchone()
            if removed is None:
                raise PermissionError("authentication session is inactive")
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="session.revoke",
                target_type="session",
                target_id=reference,
                payload={"reason": normalized_reason},
            )

    def revoke_all_sessions(
        self,
        *,
        user_id: str,
        actor_id: str,
        reason: str,
    ) -> int:
        if not 1 <= len(user_id) <= 128 or not 1 <= len(actor_id) <= 128:
            raise ValueError("session revocation identity is invalid")
        normalized_reason = reason.strip()
        if not 3 <= len(normalized_reason) <= 200:
            raise ValueError("session revocation reason is invalid")
        with self.db.transaction() as connection:
            target = connection.execute(sql.SELECT_USER_BY_ID, (user_id,)).fetchone()
            if target is None:
                raise LookupError("user not found")
            removed = connection.execute(
                sql.DELETE_ACTIVE_SESSIONS_FOR_USER,
                (user_id,),
            ).fetchall()
            revoked_count = len(removed)
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="session.revoke_all",
                target_type="user",
                target_id=user_id,
                payload={"reason": normalized_reason, "revoked_count": revoked_count},
            )
        return revoked_count

    def _reference(self, session_id: str) -> str:
        reference = self._session_reference_factory(session_id)
        if _SESSION_REFERENCE_PATTERN.fullmatch(reference) is None:
            raise ValueError("session reference is invalid")
        return reference
