from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Protocol, Self, runtime_checkable

from .authoritative_grant import ExecutionGrantV2
from .controlled_write import (
    CREATE_REF_OPERATION,
    GITHUB_CREATE_REF_CAPABILITY,
    MAX_PROVIDER_MUTATIONS_R1,
    MUTATION_REVERSIBLE_EFFECT_CLASS,
    STAGING_ENVIRONMENT,
)
from .dispatch_envelope import DispatchEnvelope
from .dispatch_inbox import DispatchInboxAdmission
from .dispatch_outbox import DispatchOutboxEntry
from .evidence_primitives import canonical_json
from .execution_lease import ExecutionLease
from .github_create_ref_provider import GitHubCreateRefRequest
from .grant_consumption import GrantConsumptionWitness
from .isolated_runner import CurrentExecutionFence, IsolatedRuntimeBootstrap, READ_ONLY_MOUNT_MODE
from .precondition_witness import ATOMIC_PROVIDER_CONDITION
from .runner_identity import DENY_ALL_NETWORK_DEFAULT, RunnerIdentity
from .trusted_clock import ClockWitness, TrustedClockAuthority
from .write_boundary import (
    GITHUB_API_AUDIENCE,
    GITHUB_CREATE_REF_CREDENTIAL_CLASS,
    GITHUB_PROVIDER,
    WRITE_BOUNDED_ACCESS_MODE,
    WRITE_RUNNER_CLASS,
    CredentialAccessDecisionV2,
    CredentialBrokerPolicyV2,
    RunnerBoundaryV2,
)

EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE: Final = "ephemeral-write-credential-delivery/v1"
WRITE_RUNTIME_ACTIVATION_TYPE: Final = "write-runtime-activation/v1"
WRITE_EFFECT_PREFLIGHT_TYPE: Final = "write-effect-preflight/v1"
OUT_OF_BAND_SECRET_CHANNEL: Final = "out-of-band-secret-channel/v1"

_DELIVERY_FIELDS = frozenset(
    {
        "schema_version",
        "delivery_type",
        "runtime_provider",
        "provider_instance_id",
        "runner_id",
        "runner_boundary_digest",
        "credential_decision_id",
        "credential_decision_digest",
        "credential_provider",
        "credential_class",
        "audience",
        "environment",
        "access_mode",
        "provider_operation",
        "valid_from",
        "expires_at",
        "delivery_channel_identity",
        "clock_witness_digest",
        "delivered_at",
        "secret_material_exposed",
        "delivery_revision",
        "delivery_digest",
    }
)

_ACTIVATION_FIELDS = frozenset(
    {
        "schema_version",
        "activation_type",
        "runtime_provider",
        "provider_instance_id",
        "runner_id",
        "runner_identity_digest",
        "runner_boundary_digest",
        "credential_decision_id",
        "credential_decision_digest",
        "credential_delivery_digest",
        "lease_id",
        "lease_digest",
        "execution_id",
        "execution_epoch",
        "execution_capsule_digest",
        "capability_definition_identity",
        "environment",
        "runner_class",
        "access_mode",
        "workspace_mount_mode",
        "network_egress_default",
        "provider_operation",
        "provider_mutation_allowed",
        "max_provider_mutations",
        "activation_revision",
        "activation_digest",
    }
)

_PREFLIGHT_FIELDS = frozenset(
    {
        "schema_version",
        "preflight_type",
        "grant_digest",
        "consumption_witness_digest",
        "outbox_entry_digest",
        "dispatch_envelope_digest",
        "admission_digest",
        "lease_digest",
        "runner_id",
        "runner_identity_digest",
        "runner_boundary_digest",
        "credential_decision_digest",
        "credential_delivery_digest",
        "runtime_activation_digest",
        "target_digest",
        "request_digest",
        "capability_definition_identity",
        "execution_id",
        "execution_epoch",
        "environment",
        "effect_ceiling",
        "provider_operation",
        "max_provider_mutations",
        "clock_witness_digest",
        "checked_at",
        "preflight_revision",
        "preflight_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
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


def _timestamp(value: object, *, field: str) -> datetime:
    text = _require_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return parsed.astimezone(UTC)


def _require_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        raise ValueError(
            f"{contract} fields are invalid; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


class WriteRuntimeDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class WriteEffectPreflightDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@runtime_checkable
class EphemeralWriteCredentialChannel(Protocol):
    """Future out-of-band secret channel. F4a provides no implementation."""

    source_identity: str

    def deliver(
        self,
        *,
        bootstrap: IsolatedRuntimeBootstrap,
        identity: RunnerIdentity,
        boundary: RunnerBoundaryV2,
        decision: CredentialAccessDecisionV2,
        lease: ExecutionLease,
    ) -> EphemeralWriteCredentialDelivery: ...


@runtime_checkable
class WriteRuntimeProvider(Protocol):
    """Future write-runtime provider. F4a provides no implementation."""

    def activate_write(
        self,
        *,
        bootstrap: IsolatedRuntimeBootstrap,
        identity: RunnerIdentity,
        boundary: RunnerBoundaryV2,
        decision: CredentialAccessDecisionV2,
        delivery: EphemeralWriteCredentialDelivery,
        lease: ExecutionLease,
    ) -> WriteRuntimeActivation: ...


@dataclass(frozen=True, slots=True)
class EphemeralWriteCredentialDelivery:
    """Provider/channel-reported delivery metadata; never secret material or authority.

    ``create`` validates/constructs the expected metadata value. It does not deliver a
    credential and does not prove secret possession or a provider effect.
    """

    runtime_provider: str
    provider_instance_id: str
    runner_id: str
    runner_boundary_digest: str
    credential_decision_id: str
    credential_decision_digest: str
    credential_provider: str
    credential_class: str
    audience: str
    environment: str
    access_mode: str
    provider_operation: str
    valid_from: str
    expires_at: str
    delivery_channel_identity: str
    clock_witness_digest: str
    delivered_at: str
    secret_material_exposed: bool
    delivery_revision: str
    delivery_digest: str

    def __post_init__(self) -> None:
        for field in (
            "runtime_provider",
            "provider_instance_id",
            "credential_provider",
            "credential_class",
            "audience",
            "environment",
            "access_mode",
            "provider_operation",
            "delivery_channel_identity",
            "delivery_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "runner_id",
            "runner_boundary_digest",
            "credential_decision_id",
            "credential_decision_digest",
            "clock_witness_digest",
            "delivery_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        valid_from = _timestamp(self.valid_from, field="valid_from")
        expires_at = _timestamp(self.expires_at, field="expires_at")
        delivered_at = _timestamp(self.delivered_at, field="delivered_at")
        if not valid_from <= delivered_at < expires_at:
            raise ValueError("credential delivery must occur inside decision lifetime")
        if self.credential_provider != GITHUB_PROVIDER:
            raise ValueError("F4a credential provider must be github")
        if self.credential_class != GITHUB_CREATE_REF_CREDENTIAL_CLASS:
            raise ValueError("F4a credential class is invalid")
        if self.audience != GITHUB_API_AUDIENCE:
            raise ValueError("F4a credential audience is invalid")
        if self.environment != STAGING_ENVIRONMENT:
            raise ValueError("F4a credential delivery is staging-only")
        if self.access_mode != WRITE_BOUNDED_ACCESS_MODE:
            raise ValueError("F4a credential delivery must be WRITE_BOUNDED")
        if self.provider_operation != CREATE_REF_OPERATION:
            raise ValueError("F4a credential delivery operation must be CREATE_REF")
        if self.delivery_channel_identity != OUT_OF_BAND_SECRET_CHANNEL:
            raise ValueError("F4a credential delivery channel is unsupported")
        if self.secret_material_exposed is not False:
            raise ValueError("F4a evidence must never expose secret material")
        if self.delivery_digest != _digest(self._claims()):
            raise ValueError("delivery_digest does not match ephemeral-write-credential-delivery/v1")

    @classmethod
    def create(
        cls,
        *,
        bootstrap: IsolatedRuntimeBootstrap,
        identity: RunnerIdentity,
        boundary: RunnerBoundaryV2,
        decision: CredentialAccessDecisionV2,
        lease: ExecutionLease,
        clock_witness: ClockWitness,
        delivery_revision: str,
    ) -> Self:
        _assert_write_binding(
            bootstrap=bootstrap,
            identity=identity,
            boundary=boundary,
            decision=decision,
            lease=lease,
        )
        if not isinstance(clock_witness, ClockWitness):
            raise ValueError("clock_witness must be ClockWitness")
        if clock_witness.environment != lease.environment:
            raise WriteRuntimeDenied("F4A_CREDENTIAL_CLOCK_ENVIRONMENT_MISMATCH")
        delivered_at = _timestamp(clock_witness.observed_at, field="clock_witness.observed_at")
        valid_from = _timestamp(decision.valid_from, field="decision.valid_from")
        expires_at = _timestamp(decision.expires_at, field="decision.expires_at")
        if delivered_at < valid_from:
            raise WriteRuntimeDenied("F4A_CREDENTIAL_NOT_YET_VALID")
        if delivered_at >= expires_at:
            raise WriteRuntimeDenied("F4A_CREDENTIAL_EXPIRED")
        claims = {
            "schema_version": 1,
            "delivery_type": EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE,
            "runtime_provider": bootstrap.provider,
            "provider_instance_id": bootstrap.provider_instance_id,
            "runner_id": identity.runner_id,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_id": decision.decision_id,
            "credential_decision_digest": decision.decision_digest,
            "credential_provider": decision.provider,
            "credential_class": decision.credential_class,
            "audience": decision.audience,
            "environment": decision.environment,
            "access_mode": decision.access_mode,
            "provider_operation": decision.provider_operation,
            "valid_from": decision.valid_from,
            "expires_at": decision.expires_at,
            "delivery_channel_identity": OUT_OF_BAND_SECRET_CHANNEL,
            "clock_witness_digest": clock_witness.witness_digest,
            "delivered_at": clock_witness.observed_at,
            "secret_material_exposed": False,
            "delivery_revision": _require_text(delivery_revision, field="delivery_revision"),
        }
        return cls(
            **{
                key: item
                for key, item in claims.items()
                if key not in {"schema_version", "delivery_type"}
            },
            delivery_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_fields(value, _DELIVERY_FIELDS, contract=EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE)
        if (
            value["schema_version"] != 1
            or value["delivery_type"] != EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE
        ):
            raise ValueError("ephemeral-write-credential-delivery/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _DELIVERY_FIELDS
                if key not in {"schema_version", "delivery_type"}
            }
        )

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "delivery_type": EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE,
            "runtime_provider": self.runtime_provider,
            "provider_instance_id": self.provider_instance_id,
            "runner_id": self.runner_id,
            "runner_boundary_digest": self.runner_boundary_digest,
            "credential_decision_id": self.credential_decision_id,
            "credential_decision_digest": self.credential_decision_digest,
            "credential_provider": self.credential_provider,
            "credential_class": self.credential_class,
            "audience": self.audience,
            "environment": self.environment,
            "access_mode": self.access_mode,
            "provider_operation": self.provider_operation,
            "valid_from": self.valid_from,
            "expires_at": self.expires_at,
            "delivery_channel_identity": self.delivery_channel_identity,
            "clock_witness_digest": self.clock_witness_digest,
            "delivered_at": self.delivered_at,
            "secret_material_exposed": self.secret_material_exposed,
            "delivery_revision": self.delivery_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "delivery_digest": self.delivery_digest}


@dataclass(frozen=True, slots=True)
class WriteRuntimeActivation:
    """Write-specific activation metadata; does not activate a runtime itself."""

    runtime_provider: str
    provider_instance_id: str
    runner_id: str
    runner_identity_digest: str
    runner_boundary_digest: str
    credential_decision_id: str
    credential_decision_digest: str
    credential_delivery_digest: str
    lease_id: str
    lease_digest: str
    execution_id: str
    execution_epoch: int
    execution_capsule_digest: str
    capability_definition_identity: str
    environment: str
    runner_class: str
    access_mode: str
    workspace_mount_mode: str
    network_egress_default: str
    provider_operation: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    activation_revision: str
    activation_digest: str

    def __post_init__(self) -> None:
        for field in (
            "runtime_provider",
            "provider_instance_id",
            "execution_id",
            "environment",
            "runner_class",
            "access_mode",
            "workspace_mount_mode",
            "network_egress_default",
            "provider_operation",
            "activation_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "runner_id",
            "runner_identity_digest",
            "runner_boundary_digest",
            "credential_decision_id",
            "credential_decision_digest",
            "credential_delivery_digest",
            "lease_id",
            "lease_digest",
            "execution_capsule_digest",
            "capability_definition_identity",
            "activation_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if isinstance(self.execution_epoch, bool) or not isinstance(self.execution_epoch, int):
            raise ValueError("execution_epoch must be an integer")
        if self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.environment != STAGING_ENVIRONMENT:
            raise ValueError("F4a write runtime is staging-only")
        if self.runner_class != WRITE_RUNNER_CLASS:
            raise ValueError("F4a write runner class is invalid")
        if self.access_mode != WRITE_BOUNDED_ACCESS_MODE:
            raise ValueError("F4a write runtime must be WRITE_BOUNDED")
        if self.workspace_mount_mode != READ_ONLY_MOUNT_MODE:
            raise ValueError("F4a workspace mount must remain READ_ONLY")
        if self.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise ValueError("F4a network default must remain DENY_ALL")
        if self.provider_operation != CREATE_REF_OPERATION:
            raise ValueError("F4a provider operation must be CREATE_REF")
        if self.provider_mutation_allowed is not True:
            raise ValueError("F4a activation must preserve the bounded mutation ceiling")
        if self.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise ValueError("F4a activation allows exactly one provider mutation")
        if self.activation_digest != _digest(self._claims()):
            raise ValueError("activation_digest does not match write-runtime-activation/v1")

    @classmethod
    def create(
        cls,
        *,
        bootstrap: IsolatedRuntimeBootstrap,
        identity: RunnerIdentity,
        boundary: RunnerBoundaryV2,
        decision: CredentialAccessDecisionV2,
        delivery: EphemeralWriteCredentialDelivery,
        lease: ExecutionLease,
        activation_revision: str,
    ) -> Self:
        _assert_write_binding(
            bootstrap=bootstrap,
            identity=identity,
            boundary=boundary,
            decision=decision,
            lease=lease,
        )
        _assert_delivery(
            delivery=delivery,
            identity=identity,
            boundary=boundary,
            decision=decision,
            runtime_provider=bootstrap.provider,
            provider_instance_id=bootstrap.provider_instance_id,
        )
        claims = {
            "schema_version": 1,
            "activation_type": WRITE_RUNTIME_ACTIVATION_TYPE,
            "runtime_provider": bootstrap.provider,
            "provider_instance_id": bootstrap.provider_instance_id,
            "runner_id": identity.runner_id,
            "runner_identity_digest": identity.identity_digest,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_id": decision.decision_id,
            "credential_decision_digest": decision.decision_digest,
            "credential_delivery_digest": delivery.delivery_digest,
            "lease_id": lease.lease_id,
            "lease_digest": lease.lease_digest,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "execution_capsule_digest": lease.execution_capsule_digest,
            "capability_definition_identity": boundary.capability_definition_identity,
            "environment": lease.environment,
            "runner_class": identity.runner_class,
            "access_mode": WRITE_BOUNDED_ACCESS_MODE,
            "workspace_mount_mode": READ_ONLY_MOUNT_MODE,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "provider_operation": CREATE_REF_OPERATION,
            "provider_mutation_allowed": True,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "activation_revision": _require_text(activation_revision, field="activation_revision"),
        }
        return cls(
            **{
                key: item
                for key, item in claims.items()
                if key not in {"schema_version", "activation_type"}
            },
            activation_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_fields(value, _ACTIVATION_FIELDS, contract=WRITE_RUNTIME_ACTIVATION_TYPE)
        if (
            value["schema_version"] != 1
            or value["activation_type"] != WRITE_RUNTIME_ACTIVATION_TYPE
        ):
            raise ValueError("write-runtime-activation/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _ACTIVATION_FIELDS
                if key not in {"schema_version", "activation_type"}
            }
        )

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "activation_type": WRITE_RUNTIME_ACTIVATION_TYPE,
            "runtime_provider": self.runtime_provider,
            "provider_instance_id": self.provider_instance_id,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "runner_boundary_digest": self.runner_boundary_digest,
            "credential_decision_id": self.credential_decision_id,
            "credential_decision_digest": self.credential_decision_digest,
            "credential_delivery_digest": self.credential_delivery_digest,
            "lease_id": self.lease_id,
            "lease_digest": self.lease_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "environment": self.environment,
            "runner_class": self.runner_class,
            "access_mode": self.access_mode,
            "workspace_mount_mode": self.workspace_mount_mode,
            "network_egress_default": self.network_egress_default,
            "provider_operation": self.provider_operation,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "max_provider_mutations": self.max_provider_mutations,
            "activation_revision": self.activation_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "activation_digest": self.activation_digest}


@dataclass(frozen=True, slots=True)
class WriteEffectPreflight:
    """Fail-closed readiness evidence immediately before a future provider mutation.

    It is not an ExecutionReceipt, VerificationResult or OperationProof. F4a never
    invokes the GitHub create-ref transport.
    """

    grant_digest: str
    consumption_witness_digest: str
    outbox_entry_digest: str
    dispatch_envelope_digest: str
    admission_digest: str
    lease_digest: str
    runner_id: str
    runner_identity_digest: str
    runner_boundary_digest: str
    credential_decision_digest: str
    credential_delivery_digest: str
    runtime_activation_digest: str
    target_digest: str
    request_digest: str
    capability_definition_identity: str
    execution_id: str
    execution_epoch: int
    environment: str
    effect_ceiling: str
    provider_operation: str
    max_provider_mutations: int
    clock_witness_digest: str
    checked_at: str
    preflight_revision: str
    preflight_digest: str

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "environment",
            "effect_ceiling",
            "provider_operation",
            "preflight_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "grant_digest",
            "consumption_witness_digest",
            "outbox_entry_digest",
            "dispatch_envelope_digest",
            "admission_digest",
            "lease_digest",
            "runner_id",
            "runner_identity_digest",
            "runner_boundary_digest",
            "credential_decision_digest",
            "credential_delivery_digest",
            "runtime_activation_digest",
            "target_digest",
            "request_digest",
            "capability_definition_identity",
            "clock_witness_digest",
            "preflight_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if isinstance(self.execution_epoch, bool) or not isinstance(self.execution_epoch, int):
            raise ValueError("execution_epoch must be an integer")
        if self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.environment != STAGING_ENVIRONMENT:
            raise ValueError("F4a preflight is staging-only")
        if self.effect_ceiling != MUTATION_REVERSIBLE_EFFECT_CLASS:
            raise ValueError("F4a preflight effect ceiling is invalid")
        if self.provider_operation != CREATE_REF_OPERATION:
            raise ValueError("F4a preflight provider operation must be CREATE_REF")
        if self.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise ValueError("F4a preflight allows exactly one provider mutation")
        _timestamp(self.checked_at, field="checked_at")
        if self.preflight_digest != _digest(self._claims()):
            raise ValueError("preflight_digest does not match write-effect-preflight/v1")

    @classmethod
    def verify(
        cls,
        *,
        grant: ExecutionGrantV2,
        consumption: GrantConsumptionWitness,
        outbox: DispatchOutboxEntry,
        envelope: DispatchEnvelope,
        admission: DispatchInboxAdmission,
        lease: ExecutionLease,
        identity: RunnerIdentity,
        boundary: RunnerBoundaryV2,
        policy: CredentialBrokerPolicyV2,
        decision: CredentialAccessDecisionV2,
        delivery: EphemeralWriteCredentialDelivery,
        delivery_clock_witness: ClockWitness,
        activation: WriteRuntimeActivation,
        request: GitHubCreateRefRequest,
        current_fence: CurrentExecutionFence,
        trusted_clock: TrustedClockAuthority,
        preflight_revision: str,
    ) -> Self:
        if not isinstance(current_fence, CurrentExecutionFence):
            raise ValueError("current_fence must implement CurrentExecutionFence")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock must be TrustedClockAuthority")
        for value, expected, field in (
            (grant, ExecutionGrantV2, "grant"),
            (consumption, GrantConsumptionWitness, "consumption"),
            (outbox, DispatchOutboxEntry, "outbox"),
            (envelope, DispatchEnvelope, "envelope"),
            (admission, DispatchInboxAdmission, "admission"),
            (lease, ExecutionLease, "lease"),
            (identity, RunnerIdentity, "identity"),
            (boundary, RunnerBoundaryV2, "boundary"),
            (policy, CredentialBrokerPolicyV2, "policy"),
            (decision, CredentialAccessDecisionV2, "decision"),
            (delivery, EphemeralWriteCredentialDelivery, "delivery"),
            (delivery_clock_witness, ClockWitness, "delivery_clock_witness"),
            (activation, WriteRuntimeActivation, "activation"),
            (request, GitHubCreateRefRequest, "request"),
        ):
            if not isinstance(value, expected):
                raise ValueError(f"{field} has invalid type")
        _require_text(preflight_revision, field="preflight_revision")

        _assert_authority_chain(
            grant=grant,
            consumption=consumption,
            outbox=outbox,
            envelope=envelope,
            admission=admission,
            lease=lease,
        )
        _assert_write_binding(
            bootstrap=None,
            identity=identity,
            boundary=boundary,
            decision=decision,
            lease=lease,
        )
        decision.assert_bound_to(boundary=boundary, lease=lease, policy=policy)
        _assert_delivery(
            delivery=delivery,
            identity=identity,
            boundary=boundary,
            decision=decision,
            runtime_provider=activation.runtime_provider,
            provider_instance_id=activation.provider_instance_id,
        )
        if delivery_clock_witness.environment != lease.environment:
            raise WriteEffectPreflightDenied("F4A_DELIVERY_CLOCK_ENVIRONMENT_MISMATCH")
        if delivery_clock_witness.witness_digest != delivery.clock_witness_digest:
            raise WriteEffectPreflightDenied("F4A_DELIVERY_CLOCK_WITNESS_MISMATCH")
        if delivery_clock_witness.observed_at != delivery.delivered_at:
            raise WriteEffectPreflightDenied("F4A_DELIVERY_CLOCK_TIME_MISMATCH")
        _assert_activation(
            activation=activation,
            identity=identity,
            boundary=boundary,
            decision=decision,
            delivery=delivery,
            lease=lease,
        )
        _assert_request(grant=grant, boundary=boundary, decision=decision, request=request)

        clock_witness = trusted_clock.witness(environment=lease.environment)
        observed_at = _timestamp(clock_witness.observed_at, field="clock_witness.observed_at")
        valid_from = _timestamp(decision.valid_from, field="decision.valid_from")
        expires_at = _timestamp(decision.expires_at, field="decision.expires_at")
        delivered_at = _timestamp(delivery.delivered_at, field="delivery.delivered_at")
        if observed_at < valid_from:
            raise WriteEffectPreflightDenied("F4A_CREDENTIAL_NOT_YET_VALID")
        if observed_at >= expires_at:
            raise WriteEffectPreflightDenied("F4A_CREDENTIAL_EXPIRED")
        if delivered_at > observed_at:
            raise WriteEffectPreflightDenied("F4A_DELIVERY_CLOCK_ORDER_INVALID")

        # Final control-plane decision. F4b must rerun this immediately before create-ref.
        current_fence.assert_current(lease=lease)

        claims = {
            "schema_version": 1,
            "preflight_type": WRITE_EFFECT_PREFLIGHT_TYPE,
            "grant_digest": grant.grant_digest,
            "consumption_witness_digest": consumption.witness_digest,
            "outbox_entry_digest": outbox.entry_digest,
            "dispatch_envelope_digest": envelope.envelope_digest,
            "admission_digest": admission.admission_digest,
            "lease_digest": lease.lease_digest,
            "runner_id": identity.runner_id,
            "runner_identity_digest": identity.identity_digest,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_digest": decision.decision_digest,
            "credential_delivery_digest": delivery.delivery_digest,
            "runtime_activation_digest": activation.activation_digest,
            "target_digest": request.target_digest,
            "request_digest": request.request_digest,
            "capability_definition_identity": boundary.capability_definition_identity,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "environment": lease.environment,
            "effect_ceiling": MUTATION_REVERSIBLE_EFFECT_CLASS,
            "provider_operation": CREATE_REF_OPERATION,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "clock_witness_digest": clock_witness.witness_digest,
            "checked_at": clock_witness.observed_at,
            "preflight_revision": preflight_revision,
        }
        return cls(
            **{
                key: item
                for key, item in claims.items()
                if key not in {"schema_version", "preflight_type"}
            },
            preflight_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_fields(value, _PREFLIGHT_FIELDS, contract=WRITE_EFFECT_PREFLIGHT_TYPE)
        if (
            value["schema_version"] != 1
            or value["preflight_type"] != WRITE_EFFECT_PREFLIGHT_TYPE
        ):
            raise ValueError("write-effect-preflight/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _PREFLIGHT_FIELDS
                if key not in {"schema_version", "preflight_type"}
            }
        )

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "preflight_type": WRITE_EFFECT_PREFLIGHT_TYPE,
            "grant_digest": self.grant_digest,
            "consumption_witness_digest": self.consumption_witness_digest,
            "outbox_entry_digest": self.outbox_entry_digest,
            "dispatch_envelope_digest": self.dispatch_envelope_digest,
            "admission_digest": self.admission_digest,
            "lease_digest": self.lease_digest,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "runner_boundary_digest": self.runner_boundary_digest,
            "credential_decision_digest": self.credential_decision_digest,
            "credential_delivery_digest": self.credential_delivery_digest,
            "runtime_activation_digest": self.runtime_activation_digest,
            "target_digest": self.target_digest,
            "request_digest": self.request_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "environment": self.environment,
            "effect_ceiling": self.effect_ceiling,
            "provider_operation": self.provider_operation,
            "max_provider_mutations": self.max_provider_mutations,
            "clock_witness_digest": self.clock_witness_digest,
            "checked_at": self.checked_at,
            "preflight_revision": self.preflight_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "preflight_digest": self.preflight_digest}


def _assert_write_binding(
    *,
    bootstrap: IsolatedRuntimeBootstrap | None,
    identity: RunnerIdentity,
    boundary: RunnerBoundaryV2,
    decision: CredentialAccessDecisionV2,
    lease: ExecutionLease,
) -> None:
    if not isinstance(identity, RunnerIdentity):
        raise ValueError("identity must be RunnerIdentity")
    if not isinstance(boundary, RunnerBoundaryV2):
        raise ValueError("boundary must be RunnerBoundaryV2")
    if not isinstance(decision, CredentialAccessDecisionV2):
        raise ValueError("decision must be CredentialAccessDecisionV2")
    if not isinstance(lease, ExecutionLease):
        raise ValueError("lease must be ExecutionLease")
    identity.assert_bound_to_lease(lease)
    expected = {
        "runner_id": identity.runner_id,
        "runner_identity_digest": identity.identity_digest,
        "lease_id": lease.lease_id,
        "lease_digest": lease.lease_digest,
        "admission_id": lease.admission_id,
        "execution_id": lease.execution_id,
        "execution_epoch": lease.execution_epoch,
        "execution_capsule_digest": lease.execution_capsule_digest,
        "environment": STAGING_ENVIRONMENT,
        "runner_class": WRITE_RUNNER_CLASS,
        "credential_class": GITHUB_CREATE_REF_CREDENTIAL_CLASS,
        "provider_mutation_allowed": True,
        "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
    }
    actual = {
        "runner_id": boundary.runner_id,
        "runner_identity_digest": boundary.runner_identity_digest,
        "lease_id": boundary.lease_id,
        "lease_digest": boundary.lease_digest,
        "admission_id": boundary.admission_id,
        "execution_id": boundary.execution_id,
        "execution_epoch": boundary.execution_epoch,
        "execution_capsule_digest": boundary.execution_capsule_digest,
        "environment": boundary.environment,
        "runner_class": boundary.runner_class,
        "credential_class": boundary.credential_class,
        "provider_mutation_allowed": boundary.provider_mutation_allowed,
        "max_provider_mutations": boundary.max_provider_mutations,
    }
    if actual != expected:
        raise WriteRuntimeDenied("F4A_RUNNER_BOUNDARY_BINDING_MISMATCH")
    if decision.runner_boundary_digest != boundary.boundary_digest:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_BOUNDARY_MISMATCH")
    if decision.runner_id != identity.runner_id:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_RUNNER_MISMATCH")
    if decision.runner_identity_digest != identity.identity_digest:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_IDENTITY_MISMATCH")
    if decision.lease_id != lease.lease_id or decision.lease_digest != lease.lease_digest:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_LEASE_MISMATCH")
    if decision.execution_id != lease.execution_id or decision.execution_epoch != lease.execution_epoch:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_EXECUTION_MISMATCH")
    if decision.execution_capsule_digest != lease.execution_capsule_digest:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_CAPSULE_MISMATCH")
    if decision.capability_definition_identity != boundary.capability_definition_identity:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_CAPABILITY_MISMATCH")
    if decision.controlled_write_requirement_digest != boundary.controlled_write_requirement_digest:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_REQUIREMENT_MISMATCH")
    if decision.atomic_provider_condition_contract_identity != boundary.atomic_provider_condition_contract_identity:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_PROVIDER_CONDITION_MISMATCH")
    if (
        decision.provider != GITHUB_PROVIDER
        or decision.audience != GITHUB_API_AUDIENCE
        or decision.credential_class != GITHUB_CREATE_REF_CREDENTIAL_CLASS
        or decision.environment != STAGING_ENVIRONMENT
        or decision.access_mode != WRITE_BOUNDED_ACCESS_MODE
        or decision.provider_operation != CREATE_REF_OPERATION
        or decision.provider_mutation_allowed is not True
        or decision.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1
    ):
        raise WriteRuntimeDenied("F4A_CREDENTIAL_SCOPE_MISMATCH")
    if bootstrap is not None:
        if not isinstance(bootstrap, IsolatedRuntimeBootstrap):
            raise ValueError("bootstrap must be IsolatedRuntimeBootstrap")
        bootstrap_expected = {
            "provider": identity.provider,
            "provider_instance_id": identity.provider_instance_id,
            "runner_class": identity.runner_class,
            "environment": identity.environment,
            "rootfs_digest": identity.rootfs_digest,
            "resource_limit_profile_digest": identity.resource_limit_profile_digest,
            "network_policy_digest": identity.network_policy_digest,
            "workspace_mount_mode": READ_ONLY_MOUNT_MODE,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "inherited_credentials": False,
            "provider_mutation_allowed": False,
        }
        bootstrap_actual = {
            "provider": bootstrap.provider,
            "provider_instance_id": bootstrap.provider_instance_id,
            "runner_class": bootstrap.runner_class,
            "environment": bootstrap.environment,
            "rootfs_digest": bootstrap.rootfs_digest,
            "resource_limit_profile_digest": bootstrap.resource_limit_profile_digest,
            "network_policy_digest": bootstrap.network_policy_digest,
            "workspace_mount_mode": bootstrap.workspace_mount_mode,
            "network_egress_default": bootstrap.network_egress_default,
            "inherited_credentials": bootstrap.inherited_credentials,
            "provider_mutation_allowed": bootstrap.provider_mutation_allowed,
        }
        if bootstrap_actual != bootstrap_expected:
            raise WriteRuntimeDenied("F4A_BOOTSTRAP_BINDING_MISMATCH")


def _assert_delivery(
    *,
    delivery: EphemeralWriteCredentialDelivery,
    identity: RunnerIdentity,
    boundary: RunnerBoundaryV2,
    decision: CredentialAccessDecisionV2,
    runtime_provider: str,
    provider_instance_id: str,
) -> None:
    expected = {
        "runtime_provider": runtime_provider,
        "provider_instance_id": provider_instance_id,
        "runner_id": identity.runner_id,
        "runner_boundary_digest": boundary.boundary_digest,
        "credential_decision_id": decision.decision_id,
        "credential_decision_digest": decision.decision_digest,
        "credential_provider": decision.provider,
        "credential_class": decision.credential_class,
        "audience": decision.audience,
        "environment": decision.environment,
        "access_mode": decision.access_mode,
        "provider_operation": decision.provider_operation,
        "valid_from": decision.valid_from,
        "expires_at": decision.expires_at,
        "delivery_channel_identity": OUT_OF_BAND_SECRET_CHANNEL,
        "secret_material_exposed": False,
    }
    actual = {
        "runtime_provider": delivery.runtime_provider,
        "provider_instance_id": delivery.provider_instance_id,
        "runner_id": delivery.runner_id,
        "runner_boundary_digest": delivery.runner_boundary_digest,
        "credential_decision_id": delivery.credential_decision_id,
        "credential_decision_digest": delivery.credential_decision_digest,
        "credential_provider": delivery.credential_provider,
        "credential_class": delivery.credential_class,
        "audience": delivery.audience,
        "environment": delivery.environment,
        "access_mode": delivery.access_mode,
        "provider_operation": delivery.provider_operation,
        "valid_from": delivery.valid_from,
        "expires_at": delivery.expires_at,
        "delivery_channel_identity": delivery.delivery_channel_identity,
        "secret_material_exposed": delivery.secret_material_exposed,
    }
    if actual != expected:
        raise WriteRuntimeDenied("F4A_CREDENTIAL_DELIVERY_BINDING_MISMATCH")


def _assert_activation(
    *,
    activation: WriteRuntimeActivation,
    identity: RunnerIdentity,
    boundary: RunnerBoundaryV2,
    decision: CredentialAccessDecisionV2,
    delivery: EphemeralWriteCredentialDelivery,
    lease: ExecutionLease,
) -> None:
    expected = {
        "runtime_provider": identity.provider,
        "provider_instance_id": identity.provider_instance_id,
        "runner_id": identity.runner_id,
        "runner_identity_digest": identity.identity_digest,
        "runner_boundary_digest": boundary.boundary_digest,
        "credential_decision_id": decision.decision_id,
        "credential_decision_digest": decision.decision_digest,
        "credential_delivery_digest": delivery.delivery_digest,
        "lease_id": lease.lease_id,
        "lease_digest": lease.lease_digest,
        "execution_id": lease.execution_id,
        "execution_epoch": lease.execution_epoch,
        "execution_capsule_digest": lease.execution_capsule_digest,
        "capability_definition_identity": boundary.capability_definition_identity,
        "environment": STAGING_ENVIRONMENT,
        "runner_class": WRITE_RUNNER_CLASS,
        "access_mode": WRITE_BOUNDED_ACCESS_MODE,
        "workspace_mount_mode": READ_ONLY_MOUNT_MODE,
        "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
        "provider_operation": CREATE_REF_OPERATION,
        "provider_mutation_allowed": True,
        "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
    }
    actual = {
        "runtime_provider": activation.runtime_provider,
        "provider_instance_id": activation.provider_instance_id,
        "runner_id": activation.runner_id,
        "runner_identity_digest": activation.runner_identity_digest,
        "runner_boundary_digest": activation.runner_boundary_digest,
        "credential_decision_id": activation.credential_decision_id,
        "credential_decision_digest": activation.credential_decision_digest,
        "credential_delivery_digest": activation.credential_delivery_digest,
        "lease_id": activation.lease_id,
        "lease_digest": activation.lease_digest,
        "execution_id": activation.execution_id,
        "execution_epoch": activation.execution_epoch,
        "execution_capsule_digest": activation.execution_capsule_digest,
        "capability_definition_identity": activation.capability_definition_identity,
        "environment": activation.environment,
        "runner_class": activation.runner_class,
        "access_mode": activation.access_mode,
        "workspace_mount_mode": activation.workspace_mount_mode,
        "network_egress_default": activation.network_egress_default,
        "provider_operation": activation.provider_operation,
        "provider_mutation_allowed": activation.provider_mutation_allowed,
        "max_provider_mutations": activation.max_provider_mutations,
    }
    if actual != expected:
        raise WriteRuntimeDenied("F4A_RUNTIME_ACTIVATION_BINDING_MISMATCH")


def _assert_authority_chain(
    *,
    grant: ExecutionGrantV2,
    consumption: GrantConsumptionWitness,
    outbox: DispatchOutboxEntry,
    envelope: DispatchEnvelope,
    admission: DispatchInboxAdmission,
    lease: ExecutionLease,
) -> None:
    expected_consumption = (
        grant.jti,
        grant.grant_id,
        grant.grant_digest,
        grant.execution_id,
        grant.authorization_snapshot_digest,
        grant.execution_capsule_digest,
        grant.runner_class,
    )
    actual_consumption = (
        consumption.jti,
        consumption.grant_id,
        consumption.grant_digest,
        consumption.execution_id,
        consumption.authorization_snapshot_digest,
        consumption.execution_capsule_digest,
        consumption.runner_class,
    )
    if actual_consumption != expected_consumption:
        raise WriteEffectPreflightDenied("F4A_GRANT_CONSUMPTION_MISMATCH")
    if consumption.live_revocation_epoch != grant.revocation_epoch:
        raise WriteEffectPreflightDenied("F4A_GRANT_REVOCATION_EPOCH_MISMATCH")
    consumed_at = _timestamp(consumption.consumed_at, field="consumption.consumed_at")
    if not (
        _timestamp(grant.issued_at, field="grant.issued_at")
        <= consumed_at
        < _timestamp(grant.expires_at, field="grant.expires_at")
    ):
        raise WriteEffectPreflightDenied("F4A_GRANT_CONSUMPTION_TIME_INVALID")
    expected_outbox = DispatchOutboxEntry.create(
        outbox_id=outbox.outbox_id,
        grant=grant,
        consumption_witness=consumption,
        outbox_revision=outbox.outbox_revision,
    )
    if outbox != expected_outbox:
        raise WriteEffectPreflightDenied("F4A_OUTBOX_LINEAGE_MISMATCH")
    try:
        envelope.assert_bound_to(outbox)
        admission.assert_bound_to(envelope=envelope, outbox_entry=outbox)
        lease.assert_bound_to(admission)
    except PermissionError as exc:
        raise WriteEffectPreflightDenied("F4A_DISPATCH_LEASE_LINEAGE_MISMATCH") from exc


def _assert_request(
    *,
    grant: ExecutionGrantV2,
    boundary: RunnerBoundaryV2,
    decision: CredentialAccessDecisionV2,
    request: GitHubCreateRefRequest,
) -> None:
    if (
        grant.environment != STAGING_ENVIRONMENT
        or grant.capability != GITHUB_CREATE_REF_CAPABILITY
        or grant.precondition_enforcement_class != ATOMIC_PROVIDER_CONDITION
        or grant.runner_class != WRITE_RUNNER_CLASS
    ):
        raise WriteEffectPreflightDenied("F4A_GRANT_SCOPE_MISMATCH")
    if grant.execution_capsule_digest != boundary.execution_capsule_digest:
        raise WriteEffectPreflightDenied("F4A_GRANT_CAPSULE_MISMATCH")
    if grant.capability_definition_identity != boundary.capability_definition_identity:
        raise WriteEffectPreflightDenied("F4A_GRANT_CAPABILITY_DEFINITION_MISMATCH")
    if grant.target_digest != request.target_digest:
        raise WriteEffectPreflightDenied("F4A_TARGET_LINEAGE_MISMATCH")
    if request.capability_definition_identity != boundary.capability_definition_identity:
        raise WriteEffectPreflightDenied("F4A_REQUEST_CAPABILITY_MISMATCH")
    if request.runner_boundary_digest != boundary.boundary_digest:
        raise WriteEffectPreflightDenied("F4A_REQUEST_BOUNDARY_MISMATCH")
    if request.credential_decision_digest != decision.decision_digest:
        raise WriteEffectPreflightDenied("F4A_REQUEST_CREDENTIAL_DECISION_MISMATCH")
    if request.controlled_write_requirement_digest != boundary.controlled_write_requirement_digest:
        raise WriteEffectPreflightDenied("F4A_REQUEST_REQUIREMENT_MISMATCH")
    if request.atomic_provider_condition_contract_identity != boundary.atomic_provider_condition_contract_identity:
        raise WriteEffectPreflightDenied("F4A_REQUEST_PROVIDER_CONDITION_MISMATCH")
    if request.operation != CREATE_REF_OPERATION:
        raise WriteEffectPreflightDenied("F4A_REQUEST_OPERATION_MISMATCH")
    if request.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
        raise WriteEffectPreflightDenied("F4A_REQUEST_MUTATION_LIMIT_MISMATCH")
