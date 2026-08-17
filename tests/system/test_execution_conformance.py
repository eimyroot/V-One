from __future__ import annotations

import inspect

import pytest

from voodoo_product.authoritative_grant import ExecutionGrantV2
from voodoo_product.capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from voodoo_product.execution_capsule import (
    CapsuleActivation,
    ExecutionCapsule,
    ImmutableExecutionCapsuleRegistry,
)
from voodoo_product.execution_conformance import (
    ExecutionConformanceAuthority,
    ExecutionConformanceDenied,
    ExecutionConformanceWitness,
    HandlerConformanceEvidence,
    ImmutableHandlerConformanceRegistry,
)
from voodoo_product.precondition_witness import (
    ATOMIC_PROVIDER_CONDITION,
    READ_THEN_COMPARE,
)
from voodoo_product.service import ProductService

CAPABILITY = "voodoo.write-artifact/v1"
TARGET_KIND = "git_ref"
HANDLER_ID = "git-ref-writer/v1"
RUNNER_CLASS = "sandcloud.isolated-linux/v1"
CREDENTIAL_CLASS = "github.ref-write/v1"
VERIFICATION_CLASS = "provider-read/v1"
POLICY_VERSION = "approval-policy/current-v1"

HANDLER_DIGEST = "1" * 64
MODULE_DIGEST = "2" * 64
ARTIFACT_DIGEST = "3" * 64
ROOTFS_DIGEST = "4" * 64
LOCK_DIGEST = "5" * 64
SBOM_DIGEST = "6" * 64
NETWORK_DIGEST = "7" * 64
RESOURCE_DIGEST = "8" * 64
VERIFICATION_CONTRACT_IDENTITY = "9" * 64
ATOMIC_CONDITION_CONTRACT_IDENTITY = "a" * 64
SNAPSHOT_DIGEST = "b" * 64
AUTHORITY_WITNESS_DIGEST = "c" * 64
AUTHORITY_EVENT_HASH = "d" * 64
PARENT_SCOPE_DIGEST = "e" * 64
AUTHORITY_CONSTRAINT_DIGEST = "f" * 64
MONOTONIC_DECISION_DIGEST = "0" * 64
TARGET_DIGEST = "1a" * 32
PAYLOAD_DIGEST = "2b" * 32
POLICY_IDENTITY = "3c" * 32
APPROVAL_SET_DIGEST = "4d" * 32
PRECONDITION_REQUIREMENT_DIGEST = "5e" * 32
PRECONDITION_EXPECTATION_DIGEST = "6f" * 32
PRECONDITION_OBSERVATION_DIGEST = "70" * 32
PRECONDITION_WITNESS_DIGEST = "81" * 32
EXECUTION_BINDING_DIGEST = "92" * 32


def _definition() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability=CAPABILITY,
        target_kind=TARGET_KIND,
        binder_id="git-ref-binder/v1",
        handler_id=HANDLER_ID,
        effect_class="write",
        verification_class=VERIFICATION_CLASS,
        supported_environments=("local", "production"),
        required_permissions=("execution.run",),
        production_eligible=True,
    )


def _capability_registry(
    *,
    revoked: bool = False,
) -> tuple[ImmutableCapabilityRegistry, CapabilityDefinition]:
    definition = _definition()
    activation = CapabilityActivation.create(
        capability_definition_identity=definition.definition_identity,
        activation_generation=1,
        enabled_environments=("local", "production"),
        revoked=revoked,
    )
    return (
        ImmutableCapabilityRegistry(
            definitions=(definition,),
            activations=(activation,),
        ),
        definition,
    )


def _capsule(
    definition: CapabilityDefinition,
    *,
    enforcement: str = READ_THEN_COMPARE,
    handler_digest: str = HANDLER_DIGEST,
) -> ExecutionCapsule:
    return ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=TARGET_KIND,
        handler_id=HANDLER_ID,
        handler_digest=handler_digest,
        module_manifest_digest=MODULE_DIGEST,
        artifact_kind="oci-image",
        artifact_digest=ARTIFACT_DIGEST,
        rootfs_digest=ROOTFS_DIGEST,
        dependency_lock_digest=LOCK_DIGEST,
        sbom_digest=SBOM_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        credential_class=CREDENTIAL_CLASS,
        runner_class=RUNNER_CLASS,
        precondition_enforcement_class=enforcement,
        verification_class=VERIFICATION_CLASS,
        verification_contract_identity=VERIFICATION_CONTRACT_IDENTITY,
        capsule_revision="capsule/git-ref-writer-r1",
    )


def _capsule_registry(
    *,
    enforcement: str = READ_THEN_COMPARE,
    capsule_revoked: bool = False,
    capability_revoked: bool = False,
) -> tuple[ImmutableExecutionCapsuleRegistry, ExecutionCapsule]:
    capability_registry, definition = _capability_registry(revoked=capability_revoked)
    capsule = _capsule(definition, enforcement=enforcement)
    activation = CapsuleActivation.create(
        execution_capsule_digest=capsule.capsule_digest,
        activation_generation=1,
        enabled_environments=("local", "production"),
        revoked=capsule_revoked,
        production_eligible=True,
    )
    return (
        ImmutableExecutionCapsuleRegistry(
            capability_registry=capability_registry,
            capsules=(capsule,),
            activations=(activation,),
        ),
        capsule,
    )


def _handler_evidence(
    capsule: ExecutionCapsule,
    *,
    atomic_contract: str | None = None,
) -> HandlerConformanceEvidence:
    return HandlerConformanceEvidence.create(
        capability_definition_identity=capsule.capability_definition_identity,
        execution_capsule_digest=capsule.capsule_digest,
        handler_id=capsule.handler_id,
        handler_digest=capsule.handler_digest,
        runner_class=capsule.runner_class,
        credential_class=capsule.credential_class,
        precondition_enforcement_class=capsule.precondition_enforcement_class,
        verification_contract_identity=capsule.verification_contract_identity,
        atomic_provider_condition_contract_identity=atomic_contract,
        evidence_revision="handler-conformance/git-ref-writer-r1",
    )


def _authority(
    registry: ImmutableExecutionCapsuleRegistry,
    capsule: ExecutionCapsule,
    *,
    atomic_contract: str | None = None,
) -> ExecutionConformanceAuthority:
    evidence = _handler_evidence(capsule, atomic_contract=atomic_contract)
    handler_registry = ImmutableHandlerConformanceRegistry(
        capsule_registry=registry,
        evidence=(evidence,),
    )
    return ExecutionConformanceAuthority(
        capsule_registry=registry,
        handler_registry=handler_registry,
        authority_revision="execution-conformance/r1",
    )


def _grant(
    capsule: ExecutionCapsule,
    *,
    capsule_digest: str | None = None,
    runner_class: str | None = None,
    enforcement: str | None = None,
) -> ExecutionGrantV2:
    return ExecutionGrantV2._issue(
        grant_id="grt_conformance",
        jti="jti_conformance",
        execution_id="exec_conformance",
        request_id="cr_conformance",
        authorization_snapshot_digest=SNAPSHOT_DIGEST,
        snapshot_authority_witness_set_digest=AUTHORITY_WITNESS_DIGEST,
        snapshot_authority_event_hash=AUTHORITY_EVENT_HASH,
        parent_scope_digest=PARENT_SCOPE_DIGEST,
        authority_constraint_digest=AUTHORITY_CONSTRAINT_DIGEST,
        monotonic_authority_decision_digest=MONOTONIC_DECISION_DIGEST,
        actor_id="usr_operator",
        workspace_id="wrk_main",
        environment="local",
        capability=CAPABILITY,
        capability_definition_identity=capsule.capability_definition_identity,
        target_kind=TARGET_KIND,
        target_digest=TARGET_DIGEST,
        payload_digest=PAYLOAD_DIGEST,
        policy_version=POLICY_VERSION,
        policy_identity=POLICY_IDENTITY,
        approval_set_digest=APPROVAL_SET_DIGEST,
        required_permission="execution.run",
        precondition_requirement_digest=PRECONDITION_REQUIREMENT_DIGEST,
        precondition_expectation_digest=PRECONDITION_EXPECTATION_DIGEST,
        precondition_observation_digest=PRECONDITION_OBSERVATION_DIGEST,
        precondition_witness_digest=PRECONDITION_WITNESS_DIGEST,
        precondition_enforcement_class=(
            enforcement or capsule.precondition_enforcement_class
        ),
        precondition_checked_at="2026-08-17T00:00:00.000+00:00",
        execution_binding_digest=EXECUTION_BINDING_DIGEST,
        execution_capsule_digest=capsule_digest or capsule.capsule_digest,
        runner_class=runner_class or capsule.runner_class,
        execution_binding_authority_revision="execution-binding/r1",
        issued_at="2026-08-17T00:00:01.000+00:00",
        expires_at="2026-08-17T00:01:01.000+00:00",
        revocation_epoch=4,
        use_semantics="ONE_TIME",
        issuer_identity="grant-issuer/main",
        issuer_revision="grant-issuer/r1",
    )


def test_exact_grant_capsule_handler_conformance_emits_witness() -> None:
    registry, capsule = _capsule_registry()
    authority = _authority(registry, capsule)
    grant = _grant(capsule)

    witness = authority.evaluate(grant=grant)

    assert witness.grant_digest == grant.grant_digest
    assert witness.execution_binding_digest == grant.execution_binding_digest
    assert witness.execution_capsule_digest == capsule.capsule_digest
    assert witness.runner_class == capsule.runner_class
    assert witness.handler_digest == capsule.handler_digest
    assert witness.credential_class == capsule.credential_class
    assert witness.precondition_enforcement_class == READ_THEN_COMPARE
    assert witness.atomic_provider_condition_contract_identity is None
    assert (
        ExecutionConformanceWitness.from_dict(witness.to_dict()).witness_digest
        == witness.witness_digest
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"capsule_digest": "f" * 64}, "GRANT_CAPSULE_BINDING_MISMATCH"),
        ({"runner_class": "sandcloud.other/v1"}, "GRANT_CAPSULE_BINDING_MISMATCH"),
        (
            {"enforcement": ATOMIC_PROVIDER_CONDITION},
            "GRANT_CAPSULE_BINDING_MISMATCH",
        ),
    ),
)
def test_grant_cannot_widen_or_drift_from_capsule(
    override: dict[str, str],
    reason: str,
) -> None:
    registry, capsule = _capsule_registry()
    authority = _authority(registry, capsule)
    grant = _grant(capsule, **override)

    with pytest.raises(ExecutionConformanceDenied, match=reason):
        authority.evaluate(grant=grant)


def test_atomic_provider_condition_requires_handler_contract() -> None:
    registry, capsule = _capsule_registry(enforcement=ATOMIC_PROVIDER_CONDITION)

    with pytest.raises(
        ValueError,
        match="atomic_provider_condition_contract_identity",
    ):
        _handler_evidence(capsule)

    authority = _authority(
        registry,
        capsule,
        atomic_contract=ATOMIC_CONDITION_CONTRACT_IDENTITY,
    )
    witness = authority.evaluate(grant=_grant(capsule))

    assert witness.precondition_enforcement_class == ATOMIC_PROVIDER_CONDITION
    assert (
        witness.atomic_provider_condition_contract_identity
        == ATOMIC_CONDITION_CONTRACT_IDENTITY
    )


def test_read_then_compare_cannot_claim_atomic_provider_contract() -> None:
    _, capsule = _capsule_registry()

    with pytest.raises(
        ValueError,
        match="forbidden for read-then-compare",
    ):
        _handler_evidence(
            capsule,
            atomic_contract=ATOMIC_CONDITION_CONTRACT_IDENTITY,
        )


def test_handler_evidence_must_match_exact_capsule_handler() -> None:
    registry, capsule = _capsule_registry()
    evidence = HandlerConformanceEvidence.create(
        capability_definition_identity=capsule.capability_definition_identity,
        execution_capsule_digest=capsule.capsule_digest,
        handler_id=capsule.handler_id,
        handler_digest="f" * 64,
        runner_class=capsule.runner_class,
        credential_class=capsule.credential_class,
        precondition_enforcement_class=capsule.precondition_enforcement_class,
        verification_contract_identity=capsule.verification_contract_identity,
        atomic_provider_condition_contract_identity=None,
        evidence_revision="handler-conformance/tampered-r1",
    )

    with pytest.raises(ValueError, match="does not match capsule"):
        ImmutableHandlerConformanceRegistry(
            capsule_registry=registry,
            evidence=(evidence,),
        )


@pytest.mark.parametrize(
    ("capsule_revoked", "capability_revoked"),
    ((True, False), (False, True)),
)
def test_revoked_execution_contract_is_not_conformant(
    capsule_revoked: bool,
    capability_revoked: bool,
) -> None:
    registry, capsule = _capsule_registry(
        capsule_revoked=capsule_revoked,
        capability_revoked=capability_revoked,
    )
    authority = _authority(registry, capsule)

    with pytest.raises(
        ExecutionConformanceDenied,
        match="CAPSULE_NOT_EXECUTION_ELIGIBLE",
    ):
        authority.evaluate(grant=_grant(capsule))


def test_handler_evidence_round_trip_rejects_unknown_or_tampered_fields() -> None:
    _, capsule = _capsule_registry()
    evidence = _handler_evidence(capsule)
    round_trip = HandlerConformanceEvidence.from_dict(evidence.to_dict())
    assert round_trip.evidence_digest == evidence.evidence_digest

    unknown = {**evidence.to_dict(), "unexpected": True}
    with pytest.raises(ValueError, match="fields are invalid"):
        HandlerConformanceEvidence.from_dict(unknown)

    tampered = {**evidence.to_dict(), "handler_digest": "f" * 64}
    with pytest.raises(ValueError, match="evidence_digest does not match"):
        HandlerConformanceEvidence.from_dict(tampered)


def test_conformance_witness_tamper_is_rejected() -> None:
    registry, capsule = _capsule_registry()
    witness = _authority(registry, capsule).evaluate(grant=_grant(capsule))
    tampered = {**witness.to_dict(), "credential_class": "github.admin/v1"}

    with pytest.raises(ValueError, match="witness_digest does not match"):
        ExecutionConformanceWitness.from_dict(tampered)


def test_b3_is_not_wired_into_current_product_runtime() -> None:
    source = inspect.getsource(ProductService)
    assert "ExecutionConformanceAuthority" not in source
    assert "ExecutionConformanceWitness" not in source
