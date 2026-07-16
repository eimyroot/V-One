from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import voodoo_product.service as service_module
from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.security import ROLE_PERMISSIONS
from voodoo_product.service import ProductService


def prepared_execution(tmp_path: Path) -> tuple[ProductService, dict[str, Any]]:
    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
            execution_timeout_seconds=10,
            execution_lease_seconds=40,
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
    reviewer = service.create_user(
        actor_id=bootstrap["user_id"],
        username="security-reviewer",
        password="VeryStrongReviewerPassword1!",
        role="security_reviewer",
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Crash recovery",
        description="",
        risk="R2",
        environment="local",
        adapter="echo",
        payload={"operation": "at-most-once"},
    )
    service.submit_change_request(actor_id=bootstrap["user_id"], request_id=request["id"])
    service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="exercise crash fencing",
    )
    return service, {
        "administrator_id": bootstrap["user_id"],
        "operator_id": operator["id"],
        "reviewer_id": reviewer["id"],
        "request_id": request["id"],
    }


def test_expired_execution_recovery_fences_late_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context = prepared_execution(tmp_path)
    adapter_started = Event()
    release_adapter = Event()

    def blocking_adapter(*_: object, **__: object) -> dict[str, Any]:
        adapter_started.set()
        if not release_adapter.wait(timeout=5):
            raise RuntimeError("test adapter release timed out")
        return {"effect": "INERT", "late_result": True}

    monkeypatch.setattr(service_module, "execute_adapter", blocking_adapter)
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        service.execute_change_request,
        actor_id=context["operator_id"],
        request_id=context["request_id"],
        idempotency_key="crash-recovery-key",
        repository_root=tmp_path,
    )
    try:
        assert adapter_started.wait(timeout=5)
        execution = service.list_executions()[0]

        with pytest.raises(PermissionError, match="emergency stop"):
            service.recover_execution(
                actor_id=context["reviewer_id"],
                execution_id=execution["id"],
                reason="worker disappeared",
            )

        service.set_emergency_stop(
            actor_id=context["reviewer_id"],
            active=True,
            reason="recover expired execution",
        )
        with pytest.raises(RuntimeError, match="lease has not expired"):
            service.recover_execution(
                actor_id=context["reviewer_id"],
                execution_id=execution["id"],
                reason="worker disappeared",
            )

        with service.db.transaction() as connection:
            connection.execute(
                "UPDATE executions SET lease_expires_at = ? WHERE id = ?",
                ("2000-01-01T00:00:00.000+00:00", execution["id"]),
            )

        recovered = service.recover_execution(
            actor_id=context["reviewer_id"],
            execution_id=execution["id"],
            reason="worker disappeared after durable start",
        )
        assert recovered["status"] == "INTERRUPTED"
        assert recovered["output"]["outcome"] == "INDETERMINATE"
        assert recovered["lease_expires_at"] is None
        assert "fence" not in recovered

        release_adapter.set()
        late_result = future.result(timeout=5)
        assert late_result["status"] == "INTERRUPTED"

        retry = service.execute_change_request(
            actor_id=context["operator_id"],
            request_id=context["request_id"],
            idempotency_key="crash-recovery-key",
            repository_root=tmp_path,
        )
        assert retry["id"] == execution["id"]
        assert retry["status"] == "INTERRUPTED"
    finally:
        release_adapter.set()
        executor.shutdown(wait=True)

    assert service.get_change_request(context["request_id"])["status"] == "FAILED"
    receipts = service.list_receipts()
    assert len(receipts) == 1
    assert receipts[0]["payload"]["status"] == "INTERRUPTED"
    assert receipts[0]["payload"]["outcome"] == "INDETERMINATE"
    assert service.verify_receipt_chain()["valid"] is True
    actions = [event["action"] for event in service.list_audit_events(limit=1_000)]
    assert actions.count("execution.start") == 1
    assert actions.count("execution.interrupted") == 1
    assert "execution.succeeded" not in actions


def test_recovery_permission_is_not_granted_to_execution_operator() -> None:
    assert "execution.recover" in ROLE_PERMISSIONS["security_reviewer"]
    assert "execution.recover" not in ROLE_PERMISSIONS["operator"]


def test_recovery_api_enforces_role_and_emergency_stop(tmp_path: Path) -> None:
    app = FastAPI()
    install_product_platform(
        app,
        config=ProductConfig(
            environment="test",
            database_path=tmp_path / "api.sqlite3",
            sandbox_root=tmp_path / "api-sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        ),
        repository_root=tmp_path,
    )
    client = TestClient(app)
    bootstrap = client.post(
        "/api/v1/auth/bootstrap",
        json={
            "username": "admin",
            "password": "VeryStrongAdminPassword1!",
            "bootstrap_token": "b" * 48,
        },
    )
    assert bootstrap.status_code == 201
    admin_token = bootstrap.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    for username, role, password in (
        ("operator", "operator", "VeryStrongOperatorPassword1!"),
        ("reviewer", "security_reviewer", "VeryStrongReviewerPassword1!"),
    ):
        created = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={"username": username, "password": password, "role": role},
        )
        assert created.status_code == 201

    def login(username: str, password: str) -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        return str(response.json()["token"])

    operator_token = login("operator", "VeryStrongOperatorPassword1!")
    reviewer_token = login("reviewer", "VeryStrongReviewerPassword1!")
    payload = {"reason": "recover missing execution"}

    operator = client.post(
        "/api/v1/executions/exec_missing/recover",
        headers={"Authorization": f"Bearer {operator_token}"},
        json=payload,
    )
    assert operator.status_code == 403
    assert operator.json()["detail"] == "permission required: execution.recover"

    reviewer = client.post(
        "/api/v1/executions/exec_missing/recover",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json=payload,
    )
    assert reviewer.status_code == 403
    assert reviewer.json()["detail"] == "emergency stop must be active for execution recovery"


def test_execution_lease_configuration_must_outlive_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="execution lease"):
        ProductConfig(
            environment="test",
            database_path=tmp_path / "invalid.sqlite3",
            sandbox_root=tmp_path / "invalid-sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
            execution_timeout_seconds=120,
            execution_lease_seconds=149,
        )


def test_default_container_grace_exceeds_execution_timeout(tmp_path: Path) -> None:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "not-opened.sqlite3",
        sandbox_root=tmp_path / "not-created",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )
    compose = (Path(__file__).resolve().parents[2] / "docker-compose.product.yml").read_text(
        encoding="utf-8"
    )

    assert config.execution_timeout_seconds == 120
    assert config.execution_lease_seconds == 180
    assert "stop_grace_period: 150s" in compose
