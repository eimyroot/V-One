from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from pathlib import Path

from voodoo_product.approval_policy import (
    ApprovalPolicyInput,
    evaluate_current_approval_policy,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.policy_decision_graph import (
    ApprovalEvidence,
    PermissionObservation,
    PolicyDecisionSnapshot,
    project_policy_decision_graph,
)

ROOT = Path(__file__).resolve().parents[2]


def payload_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def current_snapshot(
    *,
    environment: str = "local",
    approvals: tuple[ApprovalEvidence, ...] | None = None,
) -> PolicyDecisionSnapshot:
    policy = evaluate_current_approval_policy(
        ApprovalPolicyInput(environment=environment, risk="R1")
    )
    resolved_approvals = approvals
    if resolved_approvals is None:
        resolved_approvals = (
            ApprovalEvidence(
                approval_id="appr_1",
                approver_id="usr_approver",
                decision="APPROVED",
            ),
        )
        if environment == "production":
            resolved_approvals += (
                ApprovalEvidence(
                    approval_id="appr_2",
                    approver_id="usr_security",
                    decision="APPROVED",
                ),
            )
    return PolicyDecisionSnapshot(
        request_id="cr_1",
        requester_id="usr_requester",
        workspace_id="ws_1",
        workspace_environment=environment,
        request_environment=environment,
        risk="R1",
        adapter="echo",
        requested_capability="echo.execute",
        payload_sha256=payload_digest({"message": "bounded input"}),
        permission_observation=PermissionObservation(
            execution_actor_id="usr_operator",
            permission_name="execution.run",
            granted=True,
        ),
        policy_decision=policy,
        approvals=resolved_approvals,
        request_status="APPROVED",
        emergency_stop_active=False,
        production_effects_enabled=environment == "production",
    )


def graph_without_digest(graph: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in graph.items() if key != "graph_digest"}


def assert_unique_node_ids(graph: dict[str, object]) -> None:
    nodes = graph["nodes"]
    assert isinstance(nodes, list)
    node_ids = [node["id"] for node in nodes]
    assert len(node_ids) == len(set(node_ids))


def test_projection_is_deterministic_canonical_and_digest_bound() -> None:
    snapshot = current_snapshot()

    first = project_policy_decision_graph(snapshot)
    second = project_policy_decision_graph(snapshot)
    expected_digest = hashlib.sha256(
        canonical_json(graph_without_digest(first)).encode("utf-8")
    ).hexdigest()

    assert first == second
    assert canonical_json(first) == canonical_json(second)
    assert first["schema_version"] == 1
    assert first["graph_type"] == "policy-decision-graph/v1"
    assert first["graph_digest"] == expected_digest
    assert_unique_node_ids(first)


def test_changed_authoritative_input_changes_graph_digest() -> None:
    snapshot = current_snapshot()
    changed = replace(
        snapshot,
        payload_sha256=payload_digest({"message": "different bounded input"}),
    )

    first = project_policy_decision_graph(snapshot)
    second = project_policy_decision_graph(changed)

    assert first["graph_digest"] != second["graph_digest"]


def test_incomplete_snapshot_denies_by_default() -> None:
    graph = project_policy_decision_graph(PolicyDecisionSnapshot())

    assert graph["decision"] == "DENY"
    assert graph["execution_eligible"] is False
    assert "PDG_DENY_BY_DEFAULT" in graph["reason_codes"]
    assert "PDG_POLICY_DECISION_MISSING" in graph["reason_codes"]
    assert "PDG_PERMISSION_OBSERVATION_MISSING" in graph["reason_codes"]


def test_missing_permission_observation_denies() -> None:
    graph = project_policy_decision_graph(
        replace(current_snapshot(), permission_observation=None)
    )

    assert graph["decision"] == "DENY"
    assert "PDG_PERMISSION_OBSERVATION_MISSING" in graph["reason_codes"]


def test_permission_observation_binds_actor_name_and_outcome() -> None:
    snapshot = current_snapshot()
    baseline = project_policy_decision_graph(snapshot)
    assert baseline["decision"] == "ALLOW"

    assert snapshot.permission_observation is not None
    changed_actor = replace(
        snapshot,
        permission_observation=replace(
            snapshot.permission_observation,
            execution_actor_id="usr_alternate_operator",
        ),
    )
    changed_actor_graph = project_policy_decision_graph(changed_actor)
    assert changed_actor_graph["decision"] == "ALLOW"
    assert changed_actor_graph["graph_digest"] != baseline["graph_digest"]

    invalid_actor = replace(
        snapshot,
        permission_observation=replace(
            snapshot.permission_observation,
            execution_actor_id="",
        ),
    )
    mismatched_name = replace(
        snapshot,
        permission_observation=replace(
            snapshot.permission_observation,
            permission_name="approval.review",
        ),
    )
    denied_outcome = replace(
        snapshot,
        permission_observation=replace(
            snapshot.permission_observation,
            granted=False,
        ),
    )

    expected_reasons = (
        (invalid_actor, "PDG_EXECUTION_ACTOR_INVALID"),
        (mismatched_name, "PDG_PERMISSION_NAME_MISMATCH"),
        (denied_outcome, "PDG_PERMISSION_DENIED"),
    )
    for changed_snapshot, expected_reason in expected_reasons:
        graph = project_policy_decision_graph(changed_snapshot)
        assert graph["decision"] == "DENY"
        assert graph["execution_eligible"] is False
        assert graph["graph_digest"] != baseline["graph_digest"]
        assert expected_reason in graph["reason_codes"]


def test_requester_self_approval_denies() -> None:
    approval = ApprovalEvidence(
        approval_id="appr_self",
        approver_id="usr_requester",
        decision="APPROVED",
    )

    graph = project_policy_decision_graph(current_snapshot(approvals=(approval,)))

    assert graph["decision"] == "DENY"
    assert "PDG_REQUESTER_SELF_APPROVAL" in graph["reason_codes"]


def test_insufficient_approvals_deny() -> None:
    approval = ApprovalEvidence(
        approval_id="appr_1",
        approver_id="usr_approver",
        decision="APPROVED",
    )

    graph = project_policy_decision_graph(
        current_snapshot(environment="production", approvals=(approval,))
    )

    assert graph["decision"] == "DENY"
    assert "PDG_APPROVALS_INSUFFICIENT" in graph["reason_codes"]
    assert "PDG_DISTINCT_APPROVERS_INSUFFICIENT" in graph["reason_codes"]


def test_distinct_approval_requirement_denies_duplicate_approver() -> None:
    approvals = (
        ApprovalEvidence(
            approval_id="appr_1",
            approver_id="usr_approver",
            decision="APPROVED",
        ),
        ApprovalEvidence(
            approval_id="appr_2",
            approver_id="usr_approver",
            decision="APPROVED",
        ),
    )

    graph = project_policy_decision_graph(
        current_snapshot(environment="production", approvals=approvals)
    )

    assert graph["decision"] == "DENY"
    assert "PDG_APPROVALS_INSUFFICIENT" not in graph["reason_codes"]
    assert "PDG_DISTINCT_APPROVERS_INSUFFICIENT" in graph["reason_codes"]


def test_workspace_environment_mismatch_denies() -> None:
    graph = project_policy_decision_graph(
        replace(current_snapshot(), workspace_environment="staging")
    )

    assert graph["decision"] == "DENY"
    assert "PDG_WORKSPACE_ENVIRONMENT_MISMATCH" in graph["reason_codes"]


def test_non_approved_request_denies() -> None:
    graph = project_policy_decision_graph(
        replace(current_snapshot(), request_status="REVIEW_REQUIRED")
    )

    assert graph["decision"] == "DENY"
    assert "PDG_REQUEST_NOT_APPROVED" in graph["reason_codes"]


def test_emergency_stop_denies() -> None:
    graph = project_policy_decision_graph(
        replace(current_snapshot(), emergency_stop_active=True)
    )

    assert graph["decision"] == "DENY"
    assert "PDG_EMERGENCY_STOP_ACTIVE" in graph["reason_codes"]


def test_production_effects_disabled_denies_production_request() -> None:
    graph = project_policy_decision_graph(
        replace(
            current_snapshot(environment="production"),
            production_effects_enabled=False,
        )
    )

    assert graph["decision"] == "DENY"
    assert "PDG_PRODUCTION_EFFECTS_DISABLED" in graph["reason_codes"]


def test_policy_decision_must_match_current_snapshot_facts() -> None:
    local_policy = evaluate_current_approval_policy(
        ApprovalPolicyInput(environment="local", risk="R1")
    )
    snapshot = replace(
        current_snapshot(environment="production"),
        policy_decision=local_policy,
    )

    graph = project_policy_decision_graph(snapshot)

    assert graph["decision"] == "DENY"
    assert graph["execution_eligible"] is False
    assert "PDG_POLICY_DECISION_MISMATCH" in graph["reason_codes"]


def test_invalid_policy_decision_denies_instead_of_raising() -> None:
    snapshot = replace(
        current_snapshot(),
        policy_decision=object(),  # type: ignore[arg-type]
    )

    graph = project_policy_decision_graph(snapshot)

    assert graph["decision"] == "DENY"
    assert "PDG_POLICY_DECISION_INVALID" in graph["reason_codes"]


def test_current_compatible_snapshot_allows_projection() -> None:
    graph = project_policy_decision_graph(current_snapshot())

    assert graph["decision"] == "ALLOW"
    assert graph["execution_eligible"] is True
    assert "PDG_CURRENT_GATES_SATISFIED" in graph["reason_codes"]
    assert "PDG_DENY_BY_DEFAULT" not in graph["reason_codes"]
    assert_unique_node_ids(graph)


def test_requested_capability_is_descriptive_not_an_authorization_gate() -> None:
    baseline = project_policy_decision_graph(current_snapshot())
    descriptive_gap = project_policy_decision_graph(
        replace(
            current_snapshot(),
            adapter="caller-validated-adapter",
            requested_capability=None,
        )
    )

    assert baseline["decision"] == "ALLOW"
    assert descriptive_gap["decision"] == "ALLOW"
    assert descriptive_gap["graph_digest"] != baseline["graph_digest"]
    assert any(
        "Requested capability is descriptive" in limitation
        for limitation in descriptive_gap["limitations"]
    )


def test_future_assurance_gaps_are_limitations_not_denials() -> None:
    graph = project_policy_decision_graph(current_snapshot())

    assert graph["decision"] == "ALLOW"
    assert graph["limitations"] == sorted(graph["limitations"])
    assert any("payload digest" in limitation for limitation in graph["limitations"])
    assert any("policy version" in limitation for limitation in graph["limitations"])
    assert any("expiry" in limitation for limitation in graph["limitations"])
    assert not any("BINDING" in code for code in graph["reason_codes"])


def test_nodes_edges_and_reason_codes_are_stably_sorted() -> None:
    graph = project_policy_decision_graph(
        replace(
            current_snapshot(),
            audit_event_ids=("aud_z", "aud_a"),
            receipt_id="rcpt_1",
            execution_id="exec_1",
        )
    )

    nodes = graph["nodes"]
    edges = graph["edges"]
    assert nodes == sorted(
        nodes,
        key=lambda node: (node["type"], node["id"], canonical_json(node["claims"])),
    )
    assert edges == sorted(
        edges,
        key=lambda edge: (edge["from"], edge["relation"], edge["to"]),
    )
    assert graph["reason_codes"] == sorted(graph["reason_codes"])
    assert_unique_node_ids(graph)


def test_duplicate_audit_references_have_unique_node_ids() -> None:
    graph = project_policy_decision_graph(
        replace(current_snapshot(), audit_event_ids=("aud_1", "aud_1"))
    )
    audit_nodes = [
        node for node in graph["nodes"] if node["type"] == "audit_reference"
    ]

    assert graph["decision"] == "ALLOW"
    assert len(audit_nodes) == 2
    assert {node["claims"]["audit_event_id"] for node in audit_nodes} == {"aud_1"}
    assert_unique_node_ids(graph)


def test_duplicate_approval_ids_are_retained_and_deny_with_unique_nodes() -> None:
    approvals = (
        ApprovalEvidence(
            approval_id="appr_duplicate",
            approver_id="usr_approver_1",
            decision="APPROVED",
        ),
        ApprovalEvidence(
            approval_id="appr_duplicate",
            approver_id="usr_approver_2",
            decision="APPROVED",
        ),
    )

    graph = project_policy_decision_graph(current_snapshot(approvals=approvals))
    approval_nodes = [
        node for node in graph["nodes"] if node["type"] == "approval"
    ]

    assert graph["decision"] == "DENY"
    assert "PDG_APPROVAL_EVIDENCE_INVALID" in graph["reason_codes"]
    assert len(approval_nodes) == 2
    assert {
        node["claims"]["approval_id"] for node in approval_nodes
    } == {"appr_duplicate"}
    assert_unique_node_ids(graph)


def test_existing_policy_reason_codes_are_preserved_verbatim() -> None:
    snapshot = current_snapshot()
    graph = project_policy_decision_graph(snapshot)
    policy_node = next(node for node in graph["nodes"] if node["type"] == "policy")

    assert snapshot.policy_decision is not None
    assert policy_node["claims"]["reason_codes"] == list(
        snapshot.policy_decision.reason_codes
    )
    for reason_code in snapshot.policy_decision.reason_codes:
        assert reason_code in graph["reason_codes"]


def test_projection_does_not_mutate_input() -> None:
    snapshot = current_snapshot()
    before = copy.deepcopy(snapshot)

    project_policy_decision_graph(snapshot)

    assert snapshot == before


def test_optional_execution_receipt_and_audit_references_are_projected() -> None:
    snapshot = replace(
        current_snapshot(),
        execution_id="exec_1",
        receipt_id="rcpt_1",
        audit_event_ids=("aud_2", "aud_1"),
    )

    graph = project_policy_decision_graph(snapshot)
    node_ids = {node["id"] for node in graph["nodes"]}

    assert graph["decision"] == "ALLOW"
    assert {"execution:exec_1", "receipt:rcpt_1", "audit:aud_1", "audit:aud_2"} <= node_ids
    assert any(
        edge["to"] == "receipt:rcpt_1" and edge["relation"] == "evidenced_by"
        for edge in graph["edges"]
    )


def test_invalid_optional_reference_is_a_limitation_not_a_denial() -> None:
    graph = project_policy_decision_graph(
        replace(current_snapshot(), receipt_id="")
    )

    assert graph["decision"] == "ALLOW"
    assert "receipt:missing" not in {node["id"] for node in graph["nodes"]}
    assert any(
        "invalid optional evidence references" in limitation
        for limitation in graph["limitations"]
    )


def test_projection_has_no_runtime_or_cybercore_authority() -> None:
    source = (ROOT / "voodoo_product" / "policy_decision_graph.py").read_text(
        encoding="utf-8"
    )
    graph = project_policy_decision_graph(current_snapshot())
    projection_node = next(
        node for node in graph["nodes"] if node["type"] == "projection"
    )

    assert projection_node["claims"] == {"authority": "NONE", "projection_only": True}
    assert any("not authorization" in limitation for limitation in graph["limitations"])
    assert "CyberCore" not in source
    assert "execute_adapter" not in source
    assert "ProductDatabaseAdapter" not in source
    assert "ExecutionService" not in source
    assert "ChangeRequestService" not in source
    assert "VALID_ADAPTERS" not in source


def test_projection_does_not_expose_authorization_authority_semantics() -> None:
    graph = project_policy_decision_graph(current_snapshot())
    serialized = canonical_json(graph)

    assert graph["decision"] == "ALLOW"
    assert '"authority":"NONE"' in serialized
    assert not any(
        key in graph
        for key in (
            "authorization_grant",
            "authorized",
            "execute",
            "execution_grant",
        )
    )
