from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.operation_semantics import OPERATION_STAGES as SEMANTICS_OPERATION_STAGES
from voodoo_product.vop_vocabulary import (
    ARTIFACT_STATES,
    CANONICAL_NOUNS,
    CANONICAL_RELATIONS,
    CANONICAL_VERBS,
    FORBIDDEN_SHORTHANDS,
    GATE_STATUSES,
    IDENTITY_FIELDS,
    NOUN_DEFINITIONS,
    OPERATION_STAGES,
    RUN_STATES,
    SCHEMA_REGISTRY_IDS,
    TASK_OUTCOMES,
    canonical_vocabulary,
    require_canonical_term,
)


def digest_without(payload: dict[str, object], digest_field: str) -> str:
    without_digest = {key: value for key, value in payload.items() if key != digest_field}
    return hashlib.sha256(canonical_json(without_digest).encode("utf-8")).hexdigest()


def test_canonical_vocabulary_is_deterministic_and_complete() -> None:
    first = canonical_vocabulary()
    second = canonical_vocabulary()

    assert first == second
    assert first["vocabulary_digest"] == digest_without(first, "vocabulary_digest")
    assert [item["term"] for item in first["nouns"]] == list(CANONICAL_NOUNS)
    assert first["verbs"] == list(CANONICAL_VERBS)
    assert first["relations"] == list(CANONICAL_RELATIONS)
    assert first["identity_fields"] == list(IDENTITY_FIELDS)
    assert first["run_states"] == list(RUN_STATES)
    assert first["gate_statuses"] == list(GATE_STATUSES)
    assert first["task_outcomes"] == list(TASK_OUTCOMES)
    assert first["artifact_states"] == list(ARTIFACT_STATES)
    assert first["schema_registry_ids"] == list(SCHEMA_REGISTRY_IDS)


def test_canonical_collections_have_no_duplicate_terms() -> None:
    for terms in (
        CANONICAL_NOUNS,
        CANONICAL_VERBS,
        CANONICAL_RELATIONS,
        IDENTITY_FIELDS,
        RUN_STATES,
        GATE_STATUSES,
        TASK_OUTCOMES,
        ARTIFACT_STATES,
        SCHEMA_REGISTRY_IDS,
    ):
        assert len(terms) == len(set(terms))


def test_canonical_definition_maps_are_runtime_immutable() -> None:
    with pytest.raises(TypeError):
        NOUN_DEFINITIONS["Actor"] = "mutable"  # type: ignore[index]
    with pytest.raises(TypeError):
        FORBIDDEN_SHORTHANDS["deployed"] = "mutable"  # type: ignore[index]


def test_require_canonical_term_fails_closed() -> None:
    assert require_canonical_term("Operation", category="noun") == "Operation"
    assert require_canonical_term("AUTHORIZE", category="verb") == "AUTHORIZE"
    assert require_canonical_term("PROVES", category="relation") == "PROVES"

    with pytest.raises(ValueError, match="not canonical"):
        require_canonical_term("Task", category="noun")
    with pytest.raises(ValueError, match="unsupported"):
        require_canonical_term("Operation", category="unknown")


def test_operation_semantics_uses_the_same_canonical_stage_sequence() -> None:
    assert SEMANTICS_OPERATION_STAGES == OPERATION_STAGES


def test_schema_registry_manifest_matches_runtime_registry() -> None:
    registry = json.loads(Path("schemas/vop/registry.v1.json").read_text(encoding="utf-8"))

    assert registry["schema_version"] == 1
    assert registry["kind"] == "vop-schema-registry/v1"
    assert registry["vocabulary_type"] == "vop-canonical-vocabulary/v1"
    assert registry["status"] == "RESERVED_IDS"
    assert registry["canonical_schema_ids"] == list(SCHEMA_REGISTRY_IDS)
    assert registry["identity_grammar"] == list(IDENTITY_FIELDS)


def test_canonical_document_contains_non_conflation_and_system_invariants() -> None:
    text = Path("docs/architecture/VOP_CANONICAL_VOCABULARY.md").read_text(encoding="utf-8")

    required = (
        "Jeden význam → jeden termín → jeden kontrakt → jedna autoritativní definice.",
        "APPROVE\n!= AUTHORIZE",
        "AUTHORIZE\n!= ISSUE",
        "EXECUTE\n!= VERIFY",
        "RELEASE\n!= DEPLOY",
        "ONE SYSTEM\n=\nONE SEMANTIC LANGUAGE",
        "One language. One authority model. One proof model. Many providers.",
    )
    for phrase in required:
        assert phrase in text
