from __future__ import annotations

import hashlib
from types import MappingProxyType
from typing import Any, Final

from .evidence_primitives import canonical_json

SCHEMA_VERSION: Final = 1
VOCABULARY_TYPE: Final = "vop-canonical-vocabulary/v1"

# One meaning -> one term -> one contract -> one authoritative definition.
CANONICAL_NOUNS: Final = (
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
)

CANONICAL_VERBS: Final = (
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
)

CANONICAL_RELATIONS: Final = (
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
)

IDENTITY_FIELDS: Final = (
    "logical_identity",
    "content_identity",
    "instance_id",
    "schema_version",
    "producer",
    "created_at",
    "causation_id",
    "correlation_id",
)

RUN_STATES: Final = (
    "RECEIVED",
    "CLASSIFIED",
    "PLANNED",
    "IN_PROGRESS",
    "WAITING_DEPENDENCY",
    "WAITING_APPROVAL",
    "REVIEW",
    "COMPLETED",
    "CANCELLED",
)

GATE_STATUSES: Final = (
    "PASS",
    "FAIL",
    "BLOCKED",
    "UNKNOWN",
    "NOT_APPLICABLE",
)

TASK_OUTCOMES: Final = (
    "COMPLETE",
    "PARTIAL",
    "FAILED",
    "BLOCKED",
    "CANCELLED",
)

ARTIFACT_STATES: Final = (
    "PREPARED",
    "APPLIED",
    "VERIFIED",
    "PUBLISHED",
    "DEPLOYED",
)

# Existing runtime lifecycle stages remain semantically narrower than the full noun vocabulary.
# New runtime code must import these values from this module instead of redefining them.
OPERATION_STAGES: Final = (
    "intent",
    "reviewed_operation",
    "policy_decision",
    "approval_quorum_certificate",
    "authorization_snapshot",
    "execution_grant",
    "runner_execution",
    "execution_receipt",
    "independent_verification",
    "operation_proof",
)

SCHEMA_REGISTRY_IDS: Final = (
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
)

# These phrases are semantically unsafe unless the stronger downstream fact is independently proven.
FORBIDDEN_SHORTHANDS: Final = MappingProxyType(
    {
        "approved and authorized": "Approval does not imply Authorization.",
        "successful operation": "Execution success does not imply verified operation success.",
        "deployed": "Deployment must not be inferred from merge, publication, or release evidence.",
    }
)

NOUN_DEFINITIONS: Final = MappingProxyType(
    {
        "Actor": "A principal participating in or initiating a governed operation.",
        "Intent": "The requested outcome before exact operational normalization.",
        "Operation": "A governed unit of work.",
        "ReviewedOperation": "The exact operation content presented to governance.",
        "Capability": "The semantic action the system is able to perform.",
        "Input": "Operation input data.",
        "Target": "The authoritatively identified object of the intended effect.",
        "ExpectedPostState": "The state expected to exist after successful execution.",
        "Permission": "Whether an actor may request a capability in the given context.",
        "PolicyRevision": "An immutable version of policy rules used for a decision.",
        "Approval": "Human or system approval of exact reviewed content.",
        "ApprovalCertificate": "Evidence that the required approvals were satisfied.",
        "AuthorityWitnessSet": "The exact authority facts used to authorize an operation.",
        "AuthorizationSnapshot": "Immutable evidence of an authorization decision.",
        "ExecutionGrant": "Narrow execution permission bound to an authorized operation.",
        "ExecutionCapsule": "The exact identity of executable implementation and runtime inputs.",
        "Dispatch": "Durable handoff of an execution intent to an eligible Runner.",
        "Runner": "The isolated component that performs an execution under a valid grant.",
        "Handler": "The exact implementation of a Capability.",
        "ExecutionReceipt": "The execution subsystem's claim about what it performed.",
        "VerificationResult": "An independent determination of observed real post-state.",
        "Evidence": "An auditable evidence artifact.",
        "OperationProof": "Portable proof binding the governed operation chain.",
        "Module": "A provider or domain translation and implementation package.",
        "Candidate": "A proposed definition or implementation that is not active authority.",
        "Activation": "Explicit adoption of a concrete definition or implementation for use.",
    }
)


def canonical_vocabulary() -> dict[str, Any]:
    """Return the deterministic machine-readable VOP canonical vocabulary."""

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "vocabulary_type": VOCABULARY_TYPE,
        "nouns": [
            {"term": term, "definition": NOUN_DEFINITIONS[term]}
            for term in CANONICAL_NOUNS
        ],
        "verbs": list(CANONICAL_VERBS),
        "relations": list(CANONICAL_RELATIONS),
        "identity_fields": list(IDENTITY_FIELDS),
        "run_states": list(RUN_STATES),
        "gate_statuses": list(GATE_STATUSES),
        "task_outcomes": list(TASK_OUTCOMES),
        "artifact_states": list(ARTIFACT_STATES),
        "operation_stages": list(OPERATION_STAGES),
        "schema_registry_ids": list(SCHEMA_REGISTRY_IDS),
        "forbidden_shorthands": dict(sorted(FORBIDDEN_SHORTHANDS.items())),
    }
    payload["vocabulary_digest"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


def require_canonical_term(term: object, *, category: str) -> str:
    """Fail closed when code attempts to use an unregistered semantic term."""

    categories = {
        "noun": CANONICAL_NOUNS,
        "verb": CANONICAL_VERBS,
        "relation": CANONICAL_RELATIONS,
        "identity_field": IDENTITY_FIELDS,
        "run_state": RUN_STATES,
        "gate_status": GATE_STATUSES,
        "task_outcome": TASK_OUTCOMES,
        "artifact_state": ARTIFACT_STATES,
        "schema_id": SCHEMA_REGISTRY_IDS,
    }
    allowed = categories.get(category)
    if allowed is None:
        raise ValueError("canonical term category is unsupported")
    if not isinstance(term, str) or term not in allowed:
        raise ValueError(f"term is not canonical for category {category}")
    return term
