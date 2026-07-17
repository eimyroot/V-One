from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"{path} expected {count} matches, found {actual}: {old!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def replace_between(path: Path, start: str, end: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"{path} method boundary assertion failed")
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    if end_index <= start_index:
        raise RuntimeError(f"{path} method boundaries are inverted")
    path.write_text(text[:start_index] + replacement + text[end_index:], encoding="utf-8")


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to replace existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


change_request_module = '''from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import canonical_json, new_id, utc_now
from .persistence import DatabaseIntegrityError, DatabaseRow, ProductDatabaseAdapter

IdFactory = Callable[[str], str]
Clock = Callable[[], str]

VALID_RISKS = {"R0", "R1", "R2", "R3", "R4"}
VALID_ENVIRONMENTS = {"local", "development", "staging", "production"}
VALID_ADAPTERS = {"echo", "write_artifact", "run_validation"}
MAX_CHANGE_PAYLOAD_BYTES = 65_536


class ChangeRequestService:
    """Database-bound change-request and approval lifecycle boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("change request audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock

    def create_change_request(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        title: str,
        description: str,
        risk: str,
        environment: str,
        adapter: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if risk not in VALID_RISKS:
            raise ValueError("unknown risk")
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        if adapter not in VALID_ADAPTERS:
            raise ValueError("adapter is not registered")
        encoded_payload = canonical_json(payload)
        if len(encoded_payload.encode("utf-8")) > MAX_CHANGE_PAYLOAD_BYTES:
            raise ValueError("change request payload exceeds the governed limit")
        request_id = self._id_factory("cr")
        now = self._clock()
        with self.db.transaction() as connection:
            workspace = connection.execute(
                sql.SELECT_WORKSPACE_CONTEXT,
                (workspace_id,),
            ).fetchone()
            if workspace is None:
                raise LookupError("workspace not found")
            if str(workspace["environment"]) != environment:
                raise ValueError("change request environment must match workspace environment")
            connection.execute(
                sql.INSERT_CHANGE_REQUEST,
                (
                    request_id,
                    workspace_id,
                    title.strip(),
                    description.strip(),
                    risk,
                    environment,
                    adapter,
                    encoded_payload,
                    actor_id,
                    now,
                    now,
                ),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="change_request.create",
                target_type="change_request",
                target_id=request_id,
                payload={"risk": risk, "environment": environment, "adapter": adapter},
            )
        return self.get_change_request(request_id)

    def list_change_requests(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_CHANGE_REQUESTS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode_change_request(dict(row)) for row in rows]

    def get_change_request(self, request_id: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.GET_CHANGE_REQUEST,
                (request_id,),
            ).fetchone()
        if row is None:
            raise LookupError("change request not found")
        return self._decode_change_request(dict(row))

    def submit_change_request(self, *, actor_id: str, request_id: str) -> dict[str, Any]:
        with self.db.transaction() as connection:
            row = connection.execute(sql.SELECT_CHANGE_REQUEST_STATUS, (request_id,)).fetchone()
            if row is None:
                raise LookupError("change request not found")
            self._require_workspace_environment(row)
            if row["status"] != "DRAFT":
                raise RuntimeError("only a draft can be submitted")
            now = self._clock()
            connection.execute(
                sql.MARK_CHANGE_REQUEST_SUBMITTED,
                (now, request_id),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="change_request.submit",
                target_type="change_request",
                target_id=request_id,
                payload={},
            )
        return self.get_change_request(request_id)

    def approve_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        decision: str,
        reason: str,
    ) -> dict[str, Any]:
        decision = decision.upper()
        if decision not in {"APPROVED", "DENIED"}:
            raise ValueError("decision must be APPROVED or DENIED")
        with self.db.transaction() as connection:
            request_row = connection.execute(
                sql.SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT,
                (request_id,),
            ).fetchone()
            if request_row is None:
                raise LookupError("change request not found")
            self._require_workspace_environment(request_row)
            if request_row["status"] not in {"REVIEW_REQUIRED", "APPROVED"}:
                raise RuntimeError("request is not awaiting review")
            if request_row["requested_by"] == actor_id:
                raise PermissionError("requester cannot approve their own change")
            approval_id = self._id_factory("appr")
            now = self._clock()
            try:
                connection.execute(
                    sql.INSERT_APPROVAL,
                    (approval_id, request_id, actor_id, decision, reason.strip(), now),
                )
            except DatabaseIntegrityError as exc:
                raise RuntimeError("approver already decided this request") from exc

            if decision == "DENIED":
                next_status = "DENIED"
            else:
                approved_count = connection.execute(
                    sql.COUNT_APPROVED,
                    (request_id,),
                ).fetchone()["count"]
                required = 2 if request_row["environment"] == "production" else 1
                next_status = "APPROVED" if int(approved_count) >= required else "REVIEW_REQUIRED"
            connection.execute(
                sql.UPDATE_CHANGE_REQUEST_STATUS,
                (next_status, now, request_id),
            )
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action=f"change_request.{decision.lower()}",
                target_type="change_request",
                target_id=request_id,
                payload={"reason": reason, "resulting_status": next_status},
            )
        return self.get_change_request(request_id)

    def list_approvals(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_PENDING_APPROVALS if pending_only else sql.LIST_APPROVALS
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _require_workspace_environment(value: DatabaseRow) -> None:
        request_environment = str(value["environment"])
        workspace_environment = str(value["workspace_environment"])
        if (
            request_environment not in VALID_ENVIRONMENTS
            or workspace_environment not in VALID_ENVIRONMENTS
        ):
            raise RuntimeError("change request environment boundary is invalid")
        if request_environment != workspace_environment:
            raise RuntimeError("change request environment does not match workspace")

    @staticmethod
    def _decode_change_request(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value
'''

change_request_test = '''from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.change_request import ChangeRequestService
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]
CHANGE_REQUEST_STATEMENTS = {
    "SELECT_WORKSPACE_CONTEXT",
    "INSERT_CHANGE_REQUEST",
    "LIST_CHANGE_REQUESTS",
    "GET_CHANGE_REQUEST",
    "SELECT_CHANGE_REQUEST_STATUS",
    "MARK_CHANGE_REQUEST_SUBMITTED",
    "SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT",
    "INSERT_APPROVAL",
    "COUNT_APPROVED",
    "UPDATE_CHANGE_REQUEST_STATUS",
    "LIST_PENDING_APPROVALS",
    "LIST_APPROVALS",
}


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_change_request_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "change_request.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 11
    assert all(
        call.args
        and (
            isinstance(call.args[0], ast.Attribute)
            or isinstance(call.args[0], ast.IfExp)
        )
        for call in execute_calls
    )


def test_product_service_delegates_complete_change_request_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    method_names = {
        "create_change_request",
        "list_change_requests",
        "get_change_request",
        "submit_change_request",
        "approve_change_request",
        "list_approvals",
    }
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef) and node.name in method_names
    }

    assert set(methods) == method_names
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    for statement in CHANGE_REQUEST_STATEMENTS:
        assert f"sql.{statement}" not in source_text
    assert "self.change_request_service.create_change_request" in source_text
    assert "self.change_request_service.approve_change_request" in source_text


def test_change_request_service_rejects_audit_ledger_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="change request audit ledger must use its database"):
        ChangeRequestService(database=first.db, audit_ledger=second.audit_ledger)


def test_product_service_rejects_change_request_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="change request service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            change_request_service=second.change_request_service,
        )


def test_change_request_service_preserves_product_service_contract(tmp_path: Path) -> None:
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
        title="Change request service compatibility",
        description="preserve public contract",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"value": 1},
    )

    assert service.get_change_request(request["id"]) == request
    assert service.list_change_requests() == service.change_request_service.list_change_requests()
    submitted = service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    assert submitted["status"] == "REVIEW_REQUIRED"
    approved = service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="approved",
        reason="independent review complete",
    )
    assert approved["status"] == "APPROVED"
    assert service.list_approvals() == service.change_request_service.list_approvals()
    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "change_request.create" in actions
    assert "change_request.submit" in actions
    assert "change_request.approved" in actions
    assert service.verify_audit_chain()["valid"] is True


def test_change_request_service_preserves_service_monkeypatch_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_new_id = service_module.new_id

    def controlled_new_id(prefix: str) -> str:
        return "cr_controlled" if prefix == "cr" else original_new_id(prefix)

    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "utc_now", lambda: "2026-07-17T12:00:00.000+00:00")
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Controlled identity",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={},
    )

    assert request["id"] == "cr_controlled"
    assert request["created_at"] == "2026-07-17T12:00:00.000+00:00"


def test_composition_exposes_shared_change_request_service(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert app.state.voodoo_change_request_service is composition.change_request_service
    assert composition.service.change_request_service is composition.change_request_service
    assert composition.change_request_service.db is composition.service.db
    assert composition.change_request_service.audit_ledger is composition.audit_ledger
'''

change_request_doc = '''# Change Request Service Composition Boundary

## Status

Implemented as the canonical change-request and approval lifecycle boundary.

## Purpose

`ChangeRequestService` owns creation, bounded listing, retrieval, submission, approval decisions, approval listing and their audit evidence. `ProductService` preserves the existing public method surface while delegating the complete domain.

## Runtime composition

`install_composed_product_platform` exposes one shared change-request service through `ProductComposition` and `app.state.voodoo_change_request_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Preserved governance invariants

- risk, environment and adapter validation;
- governed payload-size limit;
- workspace and request environment equality;
- draft-only submission;
- requester/approver separation of duties;
- one decision per approver;
- two approvals for production and one elsewhere;
- denial terminal state;
- audit evidence in the same transaction as each lifecycle transition;
- existing method signatures, response fields, ordering and error behavior.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, alter execution semantics, enable external sign-in, release, deploy or enable production effects.
'''

write_new(ROOT / "voodoo_product" / "change_request.py", change_request_module)
write_new(ROOT / "tests" / "system" / "test_change_request_service.py", change_request_test)
write_new(
    ROOT / "docs" / "product" / "CHANGE_REQUEST_SERVICE_COMPOSITION_BOUNDARY.md",
    change_request_doc,
)

service = ROOT / "voodoo_product" / "service.py"
replace_exact(
    service,
    "from .audit import AuditLedger\n",
    "from .audit import AuditLedger\nfrom .change_request import ChangeRequestService\n",
)
replace_exact(
    service,
    "        audit_ledger: AuditLedger | None = None,\n"
    "        receipt_ledger: ReceiptLedger | None = None,\n",
    "        audit_ledger: AuditLedger | None = None,\n"
    "        change_request_service: ChangeRequestService | None = None,\n"
    "        receipt_ledger: ReceiptLedger | None = None,\n",
)
replace_exact(
    service,
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_operational_safety_service = (\n",
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_change_request_service = (\n"
    "            change_request_service\n"
    "            or ChangeRequestService(\n"
    "                database=self.db,\n"
    "                audit_ledger=self.audit_ledger,\n"
    "                id_factory=lambda prefix: new_id(prefix),\n"
    "                clock=lambda: utc_now(),\n"
    "            )\n"
    "        )\n"
    "        if resolved_change_request_service.db is not self.db:\n"
    "            raise ValueError(\n"
    "                \"change request service must use the product service database\"\n"
    "            )\n"
    "        if resolved_change_request_service.audit_ledger is not self.audit_ledger:\n"
    "            raise ValueError(\n"
    "                \"change request service must use the product service audit ledger\"\n"
    "            )\n"
    "        self.change_request_service = resolved_change_request_service\n"
    "        resolved_operational_safety_service = (\n",
)

delegates = '''    def create_change_request(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        title: str,
        description: str,
        risk: str,
        environment: str,
        adapter: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.change_request_service.create_change_request(
            actor_id=actor_id,
            workspace_id=workspace_id,
            title=title,
            description=description,
            risk=risk,
            environment=environment,
            adapter=adapter,
            payload=payload,
        )

    def list_change_requests(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.change_request_service.list_change_requests(limit=limit)

    def get_change_request(self, request_id: str) -> dict[str, Any]:
        return self.change_request_service.get_change_request(request_id)

    def submit_change_request(self, *, actor_id: str, request_id: str) -> dict[str, Any]:
        return self.change_request_service.submit_change_request(
            actor_id=actor_id,
            request_id=request_id,
        )

    def approve_change_request(
        self,
        *,
        actor_id: str,
        request_id: str,
        decision: str,
        reason: str,
    ) -> dict[str, Any]:
        return self.change_request_service.approve_change_request(
            actor_id=actor_id,
            request_id=request_id,
            decision=decision,
            reason=reason,
        )

    def list_approvals(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        return self.change_request_service.list_approvals(pending_only=pending_only)

'''
replace_between(
    service,
    "    def create_change_request(\n",
    "    def execute_change_request(\n",
    delegates,
)
replace_exact(
    service,
    "    @staticmethod\n"
    "    def _require_workspace_environment(value: DatabaseRow) -> None:\n"
    "        request_environment = str(value[\"environment\"])\n"
    "        workspace_environment = str(value[\"workspace_environment\"])\n"
    "        if (\n"
    "            request_environment not in VALID_ENVIRONMENTS\n"
    "            or workspace_environment not in VALID_ENVIRONMENTS\n"
    "        ):\n"
    "            raise RuntimeError(\"change request environment boundary is invalid\")\n"
    "        if request_environment != workspace_environment:\n"
    "            raise RuntimeError(\"change request environment does not match workspace\")\n\n"
    "    @staticmethod\n"
    "    def _decode_change_request(value: dict[str, Any]) -> dict[str, Any]:\n"
    "        value[\"payload\"] = json.loads(value.pop(\"payload_json\"))\n"
    "        return value\n",
    "",
)

composition = ROOT / "voodoo_product" / "composition.py"
replace_exact(
    composition,
    "from .audit import AuditLedger\n",
    "from .audit import AuditLedger\nfrom .change_request import ChangeRequestService\n",
)
replace_exact(
    composition,
    "    audit_ledger: AuditLedger\n"
    "    receipt_ledger: ReceiptLedger\n",
    "    audit_ledger: AuditLedger\n"
    "    change_request_service: ChangeRequestService\n"
    "    receipt_ledger: ReceiptLedger\n",
)
replace_exact(
    composition,
    "    audit_ledger = service.audit_ledger\n"
    "    receipt_ledger = service.receipt_ledger\n",
    "    audit_ledger = service.audit_ledger\n"
    "    change_request_service = service.change_request_service\n"
    "    receipt_ledger = service.receipt_ledger\n",
)
replace_exact(
    composition,
    "        service=service,\n"
    "        audit_ledger=audit_ledger,\n"
    "        receipt_ledger=receipt_ledger,\n",
    "        service=service,\n"
    "        audit_ledger=audit_ledger,\n"
    "        change_request_service=change_request_service,\n"
    "        receipt_ledger=receipt_ledger,\n",
)
replace_exact(
    composition,
    "    app.state.voodoo_audit_ledger = audit_ledger\n"
    "    app.state.voodoo_receipt_ledger = receipt_ledger\n",
    "    app.state.voodoo_audit_ledger = audit_ledger\n"
    "    app.state.voodoo_change_request_service = change_request_service\n"
    "    app.state.voodoo_receipt_ledger = receipt_ledger\n",
)

statement_test = ROOT / "tests" / "system" / "test_statement_catalog.py"
replace_exact(statement_test, "    assert len(execute_calls) == 30\n", "    assert len(execute_calls) == 19\n")

readiness = ROOT / "scripts" / "product_readiness_gate.py"
replace_exact(
    readiness,
    '    "voodoo_product/audit.py",\n',
    '    "voodoo_product/audit.py",\n    "voodoo_product/change_request.py",\n',
)
replace_exact(
    readiness,
    '    "tests/system/test_auth_rate_limiting.py",\n',
    '    "tests/system/test_auth_rate_limiting.py",\n    "tests/system/test_change_request_service.py",\n',
)
replace_exact(
    readiness,
    '    "docs/product/AUDIT_LEDGER_COMPOSITION_BOUNDARY.md",\n',
    '    "docs/product/AUDIT_LEDGER_COMPOSITION_BOUNDARY.md",\n'
    '    "docs/product/CHANGE_REQUEST_SERVICE_COMPOSITION_BOUNDARY.md",\n',
)

print("change request service transform applied")
