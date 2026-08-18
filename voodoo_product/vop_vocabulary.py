from __future__ import annotations

import hashlib
from types import MappingProxyType
from typing import Any, Final

from .evidence_primitives import canonical_json

SCHEMA_VERSION: Final = 1
VOCABULARY_TYPE: Final = "vop-canonical-vocabulary/v1"
VOCABULARY_REVISION: Final = "vop-terminology-freeze-r1"

# Canonical invariant: one semantic meaning has one canonical term and one authoritative definition.
SURFACE_CONSISTENCY_RULE: Final = (
    "Stejný VOP termín musí mít napříč kódem, docs, receipts, API a UI jeden význam."
)
SEMANTIC_CHANGE_RULE: Final = (
    "Změna významu vyžaduje nový termín nebo novou verzi."
)
VOP_PUBLIC_SURFACES: Final = ("code", "docs", "receipts", "API", "UI")

CANONICAL_NOUNS: Final = (
    "Actor",
    "Intent",
    "Operation",
    "ReviewedOperation",
    "Capability",
    "Input",
    "Target",
    "ExpectedPostState",
    "ObservedPostState",
    "Permission",
    "PolicyRevision",
    "Approval",
    "ApprovalCertificate",
    "AuthorityWitnessSet",
    "AuthorizationSnapshot",
    "ExecutionGrant",
    "ExecutionCapsule",
    "GrantConsumptionWitness",
    "Dispatch",
    "DispatchOutboxEntry",
    "DispatchInboxAdmission",
    "ExecutionEpoch",
    "ExecutionLease",
    "Runner",
    "RunnerIdentity",
    "RunnerBoundary",
    "Handler",
    "CredentialAccessDecision",
    "VerifierCredentialDecision",
    "RuntimeActivation",
    "Observation",
    "ExecutionReceipt",
    "VerifierIdentity",
    "IndependentVerificationBoundary",
    "VerificationStrength",
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
# Runtime code must import these values instead of defining another operation-stage taxonomy.
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

# Registry presence reserves semantic identity. It never implies implementation, verification,
# release, deployment or authority. Historical IDs remain reserved to preserve auditability.
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
    "execution-grant/v2",
    "execution-capsule/v1",
    "grant-consumption-witness/v1",
    "dispatch-outbox-entry/v1",
    "dispatch-envelope/v1",
    "dispatch-inbox-admission/v1",
    "execution-lease/v1",
    "runner-identity/v1",
    "runner-boundary/v1",
    "credential-access-decision/v1",
    "isolated-runtime-bootstrap/v1",
    "read-only-runtime-activation/v1",
    "controlled-write-requirement/v1",
    "github-create-ref-condition/v1",
    "github-ref-observation/v1",
    "verifier-github-ref-observation/v1",
    "execution-receipt/v1",
    "verifier-identity/v1",
    "independent-verification-boundary/v1",
    "verifier-credential-policy/v1",
    "verifier-credential-decision/v1",
    "observed-post-state/v1",
    "verification-strength/v1",
    "verification-result/v1",
    "operation-proof/v1",
)

SCHEMA_SUPERSESSIONS: Final = MappingProxyType(
    {
        # v1 remains a historical deterministic value contract. v2 is the current authoritative
        # execution-authority contract and must not be silently described as v1.
        "execution-grant/v1": "execution-grant/v2",
    }
)

# These phrases are semantically unsafe unless the stronger downstream fact is independently proven.
FORBIDDEN_SHORTHANDS: Final = MappingProxyType(
    {
        "approved and authorized": "Approval does not imply Authorization.",
        "successful operation": "Execution success does not imply verified operation success.",
        "deployed": "Deployment must not be inferred from merge, publication, or release evidence.",
    }
)

BOUNDARY_DEFINITIONS: Final = MappingProxyType(
    {
        "SandCloud": (
            "Governed non-canonical staging, review, validation and evidence layer; "
            "it is not the execution boundary and does not create authority."
        ),
        "CASTER-MINAL": (
            "Governed execution control surface that hands an already-authorized plan to an "
            "isolated Runner; it does not create authorization."
        ),
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
        "ObservedPostState": "The state independently observed at the target by verification.",
        "Permission": "Whether an actor may request a capability in the given context.",
        "PolicyRevision": "An immutable version of policy rules used for a decision.",
        "Approval": "Human or system approval of exact reviewed content.",
        "ApprovalCertificate": "Evidence that the required approvals were satisfied.",
        "AuthorityWitnessSet": "The exact authority facts used to authorize an operation.",
        "AuthorizationSnapshot": "Immutable evidence of an authorization decision.",
        "ExecutionGrant": (
            "Narrow execution permission bound to an authorized operation; the current "
            "authoritative runtime authority contract is execution-grant/v2."
        ),
        "ExecutionCapsule": "The exact identity of executable implementation and runtime inputs.",
        "GrantConsumptionWitness": (
            "Durable evidence that one ONE_TIME ExecutionGrant was consumed by the control plane "
            "before dispatch."
        ),
        "Dispatch": "Durable handoff of already-authorized execution intent toward an eligible Runner.",
        "DispatchOutboxEntry": "Immutable durable dispatch intent committed by the control plane.",
        "DispatchInboxAdmission": "Durable admission or deduplication result for one dispatch delivery.",
        "ExecutionEpoch": "Monotonic coordination generation used to fence obsolete execution attempts.",
        "ExecutionLease": "Time-bounded coordination lease for one exact current ExecutionEpoch.",
        "Runner": (
            "The isolated execution principal that performs only an already-authorized capability "
            "under current durable dispatch and lease state; it does not issue or consume grants."
        ),
        "RunnerIdentity": "Content-addressed descriptive identity evidence for one concrete Runner instance.",
        "RunnerBoundary": "Fail-closed safety ceiling binding one Runner to exact lease, capsule and capability.",
        "Handler": "The exact implementation of a Capability.",
        "CredentialAccessDecision": (
            "Serializable decision metadata permitting out-of-band delivery of a narrowed credential; "
            "it is not credential material or execution authority."
        ),
        "VerifierCredentialDecision": (
            "Verifier-specific READ-only credential decision metadata bound to an independent "
            "verification boundary; it contains no secret material."
        ),
        "RuntimeActivation": "Evidence that an eligible isolated runtime boundary was activated for use.",
        "Observation": "A bounded provider or target-state observation; observation alone is not verification.",
        "ExecutionReceipt": "The execution subsystem's claim about what it performed.",
        "VerifierIdentity": "Content-addressed identity evidence for a verifier independent from the Runner.",
        "IndependentVerificationBoundary": (
            "Fail-closed binding that proves the required identity, instance and credential separation "
            "between Runner evidence and the Verifier path."
        ),
        "VerificationStrength": "A classification of how strongly an independent VerificationResult is supported.",
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
        "vocabulary_revision": VOCABULARY_REVISION,
        "surface_consistency_rule": SURFACE_CONSISTENCY_RULE,
        "semantic_change_rule": SEMANTIC_CHANGE_RULE,
        "public_surfaces": list(VOP_PUBLIC_SURFACES),
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
        "schema_supersessions": dict(sorted(SCHEMA_SUPERSESSIONS.items())),
        "boundary_definitions": dict(sorted(BOUNDARY_DEFINITIONS.items())),
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


def require_vop_surface(surface: object) -> str:
    """Fail closed when a semantic surface is not one of the VOP-governed public surfaces."""

    if not isinstance(surface, str) or surface not in VOP_PUBLIC_SURFACES:
        raise ValueError("surface is not a governed VOP public surface")
    return surface