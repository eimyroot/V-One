from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from pathlib import Path
from threading import Barrier
from types import TracebackType
from typing import Any

from voodoo_product import statements as sql
from voodoo_product.config import ProductConfig
from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.persistence import (
    DatabaseConnection,
    DatabaseCursor,
    QueryParameters,
    SQLInput,
)
from voodoo_product.service import ProductService


class _PreflightBarrierConnection:
    def __init__(self, connection: DatabaseConnection, barrier: Barrier):
        self._connection = connection
        self._barrier = barrier

    def execute(
        self,
        statement: SQLInput,
        parameters: QueryParameters = (),
        /,
    ) -> DatabaseCursor:
        cursor = self._connection.execute(statement, parameters)
        if statement is sql.SELECT_EXECUTION_BY_IDEMPOTENCY_KEY:
            self._barrier.wait(timeout=5)
        return cursor

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> _PreflightBarrierConnection:
        self._connection.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return self._connection.__exit__(exc_type, exc_value, traceback)


class _PreflightSynchronizingDatabase:
    backend_name = "sqlite"
    write_serialization = "global"

    def __init__(self, path: Path, barrier: Barrier):
        self._database = SQLiteProductDatabase(path)
        self._barrier = barrier

    def initialize(self) -> None:
        self._database.initialize()

    def connect(self) -> DatabaseConnection:
        return _PreflightBarrierConnection(self._database.connect(), self._barrier)

    def transaction(self) -> AbstractContextManager[DatabaseConnection]:
        return self._database.transaction()

    def schema_version(self) -> int:
        return self._database.schema_version()


def test_concurrent_idempotency_key_creates_one_execution(tmp_path: Path) -> None:
    database = _PreflightSynchronizingDatabase(
        tmp_path / "product.sqlite3",
        Barrier(2),
    )
    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        ),
        database=database,
    )
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    operator = service.create_user(
        actor_id=bootstrap["user_id"],
        username="operator",
        password="VeryStrongOperatorPassword1!",
        role="operator",
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Concurrent idempotency",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"value": 1},
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="concurrency regression test",
    )

    start = Barrier(3)

    def execute() -> dict[str, Any]:
        start.wait(timeout=5)
        return service.execute_change_request(
            actor_id=operator["id"],
            request_id=request["id"],
            idempotency_key="concurrent-stable-key",
            repository_root=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(execute) for _ in range(2)]
        start.wait(timeout=5)
        results = [future.result(timeout=10) for future in futures]

    execution_ids = {result["id"] for result in results}
    assert len(execution_ids) == 1
    execution_id = execution_ids.pop()
    assert service.get_execution(execution_id)["status"] == "SUCCEEDED"
    assert [row["id"] for row in service.list_executions()] == [execution_id]
    assert len(service.list_receipts()) == 1
    actions = [row["action"] for row in service.list_audit_events(limit=1000)]
    assert actions.count("execution.start") == 1
    assert actions.count("execution.succeeded") == 1
