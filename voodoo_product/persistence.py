from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, Protocol, runtime_checkable

type QueryParameters = Sequence[Any] | Mapping[str, Any]


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


class DatabaseRow(Protocol):
    def __getitem__(self, key: str | int, /) -> Any: ...

    def keys(self) -> list[str]: ...


class DatabaseCursor(Protocol):
    def fetchone(self) -> DatabaseRow | None: ...

    def fetchall(self) -> list[DatabaseRow]: ...


class DatabaseConnection(Protocol):
    def execute(
        self,
        sql: str,
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

    def initialize(self) -> None: ...

    def connect(self) -> DatabaseConnection: ...

    def transaction(self) -> AbstractContextManager[DatabaseConnection]: ...

    def schema_version(self) -> int: ...
