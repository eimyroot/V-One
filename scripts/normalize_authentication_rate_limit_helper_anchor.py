from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "voodoo_product" / "service.py"
text = TARGET.read_text(encoding="utf-8")
start_marker = "    def _login_rate_limit_keys(\n"
end_marker = "    def get_active_user("
start = text.find(start_marker)
end = text.find(end_marker, start + 1)
if start < 0 or end < 0:
    raise SystemExit("authentication rate-limit helper anchor not found")
expected = '''    def _login_rate_limit_keys(
        self, username: str, source: str
    ) -> tuple[tuple[str, str, int], ...]:
        return (
            ("login.account", username, self.config.auth_max_failures),
            ("login.source", source, self.config.auth_source_max_failures),
        )

    def _bootstrap_rate_limit_keys(self, source: str) -> tuple[tuple[str, str, int], ...]:
        return (("bootstrap.source", source, self.config.auth_max_failures),)

    def _auth_rate_limit_key(self, *, scope: str, value: str) -> str:
        normalized = value.strip().casefold()
        return hmac.new(
            self.config.session_signing_secret.encode("utf-8"),
            f"{scope}\0{normalized}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def _enforce_auth_rate_limits(self, entries: tuple[tuple[str, str, int], ...]) -> None:
        now = int(time.time())
        retry_after = 0
        with self.db.transaction() as connection:
            for scope, value, _ in entries:
                key_hash = self._auth_rate_limit_key(scope=scope, value=value)
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

    def _record_auth_failure(self, entries: tuple[tuple[str, str, int], ...]) -> None:
        now = int(time.time())
        retry_after = 0
        retention = max(self.config.auth_window_seconds, self.config.auth_lockout_seconds) * 2
        with self.db.transaction() as connection:
            connection.execute(
                sql.DELETE_EXPIRED_AUTH_RATE_LIMITS,
                (now - retention,),
            )
            for scope, value, maximum in entries:
                key_hash = self._auth_rate_limit_key(scope=scope, value=value)
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

    def _clear_auth_rate_limits(self, entries: tuple[tuple[str, str, int], ...]) -> None:
        with self.db.transaction() as connection:
            for scope, value, _ in entries:
                connection.execute(
                    sql.DELETE_AUTH_RATE_LIMIT,
                    (scope, self._auth_rate_limit_key(scope=scope, value=value)),
                )

'''
TARGET.write_text(text[:start] + expected + text[end:], encoding="utf-8")
