from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.evidence_primitives import chained_hash
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


def test_receipt_ledger_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "receipt.py"
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


def test_product_service_delegates_complete_receipt_surface() -> None:
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
        and node.name in {"_append_receipt", "list_receipts", "verify_receipt_chain"}
    }

    assert set(methods) == {"_append_receipt", "list_receipts", "verify_receipt_chain"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.receipt_ledger.append" in source_text
    assert "self.receipt_ledger.list_receipts" in source_text
    assert "self.receipt_ledger.verify" in source_text
    assert "sql.SELECT_RECEIPT_HEAD" not in source_text
    assert "sql.INSERT_RECEIPT" not in source_text
    assert "sql.LIST_RECEIPTS" not in source_text
    assert "sql.LIST_RECEIPTS_FOR_VERIFICATION" not in source_text


def test_product_service_rejects_receipt_ledger_from_another_database(tmp_path: Path) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="receipt ledger must use the product service database"):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            receipt_ledger=second.receipt_ledger,
        )


def test_receipt_ledger_preserves_service_contract_and_hash_format(tmp_path: Path) -> None:
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
        title="Receipt ledger compatibility",
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
        reason="receipt ledger compatibility test",
    )
    execution = service.execute_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        idempotency_key="receipt-ledger-compatibility",
        repository_root=tmp_path,
    )

    receipts = service.list_receipts()
    assert receipts == service.receipt_ledger.list_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["execution_id"] == execution["id"]
    assert receipt["previous_hash"] == "GENESIS"
    assert receipt["receipt_hash"] == chained_hash(receipt["previous_hash"], receipt["payload"])
    assert service.verify_receipt_chain() == service.receipt_ledger.verify()
    assert service.verify_receipt_chain() == {
        "valid": True,
        "count": 1,
        "head": receipt["receipt_hash"],
    }
