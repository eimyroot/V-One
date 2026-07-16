from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from .config import ProductConfig
from .security import Principal, issue_token, verify_token

OIDC_PROVIDER = "oidc"
_CLAIM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")
_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class IdentityService(Protocol):
    def authenticate(self, *, username: str, password: str) -> dict[str, Any]:
        ...

    def get_active_user(self, user_id: str) -> dict[str, Any]:
        ...


class IdentityProvider(Protocol):
    name: str

    def authenticate_password(self, *, username: str, password: str) -> dict[str, Any]:
        ...

    def authenticate_bearer(self, token: str) -> Principal:
        ...

    def issue_session(self, *, user_id: str, username: str, role: str) -> str:
        ...


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


@dataclass(frozen=True, slots=True)
class ExternalIdentityClaims:
    provider: str
    issuer: str
    subject: str
    groups: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_external_identity_reference(
            provider=self.provider,
            issuer=self.issuer,
            subject=self.subject,
        )
        if not isinstance(self.groups, tuple):
            raise ValueError("external identity groups must be an immutable tuple")
        if not 1 <= len(self.groups) <= 64:
            raise ValueError("external identity must contain between 1 and 64 groups")
        for group in self.groups:
            validate_external_group(group)
        if len(set(self.groups)) != len(self.groups):
            raise ValueError("external identity groups must be unique")


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


def _validate_exact_text(label: str, value: str, *, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or value != value.strip()
        or _CONTROL_CHARACTER_PATTERN.search(value)
    ):
        raise ValueError(f"{label} is invalid")


def validate_external_identity_reference(*, provider: str, issuer: str, subject: str) -> None:
    if provider != OIDC_PROVIDER:
        raise ValueError("external identity provider is unsupported")
    _validate_https_url("external identity issuer", issuer)
    _validate_exact_text("external identity subject", subject, maximum=512)


def validate_external_group(group: str) -> None:
    _validate_exact_text("external identity group", group, maximum=256)


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
