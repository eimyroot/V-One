from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .approval_policy import (
    CURRENT_DECISION,
    VALID_ENVIRONMENTS,
    VALID_RISKS,
    ApprovalPolicyDecision,
    ApprovalPolicyInput,
    evaluate_current_approval_policy,
)
from .evidence_primitives import canonical_json

GRAPH_TYPE = "policy-decision-graph/v1"
SCHEMA_VERSION = 1

_CURRENT_EXECUTION_PERMISSION = "execution.run"
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_VALID_REQUEST_STATUSES = {
    "DRAFT",
    "REVIEW_REQUIRED",
    "APPROVED",
    "DENIED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
}
_LIMITATIONS = (
    "Current approvals are not bound to the request payload digest.",
    "Current approvals are not bound to the approval policy version.",
    "Current approvals do not have an expiry binding.",
    "Requested capability is descriptive and is not independently validated by PDG v1.",
    "This read-only projection is not authorization and is not an execution gate.",
)


@dataclass(frozen=True, slots=True)
class ApprovalEvidence:
    """One immutable approval fact supplied to the projection."""

    approval_id: str
    approver_id: str
    decision: str


@dataclass(frozen=True, slots=True)
class PermissionObservation:
    """Caller-supplied result from the authoritative execution permission gate."""

    execution_actor_id: str
    permission_name: str
    granted: bool


@dataclass(frozen=True, slots=True)
class PolicyDecisionSnapshot:
    """Current facts projected without reading or changing runtime state."""

    request_id: str | None = None
    requester_id: str | None = None
    workspace_id: str | None = None
    workspace_environment: str | None = None
    request_environment: str | None = None
    risk: str | None = None
    adapter: str | None = None
    requested_capability: str | None = None
    payload_sha256: str | None = None
    permission_observation: PermissionObservation | None = None
    policy_decision: ApprovalPolicyDecision | None = None
    approvals: tuple[ApprovalEvidence, ...] = ()
    request_status: str | None = None
    emergency_stop_active: bool | None = None
    production_effects_enabled: bool | None = None
    execution_id: str | None = None
    receipt_id: str | None = None
    audit_event_ids: tuple[str, ...] = ()


def project_policy_decision_graph(snapshot: PolicyDecisionSnapshot) -> dict[str, Any]:
    """Return a deterministic, read-only projection of supplied current facts."""

    projection_reasons: set[str] = set()
    limitations = set(_LIMITATIONS)
    policy_reasons: tuple[str, ...] = ()
    policy = snapshot.policy_decision
    valid_policy = _valid_policy_decision(policy)

    required_identifiers = {
        "request_id": snapshot.request_id,
        "requester_id": snapshot.requester_id,
        "workspace_id": snapshot.workspace_id,
        "adapter": snapshot.adapter,
    }
    if any(not _valid_identifier(value) for value in required_identifiers.values()):
        projection_reasons.add("PDG_AUTHORITATIVE_IDENTITY_INVALID")

    if snapshot.workspace_environment not in VALID_ENVIRONMENTS:
        projection_reasons.add("PDG_WORKSPACE_ENVIRONMENT_INVALID")
    if snapshot.request_environment not in VALID_ENVIRONMENTS:
        projection_reasons.add("PDG_REQUEST_ENVIRONMENT_INVALID")
    if (
        snapshot.workspace_environment in VALID_ENVIRONMENTS
        and snapshot.request_environment in VALID_ENVIRONMENTS
        and snapshot.workspace_environment != snapshot.request_environment
    ):
        projection_reasons.add("PDG_WORKSPACE_ENVIRONMENT_MISMATCH")
    if snapshot.risk not in VALID_RISKS:
        projection_reasons.add("PDG_RISK_INVALID")
    if not isinstance(snapshot.payload_sha256, str) or not _SHA256_PATTERN.fullmatch(
        snapshot.payload_sha256
    ):
        projection_reasons.add("PDG_PAYLOAD_DIGEST_INVALID")

    _validate_permission_observation(
        snapshot.permission_observation,
        projection_reasons=projection_reasons,
    )

    if policy is None:
        projection_reasons.add("PDG_POLICY_DECISION_MISSING")
    elif not valid_policy:
        projection_reasons.add("PDG_POLICY_DECISION_INVALID")
    else:
        policy_reasons = policy.reason_codes
        if policy.decision != CURRENT_DECISION:
            projection_reasons.add("PDG_POLICY_DECISION_DENIED")
        if (
            snapshot.request_environment in VALID_ENVIRONMENTS
            and snapshot.risk in VALID_RISKS
            and policy
            != evaluate_current_approval_policy(
                ApprovalPolicyInput(
                    environment=snapshot.request_environment,
                    risk=snapshot.risk,
                )
            )
        ):
            projection_reasons.add("PDG_POLICY_DECISION_MISMATCH")

    nodes = _base_nodes(snapshot, policy)
    used_node_ids = {node["id"] for node in nodes}
    approval_nodes, approval_edges = _approval_graph(
        snapshot,
        policy=policy if valid_policy else None,
        projection_reasons=projection_reasons,
        used_node_ids=used_node_ids,
    )
    nodes.extend(approval_nodes)

    if snapshot.request_status not in _VALID_REQUEST_STATUSES:
        projection_reasons.add("PDG_REQUEST_STATUS_INVALID")
    elif snapshot.request_status != "APPROVED":
        projection_reasons.add("PDG_REQUEST_NOT_APPROVED")

    if type(snapshot.emergency_stop_active) is not bool:
        projection_reasons.add("PDG_EMERGENCY_STOP_STATE_MISSING")
    elif snapshot.emergency_stop_active:
        projection_reasons.add("PDG_EMERGENCY_STOP_ACTIVE")

    if type(snapshot.production_effects_enabled) is not bool:
        projection_reasons.add("PDG_PRODUCTION_EFFECTS_STATE_MISSING")
    elif (
        snapshot.request_environment == "production"
        and not snapshot.production_effects_enabled
    ):
        projection_reasons.add("PDG_PRODUCTION_EFFECTS_DISABLED")

    optional_references = (
        snapshot.execution_id,
        snapshot.receipt_id,
        *snapshot.audit_event_ids,
    )
    if any(value is not None and not _valid_identifier(value) for value in optional_references):
        limitations.add("One or more invalid optional evidence references were omitted.")

    execution_eligible = not projection_reasons
    decision = "ALLOW" if execution_eligible else "DENY"
    projection_reasons.add(
        "PDG_CURRENT_GATES_SATISFIED"
        if execution_eligible
        else "PDG_DENY_BY_DEFAULT"
    )

    edges = _base_edges(snapshot, policy)
    edges.extend(approval_edges)
    _append_optional_evidence(
        snapshot,
        nodes=nodes,
        edges=edges,
        used_node_ids=used_node_ids,
    )
    nodes.sort(key=lambda node: (node["type"], node["id"], canonical_json(node["claims"])))
    edges.sort(key=lambda edge: (edge["from"], edge["relation"], edge["to"]))
    node_ids = [node["id"] for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise RuntimeError("policy decision graph node IDs are not unique")

    graph: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "graph_type": GRAPH_TYPE,
        "decision": decision,
        "execution_eligible": execution_eligible,
        "reason_codes": sorted((*policy_reasons, *projection_reasons)),
        "limitations": sorted(limitations),
        "nodes": nodes,
        "edges": edges,
    }
    graph["graph_digest"] = hashlib.sha256(canonical_json(graph).encode("utf-8")).hexdigest()
    return graph


def _approval_graph(
    snapshot: PolicyDecisionSnapshot,
    *,
    policy: ApprovalPolicyDecision | None,
    projection_reasons: set[str],
    used_node_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    request_node_id = _node_id("request", snapshot.request_id)
    approvals = sorted(
        snapshot.approvals,
        key=lambda item: (str(item.approval_id), str(item.approver_id), str(item.decision)),
    )
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    approval_ids: set[str] = set()
    approved_identities: set[str] = set()

    for index, approval in enumerate(approvals):
        valid = (
            _valid_identifier(approval.approval_id)
            and _valid_identifier(approval.approver_id)
            and approval.decision in {"APPROVED", "DENIED"}
            and approval.approval_id not in approval_ids
        )
        if not valid:
            projection_reasons.add("PDG_APPROVAL_EVIDENCE_INVALID")
        if _valid_identifier(approval.approval_id):
            approval_ids.add(approval.approval_id)
        approval_node_candidate = (
            _node_id("approval", approval.approval_id)
            if _valid_identifier(approval.approval_id)
            else f"approval:invalid-{index}"
        )
        approval_node_id = _unique_node_id(approval_node_candidate, used_node_ids)
        nodes.append(
            {
                "id": approval_node_id,
                "type": "approval",
                "claims": {
                    "approval_id": approval.approval_id,
                    "approver_id": approval.approver_id,
                    "decision": approval.decision,
                },
            }
        )
        edges.append(
            {
                "from": approval_node_id,
                "relation": "reviews",
                "to": request_node_id,
            }
        )
        if approval.approver_id == snapshot.requester_id:
            projection_reasons.add("PDG_REQUESTER_SELF_APPROVAL")
        if approval.decision == "DENIED":
            projection_reasons.add("PDG_APPROVAL_DENIED")
        elif approval.decision == "APPROVED" and _valid_identifier(approval.approver_id):
            approved_identities.add(approval.approver_id)

    if policy is None or not _valid_policy_decision(policy):
        return nodes, edges
    approved_count = sum(approval.decision == "APPROVED" for approval in approvals)
    if approved_count < policy.required_approvals:
        projection_reasons.add("PDG_APPROVALS_INSUFFICIENT")
    if len(approved_identities) < policy.distinct_approver_identities:
        projection_reasons.add("PDG_DISTINCT_APPROVERS_INSUFFICIENT")
    return nodes, edges


def _base_nodes(
    snapshot: PolicyDecisionSnapshot,
    policy: ApprovalPolicyDecision | None,
) -> list[dict[str, Any]]:
    policy_claims = policy.to_dict() if isinstance(policy, ApprovalPolicyDecision) else {}
    return [
        {
            "id": _node_id("subject", snapshot.requester_id),
            "type": "subject",
            "claims": {"role": "requester"},
        },
        {
            "id": _node_id("workspace", snapshot.workspace_id),
            "type": "workspace",
            "claims": {"environment": snapshot.workspace_environment},
        },
        {
            "id": _node_id("request", snapshot.request_id),
            "type": "request",
            "claims": {
                "adapter": snapshot.adapter,
                "capability": snapshot.requested_capability,
                "environment": snapshot.request_environment,
                "payload_sha256": snapshot.payload_sha256,
                "risk": snapshot.risk,
                "status": snapshot.request_status,
            },
        },
        {
            "id": _node_id(
                "policy",
                policy.policy_version if isinstance(policy, ApprovalPolicyDecision) else None,
            ),
            "type": "policy",
            "claims": policy_claims,
        },
        {
            "id": "permission:execution-observation",
            "type": "permission_observation",
            "claims": _permission_claims(snapshot.permission_observation),
        },
        {
            "id": "runtime:current",
            "type": "runtime_context",
            "claims": {
                "emergency_stop_active": snapshot.emergency_stop_active,
                "production_effects_enabled": snapshot.production_effects_enabled,
            },
        },
        {
            "id": _node_id("decision", snapshot.request_id),
            "type": "projection",
            "claims": {"authority": "NONE", "projection_only": True},
        },
    ]


def _base_edges(
    snapshot: PolicyDecisionSnapshot,
    policy: ApprovalPolicyDecision | None,
) -> list[dict[str, str]]:
    request_id = _node_id("request", snapshot.request_id)
    decision_id = _node_id("decision", snapshot.request_id)
    return [
        {
            "from": _node_id("subject", snapshot.requester_id),
            "relation": "requests",
            "to": request_id,
        },
        {
            "from": request_id,
            "relation": "targets",
            "to": _node_id("workspace", snapshot.workspace_id),
        },
        {
            "from": request_id,
            "relation": "evaluated_under",
            "to": _node_id(
                "policy",
                policy.policy_version if isinstance(policy, ApprovalPolicyDecision) else None,
            ),
        },
        {
            "from": "permission:execution-observation",
            "relation": "observed_for",
            "to": request_id,
        },
        {"from": decision_id, "relation": "projects", "to": request_id},
        {
            "from": decision_id,
            "relation": "observes",
            "to": "permission:execution-observation",
        },
        {"from": decision_id, "relation": "observes", "to": "runtime:current"},
    ]


def _append_optional_evidence(
    snapshot: PolicyDecisionSnapshot,
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    used_node_ids: set[str],
) -> None:
    decision_id = _node_id("decision", snapshot.request_id)
    execution_id = (
        _node_id("execution", snapshot.execution_id)
        if _valid_identifier(snapshot.execution_id)
        else None
    )
    receipt_id = (
        _node_id("receipt", snapshot.receipt_id)
        if _valid_identifier(snapshot.receipt_id)
        else None
    )
    if execution_id is not None:
        execution_id = _unique_node_id(execution_id, used_node_ids)
        nodes.append({"id": execution_id, "type": "execution_reference", "claims": {}})
        edges.append({"from": decision_id, "relation": "references", "to": execution_id})
    if receipt_id is not None:
        receipt_id = _unique_node_id(receipt_id, used_node_ids)
        nodes.append({"id": receipt_id, "type": "receipt_reference", "claims": {}})
        edges.append({"from": decision_id, "relation": "evidenced_by", "to": receipt_id})
    for audit_event_id in sorted(
        value for value in snapshot.audit_event_ids if _valid_identifier(value)
    ):
        node_id = _unique_node_id(_node_id("audit", audit_event_id), used_node_ids)
        nodes.append(
            {
                "id": node_id,
                "type": "audit_reference",
                "claims": {"audit_event_id": audit_event_id},
            }
        )
        edges.append({"from": decision_id, "relation": "evidenced_by", "to": node_id})


def _validate_permission_observation(
    observation: object,
    *,
    projection_reasons: set[str],
) -> None:
    if observation is None:
        projection_reasons.add("PDG_PERMISSION_OBSERVATION_MISSING")
        return
    if not isinstance(observation, PermissionObservation):
        projection_reasons.add("PDG_PERMISSION_OBSERVATION_INVALID")
        return
    if not _valid_identifier(observation.execution_actor_id):
        projection_reasons.add("PDG_EXECUTION_ACTOR_INVALID")
    if not _valid_identifier(observation.permission_name):
        projection_reasons.add("PDG_PERMISSION_NAME_INVALID")
    elif observation.permission_name != _CURRENT_EXECUTION_PERMISSION:
        projection_reasons.add("PDG_PERMISSION_NAME_MISMATCH")
    if type(observation.granted) is not bool:
        projection_reasons.add("PDG_PERMISSION_OUTCOME_INVALID")
    elif not observation.granted:
        projection_reasons.add("PDG_PERMISSION_DENIED")


def _permission_claims(observation: object) -> dict[str, Any]:
    if not isinstance(observation, PermissionObservation):
        return {}
    return {
        "execution_actor_id": observation.execution_actor_id,
        "granted": observation.granted,
        "permission_name": observation.permission_name,
    }


def _valid_policy_decision(policy: object) -> bool:
    return (
        isinstance(policy, ApprovalPolicyDecision)
        and _valid_identifier(policy.policy_version)
        and _valid_identifier(policy.profile)
        and _valid_identifier(policy.decision)
        and _valid_identifier(policy.authorization_mode)
        and type(policy.required_approvals) is int
        and policy.required_approvals > 0
        and isinstance(policy.required_permissions, tuple)
        and bool(policy.required_permissions)
        and all(_valid_identifier(value) for value in policy.required_permissions)
        and type(policy.distinct_approver_identities) is int
        and policy.distinct_approver_identities > 0
        and type(policy.requester_may_approve) is bool
        and type(policy.step_up_required) is bool
        and isinstance(policy.reason_codes, tuple)
        and bool(policy.reason_codes)
        and all(_valid_identifier(value) for value in policy.reason_codes)
    )


def _valid_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and 1 <= len(value) <= 256
        and "\x00" not in value
    )


def _node_id(kind: str, value: str | None) -> str:
    return f"{kind}:{value}" if _valid_identifier(value) else f"{kind}:missing"


def _unique_node_id(candidate: str, used_node_ids: set[str]) -> str:
    resolved = candidate
    duplicate_number = 2
    while resolved in used_node_ids:
        resolved = f"{candidate}#duplicate-{duplicate_number}"
        duplicate_number += 1
    used_node_ids.add(resolved)
    return resolved
