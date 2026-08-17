from __future__ import annotations

import hashlib

import pytest

from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_lease import ExecutionLease
from voodoo_product.precondition_witness import READ_THEN_COMPARE
from voodoo_product.runner_identity import (
    DENY_ALL_NETWORK_DEFAULT,
    READ_ONLY_EFFECT_CLASS,
    RunnerBoundary,
    RunnerBoundaryDenied,
    RunnerIdentity,
)

RUNNER_CLASS = "sandcloud.isolated-linux/v1"
ROOTFS_DIGEST = "1" * 64
RESOURCE_DIGEST = "2" * 64
NETWORK_DIGEST = "3" * 64
CAPSULE_ARTIFACT_DIGEST = "4" * 64


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_lease(
    *,
    runner_class: str = RUNNER_CLASS,
    environment: str = "local",
    capsule_digest: str,
) -> ExecutionLease:
    admission_id = "a" * 64
    execution_epoch = 1
    lease_id = digest(
        {
            "identity_type": "execution-lease-id/v1",
            "admission_id": admission_id,
            "execution_epoch": execution_epoch,
        }
    )
    claims = {
        "schema_version": 1,
        "lease_type": "execution-lease/v1",
        "lease_id": lease_id,
        "dispatch_id": "b" * 64,
        "admission_id": admission_id,
        "admission_digest": "c" * 64,
        "execution_id": "exec_phase_d_runner",
        "workspace_id": "wrk_main",
        "environment": environment,
        "execution_capsule_digest": capsule_digest,
        "runner_class": runner_class,
        "execution_epoch": execution_epoch,
        "acquired_at": "2026-08-17T06:30:00.000+00:00",
        "expires_at": "2026-08-17T06:31:00.000+00:00",
        "clock_witness_digest": "d" * 64,
        "lease_revision": "execution-lease/c4b-r1",
    }
    return ExecutionLease.from_dict({**claims, "lease_digest": digest(claims)})


def make_definition(*, effect_class: str = READ_ONLY_EFFECT_CLASS) -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability="github.read-ref/v1",
        target_kind="git_ref",
        binder_id="github-read-ref-binder/v1",
        handler_id="github-read-ref-handler/v1",
        effect_class=effect_class,
        verification_class="OBSERVE_ONLY",
        supported_environments=("local", "staging"),
        required_permissions=("execution.run",),
        production_eligible=False,
    )


def make_capsule(definition: CapabilityDefinition) -> ExecutionCapsule:
    return ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest="5" * 64,
        module_manifest_digest="6" * 64,
        artifact_kind="python-wheel",
        artifact_digest=CAPSULE_ARTIFACT_DIGEST,
        rootfs_digest=ROOTFS_DIGEST,
        dependency_lock_digest="7" * 64,
        sbom_digest="8" * 64,
        network_policy_digest=NETWORK_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        credential_class="github.read-only/v1",
        runner_class=RUNNER_CLASS,
        precondition_enforcement_class=READ_THEN_COMPARE,
        verification_class=definition.verification_class,
        verification_contract_identity="9" * 64,
        capsule_revision="execution-capsule/phase-d-r1",
    )


def make_identity(
    *,
    runner_class: str = RUNNER_CLASS,
    environment: str = "local",
    rootfs_digest: str = ROOTFS_DIGEST,
    resource_digest: str = RESOURCE_DIGEST,
    network_digest: str = NETWORK_DIGEST,
    provider_instance_id: str = "sandbox-session-001",
) -> RunnerIdentity:
    return RunnerIdentity.create(
        runner_class=runner_class,
        provider="sandcloud.reference/v1",
        provider_instance_id=provider_instance_id,
        environment=environment,
        rootfs_digest=rootfs_digest,
        resource_limit_profile_digest=resource_digest,
        network_policy_digest=network_digest,
        identity_revision="runner-identity/d1-r1",
    )


def make_chain(
    *,
    effect_class: str = READ_ONLY_EFFECT_CLASS,
) -> tuple[CapabilityDefinition, ExecutionCapsule, ExecutionLease, RunnerIdentity]:
    definition = make_definition(effect_class=effect_class)
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    identity = make_identity()
    return definition, capsule, lease, identity


def test_runner_identity_is_deterministic_and_round_trips() -> None:
    first = make_identity()
    second = make_identity()

    assert first.runner_id == second.runner_id
    assert first.identity_digest == second.identity_digest
    assert RunnerIdentity.from_dict(first.to_dict()) == first


def test_provider_instance_changes_logical_runner_identity() -> None:
    first = make_identity(provider_instance_id="sandbox-session-001")
    second = make_identity(provider_instance_id="sandbox-session-002")

    assert first.runner_id != second.runner_id
    assert first.identity_digest != second.identity_digest


def test_read_only_boundary_binds_exact_phase_d_chain() -> None:
    definition, capsule, lease, identity = make_chain()

    boundary = RunnerBoundary.create(
        identity=identity,
        lease=lease,
        capsule=capsule,
        definition=definition,
        boundary_revision="runner-boundary/d1-r1",
    )

    assert boundary.runner_id == identity.runner_id
    assert boundary.runner_identity_digest == identity.identity_digest
    assert boundary.lease_id == lease.lease_id
    assert boundary.lease_digest == lease.lease_digest
    assert boundary.execution_epoch == lease.execution_epoch
    assert boundary.execution_capsule_digest == capsule.capsule_digest
    assert boundary.capability_definition_identity == definition.definition_identity
    assert boundary.effect_ceiling == READ_ONLY_EFFECT_CLASS
    assert boundary.network_egress_default == DENY_ALL_NETWORK_DEFAULT
    assert boundary.provider_mutation_allowed is False
    assert RunnerBoundary.from_dict(boundary.to_dict()) == boundary


def test_mutating_capability_is_denied_at_phase_d_boundary() -> None:
    definition, capsule, lease, identity = make_chain(effect_class="FILESYSTEM_WRITE")

    with pytest.raises(RunnerBoundaryDenied) as denied:
        RunnerBoundary.create(
            identity=identity,
            lease=lease,
            capsule=capsule,
            definition=definition,
            boundary_revision="runner-boundary/d1-r1",
        )

    assert denied.value.reason == "PHASE_D_EFFECT_NOT_READ_ONLY"


def test_runner_class_mismatch_is_denied() -> None:
    definition, capsule, lease, _ = make_chain()
    identity = make_identity(runner_class="other.isolated-linux/v1")

    with pytest.raises(RunnerBoundaryDenied) as denied:
        RunnerBoundary.create(
            identity=identity,
            lease=lease,
            capsule=capsule,
            definition=definition,
            boundary_revision="runner-boundary/d1-r1",
        )

    assert denied.value.reason == "RUNNER_CLASS_MISMATCH"


def test_runner_environment_mismatch_is_denied() -> None:
    definition, capsule, lease, _ = make_chain()
    identity = make_identity(environment="staging")

    with pytest.raises(RunnerBoundaryDenied) as denied:
        RunnerBoundary.create(
            identity=identity,
            lease=lease,
            capsule=capsule,
            definition=definition,
            boundary_revision="runner-boundary/d1-r1",
        )

    assert denied.value.reason == "RUNNER_ENVIRONMENT_MISMATCH"


def test_runtime_profile_mismatch_is_denied() -> None:
    definition, capsule, lease, _ = make_chain()
    identity = make_identity(network_digest="e" * 64)

    with pytest.raises(RunnerBoundaryDenied) as denied:
        RunnerBoundary.create(
            identity=identity,
            lease=lease,
            capsule=capsule,
            definition=definition,
            boundary_revision="runner-boundary/d1-r1",
        )

    assert denied.value.reason == "RUNNER_NETWORK_POLICY_MISMATCH"


def test_capsule_digest_mismatch_is_denied() -> None:
    definition, capsule, _, identity = make_chain()
    lease = make_lease(capsule_digest="f" * 64)

    with pytest.raises(RunnerBoundaryDenied) as denied:
        RunnerBoundary.create(
            identity=identity,
            lease=lease,
            capsule=capsule,
            definition=definition,
            boundary_revision="runner-boundary/d1-r1",
        )

    assert denied.value.reason == "EXECUTION_CAPSULE_MISMATCH"


def test_identity_tamper_and_unknown_fields_are_rejected() -> None:
    identity = make_identity()
    tampered = identity.to_dict()
    tampered["provider_instance_id"] = "sandbox-session-tampered"

    with pytest.raises(ValueError, match="runner_id does not match"):
        RunnerIdentity.from_dict(tampered)

    unknown = identity.to_dict()
    unknown["ambient_token"] = "forbidden"
    with pytest.raises(ValueError, match="fields are invalid"):
        RunnerIdentity.from_dict(unknown)


def test_boundary_cannot_claim_provider_mutation() -> None:
    definition, capsule, lease, identity = make_chain()
    boundary = RunnerBoundary.create(
        identity=identity,
        lease=lease,
        capsule=capsule,
        definition=definition,
        boundary_revision="runner-boundary/d1-r1",
    )
    claims = boundary.to_dict()
    claims["provider_mutation_allowed"] = True
    claims_without_digest = {
        key: value for key, value in claims.items() if key != "boundary_digest"
    }
    claims["boundary_digest"] = digest(claims_without_digest)

    with pytest.raises(ValueError, match="provider mutation"):
        RunnerBoundary.from_dict(claims)
