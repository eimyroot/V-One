from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.credential_broker import (
    CredentialBrokerPolicy,
    ImmutableCredentialBroker,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_contract import ExecutionTarget
from voodoo_product.execution_lease import ExecutionLease
from voodoo_product.github_read_provider import (
    GitHubReadDenied,
    GitHubReadTransport,
    GitHubRefObservation,
    GitHubRefReadHandler,
)
from voodoo_product.isolated_runner import (
    CurrentExecutionFence,
    IsolatedRuntimeBootstrap,
    PreparedIsolatedRuntime,
    ReadOnlyRuntimeActivation,
)
from voodoo_product.precondition_witness import READ_THEN_COMPARE
from voodoo_product.runner_identity import RunnerBoundary, RunnerIdentity
from voodoo_product.trusted_clock import ClockSource, TrustedClockAuthority

RUNNER_CLASS = "caster-minal.isolated-linux/v1"
CREDENTIAL_CLASS = "github.read-only/v1"
ROOTFS_DIGEST = "1" * 64
RESOURCE_DIGEST = "2" * 64
NETWORK_DIGEST = "3" * 64
OBSERVED_SHA = "6d5ef2230ac8492e6cbef3d6840fb7920f261d36"


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class FixedClock:
    def read(self) -> datetime:
        return datetime(2026, 8, 17, 11, 30, 0, tzinfo=UTC)


class RecordingFence:
    def __init__(self, events: list[str], *, deny: bool = False) -> None:
        self.events = events
        self.deny = deny

    def assert_current(self, *, lease: ExecutionLease) -> None:
        assert isinstance(lease, ExecutionLease)
        self.events.append("fence")
        if self.deny:
            raise GitHubReadDenied("STALE_EXECUTION_EPOCH")


class RecordingGitHubTransport:
    source_identity = "api.github.com/git-ref/v1"

    def __init__(self, events: list[str], *, commit_sha: str = OBSERVED_SHA) -> None:
        self.events = events
        self.commit_sha = commit_sha
        self.calls: list[tuple[str, str]] = []

    def read_ref(self, *, repository: str, ref: str) -> str:
        self.events.append("read")
        self.calls.append((repository, ref))
        return self.commit_sha


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


def make_lease(*, capsule_digest: str) -> ExecutionLease:
    admission_id = "a" * 64
    claims = {
        "schema_version": 1,
        "lease_type": "execution-lease/v1",
        "lease_id": digest(
            {
                "identity_type": "execution-lease-id/v1",
                "admission_id": admission_id,
                "execution_epoch": 1,
            }
        ),
        "dispatch_id": "b" * 64,
        "admission_id": admission_id,
        "admission_digest": "c" * 64,
        "execution_id": "exec_phase_d_github_read",
        "workspace_id": "wrk_main",
        "environment": "local",
        "execution_capsule_digest": capsule_digest,
        "runner_class": RUNNER_CLASS,
        "execution_epoch": 1,
        "acquired_at": "2026-08-17T11:29:00.000+00:00",
        "expires_at": "2026-08-17T11:31:00.000+00:00",
        "clock_witness_digest": "d" * 64,
        "lease_revision": "execution-lease/c4b-r1",
    }
    return ExecutionLease.from_dict({**claims, "lease_digest": digest(claims)})


def make_runtime(*, credential_provider: str = "github") -> tuple[
    PreparedIsolatedRuntime,
    ReadOnlyRuntimeActivation,
]:
    definition = make_definition()
    capsule = make_capsule(definition)
    lease = make_lease(capsule_digest=capsule.capsule_digest)
    bootstrap = IsolatedRuntimeBootstrap.create(
        provider="caster-minal.reference/v1",
        provider_instance_id="isolated-session-d4-001",
        runner_class=RUNNER_CLASS,
        environment="local",
        rootfs_digest=ROOTFS_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
        bootstrap_revision="runtime-bootstrap/d3-r1",
    )
    identity = RunnerIdentity.create(
        runner_class=RUNNER_CLASS,
        provider=bootstrap.provider,
        provider_instance_id=bootstrap.provider_instance_id,
        environment="local",
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
    policy = CredentialBrokerPolicy.create(
        credential_class=CREDENTIAL_CLASS,
        provider=credential_provider,
        audience="api.github.com",
        allowed_capability_definition_identities=(definition.definition_identity,),
        enabled_environments=("local", "staging"),
        policy_revision="credential-broker-policy/d2-r1",
    )
    decision = ImmutableCredentialBroker(
        policies=(policy,),
        decision_revision="credential-access-decision/d2-r1",
    ).authorize(boundary=boundary, lease=lease)
    prepared = PreparedIsolatedRuntime(
        bootstrap=bootstrap,
        identity=identity,
        boundary=boundary,
        decision=decision,
        lease=lease,
    )
    activation = ReadOnlyRuntimeActivation.create(
        bootstrap=bootstrap,
        identity=identity,
        boundary=boundary,
        decision=decision,
        lease=lease,
        activation_revision="runtime-activation/d3-r1",
    )
    return prepared, activation


def make_target() -> ExecutionTarget:
    return ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={"repository": "nulleimy/V-One", "ref": "refs/heads/main"},
    )


def make_clock() -> TrustedClockAuthority:
    source = FixedClock()
    assert isinstance(source, ClockSource)
    return TrustedClockAuthority(
        source_identity="trusted-clock/test",
        authority_revision="trusted-clock/d4-test-r1",
        source=source,
    )


def test_exact_github_ref_read_is_fenced_and_content_addressed() -> None:
    events: list[str] = []
    prepared, activation = make_runtime()
    transport = RecordingGitHubTransport(events)
    fence = RecordingFence(events)
    handler = GitHubRefReadHandler(
        transport=transport,
        current_fence=fence,
        trusted_clock=make_clock(),
        observation_revision="github-ref-observation/d4a-r1",
    )

    observation = handler.observe_ref(
        prepared=prepared,
        activation=activation,
        target=make_target(),
    )

    assert isinstance(transport, GitHubReadTransport)
    assert isinstance(fence, CurrentExecutionFence)
    assert events == ["fence", "read"]
    assert transport.calls == [("nulleimy/V-One", "refs/heads/main")]
    assert observation.commit_sha == OBSERVED_SHA
    assert observation.execution_epoch == 1
    assert observation.lease_id == prepared.lease.lease_id
    assert observation.runtime_activation_digest == activation.activation_digest
    assert observation.credential_decision_digest == prepared.decision.decision_digest
    assert observation.source_identity == transport.source_identity
    assert observation.observed_at == "2026-08-17T11:30:00.000+00:00"
    assert GitHubRefObservation.from_dict(observation.to_dict()) == observation


def test_stale_fence_denies_before_provider_read() -> None:
    events: list[str] = []
    prepared, activation = make_runtime()
    transport = RecordingGitHubTransport(events)
    handler = GitHubRefReadHandler(
        transport=transport,
        current_fence=RecordingFence(events, deny=True),
        trusted_clock=make_clock(),
        observation_revision="github-ref-observation/d4a-r1",
    )

    with pytest.raises(GitHubReadDenied) as denied:
        handler.observe_ref(
            prepared=prepared,
            activation=activation,
            target=make_target(),
        )

    assert denied.value.reason == "STALE_EXECUTION_EPOCH"
    assert events == ["fence"]
    assert transport.calls == []


def test_target_kind_and_fields_fail_closed_before_fence() -> None:
    events: list[str] = []
    prepared, activation = make_runtime()
    handler = GitHubRefReadHandler(
        transport=RecordingGitHubTransport(events),
        current_fence=RecordingFence(events),
        trusted_clock=make_clock(),
        observation_revision="github-ref-observation/d4a-r1",
    )

    wrong_kind = ExecutionTarget.create(
        target_kind="repository",
        target_claims={"repository": "nulleimy/V-One", "ref": "refs/heads/main"},
    )
    with pytest.raises(GitHubReadDenied) as denied_kind:
        handler.observe_ref(prepared=prepared, activation=activation, target=wrong_kind)
    assert denied_kind.value.reason == "GITHUB_READ_TARGET_KIND_MISMATCH"

    extra_field = ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={
            "repository": "nulleimy/V-One",
            "ref": "refs/heads/main",
            "write": True,
        },
    )
    with pytest.raises(GitHubReadDenied) as denied_fields:
        handler.observe_ref(prepared=prepared, activation=activation, target=extra_field)
    assert denied_fields.value.reason == "GITHUB_READ_TARGET_FIELDS_INVALID"
    assert events == []


def test_non_github_credential_decision_cannot_cross_provider_port() -> None:
    events: list[str] = []
    prepared, activation = make_runtime(credential_provider="other-provider")
    handler = GitHubRefReadHandler(
        transport=RecordingGitHubTransport(events),
        current_fence=RecordingFence(events),
        trusted_clock=make_clock(),
        observation_revision="github-ref-observation/d4a-r1",
    )

    with pytest.raises(GitHubReadDenied) as denied:
        handler.observe_ref(
            prepared=prepared,
            activation=activation,
            target=make_target(),
        )

    assert denied.value.reason == "GITHUB_READ_CREDENTIAL_PROVIDER_MISMATCH"
    assert events == []


def test_invalid_provider_object_id_is_rejected() -> None:
    events: list[str] = []
    prepared, activation = make_runtime()
    handler = GitHubRefReadHandler(
        transport=RecordingGitHubTransport(events, commit_sha="not-a-git-object"),
        current_fence=RecordingFence(events),
        trusted_clock=make_clock(),
        observation_revision="github-ref-observation/d4a-r1",
    )

    with pytest.raises(ValueError, match="Git object id"):
        handler.observe_ref(
            prepared=prepared,
            activation=activation,
            target=make_target(),
        )

    assert events == ["fence", "read"]


def test_observation_contract_rejects_secret_or_mutation_fields() -> None:
    events: list[str] = []
    prepared, activation = make_runtime()
    observation = GitHubRefReadHandler(
        transport=RecordingGitHubTransport(events),
        current_fence=RecordingFence(events),
        trusted_clock=make_clock(),
        observation_revision="github-ref-observation/d4a-r1",
    ).observe_ref(
        prepared=prepared,
        activation=activation,
        target=make_target(),
    )

    serialized = observation.to_dict()
    assert {"token", "secret", "authorization", "write", "mutation"}.isdisjoint(serialized)

    tampered = dict(serialized)
    tampered["token"] = "forbidden"
    with pytest.raises(ValueError, match="fields are invalid"):
        GitHubRefObservation.from_dict(tampered)


def test_handler_exposes_no_provider_mutation_operation() -> None:
    events: list[str] = []
    prepared, _ = make_runtime()
    handler = GitHubRefReadHandler(
        transport=RecordingGitHubTransport(events),
        current_fence=RecordingFence(events),
        trusted_clock=make_clock(),
        observation_revision="github-ref-observation/d4a-r1",
    )

    assert prepared.decision.provider_mutation_allowed is False
    assert not hasattr(handler, "write_ref")
    assert not hasattr(handler.transport, "write_ref")
