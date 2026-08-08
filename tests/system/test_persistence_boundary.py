from __future__ import annotations

from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.db import ProductDatabase, SQLiteProductDatabase
from voodoo_product.persistence import (
    DatabaseIntegrityError,
    DatabaseOperationError,
    ProductDatabaseAdapter,
)
from voodoo_product.service import ProductService


def initialized_database(tmp_path: Path) -> SQLiteProductDatabase:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    return database


def config(tmp_path: Path) -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_database_implements_runtime_adapter_contract(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)

    assert isinstance(database, ProductDatabaseAdapter)
    assert ProductDatabase is SQLiteProductDatabase


def test_connection_context_closes_connection(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)
    connection = database.connect()

    with connection as active:
        assert active.execute("SELECT 1 AS healthy").fetchone()["healthy"] == 1

    with pytest.raises(DatabaseOperationError, match="connection is closed"):
        connection.execute("SELECT 1")


def test_transaction_commits_successful_write(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)

    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("wrk_commit", "Committed", "local", "2026-01-01T00:00:00+00:00"),
        )

    with database.connect() as connection:
        row = connection.execute(
            "SELECT name FROM workspaces WHERE id = ?", ("wrk_commit",)
        ).fetchone()
    assert row["name"] == "Committed"


def test_transaction_rolls_back_and_closes_after_exception(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)
    captured_connection = None

    with pytest.raises(RuntimeError, match="force rollback"), database.transaction() as connection:
        captured_connection = connection
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("wrk_rollback", "Rolled Back", "local", "2026-01-01T00:00:00+00:00"),
        )
        raise RuntimeError("force rollback")

    assert captured_connection is not None
    with pytest.raises(DatabaseOperationError, match="connection is closed"):
        captured_connection.execute("SELECT 1")
    with database.connect() as connection:
        row = connection.execute(
            "SELECT id FROM workspaces WHERE id = ?", ("wrk_rollback",)
        ).fetchone()
    assert row is None


def test_sqlite_errors_are_normalized_without_query_details(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)

    with pytest.raises(DatabaseIntegrityError) as integrity, database.connect() as connection:
        connection.execute(
            """
            INSERT INTO runtime_flags(key, value, updated_by, updated_at)
            VALUES ('emergency_stop', 'false', 'test', '2026-01-01T00:00:00+00:00')
            """
        )
    assert str(integrity.value) == "database integrity constraint failed"

    with pytest.raises(DatabaseOperationError) as operation, database.connect() as connection:
        connection.execute("SELECT secret_column FROM missing_sensitive_table")
    assert str(operation.value) == "database operation failed"
    assert "secret_column" not in str(operation.value)
    assert "missing_sensitive_table" not in str(operation.value)


def test_service_accepts_injected_database_adapter(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)

    service = ProductService(config(tmp_path), database=database)

    assert service.db is database
    assert service.health()["schema_version"] == 8


def test_service_source_has_no_sqlite_runtime_dependency() -> None:
    source = Path(__file__).resolve().parents[2] / "voodoo_product" / "service.py"
    text = source.read_text(encoding="utf-8")
    assert "import sqlite3" not in text
    assert "sqlite3." not in text
