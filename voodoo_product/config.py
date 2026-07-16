from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_TRUE_VALUES = {"1", "true", "yes", "on"}
_DEFAULT_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "testserver")
_DEFAULT_OIDC_SUBJECT_CLAIM = "sub"
_DEFAULT_OIDC_USERNAME_CLAIM = "preferred_username"
_DEFAULT_OIDC_GROUPS_CLAIM = "groups"
_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _valid_trusted_host(host: str) -> bool:
    if (
        not host
        or host == "*"
        or host != host.strip().lower()
        or len(host) > 253
        or any(character in host for character in ("*", ":", "/", " "))
    ):
        return False
    if host.replace(".", "").isdigit():
        octets = host.split(".")
        return len(octets) == 4 and all(
            octet.isdigit() and str(int(octet)) == octet and 0 <= int(octet) <= 255
            for octet in octets
        )
    return all(_HOST_LABEL_PATTERN.fullmatch(label) for label in host.split("."))


@dataclass(frozen=True, slots=True)
class ProductConfig:
    environment: str
    database_path: Path
    sandbox_root: Path
    session_signing_secret: str
    bootstrap_token: str
    database_backend: str = "sqlite"
    token_ttl_seconds: int = 3_600
    auth_max_failures: int = 5
    auth_source_max_failures: int = 20
    auth_window_seconds: int = 300
    auth_lockout_seconds: int = 900
    execution_timeout_seconds: int = 120
    execution_lease_seconds: int = 180
    log_level: str = "INFO"
    production_effects_enabled: bool = False
    cors_origins: tuple[str, ...] = ()
    trusted_hosts: tuple[str, ...] = _DEFAULT_TRUSTED_HOSTS
    identity_provider: str = "local"
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_subject_claim: str = _DEFAULT_OIDC_SUBJECT_CLAIM
    oidc_username_claim: str = _DEFAULT_OIDC_USERNAME_CLAIM
    oidc_groups_claim: str = _DEFAULT_OIDC_GROUPS_CLAIM

    def __post_init__(self) -> None:
        if self.environment not in {"local", "development", "staging", "test", "production"}:
            raise ValueError("VOODOO_ENV is invalid")
        if self.database_backend not in {"sqlite", "postgresql"}:
            raise ValueError("VOODOO_DATABASE_BACKEND is invalid")
        if self.identity_provider not in {"local", "oidc"}:
            raise ValueError("VOODOO_IDENTITY_PROVIDER is invalid")
        oidc_endpoint_values = (self.oidc_issuer, self.oidc_audience, self.oidc_jwks_url)
        oidc_claim_values = (
            self.oidc_subject_claim,
            self.oidc_username_claim,
            self.oidc_groups_claim,
        )
        oidc_default_claims = (
            _DEFAULT_OIDC_SUBJECT_CLAIM,
            _DEFAULT_OIDC_USERNAME_CLAIM,
            _DEFAULT_OIDC_GROUPS_CLAIM,
        )
        if self.identity_provider == "local" and (
            any(oidc_endpoint_values) or oidc_claim_values != oidc_default_claims
        ):
            raise ValueError("OIDC settings require VOODOO_IDENTITY_PROVIDER=oidc")
        if self.identity_provider == "oidc" and not all(oidc_endpoint_values):
            raise ValueError("OIDC provider requires issuer, audience and JWKS URL")
        if len(self.session_signing_secret.encode("utf-8")) < 32:
            raise ValueError("session signing secret must contain at least 32 bytes")
        if len(self.bootstrap_token.encode("utf-8")) < 24:
            raise ValueError("bootstrap token must contain at least 24 bytes")
        if not 300 <= self.token_ttl_seconds <= 86_400:
            raise ValueError("token TTL must be between 300 and 86400 seconds")
        if not 2 <= self.auth_max_failures <= 20:
            raise ValueError("auth max failures must be between 2 and 20")
        if not self.auth_max_failures <= self.auth_source_max_failures <= 200:
            raise ValueError("auth source max failures must be between account limit and 200")
        if not 10 <= self.auth_window_seconds <= 3_600:
            raise ValueError("auth window must be between 10 and 3600 seconds")
        if not 10 <= self.auth_lockout_seconds <= 86_400:
            raise ValueError("auth lockout must be between 10 and 86400 seconds")
        if not 10 <= self.execution_timeout_seconds <= 3_600:
            raise ValueError("execution timeout must be between 10 and 3600 seconds")
        if not (
            self.execution_timeout_seconds + 30
            <= self.execution_lease_seconds
            <= self.execution_timeout_seconds + 3_600
        ):
            raise ValueError("execution lease must exceed timeout by 30 to 3600 seconds")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log level is invalid")
        if self.production_effects_enabled and self.environment != "production":
            raise ValueError("production effects require VOODOO_ENV=production")
        for origin in self.cors_origins:
            if origin == "*" or not origin.startswith(
                ("https://", "http://127.0.0.1", "http://localhost")
            ):
                raise ValueError("CORS origins must be explicit HTTPS or loopback URLs")
        if not self.trusted_hosts or any(
            not _valid_trusted_host(host) for host in self.trusted_hosts
        ):
            raise ValueError("trusted hosts must be explicit lowercase hostnames or IPv4 addresses")
        if len(set(self.trusted_hosts)) != len(self.trusted_hosts):
            raise ValueError("trusted hosts must be unique")

    @classmethod
    def from_env(cls) -> ProductConfig:
        root = Path(os.getenv("VOODOO_ROOT", Path.cwd())).resolve()
        database_path = (
            Path(
                os.getenv(
                    "VOODOO_PRODUCT_DB",
                    root / "storage" / "product" / "voodoo_one.sqlite3",
                )
            )
            .expanduser()
            .resolve()
        )
        sandbox_root = (
            Path(
                os.getenv(
                    "VOODOO_PRODUCT_SANDBOX_ROOT",
                    root / "storage" / "product" / "sandboxes",
                )
            )
            .expanduser()
            .resolve()
        )

        signing_secret = os.getenv("VOODOO_SESSION_SIGNING_SECRET", "")
        bootstrap_token = os.getenv("VOODOO_BOOTSTRAP_TOKEN", "")

        if len(signing_secret.encode("utf-8")) < 32:
            raise RuntimeError("VOODOO_SESSION_SIGNING_SECRET must contain at least 32 bytes")
        if len(bootstrap_token.encode("utf-8")) < 24:
            raise RuntimeError("VOODOO_BOOTSTRAP_TOKEN must contain at least 24 bytes")

        origins = tuple(
            item.strip() for item in os.getenv("VOODOO_CORS_ORIGINS", "").split(",") if item.strip()
        )
        trusted_hosts = tuple(
            item.strip().lower()
            for item in os.getenv("VOODOO_TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")
            if item.strip()
        )

        return cls(
            environment=os.getenv("VOODOO_ENV", "local").strip().lower(),
            database_path=database_path,
            sandbox_root=sandbox_root,
            session_signing_secret=signing_secret,
            bootstrap_token=bootstrap_token,
            database_backend=os.getenv("VOODOO_DATABASE_BACKEND", "sqlite").strip().lower(),
            token_ttl_seconds=int(os.getenv("VOODOO_TOKEN_TTL_SECONDS", "3600")),
            auth_max_failures=int(os.getenv("VOODOO_AUTH_MAX_FAILURES", "5")),
            auth_source_max_failures=int(os.getenv("VOODOO_AUTH_SOURCE_MAX_FAILURES", "20")),
            auth_window_seconds=int(os.getenv("VOODOO_AUTH_WINDOW_SECONDS", "300")),
            auth_lockout_seconds=int(os.getenv("VOODOO_AUTH_LOCKOUT_SECONDS", "900")),
            execution_timeout_seconds=int(os.getenv("VOODOO_EXECUTION_TIMEOUT_SECONDS", "120")),
            execution_lease_seconds=int(os.getenv("VOODOO_EXECUTION_LEASE_SECONDS", "180")),
            log_level=os.getenv("VOODOO_LOG_LEVEL", "INFO").strip().upper(),
            production_effects_enabled=_bool_env("VOODOO_ALLOW_PRODUCTION_EFFECTS", False),
            cors_origins=origins,
            trusted_hosts=trusted_hosts,
            identity_provider=os.getenv("VOODOO_IDENTITY_PROVIDER", "local").strip().lower(),
            oidc_issuer=os.getenv("VOODOO_OIDC_ISSUER", "").strip(),
            oidc_audience=os.getenv("VOODOO_OIDC_AUDIENCE", "").strip(),
            oidc_jwks_url=os.getenv("VOODOO_OIDC_JWKS_URL", "").strip(),
            oidc_subject_claim=os.getenv(
                "VOODOO_OIDC_SUBJECT_CLAIM", _DEFAULT_OIDC_SUBJECT_CLAIM
            ).strip(),
            oidc_username_claim=os.getenv(
                "VOODOO_OIDC_USERNAME_CLAIM", _DEFAULT_OIDC_USERNAME_CLAIM
            ).strip(),
            oidc_groups_claim=os.getenv(
                "VOODOO_OIDC_GROUPS_CLAIM", _DEFAULT_OIDC_GROUPS_CLAIM
            ).strip(),
        )
