from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True, slots=True)
class ProductConfig:
    environment: str
    database_path: Path
    sandbox_root: Path
    session_signing_secret: str
    bootstrap_token: str
    token_ttl_seconds: int = 3_600
    production_effects_enabled: bool = False
    cors_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.environment not in {"local", "development", "staging", "test", "production"}:
            raise ValueError("VOODOO_ENV is invalid")
        if len(self.session_signing_secret.encode("utf-8")) < 32:
            raise ValueError("session signing secret must contain at least 32 bytes")
        if len(self.bootstrap_token.encode("utf-8")) < 24:
            raise ValueError("bootstrap token must contain at least 24 bytes")
        if not 300 <= self.token_ttl_seconds <= 86_400:
            raise ValueError("token TTL must be between 300 and 86400 seconds")
        if self.production_effects_enabled and self.environment != "production":
            raise ValueError("production effects require VOODOO_ENV=production")
        for origin in self.cors_origins:
            if origin == "*" or not origin.startswith(
                ("https://", "http://127.0.0.1", "http://localhost")
            ):
                raise ValueError("CORS origins must be explicit HTTPS or loopback URLs")

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

        return cls(
            environment=os.getenv("VOODOO_ENV", "local").strip().lower(),
            database_path=database_path,
            sandbox_root=sandbox_root,
            session_signing_secret=signing_secret,
            bootstrap_token=bootstrap_token,
            token_ttl_seconds=int(os.getenv("VOODOO_TOKEN_TTL_SECONDS", "3600")),
            production_effects_enabled=_bool_env("VOODOO_ALLOW_PRODUCTION_EFFECTS", False),
            cors_origins=origins,
        )
