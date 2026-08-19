from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget
from .rollback_control import (
    DELETE_REF_OPERATION,
    GITHUB_API_AUDIENCE,
    GITHUB_DELETE_REF_CREDENTIAL_CLASS,
    GITHUB_PROVIDER,
    READ_THEN_DELETE_NON_ATOMIC,
    WRITE_BOUNDED_ACCESS_MODE,
    CredentialAccessDecisionV3,
    GitHubDeleteRefConditionContract,
    GitHubDeleteRefRequest,
    RunnerBoundaryV3,
)

EPHEMERAL_ROLLBACK_CREDENTIAL_DELIVERY_TYPE: Final = (
    "ephemeral-rollback-credential-delivery/v1"
)
WRITE_RUNTIME_ACTIVATION_V2_TYPE: Final = "write-runtime-activation/v2"
WRITE_EFFECT_PREFLIGHT_V2_TYPE: Final = "write-effect-preflight/v2"
OUT_OF_BAND_ROLLBACK_CREDENTIAL_CHANNEL: Final = (
    "out-of-band-rollback-secret-channel/v1"
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _hex_digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _sha1(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if (
        len(text) != 40
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase 40-character Git object id")
    return text


def _timestamp(value: object, *, field: str) -> datetime:
    text = _text(value, field=field)
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


@dataclass(frozen=True, slots=True)
class EphemeralRollbackCredentialDelivery:
    runner_id: str
    runner_boundary_digest: str
    credential_decision_id: str
    credential_decision_digest: str
    provider_instance_id: str
    credential_provider: str
    credential_class: str
    audience: str
    access_mode: str
    provider_operation: str
    delivery_channel_identity: str
    delivered_at: str
    clock_witness_digest: str
    secret_material_exposed: bool
    delivery_revision: str
    delivery_digest: str

    def __post_init__(self) -> None:
        for field in (
            "runner_id",
            "runner_boundary_digest",
            "credential_decision_id",
            "credential_decision_digest",
            "clock_witness_digest",
            "delivery_digest",
        ):
            _hex_digest(getattr(self, field), field=field)
        for field in (
            "provider_instance_id",
            "credential_provider",
            "credential_class",
            "audience",
            "access_mode",
            "provider_operation",
            "delivery_channel_identity",
            "delivery_revision",
        ):
            _text(getattr(self, field), field=field)
        _timestamp(self.delivered_at, field="delivered_at")
        if self.credential_provider != GITHUB_PROVIDER:
            raise ValueError("rollback credential provider must be github")
        if self.credential_class != GITHUB_DELETE_REF_CREDENTIAL_CLASS:
            raise ValueError("rollback credential class is invalid")
        if self.audience != GITHUB_API_AUDIENCE:
            raise ValueError("rollback credential audience is invalid")
        if self.access_mode != WRITE_BOUNDED_ACCESS_MODE:
            raise ValueError("rollback credential delivery must be WRITE_BOUNDED")
        if self.provider_operation != DELETE_REF_OPERATION:
            raise ValueError("rollback credential delivery operation must be DELETE_REF")
        if self.delivery_channel_identity != OUT_OF_BAND_ROLLBACK_CREDENTIAL_CHANNEL:
            raise ValueError("rollback credential delivery channel is unsupported")
        if self.secret_material_exposed is not False:
            raise ValueError("rollback evidence must not expose secret material")
        if self.delivery_digest != _digest(self._claims()):
            raise ValueError("delivery_digest does not match rollback credential delivery")

    @classmethod
    def create(
        cls,
        *,
        boundary: RunnerBoundaryV3,
        decision: CredentialAccessDecisionV3,
        provider_instance_id: str,
        delivered_at: str,
        clock_witness_digest: str,
        delivery_revision: str,
    ) -> Self:
        if decision.runner_boundary_digest != boundary.boundary_digest:
            raise PermissionError("ROLLBACK_DELIVERY_BOUNDARY_MISMATCH")
        delivered = _timestamp(delivered_at, field="delivered_at")
        valid_from = _timestamp(decision.valid_from, field="decision.valid_from")
        expires_at = _timestamp(decision.expires_at, field="decision.expires_at")
        if not valid_from <= delivered < expires_at:
            raise PermissionError("ROLLBACK_CREDENTIAL_DELIVERY_OUTSIDE_LIFETIME")
        claims = {
            "schema_version": 1,
            "delivery_type": EPHEMERAL_ROLLBACK_CREDENTIAL_DELIVERY_TYPE,
            "runner_id": boundary.runner_id,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_id": decision.decision_id,
            "credential_decision_digest": decision.decision_digest,
            "provider_instance_id": _text(provider_instance_id, field="provider_instance_id"),
            "credential_provider": decision.provider,
            "credential_class": decision.credential_class,
            "audience": decision.audience,
            "access_mode": decision.access_mode,
            "provider_operation": decision.provider_operation,
            "delivery_channel_identity": OUT_OF_BAND_ROLLBACK_CREDENTIAL_CHANNEL,
            "delivered_at": delivered_at,
            "clock_witness_digest": _hex_digest(clock_witness_digest, field="clock_witness_digest"),
            "secret_material_exposed": False,
            "delivery_revision": _text(delivery_revision, field="delivery_revision"),
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "delivery_type"}
        }
        return cls(**values, delivery_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "delivery_type": EPHEMERAL_ROLLBACK_CREDENTIAL_DELIVERY_TYPE,
            **{
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "delivery_digest"
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "delivery_digest": self.delivery_digest}


@dataclass(frozen=True, slots=True)
class RollbackWriteRuntimeActivation:
    runner_id: str
    runner_boundary_digest: str
    credential_decision_digest: str
    credential_delivery_digest: str
    lease_id: str
    lease_digest: str
    execution_id: str
    execution_epoch: int
    capability_definition_identity: str
    rollback_requirement_digest: str
    provider_instance_id: str
    access_mode: str
    provider_operation: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    temporal_model: str
    activation_revision: str
    activation_digest: str

    def __post_init__(self) -> None:
        for field in (
            "runner_id",
            "runner_boundary_digest",
            "credential_decision_digest",
            "credential_delivery_digest",
            "lease_id",
            "lease_digest",
            "capability_definition_identity",
            "rollback_requirement_digest",
            "activation_digest",
        ):
            _hex_digest(getattr(self, field), field=field)
        for field in (
            "execution_id",
            "provider_instance_id",
            "access_mode",
            "provider_operation",
            "temporal_model",
            "activation_revision",
        ):
            _text(getattr(self, field), field=field)
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.access_mode != WRITE_BOUNDED_ACCESS_MODE:
            raise ValueError("rollback runtime activation must be WRITE_BOUNDED")
        if self.provider_operation != DELETE_REF_OPERATION:
            raise ValueError("rollback runtime activation operation must be DELETE_REF")
        if self.provider_mutation_allowed is not True or self.max_provider_mutations != 1:
            raise ValueError("rollback runtime allows exactly one mutation")
        if self.temporal_model != READ_THEN_DELETE_NON_ATOMIC:
            raise ValueError("rollback runtime must disclose non-atomic temporal model")
        if self.activation_digest != _digest(self._claims()):
            raise ValueError("activation_digest does not match write-runtime-activation/v2")

    @classmethod
    def create(
        cls,
        *,
        boundary: RunnerBoundaryV3,
        decision: CredentialAccessDecisionV3,
        delivery: EphemeralRollbackCredentialDelivery,
        activation_revision: str,
    ) -> Self:
        if decision.runner_boundary_digest != boundary.boundary_digest:
            raise PermissionError("ROLLBACK_ACTIVATION_DECISION_BOUNDARY_MISMATCH")
        if delivery.runner_boundary_digest != boundary.boundary_digest:
            raise PermissionError("ROLLBACK_ACTIVATION_DELIVERY_BOUNDARY_MISMATCH")
        if delivery.credential_decision_digest != decision.decision_digest:
            raise PermissionError("ROLLBACK_ACTIVATION_DELIVERY_DECISION_MISMATCH")
        claims = {
            "schema_version": 2,
            "activation_type": WRITE_RUNTIME_ACTIVATION_V2_TYPE,
            "runner_id": boundary.runner_id,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_digest": decision.decision_digest,
            "credential_delivery_digest": delivery.delivery_digest,
            "lease_id": boundary.lease_id,
            "lease_digest": boundary.lease_digest,
            "execution_id": boundary.execution_id,
            "execution_epoch": boundary.execution_epoch,
            "capability_definition_identity": boundary.capability_definition_identity,
            "rollback_requirement_digest": boundary.rollback_requirement_digest,
            "provider_instance_id": delivery.provider_instance_id,
            "access_mode": WRITE_BOUNDED_ACCESS_MODE,
            "provider_operation": DELETE_REF_OPERATION,
            "provider_mutation_allowed": True,
            "max_provider_mutations": 1,
            "temporal_model": READ_THEN_DELETE_NON_ATOMIC,
            "activation_revision": _text(activation_revision, field="activation_revision"),
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "activation_type"}
        }
        return cls(**values, activation_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "activation_type": WRITE_RUNTIME_ACTIVATION_V2_TYPE,
            **{
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "activation_digest"
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "activation_digest": self.activation_digest}


@dataclass(frozen=True, slots=True)
class RollbackWriteEffectPreflight:
    request_digest: str
    target_digest: str
    runner_boundary_digest: str
    credential_decision_digest: str
    runtime_activation_digest: str
    condition_contract_digest: str
    observed_ref_sha: str
    predelete_observation_digest: str
    provider_operation: str
    temporal_model: str
    provider_mutation_allowed: bool
    max_provider_mutations: int
    checked_at: str
    clock_witness_digest: str
    preflight_revision: str
    preflight_digest: str

    def __post_init__(self) -> None:
        for field in (
            "request_digest",
            "target_digest",
            "runner_boundary_digest",
            "credential_decision_digest",
            "runtime_activation_digest",
            "condition_contract_digest",
            "predelete_observation_digest",
            "clock_witness_digest",
            "preflight_digest",
        ):
            _hex_digest(getattr(self, field), field=field)
        _sha1(self.observed_ref_sha, field="observed_ref_sha")
        for field in ("provider_operation", "temporal_model", "preflight_revision"):
            _text(getattr(self, field), field=field)
        _timestamp(self.checked_at, field="checked_at")
        if self.provider_operation != DELETE_REF_OPERATION:
            raise ValueError("rollback preflight operation must be DELETE_REF")
        if self.temporal_model != READ_THEN_DELETE_NON_ATOMIC:
            raise ValueError("rollback preflight must disclose non-atomic temporal model")
        if self.provider_mutation_allowed is not True or self.max_provider_mutations != 1:
            raise ValueError("rollback preflight allows exactly one mutation")
        if self.preflight_digest != _digest(self._claims()):
            raise ValueError("preflight_digest does not match write-effect-preflight/v2")

    @classmethod
    def create(
        cls,
        *,
        request: GitHubDeleteRefRequest,
        target: ExecutionTarget,
        boundary: RunnerBoundaryV3,
        decision: CredentialAccessDecisionV3,
        activation: RollbackWriteRuntimeActivation,
        condition: GitHubDeleteRefConditionContract,
        observed_ref_sha: str,
        predelete_observation_digest: str,
        checked_at: str,
        clock_witness_digest: str,
        preflight_revision: str,
    ) -> Self:
        if request.target_digest != target.target_digest:
            raise PermissionError("ROLLBACK_PREFLIGHT_TARGET_MISMATCH")
        if request.runner_boundary_digest != boundary.boundary_digest:
            raise PermissionError("ROLLBACK_PREFLIGHT_BOUNDARY_MISMATCH")
        if request.credential_decision_digest != decision.decision_digest:
            raise PermissionError("ROLLBACK_PREFLIGHT_DECISION_MISMATCH")
        if activation.runner_boundary_digest != boundary.boundary_digest:
            raise PermissionError("ROLLBACK_PREFLIGHT_ACTIVATION_BOUNDARY_MISMATCH")
        if activation.credential_decision_digest != decision.decision_digest:
            raise PermissionError("ROLLBACK_PREFLIGHT_ACTIVATION_DECISION_MISMATCH")
        if request.condition_contract_digest != condition.contract_digest:
            raise PermissionError("ROLLBACK_PREFLIGHT_CONDITION_MISMATCH")
        observed = _sha1(observed_ref_sha, field="observed_ref_sha")
        if observed != request.expected_sha or observed != condition.expected_sha:
            raise PermissionError("ROLLBACK_PREFLIGHT_STALE_OR_SUBSTITUTED_REF")
        claims = {
            "schema_version": 2,
            "preflight_type": WRITE_EFFECT_PREFLIGHT_V2_TYPE,
            "request_digest": request.request_digest,
            "target_digest": target.target_digest,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_digest": decision.decision_digest,
            "runtime_activation_digest": activation.activation_digest,
            "condition_contract_digest": condition.contract_digest,
            "observed_ref_sha": observed,
            "predelete_observation_digest": _hex_digest(
                predelete_observation_digest,
                field="predelete_observation_digest",
            ),
            "provider_operation": DELETE_REF_OPERATION,
            "temporal_model": READ_THEN_DELETE_NON_ATOMIC,
            "provider_mutation_allowed": True,
            "max_provider_mutations": 1,
            "checked_at": _text(checked_at, field="checked_at"),
            "clock_witness_digest": _hex_digest(
                clock_witness_digest,
                field="clock_witness_digest",
            ),
            "preflight_revision": _text(preflight_revision, field="preflight_revision"),
        }
        _timestamp(claims["checked_at"], field="checked_at")
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "preflight_type"}
        }
        return cls(**values, preflight_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "preflight_type": WRITE_EFFECT_PREFLIGHT_V2_TYPE,
            **{
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "preflight_digest"
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "preflight_digest": self.preflight_digest}
