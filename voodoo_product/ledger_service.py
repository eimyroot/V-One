from __future__ import annotations

from typing import Any

from .audit import AuditLedger, AuditLedgerWriter
from .config import ProductConfig
from .persistence import DatabaseConnection, ProductDatabaseAdapter
from .service import ProductService


class LedgerBackedProductService(ProductService):
    """Product service whose audit surface delegates to one reusable ledger."""

    def __init__(
        self,
        config: ProductConfig,
        *,
        database: ProductDatabaseAdapter | None = None,
        audit_ledger: AuditLedger | None = None,
    ) -> None:
        super().__init__(config, database=database)
        resolved_ledger = audit_ledger or AuditLedger(self.db)
        if resolved_ledger.db is not self.db:
            raise ValueError("audit ledger must use the product service database")
        self.audit_ledger: AuditLedgerWriter & AuditLedger = resolved_ledger

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

    def list_audit_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        return self.audit_ledger.list_events(limit=limit)

    def verify_audit_chain(self) -> dict[str, Any]:
        return self.audit_ledger.verify()
