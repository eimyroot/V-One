from __future__ import annotations

import contextlib
import hashlib
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MIGRATION_PATTERN = re.compile(r"^(?P<version>[0-9]{4})_[a-z0-9_]+\.sql$")
DEFAULT_MIGRATION_DIRECTORY = Path(__file__).with_name("migrations") / "sqlite"

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    checksum TEXT NOT NULL CHECK(length(checksum) = 64),
    applied_at TEXT NOT NULL
)
"""

REQUIRED_SCHEMA: dict[str, set[str]] = {
    "users": {"id", "username", "password_hash", "role", "active", "created_at"},
    "workspaces": {"id", "name", "environment", "created_at"},
    "change_requests": {
        "id",
        "workspace_id",
        "title",
        "description",
        "risk",
        "environment",
        "adapter",
        "payload_json",
        "status",
        "requested_by",
        "created_at",
        "updated_at",
    },
    "approvals": {"id", "request_id", "approver_id", "decision", "reason", "created_at"},
    "executions": {
        "id",
        "request_id",
        "status",
        "adapter",
        "output_json",
        "error",
        "idempotency_key",
        "started_at",
        "completed_at",
    },
    "receipts": {
        "id",
        "execution_id",
        "payload_json",
        "previous_hash",
        "receipt_hash",
        "created_at",
    },
    "audit_events": {
        "sequence",
        "id",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "payload_json",
        "previous_hash",
        "event_hash",
        "created_at",
    },
    "runtime_flags": {"key", "value", "updated_by", "updated_at"},
    "auth_rate_limits": {
        "scope",
        "key_hash",
        "failure_count",
        "window_started_at",
        "blocked_until",
        "updated_at",
    },
    "schema_migrations": {"version", "name", "checksum", "applied_at"},
}
REQUIRED_INDEXES = {
    "idx_change_requests_status",
    "idx_executions_status",
    "idx_audit_target",
    "idx_auth_rate_limits_updated",
}


class DatabaseMigrationError(RuntimeError):
    pass


class DatabaseBackendError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SQLiteMigration:
    version: int
    name: str
    checksum: str
    sql: str


def load_sqlite_migrations(
    directory: Path = DEFAULT_MIGRATION_DIRECTORY,
) -> tuple[SQLiteMigration, ...]:
    migrations: list[SQLiteMigration] = []
    for path in sorted(Path(directory).glob("*.sql")):
        match = MIGRATION_PATTERN.fullmatch(path.name)
        if match is None:
            raise DatabaseMigrationError(f"invalid SQLite migration filename: {path.name}")
        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            raise DatabaseMigrationError(f"SQLite migration is empty: {path.name}")
        migrations.append(
            SQLiteMigration(
                version=int(match.group("version")),
                name=path.name,
                checksum=hashlib.sha256(sql.encode()).hexdigest(),
                sql=sql,
            )
        )
    if not migrations:
        raise DatabaseMigrationError("no SQLite migrations were found")
    for expected_version, migration in enumerate(migrations, start=1):
        if migration.version != expected_version:
            raise DatabaseMigrationError(
                f"SQLite migration sequence must be contiguous at version {expected_version}"
            )
    return tuple(migrations)


def iter_sqlite_statements(script: str) -> Iterator[str]:
    buffer: list[str] = []
    for line in script.splitlines(keepends=True):
        buffer.append(line)
        candidate = "".join(buffer)
        if sqlite3.complete_statement(candidate):
            statement = candidate.strip()
            if statement:
                yield statement
            buffer.clear()
    if "".join(buffer).strip():
        raise DatabaseMigrationError("SQLite migration contains an incomplete statement")


class SQLiteProductDatabase:
    backend_name = "sqlite"

    def __init__(self, path: Path, *, migration_directory: Path = DEFAULT_MIGRATION_DIRECTORY):
        self.path = Path(path)
        self.migration_directory = Path(migration_directory)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        migrations = load_sqlite_migrations(self.migration_directory)
        connection = self.connect()
        try:
            connection.execute("BEGIN EXCLUSIVE")
            migration_table_existed = self._table_exists(connection, "schema_migrations")
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if not migration_table_existed and user_version != 0:
                raise DatabaseMigrationError(
                    "SQLite user_version is set but migration history is missing"
                )
            connection.execute(MIGRATION_TABLE_SQL)
            applied = connection.execute(
                "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
            ).fetchall()
            if migration_table_existed:
                recorded_version = int(applied[-1]["version"]) if applied else 0
                if user_version != recorded_version:
                    raise DatabaseMigrationError(
                        "SQLite user_version does not match migration history"
                    )
            if len(applied) > len(migrations):
                raise DatabaseMigrationError("database schema is newer than this application")
            for index, row in enumerate(applied):
                expected = migrations[index]
                if int(row["version"]) != expected.version:
                    raise DatabaseMigrationError("SQLite migration history is not a valid prefix")
                if str(row["name"]) != expected.name or str(row["checksum"]) != expected.checksum:
                    raise DatabaseMigrationError(
                        f"SQLite migration history drift detected at version {expected.version}"
                    )

            for migration in migrations[len(applied) :]:
                for statement in iter_sqlite_statements(migration.sql):
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO schema_migrations(version, name, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        migration.version,
                        migration.name,
                        migration.checksum,
                        datetime.now(UTC).isoformat(timespec="milliseconds"),
                    ),
                )
                connection.execute(f"PRAGMA user_version = {migration.version}")

            self._validate_schema(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def schema_version(self) -> int:
        with self.connect() as connection:
            if not self._table_exists(connection, "schema_migrations"):
                return 0
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            recorded_version = int(row["version"])
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if user_version != recorded_version:
                raise DatabaseMigrationError("SQLite user_version does not match migration history")
            return recorded_version

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        for table, required_columns in REQUIRED_SCHEMA.items():
            columns = {
                str(row["name"])
                for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            if columns != required_columns:
                raise DatabaseMigrationError(
                    f"SQLite schema validation failed for {table}: "
                    f"expected {sorted(required_columns)}, found {sorted(columns)}"
                )
        indexes = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        missing_indexes = REQUIRED_INDEXES - indexes
        if missing_indexes:
            raise DatabaseMigrationError(
                f"SQLite schema validation failed: missing indexes {sorted(missing_indexes)}"
            )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or str(integrity[0]) != "ok":
            raise DatabaseMigrationError("SQLite integrity check failed")


# Preserve the pre-migration import for callers that explicitly selected SQLite.
ProductDatabase = SQLiteProductDatabase


def create_product_database(*, backend: str, path: Path) -> SQLiteProductDatabase:
    if backend == "sqlite":
        return SQLiteProductDatabase(path)
    if backend == "postgresql":
        raise DatabaseBackendError(
            "PostgreSQL backend is not released; VOODOO_DATABASE_BACKEND=sqlite is required"
        )
    raise DatabaseBackendError(f"unsupported database backend: {backend}")
