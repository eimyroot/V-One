from __future__ import annotations

import hashlib
from typing import Any

import pytest

from voodoo_product.authorization_snapshot import (
    PAYLOAD_DIGEST_SCHEME,
    AuthorizationSnapshot,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import (
    ApprovalEvidenceSet,
    ApprovalRecord,
    ExecutionTarget,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
AUTHORIZED_AT = "2026-08-12T12:05:00.000+00:00"
VALID_UNTIL = "2026-08-12T12:10:00.000+00:00"


def target(**changes: Any) -> ExecutionTarget:
    values = {
        "target_kind": "artifact_path",
        "target_claims": {"path": "proof/result.json", "replace": False},
    }
    values.update(changes)
    return ExecutionTarget.create(**values)


def approval_set(
    *,
    execution_target: ExecutionTarget | None = None,
    capability: str = "voodoo.validate/v1",
    payload_digest: str = DIGEST_A,
    policy_version: str = "approval-policy.test-v1",
) -> ApprovalEvidenceSet:
    resolved_target = execution_target or target()
    return ApprovalEvidenceSet.create(
        request_id="cr_snapshot",
        payload_digest=payload_digest,
        target_digest=resolved_target.target_digest,
        capability=capability,
        policy_version=policy_version,
        approvals=(
            ApprovalRecord(
                approval_id="appr_snapshot",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at="2026-08-12T12:00:00.000+00:00",
            ),
        ),
        approval_valid_until=VALID_UNTIL,
    )


def snapshot(
    *,
    execution_target: ExecutionTarget | None = None,
    evidence: ApprovalEvidenceSet | None = None,
    **changes: Any,
) -> AuthorizationSnapshot:
    resolved_target = execution_target or target()
    resolved_evidence = evidence or approval_set(execution_target=resolved_target)
    values = {
        "snapshot_id": "authz_snapshot",
        "execution_id": "exec_snapshot",
        "request_id": "cr_snapshot",
        "review_content_sha256": DIGEST_B,
        "actor_id": "usr_operator",
        "workspace_id": "wrk_main",
        "environment": "local",
        "capability": resolved_evidence.capability,
        "capability_definition_identity": hashlib.sha256(
            b"capability-definition-test"
        ).hexdigest(),
        "payload_digest": resolved_evidence.payload_digest,
        "payload_digest_scheme": PAYLOAD_DIGEST_SCHEME,
        "execution_target_identity": resolved_target.target_digest,
        "policy_version": resolved_evidence.policy_version,
        "policy_identity": hashlib.sha256(b"approval-policy-test").hexdigest(),
        "approval_evidence_identity": resolved_evidence.approval_set_digest,
        "issuance_timestamp_source_identity": "server-clock-policy.test-v1",
        "authorized_at": AUTHORIZED_AT,
        "authorization_source_revision": (
            "16d8c8d016b48b43e294de4ebb7577637191a18b"
        ),
        "execution_target": resolved_target,
        "approval_evidence": resolved_evidence,
    }
    values.update(changes)
    return AuthorizationSnapshot.create(**values)


def recompute(value: dict[str, Any]) -> str:
    claims = {key: item for key, item in value.items() if key != "snapshot_digest"}
    return hashlib.sha256(canonical_json(claims).encode("utf-8")).hexdigest()


def test_snapshot_digest_is_deterministic_and_binds_every_direct_security_field() -> None:
    baseline = snapshot()
    assert baseline.snapshot_digest == recompute(baseline.to_dict())
    assert snapshot().to_dict() == baseline.to_dict()

    changed = (
        snapshot(review_content_sha256="c" * 64),
        snapshot(actor_id="usr_other"),
        snapshot(workspace_id="wrk_other"),
        snapshot(environment="staging"),
        snapshot(capability_definition_identity="c" * 64),
        snapshot(policy_identity="d" * 64),
        snapshot(issuance_timestamp_source_identity="server-clock-policy.next-v1"),
        snapshot(authorization_source_revision="f" * 40),
    )
    assert all(item.snapshot_digest != baseline.snapshot_digest for item in changed)


def test_snapshot_round_trip_revalidates_exact_child_objects() -> None:
    original = snapshot()

    parsed = AuthorizationSnapshot.from_dict(
        original.to_dict(),
        execution_target=original.execution_target,
        approval_evidence=original.approval_evidence,
    )

    assert parsed == original
    assert parsed.execution_target_json == canonical_json(original.execution_target.to_dict())
    assert parsed.approval_evidence_json == canonical_json(
        original.approval_evidence.to_dict()
    )


def test_snapshot_rejects_cross_contract_mismatches() -> None:
    resolved_target = target()
    evidence = approval_set(execution_target=resolved_target)

    with pytest.raises(ValueError, match="cross-contract bindings mismatch"):
        snapshot(
            execution_target=resolved_target,
            evidence=evidence,
            request_id="cr_other",
        )

    with pytest.raises(ValueError, match="cross-contract bindings mismatch"):
        snapshot(
            execution_target=resolved_target,
            evidence=evidence,
            payload_digest="c" * 64,
        )

    different_target = target(target_claims={"path": "proof/other.json"})
    with pytest.raises(ValueError, match="cross-contract bindings mismatch"):
        snapshot(execution_target=different_target, evidence=evidence)


def test_snapshot_rejects_authorization_outside_approval_time_window() -> None:
    with pytest.raises(ValueError, match="after approval validity"):
        snapshot(authorized_at="2026-08-12T12:10:00.001+00:00")

    late_approval = ApprovalEvidenceSet.create(
        request_id="cr_snapshot",
        payload_digest=DIGEST_A,
        target_digest=target().target_digest,
        capability="voodoo.validate/v1",
        policy_version="approval-policy.test-v1",
        approvals=(
            ApprovalRecord(
                approval_id="appr_late",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at="2026-08-12T12:06:00.000+00:00",
            ),
        ),
        approval_valid_until=VALID_UNTIL,
    )
    with pytest.raises(ValueError, match="approval occurs after authorization"):
        snapshot(evidence=late_approval)


def test_idempotency_binding_excludes_generated_identity_and_authorization_time_only() -> None:
    baseline = snapshot()
    retry = snapshot(
        snapshot_id="authz_retry",
        execution_id="exec_retry",
        authorized_at="2026-08-12T12:05:01.000+00:00",
    )
    changed_policy = snapshot(policy_identity="e" * 64)

    assert retry.snapshot_digest != baseline.snapshot_digest
    assert retry.idempotency_binding_digest == baseline.idempotency_binding_digest
    assert changed_policy.idempotency_binding_digest != baseline.idempotency_binding_digest


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("review_content_sha256", "A" * 64, "lowercase SHA-256"),
        ("payload_digest", "short", "lowercase SHA-256"),
        ("payload_digest_scheme", "raw-json/v1", "unsupported"),
        ("environment", "unknown", "environment is invalid"),
    ],
)
def test_snapshot_rejects_malformed_direct_bindings(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        snapshot(**{field: value})


def test_parser_rejects_unknown_fields_and_tampered_snapshot_digest() -> None:
    original = snapshot()
    value = original.to_dict()
    value["unknown"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        AuthorizationSnapshot.from_dict(
            value,
            execution_target=original.execution_target,
            approval_evidence=original.approval_evidence,
        )

    value = original.to_dict()
    value["snapshot_digest"] = "f" * 64
    with pytest.raises(ValueError, match="snapshot_digest"):
        AuthorizationSnapshot.from_dict(
            value,
            execution_target=original.execution_target,
            approval_evidence=original.approval_evidence,
        )
