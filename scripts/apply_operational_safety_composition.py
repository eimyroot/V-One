from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(
            f"{path.relative_to(ROOT)} expected {count} matches, found {actual}: {old!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


def write(path: Path, content: str) -> None:
    if not content.endswith("\n"):
        content += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


service = ROOT / "voodoo_product" / "service.py"
replace_exact(
    service,
    "from .execution import ExecutionService, timestamp_after, timestamp_expired\nfrom .persistence import (\n",
    "from .execution import ExecutionService, timestamp_after, timestamp_expired\n"
    "from .operational_safety import OperationalSafetyService\n"
    "from .persistence import (\n",
)
replace_exact(
    service,
    "        receipt_ledger: ReceiptLedger | None = None,\n"
    "        execution_service: ExecutionService | None = None,\n",
    "        receipt_ledger: ReceiptLedger | None = None,\n"
    "        operational_safety_service: OperationalSafetyService | None = None,\n"
    "        execution_service: ExecutionService | None = None,\n",
)
replace_exact(
    service,
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_receipt_ledger = receipt_ledger or ReceiptLedger(self.db)\n",
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_operational_safety_service = (\n"
    "            operational_safety_service\n"
    "            or OperationalSafetyService(\n"
    "                database=self.db,\n"
    "                audit_ledger=self.audit_ledger,\n"
    "                clock=lambda: utc_now(),\n"
    "            )\n"
    "        )\n"
    "        if resolved_operational_safety_service.db is not self.db:\n"
    "            raise ValueError(\n"
    "                \"operational safety service must use the product service database\"\n"
    "            )\n"
    "        if resolved_operational_safety_service.audit_ledger is not self.audit_ledger:\n"
    "            raise ValueError(\n"
    "                \"operational safety service must use the product service audit ledger\"\n"
    "            )\n"
    "        self.operational_safety_service = resolved_operational_safety_service\n"
    "        resolved_receipt_ledger = receipt_ledger or ReceiptLedger(self.db)\n",
)
replace_exact(
    service,
    "            receipt_ledger=self.receipt_ledger,\n"
    "            adapter_executor=lambda adapter, payload, *, context: execute_adapter(\n",
    "            receipt_ledger=self.receipt_ledger,\n"
    "            operational_safety_service=self.operational_safety_service,\n"
    "            adapter_executor=lambda adapter, payload, *, context: execute_adapter(\n",
)
replace_exact(
    service,
    "        if resolved_execution_service.receipt_ledger is not self.receipt_ledger:\n"
    "            raise ValueError(\"execution service must use the product service receipt ledger\")\n"
    "        self.execution_service = resolved_execution_service\n",
    "        if resolved_execution_service.receipt_ledger is not self.receipt_ledger:\n"
    "            raise ValueError(\"execution service must use the product service receipt ledger\")\n"
    "        if (\n"
    "            resolved_execution_service.operational_safety_service\n"
    "            is not self.operational_safety_service\n"
    "        ):\n"
    "            raise ValueError(\n"
    "                \"execution service must use the product operational safety service\"\n"
    "            )\n"
    "        self.execution_service = resolved_execution_service\n",
)
replace_exact(
    service,
    "            stop = self._emergency_stop(connection)\n",
    "            stop = self.operational_safety_service.is_active(connection)\n",
    count=2,
)
replace_exact(
    service,
    "    def set_emergency_stop(self, *, actor_id: str, active: bool, reason: str) -> dict[str, Any]:\n"
    "        with self.db.transaction() as connection:\n"
    "            now = utc_now()\n"
    "            connection.execute(\n"
    "                sql.UPSERT_EMERGENCY_STOP,\n"
    "                (\"true\" if active else \"false\", actor_id, now),\n"
    "            )\n"
    "            self._append_audit(\n"
    "                connection,\n"
    "                actor_id=actor_id,\n"
    "                action=\"system.emergency_stop.activate\"\n"
    "                if active\n"
    "                else \"system.emergency_stop.clear\",\n"
    "                target_type=\"system\",\n"
    "                target_id=\"runtime\",\n"
    "                payload={\"reason\": reason},\n"
    "            )\n"
    "        return {\"emergency_stop\": active, \"reason\": reason, \"updated_at\": now}\n",
    "    def set_emergency_stop(self, *, actor_id: str, active: bool, reason: str) -> dict[str, Any]:\n"
    "        return self.operational_safety_service.set_emergency_stop(\n"
    "            actor_id=actor_id,\n"
    "            active=active,\n"
    "            reason=reason,\n"
    "        )\n",
)
replace_exact(
    service,
    "    @staticmethod\n"
    "    def _emergency_stop(connection: DatabaseConnection) -> bool:\n"
    "        row = connection.execute(sql.SELECT_EMERGENCY_STOP).fetchone()\n"
    "        return bool(row and str(row[\"value\"]).lower() == \"true\")\n\n",
    "",
)

execution = ROOT / "voodoo_product" / "execution.py"
replace_exact(
    execution,
    "from .evidence_primitives import canonical_json, new_id, utc_now\n"
    "from .persistence import DatabaseConnection, DatabaseRow, ProductDatabaseAdapter\n",
    "from .evidence_primitives import canonical_json, new_id, utc_now\n"
    "from .operational_safety import OperationalSafetyService\n"
    "from .persistence import DatabaseConnection, DatabaseRow, ProductDatabaseAdapter\n",
)
replace_exact(
    execution,
    "        audit_ledger: AuditLedger,\n"
    "        receipt_ledger: ReceiptLedger,\n"
    "        adapter_executor: AdapterExecutor = execute_adapter,\n",
    "        audit_ledger: AuditLedger,\n"
    "        receipt_ledger: ReceiptLedger,\n"
    "        operational_safety_service: OperationalSafetyService,\n"
    "        adapter_executor: AdapterExecutor = execute_adapter,\n",
)
replace_exact(
    execution,
    "        if receipt_ledger.db is not database:\n"
    "            raise ValueError(\"execution service receipt ledger must use its database\")\n"
    "        self.db = database\n"
    "        self.config = config\n"
    "        self.audit_ledger = audit_ledger\n"
    "        self.receipt_ledger = receipt_ledger\n",
    "        if receipt_ledger.db is not database:\n"
    "            raise ValueError(\"execution service receipt ledger must use its database\")\n"
    "        if operational_safety_service.db is not database:\n"
    "            raise ValueError(\"execution operational safety service must use its database\")\n"
    "        if operational_safety_service.audit_ledger is not audit_ledger:\n"
    "            raise ValueError(\n"
    "                \"execution operational safety service must use its audit ledger\"\n"
    "            )\n"
    "        self.db = database\n"
    "        self.config = config\n"
    "        self.audit_ledger = audit_ledger\n"
    "        self.receipt_ledger = receipt_ledger\n"
    "        self.operational_safety_service = operational_safety_service\n",
)
replace_exact(
    execution,
    "if self._emergency_stop(connection):",
    "if self.operational_safety_service.is_active(connection):",
    count=2,
)
replace_exact(
    execution,
    "    @staticmethod\n"
    "    def _emergency_stop(connection: DatabaseConnection) -> bool:\n"
    "        row = connection.execute(sql.SELECT_EMERGENCY_STOP).fetchone()\n"
    "        return bool(row and str(row[\"value\"]).lower() == \"true\")\n\n",
    "",
)

composition = ROOT / "voodoo_product" / "composition.py"
replace_exact(
    composition,
    "from .observability import (\n"
    "    StructuredRequestLoggingMiddleware,\n"
    "    configure_product_logging,\n"
    ")\n"
    "from .receipt import ReceiptLedger\n",
    "from .observability import (\n"
    "    StructuredRequestLoggingMiddleware,\n"
    "    configure_product_logging,\n"
    ")\n"
    "from .operational_safety import OperationalSafetyService\n"
    "from .receipt import ReceiptLedger\n",
)
replace_exact(
    composition,
    "    receipt_ledger: ReceiptLedger\n"
    "    execution_service: ExecutionService\n",
    "    receipt_ledger: ReceiptLedger\n"
    "    operational_safety_service: OperationalSafetyService\n"
    "    execution_service: ExecutionService\n",
)
replace_exact(
    composition,
    "    receipt_ledger = service.receipt_ledger\n"
    "    execution_service = service.execution_service\n",
    "    receipt_ledger = service.receipt_ledger\n"
    "    operational_safety_service = service.operational_safety_service\n"
    "    execution_service = service.execution_service\n",
)
replace_exact(
    composition,
    "        receipt_ledger=receipt_ledger,\n"
    "        execution_service=execution_service,\n",
    "        receipt_ledger=receipt_ledger,\n"
    "        operational_safety_service=operational_safety_service,\n"
    "        execution_service=execution_service,\n",
)
replace_exact(
    composition,
    "    app.state.voodoo_receipt_ledger = receipt_ledger\n"
    "    app.state.voodoo_execution_service = execution_service\n",
    "    app.state.voodoo_receipt_ledger = receipt_ledger\n"
    "    app.state.voodoo_operational_safety_service = operational_safety_service\n"
    "    app.state.voodoo_execution_service = execution_service\n",
)

write(
    ROOT / "voodoo_product" / "operational_safety.py",
    '''from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import utc_now
from .persistence import DatabaseConnection, ProductDatabaseAdapter

Clock = Callable[[], str]


class OperationalSafetyService:
    """Shared emergency-stop state and audited transition boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        clock: Clock = utc_now,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("operational safety audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._clock = clock

    def is_active(self, connection: DatabaseConnection | None = None) -> bool:
        if connection is not None:
            return self._read(connection)
        with self.db.connect() as resolved_connection:
            return self._read(resolved_connection)

    def set_emergency_stop(
        self,
        *,
        actor_id: str,
        active: bool,
        reason: str,
    ) -> dict[str, Any]:
        with self.db.transaction() as connection:
            now = self._clock()
            connection.execute(
                sql.UPSERT_EMERGENCY_STOP,
                ("true" if active else "false", actor_id, now),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action=(
                    "system.emergency_stop.activate"
                    if active
                    else "system.emergency_stop.clear"
                ),
                target_type="system",
                target_id="runtime",
                payload={"reason": reason},
            )
        return {"emergency_stop": active, "reason": reason, "updated_at": now}

    @staticmethod
    def _read(connection: DatabaseConnection) -> bool:
        row = connection.execute(sql.SELECT_EMERGENCY_STOP).fetchone()
        return bool(row and str(row["value"]).lower() == "true")
''',
)

execution_test = ROOT / "tests" / "system" / "test_execution_service.py"
replace_exact(execution_test, "    assert len(execute_calls) == 12\n", "    assert len(execute_calls) == 11\n")
replace_exact(
    execution_test,
    "            receipt_ledger=first.receipt_ledger,\n"
    "        )\n\n"
    "    with pytest.raises(\n"
    "        ValueError,\n"
    "        match=\"execution service receipt ledger must use its database\",\n",
    "            receipt_ledger=first.receipt_ledger,\n"
    "            operational_safety_service=first.operational_safety_service,\n"
    "        )\n\n"
    "    with pytest.raises(\n"
    "        ValueError,\n"
    "        match=\"execution service receipt ledger must use its database\",\n",
)
replace_exact(
    execution_test,
    "            audit_ledger=first.audit_ledger,\n"
    "            receipt_ledger=second.receipt_ledger,\n"
    "        )\n",
    "            audit_ledger=first.audit_ledger,\n"
    "            receipt_ledger=second.receipt_ledger,\n"
    "            operational_safety_service=first.operational_safety_service,\n"
    "        )\n",
)
replace_exact(
    execution_test,
    "    for statement in EXECUTION_STATEMENTS:\n"
    "        assert f\"sql.{statement}\" not in source_text\n",
    "    for statement in EXECUTION_STATEMENTS:\n"
    "        assert f\"sql.{statement}\" not in source_text\n"
    "    assert \"sql.SELECT_EMERGENCY_STOP\" not in source_text\n",
)

composition_test = ROOT / "tests" / "system" / "test_product_composition.py"
replace_exact(
    composition_test,
    "    assert app.state.voodoo_receipt_ledger is composition.receipt_ledger\n"
    "    assert app.state.voodoo_execution_service is composition.execution_service\n",
    "    assert app.state.voodoo_receipt_ledger is composition.receipt_ledger\n"
    "    assert (\n"
    "        app.state.voodoo_operational_safety_service\n"
    "        is composition.operational_safety_service\n"
    "    )\n"
    "    assert app.state.voodoo_execution_service is composition.execution_service\n",
)
replace_exact(
    composition_test,
    "    assert composition.service.receipt_ledger is composition.receipt_ledger\n"
    "    assert composition.service.execution_service is composition.execution_service\n",
    "    assert composition.service.receipt_ledger is composition.receipt_ledger\n"
    "    assert (\n"
    "        composition.service.operational_safety_service\n"
    "        is composition.operational_safety_service\n"
    "    )\n"
    "    assert composition.service.execution_service is composition.execution_service\n",
)
replace_exact(
    composition_test,
    "    assert composition.receipt_ledger.db is composition.service.db\n"
    "    assert composition.execution_service.db is composition.service.db\n",
    "    assert composition.receipt_ledger.db is composition.service.db\n"
    "    assert composition.operational_safety_service.db is composition.service.db\n"
    "    assert (\n"
    "        composition.operational_safety_service.audit_ledger\n"
    "        is composition.audit_ledger\n"
    "    )\n"
    "    assert composition.execution_service.db is composition.service.db\n",
)
replace_exact(
    composition_test,
    "    assert composition.execution_service.receipt_ledger is composition.receipt_ledger\n"
    "    assert composition.external_identity_service.db is composition.service.db\n",
    "    assert composition.execution_service.receipt_ledger is composition.receipt_ledger\n"
    "    assert (\n"
    "        composition.execution_service.operational_safety_service\n"
    "        is composition.operational_safety_service\n"
    "    )\n"
    "    assert composition.external_identity_service.db is composition.service.db\n",
)

statement_test = ROOT / "tests" / "system" / "test_statement_catalog.py"
replace_exact(statement_test, "    assert len(execute_calls) == 32\n", "    assert len(execute_calls) == 30\n")

readiness = ROOT / "scripts" / "product_readiness_gate.py"
replace_exact(
    readiness,
    '    "voodoo_product/observability.py",\n    "voodoo_product/persistence.py",\n',
    '    "voodoo_product/observability.py",\n    "voodoo_product/operational_safety.py",\n    "voodoo_product/persistence.py",\n',
)
replace_exact(
    readiness,
    '    "tests/system/test_observability.py",\n    "tests/system/test_persistence_boundary.py",\n',
    '    "tests/system/test_observability.py",\n    "tests/system/test_operational_safety.py",\n    "tests/system/test_persistence_boundary.py",\n',
)
replace_exact(
    readiness,
    '    "docs/product/IDENTITY_PROVIDER_BOUNDARY.md",\n    "docs/product/PERSISTENCE_BOUNDARY.md",\n',
    '    "docs/product/IDENTITY_PROVIDER_BOUNDARY.md",\n    "docs/product/OPERATIONAL_SAFETY_COMPOSITION_BOUNDARY.md",\n    "docs/product/PERSISTENCE_BOUNDARY.md",\n',
)

write(
    ROOT / "tests" / "system" / "test_operational_safety.py",
    '''from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.execution import ExecutionService
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_operational_safety_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "operational_safety.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 2
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_and_execution_services_delegate_emergency_stop_sql() -> None:
    product_source = (ROOT / "voodoo_product" / "service.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "voodoo_product" / "execution.py").read_text(
        encoding="utf-8"
    )

    assert "sql.SELECT_EMERGENCY_STOP" not in product_source
    assert "sql.UPSERT_EMERGENCY_STOP" not in product_source
    assert "sql.SELECT_EMERGENCY_STOP" not in execution_source
    assert "self.operational_safety_service.set_emergency_stop" in product_source
    assert "self.operational_safety_service.is_active" in product_source
    assert "self.operational_safety_service.is_active" in execution_source


def test_product_service_rejects_operational_safety_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="operational safety service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=second.operational_safety_service,
        )


def test_execution_service_rejects_operational_safety_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="execution operational safety service must use its database",
    ):
        ExecutionService(
            database=first.db,
            config=first.config,
            audit_ledger=first.audit_ledger,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=second.operational_safety_service,
        )


def test_operational_safety_preserves_product_service_contract(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )

    assert service.operational_safety_service.is_active() is False
    activated = service.set_emergency_stop(
        actor_id=bootstrap["user_id"],
        active=True,
        reason="incident containment",
    )
    assert activated["emergency_stop"] is True
    assert activated["reason"] == "incident containment"
    assert service.operational_safety_service.is_active() is True
    assert service.health()["status"] == "EMERGENCY_STOP"
    assert service.command_center()["emergency_stop"] is True

    cleared = service.set_emergency_stop(
        actor_id=bootstrap["user_id"],
        active=False,
        reason="incident resolved",
    )
    assert cleared["emergency_stop"] is False
    assert service.operational_safety_service.is_active() is False
    assert service.health()["status"] == "HEALTHY"

    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "system.emergency_stop.activate" in actions
    assert "system.emergency_stop.clear" in actions
    assert service.verify_audit_chain()["valid"] is True
''',
)

write(
    ROOT / "docs" / "product" / "OPERATIONAL_SAFETY_COMPOSITION_BOUNDARY.md",
    '''# Operational Safety Composition Boundary

## Status

Implemented as the canonical emergency-stop state and audited transition boundary.

## Purpose

`OperationalSafetyService` owns emergency-stop reads and audited set/clear transitions. `ProductService` preserves the existing API while `ExecutionService` consumes the same safety state inside execution start and recovery transactions.

## Runtime composition

`install_composed_product_platform` exposes one shared operational safety service through `ProductComposition` and `app.state.voodoo_operational_safety_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Delegation contract

- `ProductService.set_emergency_stop` delegates to the shared safety service;
- command-center and health reads use the shared safety service;
- execution start and incident recovery check the shared safety service using their existing transaction connection;
- direct emergency-stop SQL is absent from both `service.py` and `execution.py`.

## Safety invariants

The boundary preserves:

- emergency stop blocks new executions;
- recovery requires emergency stop to be active;
- set and clear transitions append audit evidence in the same transaction;
- existing action names, response fields, error behavior and API permissions;
- read-only health and command-center behavior;
- default inactive state when no setting exists.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, enable external sign-in, release, deploy, or enable production effects.
''',
)

for path in [
    ROOT / "voodoo_product" / "service.py",
    ROOT / "voodoo_product" / "execution.py",
    ROOT / "voodoo_product" / "operational_safety.py",
    ROOT / "voodoo_product" / "composition.py",
    ROOT / "tests" / "system" / "test_execution_service.py",
    ROOT / "tests" / "system" / "test_operational_safety.py",
    ROOT / "tests" / "system" / "test_product_composition.py",
    ROOT / "tests" / "system" / "test_statement_catalog.py",
    ROOT / "scripts" / "product_readiness_gate.py",
]:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
