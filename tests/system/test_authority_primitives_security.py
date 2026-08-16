from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from voodoo_product.approval_certificate import ApprovalCertificate
from voodoo_product.authority_witness import AuthorityWitnessSet
from voodoo_product.capability_registry import CapabilityActivation, CapabilityDefinition
from voodoo_product.execution_contract import ApprovalEvidenceSet, ApprovalRecord, ExecutionTarget
from voodoo_product.permission_authority import PermissionDecision, PermissionQuery
from voodoo_product.policy_authority import PolicyRevision
from voodoo_product.target_binding import TargetBinderRegistry
from voodoo_product.trusted_clock import ClockWitness


class ArtifactPathBinder:
    binder_id = "artifact-path/v1"
    target_kind = "artifact_path"

    def bind(self, *, approved_payload: dict[str, Any]) -> ExecutionTarget:
        return ExecutionTarget.create(
            target_kind=self.target_kind,
            target_claims={"path": approved_payload["path"], "replace": False},
        )


def policy() -> PolicyRevision:
    return PolicyRevision.create(
        policy_version="approval-policy.authority-r1",
        policy_package="v-one.approval",
        approval_validity_seconds=600,
        required_approvals_by_environment={
            "local": 1,
            "development": 1,
            "staging": 1,
            "production": 2,
        },
    )


def definition() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability="voodoo.write-artifact/v1",
        target_kind="artifact_path",
        binder_id="artifact-path/v1",
        handler_id="handler.write-artifact/v1",
        effect_class="FILESYSTEM_WRITE",
        verification_class="INDEPENDENT_READBACK_REQUIRED",
        supported_environments=("local",),
        required_permissions=("execution.run",),
        production_eligible=False,
    )


def permission(*, permission_name: str = "execution.run") -> PermissionDecision:
    return PermissionDecision.create(
        query=PermissionQuery(
            actor_id="usr_operator",
            workspace_id="wrk_main",
            environment="local",
            permission=permission_name,
        ),
        granted=True,
        reason="TEST_AUTHORITY",
        authority_revision="test-permission-authority/v1",
        scope_model="test/v1",
    )


def clock() -> ClockWitness:
    return ClockWitness.create(
        source_identity="server-clock/primary-v1",
        authority_revision="clock-policy/v1",
        environment="local",
        observed_at=datetime(2026, 8, 16, 1, 5, tzinfo=UTC),
    )


def test_capability_definition_requires_execution_run_permission() -> None:
    with pytest.raises(ValueError, match="must include execution.run"):
        CapabilityDefinition.create(
            capability="voodoo.write-artifact/v1",
            target_kind="artifact_path",
            binder_id="artifact-path/v1",
            handler_id="handler.write-artifact/v1",
            effect_class="FILESYSTEM_WRITE",
            verification_class="INDEPENDENT_READBACK_REQUIRED",
            supported_environments=("local",),
            required_permissions=("read",),
            production_eligible=False,
        )


def test_authority_witness_requires_execution_run_permission() -> None:
    policy_revision = policy()
    capability_definition = definition()
    activation = CapabilityActivation.create(
        capability_definition_identity=capability_definition.definition_identity,
        activation_generation=1,
        enabled_environments=("local",),
    )
    binding = TargetBinderRegistry({"artifact-path/v1": ArtifactPathBinder()}).bind(
        definition=capability_definition,
        approved_payload={"path": "proof/result.json"},
    )
    evidence = ApprovalEvidenceSet.create(
        request_id="cr_authority",
        payload_digest="a" * 64,
        target_digest=binding.target.target_digest,
        capability=capability_definition.capability,
        policy_version=policy_revision.policy_version,
        approvals=(
            ApprovalRecord(
                approval_id="appr_authority",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at="2026-08-16T01:00:00.000+00:00",
            ),
        ),
        approval_valid_until="2026-08-16T01:10:00.000+00:00",
    )
    certificate = ApprovalCertificate.create(
        review_content_sha256="b" * 64,
        policy_revision=policy_revision,
        approval_evidence=evidence,
    )

    with pytest.raises(PermissionError, match="requires execution.run"):
        AuthorityWitnessSet.create(
            permission_decision=permission(permission_name="read"),
            policy_revision=policy_revision,
            capability_definition=capability_definition,
            capability_activation=activation,
            target_binding=binding,
            approval_certificate=certificate,
            clock_witness=clock(),
            revocation_epoch=1,
        )


def test_authority_witness_rejects_approval_capability_mismatch() -> None:
    policy_revision = policy()
    capability_definition = definition()
    activation = CapabilityActivation.create(
        capability_definition_identity=capability_definition.definition_identity,
        activation_generation=1,
        enabled_environments=("local",),
    )
    binding = TargetBinderRegistry({"artifact-path/v1": ArtifactPathBinder()}).bind(
        definition=capability_definition,
        approved_payload={"path": "proof/result.json"},
    )
    evidence = ApprovalEvidenceSet.create(
        request_id="cr_authority",
        payload_digest="a" * 64,
        target_digest=binding.target.target_digest,
        capability="voodoo.other/v1",
        policy_version=policy_revision.policy_version,
        approvals=(
            ApprovalRecord(
                approval_id="appr_authority",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at="2026-08-16T01:00:00.000+00:00",
            ),
        ),
        approval_valid_until="2026-08-16T01:10:00.000+00:00",
    )
    certificate = ApprovalCertificate.create(
        review_content_sha256="b" * 64,
        policy_revision=policy_revision,
        approval_evidence=evidence,
    )

    with pytest.raises(ValueError, match="capability mismatch"):
        AuthorityWitnessSet.create(
            permission_decision=permission(),
            policy_revision=policy_revision,
            capability_definition=capability_definition,
            capability_activation=activation,
            target_binding=binding,
            approval_certificate=certificate,
            clock_witness=clock(),
            revocation_epoch=1,
        )
