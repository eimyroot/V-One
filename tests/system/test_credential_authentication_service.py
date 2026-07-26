from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.credential_authentication import CredentialAuthenticationService
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


def test_credential_authentication_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "credential_authentication.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 1
    statement = execute_calls[0].args[0]
    assert isinstance(statement, ast.Attribute)
    assert isinstance(statement.value, ast.Name)
    assert statement.value.id == "sql"
    assert statement.attr == "SELECT_USER_FOR_AUTH"


def test_product_service_delegates_credential_authentication_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    method = next(
        node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef) and node.name == "authenticate"
    )

    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
        for node in ast.walk(method)
    )
    assert "return self.credential_authentication_service.authenticate(" in source_text
    assert "sql.SELECT_USER_FOR_AUTH" not in source_text
    assert "_dummy_password_hash" not in source_text


def test_credentials_preserve_success_and_generic_failure_contract(tmp_path: Path) -> None:
    product = ProductService(product_config(tmp_path))
    bootstrap = product.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )

    assert product.authenticate(
        username=" admin ",
        password="VeryStrongAdminPassword1!",
    ) == {
        "id": bootstrap["user_id"],
        "username": "admin",
        "role": "administrator",
    }

    with product.db.connect() as connection:
        connection.execute(
            "UPDATE users SET active = 0 WHERE id = ?",
            (bootstrap["user_id"],),
        )
        connection.commit()

    for username, password in (
        ("admin", "WrongPassword1!"),
        ("missing", "WrongPassword1!"),
        ("admin", "VeryStrongAdminPassword1!"),
    ):
        with pytest.raises(PermissionError, match="^invalid credentials$"):
            product.authenticate(username=username, password=password)


def test_missing_account_executes_dummy_password_verification(tmp_path: Path) -> None:
    product = ProductService(product_config(tmp_path))
    verified: list[tuple[str, str]] = []
    service = CredentialAuthenticationService(
        database=product.db,
        password_hasher=lambda password: f"encoded:{password}",
        password_verifier=lambda password, encoded: not verified.append((password, encoded)),
        secret_factory=lambda: "fixed-dummy-secret",
    )

    with pytest.raises(PermissionError, match="invalid credentials"):
        service.authenticate(username="missing", password="supplied-password")

    assert verified == [
        (
            "supplied-password",
            "encoded:VOODOO-invalid-account-fixed-dummy-secret",
        )
    ]


def test_product_service_rejects_credential_service_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="credential authentication service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            credential_authentication_service=second.credential_authentication_service,
        )


def test_credential_service_preserves_dynamic_password_verifier_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = ProductService(product_config(tmp_path))
    product.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    original_verify_password = service_module.verify_password
    verified: list[str] = []

    def controlled_verify_password(password: str, encoded: str) -> bool:
        verified.append(password)
        return original_verify_password(password, encoded)

    monkeypatch.setattr(service_module, "verify_password", controlled_verify_password)

    product.authenticate(
        username="admin",
        password="VeryStrongAdminPassword1!",
    )

    assert verified == ["VeryStrongAdminPassword1!"]


def test_composition_exposes_shared_credential_authentication_service(
    tmp_path: Path,
) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert (
        app.state.voodoo_credential_authentication_service
        is composition.credential_authentication_service
    )
    assert (
        composition.service.credential_authentication_service
        is composition.credential_authentication_service
    )
    assert composition.credential_authentication_service.db is composition.service.db
