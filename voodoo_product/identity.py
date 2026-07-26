from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from .config import ProductConfig
from .security import Principal, issue_token, verify_session_token

_CLAIM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")


class CredentialAuthenticator(Protocol):
    def authenticate(self, *, username: str, password: str) -> dict[str, Any]:
        ...


class ActiveUserLookup(Protocol):
    def get_active_user(self, user_id: str) -> dict[str, Any]:
        ...


class SessionLifecycle(Protocol):
    def register_session(
        self,
        *,
        session_id: str,
        user_id: str,
        issued_at: int,
        expires_at: int,
    ) -> None: ...

    def require_active_session(
        self,
        *,
        session_id: str,
        user_id: str,
        issued_at: int,
        expires_at: int,
    ) -> None: ...

    def revoke_session(
        self,
        *,
        session_id: str,
        user_id: str,
        actor_id: str,
        reason: str,
    ) -> None: ...


class IdentityService(CredentialAuthenticator, ActiveUserLookup, SessionLifecycle, Protocol):
    """Compatibility protocol for callers that still expose both identity ports."""


class IdentityProvider(Protocol):
    name: str

    def authenticate_password(self, *, username: str, password: str) -> dict[str, Any]:
        ...

    def authenticate_bearer(self, token: str) -> Principal:
        ...

    def issue_session(self, *, user_id: str, username: str, role: str) -> str:
        ...

    def revoke_session(self, token: str, *, actor_id: str) -> None:
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

    def __init__(
        self,
        *,
        config: ProductConfig,
        service: IdentityService | None = None,
        credential_authenticator: CredentialAuthenticator | None = None,
        active_user_lookup: ActiveUserLookup | None = None,
        session_lifecycle: SessionLifecycle | None = None,
    ) -> None:
        self._config = config
        (
            self._credential_authenticator,
            self._active_user_lookup,
            self._session_lifecycle,
        ) = (
            _resolve_identity_dependencies(
                service=service,
                credential_authenticator=credential_authenticator,
                active_user_lookup=active_user_lookup,
                session_lifecycle=session_lifecycle,
            )
        )

    def authenticate_password(self, *, username: str, password: str) -> dict[str, Any]:
        return self._credential_authenticator.authenticate(
            username=username,
            password=password,
        )

    def authenticate_bearer(self, token: str) -> Principal:
        verified = verify_session_token(
            secret=self._config.session_signing_secret,
            token=token,
        )
        self._session_lifecycle.require_active_session(
            session_id=verified.session_id,
            user_id=verified.principal.user_id,
            issued_at=verified.issued_at,
            expires_at=verified.expires_at,
        )
        active_user = self._active_user_lookup.get_active_user(verified.principal.user_id)
        return Principal(
            user_id=str(active_user["id"]),
            username=str(active_user["username"]),
            role=str(active_user["role"]),
        )

    def issue_session(self, *, user_id: str, username: str, role: str) -> str:
        token = issue_token(
            secret=self._config.session_signing_secret,
            user_id=user_id,
            username=username,
            role=role,
            ttl_seconds=self._config.token_ttl_seconds,
        )
        verified = verify_session_token(
            secret=self._config.session_signing_secret,
            token=token,
        )
        self._session_lifecycle.register_session(
            session_id=verified.session_id,
            user_id=verified.principal.user_id,
            issued_at=verified.issued_at,
            expires_at=verified.expires_at,
        )
        return token

    def revoke_session(self, token: str, *, actor_id: str) -> None:
        verified = verify_session_token(
            secret=self._config.session_signing_secret,
            token=token,
        )
        self._session_lifecycle.revoke_session(
            session_id=verified.session_id,
            user_id=verified.principal.user_id,
            actor_id=actor_id,
            reason="user logout",
        )


def _resolve_identity_dependencies(
    *,
    service: IdentityService | None,
    credential_authenticator: CredentialAuthenticator | None,
    active_user_lookup: ActiveUserLookup | None,
    session_lifecycle: SessionLifecycle | None,
) -> tuple[CredentialAuthenticator, ActiveUserLookup, SessionLifecycle]:
    if service is not None:
        if (
            credential_authenticator is not None
            or active_user_lookup is not None
            or session_lifecycle is not None
        ):
            raise ValueError(
                "identity service compatibility input cannot be mixed with explicit ports"
            )
        return service, service, service
    if (
        credential_authenticator is None
        or active_user_lookup is None
        or session_lifecycle is None
    ):
        raise ValueError(
            "credential authenticator, active-user lookup and session lifecycle "
            "must all be configured"
        )
    return credential_authenticator, active_user_lookup, session_lifecycle


def create_identity_provider(
    *,
    config: ProductConfig,
    service: IdentityService | None = None,
    credential_authenticator: CredentialAuthenticator | None = None,
    active_user_lookup: ActiveUserLookup | None = None,
    session_lifecycle: SessionLifecycle | None = None,
) -> IdentityProvider:
    validate_identity_provider_startup(config)
    return LocalIdentityProvider(
        config=config,
        service=service,
        credential_authenticator=credential_authenticator,
        active_user_lookup=active_user_lookup,
        session_lifecycle=session_lifecycle,
    )
