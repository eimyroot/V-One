from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} matches, found {actual}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


workspace = ROOT / "voodoo_product" / "workspace.py"
if workspace.exists():
    raise SystemExit("workspace boundary already exists")
workspace.write_text(
    '''from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import new_id, utc_now
from .persistence import ProductDatabaseAdapter

IdFactory = Callable[[str], str]
Clock = Callable[[], str]

VALID_ENVIRONMENTS = {"local", "development", "staging", "production"}


class WorkspaceService:
    """Database-bound workspace lifecycle boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("workspace audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock

    def list_workspaces(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_WORKSPACES).fetchall()
        return [dict(row) for row in rows]

    def create_workspace(
        self,
        *,
        actor_id: str,
        name: str,
        environment: str,
    ) -> dict[str, Any]:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        workspace_id = self._id_factory("wrk")
        now = self._clock()
        with self.db.transaction() as connection:
            connection.execute(
                sql.INSERT_WORKSPACE,
                (workspace_id, name.strip(), environment, now),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="workspace.create",
                target_type="workspace",
                target_id=workspace_id,
                payload={"name": name, "environment": environment},
            )
        return {
            "id": workspace_id,
            "name": name,
            "environment": environment,
            "created_at": now,
        }
''',
    encoding="utf-8",
)

service = ROOT / "voodoo_product" / "service.py"
replace_exact(
    service,
    "from .security import hash_password, verify_password\n",
    "from .security import hash_password, verify_password\nfrom .workspace import WorkspaceService\n",
)
replace_exact(
    service,
    "        audit_ledger: AuditLedger | None = None,\n"
    "        change_request_service: ChangeRequestService | None = None,\n",
    "        audit_ledger: AuditLedger | None = None,\n"
    "        workspace_service: WorkspaceService | None = None,\n"
    "        change_request_service: ChangeRequestService | None = None,\n",
)
replace_exact(
    service,
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_change_request_service = (\n",
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_workspace_service = workspace_service or WorkspaceService(\n"
    "            database=self.db,\n"
    "            audit_ledger=self.audit_ledger,\n"
    "            id_factory=lambda prefix: new_id(prefix),\n"
    "            clock=lambda: utc_now(),\n"
    "        )\n"
    "        if resolved_workspace_service.db is not self.db:\n"
    "            raise ValueError(\n"
    "                \"workspace service must use the product service database\"\n"
    "            )\n"
    "        if resolved_workspace_service.audit_ledger is not self.audit_ledger:\n"
    "            raise ValueError(\n"
    "                \"workspace service must use the product service audit ledger\"\n"
    "            )\n"
    "        self.workspace_service = resolved_workspace_service\n"
    "        resolved_change_request_service = (\n",
)
replace_exact(
    service,
    '''    def list_workspaces(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_WORKSPACES).fetchall()
        return [dict(row) for row in rows]

    def create_workspace(self, *, actor_id: str, name: str, environment: str) -> dict[str, Any]:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        workspace_id = new_id("wrk")
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                sql.INSERT_WORKSPACE,
                (workspace_id, name.strip(), environment, now),
            )
            self._append_audit(
                connection,
                actor_id=actor_id,
                action="workspace.create",
                target_type="workspace",
                target_id=workspace_id,
                payload={"name": name, "environment": environment},
            )
        return {"id": workspace_id, "name": name, "environment": environment, "created_at": now}

''',
    '''    def list_workspaces(self) -> list[dict[str, Any]]:
        return self.workspace_service.list_workspaces()

    def create_workspace(self, *, actor_id: str, name: str, environment: str) -> dict[str, Any]:
        return self.workspace_service.create_workspace(
            actor_id=actor_id,
            name=name,
            environment=environment,
        )

''',
)

composition = ROOT / "voodoo_product" / "composition.py"
replace_exact(
    composition,
    "from .service import ProductService\n",
    "from .service import ProductService\nfrom .workspace import WorkspaceService\n",
)
replace_exact(
    composition,
    "    audit_ledger: AuditLedger\n    change_request_service: ChangeRequestService\n",
    "    audit_ledger: AuditLedger\n    workspace_service: WorkspaceService\n"
    "    change_request_service: ChangeRequestService\n",
)
replace_exact(
    composition,
    "    audit_ledger = service.audit_ledger\n    change_request_service = service.change_request_service\n",
    "    audit_ledger = service.audit_ledger\n    workspace_service = service.workspace_service\n"
    "    change_request_service = service.change_request_service\n",
)
replace_exact(
    composition,
    "        audit_ledger=audit_ledger,\n        change_request_service=change_request_service,\n",
    "        audit_ledger=audit_ledger,\n        workspace_service=workspace_service,\n"
    "        change_request_service=change_request_service,\n",
)
replace_exact(
    composition,
    "    app.state.voodoo_audit_ledger = audit_ledger\n"
    "    app.state.voodoo_change_request_service = change_request_service\n",
    "    app.state.voodoo_audit_ledger = audit_ledger\n"
    "    app.state.voodoo_workspace_service = workspace_service\n"
    "    app.state.voodoo_change_request_service = change_request_service\n",
)

statement_test = ROOT / "tests" / "system" / "test_statement_catalog.py"
replace_exact(statement_test, "assert len(execute_calls) == 19", "assert len(execute_calls) == 17")

readiness = ROOT / "scripts" / "product_readiness_gate.py"
replace_exact(
    readiness,
    '    "voodoo_product/version.py",\n',
    '    "voodoo_product/version.py",\n    "voodoo_product/workspace.py",\n',
)
replace_exact(
    readiness,
    '    "tests/system/test_token_security.py",\n',
    '    "tests/system/test_token_security.py",\n    "tests/system/test_workspace_service.py",\n',
)
replace_exact(
    readiness,
    '    "docs/product/STATEMENT_CATALOG.md",\n',
    '    "docs/product/STATEMENT_CATALOG.md",\n'
    '    "docs/product/WORKSPACE_SERVICE_COMPOSITION_BOUNDARY.md",\n',
)

test = ROOT / "tests" / "system" / "test_workspace_service.py"
if test.exists():
    raise SystemExit("workspace service test already exists")
test.write_text(
    '''from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import ProductService
from voodoo_product.workspace import WorkspaceService

ROOT = Path(__file__).resolve().parents[2]


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_workspace_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "workspace.py"
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


def test_product_service_delegates_workspace_surface() -> None:
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
        and node.name in {"list_workspaces", "create_workspace"}
    }

    assert set(methods) == {"list_workspaces", "create_workspace"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.workspace_service.list_workspaces" in source_text
    assert "self.workspace_service.create_workspace" in source_text
    assert "sql.LIST_WORKSPACES" not in source_text
    assert "sql.INSERT_WORKSPACE" in source_text


def test_workspace_service_rejects_audit_ledger_from_another_database(tmp_path: Path) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="workspace audit ledger must use its database"):
        WorkspaceService(database=first.db, audit_ledger=second.audit_ledger)


def test_product_service_rejects_workspace_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="workspace service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            workspace_service=second.workspace_service,
        )


def test_workspace_service_preserves_product_service_contract(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )

    created = service.create_workspace(
        actor_id=bootstrap["user_id"],
        name="  Operations  ",
        environment="staging",
    )
    assert created["name"] == "  Operations  "
    assert created["environment"] == "staging"
    listed = {item["id"]: item for item in service.list_workspaces()}
    assert listed[created["id"]]["name"] == "Operations"
    assert listed[created["id"]]["environment"] == "staging"
    with pytest.raises(ValueError, match="unknown environment"):
        service.create_workspace(
            actor_id=bootstrap["user_id"],
            name="Invalid",
            environment="invalid",
        )
    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "workspace.create" in actions
    assert service.verify_audit_chain()["valid"] is True


def test_workspace_service_preserves_service_monkeypatch_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_new_id = service_module.new_id

    def controlled_new_id(prefix: str) -> str:
        return "wrk_controlled" if prefix == "wrk" else original_new_id(prefix)

    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "utc_now", lambda: "2026-07-17T13:00:00.000+00:00")
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    workspace = service.create_workspace(
        actor_id=bootstrap["user_id"],
        name="Controlled",
        environment="local",
    )

    assert workspace["id"] == "wrk_controlled"
    assert workspace["created_at"] == "2026-07-17T13:00:00.000+00:00"


def test_composition_exposes_shared_workspace_service(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert app.state.voodoo_workspace_service is composition.workspace_service
    assert composition.service.workspace_service is composition.workspace_service
    assert composition.workspace_service.db is composition.service.db
    assert composition.workspace_service.audit_ledger is composition.audit_ledger
''',
    encoding="utf-8",
)

doc = ROOT / "docs" / "product" / "WORKSPACE_SERVICE_COMPOSITION_BOUNDARY.md"
if doc.exists():
    raise SystemExit("workspace service document already exists")
doc.write_text(
    '''# Workspace Service Composition Boundary

## Status

Implemented as the canonical ordinary workspace lifecycle boundary.

## Purpose

`WorkspaceService` owns workspace listing, ordinary workspace creation, environment validation and creation audit evidence. `ProductService` preserves the existing public method surface while delegating those operations.

## Runtime composition

`install_composed_product_platform` exposes one shared workspace service through `ProductComposition` and `app.state.voodoo_workspace_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Preserved invariants

- only governed environments are accepted;
- stored workspace names remain trimmed while the immediate create response remains compatible;
- workspace creation and audit evidence remain in the same transaction;
- existing method signatures, response fields, ordering and error behavior remain unchanged;
- `new_id` and `utc_now` monkeypatch bridges remain compatible.

Bootstrap workspace creation intentionally remains in `ProductService` because bootstrap atomically creates the first administrator, initial workspace and `system.bootstrap` audit evidence.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, alter change-request or execution semantics, enable external sign-in, release, deploy or enable production effects.
''',
    encoding="utf-8",
)

for path in (
    workspace,
    service,
    composition,
    statement_test,
    readiness,
    test,
    doc,
):
    text = path.read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).rstrip() + "\n"
    path.write_text(normalized, encoding="utf-8")
