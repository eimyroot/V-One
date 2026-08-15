from __future__ import annotations

import hashlib
from dataclasses import replace
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
    ExecutionGrant,
    ExecutionReceipt,
    ExecutionTarget,
)
from voodoo_product.operation_proof import (
    IndependentVerification,
    OperationProof,
    OperationProofError,
    VERIFIED,
)
from voodoo_product.operation_semantics import (
    MEMBER_ROLES,
    OperationMember,
    OperationSemantics,
    TechniqueEvidence,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64
AUTHORIZED_AT = "2026-08-12T12:05:00.000+00:00"
ISSUED_AT = "2026-08-12T12:05:01.000+00:00"
EXPIRES_AT = "2026-08-12T12:10:00.000+00:00"
VALID_UNTIL = "2026-08-12T12:15:00.000+00:00"


def semantics(**changes: Any) -> OperationSemantics:
    values = {
        "operation_id": "cr_snapshot",
        "capability": "voodoo.validate/v1",
        "members": tuple(
            OperationMember(role=role, member_id=f"id_{role}") for role in MEMBER_ROLES
        ),
        "techniques": tuple(
            TechniqueEvidence.from_name(name)
            for name in ("slsa", "mcp", "sigstore", "a2a", "aws_agentcore", "spiffe")
        ),
    }
    values.update(changes)
    return OperationSemantics.create(**values)


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
    approvals: tuple[ApprovalRecord, ...] | None = None,
) -> ApprovalEvidenceSet:
    resolved_target = execution_target or target()
    return ApprovalEvidenceSet.create(
        request_id="cr_snapshot",
        payload_digest=DIGEST_A,
        target_digest=resolved_target.target_digest,
        capability="voodoo.validate/v1",
        policy_version="approval-policy.test-v1",
        approvals=approvals
        or (
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
        "authorization_source_revision": "16d8c8d016b48b43e294de4ebb7577637191a18b",
        "execution_target": resolved_target,
        "approval_evidence": resolved_evidence,
    }
    values.update(changes)
    return AuthorizationSnapshot.create(**values)


def grant(
    *,
    execution_target: ExecutionTarget | None = None,
    evidence: ApprovalEvidenceSet | None = None,
    **changes: Any,
) -> ExecutionGrant:
    resolved_target = execution_target or target()
    resolved_evidence = evidence or approval_set(execution_target=resolved_target)
    values = {
        "grant_id": "grant_snapshot",
        "execution_id": "exec_snapshot",
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
        "runner_receipt_id": "rrcp_snapshot",
        "grant": execution_grant or grant(),
        "runner_id": "runner_isolated_1",
        "status": "SUCCEEDED",
        "outcome": "EXPECTED_EFFECT_VERIFIED",
        "started_at": "2026-08-12T12:05:02.000+00:00",
        "completed_at": "2026-08-12T12:05:03.000+00:00",
        "output_digest": DIGEST_C,
        "postcondition_status": "PASSED",
        "postcondition_digest": DIGEST_D,
    }
    values.update(changes)
    return ExecutionReceipt.create(**values)


def verification(
    *,
    execution_receipt: ExecutionReceipt | None = None,
    execution_target: ExecutionTarget | None = None,
    verdict: str = VERIFIED,
    **changes: Any,
) -> IndependentVerification:
    resolved_receipt = execution_receipt or receipt()
    resolved_target = execution_target or target()
    values = {
        "verifier_id": "verifier_external_1",
        "execution_id": resolved_receipt.execution_id,
        "target_digest": resolved_target.target_digest,
        "observed_output_digest": resolved_receipt.output_digest,
        "observed_postcondition_digest": resolved_receipt.postcondition_digest,
        "verdict": verdict,
        "checked_at": "2026-08-12T12:05:04.000+00:00",
        "evidence_digest": hashlib.sha256(b"provider-state").hexdigest(),
    }
    values.update(changes)
    return IndependentVerification.create(**values)


def operation_bundle() -> tuple[
    OperationSemantics,
    AuthorizationSnapshot,
    ExecutionGrant,
    ExecutionReceipt,
    IndependentVerification,
]:
    bound_target = target()
    evidence = approval_set(execution_target=bound_target)
    authz = snapshot(execution_target=bound_target, evidence=evidence)
    execution_grant = grant(execution_target=bound_target, evidence=evidence)
    execution_receipt = receipt(execution_grant=execution_grant)
    independent = verification(
        execution_receipt=execution_receipt,
        execution_target=bound_target,
    )
    return semantics(), authz, execution_grant, execution_receipt, independent


def digest_without(payload: dict[str, object], digest_field: str) -> str:
    return hashlib.sha256(
        canonical_json(
            {key: value for key, value in payload.items() if key != digest_field}
        ).encode("utf-8")
    ).hexdigest()


def test_operation_proof_digest_is_deterministic_and_round_trippable() -> None:
    op, authz, execution_grant, execution_receipt, independent = operation_bundle()
    proof = OperationProof.create(
        proof_id="proof_snapshot",
        semantics=op,
        snapshot=authz,
        grant=execution_grant,
        receipt=execution_receipt,
        verification=independent,
    )

    assert proof.final_verdict == VERIFIED
    assert proof.proof_digest == digest_without(proof.to_dict(), "proof_digest")
    assert OperationProof.from_dict(proof.to_dict()) == proof


def test_operation_proof_rejects_missing_snapshot_binding() -> None:
    op, authz, execution_grant, execution_receipt, independent = operation_bundle()
    other = semantics(operation_id="cr_other")

    with pytest.raises(OperationProofError, match="operation invariant mismatch"):
        OperationProof.create(
            proof_id="proof_snapshot",
            semantics=other,
            snapshot=authz,
            grant=execution_grant,
            receipt=execution_receipt,
            verification=independent,
        )

    assert op.semantics_digest != other.semantics_digest


def test_operation_proof_rejects_self_approval() -> None:
    bound_target = target()
    evidence = approval_set(
        execution_target=bound_target,
        approvals=(
            ApprovalRecord(
                approval_id="appr_self",
                approver_id="usr_operator",
                decision="APPROVED",
                approved_at="2026-08-12T12:00:00.000+00:00",
            ),
        ),
    )
    authz = snapshot(execution_target=bound_target, evidence=evidence)
    execution_grant = grant(execution_target=bound_target, evidence=evidence)
    execution_receipt = receipt(execution_grant=execution_grant)
    independent = verification(
        execution_receipt=execution_receipt,
        execution_target=bound_target,
    )

    with pytest.raises(OperationProofError, match="NoSelfApproval"):
        OperationProof.create(
            proof_id="proof_snapshot",
            semantics=semantics(),
            snapshot=authz,
            grant=execution_grant,
            receipt=execution_receipt,
            verification=independent,
        )


def test_operation_proof_rejects_target_substitution() -> None:
    op, authz, execution_grant, execution_receipt, independent = operation_bundle()
    substituted = verification(
        execution_receipt=execution_receipt,
        execution_target=target(target_claims={"path": "proof/other.json"}),
    )

    with pytest.raises(OperationProofError, match="target_digest"):
        OperationProof.create(
            proof_id="proof_snapshot",
            semantics=op,
            snapshot=authz,
            grant=execution_grant,
            receipt=execution_receipt,
            verification=substituted,
        )


def test_runner_success_without_independent_verification_is_not_accepted() -> None:
    op, authz, execution_grant, execution_receipt, independent = operation_bundle()
    failed_verification = replace(
        independent,
        verdict="NOT_VERIFIED",
        verification_digest=digest_without(
            {**independent.to_dict(), "verdict": "NOT_VERIFIED"},
            "verification_digest",
        ),
    )

    with pytest.raises(OperationProofError, match="independent verification"):
        OperationProof.create(
            proof_id="proof_snapshot",
            semantics=op,
            snapshot=authz,
            grant=execution_grant,
            receipt=execution_receipt,
            verification=failed_verification,
        )


def test_operation_proof_requires_distinct_verifier_from_runner_and_actor() -> None:
    op, authz, execution_grant, execution_receipt, independent = operation_bundle()
    same_as_runner = replace(
        independent,
        verifier_id=execution_receipt.runner_id,
        verification_digest=digest_without(
            {**independent.to_dict(), "verifier_id": execution_receipt.runner_id},
            "verification_digest",
        ),
    )
    with pytest.raises(OperationProofError, match="distinct verifier"):
        OperationProof.create(
            proof_id="proof_snapshot",
            semantics=op,
            snapshot=authz,
            grant=execution_grant,
            receipt=execution_receipt,
            verification=same_as_runner,
        )

    same_as_actor = replace(
        independent,
        verifier_id=execution_grant.actor_id,
        verification_digest=digest_without(
            {**independent.to_dict(), "verifier_id": execution_grant.actor_id},
            "verification_digest",
        ),
    )
    with pytest.raises(OperationProofError, match="actor cannot verify"):
        OperationProof.create(
            proof_id="proof_snapshot",
            semantics=op,
            snapshot=authz,
            grant=execution_grant,
            receipt=execution_receipt,
            verification=same_as_actor,
        )
