from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path.relative_to(ROOT)} expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def write(path: Path, content: str) -> None:
    if not content.endswith("\n"):
        content += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


service = ROOT / "voodoo_product" / "service.py"
replace_once(
    service,
    """from .persistence import (
    DatabaseConnection,
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseRow,
    ProductDatabaseAdapter,
)
from .security import hash_password, verify_password

VALID_ROLES = {
""",
    """from .persistence import (
    DatabaseConnection,
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseRow,
    ProductDatabaseAdapter,
)
from .receipt import ReceiptLedger
from .security import hash_password, verify_password

__all__ = [
    "ProductService",
    "canonical_json",
    "chained_hash",
    "new_id",
    "utc_now",
]

VALID_ROLES = {
""",
)
replace_once(
    service,
    """class ProductService:
    def __init__(
        self,
        config: ProductConfig,
        *,
        database: ProductDatabaseAdapter | None = None,
        audit_ledger: AuditLedger | None = None,
    ) -> None:
        self.config = config
        self.db = (
            database
            if database is not None
            else create_product_database(
                backend=self.config.database_backend,
                path=self.config.database_path,
            )
        )
        self.db.initialize()
        resolved_audit_ledger = audit_ledger or AuditLedger(self.db)
        if resolved_audit_ledger.db is not self.db:
            raise ValueError("audit ledger must use the product service database")
        self.audit_ledger = resolved_audit_ledger
        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)
""",
    """class ProductService:
    def __init__(
        self,
        config: ProductConfig,
        *,
        database: ProductDatabaseAdapter | None = None,
        audit_ledger: AuditLedger | None = None,
        receipt_ledger: ReceiptLedger | None = None,
    ) -> None:
        self.config = config
        self.db = (
            database
            if database is not None
            else create_product_database(
                backend=self.config.database_backend,
                path=self.config.database_path,
            )
        )
        self.db.initialize()
        resolved_audit_ledger = audit_ledger or AuditLedger(self.db)
        if resolved_audit_ledger.db is not self.db:
            raise ValueError("audit ledger must use the product service database")
        self.audit_ledger = resolved_audit_ledger
        resolved_receipt_ledger = receipt_ledger or ReceiptLedger(self.db)
        if resolved_receipt_ledger.db is not self.db:
            raise ValueError("receipt ledger must use the product service database")
        self.receipt_ledger = resolved_receipt_ledger
        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)
""",
)
replace_once(
    service,
    """    def list_receipts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_RECEIPTS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode_receipt(dict(row)) for row in rows]

    def verify_receipt_chain(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_RECEIPTS_FOR_VERIFICATION).fetchall()
        previous_hash = "GENESIS"
        for expected_sequence, row in enumerate(rows, start=1):
            payload = json.loads(row["payload_json"])
            expected = chained_hash(previous_hash, payload)
            if (
                int(row["sequence"]) != expected_sequence
                or row["previous_hash"] != previous_hash
                or row["receipt_hash"] != expected
            ):
                return {
                    "valid": False,
                    "count": len(rows),
                    "broken_at": expected_sequence,
                    "sequence": row["sequence"],
                    "receipt_id": row["id"],
                }
            previous_hash = row["receipt_hash"]
        return {"valid": True, "count": len(rows), "head": previous_hash}
""",
    """    def list_receipts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.receipt_ledger.list_receipts(limit=limit)

    def verify_receipt_chain(self) -> dict[str, Any]:
        return self.receipt_ledger.verify()
""",
)
replace_once(
    service,
    """    def _append_receipt(
        self,
        connection: DatabaseConnection,
        *,
        execution_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last = connection.execute(sql.SELECT_RECEIPT_HEAD).fetchone()
        previous_hash = str(last["receipt_hash"]) if last else "GENESIS"
        receipt_hash = chained_hash(previous_hash, payload)
        receipt = {
            "id": new_id("rcpt"),
            "execution_id": execution_id,
            "payload": payload,
            "previous_hash": previous_hash,
            "receipt_hash": receipt_hash,
            "created_at": utc_now(),
        }
        connection.execute(
            sql.INSERT_RECEIPT,
            (
                receipt["id"],
                execution_id,
                canonical_json(payload),
                previous_hash,
                receipt_hash,
                receipt["created_at"],
            ),
        )
        return receipt
""",
    """    def _append_receipt(
        self,
        connection: DatabaseConnection,
        *,
        execution_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.receipt_ledger.append(
            connection,
            execution_id=execution_id,
            payload=payload,
        )
""",
)
replace_once(
    service,
    """    @staticmethod
    def _decode_receipt(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value
""",
    "",
)

write(
    ROOT / "voodoo_product" / "receipt.py",
    """from __future__ import annotations

import json
from typing import Any

from . import statements as sql
from .evidence_primitives import canonical_json, chained_hash, new_id, utc_now
from .persistence import DatabaseConnection, ProductDatabaseAdapter


class ReceiptLedger:
    \"\"\"Reusable writer, reader, and verifier for the execution receipt hash chain.\"\"\"

    def __init__(self, database: ProductDatabaseAdapter) -> None:
        self.db = database

    def append(
        self,
        connection: DatabaseConnection,
        *,
        execution_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last = connection.execute(sql.SELECT_RECEIPT_HEAD).fetchone()
        previous_hash = str(last["receipt_hash"]) if last else "GENESIS"
        receipt_hash = chained_hash(previous_hash, payload)
        receipt = {
            "id": new_id("rcpt"),
            "execution_id": execution_id,
            "payload": payload,
            "previous_hash": previous_hash,
            "receipt_hash": receipt_hash,
            "created_at": utc_now(),
        }
        connection.execute(
            sql.INSERT_RECEIPT,
            (
                receipt["id"],
                execution_id,
                canonical_json(payload),
                previous_hash,
                receipt_hash,
                receipt["created_at"],
            ),
        )
        return receipt

    def list_receipts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                sql.LIST_RECEIPTS,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._decode(dict(row)) for row in rows]

    def verify(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            rows = connection.execute(sql.LIST_RECEIPTS_FOR_VERIFICATION).fetchall()
        previous_hash = "GENESIS"
        for expected_sequence, row in enumerate(rows, start=1):
            payload = json.loads(row["payload_json"])
            expected = chained_hash(previous_hash, payload)
            if (
                int(row["sequence"]) != expected_sequence
                or row["previous_hash"] != previous_hash
                or row["receipt_hash"] != expected
            ):
                return {
                    "valid": False,
                    "count": len(rows),
                    "broken_at": expected_sequence,
                    "sequence": row["sequence"],
                    "receipt_id": row["id"],
                }
            previous_hash = str(row["receipt_hash"])
        return {"valid": True, "count": len(rows), "head": previous_hash}

    @staticmethod
    def _decode(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value
""",
)

write(
    ROOT / "voodoo_product" / "composition.py",
    """from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api import create_product_router
from .audit import AuditLedger
from .config import ProductConfig
from .external_identity_service import GovernedExternalIdentityService
from .http_security import SecurityHeadersMiddleware
from .identity import (
    IdentityProvider,
    create_identity_provider,
    validate_identity_provider_startup,
)
from .observability import (
    StructuredRequestLoggingMiddleware,
    configure_product_logging,
)
from .receipt import ReceiptLedger
from .service import ProductService


@dataclass(frozen=True, slots=True)
class ProductComposition:
    service: ProductService
    audit_ledger: AuditLedger
    receipt_ledger: ReceiptLedger
    external_identity_service: GovernedExternalIdentityService


def install_composed_product_platform(
    app: FastAPI,
    *,
    config: ProductConfig | None = None,
    repository_root: Path | None = None,
    identity_provider: IdentityProvider | None = None,
) -> ProductComposition:
    \"\"\"Install the production platform with shared evidence ledgers.\"\"\"

    resolved_config = config or ProductConfig.from_env()
    validate_identity_provider_startup(resolved_config)
    if identity_provider is not None and identity_provider.name != resolved_config.identity_provider:
        raise RuntimeError("injected identity provider does not match configured provider")

    root = (repository_root or Path.cwd()).resolve()
    product_logger = configure_product_logging(level=resolved_config.log_level)
    service = ProductService(resolved_config)
    audit_ledger = service.audit_ledger
    receipt_ledger = service.receipt_ledger
    resolved_identity_provider = identity_provider or create_identity_provider(
        config=resolved_config,
        service=service,
    )
    external_identity_service = GovernedExternalIdentityService(
        database=service.db,
        audit_ledger=audit_ledger,
    )
    composition = ProductComposition(
        service=service,
        audit_ledger=audit_ledger,
        receipt_ledger=receipt_ledger,
        external_identity_service=external_identity_service,
    )

    app.state.voodoo_product_service = service
    app.state.voodoo_identity_provider = resolved_identity_provider
    app.state.voodoo_audit_ledger = audit_ledger
    app.state.voodoo_receipt_ledger = receipt_ledger
    app.state.voodoo_external_identity_service = external_identity_service
    app.state.voodoo_product_composition = composition
    app.include_router(
        create_product_router(
            identity_provider=resolved_identity_provider,
            service=service,
            repository_root=root,
        )
    )

    if resolved_config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_config.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "X-Request-ID",
            ],
            expose_headers=["X-Request-ID"],
        )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(resolved_config.trusted_hosts),
        www_redirect=False,
    )
    app.add_middleware(
        StructuredRequestLoggingMiddleware,
        logger=product_logger,
        environment=resolved_config.environment,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=resolved_config.environment == "production",
    )

    static_dir = Path(__file__).with_name("static")
    app.mount("/console/assets", StaticFiles(directory=static_dir), name="voodoo-product-assets")

    @app.get("/console", include_in_schema=False)
    def console() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/", include_in_schema=False)
    def product_root() -> RedirectResponse:
        return RedirectResponse(url="/console")

    return composition
""",
)

composition_test = ROOT / "tests" / "system" / "test_product_composition.py"
replace_once(
    composition_test,
    """def test_composition_shares_database_and_audit_ledger_without_public_routes(
    tmp_path: Path,
) -> None:
""",
    """def test_composition_shares_database_and_evidence_ledgers_without_public_routes(
    tmp_path: Path,
) -> None:
""",
)
replace_once(
    composition_test,
    """    assert app.state.voodoo_product_service is composition.service
    assert app.state.voodoo_audit_ledger is composition.audit_ledger
    assert app.state.voodoo_external_identity_service is composition.external_identity_service
    assert app.state.voodoo_product_composition is composition
    assert composition.service.audit_ledger is composition.audit_ledger
    assert composition.audit_ledger.db is composition.service.db
    assert composition.external_identity_service.db is composition.service.db
""",
    """    assert app.state.voodoo_product_service is composition.service
    assert app.state.voodoo_audit_ledger is composition.audit_ledger
    assert app.state.voodoo_receipt_ledger is composition.receipt_ledger
    assert app.state.voodoo_external_identity_service is composition.external_identity_service
    assert app.state.voodoo_product_composition is composition
    assert composition.service.audit_ledger is composition.audit_ledger
    assert composition.service.receipt_ledger is composition.receipt_ledger
    assert composition.audit_ledger.db is composition.service.db
    assert composition.receipt_ledger.db is composition.service.db
    assert composition.external_identity_service.db is composition.service.db
""",
)

write(
    ROOT / "tests" / "system" / "test_receipt_ledger.py",
    """from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.evidence_primitives import chained_hash
from voodoo_product.service import ProductService

ROOT = Path(__file__).resolve().parents[2]


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_receipt_ledger_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "receipt.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 4
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_service_delegates_complete_receipt_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_append_receipt", "list_receipts", "verify_receipt_chain"}
    }

    assert set(methods) == {"_append_receipt", "list_receipts", "verify_receipt_chain"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.receipt_ledger.append" in source_text
    assert "self.receipt_ledger.list_receipts" in source_text
    assert "self.receipt_ledger.verify" in source_text
    assert "sql.SELECT_RECEIPT_HEAD" not in source_text
    assert "sql.INSERT_RECEIPT" not in source_text
    assert "sql.LIST_RECEIPTS" not in source_text
    assert "sql.LIST_RECEIPTS_FOR_VERIFICATION" not in source_text


def test_product_service_rejects_receipt_ledger_from_another_database(tmp_path: Path) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="receipt ledger must use the product service database"):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            receipt_ledger=second.receipt_ledger,
        )


def test_receipt_ledger_preserves_service_contract_and_hash_format(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    operator = service.create_user(
        actor_id=bootstrap["user_id"],
        username="operator",
        password="VeryStrongOperatorPassword1!",
        role="operator",
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Receipt ledger compatibility",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"value": 1},
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="receipt ledger compatibility test",
    )
    execution = service.execute_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        idempotency_key="receipt-ledger-compatibility",
        repository_root=tmp_path,
    )

    receipts = service.list_receipts()
    assert receipts == service.receipt_ledger.list_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["execution_id"] == execution["id"]
    assert receipt["previous_hash"] == "GENESIS"
    assert receipt["receipt_hash"] == chained_hash(receipt["previous_hash"], receipt["payload"])
    assert service.verify_receipt_chain() == service.receipt_ledger.verify()
    assert service.verify_receipt_chain() == {
        "valid": True,
        "count": 1,
        "head": receipt["receipt_hash"],
    }
""",
)

replace_once(
    ROOT / "tests" / "system" / "test_statement_catalog.py",
    "    assert len(execute_calls) == 47\n",
    "    assert len(execute_calls) == 43\n",
)

replace_once(
    ROOT / ".github" / "workflows" / "ci.yml",
    """      - name: Evidence and audit composition gate
        run: >-
          python -m pytest -q
          tests/system/test_evidence_primitives.py
          tests/system/test_product_composition.py
""",
    """      - name: Evidence ledger composition gate
        run: >-
          python -m pytest -q
          tests/system/test_evidence_primitives.py
          tests/system/test_receipt_ledger.py
          tests/system/test_product_composition.py
""",
)

readiness = ROOT / "scripts" / "product_readiness_gate.py"
replace_once(
    readiness,
    '    "voodoo_product/persistence.py",\n    "voodoo_product/service.py",\n',
    '    "voodoo_product/persistence.py",\n    "voodoo_product/receipt.py",\n    "voodoo_product/service.py",\n',
)
replace_once(
    readiness,
    '    "tests/system/test_product_platform_rc1.py",\n    "tests/system/test_release_supply_chain.py",\n',
    '    "tests/system/test_product_platform_rc1.py",\n    "tests/system/test_receipt_ledger.py",\n    "tests/system/test_release_supply_chain.py",\n',
)
replace_once(
    readiness,
    '    "docs/product/PERSISTENCE_BOUNDARY.md",\n    "docs/product/STATEMENT_CATALOG.md",\n',
    '    "docs/product/PERSISTENCE_BOUNDARY.md",\n    "docs/product/RECEIPT_LEDGER_COMPOSITION_BOUNDARY.md",\n    "docs/product/STATEMENT_CATALOG.md",\n',
)

write(
    ROOT / "docs" / "product" / "RECEIPT_LEDGER_COMPOSITION_BOUNDARY.md",
    """# Receipt Ledger Composition Boundary

## Status

Implemented as the canonical execution-receipt evidence boundary.

## Purpose

`ReceiptLedger` owns receipt append, bounded listing, and full chain verification. `ProductService` preserves its existing public methods while delegating the complete receipt surface to one database-bound ledger.

## Runtime composition

`install_composed_product_platform` creates one `ProductService` with:

- one shared `AuditLedger`;
- one shared `ReceiptLedger`;
- one governed external identity service using the same database and audit ledger;
- one immutable `ProductComposition` exposing both evidence ledgers.

The receipt ledger is stored on `app.state.voodoo_receipt_ledger` for internal dependency access. No public route is added.

## Delegation contract

- `_append_receipt` delegates to `ReceiptLedger.append` inside the caller transaction;
- `list_receipts` delegates to the bounded ledger reader;
- `verify_receipt_chain` delegates to the ledger verifier.

`ProductService` contains no direct receipt SQL. The four canonical receipt statements are executed only by `receipt.py`.

## Evidence compatibility

The ledger preserves:

- prefixed non-guessable receipt identifiers;
- canonical JSON payload serialization;
- the existing `GENESIS` chain anchor;
- SHA-256 chaining over the prior hash and payload;
- monotonic receipt sequence verification;
- existing response fields and list ordering.

No schema migration or stored-data transformation is required.

## Failure model

An injected receipt ledger must use the exact same database adapter instance as the product service. A mismatch is rejected during construction. Invalid sequence, previous-hash, or receipt-hash transitions fail verification closed and identify the first broken receipt.

## Explicitly disabled

This boundary does not add routes, enable external sign-in, alter execution authorization, release, deploy, or enable production effects.
""",
)

for path in [
    ROOT / "voodoo_product" / "service.py",
    ROOT / "voodoo_product" / "receipt.py",
    ROOT / "voodoo_product" / "composition.py",
    ROOT / "tests" / "system" / "test_receipt_ledger.py",
    ROOT / "tests" / "system" / "test_product_composition.py",
    ROOT / "tests" / "system" / "test_statement_catalog.py",
    ROOT / "scripts" / "product_readiness_gate.py",
]:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
