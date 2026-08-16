from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from voodoo_product.approval_certificate import ApprovalCertificate
from voodoo_product.authority_witness import AuthorityWitnessSet
from voodoo_product.capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from voodoo_product.execution_contract import (
    ApprovalEvidenceSet,
    ApprovalRecord,
    ExecutionTarget,
)
from voodoo_product.permission_authority import (
    CurrentPrincipalPermissionAuthority,
    PermissionDecision,
    PermissionQuery,
)
from voodoo_product.policy_authority import ImmutablePolicyAuthority, PolicyRevision
from voodoo_product.security import Principal
from voodoo_product.target_binding import TargetBinderRegistry
from voodoo_product.trusted_clock import ClockWitness, TrustedClockAuthority

DIGEST_A = "a" * 64
REVIEW_DIGEST = "b" * 64
APPROVED_AT = "2026-08-16T01:00:00.000+00:00"
VALID_UNTIL = "2026-08-16T01:10:00.000+00:00"


class FixedClockSource:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def read(self) -> datetime:
        return self.value


class ArtifactPathBinder:
    binder_id = "artifact-path/v1"
    target_kind = "artifact_path"

    def bind(self, *, approved_payload: dict[str, Any]) -> ExecutionTarget:
        path = approved_payload.get("path")
        if not isinstance(path, str) or not path or path != path.strip():
            raise ValueError("approved artifact path is invalid")
        return ExecutionTarget.create(
            target_kind=self.target_kind,
            target_claims={"path": path, "replace": False},
        )


class WrongKindBinder:
    binder_id = "wrong-kind/v1"
    target_kind = "other_kind"

    def bind(self, *, approved_payload: dict[str, Any]) -> ExecutionTarget:
        return ExecutionTarget.create(
            target_kind=self.target_kind,
            target_claims={"value": approved_payload.get("path")},
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


def definition(*, production_eligible: bool = False) -> CapabilityDefinition:
    environments = ("local", "development", "staging")
    if production_eligible:
        environments += ("production",)
    return CapabilityDefinition.create(
        capability="voodoo.write-artifact/v1",
        target_kind="artifact_path",
        binder_id="artifact-path/v1",
        handler_id="handler.write-artifact/v1",
        effect_class="FILESYSTEM_WRITE",
        verification_class="INDEPENDENT_READBACK_REQUIRED",
        supported_environments=environments,
        required_permissions=("execution.run",),
        production_eligible=production_eligible,
    )


def activation(
    capability_definition: CapabilityDefinition,
    *,
    revoked: bool = False,
    environments: tuple[str, ...] = ("local",),
) -> CapabilityActivation:
    return CapabilityActivation.create(
        capability_definition_identity=capability_definition.definition_identity,
        activation_generation=1,
        enabled_environments=environments,
        revoked=revoked,
    )


def approval_evidence(
    *,
    target: ExecutionTarget,
    policy_revision: PolicyRevision,
) -> ApprovalEvidenceSet:
    return ApprovalEvidenceSet.create(
        request_id="cr_authority",
        payload_digest=DIGEST_A,
        target_digest=target.target_digest,
        capability="voodoo.write-artifact/v1",
        policy_version=policy_revision.policy_version,
        approvals=(
            ApprovalRecord(
                approval_id="appr_authority",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at=APPROVED_AT,
            ),
        ),
        approval_valid_until=VALID_UNTIL,
    )


def permission(*, actor_id: str = "usr_operator") -> PermissionDecision:
    principal = Principal(user_id="usr_operator", username="operator", role="operator")
    authority = CurrentPrincipalPermissionAuthority(
        principal=principal,
        authority_revision="role-permissions/current-v1",
    )
    return authority.decide(
        PermissionQuery(
            actor_id=actor_id,
            workspace_id="wrk_main",
            environment="local",
            permission="execution.run",
        )
    )


def test_policy_revision_is_content_addressed_and_registry_is_fail_closed() -> None:
    first = policy()
    second = policy()

    assert first == second
    assert first.required_approvals_for("production") == 2

    authority = ImmutablePolicyAuthority((first,))
    assert authority.resolve(first.policy_version) == first
    assert authority.resolve_identity(first.policy_identity) == first

    with pytest.raises(LookupError, match="policy revision not found"):
        authority.resolve("approval-policy.unknown-v1")


def test_current_permission_authority_records_scope_and_denies_actor_mismatch() -> None:
    allowed = permission()
    denied = permission(actor_id="usr_other")

    assert allowed.granted is True
    assert allowed.permission == "execution.run"
    assert allowed.scope_model == "current-global-role/v1"
    assert denied.granted is False
    assert denied.reason == "ACTOR_MISMATCH"
    assert allowed.decision_digest != denied.decision_digest


def test_capability_registry_requires_exact_activation_and_production_eligibility() -> None:
    capability_definition = definition()
    active = activation(capability_definition)
    registry = ImmutableCapabilityRegistry(
        definitions=(capability_definition,),
        activations=(active,),
    )

    resolved_definition, resolved_activation = registry.resolve_for_execution(
        capability=capability_definition.capability,
        environment="local",
    )
    assert resolved_definition == capability_definition
    assert resolved_activation == active

    with pytest.raises(PermissionError, match="not active in environment"):
        registry.resolve_for_execution(
            capability=capability_definition.capability,
            environment="staging",
        )

    production_definition = definition(production_eligible=True)
    production_activation = activation(
        production_definition,
        environments=("production",),
    )
    production_registry = ImmutableCapabilityRegistry(
        definitions=(production_definition,),
        activations=(production_activation,),
    )
    assert production_registry.resolve_for_execution(
        capability=production_definition.capability,
        environment="production",
    )[0].production_eligible is True


def test_capability_registry_rejects_revoked_or_unknown_activation() -> None:
    capability_definition = definition()
    revoked = activation(capability_definition, revoked=True)
    registry = ImmutableCapabilityRegistry(
        definitions=(capability_definition,),
        activations=(revoked,),
    )

    with pytest.raises(PermissionError, match="revoked"):
        registry.resolve_for_execution(
            capability=capability_definition.capability,
            environment="local",
        )

    no_activation = ImmutableCapabilityRegistry(
        definitions=(capability_definition,),
        activations=(),
    )
    with pytest.raises(PermissionError, match="not activated"):
        no_activation.resolve_for_execution(
            capability=capability_definition.capability,
            environment="local",
        )


def test_target_binding_is_deterministic_and_bound_to_capability_definition() -> None:
    capability_definition = definition()
    registry = TargetBinderRegistry({"artifact-path/v1": ArtifactPathBinder()})

    first = registry.bind(
        definition=capability_definition,
        approved_payload={"path": "proof/result.json"},
    )
    second = registry.bind(
        definition=capability_definition,
        approved_payload={"path": "proof/result.json"},
    )

    assert first == second
    assert first.capability_definition_identity == capability_definition.definition_identity
    assert first.target.target_kind == capability_definition.target_kind

    with pytest.raises(LookupError, match="target binder not found"):
        TargetBinderRegistry({"wrong-kind/v1": WrongKindBinder()}).bind(
            definition=capability_definition,
            approved_payload={"path": "proof/result.json"},
        )


def test_approval_certificate_binds_exact_review_policy_and_approval_bytes() -> None:
    policy_revision = policy()
    target = ExecutionTarget.create(
        target_kind="artifact_path",
        target_claims={"path": "proof/result.json", "replace": False},
    )
    evidence = approval_evidence(target=target, policy_revision=policy_revision)

    first = ApprovalCertificate.create(
        review_content_sha256=REVIEW_DIGEST,
        policy_revision=policy_revision,
        approval_evidence=evidence,
    )
    second = ApprovalCertificate.create(
        review_content_sha256=REVIEW_DIGEST,
        policy_revision=policy_revision,
        approval_evidence=evidence,
    )
    assert first == second
    assert first.approval_set_digest == evidence.approval_set_digest

    other_policy = PolicyRevision.create(
        policy_version="approval-policy.other-v1",
        policy_package="v-one.approval",
        approval_validity_seconds=600,
        required_approvals_by_environment={
            "local": 1,
            "development": 1,
            "staging": 1,
            "production": 2,
        },
    )
    with pytest.raises(ValueError, match="does not use supplied policy revision"):
        ApprovalCertificate.create(
            review_content_sha256=REVIEW_DIGEST,
            policy_revision=other_policy,
            approval_evidence=evidence,
        )


def test_trusted_clock_emits_canonical_witness_and_fails_closed_on_naive_time() -> None:
    authority = TrustedClockAuthority(
        source_identity="server-clock/primary-v1",
        authority_revision="clock-policy/v1",
        source=FixedClockSource(datetime(2026, 8, 16, 1, 5, tzinfo=UTC)),
        allowed_environments=frozenset({"local", "staging"}),
    )
    witness = authority.witness(environment="local")

    assert witness.observed_at == "2026-08-16T01:05:00.000+00:00"
    assert witness.source_identity == "server-clock/primary-v1"

    with pytest.raises(PermissionError, match="not authorized"):
        authority.witness(environment="production")

    broken = TrustedClockAuthority(
        source_identity="server-clock/broken-v1",
        authority_revision="clock-policy/v1",
        source=FixedClockSource(datetime(2026, 8, 16, 1, 5)),
    )
    with pytest.raises(ValueError, match="naive"):
        broken.witness(environment="local")


def test_authority_witness_set_binds_every_authority_and_rejects_denial() -> None:
    policy_revision = policy()
    capability_definition = definition()
    capability_activation = activation(capability_definition)
    target_binding = TargetBinderRegistry(
        {"artifact-path/v1": ArtifactPathBinder()}
    ).bind(
        definition=capability_definition,
        approved_payload={"path": "proof/result.json"},
    )
    evidence = approval_evidence(
        target=target_binding.target,
        policy_revision=policy_revision,
    )
    certificate = ApprovalCertificate.create(
        review_content_sha256=REVIEW_DIGEST,
        policy_revision=policy_revision,
        approval_evidence=evidence,
    )
    clock = ClockWitness.create(
        source_identity="server-clock/primary-v1",
        authority_revision="clock-policy/v1",
        environment="local",
        observed_at=datetime(2026, 8, 16, 1, 5, tzinfo=UTC),
    )

    first = AuthorityWitnessSet.create(
        permission_decision=permission(),
        policy_revision=policy_revision,
        capability_definition=capability_definition,
        capability_activation=capability_activation,
        target_binding=target_binding,
        approval_certificate=certificate,
        clock_witness=clock,
        revocation_epoch=7,
    )
    second = AuthorityWitnessSet.create(
        permission_decision=permission(),
        policy_revision=policy_revision,
        capability_definition=capability_definition,
        capability_activation=capability_activation,
        target_binding=target_binding,
        approval_certificate=certificate,
        clock_witness=clock,
        revocation_epoch=7,
    )
    assert first == second

    with pytest.raises(PermissionError, match="permission decision is denied"):
        AuthorityWitnessSet.create(
            permission_decision=permission(actor_id="usr_other"),
            policy_revision=policy_revision,
            capability_definition=capability_definition,
            capability_activation=capability_activation,
            target_binding=target_binding,
            approval_certificate=certificate,
            clock_witness=clock,
            revocation_epoch=7,
        )
