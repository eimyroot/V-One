from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.credential_broker import (
    CredentialBrokerPolicy,
    ImmutableCredentialBroker,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_lease import ExecutionLease
from voodoo_product.isolated_runner import (
    READ_ONLY_MOUNT_MODE,
    CurrentExecutionFence,
    IsolatedRunnerAdapter,
    IsolatedRunnerDenied,
    IsolatedRuntimeBootstrap,
    IsolatedRuntimeProvider,
    PreparedIsolatedRuntime,
    ReadOnlyRuntimeActivation,
)
from voodoo_product.precondition_witness import READ_THEN_COMPARE

RUNNER_CLASS = "caster-minal.isolated-linux/v1"
CREDENTIAL_CLASS = "github.read-only/v1"
ROOTFS_DIGEST = "1" * 64
RESOURCE_DIGEST = "2" * 64
NETWORK_DIGEST = "3" * 64
ACTIVATION_REVISION = "runtime-activation/d3-r1"


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_definition(*, effect_class: str = "READ_ONLY") -> CapabilityDefinition:
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
        handler_digest="4" * 64,
        module_manifest_digest="5" * 64,
        artifact_kind="python-wheel",
        artifact_digest="6" * 64,
        rootfs_digest=ROOTFS_DIGEST,
        dependency_lock_digest="7" * 64,
        sbom_digest="8" * 64,
        network_policy_digest=NETWORK_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        credential_class=CREDENTIAL_CLASS,
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
        "execution_id": "exec_phase_d_runtime",
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


def make_broker(definition: CapabilityDefinition) -> ImmutableCredentialBroker:
    policy = CredentialBrokerPolicy.create(
        credential_class=CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        allowed_capability_definition_identities=(definition.definition_identity,),
        enabled_environments=("local", "staging"),
        policy_revision="credential-broker-policy/d2-r1",
    )
    return ImmutableCredentialBroker(
        policies=(policy,),
        decision_revision="credential-access-decision/d2-r1",
    )


class RecordingFence:
    def __init__(self, events: list[str], *, deny: bool = False) -> None:
        self.events = events
        self.deny = deny

    def assert_current(self, *, lease: ExecutionLease) -> None:
        assert isinstance(lease, ExecutionLease)
        self.events.append("fence")
        if self.deny:
            raise IsolatedRunnerDenied("STALE_EXECUTION_EPOCH")


class RecordingProvider:
    def __init__(
        self,
        events: list[str],
        *,
        rootfs_digest: str = ROOTFS_DIGEST,
        activation_revision: str = ACTIVATION_REVISION,
    ) -> None:
        self.events = events
        self.rootfs_digest = rootfs_digest
        self.activation_revision = activation_revision

    def bootstrap(
        self,
        *,
        lease: ExecutionLease,
        capsule: ExecutionCapsule,
    ) -> IsolatedRuntimeBootstrap:
        self.events.append("bootstrap")
        return IsolatedRuntimeBootstrap.create(
            provider="caster-minal.reference/v1",
            provider_instance_id="isolated-session-001",
            runner_class=lease.runner_class,
            environment=lease.environment,
            rootfs_digest=self.rootfs_digest,
            resource_limit_profile_digest=capsule.resource_limit_profile_digest,
            network_policy_digest=capsule.network_policy_digest,
            bootstrap_revision="runtime-bootstrap/d3-r1",
        )

    def activate_read_only(
        self,
        *,
        prepared: PreparedIsolatedRuntime,
    ) -> ReadOnlyRuntimeActivation:
        self.events.append("activate")
        return ReadOnlyRuntimeActivation.create(
            bootstrap=prepared.bootstrap,
            identity=prepared.identity,
            boundary=prepared.boundary,
            decision=prepared.decision,
            lease=prepared.lease,
            activation_revision=self.activation_revision,
        )


def make_adapter(
    *,
    provider: RecordingProvider,
    fence: RecordingFence,
    definition: CapabilityDefinition,
) -> IsolatedRunnerAdapter:
    return IsolatedRunnerAdapter(
        provider=provider,
        credential_broker=make_broker(definition),
        current_fence=fence,
        identity_revision="runner-identity/d1-r1",
        boundary_revision="runner-boundary/d1-r1",
        activation_revision=ACTIVATION_REVISION,
    )


def test_prepare_bootstraps_credential_free_deny_all_runtime_and_binds_d1_d2() -> None:
    events: list[str] = []
    definition = make_definition()
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    provider = RecordingProvider(events)
    fence = RecordingFence(events)
    adapter = make_adapter(provider=provider, fence=fence, definition=definition)

    prepared = adapter.prepare(lease=lease, capsule=capsule, definition=definition)

    assert isinstance(provider, IsolatedRuntimeProvider)
    assert isinstance(fence, CurrentExecutionFence)
    assert events == ["bootstrap"]
    assert prepared.bootstrap.workspace_mount_mode == READ_ONLY_MOUNT_MODE
    assert prepared.bootstrap.network_egress_default == "DENY_ALL"
    assert prepared.bootstrap.inherited_credentials is False
    assert prepared.bootstrap.provider_mutation_allowed is False
    assert prepared.identity.provider_instance_id == "isolated-session-001"
    assert prepared.boundary.lease_id == lease.lease_id
    assert prepared.boundary.execution_epoch == lease.execution_epoch
    assert prepared.boundary.effect_ceiling == "READ_ONLY"
    assert prepared.decision.runner_boundary_digest == prepared.boundary.boundary_digest
    assert prepared.decision.access_mode == "READ_ONLY"
    assert prepared.decision.provider_mutation_allowed is False


def test_activate_rechecks_current_fence_immediately_before_provider_activation() -> None:
    events: list[str] = []
    definition = make_definition()
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    provider = RecordingProvider(events)
    adapter = make_adapter(
        provider=provider,
        fence=RecordingFence(events),
        definition=definition,
    )
    prepared = adapter.prepare(lease=lease, capsule=capsule, definition=definition)

    activation = adapter.activate(prepared=prepared)

    assert events == ["bootstrap", "fence", "activate"]
    assert activation.lease_id == lease.lease_id
    assert activation.execution_epoch == lease.execution_epoch
    assert activation.runner_boundary_digest == prepared.boundary.boundary_digest
    assert activation.credential_decision_digest == prepared.decision.decision_digest
    assert activation.workspace_mount_mode == "READ_ONLY"
    assert activation.network_egress_default == "DENY_ALL"
    assert activation.provider_mutation_allowed is False
    assert ReadOnlyRuntimeActivation.from_dict(activation.to_dict()) == activation


def test_stale_current_fence_denies_before_provider_activation() -> None:
    events: list[str] = []
    definition = make_definition()
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    provider = RecordingProvider(events)
    adapter = make_adapter(
        provider=provider,
        fence=RecordingFence(events, deny=True),
        definition=definition,
    )
    prepared = adapter.prepare(lease=lease, capsule=capsule, definition=definition)

    with pytest.raises(IsolatedRunnerDenied) as denied:
        adapter.activate(prepared=prepared)

    assert denied.value.reason == "STALE_EXECUTION_EPOCH"
    assert events == ["bootstrap", "fence"]


def test_bootstrap_profile_drift_fails_closed_before_identity_or_credentials() -> None:
    events: list[str] = []
    definition = make_definition()
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    provider = RecordingProvider(events, rootfs_digest="e" * 64)
    adapter = make_adapter(
        provider=provider,
        fence=RecordingFence(events),
        definition=definition,
    )

    with pytest.raises(IsolatedRunnerDenied) as denied:
        adapter.prepare(lease=lease, capsule=capsule, definition=definition)

    assert denied.value.reason == "RUNTIME_ROOTFS_MISMATCH"
    assert events == ["bootstrap"]


def test_mutating_capability_is_rejected_before_runtime_bootstrap() -> None:
    events: list[str] = []
    definition = make_definition(effect_class="REMOTE_WRITE")
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    provider = RecordingProvider(events)
    adapter = make_adapter(
        provider=provider,
        fence=RecordingFence(events),
        definition=definition,
    )

    with pytest.raises(IsolatedRunnerDenied) as denied:
        adapter.prepare(lease=lease, capsule=capsule, definition=definition)

    assert denied.value.reason == "PHASE_D_EFFECT_NOT_READ_ONLY"
    assert events == []


def test_provider_activation_claim_drift_is_rejected() -> None:
    events: list[str] = []
    definition = make_definition()
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    provider = RecordingProvider(events, activation_revision="runtime-activation/other")
    adapter = make_adapter(
        provider=provider,
        fence=RecordingFence(events),
        definition=definition,
    )
    prepared = adapter.prepare(lease=lease, capsule=capsule, definition=definition)

    with pytest.raises(IsolatedRunnerDenied) as denied:
        adapter.activate(prepared=prepared)

    assert denied.value.reason == "RUNTIME_ACTIVATION_BINDING_MISMATCH"
    assert events == ["bootstrap", "fence", "activate"]


def test_runtime_evidence_contracts_reject_secret_or_mutation_fields() -> None:
    bootstrap = IsolatedRuntimeBootstrap.create(
        provider="caster-minal.reference/v1",
        provider_instance_id="isolated-session-001",
        runner_class=RUNNER_CLASS,
        environment="local",
        rootfs_digest=ROOTFS_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
        bootstrap_revision="runtime-bootstrap/d3-r1",
    )
    assert IsolatedRuntimeBootstrap.from_dict(bootstrap.to_dict()) == bootstrap

    secret = dict(bootstrap.to_dict())
    secret["token"] = "forbidden"
    with pytest.raises(ValueError, match="fields are invalid"):
        IsolatedRuntimeBootstrap.from_dict(secret)

    inherited = dict(bootstrap.to_dict())
    inherited["inherited_credentials"] = True
    with pytest.raises(ValueError, match="cannot inherit credentials"):
        IsolatedRuntimeBootstrap.from_dict(inherited)


def test_new_d3_runtime_is_not_wired_into_legacy_execution_paths() -> None:
    service = Path("voodoo_product/service.py").read_text(encoding="utf-8")
    execution = Path("voodoo_product/execution.py").read_text(encoding="utf-8")

    forbidden = (
        "from .isolated_runner import",
        "from voodoo_product.isolated_runner import",
        "IsolatedRunnerAdapter",
        "activate_read_only(",
    )
    for marker in forbidden:
        assert marker not in service
        assert marker not in execution
