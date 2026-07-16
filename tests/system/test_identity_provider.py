from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.api as api_module
from voodoo_product.config import ProductConfig
from voodoo_product.identity import (
    LocalIdentityProvider,
    OIDCProviderContract,
    create_identity_provider,
    validate_identity_provider_startup,
)


def build_config(tmp_path: Path, **overrides: object) -> ProductConfig:
    values = {
        "environment": "test",
        "database_path": tmp_path / "product.sqlite3",
        "sandbox_root": tmp_path / "sandboxes",
        "session_signing_secret": "s" * 64,
        "bootstrap_token": "b" * 48,
    }
    values.update(overrides)
    return ProductConfig(**values)


def test_identity_fields_preserve_existing_positional_config_contract(tmp_path: Path) -> None:
    config = ProductConfig(
        "test",
        tmp_path / "product.sqlite3",
        tmp_path / "sandboxes",
        "s" * 64,
        "b" * 48,
        "sqlite",
        900,
    )

    assert config.token_ttl_seconds == 900
    assert config.identity_provider == "local"


class FakeIdentityService:
    def __init__(self) -> None:
        self.role = "operator"

    def authenticate(self, *, username: str, password: str) -> dict[str, object]:
        if (username, password) != ("operator", "correct-password"):
            raise PermissionError("invalid credentials")
        return {"id": "usr_operator", "username": username, "role": self.role}

    def get_active_user(self, user_id: str) -> dict[str, object]:
        if user_id != "usr_operator":
            raise PermissionError("account is inactive")
        return {"id": user_id, "username": "operator", "role": self.role}


def test_local_provider_owns_password_session_and_live_role_revalidation(
    tmp_path: Path,
) -> None:
    service = FakeIdentityService()
    provider = LocalIdentityProvider(config=build_config(tmp_path), service=service)
    user = provider.authenticate_password(username="operator", password="correct-password")
    token = provider.issue_session(
        user_id=str(user["id"]),
        username=str(user["username"]),
        role=str(user["role"]),
    )

    service.role = "auditor"
    principal = provider.authenticate_bearer(token)

    assert principal.user_id == "usr_operator"
    assert principal.role == "auditor"


def test_factory_returns_only_configured_local_provider(tmp_path: Path) -> None:
    provider = create_identity_provider(
        config=build_config(tmp_path), service=FakeIdentityService()
    )

    assert provider.name == "local"


def test_local_mode_rejects_stray_oidc_endpoints(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="OIDC settings require"):
        build_config(tmp_path, oidc_issuer="https://id.example.com")


def test_oidc_contract_is_strict_but_provider_remains_unreleased(tmp_path: Path) -> None:
    oidc = build_config(
        tmp_path,
        identity_provider="oidc",
        oidc_issuer="https://id.example.com/tenant",
        oidc_audience="voodoo-one",
        oidc_jwks_url="https://id.example.com/.well-known/jwks.json",
    )

    contract = OIDCProviderContract.from_config(oidc)

    assert contract.groups_claim == "groups"
    with pytest.raises(RuntimeError, match="configured but not released"):
        validate_identity_provider_startup(oidc)


def test_oidc_contract_rejects_insecure_or_ambiguous_mapping(tmp_path: Path) -> None:
    insecure = build_config(
        tmp_path,
        identity_provider="oidc",
        oidc_issuer="http://id.example.com",
        oidc_audience="voodoo-one",
        oidc_jwks_url="https://id.example.com/jwks",
    )
    with pytest.raises(ValueError, match="absolute HTTPS URL"):
        validate_identity_provider_startup(insecure)

    duplicate_claims = build_config(
        tmp_path,
        identity_provider="oidc",
        oidc_issuer="https://id.example.com",
        oidc_audience="voodoo-one",
        oidc_jwks_url="https://id.example.com/jwks",
        oidc_subject_claim="sub",
        oidc_username_claim="sub",
    )
    with pytest.raises(ValueError, match="must be distinct"):
        validate_identity_provider_startup(duplicate_claims)


def test_unreleased_oidc_fails_before_service_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    oidc = build_config(
        tmp_path,
        identity_provider="oidc",
        oidc_issuer="https://id.example.com",
        oidc_audience="voodoo-one",
        oidc_jwks_url="https://id.example.com/jwks",
    )

    class UnexpectedService:
        def __init__(self, _config: ProductConfig) -> None:
            raise AssertionError("database/service initialization must not run")

    monkeypatch.setattr(api_module, "ProductService", UnexpectedService)
    with pytest.raises(RuntimeError, match="configured but not released"):
        api_module.install_product_platform(FastAPI(), config=oidc, repository_root=tmp_path)


def test_injected_provider_must_match_config_before_service_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MismatchedProvider:
        name = "oidc"

    class UnexpectedService:
        def __init__(self, _config: ProductConfig) -> None:
            raise AssertionError("database/service initialization must not run")

    monkeypatch.setattr(api_module, "ProductService", UnexpectedService)
    with pytest.raises(RuntimeError, match="does not match configured provider"):
        api_module.install_product_platform(
            FastAPI(),
            config=build_config(tmp_path),
            repository_root=tmp_path,
            identity_provider=MismatchedProvider(),
        )
