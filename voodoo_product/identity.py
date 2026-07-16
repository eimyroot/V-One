from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from .config import ProductConfig
from .security import Principal, issue_token, verify_token

_CLAIM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")


class IdentityService(Protocol):
    def authenticate(self, *, username: str, password: str) -> dict[str, Any]: ...

    def get_active_user(self, user_id: str) -> dict[str, Any]: ...


class IdentityProvider(Protocol):
    name: str

    def authenticate_password(self, *, username: str, password: str) -> dict[str, Any]: ...

    def authenticate_bearer(self, token: str) -> Principal: ...

    def issue_session(self, *, user_id: str, username: str, role: str) -> str: ...


@dataclass(frozen=True, slots=True)
class OIDCProviderContract:
    issuer: str
    audience: str
    jwks_url: str
    subject_claim: str
    username_claim: str
    groups_claim: str

    def __post_init__(self) -> None:
        _validate_https_url("OIDC issuer", self.issuer)
        _validate_https_url("OIDC JWKS URL", self.jwks_url)
        if not 1 <= len(self.audience) <= 256 or any(
            character.isspace() for character in self.audience
        ):
            raise ValueError("OIDC audience is invalid")
        for label, claim in (
            ("subject", self.subject_claim),
            ("username", self.username_claim),
            ("groups", self.groups_claim),
        ):
            if not _CLAIM_NAME_PATTERN.fullmatch(claim):
                raise ValueError(f"OIDC {label} claim is invalid")
        if len({self.subject_claim, self.username_claim, self.groups_claim}) != 3:
            raise ValueError("OIDC claim names must be distinct")

    @classmethod
    def from_config(cls, config: ProductConfig) -> OIDCProviderContract:
        return cls(
            issuer=config.oidc_issuer,
            audience=config.oidc_audience,
            jwks_url=config.oidc_jwks_url,
            subject_claim=config.oidc_subject_claim,
            username_claim=config.oidc_username_claim,
            groups_claim=config.oidc_groups_claim,
        )


def _validate_https_url(label: str, value: str) -> None:
    parsed = urlsplit(value)
    if (
        not 1 <= len(value) <= 2_048
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must be an absolute HTTPS URL without credentials or fragments")


def validate_identity_provider_startup(config: ProductConfig) -> None:
    if config.identity_provider == "local":
        return
    OIDCProviderContract.from_config(config)
    raise RuntimeError("OIDC identity provider is configured but not released")


class LocalIdentityProvider:
    name = "local"

    def __init__(self, *, config: ProductConfig, service: IdentityService):
        self._config = config
        self._service = service

    def authenticate_password(self, *, username: str, password: str) -> dict[str, Any]:
        return self._service.authenticate(username=username, password=password)

    def authenticate_bearer(self, token: str) -> Principal:
        token_principal = verify_token(secret=self._config.session_signing_secret, token=token)
        active_user = self._service.get_active_user(token_principal.user_id)
        return Principal(
            user_id=str(active_user["id"]),
            username=str(active_user["username"]),
            role=str(active_user["role"]),
        )

    def issue_session(self, *, user_id: str, username: str, role: str) -> str:
        return issue_token(
            secret=self._config.session_signing_secret,
            user_id=user_id,
            username=username,
            role=role,
            ttl_seconds=self._config.token_ttl_seconds,
        )


def create_identity_provider(
    *, config: ProductConfig, service: IdentityService
) -> IdentityProvider:
    validate_identity_provider_startup(config)
    return LocalIdentityProvider(config=config, service=service)
