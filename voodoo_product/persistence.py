from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Literal, Protocol, runtime_checkable

type QueryParameters = Sequence[Any] | Mapping[str, Any]
type StatementMode = Literal["read", "write"]


class DatabaseError(Exception):
    """Base class for persistence failures safe to handle outside an adapter."""


class DatabaseOperationError(DatabaseError):
    """A database operation failed without exposing backend-specific details."""


class DatabaseIntegrityError(DatabaseOperationError):
    """A write violated a database integrity constraint."""


class DatabaseMigrationError(DatabaseError):
    """Database migration history or schema validation failed."""


class DatabaseBackendError(DatabaseError):
    """The configured database backend cannot be safely started."""


class DatabaseStatementError(DatabaseOperationError):
    """A statement is invalid or unavailable for the configured backend."""


@dataclass(frozen=True, slots=True)
class DatabaseStatement:
    name: str
    mode: StatementMode
    sqlite_sql: str
    postgresql_sql: str | None = None

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_.]*", self.name) is None:
            raise ValueError("database statement name is invalid")
        if self.mode not in {"read", "write"}:
            raise ValueError("database statement mode is invalid")
        for attribute in ("sqlite_sql", "postgresql_sql"):
            sql = getattr(self, attribute)
            if sql is not None:
                normalized = sql.strip()
                if not normalized or "\0" in normalized:
                    raise ValueError("database statement SQL is invalid")
                object.__setattr__(self, attribute, normalized)

    def for_backend(self, backend: str) -> str:
        if backend == "sqlite":
            sql = self.sqlite_sql
        elif backend == "postgresql":
            sql = self.postgresql_sql
        else:
            raise DatabaseStatementError("database statement backend is unsupported")
        if sql is None:
            raise DatabaseStatementError(
                f"database statement {self.name} is unavailable for backend {backend}"
            )
        return sql


type SQLInput = str | DatabaseStatement


class DatabaseRow(Protocol):
    def __getitem__(self, key: str | int, /) -> Any: ...

    def keys(self) -> list[str]: ...


class DatabaseCursor(Protocol):
    def fetchone(self) -> DatabaseRow | None: ...

    def fetchall(self) -> list[DatabaseRow]: ...


class DatabaseConnection(Protocol):
    def execute(
        self,
        statement: SQLInput,
        parameters: QueryParameters = (),
        /,
    ) -> DatabaseCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> DatabaseConnection: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool: ...


@runtime_checkable
class ProductDatabaseAdapter(Protocol):
    backend_name: str
    write_serialization: str

    def initialize(self) -> None: ...

    def connect(self) -> DatabaseConnection: ...

    def transaction(self) -> AbstractContextManager[DatabaseConnection]: ...

    def schema_version(self) -> int: ...
