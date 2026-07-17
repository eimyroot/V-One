from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from voodoo_product.bootstrap import BootstrapService
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


def bootstrap_service(
    product: ProductService,
    *,
    audit_ledger: Any | None = None,
) -> BootstrapService:
    identifiers = iter(("usr-fixed", "wrk-fixed"))
    return BootstrapService(
        database=product.db,
        config=product.config,
        audit_ledger=audit_ledger or product.audit_ledger,
        id_factory=lambda _prefix: next(identifiers),
        clock=lambda: "2026-07-17T12:00:00+00:00",
        password_hasher=lambda password: f"hashed:{password}",
    )


def test_bootstrap_service_uses_only_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "bootstrap.py"
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


def test_product_service_delegates_bootstrap_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef) and node.name in {"has_users", "bootstrap_admin"}
    }

    assert set(methods) == {"has_users", "bootstrap_admin"}
    assert all(
        not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
        for method in methods.values()
    )
    assert "return self.bootstrap_service.has_users()" in source_text
    assert "return self.bootstrap_service.bootstrap_admin(" in source_text
    assert "sql.INSERT_USER" not in source_text
    assert "sql.INSERT_WORKSPACE" not in source_text


def test_bootstrap_service_provisions_user_workspace_and_audit_atomically(tmp_path: Path) -> None:
    product = ProductService(product_config(tmp_path))
    service = bootstrap_service(product)

    assert service.has_users() is False
    result = service.bootstrap_admin(
        username=" admin ",
        password="secret-password",
        token=product.config.bootstrap_token,
    )

    assert result == {
        "user_id": "usr-fixed",
        "workspace_id": "wrk-fixed",
        "workspace_environment": "local",
        "role": "administrator",
    }
    assert service.has_users() is True

    with product.db.connect() as connection:
        user = connection.execute(
            "SELECT id, username, password_hash, role FROM users WHERE id = ?",
            ("usr-fixed",),
        ).fetchone()
        workspace = connection.execute(
            "SELECT id, name, environment FROM workspaces WHERE id = ?",
            ("wrk-fixed",),
        ).fetchone()
        audit = connection.execute(
            "SELECT actor_id, action, target_type, target_id FROM audit_events"
        ).fetchone()

    assert dict(user) == {
        "id": "usr-fixed",
        "username": "admin",
        "password_hash": "hashed:secret-password",
        "role": "administrator",
    }
    assert dict(workspace) == {
        "id": "wrk-fixed",
        "name": "VOODOO Local",
        "environment": "local",
    }
    assert dict(audit) == {
        "actor_id": "usr-fixed",
        "action": "system.bootstrap",
        "target_type": "workspace",
        "target_id": "wrk-fixed",
    }


def test_bootstrap_service_rejects_invalid_token_before_transaction(tmp_path: Path) -> None:
    product = ProductService(product_config(tmp_path))
    service = bootstrap_service(product)

    with pytest.raises(PermissionError, match="invalid bootstrap token"):
        service.bootstrap_admin(username="admin", password="secret", token="wrong")

    assert service.has_users() is False


def test_bootstrap_service_rolls_back_user_and_workspace_when_audit_fails(
    tmp_path: Path,
) -> None:
    product = ProductService(product_config(tmp_path))

    class FailingAuditLedger:
        def append(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("audit unavailable")

    service = bootstrap_service(product, audit_ledger=FailingAuditLedger())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.bootstrap_admin(
            username="admin",
            password="secret",
            token=product.config.bootstrap_token,
        )

    with product.db.connect() as connection:
        users = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        workspaces = connection.execute("SELECT COUNT(*) AS count FROM workspaces").fetchone()
        audits = connection.execute("SELECT COUNT(*) AS count FROM audit_events").fetchone()

    assert users["count"] == 0
    assert workspaces["count"] == 0
    assert audits["count"] == 0


def test_bootstrap_service_closes_after_first_success(tmp_path: Path) -> None:
    product = ProductService(product_config(tmp_path))
    service = bootstrap_service(product)
    service.bootstrap_admin(
        username="admin",
        password="secret",
        token=product.config.bootstrap_token,
    )

    with pytest.raises(RuntimeError, match="bootstrap is already closed"):
        service.bootstrap_admin(
            username="second",
            password="secret",
            token=product.config.bootstrap_token,
        )


def test_product_service_rejects_bootstrap_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="bootstrap service must use the product service database",
    ):
        ProductService(
            first.config,
            database=first.db,
            authentication_rate_limit_service=first.authentication_rate_limit_service,
            bootstrap_service=second.bootstrap_service,
            audit_ledger=first.audit_ledger,
            user_account_service=first.user_account_service,
            workspace_service=first.workspace_service,
            change_request_service=first.change_request_service,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
            execution_service=first.execution_service,
            platform_status_service=first.platform_status_service,
        )


def test_composition_exposes_shared_bootstrap_service(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert app.state.voodoo_bootstrap_service is composition.bootstrap_service
    assert composition.service.bootstrap_service is composition.bootstrap_service
    assert composition.bootstrap_service.db is composition.service.db
    assert composition.bootstrap_service.config is composition.service.config
    assert composition.bootstrap_service.audit_ledger is composition.audit_ledger
