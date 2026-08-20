from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .canonical_pipeline import CanonicalPreparedExecution
from .capability_registry import ImmutableCapabilityRegistry
from .durable_current_fence import DurableCurrentExecutionFence
from .execution_capsule import ImmutableExecutionCapsuleRegistry
from .execution_conformance import ImmutableHandlerConformanceRegistry
from .rollback_control import (
    GITHUB_DELETE_REF_CAPABILITY,
    CredentialAccessDecisionV3,
    CredentialBrokerPolicyV3,
    GitHubDeleteRefConditionContract,
    GitHubDeleteRefHandlerContract,
    GitHubDeleteRefRequest,
    RollbackWriteRequirement,
    RunnerBoundaryV3,
    WRITE_RUNNER_CLASS,
)
from .rollback_runtime import (
    EphemeralRollbackCredentialDelivery,
    RollbackWriteEffectPreflight,
    RollbackWriteRuntimeActivation,
)
from .runner_identity import RunnerIdentity
from .terminal_profile import BOUNDED_MUTATION_TERMINAL_PROFILE
from .trusted_clock import TrustedClockAuthority


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


def _canonical(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class A09RollbackRuntimeProfile:
    provider: str
    provider_instance_id: str
    rootfs_digest: str
    resource_limit_profile_digest: str
    network_policy_digest: str
    identity_revision: str
    condition_revision: str
    requirement_revision: str
    boundary_revision: str
    credential_policy_revision: str
    credential_decision_revision: str
    credential_delivery_revision: str
    activation_revision: str
    request_revision: str
    preflight_revision: str
    max_credential_ttl_seconds: int

    def __post_init__(self) -> None:
        for field in (
            "provider",
            "provider_instance_id",
            "identity_revision",
            "condition_revision",
            "requirement_revision",
            "boundary_revision",
            "credential_policy_revision",
            "credential_decision_revision",
            "credential_delivery_revision",
            "activation_revision",
            "request_revision",
            "preflight_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "rootfs_digest",
            "resource_limit_profile_digest",
            "network_policy_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if (
            isinstance(self.max_credential_ttl_seconds, bool)
            or not isinstance(self.max_credential_ttl_seconds, int)
            or not 1 <= self.max_credential_ttl_seconds <= 300
        ):
            raise ValueError("max_credential_ttl_seconds must be between 1 and 300")


@dataclass(frozen=True, slots=True)
class A09PreparedRollback:
    """Rollback preparation that ends at a current read-then-delete preflight."""

    prepared: CanonicalPreparedExecution
    condition: GitHubDeleteRefConditionContract
    identity: RunnerIdentity
    requirement: RollbackWriteRequirement
    boundary: RunnerBoundaryV3
    credential_policy: CredentialBrokerPolicyV3
    credential_decision: CredentialAccessDecisionV3
    credential_delivery: EphemeralRollbackCredentialDelivery
    activation: RollbackWriteRuntimeActivation
    request: GitHubDeleteRefRequest
    preflight: RollbackWriteEffectPreflight


class A09RollbackPreparer:
    """Compose separately-authorized exact rollback metadata without invoking DELETE_REF.

    The caller must supply a current read-only pre-delete observation (SHA + evidence digest). This
    class contains no GitHub delete transport and no credential secret; provider mutation remains a
    later independent authorization/effect boundary.
    """

    def __init__(
        self,
        *,
        capability_registry: ImmutableCapabilityRegistry,
        capsule_registry: ImmutableExecutionCapsuleRegistry,
        handler_registry: ImmutableHandlerConformanceRegistry,
        current_fence: DurableCurrentExecutionFence,
        trusted_clock: TrustedClockAuthority,
        runtime_profile: A09RollbackRuntimeProfile,
    ) -> None:
        if not isinstance(capability_registry, ImmutableCapabilityRegistry):
            raise ValueError("capability_registry is invalid")
        if not isinstance(capsule_registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("capsule_registry is invalid")
        if capsule_registry.capability_registry is not capability_registry:
            raise ValueError("capsule registry must use supplied capability registry")
        if not isinstance(handler_registry, ImmutableHandlerConformanceRegistry):
            raise ValueError("handler_registry is invalid")
        if handler_registry.capsule_registry is not capsule_registry:
            raise ValueError("handler registry must use supplied capsule registry")
        if not isinstance(current_fence, DurableCurrentExecutionFence):
            raise ValueError("current_fence is invalid")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock is invalid")
        if current_fence.trusted_clock is not trusted_clock:
            raise ValueError("rollback fence and preparer must share trusted clock")
        if not isinstance(runtime_profile, A09RollbackRuntimeProfile):
            raise ValueError("runtime_profile is invalid")
        self.capability_registry = capability_registry
        self.capsule_registry = capsule_registry
        self.handler_registry = handler_registry
        self.current_fence = current_fence
        self.trusted_clock = trusted_clock
        self.runtime_profile = runtime_profile
        self.handler_contract = GitHubDeleteRefHandlerContract()

    def prepare(
        self,
        *,
        prepared: CanonicalPreparedExecution,
        observed_ref_sha: str,
        predelete_observation_digest: str,
    ) -> A09PreparedRollback:
        if not isinstance(prepared, CanonicalPreparedExecution):
            raise ValueError("prepared must be CanonicalPreparedExecution")
        if prepared.terminal_profile != BOUNDED_MUTATION_TERMINAL_PROFILE:
            raise PermissionError("A09_ROLLBACK_TERMINAL_PROFILE_MISMATCH")
        if prepared.capability != GITHUB_DELETE_REF_CAPABILITY:
            raise PermissionError("A09_ROLLBACK_CAPABILITY_MISMATCH")
        _require_digest(predelete_observation_digest, field="predelete_observation_digest")

        definition = self.capability_registry.definition_by_identity(
            prepared.capability_definition_identity
        )
        if definition.capability != GITHUB_DELETE_REF_CAPABILITY:
            raise PermissionError("A09_ROLLBACK_DEFINITION_MISMATCH")
        capsule = self.capsule_registry.capsule_for_definition(
            prepared.capability_definition_identity
        )
        if capsule.capsule_digest != prepared.execution_capsule_digest:
            raise PermissionError("A09_ROLLBACK_CAPSULE_MISMATCH")
        handler_evidence = self.handler_registry.resolve(capsule.capsule_digest)

        target = getattr(prepared.snapshot, "execution_target", None)
        if target is None or target.target_digest != prepared.target_digest:
            raise PermissionError("A09_ROLLBACK_TARGET_MISMATCH")
        claims = target.target_claims
        condition = GitHubDeleteRefConditionContract.create(
            repository=claims["repository"],
            ref=claims["ref"],
            expected_sha=claims["expected_sha"],
            original_create_response_digest=claims["original_create_response_digest"],
            original_verification_result_digest=claims["original_verification_result_digest"],
            contract_revision=self.runtime_profile.condition_revision,
        )
        requirement = RollbackWriteRequirement.create(
            definition=definition,
            capsule=capsule,
            handler_evidence=handler_evidence,
            condition=condition,
            requirement_revision=self.runtime_profile.requirement_revision,
        )
        identity = RunnerIdentity.create(
            runner_class=WRITE_RUNNER_CLASS,
            provider=self.runtime_profile.provider,
            provider_instance_id=self.runtime_profile.provider_instance_id,
            environment=prepared.environment,
            rootfs_digest=self.runtime_profile.rootfs_digest,
            resource_limit_profile_digest=self.runtime_profile.resource_limit_profile_digest,
            network_policy_digest=self.runtime_profile.network_policy_digest,
            identity_revision=self.runtime_profile.identity_revision,
        )
        boundary = RunnerBoundaryV3.create(
            identity=identity,
            lease=prepared.lease,  # type: ignore[arg-type]
            capsule=capsule,
            definition=definition,
            requirement=requirement,
            condition=condition,
            boundary_revision=self.runtime_profile.boundary_revision,
        )
        policy = CredentialBrokerPolicyV3.create(
            definition=definition,
            requirement=requirement,
            max_ttl_seconds=self.runtime_profile.max_credential_ttl_seconds,
            policy_revision=self.runtime_profile.credential_policy_revision,
        )

        valid_from = datetime.fromisoformat(prepared.lease.acquired_at)
        lease_expires = datetime.fromisoformat(prepared.lease.expires_at)
        policy_expires = valid_from + timedelta(
            seconds=self.runtime_profile.max_credential_ttl_seconds
        )
        expires_at = min(lease_expires, policy_expires)
        decision = CredentialAccessDecisionV3.create(
            boundary=boundary,
            policy=policy,
            valid_from=_canonical(valid_from),
            expires_at=_canonical(expires_at),
            decision_revision=self.runtime_profile.credential_decision_revision,
        )
        delivery_clock = self.trusted_clock.witness(environment=prepared.environment)
        delivery = EphemeralRollbackCredentialDelivery.create(
            boundary=boundary,
            decision=decision,
            provider_instance_id=self.runtime_profile.provider_instance_id,
            delivered_at=delivery_clock.observed_at,
            clock_witness_digest=delivery_clock.witness_digest,
            delivery_revision=self.runtime_profile.credential_delivery_revision,
        )
        activation = RollbackWriteRuntimeActivation.create(
            boundary=boundary,
            decision=decision,
            delivery=delivery,
            activation_revision=self.runtime_profile.activation_revision,
        )
        request = self.handler_contract.prepare_request(
            target=target,
            boundary=boundary,
            decision=decision,
            condition=condition,
            request_revision=self.runtime_profile.request_revision,
        )

        # Final current-fence check before producing a mutation-ready preflight. Still no provider call.
        self.current_fence.assert_current(lease=prepared.lease)  # type: ignore[arg-type]
        checked = self.trusted_clock.witness(environment=prepared.environment)
        preflight = RollbackWriteEffectPreflight.create(
            request=request,
            target=target,
            boundary=boundary,
            decision=decision,
            activation=activation,
            condition=condition,
            observed_ref_sha=observed_ref_sha,
            predelete_observation_digest=predelete_observation_digest,
            checked_at=checked.observed_at,
            clock_witness_digest=checked.witness_digest,
            preflight_revision=self.runtime_profile.preflight_revision,
        )
        return A09PreparedRollback(
            prepared=prepared,
            condition=condition,
            identity=identity,
            requirement=requirement,
            boundary=boundary,
            credential_policy=policy,
            credential_decision=decision,
            credential_delivery=delivery,
            activation=activation,
            request=request,
            preflight=preflight,
        )
