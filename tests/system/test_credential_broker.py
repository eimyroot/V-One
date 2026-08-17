from __future__ import annotations

import hashlib

import pytest

from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.credential_broker import (
    READ_ONLY_ACCESS_MODE,
    CredentialAccessDecision,
    CredentialBroker,
    CredentialBrokerDenied,
    CredentialBrokerPolicy,
    ImmutableCredentialBroker,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_lease import ExecutionLease
from voodoo_product.precondition_witness import READ_THEN_COMPARE
from voodoo_product.runner_identity import RunnerBoundary, RunnerIdentity

RUNNER_CLASS = "sandcloud.isolated-linux/v1"
CREDENTIAL_CLASS = "github.read-only/v1"
ROOTFS_DIGEST = "1" * 64
RESOURCE_DIGEST = "2" * 64
NETWORK_DIGEST = "3" * 64


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_definition() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability="github.read-ref/v1",
        target_kind="git_ref",
        binder_id="github-read-ref-binder/v1",
        handler_id="github-read-ref-handler/v1",
        effect_class="READ_ONLY",
        verification_class="OBSERVE_ONLY",
        supported_environments=("local", "staging"),
        required_permissions=("execution.run",),
        production_eligible=False,
    )


def make_capsule(
    definition: CapabilityDefinition,
    *,
    credential_class: str = CREDENTIAL_CLASS,
) -> ExecutionCapsule:
    return ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest="4" * 64,
        module_manifest_digest="5" * 64,
        artifact_kind="python-wheel",
        artifact_digest="6" * 64,
        rootfs_digest=ROOTFS_DIGEST,
        dependency_lock_digest="7" * 64,
        sbom_digest="8" * 64,
        network_policy_digest=NETWORK_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        credential_class=credential_class,
        runner_class=RUNNER_CLASS,
        precondition_enforcement_class=READ_THEN_COMPARE,
        verification_class=definition.verification_class,
        verification_contract_identity="9" * 64,
        capsule_revision="execution-capsule/phase-d-r1",
    )


def make_lease(
    *,
    capsule_digest: str,
    epoch: int = 1,
    environment: str = "local",
) -> ExecutionLease:
    admission_id = "a" * 64
    lease_id = digest(
        {
            "identity_type": "execution-lease-id/v1",
            "admission_id": admission_id,
            "execution_epoch": epoch,
        }
    )
    minute = 30 + epoch - 1
    claims = {
        "schema_version": 1,
        "lease_type": "execution-lease/v1",
        "lease_id": lease_id,
        "dispatch_id": "b" * 64,
        "admission_id": admission_id,
        "admission_digest": "c" * 64,
        "execution_id": "exec_phase_d_credential",
        "workspace_id": "wrk_main",
        "environment": environment,
        "execution_capsule_digest": capsule_digest,
        "runner_class": RUNNER_CLASS,
        "execution_epoch": epoch,
        "acquired_at": f"2026-08-17T06:{minute:02d}:00.000+00:00",
        "expires_at": f"2026-08-17T06:{minute + 1:02d}:00.000+00:00",
        "clock_witness_digest": "d" * 64,
        "lease_revision": "execution-lease/c4b-r1",
    }
    return ExecutionLease.from_dict({**claims, "lease_digest": digest(claims)})


def make_boundary(
    *,
    credential_class: str = CREDENTIAL_CLASS,
    environment: str = "local",
) -> tuple[RunnerBoundary, ExecutionLease, CapabilityDefinition]:
    definition = make_definition()
    capsule = make_capsule(definition, credential_class=credential_class)
    lease = make_lease(capsule_digest=capsule.capsule_digest, environment=environment)
    identity = RunnerIdentity.create(
        runner_class=RUNNER_CLASS,
        provider="sandcloud.reference/v1",
        provider_instance_id="sandbox-session-001",
        environment=environment,
        rootfs_digest=ROOTFS_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
        identity_revision="runner-identity/d1-r1",
    )
    boundary = RunnerBoundary.create(
        identity=identity,
        lease=lease,
        capsule=capsule,
        definition=definition,
        boundary_revision="runner-boundary/d1-r1",
    )
    return boundary, lease, definition


def make_policy(
    definition: CapabilityDefinition,
    *,
    credential_class: str = CREDENTIAL_CLASS,
    capabilities: tuple[str, ...] | None = None,
    environments: tuple[str, ...] = ("local", "staging"),
) -> CredentialBrokerPolicy:
    return CredentialBrokerPolicy.create(
        credential_class=credential_class,
        provider="github",
        audience="api.github.com",
        allowed_capability_definition_identities=(
            capabilities if capabilities is not None else (definition.definition_identity,)
        ),
        enabled_environments=environments,
        policy_revision="credential-broker-policy/d2-r1",
    )


def test_policy_is_read_only_content_addressed_and_round_trips() -> None:
    _, _, definition = make_boundary()
    policy = make_policy(definition)

    assert policy.access_mode == READ_ONLY_ACCESS_MODE
    assert policy.provider_mutation_allowed is False
    assert CredentialBrokerPolicy.from_dict(policy.to_dict()) == policy


def test_broker_authorizes_exact_runner_lease_context() -> None:
    boundary, lease, definition = make_boundary()
    policy = make_policy(definition)
    broker = ImmutableCredentialBroker(
        policies=(policy,),
        decision_revision="credential-access-decision/d2-r1",
    )

    decision = broker.authorize(boundary=boundary, lease=lease)

    assert isinstance(broker, CredentialBroker)
    assert decision.runner_boundary_digest == boundary.boundary_digest
    assert decision.runner_id == boundary.runner_id
    assert decision.lease_id == lease.lease_id
    assert decision.lease_digest == lease.lease_digest
    assert decision.execution_epoch == lease.execution_epoch
    assert decision.credential_class == CREDENTIAL_CLASS
    assert decision.provider == "github"
    assert decision.audience == "api.github.com"
    assert decision.access_mode == READ_ONLY_ACCESS_MODE
    assert decision.provider_mutation_allowed is False
    assert decision.valid_from == lease.acquired_at
    assert decision.expires_at == lease.expires_at
    assert CredentialAccessDecision.from_dict(decision.to_dict()) == decision
    decision.assert_bound_to(boundary=boundary, lease=lease, policy=policy)


def test_repeated_authorization_is_deterministic_not_a_new_credential() -> None:
    boundary, lease, definition = make_boundary()
    broker = ImmutableCredentialBroker(
        policies=(make_policy(definition),),
        decision_revision="credential-access-decision/d2-r1",
    )

    first = broker.authorize(boundary=boundary, lease=lease)
    second = broker.authorize(boundary=boundary, lease=lease)

    assert first == second
    assert first.decision_id == second.decision_id
    assert first.decision_digest == second.decision_digest


def test_different_or_successor_lease_cannot_reuse_old_boundary() -> None:
    boundary, lease, definition = make_boundary()
    successor = make_lease(
        capsule_digest=boundary.execution_capsule_digest,
        epoch=lease.execution_epoch + 1,
    )
    broker = ImmutableCredentialBroker(
        policies=(make_policy(definition),),
        decision_revision="credential-access-decision/d2-r1",
    )

    with pytest.raises(CredentialBrokerDenied) as denied:
        broker.authorize(boundary=boundary, lease=successor)

    assert denied.value.reason == "CREDENTIAL_LEASE_BINDING_MISMATCH"


def test_unregistered_credential_class_fails_closed() -> None:
    boundary, lease, definition = make_boundary(credential_class="other.read-only/v1")
    broker = ImmutableCredentialBroker(
        policies=(make_policy(definition),),
        decision_revision="credential-access-decision/d2-r1",
    )

    with pytest.raises(CredentialBrokerDenied) as denied:
        broker.authorize(boundary=boundary, lease=lease)

    assert denied.value.reason == "CREDENTIAL_CLASS_NOT_REGISTERED"


def test_policy_cannot_authorize_unlisted_capability() -> None:
    boundary, lease, definition = make_boundary()
    policy = make_policy(definition, capabilities=("e" * 64,))
    broker = ImmutableCredentialBroker(
        policies=(policy,),
        decision_revision="credential-access-decision/d2-r1",
    )

    with pytest.raises(CredentialBrokerDenied) as denied:
        broker.authorize(boundary=boundary, lease=lease)

    assert denied.value.reason == "CREDENTIAL_CAPABILITY_NOT_ALLOWED"


def test_policy_cannot_authorize_unlisted_environment() -> None:
    boundary, lease, definition = make_boundary(environment="staging")
    broker = ImmutableCredentialBroker(
        policies=(make_policy(definition, environments=("local",)),),
        decision_revision="credential-access-decision/d2-r1",
    )

    with pytest.raises(CredentialBrokerDenied) as denied:
        broker.authorize(boundary=boundary, lease=lease)

    assert denied.value.reason == "CREDENTIAL_ENVIRONMENT_NOT_ALLOWED"


def test_policy_and_decision_cannot_claim_provider_mutation() -> None:
    _, _, definition = make_boundary()
    policy = make_policy(definition)
    policy_claims = policy.to_dict()
    policy_claims["provider_mutation_allowed"] = True
    policy_without_digest = {
        key: value for key, value in policy_claims.items() if key != "policy_digest"
    }
    policy_claims["policy_digest"] = digest(policy_without_digest)

    with pytest.raises(ValueError, match="cannot allow provider mutation"):
        CredentialBrokerPolicy.from_dict(policy_claims)


def test_secret_material_and_handles_are_not_valid_decision_fields() -> None:
    boundary, lease, definition = make_boundary()
    decision = ImmutableCredentialBroker(
        policies=(make_policy(definition),),
        decision_revision="credential-access-decision/d2-r1",
    ).authorize(boundary=boundary, lease=lease)

    serialized = decision.to_dict()
    forbidden = {
        "token",
        "secret",
        "credential",
        "credential_handle",
        "environment_variable",
        "authorization_header",
    }
    assert forbidden.isdisjoint(serialized)

    tampered = dict(serialized)
    tampered["token"] = "forbidden-secret-material"
    with pytest.raises(ValueError, match="fields are invalid"):
        CredentialAccessDecision.from_dict(tampered)
