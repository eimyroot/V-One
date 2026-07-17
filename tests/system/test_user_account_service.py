from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import ProductService
from voodoo_product.user_account import UserAccountService

ROOT = Path(__file__).resolve().parents[2]


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_user_account_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "user_account.py"
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


def test_product_service_delegates_user_account_surface() -> None:
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
        and node.name in {"get_active_user", "create_user"}
    }

    assert set(methods) == {"get_active_user", "create_user"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.user_account_service.get_active_user" in source_text
    assert "self.user_account_service.create_user" in source_text
    assert "sql.SELECT_ACTIVE_USER" not in source_text
    assert "sql.INSERT_USER" in source_text


def test_user_account_service_rejects_audit_ledger_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="user account audit ledger must use its database"):
        UserAccountService(database=first.db, audit_ledger=second.audit_ledger)


def test_product_service_rejects_user_account_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="user account service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            user_account_service=second.user_account_service,
        )


def test_user_account_service_preserves_product_service_contract(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    created = service.create_user(
        actor_id=bootstrap["user_id"],
        username="  developer  ",
        password="VeryStrongDeveloperPassword1!",
        role="developer",
    )

    assert created["username"] == "  developer  "
    assert created["role"] == "developer"
    active = service.get_active_user(created["id"])
    assert active == {
        "id": created["id"],
        "username": "developer",
        "role": "developer",
    }
    assert service.authenticate(
        username="developer",
        password="VeryStrongDeveloperPassword1!",
    ) == active
    with pytest.raises(ValueError, match="username already exists"):
        service.create_user(
            actor_id=bootstrap["user_id"],
            username="developer",
            password="AnotherStrongDeveloperPassword1!",
            role="developer",
        )
    with pytest.raises(ValueError, match="unknown role"):
        service.create_user(
            actor_id=bootstrap["user_id"],
            username="invalid-role",
            password="AnotherStrongDeveloperPassword1!",
            role="owner",
        )
    with pytest.raises(PermissionError, match="account is inactive"):
        service.get_active_user("usr_missing")
    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "user.create" in actions
    assert service.verify_audit_chain()["valid"] is True


def test_user_account_service_preserves_service_monkeypatch_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    original_new_id = service_module.new_id
    original_hash_password = service_module.hash_password
    hashed_passwords: list[str] = []

    def controlled_new_id(prefix: str) -> str:
        return "usr_controlled" if prefix == "usr" else original_new_id(prefix)

    def controlled_hash_password(password: str) -> str:
        hashed_passwords.append(password)
        return original_hash_password(password)

    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "hash_password", controlled_hash_password)
    created = service.create_user(
        actor_id=bootstrap["user_id"],
        username="controlled",
        password="VeryStrongControlledPassword1!",
        role="auditor",
    )

    assert created["id"] == "usr_controlled"
    assert hashed_passwords == ["VeryStrongControlledPassword1!"]
    assert service.authenticate(
        username="controlled",
        password="VeryStrongControlledPassword1!",
    )["id"] == "usr_controlled"


def test_composition_exposes_shared_user_account_service(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert app.state.voodoo_user_account_service is composition.user_account_service
    assert composition.service.user_account_service is composition.user_account_service
    assert composition.user_account_service.db is composition.service.db
    assert composition.user_account_service.audit_ledger is composition.audit_ledger
