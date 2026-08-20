from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from .canonical_pipeline import CanonicalPreparedExecution
from .capability_registry import ImmutableCapabilityRegistry
from .execution_capsule import ImmutableExecutionCapsuleRegistry
from .execution_contract import ExecutionTarget
from .github_read_provider import GitHubRefObservation, GitHubRefReadHandler
from .isolated_runner import IsolatedRunnerAdapter
from .runner_identity import READ_ONLY_EFFECT_CLASS
from .terminal_profile import READ_ONLY_TERMINAL_PROFILE
from .trusted_clock import TrustedClockAuthority
from .verification_result import (
    ObservedPostState,
    VerificationResult,
    VerificationStrength,
    verify_github_ref_readback,
)
from .verifier_credential import VerifierCredentialDecision, VerifierCredentialPolicy
from .verifier_identity import IndependentVerificationBoundary, VerifierIdentity
from .verifier_observation import VerifierGitHubRefObservation, VerifierGitHubRefReadHandler


class _CompletionCoordinator(Protocol):
    def complete(self, *, lease_id: str, completion_digest: str) -> object: ...


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class VerifierRuntimeProfile:
    """Non-secret immutable verifier runtime description used by the READ terminal."""

    verifier_class: str
    provider: str
    provider_instance_id: str
    credential_class: str
    rootfs_digest: str
    resource_limit_profile_digest: str
    network_policy_digest: str
    identity_revision: str
    boundary_revision: str
    decision_revision: str
    credential_ttl_seconds: int

    def __post_init__(self) -> None:
        for field in (
            "verifier_class",
            "provider",
            "provider_instance_id",
            "credential_class",
            "identity_revision",
            "boundary_revision",
            "decision_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "rootfs_digest",
            "resource_limit_profile_digest",
            "network_policy_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if (
            isinstance(self.credential_ttl_seconds, bool)
            or not isinstance(self.credential_ttl_seconds, int)
            or not 1 <= self.credential_ttl_seconds <= 3600
        ):
            raise ValueError("credential_ttl_seconds must be between 1 and 3600")

    def identity(self, *, environment: str) -> VerifierIdentity:
        return VerifierIdentity.create(
            verifier_class=self.verifier_class,
            provider=self.provider,
            provider_instance_id=self.provider_instance_id,
            environment=environment,
            credential_class=self.credential_class,
            rootfs_digest=self.rootfs_digest,
            resource_limit_profile_digest=self.resource_limit_profile_digest,
            network_policy_digest=self.network_policy_digest,
            identity_revision=self.identity_revision,
        )


@dataclass(frozen=True, slots=True)
class CanonicalReadTerminalResult:
    prepared: CanonicalPreparedExecution
    runner_observation: GitHubRefObservation
    verifier_identity: VerifierIdentity
    verification_boundary: IndependentVerificationBoundary
    verifier_credential_decision: VerifierCredentialDecision
    verifier_observation: VerifierGitHubRefObservation
    observed_post_state: ObservedPostState
    verification_strength: VerificationStrength
    verification_result: VerificationResult
    durable_completion: object


class CanonicalGitHubReadTerminal:
    """Canonical READ_ONLY terminal over existing D4b + E3/E4b contracts.

    The terminal executes only a capability already prepared under the exact READ_ONLY terminal
    allowlist. It reuses the accepted isolated Runner and independent Verifier contracts, records C4
    durable completion after the Runner observation, then performs the separate verifier readback and
    returns VerificationResult/v1. It cannot create OperationProof/v2 or OperationCell/v1.
    """

    def __init__(
        self,
        *,
        capability_registry: ImmutableCapabilityRegistry,
        capsule_registry: ImmutableExecutionCapsuleRegistry,
        runner_adapter: IsolatedRunnerAdapter,
        runner_handler: GitHubRefReadHandler,
        completion_coordinator: _CompletionCoordinator,
        verifier_profile: VerifierRuntimeProfile,
        verifier_policy: VerifierCredentialPolicy,
        verifier_handler: VerifierGitHubRefReadHandler,
        verifier_clock: TrustedClockAuthority,
        observed_post_state_revision: str,
        strength_revision: str,
        result_revision: str,
    ) -> None:
        if not isinstance(capability_registry, ImmutableCapabilityRegistry):
            raise ValueError("capability_registry is invalid")
        if not isinstance(capsule_registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("capsule_registry is invalid")
        if capsule_registry.capability_registry is not capability_registry:
            raise ValueError("capsule registry must use the supplied capability registry")
        if not isinstance(runner_adapter, IsolatedRunnerAdapter):
            raise ValueError("runner_adapter is invalid")
        if not isinstance(runner_handler, GitHubRefReadHandler):
            raise ValueError("runner_handler is invalid")
        if runner_adapter.current_fence is not runner_handler.current_fence:
            raise ValueError("Runner activation and observation must share one current fence")
        if not callable(getattr(completion_coordinator, "complete", None)):
            raise ValueError("completion_coordinator must implement complete")
        if not isinstance(verifier_profile, VerifierRuntimeProfile):
            raise ValueError("verifier_profile is invalid")
        if not isinstance(verifier_policy, VerifierCredentialPolicy):
            raise ValueError("verifier_policy is invalid")
        if verifier_policy.credential_class != verifier_profile.credential_class:
            raise ValueError("verifier policy credential class must match verifier profile")
        if verifier_policy.provider != verifier_profile.provider:
            raise ValueError("verifier policy provider must match verifier profile")
        if not isinstance(verifier_handler, VerifierGitHubRefReadHandler):
            raise ValueError("verifier_handler is invalid")
        if not isinstance(verifier_clock, TrustedClockAuthority):
            raise ValueError("verifier_clock is invalid")
        if verifier_handler.trusted_clock is not verifier_clock:
            raise ValueError("verifier handler and decision clock must share trusted clock authority")

        self.capability_registry = capability_registry
        self.capsule_registry = capsule_registry
        self.runner_adapter = runner_adapter
        self.runner_handler = runner_handler
        self.completion_coordinator = completion_coordinator
        self.verifier_profile = verifier_profile
        self.verifier_policy = verifier_policy
        self.verifier_handler = verifier_handler
        self.verifier_clock = verifier_clock
        self.observed_post_state_revision = _require_text(
            observed_post_state_revision,
            field="observed_post_state_revision",
        )
        self.strength_revision = _require_text(strength_revision, field="strength_revision")
        self.result_revision = _require_text(result_revision, field="result_revision")

    def run(self, *, prepared: CanonicalPreparedExecution) -> CanonicalReadTerminalResult:
        if not isinstance(prepared, CanonicalPreparedExecution):
            raise ValueError("prepared must be CanonicalPreparedExecution")
        if prepared.terminal_profile != READ_ONLY_TERMINAL_PROFILE:
            raise PermissionError("CANONICAL_READ_TERMINAL_PROFILE_MISMATCH")

        definition = self.capability_registry.definition_by_identity(
            prepared.capability_definition_identity
        )
        if definition.capability != prepared.capability:
            raise PermissionError("CANONICAL_READ_CAPABILITY_MISMATCH")
        if definition.effect_class != READ_ONLY_EFFECT_CLASS:
            raise PermissionError("CANONICAL_READ_EFFECT_CLASS_MISMATCH")
        capsule = self.capsule_registry.capsule_for_definition(
            prepared.capability_definition_identity
        )
        if capsule.capsule_digest != prepared.execution_capsule_digest:
            raise PermissionError("CANONICAL_READ_CAPSULE_MISMATCH")

        snapshot = prepared.snapshot
        target = getattr(snapshot, "execution_target", None)
        if not isinstance(target, ExecutionTarget):
            raise ValueError("prepared snapshot has no valid ExecutionTarget")
        if target.target_digest != prepared.target_digest:
            raise PermissionError("CANONICAL_READ_TARGET_MISMATCH")

        runner_runtime = self.runner_adapter.prepare(
            lease=prepared.lease,  # type: ignore[arg-type]
            capsule=capsule,
            definition=definition,
        )
        activation = self.runner_adapter.activate(prepared=runner_runtime)
        runner_observation = self.runner_handler.observe_ref(
            prepared=runner_runtime,
            activation=activation,
            target=target,
        )
        durable_completion = self.completion_coordinator.complete(
            lease_id=prepared.lease_id,
            completion_digest=runner_observation.observation_digest,
        )

        verifier = self.verifier_profile.identity(environment=prepared.environment)
        boundary = IndependentVerificationBoundary.create(
            verifier=verifier,
            runner_identity=runner_runtime.identity,
            runner_boundary=runner_runtime.boundary,
            runner_observation=runner_observation,
            boundary_revision=self.verifier_profile.boundary_revision,
        )
        clock_witness = self.verifier_clock.witness(environment=prepared.environment)
        valid_from = datetime.fromisoformat(clock_witness.observed_at)
        expires_at = valid_from + timedelta(seconds=self.verifier_profile.credential_ttl_seconds)
        decision = VerifierCredentialDecision.create(
            verifier=verifier,
            boundary=boundary,
            policy=self.verifier_policy,
            valid_from=_canonical_timestamp(valid_from),
            expires_at=_canonical_timestamp(expires_at),
            decision_revision=self.verifier_profile.decision_revision,
        )
        verifier_observation = self.verifier_handler.observe_ref(
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            target=target,
        )
        observed_post_state, strength, result = verify_github_ref_readback(
            runner_observation=runner_observation,
            verifier_observation=verifier_observation,
            boundary=boundary,
            observed_post_state_revision=self.observed_post_state_revision,
            strength_revision=self.strength_revision,
            result_revision=self.result_revision,
        )
        return CanonicalReadTerminalResult(
            prepared=prepared,
            runner_observation=runner_observation,
            verifier_identity=verifier,
            verification_boundary=boundary,
            verifier_credential_decision=decision,
            verifier_observation=verifier_observation,
            observed_post_state=observed_post_state,
            verification_strength=strength,
            verification_result=result,
            durable_completion=durable_completion,
        )
