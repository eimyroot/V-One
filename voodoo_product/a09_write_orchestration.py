from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final

from .canonical_pipeline import CanonicalPreparedExecution
from .capability_registry import ImmutableCapabilityRegistry
from .controlled_write import (
    GITHUB_CREATE_REF_CAPABILITY,
    GitHubCreateRefConditionContract,
    ControlledWriteRequirement,
)
from .durable_current_fence import DurableCurrentExecutionFence
from .execution_capsule import ImmutableExecutionCapsuleRegistry
from .execution_conformance import ImmutableHandlerConformanceRegistry
from .github_create_ref_provider import (
    GITHUB_CREATE_REF_BINDER_ID,
    GitHubCreateRefHandlerContract,
    GitHubCreateRefRequest,
)
from .grant_consumption import GrantConsumptionWitness
from .isolated_runner import IsolatedRuntimeBootstrap
from .persistence import DatabaseStatement, ProductDatabaseAdapter
from .runner_identity import RunnerIdentity
from .target_binding import TargetBinding
from .terminal_profile import BOUNDED_MUTATION_TERMINAL_PROFILE
from .trusted_clock import TrustedClockAuthority
from .write_boundary import (
    WRITE_RUNNER_CLASS,
    CredentialAccessDecisionV2,
    CredentialBrokerPolicyV2,
    RunnerBoundaryV2,
)
from .write_runtime import (
    EphemeralWriteCredentialDelivery,
    WriteEffectPreflight,
    WriteRuntimeActivation,
)

SELECT_CONSUMPTION_FOR_A09: Final = DatabaseStatement(
    name="a09.select_consumption",
    mode="read",
    sqlite_sql="""
        SELECT consumption_id, witness_digest, consumption_json
        FROM grant_consumptions_v1
        WHERE consumption_id = ?
    """,
)


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


@dataclass(frozen=True, slots=True)
class A09WriteRuntimeProfile:
    """Non-secret runtime identity/profile for reusable bounded WRITE preparation."""

    provider: str
    provider_instance_id: str
    rootfs_digest: str
    resource_limit_profile_digest: str
    network_policy_digest: str
    bootstrap_revision: str
    identity_revision: str
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
            "bootstrap_revision",
            "identity_revision",
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
class A09PreparedCreateRef:
    """Reusable create-ref preparation that deliberately stops before provider mutation."""

    prepared: CanonicalPreparedExecution
    consumption: GrantConsumptionWitness
    bootstrap: IsolatedRuntimeBootstrap
    identity: RunnerIdentity
    requirement: ControlledWriteRequirement
    boundary: RunnerBoundaryV2
    credential_policy: CredentialBrokerPolicyV2
    credential_decision: CredentialAccessDecisionV2
    credential_delivery: EphemeralWriteCredentialDelivery
    activation: WriteRuntimeActivation
    target_binding: TargetBinding
    request: GitHubCreateRefRequest
    preflight: WriteEffectPreflight


class A09CreateRefPreparer:
    """Compose current bounded create-ref safety contracts without executing a provider effect.

    This class has no provider transport and accepts no credential secret. Its strongest result is a
    WriteEffectPreflight proving the exact current lease/authority/target/runtime bindings immediately
    before a future separately-authorized mutation.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        capability_registry: ImmutableCapabilityRegistry,
        capsule_registry: ImmutableExecutionCapsuleRegistry,
        handler_registry: ImmutableHandlerConformanceRegistry,
        provider_condition: GitHubCreateRefConditionContract,
        current_fence: DurableCurrentExecutionFence,
        trusted_clock: TrustedClockAuthority,
        runtime_profile: A09WriteRuntimeProfile,
    ) -> None:
        if not isinstance(database, ProductDatabaseAdapter):
            raise ValueError("database must implement ProductDatabaseAdapter")
        if not isinstance(capability_registry, ImmutableCapabilityRegistry):
            raise ValueError("capability_registry is invalid")
        if not isinstance(capsule_registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("capsule_registry is invalid")
        if capsule_registry.capability_registry is not capability_registry:
            raise ValueError("capsule registry must use the supplied capability registry")
        if not isinstance(handler_registry, ImmutableHandlerConformanceRegistry):
            raise ValueError("handler_registry is invalid")
        if handler_registry.capsule_registry is not capsule_registry:
            raise ValueError("handler registry must use the supplied capsule registry")
        if not isinstance(provider_condition, GitHubCreateRefConditionContract):
            raise ValueError("provider_condition is invalid")
        if not isinstance(current_fence, DurableCurrentExecutionFence):
            raise ValueError("current_fence is invalid")
        if current_fence.db is not database:
            raise ValueError("current fence must use the supplied database")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock is invalid")
        if current_fence.trusted_clock is not trusted_clock:
            raise ValueError("current fence and A09 must share trusted clock authority")
        if not isinstance(runtime_profile, A09WriteRuntimeProfile):
            raise ValueError("runtime_profile is invalid")
        self.db = database
        self.capability_registry = capability_registry
        self.capsule_registry = capsule_registry
        self.handler_registry = handler_registry
        self.provider_condition = provider_condition
        self.current_fence = current_fence
        self.trusted_clock = trusted_clock
        self.runtime_profile = runtime_profile
        self.handler_contract = GitHubCreateRefHandlerContract()

    def _load_consumption(self, *, prepared: CanonicalPreparedExecution) -> GrantConsumptionWitness:
        consumption_id = _require_digest(
            getattr(prepared.outbox, "consumption_id", None),
            field="outbox.consumption_id",
        )
        with self.db.connect() as connection:
            row = connection.execute(SELECT_CONSUMPTION_FOR_A09, (consumption_id,)).fetchone()
        if row is None:
            raise PermissionError("A09_CONSUMPTION_NOT_FOUND")
        try:
            raw = json.loads(str(row["consumption_json"]))
            witness = GrantConsumptionWitness.from_dict(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PermissionError("A09_CONSUMPTION_INVALID") from exc
        if str(row["consumption_id"]) != witness.consumption_id:
            raise PermissionError("A09_CONSUMPTION_ID_MISMATCH")
        if str(row["witness_digest"]) != witness.witness_digest:
            raise PermissionError("A09_CONSUMPTION_DIGEST_MISMATCH")
        if witness.consumption_id != consumption_id:
            raise PermissionError("A09_CONSUMPTION_OUTBOX_MISMATCH")
        if witness.witness_digest != getattr(prepared.outbox, "consumption_witness_digest", None):
            raise PermissionError("A09_CONSUMPTION_WITNESS_MISMATCH")
        if witness.grant_digest != prepared.grant_digest:
            raise PermissionError("A09_CONSUMPTION_GRANT_MISMATCH")
        return witness

    def prepare(self, *, prepared: CanonicalPreparedExecution) -> A09PreparedCreateRef:
        if not isinstance(prepared, CanonicalPreparedExecution):
            raise ValueError("prepared must be CanonicalPreparedExecution")
        if prepared.terminal_profile != BOUNDED_MUTATION_TERMINAL_PROFILE:
            raise PermissionError("A09_CREATE_REF_TERMINAL_PROFILE_MISMATCH")
        if prepared.capability != GITHUB_CREATE_REF_CAPABILITY:
            raise PermissionError("A09_CREATE_REF_CAPABILITY_MISMATCH")
        if getattr(prepared.snapshot, "execution_target", None) is None:
            raise ValueError("prepared snapshot has no execution target")

        definition = self.capability_registry.definition_by_identity(
            prepared.capability_definition_identity
        )
        if definition.capability != GITHUB_CREATE_REF_CAPABILITY:
            raise PermissionError("A09_CREATE_REF_DEFINITION_MISMATCH")
        capsule = self.capsule_registry.capsule_for_definition(
            prepared.capability_definition_identity
        )
        if capsule.capsule_digest != prepared.execution_capsule_digest:
            raise PermissionError("A09_CREATE_REF_CAPSULE_MISMATCH")
        handler_evidence = self.handler_registry.resolve(capsule.capsule_digest)
        requirement = ControlledWriteRequirement.create(
            definition=definition,
            capsule=capsule,
            handler_evidence=handler_evidence,
            provider_condition=self.provider_condition,
            requirement_revision=self.runtime_profile.requirement_revision,
        )

        bootstrap = IsolatedRuntimeBootstrap.create(
            provider=self.runtime_profile.provider,
            provider_instance_id=self.runtime_profile.provider_instance_id,
            runner_class=WRITE_RUNNER_CLASS,
            environment=prepared.environment,
            rootfs_digest=self.runtime_profile.rootfs_digest,
            resource_limit_profile_digest=self.runtime_profile.resource_limit_profile_digest,
            network_policy_digest=self.runtime_profile.network_policy_digest,
            bootstrap_revision=self.runtime_profile.bootstrap_revision,
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
        boundary = RunnerBoundaryV2.create(
            identity=identity,
            lease=prepared.lease,  # type: ignore[arg-type]
            capsule=capsule,
            definition=definition,
            handler_evidence=handler_evidence,
            provider_condition=self.provider_condition,
            requirement=requirement,
            boundary_revision=self.runtime_profile.boundary_revision,
        )
        policy = CredentialBrokerPolicyV2.create(
            boundary=boundary,
            max_ttl_seconds=self.runtime_profile.max_credential_ttl_seconds,
            policy_revision=self.runtime_profile.credential_policy_revision,
        )
        decision = CredentialAccessDecisionV2.create(
            boundary=boundary,
            lease=prepared.lease,  # type: ignore[arg-type]
            policy=policy,
            decision_revision=self.runtime_profile.credential_decision_revision,
        )
        delivery_clock = self.trusted_clock.witness(environment=prepared.environment)
        delivery = EphemeralWriteCredentialDelivery.create(
            bootstrap=bootstrap,
            identity=identity,
            boundary=boundary,
            decision=decision,
            lease=prepared.lease,  # type: ignore[arg-type]
            clock_witness=delivery_clock,
            delivery_revision=self.runtime_profile.credential_delivery_revision,
        )
        activation = WriteRuntimeActivation.create(
            bootstrap=bootstrap,
            identity=identity,
            boundary=boundary,
            decision=decision,
            delivery=delivery,
            lease=prepared.lease,  # type: ignore[arg-type]
            activation_revision=self.runtime_profile.activation_revision,
        )

        target = prepared.snapshot.execution_target
        if target.target_digest != prepared.target_digest:
            raise PermissionError("A09_CREATE_REF_TARGET_MISMATCH")
        target_binding = TargetBinding.create(
            binder_id=GITHUB_CREATE_REF_BINDER_ID,
            capability_definition_identity=prepared.capability_definition_identity,
            target=target,
        )
        request = self.handler_contract.prepare_request(
            target_binding=target_binding,
            boundary=boundary,
            decision=decision,
            request_revision=self.runtime_profile.request_revision,
        )
        consumption = self._load_consumption(prepared=prepared)
        preflight = WriteEffectPreflight.verify(
            grant=prepared.grant,  # type: ignore[arg-type]
            consumption=consumption,
            outbox=prepared.outbox,  # type: ignore[arg-type]
            envelope=prepared.envelope,  # type: ignore[arg-type]
            admission=prepared.admission,  # type: ignore[arg-type]
            lease=prepared.lease,  # type: ignore[arg-type]
            identity=identity,
            boundary=boundary,
            policy=policy,
            decision=decision,
            delivery=delivery,
            delivery_clock_witness=delivery_clock,
            activation=activation,
            request=request,
            current_fence=self.current_fence,
            trusted_clock=self.trusted_clock,
            preflight_revision=self.runtime_profile.preflight_revision,
        )
        return A09PreparedCreateRef(
            prepared=prepared,
            consumption=consumption,
            bootstrap=bootstrap,
            identity=identity,
            requirement=requirement,
            boundary=boundary,
            credential_policy=policy,
            credential_decision=decision,
            credential_delivery=delivery,
            activation=activation,
            target_binding=target_binding,
            request=request,
            preflight=preflight,
        )
