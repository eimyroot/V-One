from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import (
    ApprovalEvidenceSet,
    ApprovalRecord,
    ExecutionGrant,
    ExecutionReceipt,
    ExecutionTarget,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
ISSUED_AT = "2026-07-31T12:00:00.000+00:00"
EXPIRES_AT = "2026-07-31T12:05:00.000+00:00"
APPROVAL_VALID_UNTIL = "2026-07-31T12:10:00.000+00:00"


def target(**changes: Any) -> ExecutionTarget:
    values = {
        "target_kind": "workspace_artifact",
        "target_claims": {"path": "proof/result.json", "replace": False},
    }
    values.update(changes)
    return ExecutionTarget.create(**values)


def approval_set(
    *,
    execution_target: ExecutionTarget | None = None,
    approvals: tuple[ApprovalRecord, ...] | None = None,
    **changes: Any,
) -> ApprovalEvidenceSet:
    resolved_target = execution_target or target()
    values = {
        "request_id": "cr_contract",
        "payload_digest": DIGEST_A,
        "target_digest": resolved_target.target_digest,
        "capability": "voodoo.write-artifact/v1",
        "policy_version": "approval-policy/current-v1",
        "approvals": approvals
        or (
            ApprovalRecord(
                approval_id="appr_2",
                approver_id="usr_reviewer_2",
                decision="APPROVED",
                approved_at="2026-07-31T11:59:01.000+00:00",
            ),
            ApprovalRecord(
                approval_id="appr_1",
                approver_id="usr_reviewer_1",
                decision="APPROVED",
                approved_at="2026-07-31T11:59:00.000+00:00",
            ),
        ),
        "approval_valid_until": APPROVAL_VALID_UNTIL,
    }
    values.update(changes)
    return ApprovalEvidenceSet.create(**values)


def grant(
    *,
    execution_target: ExecutionTarget | None = None,
    evidence: ApprovalEvidenceSet | None = None,
    **changes: Any,
) -> ExecutionGrant:
    resolved_target = execution_target or target()
    resolved_evidence = evidence or approval_set(execution_target=resolved_target)
    values = {
        "grant_id": "grant_contract",
        "execution_id": "exec_contract",
        "actor_id": "usr_operator",
        "workspace_id": "wrk_main",
        "environment": "local",
        "target": resolved_target,
        "approval_evidence": resolved_evidence,
        "issued_at": ISSUED_AT,
        "expires_at": EXPIRES_AT,
    }
    values.update(changes)
    return ExecutionGrant.create(**values)


def receipt(*, execution_grant: ExecutionGrant | None = None, **changes: Any) -> ExecutionReceipt:
    values = {
        "runner_receipt_id": "rrcp_contract",
        "grant": execution_grant or grant(),
        "runner_id": "runner_isolated_1",
        "status": "SUCCEEDED",
        "outcome": "EXPECTED_EFFECT_VERIFIED",
        "started_at": "2026-07-31T12:00:01.000+00:00",
        "completed_at": "2026-07-31T12:00:02.000+00:00",
        "output_digest": DIGEST_A,
        "postcondition_status": "PASSED",
        "postcondition_digest": DIGEST_B,
    }
    values.update(changes)
    return ExecutionReceipt.create(**values)


def recompute(value: dict[str, Any], digest_field: str) -> str:
    claims = {key: item for key, item in value.items() if key != digest_field}
    return hashlib.sha256(canonical_json(claims).encode("utf-8")).hexdigest()


def structurally_parse_with_recomputed_digest(
    value: dict[str, Any],
    *,
    parser: Any,
    digest_field: str,
) -> Any:
    value[digest_field] = recompute(value, digest_field)
    return parser(value)


def test_contract_digests_are_deterministic_and_exclude_only_their_digest() -> None:
    first_target = target()
    second_target = target(target_claims={"replace": False, "path": "proof/result.json"})
    assert first_target.to_dict() == second_target.to_dict()
    assert first_target.target_digest == recompute(first_target.to_dict(), "target_digest")

    first_approvals = approval_set(execution_target=first_target)
    second_approvals = approval_set(
        execution_target=second_target,
        approvals=tuple(reversed(first_approvals.approvals)),
    )
    assert first_approvals.to_dict() == second_approvals.to_dict()
    assert first_approvals.approval_set_digest == recompute(
        first_approvals.to_dict(),
        "approval_set_digest",
    )

    first_grant = grant(execution_target=first_target, evidence=first_approvals)
    second_grant = grant(execution_target=second_target, evidence=second_approvals)
    assert first_grant.to_dict() == second_grant.to_dict()
    assert first_grant.grant_digest == recompute(first_grant.to_dict(), "grant_digest")

    first_receipt = receipt(execution_grant=first_grant)
    second_receipt = receipt(execution_grant=second_grant)
    assert first_receipt.to_dict() == second_receipt.to_dict()
    assert first_receipt.receipt_digest == recompute(
        first_receipt.to_dict(),
        "receipt_digest",
    )


@pytest.mark.parametrize(
    ("contract", "parser"),
    [
        (lambda: target().to_dict(), ExecutionTarget.from_dict),
        (lambda: approval_set().to_dict(), ApprovalEvidenceSet.from_dict),
        (lambda: grant().to_dict(), ExecutionGrant.from_dict),
        (lambda: receipt().to_dict(), ExecutionReceipt.from_dict),
    ],
)
def test_strict_top_level_parsing_rejects_unknown_and_missing_fields(
    contract: Any,
    parser: Any,
) -> None:
    value = contract()
    value["unknown"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        parser(value)

    value = contract()
    value.pop(next(iter(value)))
    with pytest.raises(ValueError, match="fields are invalid"):
        parser(value)


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (lambda: target().to_dict(), "target_digest"),
        (lambda: approval_set().to_dict(), "payload_digest"),
        (lambda: grant().to_dict(), "grant_digest"),
        (lambda: receipt().to_dict(), "output_digest"),
    ],
)
def test_malformed_digests_are_rejected(factory: Any, field: str) -> None:
    value = factory()
    value[field] = "A" * 64
    parser = {
        "target_digest": ExecutionTarget.from_dict,
        "payload_digest": ApprovalEvidenceSet.from_dict,
        "grant_digest": ExecutionGrant.from_dict,
        "output_digest": ExecutionReceipt.from_dict,
    }[field]
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        parser(value)


@pytest.mark.parametrize(
    "changes",
    [
        {"target_claims": {"path": "other.json"}},
        {"target_kind": "validation_target"},
    ],
)
def test_target_digest_changes_for_security_relevant_bindings(changes: dict[str, Any]) -> None:
    assert target(**changes).target_digest != target().target_digest


def test_approval_set_digest_changes_for_every_binding() -> None:
    baseline = approval_set()
    changed_values = (
        approval_set(request_id="cr_other"),
        approval_set(payload_digest=DIGEST_B),
        approval_set(execution_target=target(target_claims={"path": "other.json"})),
        approval_set(capability="voodoo.validate/v1"),
        approval_set(policy_version="approval-policy.next-v1"),
        approval_set(
            approvals=(
                replace(baseline.approvals[0], approval_id="appr_other"),
                baseline.approvals[1],
            )
        ),
        approval_set(approval_valid_until="2026-07-31T12:09:00.000+00:00"),
    )
    assert all(
        item.approval_set_digest != baseline.approval_set_digest for item in changed_values
    )


def test_grant_digest_changes_for_every_direct_binding() -> None:
    baseline = grant()
    direct_changes = {
        "grant_id": "grant_other",
        "execution_id": "exec_other",
        "actor_id": "usr_other",
        "workspace_id": "wrk_other",
        "environment": "staging",
        "issued_at": "2026-07-31T12:00:01.000+00:00",
        "expires_at": "2026-07-31T12:04:59.000+00:00",
    }
    assert all(
        grant(**{field: value}).grant_digest != baseline.grant_digest
        for field, value in direct_changes.items()
    )
    changed_target = target(target_claims={"path": "other.json"})
    changed_approval = approval_set(execution_target=changed_target)
    assert (
        grant(execution_target=changed_target, evidence=changed_approval).grant_digest
        != baseline.grant_digest
    )
    changed_approval = approval_set(payload_digest=DIGEST_B)
    assert grant(evidence=changed_approval).grant_digest != baseline.grant_digest


def test_receipt_digest_changes_for_every_security_relevant_binding() -> None:
    baseline = receipt()
    baseline_claims = baseline.to_dict()
    changes = {
        "runner_receipt_id": "rrcp_other",
        "runner_id": "runner_other",
        "status": "FAILED",
        "outcome": "EXPECTED_EFFECT_NOT_VERIFIED",
        "started_at": "2026-07-31T12:00:00.500+00:00",
        "completed_at": "2026-07-31T12:00:03.000+00:00",
        "output_digest": DIGEST_B,
        "postcondition_status": "FAILED",
        "postcondition_digest": DIGEST_A,
    }
    assert all(
        recompute(baseline_claims | {field: value}, "receipt_digest")
        != baseline.receipt_digest
        for field, value in changes.items()
    )
    assert (
        receipt(execution_grant=grant(grant_id="grant_other")).receipt_digest
        != baseline.receipt_digest
    )


@pytest.mark.parametrize(
    ("issued_at", "expires_at", "message"),
    [
        (ISSUED_AT, ISSUED_AT, "positive"),
        (
            ISSUED_AT,
            "2026-07-31T12:05:00.001+00:00",
            "exceeds 300",
        ),
        ("2026-07-31T12:00:00", EXPIRES_AT, "timezone-aware"),
    ],
)
def test_grant_timestamp_and_ttl_validation(
    issued_at: str,
    expires_at: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        grant(issued_at=issued_at, expires_at=expires_at)


def test_grant_cannot_outlive_approval() -> None:
    evidence = approval_set(approval_valid_until="2026-07-31T12:04:59.999+00:00")
    with pytest.raises(ValueError, match="approval_valid_until"):
        grant(evidence=evidence)


def test_grant_cannot_be_issued_before_any_bound_approval() -> None:
    evidence = approval_set(
        approvals=(
            ApprovalRecord(
                approval_id="appr_future",
                approver_id="usr_future_reviewer",
                decision="APPROVED",
                approved_at="2026-07-31T12:00:01.000+00:00",
            ),
        )
    )
    with pytest.raises(ValueError, match="approval_causality"):
        grant(evidence=evidence)

    valid_after_approval = grant(
        evidence=evidence,
        issued_at="2026-07-31T12:00:02.000+00:00",
    )
    structurally_valid = valid_after_approval.to_dict()
    structurally_valid["issued_at"] = ISSUED_AT
    parsed = structurally_parse_with_recomputed_digest(
        structurally_valid,
        parser=ExecutionGrant.from_dict,
        digest_field="grant_digest",
    )
    with pytest.raises(ValueError, match="approval_causality"):
        parsed.validate_bindings(
            target=target(),
            approval_evidence=evidence,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("required_permission", "approval.review", "execution.run"),
        ("use_semantics", "REUSABLE", "ONE_TIME"),
    ],
)
def test_grant_permission_and_one_time_invariants(
    field: str,
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        grant(**{field: value})


def test_capability_syntax_is_validated_without_runtime_allowlisting() -> None:
    unknown_but_canonical = approval_set(capability="vendor.future-operation/v17")
    created = grant(evidence=unknown_but_canonical)
    assert created.capability == "vendor.future-operation/v17"
    with pytest.raises(ValueError, match="capability is invalid"):
        approval_set(capability="arbitrary shell command")


def test_approval_ordering_is_canonical_and_duplicate_identities_fail() -> None:
    evidence = approval_set()
    assert [item.approval_id for item in evidence.approvals] == ["appr_1", "appr_2"]
    duplicate = replace(evidence.approvals[1], approver_id=evidence.approvals[0].approver_id)
    with pytest.raises(ValueError, match="approver identities must be distinct"):
        approval_set(approvals=(evidence.approvals[0], duplicate))


def test_cross_contract_mismatches_fail_closed() -> None:
    execution_target = target()
    evidence = approval_set(execution_target=execution_target)
    execution_grant = grant(execution_target=execution_target, evidence=evidence)
    execution_grant.validate_bindings(
        target=execution_target,
        approval_evidence=evidence,
    )

    different_target = target(target_claims={"path": "other.json"})
    with pytest.raises(ValueError, match="cross-contract bindings mismatch"):
        execution_grant.validate_bindings(
            target=different_target,
            approval_evidence=evidence,
        )
    with pytest.raises(ValueError, match="cross-contract bindings mismatch"):
        execution_grant.validate_bindings(
            target=execution_target,
            approval_evidence=approval_set(payload_digest=DIGEST_B),
        )
    with pytest.raises(ValueError, match="approval_evidence.target_digest"):
        grant(execution_target=different_target, evidence=evidence)


def test_receipt_time_ordering_is_validated() -> None:
    with pytest.raises(ValueError, match="precedes"):
        receipt(
            started_at="2026-07-31T12:00:02.001+00:00",
            completed_at="2026-07-31T12:00:02.000+00:00",
        )


@pytest.mark.parametrize(
    ("started_at", "completed_at"),
    [
        (
            "2026-07-31T11:59:59.999+00:00",
            "2026-07-31T12:00:00.000+00:00",
        ),
        (
            "2026-07-31T12:05:00.001+00:00",
            "2026-07-31T12:05:01.000+00:00",
        ),
    ],
)
def test_attempted_execution_must_start_within_grant_validity(
    started_at: str,
    completed_at: str,
) -> None:
    with pytest.raises(ValueError, match="execution_start_grant_validity"):
        receipt(started_at=started_at, completed_at=completed_at)


@pytest.mark.parametrize(
    ("status", "outcome", "postcondition_status", "message"),
    [
        (
            "FAILED",
            "EXPECTED_EFFECT_VERIFIED",
            "PASSED",
            "requires status SUCCEEDED",
        ),
        (
            "SUCCEEDED",
            "EXPECTED_EFFECT_VERIFIED",
            "FAILED",
            "requires postcondition_status PASSED",
        ),
        (
            "SUCCEEDED",
            "EXPECTED_EFFECT_NOT_VERIFIED",
            "PASSED",
            "PASSED requires EXPECTED_EFFECT_VERIFIED",
        ),
        (
            "FAILED",
            "EXPECTED_EFFECT_NOT_VERIFIED",
            "NOT_RUN",
            "NOT_RUN requires status REJECTED",
        ),
        (
            "REJECTED",
            "INDETERMINATE",
            "NOT_RUN",
            "REJECTED requires",
        ),
        (
            "REJECTED",
            "EXPECTED_EFFECT_NOT_VERIFIED",
            "FAILED",
            "REJECTED requires",
        ),
        (
            "INTERRUPTED",
            "INDETERMINATE",
            "FAILED",
            "INDETERMINATE outcome requires",
        ),
        (
            "FAILED",
            "EXPECTED_EFFECT_NOT_VERIFIED",
            "INDETERMINATE",
            "indeterminate postcondition requires",
        ),
    ],
)
def test_receipt_result_contradictions_fail_closed(
    status: str,
    outcome: str,
    postcondition_status: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        receipt(
            status=status,
            outcome=outcome,
            postcondition_status=postcondition_status,
        )


def test_receipt_result_semantics_allow_only_consistent_evidence() -> None:
    assert receipt().outcome == "EXPECTED_EFFECT_VERIFIED"
    failed = receipt(
        status="FAILED",
        outcome="EXPECTED_EFFECT_NOT_VERIFIED",
        postcondition_status="FAILED",
    )
    assert failed.postcondition_status == "FAILED"
    interrupted = receipt(
        status="INTERRUPTED",
        outcome="INDETERMINATE",
        postcondition_status="INDETERMINATE",
    )
    assert interrupted.outcome == "INDETERMINATE"
    rejected = receipt(
        status="REJECTED",
        outcome="EXPECTED_EFFECT_NOT_VERIFIED",
        postcondition_status="NOT_RUN",
        started_at="2026-07-31T12:05:01.000+00:00",
        completed_at="2026-07-31T12:05:01.001+00:00",
    )
    assert rejected.postcondition_status == "NOT_RUN"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("grant_id", "grant_other"),
        ("grant_digest", DIGEST_B),
        ("execution_id", "exec_other"),
    ],
)
def test_receipt_consumer_validation_rejects_grant_identity_mismatch(
    field: str,
    value: str,
) -> None:
    execution_grant = grant()
    claims = receipt(execution_grant=execution_grant).to_dict()
    claims[field] = value
    parsed = structurally_parse_with_recomputed_digest(
        claims,
        parser=ExecutionReceipt.from_dict,
        digest_field="receipt_digest",
    )
    with pytest.raises(ValueError, match=field):
        parsed.validate_bindings(execution_grant)


def test_receipt_structural_parse_still_requires_authoritative_grant_validation() -> None:
    execution_grant = grant()
    claims = receipt(execution_grant=execution_grant).to_dict()
    claims["started_at"] = "2026-07-31T12:05:00.001+00:00"
    claims["completed_at"] = "2026-07-31T12:05:01.000+00:00"
    parsed = structurally_parse_with_recomputed_digest(
        claims,
        parser=ExecutionReceipt.from_dict,
        digest_field="receipt_digest",
    )
    with pytest.raises(ValueError, match="execution_start_grant_validity"):
        parsed.validate_bindings(execution_grant)


def test_grant_and_receipt_never_serialize_raw_payload_or_target_claims() -> None:
    raw_value = "raw-sensitive-request-value"
    execution_target = target(target_claims={"opaque": raw_value})
    evidence = approval_set(execution_target=execution_target)
    execution_grant = grant(execution_target=execution_target, evidence=evidence)
    execution_receipt = receipt(execution_grant=execution_grant)
    assert raw_value not in canonical_json(execution_grant.to_dict())
    assert raw_value not in canonical_json(execution_receipt.to_dict())
    assert "target_claims" not in execution_grant.to_dict()
    assert "payload" not in execution_grant.to_dict()
    assert "payload" not in execution_receipt.to_dict()


def test_runner_receipt_identity_is_not_v_one_ledger_entry_identity() -> None:
    value = receipt().to_dict()
    assert "runner_receipt_id" in value
    assert "receipt_id" not in value
    assert value["runner_receipt_id"].startswith("rrcp_")


def test_direct_parsing_round_trips_all_contracts() -> None:
    execution_target = target()
    evidence = approval_set(execution_target=execution_target)
    execution_grant = grant(execution_target=execution_target, evidence=evidence)
    execution_receipt = receipt(execution_grant=execution_grant)
    assert ExecutionTarget.from_dict(execution_target.to_dict()) == execution_target
    assert ApprovalEvidenceSet.from_dict(evidence.to_dict()) == evidence
    assert ExecutionGrant.from_dict(execution_grant.to_dict()) == execution_grant
    assert ExecutionReceipt.from_dict(execution_receipt.to_dict()) == execution_receipt


def test_timestamp_helper_inputs_are_stable_for_boundary_fixtures() -> None:
    issued = datetime.fromisoformat(ISSUED_AT)
    assert issued.tzinfo == UTC
    assert (issued + timedelta(seconds=300)).isoformat(timespec="milliseconds") == EXPIRES_AT
