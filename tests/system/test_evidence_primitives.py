from __future__ import annotations

import ast
import re
from datetime import UTC, datetime
from pathlib import Path

from voodoo_product.evidence_primitives import canonical_json, chained_hash, new_id, utc_now
from voodoo_product.service import (
    canonical_json as legacy_canonical_json,
    chained_hash as legacy_chained_hash,
)

ROOT = Path(__file__).resolve().parents[2]


def test_evidence_primitives_are_dependency_neutral() -> None:
    source = ROOT / "voodoo_product" / "evidence_primitives.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not {
        module
        for module in imported_modules | imported_from
        if module.startswith("voodoo_product")
    }
    assert ".service" not in source_text
    assert ".persistence" not in source_text
    assert "fastapi" not in source_text


def test_audit_ledger_does_not_import_product_service() -> None:
    source_text = (ROOT / "voodoo_product" / "audit.py").read_text(encoding="utf-8")

    assert "from .service import" not in source_text
    assert "from .evidence_primitives import" in source_text


def test_canonical_evidence_format_is_backward_compatible() -> None:
    payload = {
        "action": "system.bootstrap",
        "payload": {"role": "administrator", "username": "eimy"},
    }
    encoded = '{"action":"system.bootstrap","payload":{"role":"administrator","username":"eimy"}}'
    expected_hash = "07cbfeda9632d663e091441859ca86fb98f931a3f1320910829424982cac7905"

    assert canonical_json(payload) == encoded
    assert chained_hash("GENESIS", payload) == expected_hash
    assert canonical_json(payload) == legacy_canonical_json(payload)
    assert chained_hash("GENESIS", payload) == legacy_chained_hash("GENESIS", payload)


def test_identifier_and_timestamp_contracts_remain_stable() -> None:
    identifier = new_id("aud")
    timestamp = utc_now()
    parsed = datetime.fromisoformat(timestamp)

    assert re.fullmatch(r"aud_[0-9a-f]{16}", identifier)
    assert parsed.tzinfo == UTC
    assert len(timestamp.rsplit(".", maxsplit=1)[-1].removesuffix("+00:00")) == 3
