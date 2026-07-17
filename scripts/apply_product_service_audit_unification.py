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


def rewrite(path: Path, content: str) -> None:
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")


def patch_service() -> None:
    path = ROOT / "voodoo_product" / "service.py"
    replace_once(
        path,
        "from .adapters import AdapterContext, AdapterError, execute_adapter\n"
        "from .config import ProductConfig\n"
        "from .db import create_product_database\n",
        "from .adapters import AdapterContext, AdapterError, execute_adapter\n"
        "from .audit import AuditLedger\n"
        "from .config import ProductConfig\n"
        "from .db import create_product_database\n"
        "from .evidence_primitives import canonical_json, chained_hash, new_id, utc_now\n",
    )
    replace_once(
        path,
        "\n\ndef utc_now() -> str:\n"
        "    return datetime.now(UTC).isoformat(timespec=\"milliseconds\")\n",
        "",
    )
    replace_once(
        path,
        "\n\ndef new_id(prefix: str) -> str:\n"
        "    return f\"{prefix}_{secrets.token_hex(8)}\"\n"
        "\n\n"
        "def canonical_json(value: Any) -> str:\n"
        "    return json.dumps(value, sort_keys=True, separators=(\",\", \":\"), ensure_ascii=False)\n"
        "\n\n"
        "def chained_hash(previous_hash: str, payload: dict[str, Any]) -> str:\n"
        "    return hashlib.sha256(f\"{previous_hash}\\n{canonical_json(payload)}\".encode()).hexdigest()\n",
        "",
    )
    replace_once(
        path,
        "        database: ProductDatabaseAdapter | None = None,\n"
        "    ):\n",
        "        database: ProductDatabaseAdapter | None = None,\n"
        "        audit_ledger: AuditLedger | None = None,\n"
        "    ) -> None:\n",
    )
    replace_once(
        path,
        "        self.db.initialize()\n"
        "        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)\n",
        "        self.db.initialize()\n"
        "        resolved_audit_ledger = audit_ledger or AuditLedger(self.db)\n"
        "        if resolved_audit_ledger.db is not self.db:\n"
        "            raise ValueError(\"audit ledger must use the product service database\")\n"
        "        self.audit_ledger = resolved_audit_ledger\n"
        "        self.config.sandbox_root.mkdir(parents=True, exist_ok=True)\n",
    )
    replace_once(
        path,
        "    def list_audit_events(self, *, limit: int = 200) -> list[dict[str, Any]]:\n"
        "        with self.db.connect() as connection:\n"
        "            rows = connection.execute(\n"
        "                sql.LIST_AUDIT_EVENTS,\n"
        "                (max(1, min(limit, 1000)),),\n"
        "            ).fetchall()\n"
        "        return [self._decode_audit(dict(row)) for row in rows]\n"
        "\n"
        "    def verify_audit_chain(self) -> dict[str, Any]:\n"
        "        with self.db.connect() as connection:\n"
        "            rows = connection.execute(sql.LIST_AUDIT_EVENTS_FOR_VERIFICATION).fetchall()\n"
        "        previous_hash = \"GENESIS\"\n"
        "        for row in rows:\n"
        "            payload = {\n"
        "                \"id\": row[\"id\"],\n"
        "                \"actor_id\": row[\"actor_id\"],\n"
        "                \"action\": row[\"action\"],\n"
        "                \"target_type\": row[\"target_type\"],\n"
        "                \"target_id\": row[\"target_id\"],\n"
        "                \"payload\": json.loads(row[\"payload_json\"]),\n"
        "                \"created_at\": row[\"created_at\"],\n"
        "            }\n"
        "            expected = chained_hash(previous_hash, payload)\n"
        "            if row[\"previous_hash\"] != previous_hash or row[\"event_hash\"] != expected:\n"
        "                return {\"valid\": False, \"sequence\": row[\"sequence\"], \"event_id\": row[\"id\"]}\n"
        "            previous_hash = row[\"event_hash\"]\n"
        "        return {\"valid\": True, \"count\": len(rows), \"head\": previous_hash}\n",
        "    def list_audit_events(self, *, limit: int = 200) -> list[dict[str, Any]]:\n"
        "        return self.audit_ledger.list_events(limit=limit)\n"
        "\n"
        "    def verify_audit_chain(self) -> dict[str, Any]:\n"
        "        return self.audit_ledger.verify()\n",
    )
    replace_once(
        path,
        "    def _append_audit(\n"
        "        self,\n"
        "        connection: DatabaseConnection,\n"
        "        *,\n"
        "        actor_id: str,\n"
        "        action: str,\n"
        "        target_type: str,\n"
        "        target_id: str,\n"
        "        payload: dict[str, Any],\n"
        "    ) -> dict[str, Any]:\n"
        "        last = connection.execute(sql.SELECT_AUDIT_HEAD).fetchone()\n"
        "        previous_hash = str(last[\"event_hash\"]) if last else \"GENESIS\"\n"
        "        event = {\n"
        "            \"id\": new_id(\"aud\"),\n"
        "            \"actor_id\": actor_id,\n"
        "            \"action\": action,\n"
        "            \"target_type\": target_type,\n"
        "            \"target_id\": target_id,\n"
        "            \"payload\": payload,\n"
        "            \"created_at\": utc_now(),\n"
        "        }\n"
        "        event_hash = chained_hash(previous_hash, event)\n"
        "        connection.execute(\n"
        "            sql.INSERT_AUDIT_EVENT,\n"
        "            (\n"
        "                event[\"id\"],\n"
        "                actor_id,\n"
        "                action,\n"
        "                target_type,\n"
        "                target_id,\n"
        "                canonical_json(payload),\n"
        "                previous_hash,\n"
        "                event_hash,\n"
        "                event[\"created_at\"],\n"
        "            ),\n"
        "        )\n"
        "        return {**event, \"previous_hash\": previous_hash, \"event_hash\": event_hash}\n",
        "    def _append_audit(\n"
        "        self,\n"
        "        connection: DatabaseConnection,\n"
        "        *,\n"
        "        actor_id: str,\n"
        "        action: str,\n"
        "        target_type: str,\n"
        "        target_id: str,\n"
        "        payload: dict[str, Any],\n"
        "    ) -> dict[str, Any]:\n"
        "        return self.audit_ledger.append(\n"
        "            connection,\n"
        "            actor_id=actor_id,\n"
        "            action=action,\n"
        "            target_type=target_type,\n"
        "            target_id=target_id,\n"
        "            payload=payload,\n"
        "        )\n",
    )
    replace_once(
        path,
        "\n"
        "    @staticmethod\n"
        "    def _decode_audit(value: dict[str, Any]) -> dict[str, Any]:\n"
        "        value[\"payload\"] = json.loads(value.pop(\"payload_json\"))\n"
        "        return value\n",
        "",
    )


def patch_composition() -> None:
    path = ROOT / "voodoo_product" / "composition.py"
    replace_once(path, "from .ledger_service import LedgerBackedProductService\n", "from .service import ProductService\n")
    replace_once(path, "    service: LedgerBackedProductService\n", "    service: ProductService\n")
    replace_once(path, "    service = LedgerBackedProductService(resolved_config)\n", "    service = ProductService(resolved_config)\n")


def patch_tests() -> None:
    rewrite(
        ROOT / "tests" / "system" / "test_product_composition.py",
        '''from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi import FastAPI

from voodoo_product.api import install_product_platform
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
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


def test_audit_ledger_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "audit.py"
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


def test_product_service_delegates_complete_audit_surface() -> None:
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
        and node.name in {"_append_audit", "list_audit_events", "verify_audit_chain"}
    }

    assert set(methods) == {"_append_audit", "list_audit_events", "verify_audit_chain"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.audit_ledger.append" in source_text
    assert "self.audit_ledger.list_events" in source_text
    assert "self.audit_ledger.verify" in source_text
    assert "sql.SELECT_AUDIT_HEAD" not in source_text
    assert "sql.INSERT_AUDIT_EVENT" not in source_text
    assert "sql.LIST_AUDIT_EVENTS" not in source_text
    assert "sql.LIST_AUDIT_EVENTS_FOR_VERIFICATION" not in source_text
    assert not (ROOT / "voodoo_product" / "ledger_service.py").exists()


def test_product_service_rejects_audit_ledger_from_another_database(tmp_path: Path) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="audit ledger must use the product service database"):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=second.audit_ledger,
        )


def test_composition_shares_database_and_audit_ledger_without_public_routes(
    tmp_path: Path,
) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert type(composition.service) is ProductService
    assert app.state.voodoo_product_service is composition.service
    assert app.state.voodoo_audit_ledger is composition.audit_ledger
    assert app.state.voodoo_external_identity_service is composition.external_identity_service
    assert app.state.voodoo_product_composition is composition
    assert composition.service.audit_ledger is composition.audit_ledger
    assert composition.audit_ledger.db is composition.service.db
    assert composition.external_identity_service.db is composition.service.db
    assert composition.external_identity_service.audit_ledger is composition.audit_ledger

    bootstrap = composition.service.bootstrap_admin(
        username="bootstrap-admin",
        password="VeryStrongBootstrapPassword1!",
        token="b" * 48,
    )
    administrator = composition.service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="identity-admin",
        password="VeryStrongIdentityAdminPassword1!",
        role="administrator",
    )
    viewer = composition.service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="bound-viewer",
        password="VeryStrongBoundViewerPassword1!",
        role="viewer",
    )
    raw_subject = "composition-subject"
    composition.external_identity_service.create_binding(
        actor_id=str(administrator["id"]),
        user_id=str(viewer["id"]),
        provider="oidc",
        issuer="https://identity.example.com",
        subject=raw_subject,
        reason="Approved composition-bound identity enrollment",
    )

    assert composition.audit_ledger.verify()["valid"] is True
    assert composition.service.verify_audit_chain()["valid"] is True
    assert composition.service.list_audit_events() == composition.audit_ledger.list_events()
    events = composition.audit_ledger.list_events()
    assert events[0]["action"] == "external_identity_binding.create"
    assert "system.bootstrap" in {event["action"] for event in events}
    assert raw_subject not in json.dumps(events, sort_keys=True)

    paths = app.openapi()["paths"]
    assert all("external-identity" not in path for path in paths)
    assert all("identity-bindings" not in path for path in paths)


def test_composed_installer_preserves_routes_and_middleware(tmp_path: Path) -> None:
    legacy_app = FastAPI()
    install_product_platform(
        legacy_app,
        config=product_config(tmp_path, name="legacy"),
        repository_root=tmp_path,
    )
    composed_app = FastAPI()
    install_composed_product_platform(
        composed_app,
        config=product_config(tmp_path, name="composed"),
        repository_root=tmp_path,
    )

    legacy_paths = {
        path: tuple(sorted(methods)) for path, methods in legacy_app.openapi()["paths"].items()
    }
    composed_paths = {
        path: tuple(sorted(methods)) for path, methods in composed_app.openapi()["paths"].items()
    }
    assert composed_paths == legacy_paths
    assert [middleware.cls for middleware in composed_app.user_middleware] == [
        middleware.cls for middleware in legacy_app.user_middleware
    ]


def test_product_entrypoint_uses_composed_installer() -> None:
    source = (ROOT / "voodoo_product" / "main.py").read_text(encoding="utf-8")
    assert "from .composition import install_composed_product_platform" in source
    assert "install_composed_product_platform(app)" in source
    assert "from .api import install_product_platform" not in source
''',
    )


def patch_readiness() -> None:
    path = ROOT / "scripts" / "product_readiness_gate.py"
    replace_once(path, '    "voodoo_product/ledger_service.py",\n', "")


def patch_documentation() -> None:
    rewrite(
        ROOT / "docs" / "product" / "AUDIT_LEDGER_COMPOSITION_BOUNDARY.md",
        '''# Audit Ledger and Product Composition Boundary

## Status

Implemented as the canonical product audit boundary. `ProductService` now owns and delegates to one reusable `AuditLedger`; the temporary ledger-backed subclass and duplicate audit implementation have been removed.

## Purpose

Every product operation, governed external identity operation, audit reader, and audit verifier must share one database-bound ledger implementation without changing the public service interface or stored evidence format.

## Runtime composition

`install_composed_product_platform` creates:

- one canonical `ProductService`;
- one audit ledger owned by that service;
- one governed external identity service using the same database and ledger;
- one immutable `ProductComposition` containing those components.

The components are stored on `app.state` for internal dependency access. The identity lifecycle service is not attached to a router.

## Delegation contract

`ProductService` preserves all existing methods while delegating its audit surface:

- `_append_audit` delegates to `AuditLedger.append` inside the caller transaction;
- `list_audit_events` delegates to the bounded ledger reader;
- `verify_audit_chain` delegates to the ledger verifier.

The service contains no direct audit SQL statements. Constructor injection is permitted only when the supplied ledger is bound to the exact same database adapter instance.

## Neutral evidence primitives

`evidence_primitives.py` owns the dependency-neutral contracts used to create and hash evidence:

- timezone-aware millisecond UTC timestamps;
- non-guessable prefixed identifiers;
- deterministic canonical JSON encoding;
- SHA-256 chaining over the previous hash and canonical payload.

`AuditLedger` imports these primitives directly. A fixed compatibility vector verifies that canonical JSON and hash output remain byte-for-byte identical to the existing stored evidence format.

## Audit guarantees

The ledger uses the canonical statement catalog, preserves the existing `GENESIS`-anchored SHA-256 chain, verifies every hash transition, and remains compatible with audit events produced before this unification.

External identity events continue to exclude the raw provider subject. Only its SHA-256 digest appears in responses and audit payloads.

## Compatibility boundary

Both the compatibility installer and the production composition installer now use the same canonical `ProductService` audit implementation. System tests enforce route and middleware parity, shared-ledger identity, database binding, and absence of legacy audit SQL from the service.

The removed `ledger_service.py` module was internal and temporary. No public route, schema, service method, or evidence field was removed.

## Explicitly disabled

This boundary does not enable external sign-in, network issuer discovery, public identity-binding management, automatic provisioning, release, deployment, or production effects.
''',
    )


def validate() -> None:
    expected_absent = [
        ROOT / "voodoo_product" / "ledger_service.py",
    ]
    if any(path.exists() for path in expected_absent):
        raise RuntimeError("temporary ledger service still exists")

    for relative in (
        "voodoo_product/service.py",
        "voodoo_product/composition.py",
        "tests/system/test_product_composition.py",
        "scripts/product_readiness_gate.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    service_text = (ROOT / "voodoo_product" / "service.py").read_text(encoding="utf-8")
    forbidden = (
        "sql.SELECT_AUDIT_HEAD",
        "sql.INSERT_AUDIT_EVENT",
        "sql.LIST_AUDIT_EVENTS",
        "sql.LIST_AUDIT_EVENTS_FOR_VERIFICATION",
        "def _decode_audit",
    )
    present = [token for token in forbidden if token in service_text]
    if present:
        raise RuntimeError(f"legacy audit implementation remains: {present}")


if __name__ == "__main__":
    patch_service()
    patch_composition()
    patch_tests()
    patch_readiness()
    patch_documentation()
    (ROOT / "voodoo_product" / "ledger_service.py").unlink()
    validate()
    print("product service audit unification applied")
