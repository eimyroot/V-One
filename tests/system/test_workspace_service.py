from __future__ import annotations

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


def test_workspace_service_uses_only_statement_catalogs() -> None:
    source = ROOT / "voodoo_product" / "workspace.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert execute_calls
    allowed_catalogs = {"sql", "membership_sql"}
    for call in execute_calls:
        assert call.args
        assert isinstance(call.args[0], ast.Attribute)
        assert isinstance(call.args[0].value, ast.Name)
        assert call.args[0].value.id in allowed_catalogs

    attributes = {
        call.args[0].attr
        for call in execute_calls
        if isinstance(call.args[0], ast.Attribute)
    }
    assert {
        "INSERT_WORKSPACE",
        "LIST_WORKSPACES",
        "SELECT_ACTIVE_USER",
        "SELECT_WORKSPACE_CONTEXT",
        "INSERT_WORKSPACE_MEMBERSHIP",
        "SELECT_WORKSPACE_MEMBERSHIP",
        "LIST_WORKSPACE_MEMBERS",
        "DELETE_WORKSPACE_MEMBERSHIP",
        "COUNT_WORKSPACE_OWNERS",
    } <= attributes


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
    assert "sql.INSERT_WORKSPACE" not in source_text


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


def test_workspace_creator_is_atomic_owner_and_membership_is_audited(tmp_path: Path) -> None:
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

    members = service.workspace_service.list_members(workspace_id=created["id"])
    assert len(members) == 1
    assert members[0]["user_id"] == bootstrap["user_id"]
    assert members[0]["membership_role"] == "owner"

    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "workspace.create" in actions
    assert "workspace.member.add" in actions
    assert service.verify_audit_chain()["valid"] is True

    with pytest.raises(ValueError, match="unknown environment"):
        service.create_workspace(
            actor_id=bootstrap["user_id"],
            name="Invalid",
            environment="invalid",
        )


def test_owner_can_add_and_remove_member_but_cannot_remove_last_owner(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    member = service.create_user(
        actor_id=bootstrap["user_id"],
        username="member",
        password="VeryStrongMemberPassword1!",
        role="operator",
    )

    added = service.workspace_service.add_member(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        user_id=member["id"],
    )
    assert added["membership_role"] == "member"
    assert {item["user_id"] for item in service.workspace_service.list_members(
        workspace_id=bootstrap["workspace_id"]
    )} == {bootstrap["user_id"], member["id"]}

    service.workspace_service.remove_member(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        user_id=member["id"],
    )
    assert [item["user_id"] for item in service.workspace_service.list_members(
        workspace_id=bootstrap["workspace_id"]
    )] == [bootstrap["user_id"]]

    with pytest.raises(PermissionError, match="last workspace owner"):
        service.workspace_service.remove_member(
            actor_id=bootstrap["user_id"],
            workspace_id=bootstrap["workspace_id"],
            user_id=bootstrap["user_id"],
        )


def test_non_owner_member_cannot_manage_membership(tmp_path: Path) -> None:
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
    target = service.create_user(
        actor_id=bootstrap["user_id"],
        username="target",
        password="VeryStrongTargetPassword1!",
        role="viewer",
    )
    service.workspace_service.add_member(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        user_id=operator["id"],
    )

    with pytest.raises(PermissionError, match="owner or administrator"):
        service.workspace_service.add_member(
            actor_id=operator["id"],
            workspace_id=bootstrap["workspace_id"],
            user_id=target["id"],
        )


def test_workspace_service_preserves_service_monkeypatch_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_new_id = service_module.new_id

    def controlled_new_id(prefix: str) -> str:
        return "wrk_controlled" if prefix == "wrk" else original_new_id(prefix)

    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "utc_now", lambda: "2026-07-17T13:00:00.000+00:00")
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
