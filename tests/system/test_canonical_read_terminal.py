from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from voodoo_product import canonical_read_terminal as terminal_module
from voodoo_product.canonical_pipeline import CanonicalPreparedExecution
from voodoo_product.canonical_read_terminal import (
    CanonicalGitHubReadTerminal,
    VerifierRuntimeProfile,
)
from voodoo_product.capability_registry import ImmutableCapabilityRegistry
from voodoo_product.execution_capsule import ImmutableExecutionCapsuleRegistry
from voodoo_product.execution_contract import ExecutionTarget
from voodoo_product.github_read_provider import GitHubRefReadHandler
from voodoo_product.isolated_runner import IsolatedRunnerAdapter
from voodoo_product.terminal_profile import (
    BOUNDED_MUTATION_TERMINAL_PROFILE,
    READ_ONLY_TERMINAL_PROFILE,
)
from voodoo_product.trusted_clock import TrustedClockAuthority
from voodoo_product.verifier_credential import VerifierCredentialPolicy
from voodoo_product.verifier_observation import VerifierGitHubRefReadHandler

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
D6 = "6" * 64
D7 = "7" * 64
D8 = "8" * 64
D9 = "9" * 64
DA = "a" * 64
DB = "b" * 64
DC = "c" * 64
DD = "d" * 64
DE = "e" * 64
DF = "f" * 64


class FixedClock:
    def read(self) -> datetime:
        return datetime(2026, 8, 20, 2, 0, tzinfo=UTC)


class FakeCapabilityRegistry(ImmutableCapabilityRegistry):
    def __init__(self, definition: object) -> None:
        self.definition = definition

    def definition_by_identity(self, definition_identity: str) -> object:
        assert definition_identity == DC
        return self.definition


class FakeCapsuleRegistry(ImmutableExecutionCapsuleRegistry):
    def __init__(self, capability_registry: ImmutableCapabilityRegistry, capsule: object) -> None:
        self.capability_registry = capability_registry
        self.capsule = capsule

    def capsule_for_definition(self, definition_identity: str) -> object:
        assert definition_identity == DC
        return self.capsule


class FakeRunnerAdapter(IsolatedRunnerAdapter):
    def __init__(self, events: list[str], fence: object) -> None:
        self.events = events
        self.current_fence = fence

    def prepare(self, *, lease: object, capsule: object, definition: object) -> object:
        del lease, capsule, definition
        self.events.append("runner.prepare")
        return SimpleNamespace(
            identity=SimpleNamespace(identity_digest=D8),
            boundary=SimpleNamespace(boundary_digest=D9),
        )

    def activate(self, *, prepared: object) -> object:
        del prepared
        self.events.append("runner.activate")
        return SimpleNamespace(activation_digest=DA)


class FakeRunnerHandler(GitHubRefReadHandler):
    def __init__(self, events: list[str], fence: object) -> None:
        self.events = events
        self.current_fence = fence

    def observe_ref(self, *, prepared: object, activation: object, target: object) -> object:
        del prepared, activation, target
        self.events.append("runner.observe")
        return SimpleNamespace(observation_digest=DB)


class CompletionCoordinator:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def complete(self, *, lease_id: str, completion_digest: str) -> object:
        self.events.append("durable.complete")
        assert lease_id == D7
        assert completion_digest == DB
        return SimpleNamespace(outcome="COMPLETED", completion_digest=completion_digest)


class FakeVerifierHandler(VerifierGitHubRefReadHandler):
    def __init__(self, events: list[str], clock: TrustedClockAuthority) -> None:
        self.events = events
        self.trusted_clock = clock

    def observe_ref(self, *, verifier: object, boundary: object, decision: object, target: object) -> object:
        del verifier, boundary, decision, target
        self.events.append("verifier.observe")
        return SimpleNamespace(observation_digest=DD)


def prepared(*, terminal_profile: str = READ_ONLY_TERMINAL_PROFILE) -> CanonicalPreparedExecution:
    target = ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={"repository": "nulleimy/V-One", "ref": "refs/heads/main"},
    )
    snapshot = SimpleNamespace(execution_target=target)
    return CanonicalPreparedExecution(
        terminal_profile=terminal_profile,
        terminal_profile_binding_digest=D1,
        execution_id="exec-canonical-read-1",
        request_id="req-canonical-read-1",
        capability="github.read-ref/v1",
        capability_definition_identity=DC,
        environment="staging",
        target_digest=target.target_digest,
        authorization_snapshot_digest=D2,
        grant_digest=D3,
        grant_jti="jti-canonical-read-1",
        outbox_entry_digest=D4,
        envelope_digest=D5,
        admission_digest=D6,
        lease_id=D7,
        lease_digest=D8,
        execution_epoch=1,
        execution_capsule_digest=D9,
        snapshot=snapshot,
        grant=SimpleNamespace(),
        outbox=SimpleNamespace(),
        envelope=SimpleNamespace(),
        admission=SimpleNamespace(),
        lease=SimpleNamespace(),
    )


def terminal(events: list[str]) -> CanonicalGitHubReadTerminal:
    definition = SimpleNamespace(
        capability="github.read-ref/v1",
        effect_class="READ_ONLY",
    )
    capability_registry = FakeCapabilityRegistry(definition)
    capsule_registry = FakeCapsuleRegistry(
        capability_registry,
        SimpleNamespace(capsule_digest=D9),
    )
    fence = object()
    clock = TrustedClockAuthority(
        source_identity="trusted-clock/canonical-read-test",
        authority_revision="trusted-clock/canonical-read-test-r1",
        source=FixedClock(),
        allowed_environments=frozenset({"staging"}),
    )
    verifier_profile = VerifierRuntimeProfile(
        verifier_class="github-actions.verifier/v1",
        provider="github",
        provider_instance_id="gha:canonical-read:verifier:1",
        credential_class="github.verifier-read/scoped-v1",
        rootfs_digest=DE,
        resource_limit_profile_digest=DF,
        network_policy_digest=DA,
        identity_revision="verifier-identity/canonical-read-test-r1",
        boundary_revision="verification-boundary/canonical-read-test-r1",
        decision_revision="verifier-credential/canonical-read-test-r1",
        credential_ttl_seconds=60,
    )
    verifier_policy = VerifierCredentialPolicy.create(
        credential_class=verifier_profile.credential_class,
        provider=verifier_profile.provider,
        audience="api.github.com",
        enabled_environments=("staging",),
        max_ttl_seconds=60,
        policy_revision="verifier-policy/canonical-read-test-r1",
    )
    return CanonicalGitHubReadTerminal(
        capability_registry=capability_registry,
        capsule_registry=capsule_registry,
        runner_adapter=FakeRunnerAdapter(events, fence),
        runner_handler=FakeRunnerHandler(events, fence),
        completion_coordinator=CompletionCoordinator(events),
        verifier_profile=verifier_profile,
        verifier_policy=verifier_policy,
        verifier_handler=FakeVerifierHandler(events, clock),
        verifier_clock=clock,
        observed_post_state_revision="observed-post-state/canonical-read-test-r1",
        strength_revision="verification-strength/canonical-read-test-r1",
        result_revision="verification-result/canonical-read-test-r1",
    )


def test_read_terminal_routes_runner_completion_then_independent_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    boundary = SimpleNamespace(boundary_digest=DC)
    decision = SimpleNamespace(decision_digest=DD)
    verifier_observation = SimpleNamespace(observation_digest=DE)
    observed_post_state = SimpleNamespace(state_digest=DF)
    strength = SimpleNamespace(strength_digest=D1)
    result = SimpleNamespace(
        verdict="VERIFIED",
        result_digest=D2,
        verification_strength_class="INDEPENDENT_PROVIDER_READBACK",
    )

    def create_boundary(**_: object) -> object:
        events.append("verification.boundary")
        return boundary

    def create_decision(**_: object) -> object:
        events.append("verifier.credential")
        return decision

    def verify(**_: object) -> tuple[object, object, object]:
        events.append("verification.result")
        return observed_post_state, strength, result

    monkeypatch.setattr(
        terminal_module.IndependentVerificationBoundary,
        "create",
        staticmethod(create_boundary),
    )
    monkeypatch.setattr(
        terminal_module.VerifierCredentialDecision,
        "create",
        staticmethod(create_decision),
    )
    subject = terminal(events)
    subject.verifier_handler.observe_ref = (  # type: ignore[method-assign]
        lambda **_: events.append("verifier.observe") or verifier_observation
    )
    monkeypatch.setattr(terminal_module, "verify_github_ref_readback", verify)

    output = subject.run(prepared=prepared())

    assert events == [
        "runner.prepare",
        "runner.activate",
        "runner.observe",
        "durable.complete",
        "verification.boundary",
        "verifier.credential",
        "verifier.observe",
        "verification.result",
    ]
    assert output.runner_observation.observation_digest == DB
    assert output.verifier_observation is verifier_observation
    assert output.verification_result is result
    assert output.verification_result.verdict == "VERIFIED"


def test_read_terminal_rejects_mutation_profile_before_runner_activity() -> None:
    events: list[str] = []
    subject = terminal(events)

    with pytest.raises(PermissionError, match="CANONICAL_READ_TERMINAL_PROFILE_MISMATCH"):
        subject.run(prepared=prepared(terminal_profile=BOUNDED_MUTATION_TERMINAL_PROFILE))

    assert events == []


def test_read_terminal_rejects_capability_identity_semantic_mismatch() -> None:
    events: list[str] = []
    subject = terminal(events)
    subject.capability_registry.definition.capability = "github.other/v1"

    with pytest.raises(PermissionError, match="CANONICAL_READ_CAPABILITY_MISMATCH"):
        subject.run(prepared=prepared())

    assert events == []


def test_read_terminal_has_no_mutation_or_proof_cell_api() -> None:
    subject = terminal([])

    for forbidden in (
        "mutate",
        "write",
        "create_ref",
        "delete_ref",
        "create_operation_proof",
        "create_operation_cell",
    ):
        assert not hasattr(subject, forbidden)
