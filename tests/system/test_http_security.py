from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voodoo_product.api import install_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.http_security import CONTENT_SECURITY_POLICY

ROOT = Path(__file__).resolve().parents[2]


def build_app(
    tmp_path: Path,
    *,
    environment: str = "test",
    trusted_hosts: tuple[str, ...] = ("testserver",),
) -> FastAPI:
    app = FastAPI()
    install_product_platform(
        app,
        config=ProductConfig(
            environment=environment,
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
            trusted_hosts=trusted_hosts,
        ),
        repository_root=tmp_path,
    )
    return app


@pytest.mark.parametrize(
    "path",
    ["/api/v1/health", "/console", "/console/assets/app.js", "/missing"],
)
def test_security_headers_cover_application_responses(tmp_path: Path, path: str) -> None:
    client = TestClient(build_app(tmp_path))

    response = client.get(path)

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert response.headers["permissions-policy"] == (
        "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    )
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "strict-transport-security" not in response.headers

    if path == "/missing":
        assert "content-security-policy" not in response.headers
    else:
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert "'unsafe-inline'" not in response.headers["content-security-policy"]
        assert "'unsafe-eval'" not in response.headers["content-security-policy"]


def test_untrusted_host_is_rejected_and_still_hardened(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = client.get("/api/v1/health", headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert response.text == "Invalid host header"
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


def test_explicit_host_allows_ports_and_production_enables_hsts(tmp_path: Path) -> None:
    client = TestClient(
        build_app(
            tmp_path,
            environment="production",
            trusted_hosts=("control.example.com",),
        ),
        base_url="https://control.example.com:8443",
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000"


@pytest.mark.parametrize(
    "trusted_hosts",
    [
        (),
        ("*",),
        ("*.example.com",),
        ("https://control.example.com",),
        ("control.example.com:443",),
        ("Control.example.com",),
        ("127.0.0.01",),
        ("control.example.com", "control.example.com"),
    ],
)
def test_config_rejects_ambiguous_trusted_hosts(
    tmp_path: Path, trusted_hosts: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError, match="trusted hosts"):
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
            trusted_hosts=trusted_hosts,
        )


def test_trusted_hosts_are_loaded_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOODOO_ROOT", str(tmp_path))
    monkeypatch.setenv("VOODOO_SESSION_SIGNING_SECRET", "s" * 64)
    monkeypatch.setenv("VOODOO_BOOTSTRAP_TOKEN", "b" * 48)
    monkeypatch.setenv(
        "VOODOO_TRUSTED_HOSTS",
        "Control.Example.com, api.example.com",
    )

    config = ProductConfig.from_env()

    assert config.trusted_hosts == ("control.example.com", "api.example.com")


def test_approval_policy_compatibility_flag_is_default_off_and_env_controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOODOO_ROOT", str(tmp_path))
    monkeypatch.setenv("VOODOO_SESSION_SIGNING_SECRET", "s" * 64)
    monkeypatch.setenv("VOODOO_BOOTSTRAP_TOKEN", "b" * 48)

    assert ProductConfig.from_env().approval_policy_compatibility_enabled is False

    monkeypatch.setenv("VOODOO_ENABLE_APPROVAL_POLICY_COMPATIBILITY", "true")
    assert ProductConfig.from_env().approval_policy_compatibility_enabled is True


def test_console_source_is_compatible_with_strict_csp() -> None:
    javascript = (ROOT / "voodoo_product" / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "voodoo_product" / "static" / "index.html").read_text(encoding="utf-8")

    assert "onclick=" not in javascript
    assert ".style." not in javascript
    assert "data-change-action" in javascript
    assert "data-decision" in javascript
    assert '<script src="/console/assets/app.js" defer></script>' in html
