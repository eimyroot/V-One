import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "schemas" / "vop" / "registry.v1.json"

EXPECTED_NOUNS = {
    "Actor",
    "Intent",
    "Operation",
    "ReviewedOperation",
    "Capability",
    "Input",
    "Target",
    "ExpectedPostState",
    "Permission",
    "PolicyRevision",
    "Approval",
    "ApprovalCertificate",
    "AuthorityWitnessSet",
    "AuthorizationSnapshot",
    "ExecutionGrant",
    "ExecutionCapsule",
    "Dispatch",
    "Runner",
    "Handler",
    "ExecutionReceipt",
    "VerificationResult",
    "Evidence",
    "OperationProof",
    "Module",
    "Candidate",
    "Activation",
}

EXPECTED_VERBS = {
    "PROPOSE",
    "NORMALIZE",
    "VALIDATE",
    "REVIEW",
    "APPROVE",
    "AUTHORIZE",
    "ISSUE",
    "DISPATCH",
    "EXECUTE",
    "VERIFY",
    "ATTEST",
    "ADOPT",
    "ACTIVATE",
    "RELEASE",
    "DEPLOY",
    "REVOKE",
    "SUPERSEDE",
}

EXPECTED_RELATIONS = {
    "REQUESTED_BY",
    "PARENT_OF",
    "CHILD_OF",
    "DEPENDS_ON",
    "DERIVED_FROM",
    "BOUND_TO",
    "AUTHORIZED_BY",
    "ISSUED_FROM",
    "DISPATCHED_TO",
    "EXECUTED_BY",
    "VERIFIED_BY",
    "PRODUCED",
    "PROVES",
    "SUPERSEDES",
    "ACTIVATES",
    "CAUSES",
    "CORRELATES_WITH",
}

EXPECTED_SCHEMA_IDS = {
    "operation-request/v1",
    "reviewed-operation/v1",
    "capability-definition/v1",
    "execution-target/v1",
    "policy-revision/v1",
    "approval-certificate/v1",
    "authority-witness-set/v1",
    "authorization-snapshot/v1",
    "execution-grant/v1",
    "execution-capsule/v1",
    "dispatch-envelope/v1",
    "execution-receipt/v1",
    "verification-result/v1",
    "operation-proof/v1",
}

EXPECTED_STATES = {
    "RunState": [
        "RECEIVED",
        "CLASSIFIED",
        "PLANNED",
        "IN_PROGRESS",
        "WAITING_DEPENDENCY",
        "WAITING_APPROVAL",
        "REVIEW",
        "COMPLETED",
        "CANCELLED",
    ],
    "GateStatus": ["PASS", "FAIL", "BLOCKED", "UNKNOWN", "NOT_APPLICABLE"],
    "TaskOutcome": ["COMPLETE", "PARTIAL", "FAILED", "BLOCKED", "CANCELLED"],
    "ArtifactLifecycle": ["PREPARED", "APPLIED", "VERIFIED", "PUBLISHED", "DEPLOYED"],
}


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_vop_registry_identity_and_invariant() -> None:
    registry = load_registry()
    assert registry["schema"] == "vone.vop-canonical-vocabulary/v1"
    assert registry["invariant"] == "ONE_SYSTEM_ONE_SEMANTIC_LANGUAGE"


def test_vop_canonical_terms_are_exact_and_unique() -> None:
    registry = load_registry()
    assert set(registry["nouns"]) == EXPECTED_NOUNS
    assert len(registry["nouns"]) == len(EXPECTED_NOUNS)
    assert set(registry["verbs"]) == EXPECTED_VERBS
    assert len(registry["verbs"]) == len(EXPECTED_VERBS)
    assert set(registry["relations"]) == EXPECTED_RELATIONS
    assert len(registry["relations"]) == len(EXPECTED_RELATIONS)


def test_vop_uses_existing_canonical_state_taxonomies() -> None:
    registry = load_registry()
    assert registry["states"] == EXPECTED_STATES


def test_vop_schema_registry_is_versioned_and_exact() -> None:
    registry = load_registry()
    assert set(registry["schema_ids"]) == EXPECTED_SCHEMA_IDS
    assert len(registry["schema_ids"]) == len(EXPECTED_SCHEMA_IDS)
    assert all(schema_id.endswith("/v1") for schema_id in registry["schema_ids"])


def test_vop_distinct_lifecycle_verbs_never_collapse() -> None:
    registry = load_registry()
    expected_pairs = {
        ("APPROVE", "AUTHORIZE"),
        ("AUTHORIZE", "ISSUE"),
        ("ISSUE", "EXECUTE"),
        ("EXECUTE", "VERIFY"),
        ("VERIFY", "RELEASE"),
        ("RELEASE", "DEPLOY"),
    }
    pairs = {tuple(pair) for pair in registry["distinct_semantics"]}
    assert pairs == expected_pairs
    assert all(left != right for left, right in pairs)


def test_vop_semantic_safety_rules_fail_closed() -> None:
    rules = load_registry()["semantic_rules"]
    assert rules == {
        "provider_specific_language_behind_module_boundary": True,
        "module_translates_but_does_not_authorize": True,
        "no_parallel_status_taxonomy": True,
        "no_evidence_is_not_pass": True,
        "execution_success_is_not_verification": True,
        "discovery_is_not_adoption": True,
        "adoption_is_not_activation": True,
    }
