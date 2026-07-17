from __future__ import annotations

from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .config import ProductConfig
from .operational_safety import OperationalSafetyService
from .persistence import DatabaseError, ProductDatabaseAdapter
from .receipt import ReceiptLedger


class PlatformStatusService:
    """Read-only command-center and liveness projection boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        config: ProductConfig,
        audit_ledger: AuditLedger,
        receipt_ledger: ReceiptLedger,
        operational_safety_service: OperationalSafetyService,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("platform status audit ledger must use its database")
        if receipt_ledger.db is not database:
            raise ValueError("platform status receipt ledger must use its database")
        if operational_safety_service.db is not database:
            raise ValueError("platform status safety service must use its database")
        if operational_safety_service.audit_ledger is not audit_ledger:
            raise ValueError("platform status safety service must use its audit ledger")
        self.db = database
        self.config = config
        self.audit_ledger = audit_ledger
        self.receipt_ledger = receipt_ledger
        self.operational_safety_service = operational_safety_service

    def command_center(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            statuses = {
                row["status"]: row["count"]
                for row in connection.execute(sql.COUNT_CHANGE_REQUESTS_BY_STATUS).fetchall()
            }
            executions = {
                row["status"]: row["count"]
                for row in connection.execute(sql.COUNT_EXECUTIONS_BY_STATUS).fetchall()
            }
            risks = {
                row["risk"]: row["count"]
                for row in connection.execute(sql.COUNT_CHANGE_REQUESTS_BY_RISK).fetchall()
            }
            stop = self.operational_safety_service.is_active(connection)
        receipts = self.receipt_ledger.verify()
        audit = self.audit_ledger.verify()
        health = "INCIDENT" if stop or not receipts["valid"] or not audit["valid"] else "HEALTHY"
        return {
            "trust_state": health,
            "emergency_stop": stop,
            "change_requests": statuses,
            "executions": executions,
            "risk": risks,
            "pending_approvals": statuses.get("REVIEW_REQUIRED", 0),
            "receipt_integrity": receipts,
            "audit_integrity": audit,
            "production_effects_enabled": self.config.production_effects_enabled,
            "environment": self.config.environment,
        }

    def health(self) -> dict[str, Any]:
        try:
            with self.db.connect() as connection:
                connection.execute(sql.HEALTH_CHECK).fetchone()
                stop = self.operational_safety_service.is_active(connection)
            return {
                "status": "EMERGENCY_STOP" if stop else "HEALTHY",
                "database": "HEALTHY",
                "database_backend": self.db.backend_name,
                "schema_version": self.db.schema_version(),
                "evidence_integrity": "NOT_CHECKED_BY_LIVENESS",
                "production_effects": "ENABLED"
                if self.config.production_effects_enabled
                else "DISABLED",
            }
        except DatabaseError:
            return {
                "status": "UNAVAILABLE",
                "database": "UNAVAILABLE",
                "database_backend": self.db.backend_name,
            }
