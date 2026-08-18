from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from voodoo_product.authoritative_grant import EXECUTION_GRANT_V2_TYPE
from voodoo_product.credential_broker import CREDENTIAL_ACCESS_DECISION_TYPE
from voodoo_product.dispatch_envelope import DISPATCH_ENVELOPE_TYPE
from voodoo_product.dispatch_inbox import DISPATCH_INBOX_ADMISSION_TYPE
from voodoo_product.dispatch_outbox import DISPATCH_OUTBOX_ENTRY_TYPE
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_lease import EXECUTION_LEASE_TYPE
from voodoo_product.github_read_provider import GITHUB_REF_OBSERVATION_TYPE
from voodoo_product.grant_consumption import GRANT_CONSUMPTION_WITNESS_TYPE
from voodoo_product.isolated_runner import RUNTIME_ACTIVATION_TYPE, RUNTIME_BOOTSTRAP_TYPE
from voodoo_product.operation_semantics import OPERATION_STAGES as SEMANTICS_OPERATION_STAGES
from voodoo_product.runner_identity import RUNNER_BOUNDARY_TYPE, RUNNER_IDENTITY_TYPE
from voodoo_product.verifier_identity import (
    INDEPENDENT_VERIFICATION_BOUNDARY_TYPE,
    VERIFIER_IDENTITY_TYPE,
)
from voodoo_product.vop_vocabulary import (
    ARTIFACT_STATES,
    BOUNDARY_DEFINITIONS,
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
    SCHEMA_SUPERSESSIONS,
    SEMANTIC_CHANGE_RULE,
    SURFACE_CONSISTENCY_RULE,
    TASK_OUTCOMES,
    VOCABULARY_REVISION,
    VOP_PUBLIC_SURFACES,
    canonical_vocabulary,
    require_canonical_term,
    require_vop_surface,
)


def digest_without(payload: dict[str, object], digest_field: str) -> str:
    without_digest = {key: value for key, value in payload.items() if key != digest_field}
    return hashlib.sha256(canonical_json(without_digest).encode("utf-8")).hexdigest()


def test_canonical_vocabulary_is_deterministic_and_complete() -> None:
    first = canonical_vocabulary()
    second = canonical_vocabulary()

    assert first == second
    assert first["vocabulary_digest"] == digest_without(first, "vocabulary_digest")
    assert first["vocabulary_revision"] == VOCABULARY_REVISION
    assert first["surface_consistency_rule"] == SURFACE_CONSISTENCY_RULE
    assert first["semantic_change_rule"] == SEMANTIC_CHANGE_RULE
    assert first["public_surfaces"] == list(VOP_PUBLIC_SURFACES)
    assert [item["term"] for item in first["nouns"]] == list(CANONICAL_NOUNS)
    assert first["verbs"] == list(CANONICAL_VERBS)
    assert first["relations"] == list(CANONICAL_RELATIONS)
    assert first["identity_fields"] == list(IDENTITY_FIELDS)
    assert first["run_states"] == list(RUN_STATES)
    assert first["gate_statuses"] == list(GATE_STATUSES)
    assert first["task_outcomes"] == list(TASK_OUTCOMES)
    assert first["artifact_states"] == list(ARTIFACT_STATES)
    assert first["schema_registry_ids"] == list(SCHEMA_REGISTRY_IDS)
    assert first["schema_supersessions"] == dict(SCHEMA_SUPERSESSIONS)
    assert first["boundary_definitions"] == dict(sorted(BOUNDARY_DEFINITIONS.items()))


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
        VOP_PUBLIC_SURFACES,
    ):
        assert len(terms) == len(set(terms))


def test_canonical_definition_maps_are_runtime_immutable() -> None:
    with pytest.raises(TypeError):
        NOUN_DEFINITIONS["Actor"] = "mutable"  # type: ignore[index]
    with pytest.raises(TypeError):
        FORBIDDEN_SHORTHANDS["deployed"] = "mutable"  # type: ignore[index]
    with pytest.raises(TypeError):
        SCHEMA_SUPERSESSIONS["execution-grant/v1"] = "other"  # type: ignore[index]


def test_require_canonical_term_and_surface_fail_closed() -> None:
    assert require_canonical_term("Operation", category="noun") == "Operation"
    assert require_canonical_term("AUTHORIZE", category="verb") == "AUTHORIZE"
    assert require_canonical_term("PROVES", category="relation") == "PROVES"
    assert require_vop_surface("code") == "code"
    assert require_vop_surface("UI") == "UI"

    with pytest.raises(ValueError, match="not canonical"):
        require_canonical_term("Task", category="noun")
    with pytest.raises(ValueError, match="unsupported"):
        require_canonical_term("Operation", category="unknown")
    with pytest.raises(ValueError, match="not a governed VOP public surface"):
        require_vop_surface("random")


def test_operation_semantics_uses_the_same_canonical_stage_sequence() -> None:
    assert SEMANTICS_OPERATION_STAGES == OPERATION_STAGES


def test_schema_registry_manifest_matches_runtime_registry_and_version_lineage() -> None:
    registry = json.loads(Path("schemas/vop/registry.v1.json").read_text(encoding="utf-8"))

    assert registry["schema_version"] == 1
    assert registry["kind"] == "vop-schema-registry/v1"
    assert registry["vocabulary_type"] == "vop-canonical-vocabulary/v1"
    assert registry["vocabulary_revision"] == VOCABULARY_REVISION
    assert registry["status"] == "RESERVED_IDS"
    assert registry["canonical_schema_ids"] == list(SCHEMA_REGISTRY_IDS)
    assert registry["schema_supersessions"] == dict(SCHEMA_SUPERSESSIONS)
    assert registry["identity_grammar"] == list(IDENTITY_FIELDS)
    assert registry["surface_consistency_rule"] == SURFACE_CONSISTENCY_RULE
    assert registry["semantic_change_rule"] == SEMANTIC_CHANGE_RULE
    assert SCHEMA_SUPERSESSIONS["execution-grant/v1"] == EXECUTION_GRANT_V2_TYPE


def test_released_phase_c_d_e1_contract_ids_are_reserved_in_one_registry() -> None:
    released_ids = {
        EXECUTION_GRANT_V2_TYPE,
        GRANT_CONSUMPTION_WITNESS_TYPE,
        DISPATCH_OUTBOX_ENTRY_TYPE,
        DISPATCH_ENVELOPE_TYPE,
        DISPATCH_INBOX_ADMISSION_TYPE,
        EXECUTION_LEASE_TYPE,
        RUNNER_IDENTITY_TYPE,
        RUNNER_BOUNDARY_TYPE,
        CREDENTIAL_ACCESS_DECISION_TYPE,
        RUNTIME_BOOTSTRAP_TYPE,
        RUNTIME_ACTIVATION_TYPE,
        GITHUB_REF_OBSERVATION_TYPE,
        VERIFIER_IDENTITY_TYPE,
        INDEPENDENT_VERIFICATION_BOUNDARY_TYPE,
    }

    assert released_ids <= set(SCHEMA_REGISTRY_IDS)


def test_vop_cross_surface_invariant_is_normative_and_not_redefined() -> None:
    foundation = Path("foundation/TERMINOLOGY.md").read_text(encoding="utf-8")
    adr = Path("docs/adr/ADR-0014-vop-terminology-freeze-r1.md").read_text(encoding="utf-8")

    invariant = f"{SURFACE_CONSISTENCY_RULE} {SEMANTIC_CHANGE_RULE}"
    assert invariant in foundation
    assert invariant in adr
    assert "VOP authority | `docs/architecture/VOP_CANONICAL_VOCABULARY.md` + `voodoo_product/vop_vocabulary.py`" in foundation


def test_execution_grant_and_runner_meanings_match_released_authority_model() -> None:
    foundation = Path("foundation/TERMINOLOGY.md").read_text(encoding="utf-8")

    assert "current authoritative runtime authority contract is" in foundation
    assert "execution-grant/v2" in foundation
    assert "Runner **does not\nissue or consume the Grant**" in foundation
    assert "Grant consumption" in foundation


def test_sandcloud_is_not_defined_as_execution_boundary_anymore() -> None:
    foundation = Path("foundation/TERMINOLOGY.md").read_text(encoding="utf-8")
    adr_13 = Path("docs/adr/ADR-0013-read-only-sandcloud-runner-boundary.md").read_text(
        encoding="utf-8"
    )

    stale = "SandCloud is the V-One provider-neutral name for the isolated execution boundary"
    assert stale not in foundation
    assert stale not in adr_13
    assert "SandCloud    = governed non-canonical staging/review/validation/evidence" in adr_13
    assert "not the execution boundary" in BOUNDARY_DEFINITIONS["SandCloud"]


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
