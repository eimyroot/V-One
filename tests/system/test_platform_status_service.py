from __future__ import annotations

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
