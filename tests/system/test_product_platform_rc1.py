from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import voodoo_product.receipt as receipt_module
from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig


def build_client(tmp_path: Path, *, production_effects: bool = False) -> TestClient:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
        production_effects_enabled=production_effects,
    )
    app = FastAPI()
    install_product_platform(app, config=config, repository_root=tmp_path)
    return TestClient(app)


def bootstrap(
    client: TestClient, username: str = "admin", password: str = "VeryStrongAdminPassword1!"
) -> str:
    response = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": username, "password": password, "bootstrap_token": "b" * 48},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user(client: TestClient, token: str, username: str, role: str) -> None:
    response = client.post(
        "/api/v1/users",
        headers=headers(token),
        json={"username": username, "password": f"VeryStrongPassword-{username}-1!", "role": role},
    )
    assert response.status_code == 201, response.text


def login(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": f"VeryStrongPassword-{username}-1!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_golden_path_creates_execution_and_verified_receipt(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "developer", "developer")
    create_user(client, admin, "operator", "operator")
    developer = login(client, "developer")
    operator = login(client, "operator")
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    assert workspace["environment"] == "local"

    created = client.post(
        "/api/v1/change-requests",
        headers=headers(developer),
        json={
            "workspace_id": workspace["id"],
            "title": "Write governed artifact",
            "description": "Golden path",
            "risk": "R1",
            "environment": "local",
            "adapter": "write_artifact",
            "payload": {"path": "proof/result.json", "content": {"ok": True}},
        },
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert (
        client.post(
            f"/api/v1/change-requests/{request_id}/submit", headers=headers(developer)
        ).status_code
        == 200
    )
    approved = client.post(
        f"/api/v1/change-requests/{request_id}/decision",
        headers=headers(operator),
        json={"decision": "APPROVED", "reason": "Validated scope"},
    )
    assert approved.status_code == 200, approved.text
    executed = client.post(
        f"/api/v1/change-requests/{request_id}/execute",
        headers={**headers(operator), "Idempotency-Key": "golden-1"},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "SUCCEEDED"
    assert executed.json()["receipt_id"]
    assert (tmp_path / "sandboxes" / workspace["id"] / "proof" / "result.json").exists()
    evidence = client.get("/api/v1/evidence/verify", headers=headers(admin))
    assert evidence.status_code == 200
    assert evidence.json()["receipts"]["valid"] is True
    assert evidence.json()["audit"]["valid"] is True


def test_requester_cannot_self_approve(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    request = client.post(
        "/api/v1/change-requests",
        headers=headers(admin),
        json={
            "workspace_id": workspace["id"],
            "title": "Self approval",
            "risk": "R1",
            "environment": "local",
            "adapter": "echo",
            "payload": {},
        },
    ).json()
    client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(admin))
    response = client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(admin),
        json={"decision": "APPROVED", "reason": "Should fail"},
    )
    assert response.status_code == 403


def test_production_requires_two_approvers_and_remains_disabled(tmp_path: Path) -> None:
    client = build_client(tmp_path, production_effects=False)
    admin = bootstrap(client)
    for username in ("developer", "operator1", "operator2"):
        create_user(client, admin, username, "developer" if username == "developer" else "operator")
    developer = login(client, "developer")
    operator1 = login(client, "operator1")
    operator2 = login(client, "operator2")
    workspace_response = client.post(
        "/api/v1/workspaces",
        headers=headers(admin),
        json={"name": "Production target", "environment": "production"},
    )
    assert workspace_response.status_code == 201, workspace_response.text
    workspace = workspace_response.json()
    request = client.post(
        "/api/v1/change-requests",
        headers=headers(developer),
        json={
            "workspace_id": workspace["id"],
            "title": "Production request",
            "risk": "R3",
            "environment": "production",
            "adapter": "echo",
            "payload": {},
        },
    ).json()
    client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(developer))
    first = client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(operator1),
        json={"decision": "APPROVED", "reason": "First review"},
    )
    assert first.json()["status"] == "REVIEW_REQUIRED"
    second = client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(operator2),
        json={"decision": "APPROVED", "reason": "Second review"},
    )
    assert second.json()["status"] == "APPROVED"
    execution = client.post(
        f"/api/v1/change-requests/{request['id']}/execute", headers=headers(operator1)
    )
    assert execution.status_code == 403
    assert "production effects remain disabled" in execution.text


def test_change_request_environment_must_match_workspace(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    workspace_response = client.post(
        "/api/v1/workspaces",
        headers=headers(admin),
        json={"name": "Protected production", "environment": "production"},
    )
    assert workspace_response.status_code == 201, workspace_response.text
    workspace = workspace_response.json()

    response = client.post(
        "/api/v1/change-requests",
        headers=headers(admin),
        json={
            "workspace_id": workspace["id"],
            "title": "Environment downgrade",
            "risk": "R3",
            "environment": "local",
            "adapter": "echo",
            "payload": {},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "change request environment must match workspace environment"
    )
    assert client.get("/api/v1/change-requests", headers=headers(admin)).json() == []


def test_path_traversal_fails_closed(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "developer", "developer")
    create_user(client, admin, "operator", "operator")
    developer = login(client, "developer")
    operator = login(client, "operator")
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    request = client.post(
        "/api/v1/change-requests",
        headers=headers(developer),
        json={
            "workspace_id": workspace["id"],
            "title": "Traversal",
            "risk": "R2",
            "environment": "local",
            "adapter": "write_artifact",
            "payload": {"path": "../../escape.txt", "content": "no"},
        },
    ).json()
    client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(developer))
    client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(operator),
        json={"decision": "APPROVED", "reason": "Boundary test"},
    )
    execution = client.post(
        f"/api/v1/change-requests/{request['id']}/execute", headers=headers(operator)
    )
    assert execution.status_code == 200
    assert execution.json()["status"] == "FAILED"
    assert not (tmp_path / "escape.txt").exists()


def test_emergency_stop_blocks_execution(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "developer", "developer")
    create_user(client, admin, "operator", "operator")
    developer = login(client, "developer")
    operator = login(client, "operator")
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    request = client.post(
        "/api/v1/change-requests",
        headers=headers(developer),
        json={
            "workspace_id": workspace["id"],
            "title": "Stop test",
            "risk": "R1",
            "environment": "local",
            "adapter": "echo",
            "payload": {},
        },
    ).json()
    client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(developer))
    client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(operator),
        json={"decision": "APPROVED", "reason": "Ready"},
    )
    stop = client.post(
        "/api/v1/system/emergency-stop",
        headers=headers(admin),
        json={"active": True, "reason": "Test incident"},
    )
    assert stop.status_code == 200
    execution = client.post(
        f"/api/v1/change-requests/{request['id']}/execute", headers=headers(operator)
    )
    assert execution.status_code == 403


def test_console_and_openapi_are_available(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    console = client.get("/console")
    assert console.status_code == 200
    assert "VOODOO One" in console.text
    assert 'id="change-environment" readonly' in console.text
    css = client.get("/console/assets/styles.css")
    assert css.status_code == 200
    javascript = client.get("/console/assets/app.js")
    assert javascript.status_code == 200
    assert "syncChangeEnvironment" in javascript.text
    assert "api('/auth/logout',{method:'POST'})" in javascript.text
    assert "Serverové odvolání relace se nepodařilo potvrdit" in javascript.text
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/change-requests" in schema.json()["paths"]
    assert "/api/v1/auth/logout" in schema.json()["paths"]


def test_roles_are_permission_based_not_linear(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "auditor", "auditor")
    create_user(client, admin, "operator", "operator")
    auditor = login(client, "auditor")
    operator = login(client, "operator")

    denied_stop = client.post(
        "/api/v1/system/emergency-stop",
        headers=headers(auditor),
        json={"active": True, "reason": "Auditor must not control runtime"},
    )
    assert denied_stop.status_code == 403

    denied_user = client.post(
        "/api/v1/users",
        headers=headers(operator),
        json={
            "username": "unauthorized",
            "password": "VeryStrongUnauthorizedPassword1!",
            "role": "viewer",
        },
    )
    assert denied_user.status_code == 403

    evidence = client.get("/api/v1/evidence/verify", headers=headers(auditor))
    assert evidence.status_code == 200


def test_tampered_token_is_rejected(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = bootstrap(client)
    version, payload, signature = token.split(".", 2)
    signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered = f"{version}.{payload}.{signature}"
    response = client.get("/api/v1/me", headers=headers(tampered))
    assert response.status_code == 401


def test_execution_idempotency_returns_original_execution(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "developer", "developer")
    create_user(client, admin, "operator", "operator")
    developer = login(client, "developer")
    operator = login(client, "operator")
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    request = client.post(
        "/api/v1/change-requests",
        headers=headers(developer),
        json={
            "workspace_id": workspace["id"],
            "title": "Idempotency",
            "risk": "R1",
            "environment": "local",
            "adapter": "echo",
            "payload": {"value": 1},
        },
    ).json()
    client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(developer))
    client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(operator),
        json={"decision": "APPROVED", "reason": "Ready"},
    )
    request_headers = {**headers(operator), "Idempotency-Key": "stable-key"}
    first = client.post(f"/api/v1/change-requests/{request['id']}/execute", headers=request_headers)
    second = client.post(
        f"/api/v1/change-requests/{request['id']}/execute", headers=request_headers
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_receipt_tampering_is_detected(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "developer", "developer")
    create_user(client, admin, "operator", "operator")
    developer = login(client, "developer")
    operator = login(client, "operator")
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    request = client.post(
        "/api/v1/change-requests",
        headers=headers(developer),
        json={
            "workspace_id": workspace["id"],
            "title": "Tamper check",
            "risk": "R1",
            "environment": "local",
            "adapter": "echo",
            "payload": {},
        },
    ).json()
    client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(developer))
    client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(operator),
        json={"decision": "APPROVED", "reason": "Ready"},
    )
    client.post(f"/api/v1/change-requests/{request['id']}/execute", headers=headers(operator))

    service = client.app.state.voodoo_product_service
    with service.db.connect() as connection:
        connection.execute("UPDATE receipts SET payload_json = '{\"tampered\":true}'")
        connection.commit()

    verification = client.get("/api/v1/evidence/verify", headers=headers(admin))
    assert verification.status_code == 200
    assert verification.json()["receipts"]["valid"] is False


def test_receipt_sequence_is_stable_when_timestamps_collide(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "operator", "operator")
    operator = login(client, "operator")
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    service = client.app.state.voodoo_product_service
    original_new_id = receipt_module.new_id
    receipt_ids = iter(("rcpt_z", "rcpt_a"))

    monkeypatch.setattr(
        receipt_module,
        "utc_now",
        lambda: "2026-07-16T12:00:00.000+00:00",
    )

    def controlled_new_id(prefix: str) -> str:
        return next(receipt_ids) if prefix == "rcpt" else original_new_id(prefix)

    monkeypatch.setattr(receipt_module, "new_id", controlled_new_id)

    for index in range(2):
        request = client.post(
            "/api/v1/change-requests",
            headers=headers(admin),
            json={
                "workspace_id": workspace["id"],
                "title": f"Receipt ordering {index}",
                "risk": "R1",
                "environment": "local",
                "adapter": "echo",
                "payload": {"index": index},
            },
        ).json()
        client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(admin))
        client.post(
            f"/api/v1/change-requests/{request['id']}/decision",
            headers=headers(operator),
            json={"decision": "APPROVED", "reason": "receipt ordering regression"},
        )
        execution = client.post(
            f"/api/v1/change-requests/{request['id']}/execute",
            headers={**headers(operator), "Idempotency-Key": f"receipt-order-{index}"},
        )
        assert execution.status_code == 200, execution.text

    receipts = service.list_receipts()
    assert [(row["sequence"], row["id"]) for row in receipts] == [
        (2, "rcpt_a"),
        (1, "rcpt_z"),
    ]
    verification = service.verify_receipt_chain()
    assert verification == {
        "valid": True,
        "count": 2,
        "head": receipts[0]["receipt_hash"],
    }


def test_inactive_account_invalidates_existing_session(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "operator", "operator")
    operator = login(client, "operator")
    service = client.app.state.voodoo_product_service
    with service.db.transaction() as connection:
        connection.execute("UPDATE users SET active = 0 WHERE username = 'operator'")

    response = client.get("/api/v1/me", headers=headers(operator))
    assert response.status_code == 401


def test_role_change_applies_to_existing_session(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "operator", "operator")
    operator = login(client, "operator")
    service = client.app.state.voodoo_product_service
    with service.db.transaction() as connection:
        connection.execute("UPDATE users SET role = 'viewer' WHERE username = 'operator'")

    response = client.post(
        "/api/v1/system/emergency-stop",
        headers=headers(operator),
        json={"active": True, "reason": "must be denied"},
    )
    assert response.status_code == 403


def test_symlinked_sandbox_directory_fails_closed(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    create_user(client, admin, "developer", "developer")
    create_user(client, admin, "operator", "operator")
    developer = login(client, "developer")
    operator = login(client, "operator")
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace_root = tmp_path / "sandboxes" / workspace["id"]
    workspace_root.mkdir(parents=True)
    (workspace_root / "linked").symlink_to(outside, target_is_directory=True)

    request = client.post(
        "/api/v1/change-requests",
        headers=headers(developer),
        json={
            "workspace_id": workspace["id"],
            "title": "Symlink boundary",
            "risk": "R2",
            "environment": "local",
            "adapter": "write_artifact",
            "payload": {"path": "linked/escape.txt", "content": "blocked"},
        },
    ).json()
    client.post(f"/api/v1/change-requests/{request['id']}/submit", headers=headers(developer))
    client.post(
        f"/api/v1/change-requests/{request['id']}/decision",
        headers=headers(operator),
        json={"decision": "APPROVED", "reason": "boundary test"},
    )
    execution = client.post(
        f"/api/v1/change-requests/{request['id']}/execute",
        headers=headers(operator),
    )
    assert execution.status_code == 200
    assert execution.json()["status"] == "FAILED"
    assert not (outside / "escape.txt").exists()


def test_oversized_change_payload_is_rejected(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin = bootstrap(client)
    workspace = client.get("/api/v1/workspaces", headers=headers(admin)).json()[0]
    response = client.post(
        "/api/v1/change-requests",
        headers=headers(admin),
        json={
            "workspace_id": workspace["id"],
            "title": "Oversized change",
            "risk": "R2",
            "environment": "local",
            "adapter": "echo",
            "payload": {"content": "x" * 65_536},
        },
    )
    assert response.status_code == 422
