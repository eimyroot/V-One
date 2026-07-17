from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable

from . import statements as sql
from .config import ProductConfig
from .persistence import ProductDatabaseAdapter

Clock = Callable[[], float]
RateLimitEntries = tuple[tuple[str, str, int], ...]


class AuthRateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__("authentication temporarily rate limited")


class AuthenticationRateLimitService:
    """Database-bound authentication rate-limit state boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        config: ProductConfig,
        clock: Clock = time.time,
    ) -> None:
        self.db = database
        self.config = config
        self._clock = clock

    def enforce_login_rate_limit(self, *, username: str, source: str) -> None:
        self._enforce(self._login_keys(username, source))

    def record_login_failure(self, *, username: str, source: str) -> None:
        self._record_failure(self._login_keys(username, source))

    def clear_login_rate_limit(self, *, username: str, source: str) -> None:
        self._clear(self._login_keys(username, source))

    def enforce_bootstrap_rate_limit(self, *, source: str) -> None:
        self._enforce(self._bootstrap_keys(source))

    def record_bootstrap_failure(self, *, source: str) -> None:
        self._record_failure(self._bootstrap_keys(source))

    def clear_bootstrap_rate_limit(self, *, source: str) -> None:
        self._clear(self._bootstrap_keys(source))

    def _login_keys(self, username: str, source: str) -> RateLimitEntries:
        return (
            ("login.account", username, self.config.auth_max_failures),
            ("login.source", source, self.config.auth_source_max_failures),
        )

    def _bootstrap_keys(self, source: str) -> RateLimitEntries:
        return (("bootstrap.source", source, self.config.auth_max_failures),)

    def _key_hash(self, *, scope: str, value: str) -> str:
        normalized = value.strip().casefold()
        return hmac.new(
            self.config.session_signing_secret.encode("utf-8"),
            f"{scope}\0{normalized}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def _enforce(self, entries: RateLimitEntries) -> None:
        now = int(self._clock())
        retry_after = 0
        with self.db.transaction() as connection:
            for scope, value, _ in entries:
                key_hash = self._key_hash(scope=scope, value=value)
                row = connection.execute(
                    sql.SELECT_AUTH_RATE_LIMIT,
                    (scope, key_hash),
                ).fetchone()
                if row is None:
                    continue
                blocked_until = int(row["blocked_until"])
                if blocked_until > now:
                    retry_after = max(retry_after, blocked_until - now)
                    continue
                window_expired = now - int(row["window_started_at"]) >= (
                    self.config.auth_window_seconds
                )
                if blocked_until > 0 or window_expired:
                    connection.execute(
                        sql.DELETE_AUTH_RATE_LIMIT,
                        (scope, key_hash),
                    )
        if retry_after:
            raise AuthRateLimitExceeded(retry_after)

    def _record_failure(self, entries: RateLimitEntries) -> None:
        now = int(self._clock())
        retry_after = 0
        retention = max(self.config.auth_window_seconds, self.config.auth_lockout_seconds) * 2
        with self.db.transaction() as connection:
            connection.execute(
                sql.DELETE_EXPIRED_AUTH_RATE_LIMITS,
                (now - retention,),
            )
            for scope, value, maximum in entries:
                key_hash = self._key_hash(scope=scope, value=value)
                row = connection.execute(
                    sql.SELECT_AUTH_RATE_LIMIT,
                    (scope, key_hash),
                ).fetchone()
                if row is not None and int(row["blocked_until"]) > now:
                    retry_after = max(retry_after, int(row["blocked_until"]) - now)
                    continue
                if (
                    row is None
                    or int(row["blocked_until"]) > 0
                    or now - int(row["window_started_at"]) >= self.config.auth_window_seconds
                ):
                    failure_count = 1
                    window_started_at = now
                else:
                    failure_count = int(row["failure_count"]) + 1
                    window_started_at = int(row["window_started_at"])
                blocked_until = (
                    now + self.config.auth_lockout_seconds if failure_count >= maximum else 0
                )
                connection.execute(
                    sql.UPSERT_AUTH_RATE_LIMIT,
                    (scope, key_hash, failure_count, window_started_at, blocked_until, now),
                )
                if blocked_until > now:
                    retry_after = max(retry_after, blocked_until - now)
        if retry_after:
            raise AuthRateLimitExceeded(retry_after)

    def _clear(self, entries: RateLimitEntries) -> None:
        with self.db.transaction() as connection:
            for scope, value, _ in entries:
                connection.execute(
                    sql.DELETE_AUTH_RATE_LIMIT,
                    (scope, self._key_hash(scope=scope, value=value)),
                )
