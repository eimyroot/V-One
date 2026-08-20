from __future__ import annotations

from pathlib import Path

from voodoo_product.config import ProductConfig
from voodoo_product.permission_authority import (
    DATABASE_PERMISSION_SCOPE_MODEL,
    DatabasePermissionAuthority,
    PermissionQuery,
)
from voodoo_product.service import ProductService


def product(tmp_path: Path) -> tuple[ProductService, dict[str, str]]:
    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
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
    viewer = service.create_user(
        actor_id=bootstrap["user_id"],
        username="viewer",
        password="VeryStrongViewerPassword1!",
        role="viewer",
    )
    staging = service.create_workspace(
        actor_id=bootstrap["user_id"],
        name="Staging",
        environment="staging",
    )
    return service, {
        "local_workspace": bootstrap["workspace_id"],
        "staging_workspace": staging["id"],
        "operator": operator["id"],
        "viewer": viewer["id"],
    }


def authority(service: ProductService) -> DatabasePermissionAuthority:
    return DatabasePermissionAuthority(
        database=service.db,
        authority_revision="database-permission/test-r1",
    )


def query(*, actor_id: str, workspace_id: str, environment: str = "local") -> PermissionQuery:
    return PermissionQuery(
        actor_id=actor_id,
        workspace_id=workspace_id,
        environment=environment,
        permission="execution.run",
    )


def test_operator_permission_is_resolved_from_current_database_state(tmp_path: Path) -> None:
    service, ids = product(tmp_path)
    decision = authority(service).decide(
        query(actor_id=ids["operator"], workspace_id=ids["local_workspace"])
    )

    assert decision.granted is True
    assert decision.reason == "DATABASE_ROLE_PERMISSION_GRANTED"
    assert decision.scope_model == DATABASE_PERMISSION_SCOPE_MODEL
    assert decision.authority_revision == "database-permission/test-r1"


def test_viewer_is_denied_even_when_caller_requests_execution_permission(tmp_path: Path) -> None:
    service, ids = product(tmp_path)
    decision = authority(service).decide(
        query(actor_id=ids["viewer"], workspace_id=ids["local_workspace"])
    )

    assert decision.granted is False
    assert decision.reason == "DATABASE_ROLE_PERMISSION_DENIED"


def test_inactive_actor_is_denied_from_live_database_state(tmp_path: Path) -> None:
    service, ids = product(tmp_path)
    with service.db.transaction() as connection:
        connection.execute("UPDATE users SET active = 0 WHERE id = ?", (ids["operator"],))

    decision = authority(service).decide(
        query(actor_id=ids["operator"], workspace_id=ids["local_workspace"])
    )
    assert decision.granted is False
    assert decision.reason == "ACTOR_INACTIVE"


def test_missing_actor_and_workspace_fail_closed(tmp_path: Path) -> None:
    service, ids = product(tmp_path)
    subject = authority(service)

    missing_actor = subject.decide(
        query(actor_id="usr_missing", workspace_id=ids["local_workspace"])
    )
    assert missing_actor.granted is False
    assert missing_actor.reason == "ACTOR_NOT_FOUND"

    missing_workspace = subject.decide(
        query(actor_id=ids["operator"], workspace_id="wrk_missing")
    )
    assert missing_workspace.granted is False
    assert missing_workspace.reason == "WORKSPACE_NOT_FOUND"


def test_workspace_environment_mismatch_is_denied(tmp_path: Path) -> None:
    service, ids = product(tmp_path)
    decision = authority(service).decide(
        query(
            actor_id=ids["operator"],
            workspace_id=ids["staging_workspace"],
            environment="local",
        )
    )

    assert decision.granted is False
    assert decision.reason == "WORKSPACE_ENVIRONMENT_MISMATCH"


def test_role_change_is_observed_without_rebuilding_authority(tmp_path: Path) -> None:
    service, ids = product(tmp_path)
    subject = authority(service)
    initial = subject.decide(
        query(actor_id=ids["operator"], workspace_id=ids["local_workspace"])
    )
    assert initial.granted is True

    with service.db.transaction() as connection:
        connection.execute("UPDATE users SET role = 'viewer' WHERE id = ?", (ids["operator"],))

    changed = subject.decide(
        query(actor_id=ids["operator"], workspace_id=ids["local_workspace"])
    )
    assert changed.granted is False
    assert changed.reason == "DATABASE_ROLE_PERMISSION_DENIED"
