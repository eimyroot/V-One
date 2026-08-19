from __future__ import annotations

from pathlib import Path

from voodoo_product.operation_semantics import common_language
from voodoo_product.vop_vocabulary import (
    CANONICAL_NOUNS,
    OPERATION_STAGES,
    SCHEMA_REGISTRY_IDS,
    SCHEMA_SUPERSESSIONS,
)

ROOT = Path(__file__).resolve().parents[2]


def test_evidence_ui_does_not_promote_receipt_integrity_to_verified_operation() -> None:
    source = (ROOT / "voodoo_product" / "static" / "app.js").read_text(encoding="utf-8")

    assert "verification.receipts.valid?'PASS':'FAIL'" in source
    assert "verification.audit.valid?'PASS':'FAIL'" in source
    assert "Independent verification: ${status('UNKNOWN')}" in source
    assert "receipts.map(r=>`<article class=\"receipt-card\"><header><strong class=\"mono\">${escapeHtml(r.id)}</strong>${status('VERIFIED')}" not in source


def test_runner_common_language_never_owns_grant_consumption() -> None:
    runner = next(member for member in common_language()["members"] if member["role"] == "runner")

    assert runner["authority"] == "bounded_execution_only"
    assert "without issuing or consuming grants" in runner["purpose"]
    assert "Consumes a scoped grant" not in runner["purpose"]


def test_current_proof_and_operation_cell_are_canonical_vop_identities() -> None:
    assert "OperationCell" in CANONICAL_NOUNS
    assert OPERATION_STAGES[-1] == "operation_cell"
    assert "operation-proof/v1" in SCHEMA_REGISTRY_IDS
    assert "operation-proof/v2" in SCHEMA_REGISTRY_IDS
    assert "operation-cell/v1" in SCHEMA_REGISTRY_IDS
    assert SCHEMA_SUPERSESSIONS["operation-proof/v1"] == "operation-proof/v2"
