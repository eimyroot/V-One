from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def create_once(path: str, content: str) -> None:
    target = ROOT / path
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing file: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


create_once(
    "voodoo_product/platform_status.py",
    '''from __future__ import annotations

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
''',
)

replace_once(
    "voodoo_product/service.py",
    '''from .operational_safety import OperationalSafetyService
from .persistence import (
    DatabaseConnection,
    DatabaseError,
    DatabaseRow,
    ProductDatabaseAdapter,
)
from .receipt import ReceiptLedger
''',
    '''from .operational_safety import OperationalSafetyService
from .persistence import DatabaseConnection, DatabaseRow, ProductDatabaseAdapter
from .platform_status import PlatformStatusService
from .receipt import ReceiptLedger
''',
)
replace_once(
    "voodoo_product/service.py",
    '''        operational_safety_service: OperationalSafetyService | None = None,
        execution_service: ExecutionService | None = None,
    ) -> None:
''',
    '''        operational_safety_service: OperationalSafetyService | None = None,
        execution_service: ExecutionService | None = None,
        platform_status_service: PlatformStatusService | None = None,
    ) -> None:
''',
)
replace_once(
    "voodoo_product/service.py",
    '''        self.execution_service = resolved_execution_service
        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)
''',
    '''        self.execution_service = resolved_execution_service
        resolved_platform_status_service = platform_status_service or PlatformStatusService(
            database=self.db,
            config=self.config,
            audit_ledger=self.audit_ledger,
            receipt_ledger=self.receipt_ledger,
            operational_safety_service=self.operational_safety_service,
        )
        if resolved_platform_status_service.db is not self.db:
            raise ValueError("platform status service must use the product service database")
        if resolved_platform_status_service.config is not self.config:
            raise ValueError("platform status service must use the product service configuration")
        if resolved_platform_status_service.audit_ledger is not self.audit_ledger:
            raise ValueError("platform status service must use the product service audit ledger")
        if resolved_platform_status_service.receipt_ledger is not self.receipt_ledger:
            raise ValueError("platform status service must use the product service receipt ledger")
        if (
            resolved_platform_status_service.operational_safety_service
            is not self.operational_safety_service
        ):
            raise ValueError(
                "platform status service must use the product operational safety service"
            )
        self.platform_status_service = resolved_platform_status_service
        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)
''',
)
replace_once(
    "voodoo_product/service.py",
    '''    def command_center(self) -> dict[str, Any]:
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
        receipts = self.verify_receipt_chain()
        audit = self.verify_audit_chain()
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
''',
    '''    def command_center(self) -> dict[str, Any]:
        return self.platform_status_service.command_center()
''',
)
replace_once(
    "voodoo_product/service.py",
    '''    def health(self) -> dict[str, Any]:
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
''',
    '''    def health(self) -> dict[str, Any]:
        return self.platform_status_service.health()
''',
)

replace_once(
    "voodoo_product/composition.py",
    '''from .operational_safety import OperationalSafetyService
from .receipt import ReceiptLedger
''',
    '''from .operational_safety import OperationalSafetyService
from .platform_status import PlatformStatusService
from .receipt import ReceiptLedger
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''    operational_safety_service: OperationalSafetyService
    execution_service: ExecutionService
    external_identity_service: GovernedExternalIdentityService
''',
    '''    operational_safety_service: OperationalSafetyService
    execution_service: ExecutionService
    platform_status_service: PlatformStatusService
    external_identity_service: GovernedExternalIdentityService
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''    operational_safety_service = service.operational_safety_service
    execution_service = service.execution_service
    resolved_identity_provider = identity_provider or create_identity_provider(
''',
    '''    operational_safety_service = service.operational_safety_service
    execution_service = service.execution_service
    platform_status_service = service.platform_status_service
    resolved_identity_provider = identity_provider or create_identity_provider(
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''        operational_safety_service=operational_safety_service,
        execution_service=execution_service,
        external_identity_service=external_identity_service,
''',
    '''        operational_safety_service=operational_safety_service,
        execution_service=execution_service,
        platform_status_service=platform_status_service,
        external_identity_service=external_identity_service,
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''    app.state.voodoo_operational_safety_service = operational_safety_service
    app.state.voodoo_execution_service = execution_service
    app.state.voodoo_external_identity_service = external_identity_service
''',
    '''    app.state.voodoo_operational_safety_service = operational_safety_service
    app.state.voodoo_execution_service = execution_service
    app.state.voodoo_platform_status_service = platform_status_service
    app.state.voodoo_external_identity_service = external_identity_service
''',
)

replace_once(
    "tests/system/test_statement_catalog.py",
    "    assert len(execute_calls) == 15\n",
    "    assert len(execute_calls) == 11\n",
)

replace_once(
    "scripts/product_readiness_gate.py",
    '''    "voodoo_product/operational_safety.py",
    "voodoo_product/persistence.py",
''',
    '''    "voodoo_product/operational_safety.py",
    "voodoo_product/persistence.py",
    "voodoo_product/platform_status.py",
''',
)
replace_once(
    "scripts/product_readiness_gate.py",
    '''    "tests/system/test_operational_safety.py",
    "tests/system/test_persistence_boundary.py",
''',
    '''    "tests/system/test_operational_safety.py",
    "tests/system/test_persistence_boundary.py",
    "tests/system/test_platform_status_service.py",
''',
)
replace_once(
    "scripts/product_readiness_gate.py",
    '''    "docs/product/OPERATIONAL_SAFETY_COMPOSITION_BOUNDARY.md",
    "docs/product/PERSISTENCE_BOUNDARY.md",
''',
    '''    "docs/product/OPERATIONAL_SAFETY_COMPOSITION_BOUNDARY.md",
    "docs/product/PERSISTENCE_BOUNDARY.md",
    "docs/product/PLATFORM_STATUS_SERVICE_COMPOSITION_BOUNDARY.md",
''',
)

create_once(
    "tests/system/test_platform_status_service.py",
    '''from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.persistence import DatabaseError
from voodoo_product.platform_status import PlatformStatusService
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_platform_status_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "platform_status.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 4
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_service_delegates_platform_status_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef) and node.name in {"command_center", "health"}
    }

    assert set(methods) == {"command_center", "health"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.platform_status_service.command_center" in source_text
    assert "self.platform_status_service.health" in source_text
    assert "sql.COUNT_CHANGE_REQUESTS_BY_STATUS" not in source_text
    assert "sql.COUNT_EXECUTIONS_BY_STATUS" not in source_text
    assert "sql.COUNT_CHANGE_REQUESTS_BY_RISK" not in source_text
    assert "sql.HEALTH_CHECK" not in source_text


def test_platform_status_service_rejects_cross_database_dependencies(tmp_path: Path) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="platform status audit ledger must use its database"):
        PlatformStatusService(
            database=first.db,
            config=first.config,
            audit_ledger=second.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
        )
    with pytest.raises(ValueError, match="platform status receipt ledger must use its database"):
        PlatformStatusService(
            database=first.db,
            config=first.config,
            audit_ledger=first.audit_ledger,
            receipt_ledger=second.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
        )


def test_product_service_rejects_platform_status_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="platform status service must use the product service database",
    ):
        ProductService(
            first.config,
            database=first.db,
            audit_ledger=first.audit_ledger,
            user_account_service=first.user_account_service,
            workspace_service=first.workspace_service,
            change_request_service=first.change_request_service,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
            execution_service=first.execution_service,
            platform_status_service=second.platform_status_service,
        )


def test_platform_status_service_preserves_command_center_and_health_contract(
    tmp_path: Path,
) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )

    command_center = service.command_center()
    assert command_center["trust_state"] == "HEALTHY"
    assert command_center["emergency_stop"] is False
    assert command_center["change_requests"] == {}
    assert command_center["executions"] == {}
    assert command_center["risk"] == {}
    assert command_center["pending_approvals"] == 0
    assert command_center["receipt_integrity"]["valid"] is True
    assert command_center["audit_integrity"]["valid"] is True
    assert command_center["production_effects_enabled"] is False
    assert command_center["environment"] == "test"

    health = service.health()
    assert health["status"] == "HEALTHY"
    assert health["database"] == "HEALTHY"
    assert health["database_backend"] == service.db.backend_name
    assert health["schema_version"] == service.db.schema_version()
    assert health["evidence_integrity"] == "NOT_CHECKED_BY_LIVENESS"
    assert health["production_effects"] == "DISABLED"

    service.set_emergency_stop(
        actor_id=str(bootstrap["user_id"]),
        active=True,
        reason="Governed platform status boundary test",
    )
    assert service.command_center()["trust_state"] == "INCIDENT"
    assert service.command_center()["emergency_stop"] is True
    assert service.health()["status"] == "EMERGENCY_STOP"


def test_platform_status_service_preserves_unavailable_health_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ProductService(product_config(tmp_path))

    def unavailable_connect() -> None:
        raise DatabaseError("database unavailable")

    monkeypatch.setattr(service.platform_status_service.db, "connect", unavailable_connect)
    assert service.health() == {
        "status": "UNAVAILABLE",
        "database": "UNAVAILABLE",
        "database_backend": service.db.backend_name,
    }


def test_composition_exposes_shared_platform_status_service(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert app.state.voodoo_platform_status_service is composition.platform_status_service
    assert composition.service.platform_status_service is composition.platform_status_service
    assert composition.platform_status_service.db is composition.service.db
    assert composition.platform_status_service.config is composition.service.config
    assert composition.platform_status_service.audit_ledger is composition.audit_ledger
    assert composition.platform_status_service.receipt_ledger is composition.receipt_ledger
    assert (
        composition.platform_status_service.operational_safety_service
        is composition.operational_safety_service
    )
''',
)

create_once(
    "docs/product/PLATFORM_STATUS_SERVICE_COMPOSITION_BOUNDARY.md",
    '''# Platform Status Service Composition Boundary

## Status

Implemented as the canonical read-only command-center and liveness projection boundary.

## Purpose

`PlatformStatusService` owns operational aggregate reads for the command center and the lightweight database liveness projection. `ProductService` preserves the existing public method surface while delegating `command_center` and `health`.

## Runtime composition

`install_composed_product_platform` exposes one shared platform status service through `ProductComposition` and `app.state.voodoo_platform_status_service`.

The service uses the exact product database, configuration, audit ledger, receipt ledger and operational-safety service instances. Composition mismatches fail closed.

## Preserved invariants

- command-center change-request, execution and risk aggregates use the central statement catalog;
- emergency-stop state is read through the shared operational-safety boundary;
- command-center trust state remains incident-driven by emergency stop or invalid evidence chains;
- receipt and audit verification continue through the shared canonical ledgers;
- liveness performs only the existing lightweight database probe and emergency-stop read;
- liveness continues to report evidence integrity as not checked;
- database failures preserve the existing `UNAVAILABLE` response shape;
- existing method signatures, routes, status codes, fields and ordering remain unchanged.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, modify bootstrap, authentication, change-request or execution behavior, enable external sign-in, release, deploy or enable production effects.
''',
)
