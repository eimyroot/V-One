from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.auth_rate_limit import (
    AuthenticationRateLimitService,
    AuthRateLimitExceeded,
)
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import (
    AuthRateLimitExceeded as ServiceAuthRateLimitExceeded,
)
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]


def product_config(
    tmp_path: Path,
    *,
    name: str = "product",
    auth_max_failures: int = 3,
    auth_source_max_failures: int = 20,
) -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
        auth_max_failures=auth_max_failures,
        auth_source_max_failures=auth_source_max_failures,
        auth_window_seconds=300,
        auth_lockout_seconds=900,
    )


def test_authentication_rate_limit_service_uses_only_catalog_statements() -> None:
    source = ROOT / "voodoo_product" / "auth_rate_limit.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 6
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_service_delegates_authentication_rate_limit_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    names = {
        "enforce_login_rate_limit",
        "record_login_failure",
        "clear_login_rate_limit",
        "enforce_bootstrap_rate_limit",
        "record_bootstrap_failure",
        "clear_bootstrap_rate_limit",
    }
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }

    assert set(methods) == names
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.authentication_rate_limit_service.enforce_login_rate_limit" in source_text
    assert "self.authentication_rate_limit_service.record_login_failure" in source_text
    assert "self.authentication_rate_limit_service.clear_login_rate_limit" in source_text
    assert "self.authentication_rate_limit_service.enforce_bootstrap_rate_limit" in source_text
    assert "self.authentication_rate_limit_service.record_bootstrap_failure" in source_text
    assert "self.authentication_rate_limit_service.clear_bootstrap_rate_limit" in source_text
    assert "sql.SELECT_AUTH_RATE_LIMIT" not in source_text
    assert "sql.DELETE_AUTH_RATE_LIMIT" not in source_text
    assert "sql.DELETE_EXPIRED_AUTH_RATE_LIMITS" not in source_text
    assert "sql.UPSERT_AUTH_RATE_LIMIT" not in source_text


def test_service_exception_import_remains_compatible() -> None:
    assert ServiceAuthRateLimitExceeded is AuthRateLimitExceeded


def test_product_service_rejects_rate_limit_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="authentication rate-limit service must use the product service database",
    ):
        ProductService(
            first.config,
            database=first.db,
            authentication_rate_limit_service=second.authentication_rate_limit_service,
            audit_ledger=first.audit_ledger,
            user_account_service=first.user_account_service,
            workspace_service=first.workspace_service,
            change_request_service=first.change_request_service,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
            execution_service=first.execution_service,
            platform_status_service=first.platform_status_service,
        )


def test_rate_limit_service_preserves_hashing_lockout_and_expiry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ProductService(
        product_config(
            tmp_path,
            auth_max_failures=2,
            auth_source_max_failures=10,
        )
    )
    now = 1_000
    monkeypatch.setattr(service_module.time, "time", lambda: now)

    service.record_login_failure(username=" Victim ", source="SOURCE-A")
    with pytest.raises(AuthRateLimitExceeded) as recorded:
        service.record_login_failure(username="victim", source="source-b")
    assert recorded.value.retry_after == 900
    with pytest.raises(AuthRateLimitExceeded) as enforced:
        service.enforce_login_rate_limit(username="VICTIM", source="source-c")
    assert enforced.value.retry_after == 900

    with service.db.connect() as connection:
        rows = connection.execute(
            "SELECT scope, key_hash, failure_count, window_started_at, updated_at "
            "FROM auth_rate_limits ORDER BY scope, key_hash"
        ).fetchall()
    account = next(row for row in rows if row["scope"] == "login.account")
    assert account["failure_count"] == 2
    assert account["window_started_at"] == now
    assert account["updated_at"] == now
    assert len(account["key_hash"]) == 64
    assert "victim" not in account["key_hash"]

    now = 2_000
    service.enforce_login_rate_limit(username="victim", source="source-c")
    with service.db.connect() as connection:
        account_count = connection.execute(
            "SELECT COUNT(*) AS count FROM auth_rate_limits WHERE scope = 'login.account'"
        ).fetchone()
    assert account_count["count"] == 0


def test_clear_rate_limit_preserves_account_and_source_semantics(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    service.record_login_failure(username="operator", source="source-a")
    service.clear_login_rate_limit(username="operator", source="source-a")

    with service.db.connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM auth_rate_limits").fetchone()
    assert count["count"] == 0


def test_authentication_rate_limit_service_rejects_wrong_composition_identity(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    service = AuthenticationRateLimitService(
        database=first.db,
        config=second.config,
    )
    assert service.db is first.db
    assert service.config is second.config
    with pytest.raises(
        ValueError,
        match="authentication rate-limit service must use the product service configuration",
    ):
        ProductService(
            first.config,
            database=first.db,
            authentication_rate_limit_service=service,
            audit_ledger=first.audit_ledger,
            user_account_service=first.user_account_service,
            workspace_service=first.workspace_service,
            change_request_service=first.change_request_service,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
            execution_service=first.execution_service,
            platform_status_service=first.platform_status_service,
        )


def test_composition_exposes_shared_authentication_rate_limit_service(
    tmp_path: Path,
) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert (
        app.state.voodoo_authentication_rate_limit_service
        is composition.authentication_rate_limit_service
    )
    assert (
        composition.service.authentication_rate_limit_service
        is composition.authentication_rate_limit_service
    )
    assert composition.authentication_rate_limit_service.db is composition.service.db
    assert composition.authentication_rate_limit_service.config is composition.service.config
