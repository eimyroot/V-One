from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi import FastAPI

from voodoo_product.api import install_product_platform
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
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


def test_audit_ledger_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "audit.py"
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


def test_product_service_delegates_complete_audit_surface() -> None:
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
        and node.name in {"_append_audit", "list_audit_events", "verify_audit_chain"}
    }

    assert set(methods) == {"_append_audit", "list_audit_events", "verify_audit_chain"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.audit_ledger.append" in source_text
    assert "self.audit_ledger.list_events" in source_text
    assert "self.audit_ledger.verify" in source_text
    assert "sql.SELECT_AUDIT_HEAD" not in source_text
    assert "sql.INSERT_AUDIT_EVENT" not in source_text
    assert "sql.LIST_AUDIT_EVENTS" not in source_text
    assert "sql.LIST_AUDIT_EVENTS_FOR_VERIFICATION" not in source_text
    assert not (ROOT / "voodoo_product" / "ledger_service.py").exists()


def test_product_service_rejects_audit_ledger_from_another_database(tmp_path: Path) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="audit ledger must use the product service database"):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=second.audit_ledger,
        )


def test_composition_shares_database_and_runtime_dependencies_without_public_routes(
    tmp_path: Path,
) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert composition.service.__class__ is ProductService
    assert app.state.voodoo_product_service is composition.service
    assert app.state.voodoo_audit_ledger is composition.audit_ledger
    assert app.state.voodoo_receipt_ledger is composition.receipt_ledger
    assert app.state.voodoo_execution_service is composition.execution_service
    assert app.state.voodoo_external_identity_service is composition.external_identity_service
    assert app.state.voodoo_product_composition is composition
    assert composition.service.audit_ledger is composition.audit_ledger
    assert composition.service.receipt_ledger is composition.receipt_ledger
    assert composition.service.execution_service is composition.execution_service
    assert composition.audit_ledger.db is composition.service.db
    assert composition.receipt_ledger.db is composition.service.db
    assert composition.execution_service.db is composition.service.db
    assert composition.execution_service.config is composition.service.config
    assert composition.execution_service.audit_ledger is composition.audit_ledger
    assert composition.execution_service.receipt_ledger is composition.receipt_ledger
    assert composition.external_identity_service.db is composition.service.db
    assert composition.external_identity_service.audit_ledger is composition.audit_ledger

    bootstrap = composition.service.bootstrap_admin(
        username="bootstrap-admin",
        password="VeryStrongBootstrapPassword1!",
        token="b" * 48,
    )
    administrator = composition.service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="identity-admin",
        password="VeryStrongIdentityAdminPassword1!",
        role="administrator",
    )
    viewer = composition.service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="bound-viewer",
        password="VeryStrongBoundViewerPassword1!",
        role="viewer",
    )
    raw_subject = "composition-subject"
    composition.external_identity_service.create_binding(
        actor_id=str(administrator["id"]),
        user_id=str(viewer["id"]),
        provider="oidc",
        issuer="https://identity.example.com",
        subject=raw_subject,
        reason="Approved composition-bound identity enrollment",
    )

    assert composition.audit_ledger.verify()["valid"] is True
    assert composition.service.verify_audit_chain()["valid"] is True
    assert composition.service.list_audit_events() == composition.audit_ledger.list_events()
    events = composition.audit_ledger.list_events()
    assert events[0]["action"] == "external_identity_binding.create"
    assert "system.bootstrap" in {event["action"] for event in events}
    assert raw_subject not in json.dumps(events, sort_keys=True)

    paths = app.openapi()["paths"]
    assert all("external-identity" not in path for path in paths)
    assert all("identity-bindings" not in path for path in paths)


def test_composed_installer_preserves_routes_and_middleware(tmp_path: Path) -> None:
    legacy_app = FastAPI()
    install_product_platform(
        legacy_app,
        config=product_config(tmp_path, name="legacy"),
        repository_root=tmp_path,
    )
    composed_app = FastAPI()
    install_composed_product_platform(
        composed_app,
        config=product_config(tmp_path, name="composed"),
        repository_root=tmp_path,
    )

    legacy_paths = {
        path: tuple(sorted(methods)) for path, methods in legacy_app.openapi()["paths"].items()
    }
    composed_paths = {
        path: tuple(sorted(methods)) for path, methods in composed_app.openapi()["paths"].items()
    }
    assert composed_paths == legacy_paths
    assert [middleware.cls for middleware in composed_app.user_middleware] == [
        middleware.cls for middleware in legacy_app.user_middleware
    ]


def test_product_entrypoint_uses_composed_installer() -> None:
    source = (ROOT / "voodoo_product" / "main.py").read_text(encoding="utf-8")
    assert "from .composition import install_composed_product_platform" in source
    assert "install_composed_product_platform(app)" in source
    assert "from .api import install_product_platform" not in source
