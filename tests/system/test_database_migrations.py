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
    MIGRATION_TABLE_SQL,
    DatabaseBackendError,
    DatabaseMigrationError,
    SQLiteProductDatabase,
    create_product_database,
    iter_sqlite_statements,
    load_sqlite_migrations,
)
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.service import ProductService, canonical_json, chained_hash


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


def create_schema_version(path: Path, version: int) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(MIGRATION_TABLE_SQL)
        for migration in load_sqlite_migrations()[:version]:
            for statement in iter_sqlite_statements(migration.sql):
                connection.execute(statement)
            connection.execute(
                """
                INSERT INTO schema_migrations(version, name, checksum, applied_at)
                VALUES (?, ?, ?, '2026-07-16T12:00:00.000+00:00')
                """,
                (migration.version, migration.name, migration.checksum),
            )
            connection.execute(f"PRAGMA user_version = {migration.version}")
        connection.commit()
    finally:
        connection.close()


def create_schema_v2(path: Path) -> None:
    create_schema_version(path, 2)


def insert_completed_execution(
    connection: sqlite3.Connection,
    *,
    index: int,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO users(id, username, password_hash, role, active, created_at)
        VALUES ('usr_admin', 'admin', 'unused', 'administrator', 1, ?)
        """,
        (created_at,),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO workspaces(id, name, environment, created_at)
        VALUES ('wrk_main', 'Main', 'local', ?)
        """,
        (created_at,),
    )
    connection.execute(
        """
        INSERT INTO change_requests(
            id, workspace_id, title, description, risk, environment, adapter,
            payload_json, status, requested_by, created_at, updated_at
        ) VALUES (?, 'wrk_main', ?, '', 'R1', 'local', 'echo', '{}',
                  'COMPLETED', 'usr_admin', ?, ?)
        """,
        (f"cr_{index}", f"Receipt {index}", created_at, created_at),
    )
    connection.execute(
        """
        INSERT INTO executions(
            id, request_id, status, adapter, output_json, started_at, completed_at
        ) VALUES (?, ?, 'SUCCEEDED', 'echo', '{}', ?, ?)
        """,
        (f"exec_{index}", f"cr_{index}", created_at, created_at),
    )


def test_fresh_database_records_ordered_checksum_history(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")

    database.initialize()

    rows = migration_rows(database)
    assert database.schema_version() == 6
    assert [row[0] for row in rows] == [1, 2, 3, 4, 5, 6]
    assert [row[1] for row in rows] == [
        "0001_core_schema.sql",
        "0002_auth_rate_limits.sql",
        "0003_receipt_sequence.sql",
        "0004_execution_leases.sql",
        "0005_workspace_environment_boundary.sql",
        "0006_external_identity_bindings.sql",
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
        for migration in load_sqlite_migrations()[:1]:
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
    assert database.schema_version() == 6


def test_initialization_is_idempotent(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    first_history = migration_rows(database)

    database.initialize()

    assert migration_rows(database) == first_history


def test_receipt_sequence_migration_reconstructs_chain_links(tmp_path: Path) -> None:
    path = tmp_path / "schema-v2.sqlite3"
    create_schema_v2(path)
    connection = sqlite3.connect(path)
    try:
        created_at = "2026-07-16T12:00:00.000+00:00"
        for index in (1, 2):
            insert_completed_execution(connection, index=index, created_at=created_at)

        first_payload = {"execution_id": "exec_1", "status": "SUCCEEDED"}
        first_hash = chained_hash("GENESIS", first_payload)
        second_payload = {"execution_id": "exec_2", "status": "SUCCEEDED"}
        second_hash = chained_hash(first_hash, second_payload)
        connection.execute(
            """
            INSERT INTO receipts(
                id, execution_id, payload_json, previous_hash, receipt_hash, created_at
            ) VALUES ('rcpt_a', 'exec_2', ?, ?, ?, ?)
            """,
            (canonical_json(second_payload), first_hash, second_hash, created_at),
        )
        connection.execute(
            """
            INSERT INTO receipts(
                id, execution_id, payload_json, previous_hash, receipt_hash, created_at
            ) VALUES ('rcpt_z', 'exec_1', ?, 'GENESIS', ?, ?)
            """,
            (canonical_json(first_payload), first_hash, created_at),
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLiteProductDatabase(path)
    database.initialize()

    with database.connect() as migrated:
        rows = migrated.execute("SELECT sequence, id FROM receipts ORDER BY sequence").fetchall()
    assert [tuple(row) for row in rows] == [(1, "rcpt_z"), (2, "rcpt_a")]
    assert database.schema_version() == 6
    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=path,
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        ),
        database=database,
    )
    assert service.verify_receipt_chain() == {
        "valid": True,
        "count": 2,
        "head": second_hash,
    }

    operator = service.create_user(
        actor_id="usr_admin",
        username="operator",
        password="VeryStrongOperatorPassword1!",
        role="operator",
    )
    request = service.create_change_request(
        actor_id="usr_admin",
        workspace_id="wrk_main",
        title="Post-migration receipt",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"migrated": True},
    )
    service.submit_change_request(actor_id="usr_admin", request_id=request["id"])
    service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="verify post-migration append",
    )
    service.execute_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        idempotency_key="post-migration-receipt",
        repository_root=tmp_path,
    )

    receipts = service.list_receipts()
    assert receipts[0]["sequence"] == 3
    assert service.verify_receipt_chain()["valid"] is True


def test_receipt_sequence_migration_rejects_disconnected_history(tmp_path: Path) -> None:
    path = tmp_path / "disconnected-schema-v2.sqlite3"
    create_schema_v2(path)
    created_at = "2026-07-16T12:00:00.000+00:00"
    connection = sqlite3.connect(path)
    try:
        insert_completed_execution(connection, index=1, created_at=created_at)
        connection.execute(
            """
            INSERT INTO receipts(
                id, execution_id, payload_json, previous_hash, receipt_hash, created_at
            ) VALUES ('rcpt_orphan', 'exec_1', '{}', 'missing-parent', 'orphan-hash', ?)
            """,
            (created_at,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(DatabaseMigrationError, match="migration execution failed"):
        SQLiteProductDatabase(path).initialize()

    connection = sqlite3.connect(path)
    try:
        columns = [row[1] for row in connection.execute('PRAGMA table_info("receipts")')]
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()
    assert "sequence" not in columns
    assert "receipts_v3" not in tables
    assert user_version == 2


def test_execution_lease_migration_marks_legacy_running_execution_expired(
    tmp_path: Path,
) -> None:
    path = tmp_path / "schema-v3.sqlite3"
    create_schema_version(path, 3)
    started_at = "2026-07-16T12:00:00.000+00:00"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_admin', 'admin', 'unused', 'administrator', 1, ?)
            """,
            (started_at,),
        )
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES ('wrk_main', 'Main', 'local', ?)
            """,
            (started_at,),
        )
        connection.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES ('cr_running', 'wrk_main', 'Interrupted', '', 'R1', 'local',
                      'echo', '{}', 'RUNNING', 'usr_admin', ?, ?)
            """,
            (started_at, started_at),
        )
        connection.execute(
            """
            INSERT INTO executions(
                id, request_id, status, adapter, output_json, started_at
            ) VALUES ('exec_running', 'cr_running', 'RUNNING', 'echo', '{}', ?)
            """,
            (started_at,),
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLiteProductDatabase(path)
    database.initialize()

    with database.connect() as migrated:
        execution = migrated.execute(
            "SELECT fence, lease_expires_at FROM executions WHERE id = 'exec_running'"
        ).fetchone()
    assert tuple(execution) == (1, started_at)
    assert database.schema_version() == 6


def test_workspace_environment_migration_preserves_history_and_blocks_bypass(
    tmp_path: Path,
) -> None:
    path = tmp_path / "schema-v4.sqlite3"
    create_schema_version(path, 4)
    created_at = "2026-07-16T12:00:00.000+00:00"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_admin', 'admin', 'unused', 'administrator', 1, ?)
            """,
            (created_at,),
        )
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES ('wrk_production', 'Production', 'production', ?)
            """,
            (created_at,),
        )
        connection.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES ('cr_legacy', 'wrk_production', 'Legacy mismatch', '', 'R1', 'local',
                      'echo', '{}', 'COMPLETED', 'usr_admin', ?, ?)
            """,
            (created_at, created_at),
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLiteProductDatabase(path)
    database.initialize()

    assert database.schema_version() == 6
    with database.connect() as migrated:
        legacy = migrated.execute(
            "SELECT environment, status FROM change_requests WHERE id = 'cr_legacy'"
        ).fetchone()
    assert tuple(legacy) == ("local", "COMPLETED")

    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=path,
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        ),
        database=database,
    )
    with pytest.raises(RuntimeError, match="environment does not match workspace"):
        service.submit_change_request(actor_id="usr_admin", request_id="cr_legacy")

    with pytest.raises(DatabaseIntegrityError), database.connect() as migrated:
        migrated.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES ('wrk_invalid', 'Invalid', 'unknown', ?)
            """,
            (created_at,),
        )

    with pytest.raises(DatabaseIntegrityError), database.connect() as migrated:
        migrated.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES ('cr_bypass', 'wrk_production', 'Bypass', '', 'R1', 'local',
                      'echo', '{}', 'DRAFT', 'usr_admin', ?, ?)
            """,
            (created_at, created_at),
        )

    with pytest.raises(DatabaseIntegrityError), database.connect() as migrated:
        migrated.execute(
            """
            INSERT INTO executions(id, request_id, status, adapter, output_json, started_at)
            VALUES ('exec_bypass', 'cr_legacy', 'RUNNING', 'echo', '{}', ?)
            """,
            (created_at,),
        )


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

    assert database.schema_version() == 6


def test_missing_required_environment_trigger_fails_schema_validation(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    with database.connect() as connection:
        connection.execute("DROP TRIGGER trg_executions_environment_insert")

    with pytest.raises(DatabaseMigrationError, match="missing triggers"):
        database.initialize()


def test_failed_pending_migration_rolls_back_complete_initialization(tmp_path: Path) -> None:
    migrations = copy_migrations(tmp_path)
    (migrations / "0007_broken.sql").write_text(
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


def test_missing_migration_sequence_is_rejected(tmp_path: Path) -> None:
    migrations = copy_migrations(tmp_path)
    (migrations / "0002_auth_rate_limits.sql").unlink()

    with pytest.raises(DatabaseMigrationError, match="contiguous at version 2"):
        SQLiteProductDatabase(
            tmp_path / "product.sqlite3",
            migration_directory=migrations,
        ).initialize()


def test_user_version_and_history_drift_is_rejected(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 0")
        connection.commit()

    with pytest.raises(DatabaseMigrationError, match="does not match migration history"):
        database.initialize()


def test_concurrent_initialization_serializes_cleanly(tmp_path: Path) -> None:
    path = tmp_path / "concurrent.sqlite3"

    def initialize() -> int:
        database = SQLiteProductDatabase(path)
        database.initialize()
        return database.schema_version()

    with ThreadPoolExecutor(max_workers=2) as executor:
        versions = list(executor.map(lambda _: initialize(), range(2)))

    assert versions == [6, 6]


def test_unreleased_postgresql_backend_fails_before_service_start(tmp_path: Path) -> None:
    with pytest.raises(DatabaseBackendError, match="PostgreSQL backend is not released"):
        create_product_database(backend="postgresql", path=tmp_path / "unused.sqlite3")

    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "unused.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
        database_backend="postgresql",
    )
    app = FastAPI()
    with pytest.raises(DatabaseBackendError, match="PostgreSQL backend is not released"):
        install_product_platform(app, config=config, repository_root=tmp_path)
    assert not config.database_path.exists()


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
    assert response.json()["schema_version"] == 6
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


def test_health_reports_database_unavailable_as_http_503(tmp_path: Path) -> None:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )
    app = FastAPI()
    service = install_product_platform(app, config=config, repository_root=tmp_path)

    def unavailable() -> dict[str, object]:
        return {"status": "UNAVAILABLE", "reason": "database unavailable"}

    service.health = unavailable  # type: ignore[method-assign]
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "UNAVAILABLE", "reason": "database unavailable"}
