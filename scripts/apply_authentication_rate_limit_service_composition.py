from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def create_once(path: str, content: str) -> None:
    target = ROOT / path
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing file: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


create_once(
    "voodoo_product/auth_rate_limit.py",
    '''from __future__ import annotations

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
''',
)

replace_once(
    "voodoo_product/service.py",
    '''import hashlib
import hmac
import secrets
import time
''',
    '''import secrets
import time
''',
)
replace_once(
    "voodoo_product/service.py",
    '''from .adapters import execute_adapter
from .audit import AuditLedger
''',
    '''from .adapters import execute_adapter
from .audit import AuditLedger
from .auth_rate_limit import AuthRateLimitExceeded, AuthenticationRateLimitService
''',
)
replace_once(
    "voodoo_product/service.py",
    '''    "ProductService",
    "canonical_json",
''',
    '''    "AuthRateLimitExceeded",
    "ProductService",
    "canonical_json",
''',
)
replace_once(
    "voodoo_product/service.py",
    '''

class AuthRateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__("authentication temporarily rate limited")





''',
    '''

''',
)
replace_once(
    "voodoo_product/service.py",
    '''        database: ProductDatabaseAdapter | None = None,
        audit_ledger: AuditLedger | None = None,
''',
    '''        database: ProductDatabaseAdapter | None = None,
        authentication_rate_limit_service: AuthenticationRateLimitService | None = None,
        audit_ledger: AuditLedger | None = None,
''',
)
replace_once(
    "voodoo_product/service.py",
    '''        self.db.initialize()
        resolved_audit_ledger = audit_ledger or AuditLedger(self.db)
''',
    '''        self.db.initialize()
        resolved_authentication_rate_limit_service = (
            authentication_rate_limit_service
            or AuthenticationRateLimitService(
                database=self.db,
                config=self.config,
                clock=lambda: time.time(),
            )
        )
        if resolved_authentication_rate_limit_service.db is not self.db:
            raise ValueError(
                "authentication rate-limit service must use the product service database"
            )
        if resolved_authentication_rate_limit_service.config is not self.config:
            raise ValueError(
                "authentication rate-limit service must use the product service configuration"
            )
        self.authentication_rate_limit_service = resolved_authentication_rate_limit_service
        resolved_audit_ledger = audit_ledger or AuditLedger(self.db)
''',
)
replace_once(
    "voodoo_product/service.py",
    '''    def enforce_login_rate_limit(self, *, username: str, source: str) -> None:
        self._enforce_auth_rate_limits(self._login_rate_limit_keys(username, source))

    def record_login_failure(self, *, username: str, source: str) -> None:
        self._record_auth_failure(self._login_rate_limit_keys(username, source))

    def clear_login_rate_limit(self, *, username: str, source: str) -> None:
        self._clear_auth_rate_limits(self._login_rate_limit_keys(username, source))

    def enforce_bootstrap_rate_limit(self, *, source: str) -> None:
        self._enforce_auth_rate_limits(self._bootstrap_rate_limit_keys(source))

    def record_bootstrap_failure(self, *, source: str) -> None:
        self._record_auth_failure(self._bootstrap_rate_limit_keys(source))

    def clear_bootstrap_rate_limit(self, *, source: str) -> None:
        self._clear_auth_rate_limits(self._bootstrap_rate_limit_keys(source))
''',
    '''    def enforce_login_rate_limit(self, *, username: str, source: str) -> None:
        self.authentication_rate_limit_service.enforce_login_rate_limit(
            username=username,
            source=source,
        )

    def record_login_failure(self, *, username: str, source: str) -> None:
        self.authentication_rate_limit_service.record_login_failure(
            username=username,
            source=source,
        )

    def clear_login_rate_limit(self, *, username: str, source: str) -> None:
        self.authentication_rate_limit_service.clear_login_rate_limit(
            username=username,
            source=source,
        )

    def enforce_bootstrap_rate_limit(self, *, source: str) -> None:
        self.authentication_rate_limit_service.enforce_bootstrap_rate_limit(source=source)

    def record_bootstrap_failure(self, *, source: str) -> None:
        self.authentication_rate_limit_service.record_bootstrap_failure(source=source)

    def clear_bootstrap_rate_limit(self, *, source: str) -> None:
        self.authentication_rate_limit_service.clear_bootstrap_rate_limit(source=source)
''',
)
replace_once(
    "voodoo_product/service.py",
    '''    def _login_rate_limit_keys(
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

''',
    '''''',
)

replace_once(
    "voodoo_product/composition.py",
    '''from .audit import AuditLedger
from .change_request import ChangeRequestService
''',
    '''from .audit import AuditLedger
from .auth_rate_limit import AuthenticationRateLimitService
from .change_request import ChangeRequestService
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''    service: ProductService
    audit_ledger: AuditLedger
''',
    '''    service: ProductService
    authentication_rate_limit_service: AuthenticationRateLimitService
    audit_ledger: AuditLedger
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''    service = ProductService(resolved_config)
    audit_ledger = service.audit_ledger
''',
    '''    service = ProductService(resolved_config)
    authentication_rate_limit_service = service.authentication_rate_limit_service
    audit_ledger = service.audit_ledger
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''        service=service,
        audit_ledger=audit_ledger,
''',
    '''        service=service,
        authentication_rate_limit_service=authentication_rate_limit_service,
        audit_ledger=audit_ledger,
''',
)
replace_once(
    "voodoo_product/composition.py",
    '''    app.state.voodoo_product_service = service
    app.state.voodoo_identity_provider = resolved_identity_provider
''',
    '''    app.state.voodoo_product_service = service
    app.state.voodoo_authentication_rate_limit_service = authentication_rate_limit_service
    app.state.voodoo_identity_provider = resolved_identity_provider
''',
)

replace_once(
    "tests/system/test_statement_catalog.py",
    "    assert len(execute_calls) == 11\n",
    "    assert len(execute_calls) == 5\n",
)

replace_once(
    "scripts/product_readiness_gate.py",
    '''    "voodoo_product/audit.py",
    "voodoo_product/change_request.py",
''',
    '''    "voodoo_product/audit.py",
    "voodoo_product/auth_rate_limit.py",
    "voodoo_product/change_request.py",
''',
)
replace_once(
    "scripts/product_readiness_gate.py",
    '''    "tests/system/test_auth_rate_limiting.py",
    "tests/system/test_change_request_service.py",
''',
    '''    "tests/system/test_auth_rate_limiting.py",
    "tests/system/test_authentication_rate_limit_service.py",
    "tests/system/test_change_request_service.py",
''',
)
replace_once(
    "scripts/product_readiness_gate.py",
    '''    "docs/product/AUDIT_LEDGER_COMPOSITION_BOUNDARY.md",
    "docs/product/CHANGE_REQUEST_SERVICE_COMPOSITION_BOUNDARY.md",
''',
    '''    "docs/product/AUDIT_LEDGER_COMPOSITION_BOUNDARY.md",
    "docs/product/AUTHENTICATION_RATE_LIMIT_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/CHANGE_REQUEST_SERVICE_COMPOSITION_BOUNDARY.md",
''',
)

create_once(
    "tests/system/test_authentication_rate_limit_service.py",
    '''from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.auth_rate_limit import (
    AuthRateLimitExceeded,
    AuthenticationRateLimitService,
)
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import (
    AuthRateLimitExceeded as ServiceAuthRateLimitExceeded,
)
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]


def product_config(
    tmp_path: Path,
    *,
    name: str = "product",
    auth_max_failures: int = 3,
    auth_source_max_failures: int = 20,
) -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
        auth_max_failures=auth_max_failures,
        auth_source_max_failures=auth_source_max_failures,
        auth_window_seconds=300,
        auth_lockout_seconds=900,
    )


def test_authentication_rate_limit_service_uses_only_catalog_statements() -> None:
    source = ROOT / "voodoo_product" / "auth_rate_limit.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 6
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_service_delegates_authentication_rate_limit_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    names = {
        "enforce_login_rate_limit",
        "record_login_failure",
        "clear_login_rate_limit",
        "enforce_bootstrap_rate_limit",
        "record_bootstrap_failure",
        "clear_bootstrap_rate_limit",
    }
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }

    assert set(methods) == names
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.authentication_rate_limit_service.enforce_login_rate_limit" in source_text
    assert "self.authentication_rate_limit_service.record_login_failure" in source_text
    assert "self.authentication_rate_limit_service.clear_login_rate_limit" in source_text
    assert "self.authentication_rate_limit_service.enforce_bootstrap_rate_limit" in source_text
    assert "self.authentication_rate_limit_service.record_bootstrap_failure" in source_text
    assert "self.authentication_rate_limit_service.clear_bootstrap_rate_limit" in source_text
    assert "sql.SELECT_AUTH_RATE_LIMIT" not in source_text
    assert "sql.DELETE_AUTH_RATE_LIMIT" not in source_text
    assert "sql.DELETE_EXPIRED_AUTH_RATE_LIMITS" not in source_text
    assert "sql.UPSERT_AUTH_RATE_LIMIT" not in source_text


def test_service_exception_import_remains_compatible() -> None:
    assert ServiceAuthRateLimitExceeded is AuthRateLimitExceeded


def test_product_service_rejects_rate_limit_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="authentication rate-limit service must use the product service database",
    ):
        ProductService(
            first.config,
            database=first.db,
            authentication_rate_limit_service=second.authentication_rate_limit_service,
            audit_ledger=first.audit_ledger,
            user_account_service=first.user_account_service,
            workspace_service=first.workspace_service,
            change_request_service=first.change_request_service,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
            execution_service=first.execution_service,
            platform_status_service=first.platform_status_service,
        )


def test_rate_limit_service_preserves_hashing_lockout_and_expiry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ProductService(
        product_config(
            tmp_path,
            auth_max_failures=2,
            auth_source_max_failures=10,
        )
    )
    now = 1_000
    monkeypatch.setattr(service_module.time, "time", lambda: now)

    service.record_login_failure(username=" Victim ", source="SOURCE-A")
    with pytest.raises(AuthRateLimitExceeded) as recorded:
        service.record_login_failure(username="victim", source="source-b")
    assert recorded.value.retry_after == 900
    with pytest.raises(AuthRateLimitExceeded) as enforced:
        service.enforce_login_rate_limit(username="VICTIM", source="source-c")
    assert enforced.value.retry_after == 900

    with service.db.connect() as connection:
        rows = connection.execute(
            "SELECT scope, key_hash, failure_count, window_started_at, updated_at "
            "FROM auth_rate_limits ORDER BY scope, key_hash"
        ).fetchall()
    account = next(row for row in rows if row["scope"] == "login.account")
    assert account["failure_count"] == 2
    assert account["window_started_at"] == now
    assert account["updated_at"] == now
    assert len(account["key_hash"]) == 64
    assert "victim" not in account["key_hash"]

    now = 2_000
    service.enforce_login_rate_limit(username="victim", source="source-c")
    with service.db.connect() as connection:
        account_count = connection.execute(
            "SELECT COUNT(*) AS count FROM auth_rate_limits WHERE scope = 'login.account'"
        ).fetchone()
    assert account_count["count"] == 0


def test_clear_rate_limit_preserves_account_and_source_semantics(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    service.record_login_failure(username="operator", source="source-a")
    service.clear_login_rate_limit(username="operator", source="source-a")

    with service.db.connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM auth_rate_limits").fetchone()
    assert count["count"] == 0


def test_authentication_rate_limit_service_rejects_wrong_composition_identity(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    service = AuthenticationRateLimitService(
        database=first.db,
        config=second.config,
    )
    assert service.db is first.db
    assert service.config is second.config
    with pytest.raises(
        ValueError,
        match="authentication rate-limit service must use the product service configuration",
    ):
        ProductService(
            first.config,
            database=first.db,
            authentication_rate_limit_service=service,
            audit_ledger=first.audit_ledger,
            user_account_service=first.user_account_service,
            workspace_service=first.workspace_service,
            change_request_service=first.change_request_service,
            receipt_ledger=first.receipt_ledger,
            operational_safety_service=first.operational_safety_service,
            execution_service=first.execution_service,
            platform_status_service=first.platform_status_service,
        )


def test_composition_exposes_shared_authentication_rate_limit_service(
    tmp_path: Path,
) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert (
        app.state.voodoo_authentication_rate_limit_service
        is composition.authentication_rate_limit_service
    )
    assert (
        composition.service.authentication_rate_limit_service
        is composition.authentication_rate_limit_service
    )
    assert composition.authentication_rate_limit_service.db is composition.service.db
    assert composition.authentication_rate_limit_service.config is composition.service.config
''',
)

create_once(
    "docs/product/AUTHENTICATION_RATE_LIMIT_SERVICE_COMPOSITION_BOUNDARY.md",
    '''# Authentication Rate-Limit Service Composition Boundary

## Status

Implemented as the canonical database-bound authentication throttling state boundary.

## Purpose

`AuthenticationRateLimitService` owns login and bootstrap rate-limit key derivation, persistent counters, expiry cleanup, lockout calculation and clearing. `ProductService` preserves the existing public method surface while delegating all six rate-limit operations.

Password lookup, dummy-hash timing protection, password verification, bootstrap authorization and credential decisions intentionally remain in `ProductService` and the identity boundary.

## Runtime composition

`install_composed_product_platform` exposes one shared authentication rate-limit service through `ProductComposition` and `app.state.voodoo_authentication_rate_limit_service`.

The service uses the exact product database and configuration instances. Composition mismatches fail closed.

## Preserved invariants

- account and source throttles remain separate;
- bootstrap throttling remains source-bound;
- normalized identities are HMAC-SHA256 hashed before storage;
- raw usernames and client sources are not persisted in rate-limit keys;
- counters, lockouts and cleanup remain transactionally consistent;
- concurrent failures remain atomically counted;
- successful authentication clears both account and source state;
- expired windows and lockouts are removed during enforcement;
- `AuthRateLimitExceeded` identity, message and `retry_after` behavior remain compatible;
- existing routes, HTTP 429 responses and `Retry-After` headers remain unchanged;
- dynamic `time.time` monkeypatch compatibility is preserved.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not change passwords, identity-provider behavior, bootstrap authorization, permissions, routes, external sign-in, release, deployment or production effects.
''',
)
