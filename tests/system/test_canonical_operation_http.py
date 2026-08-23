from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from voodoo_product.canonical_operation_http import create_canonical_operation_router
from voodoo_product.security import Principal
from voodoo_product.terminal_profile import READ_ONLY_TERMINAL_PROFILE

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
D6 = "6" * 64


class FakeIdentityProvider:
    def authenticate_bearer(self, token: str) -> Principal:
        if token == "operator-token":
            return Principal(user_id="usr-operator", username="operator", role="operator")
        if token == "developer-token":
            return Principal(user_id="usr-developer", username="developer", role="developer")
        if token == "viewer-token":
            return Principal(user_id="usr-viewer", username="viewer", role="viewer")
        raise PermissionError("invalid session")


class FakeRuntime:
    def __init__(self, *, verdict: str = "NOT_VERIFIED", error: Exception | None = None) -> None:
        self.read_terminal = object()
        self.verdict = verdict
        self.error = error
        self.calls: list[dict[str, str]] = []

    def run_read_only(self, **kwargs: str) -> object:
        self.calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        prepared = SimpleNamespace(
            request_id=kwargs["request_id"],
            execution_id="exec-1",
            capability="github.read-ref/v1",
            environment="staging",
            target_digest=D1,
            terminal_profile=READ_ONLY_TERMINAL_PROFILE,
            execution_epoch=3,
            lease_digest=D2,
            execution_capsule_digest=D3,
        )
        verification = SimpleNamespace(
            verdict=self.verdict,
            reason="OBSERVED_STATE_MISMATCH" if self.verdict == "NOT_VERIFIED" else "OBSERVED_STATE_MATCH",
            verification_strength_class="INDEPENDENT_PROVIDER_READBACK",
            result_digest=D4,
            observed_post_state_digest=D5,
            verifier_identity_digest=D6,
            checked_at="2026-08-23T06:00:00.000+00:00",
        )
        return SimpleNamespace(
            prepared=prepared,
            runner_observation=SimpleNamespace(observation_digest="a" * 64),
            verification_result=verification,
        )


def client(runtime: object | None) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_canonical_operation_router(
            identity_provider=FakeIdentityProvider(),  # type: ignore[arg-type]
            runtime=runtime,  # type: ignore[arg-type]
        )
    )
    return TestClient(app)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def read_headers(token: str = "operator-token") -> dict[str, str]:
    return {**auth(token), "Idempotency-Key": "canonical-read-1"}


def read_body(**extra: object) -> dict[str, object]:
    return {"correlation_id": "corr-canonical-1", **extra}


def test_status_requires_authentication_and_reports_no_write_surface() -> None:
    runtime = FakeRuntime()
    api = client(runtime)

    assert api.get("/api/v1/operations/status").status_code == 401
    response = api.get("/api/v1/operations/status", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json() == {
        "schema": "vone.canonical-operation-api-status/v1",
        "configured": True,
        "read_terminal_configured": True,
        "write_routes_exposed": False,
        "provider_write_effects_exposed": False,
    }


def test_read_fails_closed_when_runtime_is_not_configured() -> None:
    api = client(None)

    response = api.post(
        "/api/v1/operations/req-12345/read",
        headers=read_headers(),
        json=read_body(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "canonical operation runtime is not configured"


def test_read_requires_execution_permission() -> None:
    api = client(FakeRuntime())

    response = api.post(
        "/api/v1/operations/req-12345/read",
        headers=read_headers("developer-token"),
        json=read_body(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "permission required: execution.run"


def test_caller_cannot_select_terminal_profile() -> None:
    runtime = FakeRuntime()
    api = client(runtime)

    response = api.post(
        "/api/v1/operations/req-12345/read",
        headers=read_headers(),
        json=read_body(terminal_profile="BOUNDED_MUTATION_VERIFIED"),
    )

    assert response.status_code == 422
    assert runtime.calls == []


def test_read_requires_idempotency_key() -> None:
    runtime = FakeRuntime()
    api = client(runtime)

    response = api.post(
        "/api/v1/operations/req-12345/read",
        headers=auth("operator-token"),
        json=read_body(),
    )

    assert response.status_code == 422
    assert runtime.calls == []


def test_execution_success_and_independent_verification_remain_separate() -> None:
    runtime = FakeRuntime(verdict="NOT_VERIFIED")
    api = client(runtime)

    response = api.post(
        "/api/v1/operations/req-12345/read",
        headers=read_headers(),
        json=read_body(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "vone.canonical-operation-read/v1"
    assert payload["operation"]["terminal_profile"] == READ_ONLY_TERMINAL_PROFILE
    assert payload["execution"]["status"] == "SUCCEEDED"
    assert payload["verification"]["verdict"] == "NOT_VERIFIED"
    assert payload["verification"]["reason"] == "OBSERVED_STATE_MISMATCH"
    assert runtime.calls == [
        {
            "actor_id": "usr-operator",
            "request_id": "req-12345",
            "idempotency_key": "canonical-read-1",
            "correlation_id": "corr-canonical-1",
        }
    ]


def test_runtime_permission_failure_is_not_translated_to_execution_success() -> None:
    runtime = FakeRuntime(error=PermissionError("CANONICAL_PIPELINE_REQUIRED_CAPABILITY_MISMATCH"))
    api = client(runtime)

    response = api.post(
        "/api/v1/operations/req-12345/read",
        headers=read_headers(),
        json=read_body(),
    )

    assert response.status_code == 403
    assert "REQUIRED_CAPABILITY_MISMATCH" in response.text


def test_openapi_exposes_read_only_canonical_operation_surface() -> None:
    api = client(FakeRuntime())
    paths = api.get("/openapi.json").json()["paths"]

    assert "/api/v1/operations/status" in paths
    assert "/api/v1/operations/{request_id}/read" in paths
    assert all("create-ref" not in path for path in paths)
    assert all("rollback" not in path for path in paths)
