from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path.relative_to(ROOT)} expected one match, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def replace_function(path: Path, name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    node = next(
        (
            item
            for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
        ),
        None,
    )
    if node is None or node.end_lineno is None:
        raise RuntimeError(f"{path.relative_to(ROOT)} missing top-level function {name}")
    lines = text.splitlines(keepends=True)
    replacement_text = replacement.rstrip() + "\n" if replacement else ""
    lines[node.lineno - 1 : node.end_lineno] = [replacement_text]
    path.write_text("".join(lines), encoding="utf-8")


def replace_method(path: Path, class_name: str, method_name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    class_node = next(
        (
            item
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == class_name
        ),
        None,
    )
    if class_node is None:
        raise RuntimeError(f"{path.relative_to(ROOT)} missing class {class_name}")
    node = next(
        (
            item
            for item in class_node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == method_name
        ),
        None,
    )
    if node is None or node.end_lineno is None:
        raise RuntimeError(
            f"{path.relative_to(ROOT)} missing method {class_name}.{method_name}"
        )
    start = min((decorator.lineno for decorator in node.decorator_list), default=node.lineno)
    lines = text.splitlines(keepends=True)
    replacement_text = replacement.rstrip() + "\n" if replacement else ""
    lines[start - 1 : node.end_lineno] = [replacement_text]
    path.write_text("".join(lines), encoding="utf-8")


service = ROOT / "voodoo_product" / "service.py"

replace_once(service, "from datetime import UTC, datetime, timedelta\n", "")
replace_once(
    service,
    "from .adapters import AdapterContext, AdapterError, execute_adapter\n",
    "from .adapters import execute_adapter\n",
)
replace_once(
    service,
    "from .evidence_primitives import canonical_json, chained_hash, new_id, utc_now\n",
    "from .evidence_primitives import canonical_json, chained_hash, new_id, utc_now\n"
    "from .execution import ExecutionService, timestamp_after, timestamp_expired\n",
)
replace_function(service, "timestamp_after", "")
replace_function(service, "timestamp_expired", "")

replace_method(
    service,
    "ProductService",
    "__init__",
    '''    def __init__(
        self,
        config: ProductConfig,
        *,
        database: ProductDatabaseAdapter | None = None,
        audit_ledger: AuditLedger | None = None,
        receipt_ledger: ReceiptLedger | None = None,
        execution_service: ExecutionService | None = None,
    ) -> None:
        self.config = config
        self.db = (
            database
            if database is not None
            else create_product_database(
                backend=self.config.database_backend,
                path=self.config.database_path,
            )
        )
        self.db.initialize()
        resolved_audit_ledger = audit_ledger or AuditLedger(self.db)
        if resolved_audit_ledger.db is not self.db:
            raise ValueError("audit ledger must use the product service database")
        self.audit_ledger = resolved_audit_ledger
        resolved_receipt_ledger = receipt_ledger or ReceiptLedger(self.db)
        if resolved_receipt_ledger.db is not self.db:
            raise ValueError("receipt ledger must use the product service database")
        self.receipt_ledger = resolved_receipt_ledger
        resolved_execution_service = execution_service or ExecutionService(
            database=self.db,
            config=self.config,
            audit_ledger=self.audit_ledger,
            receipt_ledger=self.receipt_ledger,
            adapter_executor=lambda adapter, payload, *, context: execute_adapter(
                adapter,
                payload,
                context=context,
            ),
            id_factory=lambda prefix: new_id(prefix),
            clock=lambda: utc_now(),
            lease_deadline=lambda value, seconds: timestamp_after(value, seconds),
            lease_expired=lambda value, *, now: timestamp_expired(value, now=now),
        )
        if resolved_execution_service.db is not self.db:
            raise ValueError("execution service must use the product service database")
        if resolved_execution_service.config is not self.config:
            raise ValueError("execution service must use the product service configuration")
        if resolved_execution_service.audit_ledger is not self.audit_ledger:
            raise ValueError("execution service must use the product service audit ledger")
        if resolved_execution_service.receipt_ledger is not self.receipt_ledger:
            raise ValueError("execution service must use the product service receipt ledger")
        self.execution_service = resolved_execution_service
        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)
        self._dummy_password_hash = hash_password(
            f"VOODOO-invalid-account-{secrets.token_urlsafe(32)}"
        )
''',
)

replace_method(
    service,
    "ProductService",
    "execute_change_request",
    '''    def execute_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str | None,
        repository_root: Path,
    ) -> dict[str, Any]:
        return self.execution_service.execute_change_request(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            repository_root=repository_root,
        )
''',
)
replace_method(
    service,
    "ProductService",
    "recover_execution",
    '''    def recover_execution(
        self,
        *,
        actor_id: str,
        execution_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return self.execution_service.recover_execution(
            actor_id=actor_id,
            execution_id=execution_id,
            reason=reason,
        )
''',
)
replace_method(
    service,
    "ProductService",
    "list_executions",
    '''    def list_executions(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.execution_service.list_executions(limit=limit)
''',
)
replace_method(
    service,
    "ProductService",
    "get_execution",
    '''    def get_execution(self, execution_id: str) -> dict[str, Any]:
        return self.execution_service.get_execution(execution_id)
''',
)
replace_method(service, "ProductService", "_decode_execution", "")

write(
    ROOT / "voodoo_product" / "execution.py",
    '''from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import statements as sql
from .adapters import AdapterContext, AdapterError, execute_adapter
from .audit import AuditLedger
from .config import ProductConfig
from .evidence_primitives import canonical_json, new_id, utc_now
from .persistence import DatabaseConnection, DatabaseRow, ProductDatabaseAdapter
from .receipt import ReceiptLedger

AdapterExecutor = Callable[..., dict[str, Any]]
IdFactory = Callable[[str], str]
Clock = Callable[[], str]
LeaseDeadline = Callable[[str, int], str]
LeaseExpired = Callable[..., bool]


def timestamp_after(value: str, seconds: int) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("timestamp has no timezone")
    except ValueError as exc:
        raise RuntimeError("execution timestamp is invalid") from exc
    return (parsed + timedelta(seconds=seconds)).astimezone(UTC).isoformat(timespec="milliseconds")


def timestamp_expired(value: str, *, now: str) -> bool:
    try:
        expires_at = datetime.fromisoformat(value)
        current = datetime.fromisoformat(now)
        if expires_at.tzinfo is None or current.tzinfo is None:
            raise ValueError("timestamp has no timezone")
    except ValueError as exc:
        raise RuntimeError("execution lease timestamp is invalid") from exc
    return expires_at <= current


class ExecutionService:
    """Database-bound execution lifecycle, adapter invocation, and recovery boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        config: ProductConfig,
        audit_ledger: AuditLedger,
        receipt_ledger: ReceiptLedger,
        adapter_executor: AdapterExecutor = execute_adapter,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
        lease_deadline: LeaseDeadline = timestamp_after,
        lease_expired: LeaseExpired = timestamp_expired,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("execution service audit ledger must use its database")
        if receipt_ledger.db is not database:
            raise ValueError("execution service receipt ledger must use its database")
        self.db = database
        self.config = config
        self.audit_ledger = audit_ledger
        self.receipt_ledger = receipt_ledger
        self._adapter_executor = adapter_executor
        self._id_factory = id_factory
        self._clock = clock
        self._lease_deadline = lease_deadline
        self._lease_expired = lease_expired

    def execute_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str | None,
        repository_root: Path,
    ) -> dict[str, Any]:
        existing_execution_id: str | None = None
        request_row: DatabaseRow | None = None
        with self.db.transaction() as connection:
            if idempotency_key:
                existing = connection.execute(
                    sql.SELECT_EXECUTION_BY_IDEMPOTENCY_KEY,
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    if str(existing["request_id"]) != request_id:
                        raise RuntimeError("idempotency key is bound to another request")
                    existing_execution_id = str(existing["id"])

            if existing_execution_id is None:
                if self._emergency_stop(connection):
                    raise PermissionError("emergency stop is active")
                request_row = connection.execute(
                    sql.SELECT_CHANGE_REQUEST_FOR_EXECUTION,
                    (request_id,),
                ).fetchone()
                if request_row is None:
                    raise LookupError("change request not found")
                self._require_workspace_environment(request_row)
                if request_row["status"] != "APPROVED":
                    raise PermissionError("change request is not approved")
                if (
                    request_row["environment"] == "production"
                    and not self.config.production_effects_enabled
                ):
                    raise PermissionError("production effects remain disabled")
                execution_id = self._id_factory("exec")
                execution_fence = 1
                now = self._clock()
                lease_expires_at = self._lease_deadline(
                    now,
                    self.config.execution_lease_seconds,
                )
                connection.execute(
                    sql.INSERT_EXECUTION,
                    (
                        execution_id,
                        request_id,
                        request_row["adapter"],
                        idempotency_key,
                        now,
                        lease_expires_at,
                    ),
                )
                connection.execute(
                    sql.MARK_CHANGE_REQUEST_RUNNING,
                    (now, request_id),
                )
                self.audit_ledger.append(
                    connection,
                    actor_id=actor_id,
                    action="execution.start",
                    target_type="execution",
                    target_id=execution_id,
                    payload={"request_id": request_id, "adapter": request_row["adapter"]},
                )

        if existing_execution_id is not None:
            return self.get_execution(existing_execution_id)
        if request_row is None:
            raise RuntimeError("execution start transaction did not produce a request")

        try:
            output = self._adapter_executor(
                str(request_row["adapter"]),
                json.loads(str(request_row["payload_json"])),
                context=AdapterContext(
                    workspace_id=str(request_row["workspace_id"]),
                    repository_root=repository_root.resolve(),
                    sandbox_root=self.config.sandbox_root,
                    timeout_seconds=self.config.execution_timeout_seconds,
                ),
            )
            if output.get("success") is False:
                raise AdapterError("validation adapter returned non-zero status")
            status = "SUCCEEDED"
            error = None
        except Exception as exc:
            output = {"error_type": type(exc).__name__}
            status = "FAILED"
            error = str(exc)[:2000]

        with self.db.transaction() as connection:
            completed_at = self._clock()
            completed = connection.execute(
                sql.COMPLETE_EXECUTION,
                (
                    status,
                    canonical_json(output),
                    error,
                    completed_at,
                    execution_id,
                    execution_fence,
                ),
            ).fetchone()
            if completed is not None:
                request_status = "COMPLETED" if status == "SUCCEEDED" else "FAILED"
                connection.execute(
                    sql.MARK_CHANGE_REQUEST_COMPLETED,
                    (request_status, completed_at, request_id),
                )
                receipt = self.receipt_ledger.append(
                    connection,
                    execution_id=execution_id,
                    payload={
                        "execution_id": execution_id,
                        "request_id": request_id,
                        "workspace_id": request_row["workspace_id"],
                        "actor_id": actor_id,
                        "adapter": request_row["adapter"],
                        "risk": request_row["risk"],
                        "environment": request_row["environment"],
                        "status": status,
                        "output_digest": hashlib.sha256(
                            canonical_json(output).encode("utf-8")
                        ).hexdigest(),
                        "completed_at": completed_at,
                    },
                )
                self.audit_ledger.append(
                    connection,
                    actor_id=actor_id,
                    action=f"execution.{status.lower()}",
                    target_type="execution",
                    target_id=execution_id,
                    payload={
                        "request_id": request_id,
                        "receipt_id": receipt["id"],
                        "error": error,
                    },
                )
        return self.get_execution(execution_id)

    def recover_execution(
        self,
        *,
        actor_id: str,
        execution_id: str,
        reason: str,
    ) -> dict[str, Any]:
        normalized_reason = reason.strip()
        if not 3 <= len(normalized_reason) <= 2_000:
            raise ValueError("recovery reason must contain 3 to 2000 characters")

        with self.db.transaction() as connection:
            if not self._emergency_stop(connection):
                raise PermissionError("emergency stop must be active for execution recovery")
            execution = connection.execute(
                sql.SELECT_EXECUTION_FOR_RECOVERY,
                (execution_id,),
            ).fetchone()
            if execution is None:
                raise LookupError("execution not found")
            if execution["status"] != "RUNNING":
                raise RuntimeError("execution is not running")

            now = self._clock()
            raw_lease = execution["lease_expires_at"]
            lease_expires_at = str(raw_lease) if raw_lease is not None else None
            if lease_expires_at is not None and not self._lease_expired(
                lease_expires_at,
                now=now,
            ):
                raise RuntimeError("execution lease has not expired")

            output = {"error_type": "ExecutionInterrupted", "outcome": "INDETERMINATE"}
            error = "execution outcome is indeterminate after lease expiry"
            interrupted = connection.execute(
                sql.INTERRUPT_EXECUTION,
                (
                    canonical_json(output),
                    error,
                    now,
                    execution_id,
                    int(execution["fence"]),
                    lease_expires_at,
                ),
            ).fetchone()
            if interrupted is None:
                raise RuntimeError("execution changed during recovery")

            request_id = str(execution["request_id"])
            connection.execute(
                sql.MARK_CHANGE_REQUEST_COMPLETED,
                ("FAILED", now, request_id),
            )
            receipt = self.receipt_ledger.append(
                connection,
                execution_id=execution_id,
                payload={
                    "execution_id": execution_id,
                    "request_id": request_id,
                    "workspace_id": execution["workspace_id"],
                    "actor_id": actor_id,
                    "adapter": execution["adapter"],
                    "risk": execution["risk"],
                    "environment": execution["environment"],
                    "status": "INTERRUPTED",
                    "outcome": "INDETERMINATE",
                    "output_digest": hashlib.sha256(
                        canonical_json(output).encode("utf-8")
                    ).hexdigest(),
                    "completed_at": now,
                },
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="execution.interrupted",
                target_type="execution",
                target_id=execution_id,
                payload={
                    "request_id": request_id,
                    "receipt_id": receipt["id"],
                    "outcome": "INDETERMINATE",
                    "reason": normalized_reason,
                },
            )
        return self.get_execution(execution_id)

    def list_executions(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_EXECUTIONS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode_execution(dict(row)) for row in rows]

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.GET_EXECUTION,
                (execution_id,),
            ).fetchone()
        if row is None:
            raise LookupError("execution not found")
        return self._decode_execution(dict(row))

    @staticmethod
    def _emergency_stop(connection: DatabaseConnection) -> bool:
        row = connection.execute(sql.SELECT_EMERGENCY_STOP).fetchone()
        return bool(row and str(row["value"]).lower() == "true")

    @staticmethod
    def _require_workspace_environment(value: DatabaseRow) -> None:
        request_environment = str(value["environment"])
        workspace_environment = str(value["workspace_environment"])
        valid_environments = {"local", "development", "staging", "production"}
        if (
            request_environment not in valid_environments
            or workspace_environment not in valid_environments
        ):
            raise RuntimeError("change request environment boundary is invalid")
        if request_environment != workspace_environment:
            raise RuntimeError("change request environment does not match workspace")

    @staticmethod
    def _decode_execution(value: dict[str, Any]) -> dict[str, Any]:
        value["output"] = json.loads(value.pop("output_json"))
        value.pop("fence", None)
        return value
''',
)

composition = ROOT / "voodoo_product" / "composition.py"
replace_once(
    composition,
    "from .external_identity_service import GovernedExternalIdentityService\n",
    "from .execution import ExecutionService\n"
    "from .external_identity_service import GovernedExternalIdentityService\n",
)
replace_once(
    composition,
    '''class ProductComposition:
    service: ProductService
    audit_ledger: AuditLedger
    receipt_ledger: ReceiptLedger
    external_identity_service: GovernedExternalIdentityService
''',
    '''class ProductComposition:
    service: ProductService
    audit_ledger: AuditLedger
    receipt_ledger: ReceiptLedger
    execution_service: ExecutionService
    external_identity_service: GovernedExternalIdentityService
''',
)
replace_once(
    composition,
    '''    service = ProductService(resolved_config)
    audit_ledger = service.audit_ledger
    receipt_ledger = service.receipt_ledger
''',
    '''    service = ProductService(resolved_config)
    audit_ledger = service.audit_ledger
    receipt_ledger = service.receipt_ledger
    execution_service = service.execution_service
''',
)
replace_once(
    composition,
    '''    composition = ProductComposition(
        service=service,
        audit_ledger=audit_ledger,
        receipt_ledger=receipt_ledger,
        external_identity_service=external_identity_service,
    )
''',
    '''    composition = ProductComposition(
        service=service,
        audit_ledger=audit_ledger,
        receipt_ledger=receipt_ledger,
        execution_service=execution_service,
        external_identity_service=external_identity_service,
    )
''',
)
replace_once(
    composition,
    '''    app.state.voodoo_audit_ledger = audit_ledger
    app.state.voodoo_receipt_ledger = receipt_ledger
    app.state.voodoo_external_identity_service = external_identity_service
''',
    '''    app.state.voodoo_audit_ledger = audit_ledger
    app.state.voodoo_receipt_ledger = receipt_ledger
    app.state.voodoo_execution_service = execution_service
    app.state.voodoo_external_identity_service = external_identity_service
''',
)

composition_test = ROOT / "tests" / "system" / "test_product_composition.py"
replace_once(
    composition_test,
    "def test_composition_shares_database_and_evidence_ledgers_without_public_routes(\n",
    "def test_composition_shares_database_and_runtime_dependencies_without_public_routes(\n",
)
replace_once(
    composition_test,
    '''    assert app.state.voodoo_audit_ledger is composition.audit_ledger
    assert app.state.voodoo_receipt_ledger is composition.receipt_ledger
    assert app.state.voodoo_external_identity_service is composition.external_identity_service
''',
    '''    assert app.state.voodoo_audit_ledger is composition.audit_ledger
    assert app.state.voodoo_receipt_ledger is composition.receipt_ledger
    assert app.state.voodoo_execution_service is composition.execution_service
    assert app.state.voodoo_external_identity_service is composition.external_identity_service
''',
)
replace_once(
    composition_test,
    '''    assert composition.service.audit_ledger is composition.audit_ledger
    assert composition.service.receipt_ledger is composition.receipt_ledger
    assert composition.audit_ledger.db is composition.service.db
    assert composition.receipt_ledger.db is composition.service.db
''',
    '''    assert composition.service.audit_ledger is composition.audit_ledger
    assert composition.service.receipt_ledger is composition.receipt_ledger
    assert composition.service.execution_service is composition.execution_service
    assert composition.audit_ledger.db is composition.service.db
    assert composition.receipt_ledger.db is composition.service.db
    assert composition.execution_service.db is composition.service.db
    assert composition.execution_service.config is composition.service.config
    assert composition.execution_service.audit_ledger is composition.audit_ledger
    assert composition.execution_service.receipt_ledger is composition.receipt_ledger
''',
)

replace_once(
    ROOT / "tests" / "system" / "test_statement_catalog.py",
    "    assert len(execute_calls) == 43\n",
    "    assert len(execute_calls) == 32\n",
)

write(
    ROOT / "tests" / "system" / "test_execution_service.py",
    '''from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.execution import ExecutionService
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]
EXECUTION_STATEMENTS = {
    "SELECT_EXECUTION_BY_IDEMPOTENCY_KEY",
    "SELECT_CHANGE_REQUEST_FOR_EXECUTION",
    "INSERT_EXECUTION",
    "MARK_CHANGE_REQUEST_RUNNING",
    "COMPLETE_EXECUTION",
    "MARK_CHANGE_REQUEST_COMPLETED",
    "SELECT_EXECUTION_FOR_RECOVERY",
    "INTERRUPT_EXECUTION",
    "LIST_EXECUTIONS",
    "GET_EXECUTION",
}


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_execution_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "execution.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 12
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_service_delegates_complete_execution_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "execute_change_request",
            "recover_execution",
            "list_executions",
            "get_execution",
        }
    }

    assert set(methods) == {
        "execute_change_request",
        "recover_execution",
        "list_executions",
        "get_execution",
    }
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.execution_service.execute_change_request" in source_text
    assert "self.execution_service.recover_execution" in source_text
    assert "self.execution_service.list_executions" in source_text
    assert "self.execution_service.get_execution" in source_text
    for statement in EXECUTION_STATEMENTS:
        assert f"sql.{statement}" not in source_text


def test_execution_service_rejects_evidence_ledgers_from_other_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="execution service audit ledger must use its database",
    ):
        ExecutionService(
            database=first.db,
            config=first.config,
            audit_ledger=second.audit_ledger,
            receipt_ledger=first.receipt_ledger,
        )

    with pytest.raises(
        ValueError,
        match="execution service receipt ledger must use its database",
    ):
        ExecutionService(
            database=first.db,
            config=first.config,
            audit_ledger=first.audit_ledger,
            receipt_ledger=second.receipt_ledger,
        )


def test_product_service_rejects_execution_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="execution service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            execution_service=second.execution_service,
        )


def test_execution_service_preserves_product_service_contract(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
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
        title="Execution service compatibility",
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
        reason="execution service compatibility test",
    )

    execution = service.execute_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        idempotency_key="execution-service-compatibility",
        repository_root=tmp_path,
    )

    assert service.get_execution(execution["id"]) == service.execution_service.get_execution(
        execution["id"]
    )
    assert service.list_executions() == service.execution_service.list_executions()
    assert execution["status"] == "SUCCEEDED"
    assert service.verify_receipt_chain()["valid"] is True
    assert service.verify_audit_chain()["valid"] is True
''',
)

readiness = ROOT / "scripts" / "product_readiness_gate.py"
replace_once(
    readiness,
    '    "voodoo_product/evidence_primitives.py",\n    "voodoo_product/external_identity.py",\n',
    '    "voodoo_product/evidence_primitives.py",\n    "voodoo_product/execution.py",\n'
    '    "voodoo_product/external_identity.py",\n',
)
replace_once(
    readiness,
    '    "tests/system/test_execution_recovery.py",\n    "tests/system/test_external_identity_binding.py",\n',
    '    "tests/system/test_execution_recovery.py",\n'
    '    "tests/system/test_execution_service.py",\n'
    '    "tests/system/test_external_identity_binding.py",\n',
)
replace_once(
    readiness,
    '    "docs/product/EXTERNAL_IDENTITY_BINDING_BOUNDARY.md",\n',
    '    "docs/product/EXECUTION_SERVICE_COMPOSITION_BOUNDARY.md",\n'
    '    "docs/product/EXTERNAL_IDENTITY_BINDING_BOUNDARY.md",\n',
)

write(
    ROOT / "docs" / "product" / "EXECUTION_SERVICE_COMPOSITION_BOUNDARY.md",
    '''# Execution Service Composition Boundary

## Status

Implemented as the canonical execution lifecycle and recovery boundary.

## Purpose

`ExecutionService` owns durable execution start, idempotency binding, lease and fence handling, adapter invocation, completion, receipt evidence, audit evidence, incident recovery, and execution reads.

`ProductService` preserves the existing public method surface and delegates the complete execution domain to one database-bound service.

## Runtime composition

`install_composed_product_platform` creates one `ProductService` with:

- one shared database adapter;
- one shared `AuditLedger`;
- one shared `ReceiptLedger`;
- one shared `ExecutionService`;
- one governed external identity service.

The execution service is exposed internally through `ProductComposition` and `app.state.voodoo_execution_service`. No public route is added or changed.

## Delegation contract

- `execute_change_request` delegates to `ExecutionService.execute_change_request`;
- `recover_execution` delegates to `ExecutionService.recover_execution`;
- `list_executions` delegates to `ExecutionService.list_executions`;
- `get_execution` delegates to `ExecutionService.get_execution`.

`ProductService` contains no direct execution lifecycle SQL after composition.

## Safety invariants

The boundary preserves:

- idempotency keys bound to exactly one change request;
- emergency-stop enforcement before new execution;
- workspace and request environment equality;
- production effects disabled unless explicitly configured;
- durable start before adapter invocation;
- lease expiry and fence checks during recovery;
- late-worker completion rejection;
- receipt and audit append in the completion or recovery transaction;
- indeterminate interrupted outcome semantics;
- existing response fields and error behavior.

An injected execution service must use the exact product database, configuration, audit ledger, and receipt ledger instances. Mismatches fail closed during construction.

## Compatibility

The product service continues to expose the same API methods. Existing adapter monkeypatch behavior remains supported through an injected adapter executor bridge. No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, enable external sign-in, release, deploy, or enable production effects.
''',
)

for path in [
    service,
    ROOT / "voodoo_product" / "execution.py",
    composition,
    composition_test,
    ROOT / "tests" / "system" / "test_execution_service.py",
    ROOT / "tests" / "system" / "test_statement_catalog.py",
    readiness,
]:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

service_text = service.read_text(encoding="utf-8")
for statement in [
    "SELECT_EXECUTION_BY_IDEMPOTENCY_KEY",
    "SELECT_CHANGE_REQUEST_FOR_EXECUTION",
    "INSERT_EXECUTION",
    "MARK_CHANGE_REQUEST_RUNNING",
    "COMPLETE_EXECUTION",
    "MARK_CHANGE_REQUEST_COMPLETED",
    "SELECT_EXECUTION_FOR_RECOVERY",
    "INTERRUPT_EXECUTION",
    "LIST_EXECUTIONS",
    "GET_EXECUTION",
]:
    if f"sql.{statement}" in service_text:
        raise RuntimeError(f"service still owns execution statement {statement}")
