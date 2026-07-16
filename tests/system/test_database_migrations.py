from __future__ import annotations

import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.db import (
    DEFAULT_MIGRATION_DIRECTORY,
    DatabaseBackendError,
    DatabaseMigrationError,
    SQLiteProductDatabase,
    create_product_database,
    load_sqlite_migrations,
)


def copy_migrations(tmp_path: Path) -> Path:
    target = tmp_path / "migrations"
    shutil.copytree(DEFAULT_MIGRATION_DIRECTORY, target)
    return target


def migration_rows(database: SQLiteProductDatabase) -> list[tuple[object, ...]]:
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT version, name, checksum, applied_at
            FROM schema_migrations ORDER BY version
            """
        ).fetchall()
    return [tuple(row) for row in rows]


def test_fresh_database_records_ordered_checksum_history(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")

    database.initialize()

    rows = migration_rows(database)
    assert database.schema_version() == 2
    assert [row[0] for row in rows] == [1, 2]
    assert [row[1] for row in rows] == [
        "0001_core_schema.sql",
        "0002_auth_rate_limits.sql",
    ]
    assert all(len(str(row[2])) == 64 for row in rows)
    assert all(str(row[3]).endswith("+00:00") for row in rows)
    with database.connect() as connection:
        stop = connection.execute(
            "SELECT value FROM runtime_flags WHERE key = 'emergency_stop'"
        ).fetchone()
    assert stop["value"] == "false"


def test_legacy_database_is_adopted_without_data_loss(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    try:
        for migration in load_sqlite_migrations():
            connection.executescript(migration.sql)
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_legacy', 'legacy-admin', 'preserved-hash', 'administrator', 1,
                    '2026-01-01T00:00:00+00:00')
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLiteProductDatabase(path)
    database.initialize()

    with database.connect() as upgraded:
        user = upgraded.execute(
            "SELECT id, username, password_hash FROM users WHERE id = 'usr_legacy'"
        ).fetchone()
    assert tuple(user) == ("usr_legacy", "legacy-admin", "preserved-hash")
    assert database.schema_version() == 2


def test_initialization_is_idempotent(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    first_history = migration_rows(database)

    database.initialize()

    assert migration_rows(database) == first_history


def test_applied_migration_checksum_drift_fails_closed(tmp_path: Path) -> None:
    migrations = copy_migrations(tmp_path)
    database = SQLiteProductDatabase(
        tmp_path / "product.sqlite3",
        migration_directory=migrations,
    )
    database.initialize()
    migration = migrations / "0001_core_schema.sql"
    migration.write_text(
        migration.read_text(encoding="utf-8") + "\n-- forbidden rewrite\n",
        encoding="utf-8",
    )

    with pytest.raises(DatabaseMigrationError, match="history drift detected"):
        database.initialize()

    assert database.schema_version() == 2


def test_failed_pending_migration_rolls_back_complete_initialization(tmp_path: Path) -> None:
    migrations = copy_migrations(tmp_path)
    (migrations / "0003_broken.sql").write_text(
        "CREATE TABLE migration_should_rollback (id INTEGER);\nTHIS IS NOT SQL;\n",
        encoding="utf-8",
    )
    path = tmp_path / "product.sqlite3"
    database = SQLiteProductDatabase(path, migration_directory=migrations)

    with pytest.raises(DatabaseMigrationError, match="migration execution failed"):
        database.initialize()

    connection = sqlite3.connect(path)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    finally:
        connection.close()
    assert tables == set()
    assert user_version == 0


def test_migration_sequence_gap_is_rejected_before_database_access(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_start.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (migrations / "0003_gap.sql").write_text("SELECT 3;\n", encoding="utf-8")

    with pytest.raises(DatabaseMigrationError, match="contiguous at version 2"):
        load_sqlite_migrations(migrations)


def test_user_version_and_history_drift_is_rejected(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 0")
        connection.commit()

    with pytest.raises(DatabaseMigrationError, match="does not match migration history"):
        database.initialize()


def test_concurrent_initialization_serializes_without_duplicate_history(tmp_path: Path) -> None:
    path = tmp_path / "product.sqlite3"

    def initialize(_: int) -> None:
        SQLiteProductDatabase(path).initialize()

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(initialize, range(8)))

    database = SQLiteProductDatabase(path)
    assert database.schema_version() == 2
    assert len(migration_rows(database)) == 2


def test_postgresql_backend_fails_before_creating_local_database(tmp_path: Path) -> None:
    path = tmp_path / "must-not-exist.sqlite3"

    with pytest.raises(DatabaseBackendError, match="PostgreSQL backend is not released"):
        create_product_database(backend="postgresql", path=path)

    assert not path.exists()


def test_health_reports_released_backend_and_schema_version(tmp_path: Path) -> None:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )
    app = FastAPI()
    install_product_platform(app, config=config, repository_root=tmp_path)

    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["database_backend"] == "sqlite"
    assert response.json()["schema_version"] == 2
    assert response.json()["production_effects"] == "DISABLED"

    service = app.state.voodoo_product_service
    with service.db.connect() as connection:
        connection.execute("PRAGMA user_version = 0")
        connection.commit()

    unavailable = client.get("/api/v1/health")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "status": "UNAVAILABLE",
        "database": "UNAVAILABLE",
        "database_backend": "sqlite",
    }
