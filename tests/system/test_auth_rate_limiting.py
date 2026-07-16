from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import AuthRateLimitExceeded


def build_client(
    tmp_path: Path,
    *,
    auth_max_failures: int = 3,
    auth_source_max_failures: int = 20,
) -> TestClient:
    config = ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
        auth_max_failures=auth_max_failures,
        auth_source_max_failures=auth_source_max_failures,
        auth_window_seconds=300,
        auth_lockout_seconds=900,
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
    return response.json()["token"]


def create_operator(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "operator",
            "password": "VeryStrongPassword-operator-1!",
            "role": "operator",
        },
    )
    assert response.status_code == 201, response.text


def login(client: TestClient, *, password: str) -> object:
    return client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": password},
    )


def expire_rate_limits(client: TestClient) -> None:
    service = client.app.state.voodoo_product_service
    with service.db.transaction() as connection:
        connection.execute("UPDATE auth_rate_limits SET blocked_until = 0, window_started_at = 0")


def test_login_limit_persists_without_storing_raw_identity(tmp_path: Path) -> None:
    first_client = build_client(tmp_path)
    create_operator(first_client, bootstrap(first_client))

    assert login(first_client, password="wrong-1").status_code == 401
    assert login(first_client, password="wrong-2").status_code == 401
    limited = login(first_client, password="wrong-3")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0

    service = first_client.app.state.voodoo_product_service
    with service.db.connect() as connection:
        rows = connection.execute(
            "SELECT scope, key_hash FROM auth_rate_limits ORDER BY scope"
        ).fetchall()
    assert {row["scope"] for row in rows} == {"login.account", "login.source"}
    assert all(len(row["key_hash"]) == 64 for row in rows)
    assert all("operator" not in row["key_hash"] for row in rows)
    first_client.close()

    restarted_client = build_client(tmp_path)
    still_limited = login(restarted_client, password="VeryStrongPassword-operator-1!")
    assert still_limited.status_code == 429

    expire_rate_limits(restarted_client)
    recovered = login(restarted_client, password="VeryStrongPassword-operator-1!")
    assert recovered.status_code == 200


def test_successful_login_clears_account_and_source_failures(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    create_operator(client, bootstrap(client))

    assert login(client, password="wrong-1").status_code == 401
    assert login(client, password="wrong-2").status_code == 401
    assert login(client, password="VeryStrongPassword-operator-1!").status_code == 200

    service = client.app.state.voodoo_product_service
    with service.db.connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM auth_rate_limits").fetchone()
    assert count["count"] == 0
    assert login(client, password="wrong-3").status_code == 401


def test_source_limit_spans_distinct_unknown_accounts(tmp_path: Path) -> None:
    client = build_client(
        tmp_path,
        auth_max_failures=3,
        auth_source_max_failures=3,
    )
    bootstrap(client)

    for username in ("unknown-a", "unknown-b"):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "wrong"},
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={"username": "unknown-c", "password": "wrong"},
    )
    assert limited.status_code == 429


def test_bootstrap_limit_persists_and_recovers_after_expiry(tmp_path: Path) -> None:
    client = build_client(
        tmp_path,
        auth_max_failures=2,
        auth_source_max_failures=20,
    )
    request = {
        "username": "admin",
        "password": "VeryStrongAdminPassword1!",
        "bootstrap_token": "x" * 48,
    }

    assert client.post("/api/v1/auth/bootstrap", json=request).status_code == 403
    limited = client.post("/api/v1/auth/bootstrap", json=request)
    assert limited.status_code == 429

    request["bootstrap_token"] = "b" * 48
    assert client.post("/api/v1/auth/bootstrap", json=request).status_code == 429

    expire_rate_limits(client)
    recovered = client.post("/api/v1/auth/bootstrap", json=request)
    assert recovered.status_code == 201


def test_concurrent_failures_are_counted_atomically(tmp_path: Path) -> None:
    client = build_client(
        tmp_path,
        auth_max_failures=5,
        auth_source_max_failures=100,
    )
    service = client.app.state.voodoo_product_service

    def record_failure(index: int) -> bool:
        try:
            service.record_login_failure(username="victim", source=f"source-{index}")
        except AuthRateLimitExceeded:
            return True
        return False

    with ThreadPoolExecutor(max_workers=12) as executor:
        limited = list(executor.map(record_failure, range(12)))

    assert sum(limited) == 8
    with service.db.connect() as connection:
        account = connection.execute(
            """
            SELECT failure_count, blocked_until
            FROM auth_rate_limits WHERE scope = 'login.account'
            """
        ).fetchone()
    assert account["failure_count"] == 5
    assert account["blocked_until"] > 0
