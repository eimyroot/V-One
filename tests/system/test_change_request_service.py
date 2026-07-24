from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.approval_policy import (
    ApprovalPolicyCompatibilityError,
    ApprovalPolicyInput,
    evaluate_current_approval_policy,
)
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


def product_config(
    tmp_path: Path,
    *,
    name: str = "product",
    approval_policy_compatibility_enabled: bool = False,
) -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
        approval_policy_compatibility_enabled=approval_policy_compatibility_enabled,
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
            isinstance(call.args[0], (ast.Attribute, ast.IfExp))
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


def test_policy_compatibility_mode_preserves_current_runtime_outcomes(tmp_path: Path) -> None:
    disabled = ProductService(product_config(tmp_path, name="disabled"))
    assert disabled.change_request_service.approval_policy_compatibility_enabled is False

    service = ProductService(
        product_config(
            tmp_path,
            name="enabled",
            approval_policy_compatibility_enabled=True,
        )
    )
    assert service.change_request_service.approval_policy_compatibility_enabled is True

    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    operators = [
        service.create_user(
            actor_id=bootstrap["user_id"],
            username=f"operator{index}",
            password=f"VeryStrongOperatorPassword{index}!",
            role="operator",
        )
        for index in (1, 2)
    ]
    production_workspace = service.create_workspace(
        actor_id=bootstrap["user_id"],
        name="Production",
        environment="production",
    )

    requests = {}
    for environment, workspace_id in (
        ("local", bootstrap["workspace_id"]),
        ("production", production_workspace["id"]),
    ):
        request = service.create_change_request(
            actor_id=bootstrap["user_id"],
            workspace_id=workspace_id,
            title=f"Compatibility {environment}",
            description="preserve current behavior",
            risk="R4",
            environment=environment,
            adapter="echo",
            payload={},
        )
        service.submit_change_request(
            actor_id=bootstrap["user_id"],
            request_id=request["id"],
        )
        requests[environment] = request

    required_by_request = {
        row["request_id"]: row["required_count"]
        for row in service.list_approvals(pending_only=True)
    }
    assert required_by_request[requests["local"]["id"]] == 1
    assert required_by_request[requests["production"]["id"]] == 2

    local = service.approve_change_request(
        actor_id=operators[0]["id"],
        request_id=requests["local"]["id"],
        decision="APPROVED",
        reason="single review",
    )
    production_first = service.approve_change_request(
        actor_id=operators[0]["id"],
        request_id=requests["production"]["id"],
        decision="APPROVED",
        reason="first review",
    )
    production_second = service.approve_change_request(
        actor_id=operators[1]["id"],
        request_id=requests["production"]["id"],
        decision="APPROVED",
        reason="second review",
    )

    assert local["status"] == "APPROVED"
    assert production_first["status"] == "REVIEW_REQUIRED"
    assert production_second["status"] == "APPROVED"


def test_policy_compatibility_mismatch_fails_closed_before_approval_write(
    tmp_path: Path,
) -> None:
    product = ProductService(product_config(tmp_path))
    bootstrap = product.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    operator = product.create_user(
        actor_id=bootstrap["user_id"],
        username="operator",
        password="VeryStrongOperatorPassword1!",
        role="operator",
    )

    def incompatible_evaluator(value: ApprovalPolicyInput):
        current = evaluate_current_approval_policy(value)
        return replace(current, required_approvals=0, distinct_approver_identities=0)

    compatibility_service = ChangeRequestService(
        database=product.db,
        audit_ledger=product.audit_ledger,
        approval_policy_compatibility_enabled=True,
        approval_policy_evaluator=incompatible_evaluator,
    )
    request = compatibility_service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Fail closed mismatch",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={},
    )
    compatibility_service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )

    with pytest.raises(ApprovalPolicyCompatibilityError, match="diverged"):
        compatibility_service.approve_change_request(
            actor_id=operator["id"],
            request_id=request["id"],
            decision="APPROVED",
            reason="must not persist",
        )

    persisted = product.get_change_request(request["id"])
    approval_row = next(
        row for row in product.list_approvals() if row["request_id"] == request["id"]
    )
    assert persisted["status"] == "REVIEW_REQUIRED"
    assert approval_row["approved_count"] == 0


def test_approved_audit_event_records_resolved_policy_metadata(tmp_path: Path) -> None:
    service = ProductService(
        product_config(
            tmp_path,
            approval_policy_compatibility_enabled=True,
        )
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
        title="Auditable approval policy",
        description="record the resolved decision",
        risk="R2",
        environment="local",
        adapter="echo",
        payload={},
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )

    service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="independent review complete",
    )

    event = next(
        item
        for item in service.list_audit_events(limit=100)
        if item["action"] == "change_request.approved"
        and item["target_id"] == request["id"]
    )
    assert event["payload"]["approval_policy"] == {
        "policy_version": "approval-policy/current-v1",
        "profile": "CURRENT_COMPATIBILITY",
        "decision": "ALLOW_AFTER_AUTHORIZATION",
        "authorization_mode": "INDEPENDENT_APPROVAL",
        "required_approvals": 1,
        "required_permissions": ["approval.review"],
        "distinct_approver_identities": 1,
        "requester_may_approve": False,
        "step_up_required": False,
        "reason_codes": [
            "CURRENT_BEHAVIOR_COMPATIBILITY",
            "ENVIRONMENT_LOCAL",
            "R2_CURRENTLY_NON_ENFORCING",
            "REQUESTER_SELF_APPROVAL_DENIED",
            "NON_PRODUCTION_ONE_APPROVAL_REQUIRED",
        ],
    }
    assert service.verify_audit_chain()["valid"] is True
