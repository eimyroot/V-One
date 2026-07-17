from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.change_request import ChangeRequestService
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]
CHANGE_REQUEST_STATEMENTS = {
    "SELECT_WORKSPACE_CONTEXT",
    "INSERT_CHANGE_REQUEST",
    "LIST_CHANGE_REQUESTS",
    "GET_CHANGE_REQUEST",
    "SELECT_CHANGE_REQUEST_STATUS",
    "MARK_CHANGE_REQUEST_SUBMITTED",
    "SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT",
    "INSERT_APPROVAL",
    "COUNT_APPROVED",
    "UPDATE_CHANGE_REQUEST_STATUS",
    "LIST_PENDING_APPROVALS",
    "LIST_APPROVALS",
}


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_change_request_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "change_request.py"
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
        and (
            isinstance(call.args[0], (ast.Attribute, ast.IfExp))
        )
        for call in execute_calls
    )


def test_product_service_delegates_complete_change_request_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    method_names = {
        "create_change_request",
        "list_change_requests",
        "get_change_request",
        "submit_change_request",
        "approve_change_request",
        "list_approvals",
    }
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef) and node.name in method_names
    }

    assert set(methods) == method_names
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    for statement in CHANGE_REQUEST_STATEMENTS:
        assert f"sql.{statement}" not in source_text
    assert "self.change_request_service.create_change_request" in source_text
    assert "self.change_request_service.approve_change_request" in source_text


def test_change_request_service_rejects_audit_ledger_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="change request audit ledger must use its database"):
        ChangeRequestService(database=first.db, audit_ledger=second.audit_ledger)


def test_product_service_rejects_change_request_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="change request service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            change_request_service=second.change_request_service,
        )


def test_change_request_service_preserves_product_service_contract(tmp_path: Path) -> None:
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
        title="Change request service compatibility",
        description="preserve public contract",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"value": 1},
    )

    assert service.get_change_request(request["id"]) == request
    assert service.list_change_requests() == service.change_request_service.list_change_requests()
    submitted = service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    assert submitted["status"] == "REVIEW_REQUIRED"
    approved = service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="approved",
        reason="independent review complete",
    )
    assert approved["status"] == "APPROVED"
    assert service.list_approvals() == service.change_request_service.list_approvals()
    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "change_request.create" in actions
    assert "change_request.submit" in actions
    assert "change_request.approved" in actions
    assert service.verify_audit_chain()["valid"] is True


def test_change_request_service_preserves_service_monkeypatch_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_new_id = service_module.new_id

    def controlled_new_id(prefix: str) -> str:
        return "cr_controlled" if prefix == "cr" else original_new_id(prefix)

    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "utc_now", lambda: "2026-07-17T12:00:00.000+00:00")
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Controlled identity",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={},
    )

    assert request["id"] == "cr_controlled"
    assert request["created_at"] == "2026-07-17T12:00:00.000+00:00"


def test_composition_exposes_shared_change_request_service(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert app.state.voodoo_change_request_service is composition.change_request_service
    assert composition.service.change_request_service is composition.change_request_service
    assert composition.change_request_service.db is composition.service.db
    assert composition.change_request_service.audit_ledger is composition.audit_ledger
