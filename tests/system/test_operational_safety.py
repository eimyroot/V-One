from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.execution import ExecutionService
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


def test_operational_safety_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "operational_safety.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 2
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_and_execution_services_delegate_emergency_stop_sql() -> None:
    product_source = (ROOT / "voodoo_product" / "service.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "voodoo_product" / "execution.py").read_text(
        encoding="utf-8"
    )
    platform_status_source = (ROOT / "voodoo_product" / "platform_status.py").read_text(
        encoding="utf-8"
    )

    assert "sql.SELECT_EMERGENCY_STOP" not in product_source
    assert "sql.UPSERT_EMERGENCY_STOP" not in product_source
    assert "sql.SELECT_EMERGENCY_STOP" not in execution_source
    assert "self.operational_safety_service.set_emergency_stop" in product_source
    assert "self.operational_safety_service.is_active" not in product_source
    assert "self.operational_safety_service.is_active" in platform_status_source
    assert "self.operational_safety_service.is_active" in execution_source


def test_product_service_rejects_operational_safety_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="operational safety service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=second.operational_safety_service,
        )


def test_execution_service_rejects_operational_safety_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="execution operational safety service must use its database",
    ):
        ExecutionService(
            database=first.db,
            config=first.config,
            audit_ledger=first.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=second.operational_safety_service,
        )


def test_operational_safety_preserves_product_service_contract(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )

    assert service.operational_safety_service.is_active() is False
    activated = service.set_emergency_stop(
        actor_id=bootstrap["user_id"],
        active=True,
        reason="incident containment",
    )
    assert activated["emergency_stop"] is True
    assert activated["reason"] == "incident containment"
    assert service.operational_safety_service.is_active() is True
    assert service.health()["status"] == "EMERGENCY_STOP"
    assert service.command_center()["emergency_stop"] is True

    cleared = service.set_emergency_stop(
        actor_id=bootstrap["user_id"],
        active=False,
        reason="incident resolved",
    )
    assert cleared["emergency_stop"] is False
    assert service.operational_safety_service.is_active() is False
    assert service.health()["status"] == "HEALTHY"

    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "system.emergency_stop.activate" in actions
    assert "system.emergency_stop.clear" in actions
    assert service.verify_audit_chain()["valid"] is True
