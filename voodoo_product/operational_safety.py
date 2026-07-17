from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import utc_now
from .persistence import DatabaseConnection, ProductDatabaseAdapter

Clock = Callable[[], str]


class OperationalSafetyService:
    """Shared emergency-stop state and audited transition boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        clock: Clock = utc_now,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("operational safety audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._clock = clock

    def is_active(self, connection: DatabaseConnection | None = None) -> bool:
        if connection is not None:
            return self._read(connection)
        with self.db.connect() as resolved_connection:
            return self._read(resolved_connection)

    def set_emergency_stop(
        self,
        *,
        actor_id: str,
        active: bool,
        reason: str,
    ) -> dict[str, Any]:
        with self.db.transaction() as connection:
            now = self._clock()
            connection.execute(
                sql.UPSERT_EMERGENCY_STOP,
                ("true" if active else "false", actor_id, now),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action=(
                    "system.emergency_stop.activate"
                    if active
                    else "system.emergency_stop.clear"
                ),
                target_type="system",
                target_id="runtime",
                payload={"reason": reason},
            )
        return {"emergency_stop": active, "reason": reason, "updated_at": now}

    @staticmethod
    def _read(connection: DatabaseConnection) -> bool:
        row = connection.execute(sql.SELECT_EMERGENCY_STOP).fetchone()
        return bool(row and str(row["value"]).lower() == "true")
