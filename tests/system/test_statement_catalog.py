from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.persistence import DatabaseStatement, DatabaseStatementError
from voodoo_product.service import ProductService
from voodoo_product.statements import ALL_STATEMENTS, HEALTH_CHECK, STATEMENTS_BY_NAME

ROOT = Path(__file__).resolve().parents[2]


def test_statement_catalog_is_complete_unique_and_classified() -> None:
    assert len(ALL_STATEMENTS) == 44
    assert tuple(STATEMENTS_BY_NAME) == tuple(statement.name for statement in ALL_STATEMENTS)
    assert tuple(STATEMENTS_BY_NAME.values()) == ALL_STATEMENTS

    write_verbs = {"DELETE", "INSERT", "UPDATE"}
    for statement in ALL_STATEMENTS:
        first_verb = statement.sqlite_sql.split(maxsplit=1)[0].upper()
        expected_mode = "write" if first_verb in write_verbs else "read"
        assert statement.mode == expected_mode
        assert statement.sqlite_sql == statement.sqlite_sql.strip()
        assert statement.for_backend("sqlite") == statement.sqlite_sql
        assert statement.postgresql_sql is None


def test_statement_catalog_fails_closed_for_unreleased_backends() -> None:
    with pytest.raises(DatabaseStatementError, match="unavailable for backend postgresql"):
        HEALTH_CHECK.for_backend("postgresql")
    with pytest.raises(DatabaseStatementError, match="backend is unsupported"):
        HEALTH_CHECK.for_backend("mysql")


@pytest.mark.parametrize(
    ("name", "mode", "sqlite_sql"),
    [
        ("Invalid.Name", "read", "SELECT 1"),
        ("valid.name", "invalid", "SELECT 1"),
        ("valid.name", "read", "  "),
        ("valid.name", "read", "SELECT \0"),
    ],
)
def test_statement_validation_rejects_invalid_definitions(
    name: str, mode: str, sqlite_sql: str
) -> None:
    with pytest.raises(ValueError, match="database statement"):
        DatabaseStatement(name=name, mode=mode, sqlite_sql=sqlite_sql)  # type: ignore[arg-type]


def test_sqlite_adapter_executes_catalog_statements(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()

    with database.connect() as connection:
        row = connection.execute(HEALTH_CHECK).fetchone()

    assert row is not None
    assert row[0] == 1
    assert database.write_serialization == "global"


def test_approval_catalog_variants_preserve_pending_filter(tmp_path: Path) -> None:
    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        )
    )
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    pending = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Pending",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={},
    )
    service.submit_change_request(actor_id=bootstrap["user_id"], request_id=pending["id"])
    draft = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Draft",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={},
    )

    assert {row["request_id"] for row in service.list_approvals()} == {
        pending["id"],
        draft["id"],
    }
    assert [row["request_id"] for row in service.list_approvals(pending_only=True)] == [
        pending["id"]
    ]


def _is_catalog_reference(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "sql"
    )


def _is_catalog_expression(node: ast.expr) -> bool:
    return _is_catalog_reference(node) or (
        isinstance(node, ast.IfExp)
        and _is_catalog_reference(node.body)
        and _is_catalog_reference(node.orelse)
    )


def test_service_database_calls_use_only_catalog_statements() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 48
    assert all(call.args and _is_catalog_expression(call.args[0]) for call in execute_calls)
