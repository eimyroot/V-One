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
        self.sessions: set[str] = set()

    def authenticate(self, *, username: str, password: str) -> dict[str, object]:
        if (username, password) != ("operator", "correct-password"):
            raise PermissionError("invalid credentials")
        return {"id": "usr_operator", "username": username, "role": self.role}

    def get_active_user(self, user_id: str) -> dict[str, object]:
        if user_id != "usr_operator":
            raise PermissionError("account is inactive")
        return {"id": user_id, "username": "operator", "role": self.role}

    def register_session(
        self,
        *,
        session_id: str,
        user_id: str,
        issued_at: int,
        expires_at: int,
    ) -> None:
        del user_id, issued_at, expires_at
        self.sessions.add(session_id)

    def require_active_session(
        self,
        *,
        session_id: str,
        user_id: str,
        issued_at: int,
        expires_at: int,
    ) -> None:
        del user_id, issued_at, expires_at
        if session_id not in self.sessions:
            raise PermissionError("authentication session is inactive")

    def revoke_session(
        self,
        *,
        session_id: str,
        user_id: str,
        actor_id: str,
        reason: str,
    ) -> None:
        del reason
        if actor_id != user_id or session_id not in self.sessions:
            raise PermissionError("authentication session is inactive")
        self.sessions.remove(session_id)


class FakeCredentialAuthenticator:
    def authenticate(self, *, username: str, password: str) -> dict[str, object]:
        if (username, password) != ("operator", "correct-password"):
            raise PermissionError("invalid credentials")
        return {"id": "usr_operator", "username": username, "role": "operator"}


class FakeActiveUserLookup:
    def __init__(self) -> None:
        self.role = "operator"

    def get_active_user(self, user_id: str) -> dict[str, object]:
        if user_id != "usr_operator":
            raise PermissionError("account is inactive")
        return {"id": user_id, "username": "operator", "role": self.role}


class FakeSessionLifecycle(FakeIdentityService):
    pass


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


def test_local_provider_accepts_separate_least_privilege_identity_ports(
    tmp_path: Path,
) -> None:
    active_users = FakeActiveUserLookup()
    sessions = FakeSessionLifecycle()
    provider = LocalIdentityProvider(
        config=build_config(tmp_path),
        credential_authenticator=FakeCredentialAuthenticator(),
        active_user_lookup=active_users,
        session_lifecycle=sessions,
    )
    user = provider.authenticate_password(
        username="operator",
        password="correct-password",
    )
    token = provider.issue_session(
        user_id=str(user["id"]),
        username=str(user["username"]),
        role=str(user["role"]),
    )

    active_users.role = "auditor"

    assert provider.authenticate_bearer(token).role == "auditor"


def test_identity_dependency_configuration_fails_closed(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    combined = FakeIdentityService()
    credentials = FakeCredentialAuthenticator()
    active_users = FakeActiveUserLookup()
    sessions = FakeSessionLifecycle()

    with pytest.raises(ValueError, match="cannot be mixed"):
        LocalIdentityProvider(
            config=config,
            service=combined,
            credential_authenticator=credentials,
            active_user_lookup=active_users,
        )
    with pytest.raises(ValueError, match="must all be configured"):
        LocalIdentityProvider(
            config=config,
            credential_authenticator=credentials,
        )
    with pytest.raises(ValueError, match="must all be configured"):
        LocalIdentityProvider(
            config=config,
            active_user_lookup=active_users,
        )
    LocalIdentityProvider(
        config=config,
        credential_authenticator=credentials,
        active_user_lookup=active_users,
        session_lifecycle=sessions,
    )


def test_runtime_installers_use_canonical_narrow_identity_dependencies() -> None:
    composition_source = (
        Path(__file__).resolve().parents[2] / "voodoo_product" / "composition.py"
    ).read_text(encoding="utf-8")
    compatibility_source = (
        Path(__file__).resolve().parents[2] / "voodoo_product" / "api.py"
    ).read_text(encoding="utf-8")

    assert "credential_authenticator=credential_authentication_service" in composition_source
    assert "active_user_lookup=user_account_service" in composition_source
    assert "session_lifecycle=session_lifecycle_service" in composition_source
    assert (
        "credential_authenticator=service.credential_authentication_service"
        in compatibility_source
    )
    assert "active_user_lookup=service.user_account_service" in compatibility_source
    assert "session_lifecycle=service.session_lifecycle_service" in compatibility_source
    assert "create_identity_provider(\n        config=resolved_config,\n        service=service" not in (
        composition_source + compatibility_source
    )


def test_local_mode_rejects_stray_oidc_settings(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="OIDC settings require"):
        build_config(tmp_path, oidc_issuer="https://id.example.com")
    with pytest.raises(ValueError, match="OIDC settings require"):
        build_config(tmp_path, oidc_username_claim="email")


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
