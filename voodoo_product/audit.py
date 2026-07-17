from __future__ import annotations

import json
from typing import Any, Protocol

from . import statements as sql
from .evidence_primitives import canonical_json, chained_hash, new_id, utc_now
from .persistence import DatabaseConnection, ProductDatabaseAdapter


class AuditLedgerWriter(Protocol):
    def append(
        self,
        connection: DatabaseConnection,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...


class AuditLedger:
    """Reusable writer and verifier for the product audit hash chain."""

    def __init__(self, database: ProductDatabaseAdapter) -> None:
        self.db = database

    def append(
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

    def list_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_AUDIT_EVENTS,
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [self._decode(dict(row)) for row in rows]

    def verify(self) -> dict[str, Any]:
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
                return {
                    "valid": False,
                    "sequence": row["sequence"],
                    "event_id": row["id"],
                }
            previous_hash = str(row["event_hash"])
        return {"valid": True, "count": len(rows), "head": previous_hash}

    @staticmethod
    def _decode(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value
