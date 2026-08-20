from __future__ import annotations

from pathlib import Path

from voodoo_product.operation_semantics import common_language
from voodoo_product.vop_vocabulary import (
    CANONICAL_NOUNS,
    OPERATION_STAGES,
    OPERATION_TERMINAL_PROFILES,
    SCHEMA_COMPATIBILITY,
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


def test_current_proof_and_operation_cell_are_registered_without_false_universal_supersession() -> None:
    assert "OperationCell" in CANONICAL_NOUNS
    assert OPERATION_STAGES[-1] == "operation_cell"
    assert "verification_result" in OPERATION_STAGES
    assert "operation-proof/v1" in SCHEMA_REGISTRY_IDS
    assert "operation-proof/v2" in SCHEMA_REGISTRY_IDS
    assert "operation-cell/v1" in SCHEMA_REGISTRY_IDS
    assert "operation-proof/v1" not in SCHEMA_SUPERSESSIONS
    assert SCHEMA_COMPATIBILITY["operation-proof/v2"] == (
        "CURRENT_BOUNDED_MUTATION_PROOF_NOT_UNIVERSAL_REPLACEMENT"
    )


def test_read_only_verified_terminal_does_not_require_mutation_receipt_proof_or_cell() -> None:
    read_only = OPERATION_TERMINAL_PROFILES["READ_ONLY_VERIFIED"]
    assert read_only == ("independent_verification", "verification_result")
    assert "execution_receipt" not in read_only
    assert "operation_proof" not in read_only
    assert "operation_cell" not in read_only


def test_bounded_mutation_verified_terminal_requires_receipt_verification_proof_and_cell() -> None:
    mutation = OPERATION_TERMINAL_PROFILES["BOUNDED_MUTATION_VERIFIED"]
    assert mutation == (
        "execution_receipt",
        "independent_verification",
        "verification_result",
        "operation_proof",
        "operation_cell",
    )
