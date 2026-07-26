from __future__ import annotations

import ast
import base64
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.security import issue_token, session_reference
from voodoo_product.service import ProductService
from voodoo_product.session_lifecycle import SessionLifecycleService

ROOT = Path(__file__).resolve().parents[2]


def build_client(tmp_path: Path) -> TestClient:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )
    app = FastAPI()
    install_product_platform(app, config=config, repository_root=tmp_path)
    return TestClient(app)


def bootstrap(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/bootstrap",
        json={
            "username": "admin",
            "password": "VeryStrongAdminPassword1!",
            "bootstrap_token": "b" * 48,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["token"])


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def token_nonce(token: str) -> str:
    encoded_payload = token.split(".", 2)[1]
    padding = "=" * (-len(encoded_payload) % 4)
    payload = json.loads(base64.urlsafe_b64decode(encoded_payload + padding))
    return str(payload["nonce"])


def test_session_lifecycle_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "session_lifecycle.py"
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
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_logout_revokes_only_current_session_and_records_redacted_audit(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    first = bootstrap(client)
    second_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "VeryStrongAdminPassword1!"},
    )
    assert second_response.status_code == 200, second_response.text
    second = str(second_response.json()["token"])

    assert client.get("/api/v1/me", headers=authorization(first)).status_code == 200
    assert client.get("/api/v1/me", headers=authorization(second)).status_code == 200

    logout = client.post("/api/v1/auth/logout", headers=authorization(first))

    assert logout.status_code == 204
    assert logout.content == b""
    assert client.get("/api/v1/me", headers=authorization(first)).status_code == 401
    assert client.get("/api/v1/me", headers=authorization(second)).status_code == 200

    service = client.app.state.voodoo_product_service
    with service.db.connect() as connection:
        rows = connection.execute(
            "SELECT session_reference FROM active_sessions ORDER BY session_reference"
        ).fetchall()
    assert len(rows) == 1
    stored_reference = str(rows[0]["session_reference"])
    assert len(stored_reference) == 64
    assert stored_reference not in {first, second, token_nonce(first), token_nonce(second)}

    session_events = [
        event
        for event in service.list_audit_events()
        if event["action"].startswith("session.")
    ]
    assert [event["action"] for event in session_events] == [
        "session.revoke",
        "session.issue",
        "session.issue",
    ]
    assert all(event["target_id"] not in {first, second} for event in session_events)
    assert service.verify_audit_chain()["valid"] is True


def test_cryptographically_valid_unregistered_session_fails_closed(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    registered = bootstrap(client)
    principal = client.get("/api/v1/me", headers=authorization(registered)).json()
    unregistered = issue_token(
        secret="s" * 64,
        user_id=str(principal["id"]),
        username=str(principal["username"]),
        role=str(principal["role"]),
        ttl_seconds=900,
    )

    response = client.get("/api/v1/me", headers=authorization(unregistered))

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication session is inactive"}


def test_active_session_rows_are_immutable_and_revocation_is_idempotently_denied(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    token = bootstrap(client)
    service = client.app.state.voodoo_product_service

    with (
        pytest.raises(DatabaseIntegrityError, match="database integrity constraint failed"),
        service.db.transaction() as connection,
    ):
        connection.execute("UPDATE active_sessions SET expires_at = expires_at + 1")

    assert client.post("/api/v1/auth/logout", headers=authorization(token)).status_code == 204
    replay = client.post("/api/v1/auth/logout", headers=authorization(token))
    assert replay.status_code == 401
    assert replay.json() == {"detail": "authentication session is inactive"}


def test_session_registration_removes_expired_rows_and_preserves_audit(
    tmp_path: Path,
) -> None:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )
    product = ProductService(config)
    user_id = str(
        product.bootstrap_admin(
            username="admin",
            password="VeryStrongAdminPassword1!",
            token="b" * 48,
        )["user_id"]
    )
    now = [100]
    lifecycle = SessionLifecycleService(
        database=product.db,
        audit_ledger=product.audit_ledger,
        session_reference_factory=lambda session_id: session_reference(
            secret=config.session_signing_secret,
            session_id=session_id,
        ),
        clock=lambda: now[0],
    )
    lifecycle.register_session(
        session_id="expired-session-0001",
        user_id=user_id,
        issued_at=90,
        expires_at=101,
    )
    now[0] = 102
    lifecycle.register_session(
        session_id="current-session-0002",
        user_id=user_id,
        issued_at=102,
        expires_at=202,
    )

    with product.db.connect() as connection:
        rows = connection.execute(
            "SELECT user_id, issued_at, expires_at FROM active_sessions"
        ).fetchall()
    assert [tuple(row) for row in rows] == [(user_id, 102, 202)]
    assert [
        event["action"]
        for event in product.list_audit_events()
        if event["action"] == "session.issue"
    ] == ["session.issue", "session.issue"]


def test_session_registration_rolls_back_when_audit_append_fails(tmp_path: Path) -> None:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )
    product = ProductService(config)
    user_id = str(
        product.bootstrap_admin(
            username="admin",
            password="VeryStrongAdminPassword1!",
            token="b" * 48,
        )["user_id"]
    )

    class FailingAuditLedger:
        db = product.db

        def append(self, *_: object, **__: object) -> dict[str, object]:
            raise RuntimeError("audit unavailable")

    lifecycle = SessionLifecycleService(
        database=product.db,
        audit_ledger=FailingAuditLedger(),  # type: ignore[arg-type]
        session_reference_factory=lambda session_id: session_reference(
            secret=config.session_signing_secret,
            session_id=session_id,
        ),
        clock=lambda: 100,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        lifecycle.register_session(
            session_id="rollback-session-0003",
            user_id=user_id,
            issued_at=90,
            expires_at=190,
        )
    with product.db.connect() as connection:
        count = connection.execute("SELECT COUNT(*) FROM active_sessions").fetchone()
    assert int(count[0]) == 0


def test_administrator_revokes_all_target_sessions_atomically(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    created = client.post(
        "/api/v1/users",
        headers=authorization(admin),
        json={
            "username": "operator",
            "password": "VeryStrongOperatorPassword1!",
            "role": "operator",
        },
    )
    assert created.status_code == 201, created.text
    user_id = str(created.json()["id"])
    tokens = []
    for _ in range(2):
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "operator", "password": "VeryStrongOperatorPassword1!"},
        )
        assert login.status_code == 200, login.text
        tokens.append(str(login.json()["token"]))

    revoked = client.post(
        f"/api/v1/users/{user_id}/sessions/revoke",
        headers=authorization(admin),
        json={"reason": "suspected credential compromise"},
    )

    assert revoked.status_code == 200, revoked.text
    assert revoked.json() == {"user_id": user_id, "revoked_count": 2}
    assert all(
        client.get("/api/v1/me", headers=authorization(token)).status_code == 401
        for token in tokens
    )
    assert client.get("/api/v1/me", headers=authorization(admin)).status_code == 200
    event = next(
        item
        for item in client.app.state.voodoo_product_service.list_audit_events()
        if item["action"] == "session.revoke_all"
    )
    assert event["target_id"] == user_id
    assert event["payload"] == {
        "reason": "suspected credential compromise",
        "revoked_count": 2,
    }
    assert all(token not in json.dumps(event) for token in tokens)


def test_revoke_all_is_admin_only_and_idempotent(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    created = client.post(
        "/api/v1/users",
        headers=authorization(admin),
        json={
            "username": "viewer",
            "password": "VeryStrongViewerPassword1!",
            "role": "viewer",
        },
    )
    user_id = str(created.json()["id"])
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "VeryStrongViewerPassword1!"},
    )
    viewer = str(login.json()["token"])

    denied = client.post(
        f"/api/v1/users/{user_id}/sessions/revoke",
        headers=authorization(viewer),
        json={"reason": "operator requested revocation"},
    )
    assert denied.status_code == 403
    assert client.get("/api/v1/me", headers=authorization(viewer)).status_code == 200

    first = client.post(
        f"/api/v1/users/{user_id}/sessions/revoke",
        headers=authorization(admin),
        json={"reason": "operator requested revocation"},
    )
    second = client.post(
        f"/api/v1/users/{user_id}/sessions/revoke",
        headers=authorization(admin),
        json={"reason": "confirm incident containment"},
    )

    assert first.json()["revoked_count"] == 1
    assert second.json()["revoked_count"] == 0
    missing = client.post(
        "/api/v1/users/usr_missing/sessions/revoke",
        headers=authorization(admin),
        json={"reason": "confirm incident containment"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "user not found"}


def test_revoke_all_rolls_back_when_audit_append_fails(tmp_path: Path) -> None:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )
    product = ProductService(config)
    user_id = str(
        product.bootstrap_admin(
            username="admin",
            password="VeryStrongAdminPassword1!",
            token="b" * 48,
        )["user_id"]
    )
    lifecycle = SessionLifecycleService(
        database=product.db,
        audit_ledger=product.audit_ledger,
        session_reference_factory=lambda session_id: session_reference(
            secret=config.session_signing_secret,
            session_id=session_id,
        ),
        clock=lambda: 100,
    )
    lifecycle.register_session(
        session_id="incident-session-0004",
        user_id=user_id,
        issued_at=90,
        expires_at=190,
    )

    class FailingAuditLedger:
        db = product.db

        def append(self, *_: object, **__: object) -> dict[str, object]:
            raise RuntimeError("audit unavailable")

    failing = SessionLifecycleService(
        database=product.db,
        audit_ledger=FailingAuditLedger(),  # type: ignore[arg-type]
        session_reference_factory=lambda session_id: session_reference(
            secret=config.session_signing_secret,
            session_id=session_id,
        ),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        failing.revoke_all_sessions(
            user_id=user_id,
            actor_id=user_id,
            reason="incident containment",
        )
    with product.db.connect() as connection:
        count = connection.execute("SELECT COUNT(*) FROM active_sessions").fetchone()
    assert int(count[0]) == 1
