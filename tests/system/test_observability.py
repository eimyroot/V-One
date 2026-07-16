from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.observability import (
    PRODUCT_LOGGER_NAME,
    JsonLogFormatter,
    StructuredRequestLoggingMiddleware,
)


def build_logger(stream: io.StringIO, name: str) -> logging.Logger:
    logger = logging.Logger(name, level=logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    return logger


def records(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


def build_observed_app(stream: io.StringIO) -> FastAPI:
    app = FastAPI()

    @app.get("/items/{item_id}")
    def item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    @app.get("/explode")
    def explode() -> None:
        raise RuntimeError("SECRET-MUST-NOT-ENTER-LOGS")

    app.add_middleware(
        StructuredRequestLoggingMiddleware,
        logger=build_logger(stream, "voodoo-observability-test"),
        environment="test",
    )
    return app


def test_request_log_uses_route_template_and_omits_raw_url(tmp_path: Path) -> None:
    del tmp_path
    stream = io.StringIO()
    client = TestClient(build_observed_app(stream))
    request_id = "req-safe-12345678"

    response = client.get(
        "/items/SENSITIVE-ITEM?token=SECRET-QUERY",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    event = records(stream)[0]
    assert event["event"] == "http.request.completed"
    assert event["request_id"] == request_id
    assert event["route"] == "/items/{item_id}"
    assert event["status_code"] == 200
    assert "SENSITIVE-ITEM" not in stream.getvalue()
    assert "SECRET-QUERY" not in stream.getvalue()


def test_invalid_request_id_is_replaced_with_server_id() -> None:
    stream = io.StringIO()
    client = TestClient(build_observed_app(stream))

    response = client.get("/items/example", headers={"X-Request-ID": "invalid request id"})

    request_id = response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)
    assert records(stream)[0]["request_id"] == request_id


def test_unhandled_error_is_generic_correlated_and_secret_safe() -> None:
    stream = io.StringIO()
    client = TestClient(build_observed_app(stream), raise_server_exceptions=False)

    response = client.get("/explode", headers={"X-Request-ID": "req-error-12345678"})

    assert response.status_code == 500
    assert response.json() == {"detail": "internal server error"}
    assert response.headers["X-Request-ID"] == "req-error-12345678"
    event = records(stream)[0]
    assert event["status_code"] == 500
    assert event["error_type"] == "RuntimeError"
    assert "SECRET-MUST-NOT-ENTER-LOGS" not in stream.getvalue()


def test_formatter_serializes_only_allowlisted_fields() -> None:
    stream = io.StringIO()
    logger = build_logger(stream, "voodoo-formatter-test")

    logger.warning(
        "ignored raw message SECRET-MESSAGE",
        extra={
            "event": "security.test",
            "request_id": "req-format-12345678",
            "username": "SENSITIVE-USERNAME",
            "password": "SENSITIVE-PASSWORD",
            "authorization": "Bearer SENSITIVE-TOKEN",
            "source": "192.0.2.1",
        },
    )

    serialized = stream.getvalue()
    event = records(stream)[0]
    assert event["event"] == "security.test"
    assert event["request_id"] == "req-format-12345678"
    for forbidden in (
        "SECRET-MESSAGE",
        "SENSITIVE-USERNAME",
        "SENSITIVE-PASSWORD",
        "SENSITIVE-TOKEN",
        "192.0.2.1",
    ):
        assert forbidden not in serialized


def test_auth_security_events_are_correlated_without_credentials(tmp_path: Path) -> None:
    stream = io.StringIO()
    product_logger = logging.getLogger(PRODUCT_LOGGER_NAME)
    previous_handlers = list(product_logger.handlers)
    previous_level = product_logger.level
    previous_propagate = product_logger.propagate
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    handler._voodoo_json_handler = True  # type: ignore[attr-defined]
    product_logger.handlers = [handler]

    try:
        config = ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="BOOTSTRAP-SECRET-THAT-MUST-NOT-LEAK",
            auth_max_failures=2,
        )
        app = FastAPI()
        install_product_platform(app, config=config, repository_root=tmp_path)
        client = TestClient(app)
        bootstrap = client.post(
            "/api/v1/auth/bootstrap",
            headers={"X-Request-ID": "req-bootstrap-1234"},
            json={
                "username": "SENSITIVE-ADMIN",
                "password": "SENSITIVE-ADMIN-PASSWORD",
                "bootstrap_token": "BOOTSTRAP-SECRET-THAT-MUST-NOT-LEAK",
            },
        )
        assert bootstrap.status_code == 201

        denied = client.post(
            "/api/v1/auth/login",
            headers={"X-Request-ID": "req-login-denied-1"},
            json={"username": "SENSITIVE-ADMIN", "password": "SENSITIVE-WRONG-PASSWORD"},
        )
        assert denied.status_code == 401
        limited = client.post(
            "/api/v1/auth/login",
            headers={"X-Request-ID": "req-login-limited-2"},
            json={"username": "SENSITIVE-ADMIN", "password": "SENSITIVE-WRONG-PASSWORD"},
        )
        assert limited.status_code == 429

        captured = records(stream)
        by_event = {str(item["event"]): item for item in captured}
        assert by_event["auth.bootstrap.succeeded"]["request_id"] == "req-bootstrap-1234"
        assert by_event["auth.login.denied"]["request_id"] == "req-login-denied-1"
        assert by_event["auth.login.rate_limited"]["request_id"] == "req-login-limited-2"
        assert int(by_event["auth.login.rate_limited"]["retry_after"]) > 0

        serialized = stream.getvalue()
        for forbidden in (
            "SENSITIVE-ADMIN",
            "SENSITIVE-ADMIN-PASSWORD",
            "SENSITIVE-WRONG-PASSWORD",
            "BOOTSTRAP-SECRET-THAT-MUST-NOT-LEAK",
            "testclient",
        ):
            assert forbidden not in serialized
    finally:
        product_logger.handlers = previous_handlers
        product_logger.setLevel(previous_level)
        product_logger.propagate = previous_propagate
