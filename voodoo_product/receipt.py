from __future__ import annotations

import json
from typing import Any

from . import statements as sql
from .evidence_primitives import canonical_json, chained_hash, new_id, utc_now
from .persistence import DatabaseConnection, ProductDatabaseAdapter


class ReceiptLedger:
    """Reusable writer, reader, and verifier for the execution receipt hash chain."""

    def __init__(self, database: ProductDatabaseAdapter) -> None:
        self.db = database

    def append(
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

    def list_receipts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_RECEIPTS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode(dict(row)) for row in rows]

    def verify(self) -> dict[str, Any]:
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
            previous_hash = str(row["receipt_hash"])
        return {"valid": True, "count": len(rows), "head": previous_hash}

    @staticmethod
    def _decode(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value
