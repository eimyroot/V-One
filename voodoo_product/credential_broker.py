from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Final, Protocol, Self, runtime_checkable

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json
from .execution_lease import ExecutionLease
from .runner_identity import READ_ONLY_EFFECT_CLASS, RunnerBoundary

CREDENTIAL_BROKER_POLICY_TYPE: Final = "credential-broker-policy/v1"
CREDENTIAL_ACCESS_DECISION_TYPE: Final = "credential-access-decision/v1"
CREDENTIAL_ACCESS_DECISION_IDENTITY_TYPE: Final = "credential-access-decision-id/v1"
READ_ONLY_ACCESS_MODE: Final = "READ_ONLY"

_POLICY_FIELDS = frozenset(
    {
        "schema_version",
        "policy_type",
        "credential_class",
        "provider",
        "audience",
        "allowed_capability_definition_identities",
        "enabled_environments",
        "access_mode",
        "provider_mutation_allowed",
        "policy_revision",
        "policy_digest",
    }
)
_DECISION_FIELDS = frozenset(
    {
        "schema_version",
        "decision_type",
        "decision_id",
        "runner_boundary_digest",
        "runner_id",
        "runner_identity_digest",
        "lease_id",
        "lease_digest",
        "execution_id",
        "execution_epoch",
        "execution_capsule_digest",
        "capability_definition_identity",
        "credential_class",
        "provider",
        "audience",
        "environment",
        "access_mode",
        "provider_mutation_allowed",
        "valid_from",
        "expires_at",
        "policy_digest",
        "policy_revision",
        "decision_revision",
        "decision_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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


def _require_timestamp(value: object, *, field: str) -> tuple[str, datetime]:
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
    return canonical, parsed.astimezone(UTC)


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


class CredentialBrokerDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CredentialBrokerPolicy:
    """Immutable D2 policy describing which exact READ-only boundary may obtain credentials.

    The policy never contains secret bytes, token handles or ambient credential locations. It is
    only the broker-side narrowing rule used to authorize later out-of-band credential delivery.
    """

    credential_class: str
    provider: str
    audience: str
    allowed_capability_definition_identities: tuple[str, ...]
    enabled_environments: tuple[str, ...]
    access_mode: str
    provider_mutation_allowed: bool
    policy_revision: str
    policy_digest: str

    def __post_init__(self) -> None:
        for field in ("credential_class", "provider", "audience", "policy_revision"):
            _require_text(getattr(self, field), field=field)
        if (
            not self.allowed_capability_definition_identities
            or self.allowed_capability_definition_identities
            != tuple(sorted(set(self.allowed_capability_definition_identities)))
        ):
            raise ValueError("allowed capability identities are invalid")
        for identity in self.allowed_capability_definition_identities:
            _require_digest(identity, field="capability_definition_identity")
        if (
            not self.enabled_environments
            or self.enabled_environments != tuple(sorted(set(self.enabled_environments)))
            or any(item not in VALID_ENVIRONMENTS for item in self.enabled_environments)
        ):
            raise ValueError("enabled_environments are invalid")
        if self.access_mode != READ_ONLY_ACCESS_MODE:
            raise ValueError("Phase-D credential access mode must be READ_ONLY")
        if self.provider_mutation_allowed is not False:
            raise ValueError("Phase-D credential policy cannot allow provider mutation")
        _require_digest(self.policy_digest, field="policy_digest")
        if self.policy_digest != _digest(self._claims_without_digest()):
            raise ValueError("policy_digest does not match credential broker policy")

    @classmethod
    def create(
        cls,
        *,
        credential_class: str,
        provider: str,
        audience: str,
        allowed_capability_definition_identities: Iterable[str],
        enabled_environments: Iterable[str],
        policy_revision: str,
    ) -> Self:
        capabilities = tuple(sorted(set(allowed_capability_definition_identities)))
        environments = tuple(sorted(set(enabled_environments)))
        claims = {
            "schema_version": 1,
            "policy_type": CREDENTIAL_BROKER_POLICY_TYPE,
            "credential_class": credential_class,
            "provider": provider,
            "audience": audience,
            "allowed_capability_definition_identities": list(capabilities),
            "enabled_environments": list(environments),
            "access_mode": READ_ONLY_ACCESS_MODE,
            "provider_mutation_allowed": False,
            "policy_revision": policy_revision,
        }
        return cls(
            credential_class=credential_class,
            provider=provider,
            audience=audience,
            allowed_capability_definition_identities=capabilities,
            enabled_environments=environments,
            access_mode=READ_ONLY_ACCESS_MODE,
            provider_mutation_allowed=False,
            policy_revision=policy_revision,
            policy_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _POLICY_FIELDS, contract=CREDENTIAL_BROKER_POLICY_TYPE)
        if (
            value["schema_version"] != 1
            or value["policy_type"] != CREDENTIAL_BROKER_POLICY_TYPE
        ):
            raise ValueError("credential-broker-policy/v1 schema or type is unsupported")
        capabilities = value["allowed_capability_definition_identities"]
        environments = value["enabled_environments"]
        if not isinstance(capabilities, list) or not isinstance(environments, list):
            raise ValueError("credential broker policy collections must be arrays")
        return cls(
            credential_class=value["credential_class"],
            provider=value["provider"],
            audience=value["audience"],
            allowed_capability_definition_identities=tuple(capabilities),
            enabled_environments=tuple(environments),
            access_mode=value["access_mode"],
            provider_mutation_allowed=value["provider_mutation_allowed"],
            policy_revision=value["policy_revision"],
            policy_digest=value["policy_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "policy_type": CREDENTIAL_BROKER_POLICY_TYPE,
            "credential_class": self.credential_class,
            "provider": self.provider,
            "audience": self.audience,
            "allowed_capability_definition_identities": list(
                self.allowed_capability_definition_identities
            ),
            "enabled_environments": list(self.enabled_environments),
            "access_mode": self.access_mode,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "policy_revision": self.policy_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "policy_digest": self.policy_digest}


@dataclass(frozen=True, slots=True)
class CredentialAccessDecision:
    """Content-addressed authorization to deliver one READ-only credential out of band.

    This object is deliberately not the credential itself. It contains no token, secret, handle,
    environment-variable name or provider session key. Later D3 delivery must use a separate secret
    channel and must re-check the current C4 execution epoch before exposing any secret material.
    """

    decision_id: str
    runner_boundary_digest: str
    runner_id: str
    runner_identity_digest: str
    lease_id: str
    lease_digest: str
    execution_id: str
    execution_epoch: int
    execution_capsule_digest: str
    capability_definition_identity: str
    credential_class: str
    provider: str
    audience: str
    environment: str
    access_mode: str
    provider_mutation_allowed: bool
    valid_from: str
    expires_at: str
    policy_digest: str
    policy_revision: str
    decision_revision: str
    decision_digest: str

    def __post_init__(self) -> None:
        for field in (
            "decision_id",
            "runner_boundary_digest",
            "runner_id",
            "runner_identity_digest",
            "lease_id",
            "lease_digest",
            "execution_capsule_digest",
            "capability_definition_identity",
            "policy_digest",
            "decision_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "execution_id",
            "credential_class",
            "provider",
            "audience",
            "policy_revision",
            "decision_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        if isinstance(self.execution_epoch, bool) or not isinstance(self.execution_epoch, int):
            raise ValueError("execution_epoch must be an integer")
        if self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        _, valid_from = _require_timestamp(self.valid_from, field="valid_from")
        _, expires_at = _require_timestamp(self.expires_at, field="expires_at")
        if expires_at <= valid_from:
            raise ValueError("credential decision expiry must be after valid_from")
        if self.access_mode != READ_ONLY_ACCESS_MODE:
            raise ValueError("Phase-D credential decision must be READ_ONLY")
        if self.provider_mutation_allowed is not False:
            raise ValueError("Phase-D credential decision cannot allow provider mutation")
        if self.decision_id != self._logical_identity():
            raise ValueError("decision_id does not match credential decision identity")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise ValueError("decision_digest does not match credential access decision")

    @classmethod
    def create(
        cls,
        *,
        boundary: RunnerBoundary,
        lease: ExecutionLease,
        policy: CredentialBrokerPolicy,
        decision_revision: str,
    ) -> Self:
        if not isinstance(boundary, RunnerBoundary):
            raise ValueError("boundary must be RunnerBoundary")
        if not isinstance(lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")
        if not isinstance(policy, CredentialBrokerPolicy):
            raise ValueError("policy must be CredentialBrokerPolicy")
        _require_text(decision_revision, field="decision_revision")

        if boundary.effect_ceiling != READ_ONLY_EFFECT_CLASS:
            raise CredentialBrokerDenied("RUNNER_BOUNDARY_NOT_READ_ONLY")
        if boundary.provider_mutation_allowed is not False:
            raise CredentialBrokerDenied("RUNNER_BOUNDARY_MUTATION_ALLOWED")
        if boundary.lease_id != lease.lease_id or boundary.lease_digest != lease.lease_digest:
            raise CredentialBrokerDenied("CREDENTIAL_LEASE_BINDING_MISMATCH")
        if boundary.execution_id != lease.execution_id:
            raise CredentialBrokerDenied("CREDENTIAL_EXECUTION_BINDING_MISMATCH")
        if boundary.execution_epoch != lease.execution_epoch:
            raise CredentialBrokerDenied("CREDENTIAL_EPOCH_BINDING_MISMATCH")
        if boundary.environment != lease.environment:
            raise CredentialBrokerDenied("CREDENTIAL_ENVIRONMENT_BINDING_MISMATCH")
        if boundary.credential_class != policy.credential_class:
            raise CredentialBrokerDenied("CREDENTIAL_CLASS_NOT_ALLOWED")
        if (
            boundary.capability_definition_identity
            not in policy.allowed_capability_definition_identities
        ):
            raise CredentialBrokerDenied("CREDENTIAL_CAPABILITY_NOT_ALLOWED")
        if boundary.environment not in policy.enabled_environments:
            raise CredentialBrokerDenied("CREDENTIAL_ENVIRONMENT_NOT_ALLOWED")

        claims = {
            "schema_version": 1,
            "decision_type": CREDENTIAL_ACCESS_DECISION_TYPE,
            "decision_id": _digest(
                {
                    "identity_type": CREDENTIAL_ACCESS_DECISION_IDENTITY_TYPE,
                    "runner_boundary_digest": boundary.boundary_digest,
                    "lease_digest": lease.lease_digest,
                    "policy_digest": policy.policy_digest,
                }
            ),
            "runner_boundary_digest": boundary.boundary_digest,
            "runner_id": boundary.runner_id,
            "runner_identity_digest": boundary.runner_identity_digest,
            "lease_id": lease.lease_id,
            "lease_digest": lease.lease_digest,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "execution_capsule_digest": boundary.execution_capsule_digest,
            "capability_definition_identity": boundary.capability_definition_identity,
            "credential_class": boundary.credential_class,
            "provider": policy.provider,
            "audience": policy.audience,
            "environment": boundary.environment,
            "access_mode": READ_ONLY_ACCESS_MODE,
            "provider_mutation_allowed": False,
            "valid_from": lease.acquired_at,
            "expires_at": lease.expires_at,
            "policy_digest": policy.policy_digest,
            "policy_revision": policy.policy_revision,
            "decision_revision": decision_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "decision_type"}
        }
        return cls(**values, decision_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _DECISION_FIELDS, contract=CREDENTIAL_ACCESS_DECISION_TYPE)
        if (
            value["schema_version"] != 1
            or value["decision_type"] != CREDENTIAL_ACCESS_DECISION_TYPE
        ):
            raise ValueError("credential-access-decision/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _DECISION_FIELDS
                if key not in {"schema_version", "decision_type"}
            }
        )

    def assert_bound_to(
        self,
        *,
        boundary: RunnerBoundary,
        lease: ExecutionLease,
        policy: CredentialBrokerPolicy,
    ) -> None:
        expected = CredentialAccessDecision.create(
            boundary=boundary,
            lease=lease,
            policy=policy,
            decision_revision=self.decision_revision,
        )
        if self != expected:
            raise CredentialBrokerDenied("CREDENTIAL_DECISION_BINDING_MISMATCH")

    def _logical_identity(self) -> str:
        return _digest(
            {
                "identity_type": CREDENTIAL_ACCESS_DECISION_IDENTITY_TYPE,
                "runner_boundary_digest": self.runner_boundary_digest,
                "lease_digest": self.lease_digest,
                "policy_digest": self.policy_digest,
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "decision_type": CREDENTIAL_ACCESS_DECISION_TYPE,
            "decision_id": self.decision_id,
            "runner_boundary_digest": self.runner_boundary_digest,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "lease_id": self.lease_id,
            "lease_digest": self.lease_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "credential_class": self.credential_class,
            "provider": self.provider,
            "audience": self.audience,
            "environment": self.environment,
            "access_mode": self.access_mode,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "valid_from": self.valid_from,
            "expires_at": self.expires_at,
            "policy_digest": self.policy_digest,
            "policy_revision": self.policy_revision,
            "decision_revision": self.decision_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "decision_digest": self.decision_digest}


@runtime_checkable
class CredentialBroker(Protocol):
    def authorize(
        self,
        *,
        boundary: RunnerBoundary,
        lease: ExecutionLease,
    ) -> CredentialAccessDecision:
        """Authorize later out-of-band READ-only credential delivery."""
        ...


class ImmutableCredentialBroker:
    """Policy-backed D2 broker that issues decisions but never credential material."""

    def __init__(
        self,
        *,
        policies: Iterable[CredentialBrokerPolicy],
        decision_revision: str,
    ) -> None:
        _require_text(decision_revision, field="decision_revision")
        by_class: dict[str, CredentialBrokerPolicy] = {}
        for policy in policies:
            if not isinstance(policy, CredentialBrokerPolicy):
                raise ValueError("credential broker policy is invalid")
            if policy.credential_class in by_class:
                raise ValueError("duplicate credential class policy")
            by_class[policy.credential_class] = policy
        if not by_class:
            raise ValueError("credential broker requires at least one policy")
        self._policies = MappingProxyType(by_class)
        self._decision_revision = decision_revision

    def authorize(
        self,
        *,
        boundary: RunnerBoundary,
        lease: ExecutionLease,
    ) -> CredentialAccessDecision:
        if not isinstance(boundary, RunnerBoundary):
            raise ValueError("boundary must be RunnerBoundary")
        try:
            policy = self._policies[boundary.credential_class]
        except KeyError as exc:
            raise CredentialBrokerDenied("CREDENTIAL_CLASS_NOT_REGISTERED") from exc
        return CredentialAccessDecision.create(
            boundary=boundary,
            lease=lease,
            policy=policy,
            decision_revision=self._decision_revision,
        )
