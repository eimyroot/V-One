from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi import FastAPI

from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.external_identity_service import GovernedExternalIdentityService
from voodoo_product.external_identity_statements import (
    ALL_EXTERNAL_IDENTITY_STATEMENTS,
    EXTERNAL_IDENTITY_STATEMENTS_BY_NAME,
)
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]


def build_services(
    tmp_path: Path,
) -> tuple[
    ProductService,
    GovernedExternalIdentityService,
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    product = ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        )
    )
    bootstrap = product.bootstrap_admin(
        username="bootstrap-admin",
        password="VeryStrongBootstrapPassword1!",
        token="b" * 48,
    )
    administrator = product.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="identity-admin",
        password="VeryStrongIdentityAdminPassword1!",
        role="administrator",
    )
    viewer = product.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="bound-viewer",
        password="VeryStrongBoundViewerPassword1!",
        role="viewer",
    )
    governed = GovernedExternalIdentityService(
        database=product.db,
        audit_writer=product._append_audit,
    )
    return product, governed, bootstrap, administrator, viewer


def test_external_identity_statement_catalog_is_unique_and_classified() -> None:
    assert len(ALL_EXTERNAL_IDENTITY_STATEMENTS) == 5
    assert tuple(EXTERNAL_IDENTITY_STATEMENTS_BY_NAME) == tuple(
        statement.name for statement in ALL_EXTERNAL_IDENTITY_STATEMENTS
    )
    assert tuple(EXTERNAL_IDENTITY_STATEMENTS_BY_NAME.values()) == (
        ALL_EXTERNAL_IDENTITY_STATEMENTS
    )

    write_verbs = {"INSERT", "UPDATE"}
    for statement in ALL_EXTERNAL_IDENTITY_STATEMENTS:
        first_verb = statement.sqlite_sql.split(maxsplit=1)[0].upper()
        expected_mode = "write" if first_verb in write_verbs else "read"
        assert statement.mode == expected_mode
        assert statement.for_backend("sqlite") == statement.sqlite_sql


def test_governed_service_database_calls_use_identity_catalog() -> None:
    source = ROOT / "voodoo_product" / "external_identity_service.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 6
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "identity_sql"
        for call in execute_calls
    )


def test_administrator_creates_and_resolves_binding_with_valid_audit_chain(
    tmp_path: Path,
) -> None:
    product, governed, _, administrator, viewer = build_services(tmp_path)
    subject = "stable-provider-subject"

    binding = governed.create_binding(
        actor_id=str(administrator["id"]),
        user_id=str(viewer["id"]),
        provider="OIDC",
        issuer="https://identity.example.com/",
        subject=f" {subject} ",
        reason="Approved enterprise identity enrollment",
    )

    assert binding["active"] is True
    assert binding["provider"] == "oidc"
    assert binding["issuer"] == "https://identity.example.com"
    assert "subject" not in binding
    resolved = governed.resolve_active_binding(
        provider="oidc",
        issuer="https://identity.example.com",
        subject=subject,
    )
    assert resolved == {
        "binding_id": binding["id"],
        "user_id": viewer["id"],
        "username": viewer["username"],
        "role": "viewer",
    }

    events = product.list_audit_events()
    assert events[0]["action"] == "external_identity_binding.create"
    assert events[0]["payload"]["user_id"] == viewer["id"]
    assert subject not in json.dumps(events, sort_keys=True)
    assert product.verify_audit_chain()["valid"] is True


def test_non_admin_inactive_target_and_self_binding_fail_closed(tmp_path: Path) -> None:
    product, governed, _, administrator, viewer = build_services(tmp_path)

    with pytest.raises(PermissionError, match="administrator role"):
        governed.create_binding(
            actor_id=str(viewer["id"]),
            user_id=str(administrator["id"]),
            provider="oidc",
            issuer="https://identity.example.com",
            subject="viewer-cannot-govern",
            reason="Attempted unauthorized enrollment",
        )

    with pytest.raises(PermissionError, match="own external identity"):
        governed.create_binding(
            actor_id=str(administrator["id"]),
            user_id=str(administrator["id"]),
            provider="oidc",
            issuer="https://identity.example.com",
            subject="self-binding",
            reason="Self enrollment must be rejected",
        )

    with product.db.connect() as connection:
        connection.execute("UPDATE users SET active = 0 WHERE id = ?", (viewer["id"],))
    with pytest.raises(PermissionError, match="target user is inactive"):
        governed.create_binding(
            actor_id=str(administrator["id"]),
            user_id=str(viewer["id"]),
            provider="oidc",
            issuer="https://identity.example.com",
            subject="inactive-target",
            reason="Inactive account must not be enrolled",
        )


def test_duplicate_subject_or_user_binding_fails_closed(tmp_path: Path) -> None:
    product, governed, bootstrap, administrator, viewer = build_services(tmp_path)
    second_viewer = product.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="second-viewer",
        password="VeryStrongSecondViewerPassword1!",
        role="viewer",
    )
    governed.create_binding(
        actor_id=str(administrator["id"]),
        user_id=str(viewer["id"]),
        provider="oidc",
        issuer="https://identity.example.com",
        subject="subject-one",
        reason="Initial approved binding",
    )

    with pytest.raises(RuntimeError, match="already bound"):
        governed.create_binding(
            actor_id=str(administrator["id"]),
            user_id=str(second_viewer["id"]),
            provider="oidc",
            issuer="https://identity.example.com",
            subject="subject-one",
            reason="Duplicate subject must fail",
        )
    with pytest.raises(RuntimeError, match="already bound"):
        governed.create_binding(
            actor_id=str(administrator["id"]),
            user_id=str(viewer["id"]),
            provider="oidc",
            issuer="https://identity.example.com",
            subject="subject-two",
            reason="Duplicate user must fail",
        )


def test_disablement_is_one_way_audited_and_blocks_resolution(tmp_path: Path) -> None:
    product, governed, bootstrap, administrator, viewer = build_services(tmp_path)
    binding = governed.create_binding(
        actor_id=str(administrator["id"]),
        user_id=str(viewer["id"]),
        provider="oidc",
        issuer="https://identity.example.com",
        subject="disable-me",
        reason="Initial approved binding",
    )

    disabled = governed.disable_binding(
        actor_id=str(bootstrap["user_id"]),
        binding_id=str(binding["id"]),
        reason="Identity access was revoked by the provider owner",
    )

    assert disabled["active"] is False
    with pytest.raises(PermissionError, match="not actively bound"):
        governed.resolve_active_binding(
            provider="oidc",
            issuer="https://identity.example.com",
            subject="disable-me",
        )
    with pytest.raises(RuntimeError, match="already disabled"):
        governed.disable_binding(
            actor_id=str(bootstrap["user_id"]),
            binding_id=str(binding["id"]),
            reason="Repeated disablement must fail",
        )
    with pytest.raises(DatabaseIntegrityError), product.db.connect() as connection:
        connection.execute(
            "UPDATE external_identity_bindings SET active = 1, disabled_at = NULL WHERE id = ?",
            (binding["id"],),
        )

    actions = [event["action"] for event in product.list_audit_events()]
    assert actions[:2] == [
        "external_identity_binding.disable",
        "external_identity_binding.create",
    ]
    assert product.verify_audit_chain()["valid"] is True


def test_administrator_cannot_disable_own_binding(tmp_path: Path) -> None:
    _, governed, bootstrap, administrator, _ = build_services(tmp_path)
    binding = governed.create_binding(
        actor_id=str(bootstrap["user_id"]),
        user_id=str(administrator["id"]),
        provider="oidc",
        issuer="https://identity.example.com",
        subject="administrator-subject",
        reason="Second administrator approved the enrollment",
    )

    with pytest.raises(PermissionError, match="own external identity"):
        governed.disable_binding(
            actor_id=str(administrator["id"]),
            binding_id=str(binding["id"]),
            reason="Self disablement must be rejected",
        )


def test_governed_service_exposes_no_public_api(tmp_path: Path) -> None:
    app = FastAPI()
    install_product_platform(
        app,
        config=ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        ),
        repository_root=tmp_path,
    )

    paths = app.openapi()["paths"]
    assert all("external-identity" not in path for path in paths)
    assert all("identity-bindings" not in path for path in paths)
