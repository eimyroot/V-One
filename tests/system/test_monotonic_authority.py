from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from voodoo_product.authorization_snapshot import PAYLOAD_DIGEST_SCHEME, AuthorizationSnapshot
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import (
    ApprovalEvidenceSet,
    ApprovalRecord,
    ExecutionTarget,
)
from voodoo_product.monotonic_authority import (
    NARROW_OR_EQUAL,
    AuthorityConstraint,
    AuthorityScope,
    MonotonicAuthorityChecker,
    MonotonicAuthorityDecision,
    MonotonicAuthorityViolation,
)

REVIEW_DIGEST = "1" * 64
CAPABILITY_DEFINITION_IDENTITY = "2" * 64
POLICY_IDENTITY = "3" * 64
AUTHORIZED_AT = "2026-08-17T00:00:00.000+00:00"
VALID_UNTIL = "2026-08-17T00:10:00.000+00:00"


def _payload_digest(payload: dict[str, object]) -> str:
    binding = {
        "schema_version": 1,
        "binding_type": PAYLOAD_DIGEST_SCHEME,
        "payload": payload,
    }
    return hashlib.sha256(canonical_json(binding).encode("utf-8")).hexdigest()


def snapshot() -> AuthorizationSnapshot:
    payload = {"path": "proof/result.json", "replace": False}
    target = ExecutionTarget.create(
        target_kind="workspace_artifact",
        target_claims={"path": payload["path"]},
    )
    approvals = ApprovalEvidenceSet.create(
        request_id="cr_monotonic",
        payload_digest=_payload_digest(payload),
        target_digest=target.target_digest,
        capability="voodoo.write-artifact/v1",
        policy_version="approval-policy/current-v1",
        approvals=(
            ApprovalRecord(
                approval_id="appr_monotonic",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at="2026-08-16T23:59:00.000+00:00",
            ),
        ),
        approval_valid_until=VALID_UNTIL,
    )
    return AuthorizationSnapshot.create(
        snapshot_id="authz_monotonic",
        execution_id="exec_monotonic",
        request_id="cr_monotonic",
        review_content_sha256=REVIEW_DIGEST,
        actor_id="usr_operator",
        workspace_id="wrk_main",
        environment="local",
        capability=approvals.capability,
        capability_definition_identity=CAPABILITY_DEFINITION_IDENTITY,
        payload_digest=approvals.payload_digest,
        payload_digest_scheme=PAYLOAD_DIGEST_SCHEME,
        execution_target_identity=target.target_digest,
        policy_version=approvals.policy_version,
        policy_identity=POLICY_IDENTITY,
        approval_evidence_identity=approvals.approval_set_digest,
        issuance_timestamp_source_identity="clock_test",
        authorized_at=AUTHORIZED_AT,
        authorization_source_revision="snapshot-authority/r2",
        execution_target=target,
        approval_evidence=approvals,
    )


def constraint(
    scope: AuthorityScope,
    **changes: Any,
) -> AuthorityConstraint:
    values = {
        "parent_scope_digest": scope.scope_digest,
        "actor_id": scope.actor_id,
        "workspace_id": scope.workspace_id,
        "environment": scope.environment,
        "capability": scope.capability,
        "capability_definition_identity": scope.capability_definition_identity,
        "target_kind": scope.target_kind,
        "target_digest": scope.target_digest,
        "payload_digest": scope.payload_digest,
        "policy_version": scope.policy_version,
        "policy_identity": scope.policy_identity,
        "approval_set_digest": scope.approval_set_digest,
        "required_permission": scope.required_permission,
        "valid_from": scope.valid_from,
        "valid_until": scope.valid_until,
    }
    values.update(changes)
    return AuthorityConstraint.create(**values)


def test_scope_is_exact_content_addressed_projection_of_snapshot() -> None:
    parent_snapshot = snapshot()
    scope = AuthorityScope.from_snapshot(parent_snapshot)

    assert scope.authorization_snapshot_digest == parent_snapshot.snapshot_digest
    assert scope.actor_id == parent_snapshot.actor_id
    assert scope.workspace_id == parent_snapshot.workspace_id
    assert scope.environment == parent_snapshot.environment
    assert scope.capability == parent_snapshot.capability
    assert (
        scope.capability_definition_identity
        == parent_snapshot.capability_definition_identity
    )
    assert scope.target_kind == parent_snapshot.target_kind
    assert scope.target_digest == parent_snapshot.target_digest
    assert scope.payload_digest == parent_snapshot.payload_digest
    assert scope.policy_version == parent_snapshot.policy_version
    assert scope.policy_identity == parent_snapshot.policy_identity
    assert scope.approval_set_digest == parent_snapshot.approval_set_digest
    assert scope.valid_from == parent_snapshot.authorized_at
    assert scope.valid_until == parent_snapshot.approval_valid_until

    assert AuthorityScope.from_dict(scope.to_dict()) == scope


def test_equal_scope_is_allowed_and_decision_is_content_addressed() -> None:
    scope = AuthorityScope.from_snapshot(snapshot())
    child = AuthorityConstraint.from_scope(scope)

    decision = MonotonicAuthorityChecker.check(parent=scope, child=child)

    assert decision.relation == NARROW_OR_EQUAL
    assert decision.parent_scope_digest == scope.scope_digest
    assert decision.child_constraint_digest == child.constraint_digest
    assert MonotonicAuthorityDecision.from_dict(decision.to_dict()) == decision


def test_temporal_narrowing_is_allowed() -> None:
    scope = AuthorityScope.from_snapshot(snapshot())
    child = AuthorityConstraint.from_scope(
        scope,
        valid_from="2026-08-17T00:01:00.000+00:00",
        valid_until="2026-08-17T00:05:00.000+00:00",
    )

    decision = MonotonicAuthorityChecker.check(parent=scope, child=child)

    assert decision.relation == NARROW_OR_EQUAL


@pytest.mark.parametrize(
    ("field", "value", "reason_code"),
    [
        ("actor_id", "usr_other", "ACTOR_ID_WIDENING"),
        ("workspace_id", "wrk_other", "WORKSPACE_ID_WIDENING"),
        ("environment", "staging", "ENVIRONMENT_WIDENING"),
        ("capability", "voodoo.validate/v1", "CAPABILITY_WIDENING"),
        (
            "capability_definition_identity",
            "4" * 64,
            "CAPABILITY_DEFINITION_IDENTITY_WIDENING",
        ),
        ("target_kind", "other_target", "TARGET_KIND_WIDENING"),
        ("target_digest", "5" * 64, "TARGET_DIGEST_WIDENING"),
        ("payload_digest", "6" * 64, "PAYLOAD_DIGEST_WIDENING"),
        ("policy_version", "approval-policy/next-v1", "POLICY_VERSION_WIDENING"),
        ("policy_identity", "7" * 64, "POLICY_IDENTITY_WIDENING"),
        ("approval_set_digest", "8" * 64, "APPROVAL_SET_DIGEST_WIDENING"),
    ],
)
def test_security_binding_changes_are_denied(
    field: str,
    value: str,
    reason_code: str,
) -> None:
    scope = AuthorityScope.from_snapshot(snapshot())
    child = constraint(scope, **{field: value})

    with pytest.raises(MonotonicAuthorityViolation) as exc_info:
        MonotonicAuthorityChecker.check(parent=scope, child=child)

    assert reason_code in exc_info.value.reason_codes


def test_parent_binding_mismatch_is_denied() -> None:
    scope = AuthorityScope.from_snapshot(snapshot())
    child = constraint(scope, parent_scope_digest="9" * 64)

    with pytest.raises(MonotonicAuthorityViolation) as exc_info:
        MonotonicAuthorityChecker.check(parent=scope, child=child)

    assert "PARENT_SCOPE_BINDING_MISMATCH" in exc_info.value.reason_codes


@pytest.mark.parametrize(
    ("changes", "reason_code"),
    [
        (
            {"valid_from": "2026-08-16T23:59:59.999+00:00"},
            "VALID_FROM_WIDENING",
        ),
        (
            {"valid_until": "2026-08-17T00:10:00.001+00:00"},
            "VALID_UNTIL_WIDENING",
        ),
        (
            {
                "valid_from": "2026-08-17T00:11:00.000+00:00",
                "valid_until": "2026-08-17T00:12:00.000+00:00",
            },
            "CHILD_STARTS_AFTER_PARENT_EXPIRY",
        ),
    ],
)
def test_temporal_widening_or_stale_derivation_is_denied(
    changes: dict[str, str],
    reason_code: str,
) -> None:
    scope = AuthorityScope.from_snapshot(snapshot())
    child = constraint(scope, **changes)

    with pytest.raises(MonotonicAuthorityViolation) as exc_info:
        MonotonicAuthorityChecker.check(parent=scope, child=child)

    assert reason_code in exc_info.value.reason_codes


def test_reusable_or_different_permission_constraint_is_structurally_rejected() -> None:
    scope = AuthorityScope.from_snapshot(snapshot())

    reusable_values = constraint(scope).to_dict()
    reusable_values.pop("constraint_digest")
    reusable_values.pop("schema_version")
    reusable_values.pop("constraint_type")
    reusable_values["use_semantics"] = "REUSABLE"
    with pytest.raises(ValueError, match="ONE_TIME"):
        AuthorityConstraint.create(**reusable_values)

    values = constraint(scope).to_dict()
    values.pop("constraint_digest")
    values.pop("schema_version")
    values.pop("constraint_type")
    values["required_permission"] = "approval.review"
    with pytest.raises(ValueError, match="execution.run"):
        AuthorityConstraint.create(**values)


@pytest.mark.parametrize(
    ("factory", "digest_field"),
    [
        (lambda: AuthorityScope.from_snapshot(snapshot()).to_dict(), "scope_digest"),
        (
            lambda: AuthorityConstraint.from_scope(
                AuthorityScope.from_snapshot(snapshot())
            ).to_dict(),
            "constraint_digest",
        ),
    ],
)
def test_tampered_contract_digest_is_rejected(
    factory: Any,
    digest_field: str,
) -> None:
    value = factory()
    value[digest_field] = "f" * 64
    parser = (
        AuthorityScope.from_dict
        if digest_field == "scope_digest"
        else AuthorityConstraint.from_dict
    )
    with pytest.raises(ValueError, match="does not match"):
        parser(value)


def test_contract_parsers_reject_unknown_fields() -> None:
    scope_value = AuthorityScope.from_snapshot(snapshot()).to_dict()
    scope_value["unknown"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        AuthorityScope.from_dict(scope_value)

    constraint_value = AuthorityConstraint.from_scope(
        AuthorityScope.from_snapshot(snapshot())
    ).to_dict()
    constraint_value["unknown"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        AuthorityConstraint.from_dict(constraint_value)


def test_a9_is_not_runtime_wired() -> None:
    service_source = Path("voodoo_product/service.py").read_text(encoding="utf-8")
    execution_source = Path("voodoo_product/execution.py").read_text(encoding="utf-8")

    assert "MonotonicAuthorityChecker" not in service_source
    assert "MonotonicAuthorityChecker" not in execution_source
