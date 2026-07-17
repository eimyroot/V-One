from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.execution import ExecutionService
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]
EXECUTION_STATEMENTS = {
    "SELECT_EXECUTION_BY_IDEMPOTENCY_KEY",
    "SELECT_CHANGE_REQUEST_FOR_EXECUTION",
    "INSERT_EXECUTION",
    "MARK_CHANGE_REQUEST_RUNNING",
    "COMPLETE_EXECUTION",
    "MARK_CHANGE_REQUEST_COMPLETED",
    "SELECT_EXECUTION_FOR_RECOVERY",
    "INTERRUPT_EXECUTION",
    "LIST_EXECUTIONS",
    "GET_EXECUTION",
}


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_execution_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "execution.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 11
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_service_delegates_complete_execution_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "execute_change_request",
            "recover_execution",
            "list_executions",
            "get_execution",
        }
    }

    assert set(methods) == {
        "execute_change_request",
        "recover_execution",
        "list_executions",
        "get_execution",
    }
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.execution_service.execute_change_request" in source_text
    assert "self.execution_service.recover_execution" in source_text
    assert "self.execution_service.list_executions" in source_text
    assert "self.execution_service.get_execution" in source_text
    for statement in EXECUTION_STATEMENTS:
        assert f"sql.{statement}" not in source_text
    assert "sql.SELECT_EMERGENCY_STOP" not in source_text


def test_execution_service_rejects_evidence_ledgers_from_other_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="execution service audit ledger must use its database",
    ):
        ExecutionService(
            database=first.db,
            config=first.config,
            audit_ledger=second.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
        )

    with pytest.raises(
        ValueError,
        match="execution service receipt ledger must use its database",
    ):
        ExecutionService(
            database=first.db,
            config=first.config,
            audit_ledger=first.audit_ledger,
            receipt_ledger=second.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
        )


def test_product_service_rejects_execution_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="execution service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            execution_service=second.execution_service,
        )


def test_execution_service_preserves_product_service_contract(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    operator = service.create_user(
        actor_id=bootstrap["user_id"],
        username="operator",
        password="VeryStrongOperatorPassword1!",
        role="operator",
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Execution service compatibility",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"value": 1},
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="execution service compatibility test",
    )

    execution = service.execute_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        idempotency_key="execution-service-compatibility",
        repository_root=tmp_path,
    )

    assert service.get_execution(execution["id"]) == service.execution_service.get_execution(
        execution["id"]
    )
    assert service.list_executions() == service.execution_service.list_executions()
    assert execution["status"] == "SUCCEEDED"
    assert service.verify_receipt_chain()["valid"] is True
    assert service.verify_audit_chain()["valid"] is True
