from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json
from .verifier_identity import IndependentVerificationBoundary, VerifierIdentity

VERIFIER_CREDENTIAL_POLICY_TYPE: Final = "verifier-credential-policy/v1"
VERIFIER_CREDENTIAL_DECISION_TYPE: Final = "verifier-credential-decision/v1"
VERIFIER_CREDENTIAL_DECISION_IDENTITY_TYPE: Final = "verifier-credential-decision-id/v1"
READ_ONLY_ACCESS_MODE: Final = "READ_ONLY"

_POLICY_FIELDS = frozenset(
    {
        "schema_version",
        "policy_type",
        "credential_class",
        "provider",
        "audience",
        "enabled_environments",
        "access_mode",
        "provider_mutation_allowed",
        "max_ttl_seconds",
        "policy_revision",
        "policy_digest",
    }
)
_DECISION_FIELDS = frozenset(
    {
        "schema_version",
        "decision_type",
        "decision_id",
        "verifier_id",
        "verifier_identity_digest",
        "verification_boundary_digest",
        "runner_observation_digest",
        "target_digest",
        "execution_id",
        "execution_epoch",
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
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if len(text) != 64 or text.casefold() != text or any(c not in "0123456789abcdef" for c in text):
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


def _require_exact_fields(value: Mapping[str, Any], expected: frozenset[str], *, contract: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        raise ValueError(
            f"{contract} fields are invalid; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


class VerifierCredentialDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class VerifierCredentialPolicy:
    """Immutable E2 policy for a separate verifier READ credential class.

    This policy contains no token, secret, secret handle, environment variable name,
    repository scope supplied by a caller, or execution permission.
    """

    credential_class: str
    provider: str
    audience: str
    enabled_environments: tuple[str, ...]
    access_mode: str
    provider_mutation_allowed: bool
    max_ttl_seconds: int
    policy_revision: str
    policy_digest: str

    def __post_init__(self) -> None:
        for field in ("credential_class", "provider", "audience", "policy_revision"):
            _require_text(getattr(self, field), field=field)
        if (
            not self.enabled_environments
            or self.enabled_environments != tuple(sorted(set(self.enabled_environments)))
            or any(item not in VALID_ENVIRONMENTS for item in self.enabled_environments)
        ):
            raise ValueError("enabled_environments are invalid")
        if self.access_mode != READ_ONLY_ACCESS_MODE:
            raise ValueError("Phase-E verifier access mode must be READ_ONLY")
        if self.provider_mutation_allowed is not False:
            raise ValueError("Phase-E verifier credential cannot allow provider mutation")
        if type(self.max_ttl_seconds) is not int or not 1 <= self.max_ttl_seconds <= 3600:
            raise ValueError("max_ttl_seconds must be between 1 and 3600")
        _require_digest(self.policy_digest, field="policy_digest")
        if self.policy_digest != _digest(self._claims_without_digest()):
            raise ValueError("policy_digest does not match verifier credential policy")

    @classmethod
    def create(
        cls,
        *,
        credential_class: str,
        provider: str,
        audience: str,
        enabled_environments: Iterable[str],
        max_ttl_seconds: int,
        policy_revision: str,
    ) -> Self:
        environments = tuple(sorted(set(enabled_environments)))
        claims = {
            "schema_version": 1,
            "policy_type": VERIFIER_CREDENTIAL_POLICY_TYPE,
            "credential_class": credential_class,
            "provider": provider,
            "audience": audience,
            "enabled_environments": list(environments),
            "access_mode": READ_ONLY_ACCESS_MODE,
            "provider_mutation_allowed": False,
            "max_ttl_seconds": max_ttl_seconds,
            "policy_revision": policy_revision,
        }
        return cls(
            credential_class=credential_class,
            provider=provider,
            audience=audience,
            enabled_environments=environments,
            access_mode=READ_ONLY_ACCESS_MODE,
            provider_mutation_allowed=False,
            max_ttl_seconds=max_ttl_seconds,
            policy_revision=policy_revision,
            policy_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "policy_type": VERIFIER_CREDENTIAL_POLICY_TYPE,
            "credential_class": self.credential_class,
            "provider": self.provider,
            "audience": self.audience,
            "enabled_environments": list(self.enabled_environments),
            "access_mode": self.access_mode,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "max_ttl_seconds": self.max_ttl_seconds,
            "policy_revision": self.policy_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "policy_digest": self.policy_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _POLICY_FIELDS, contract=VERIFIER_CREDENTIAL_POLICY_TYPE)
        if value["schema_version"] != 1 or value["policy_type"] != VERIFIER_CREDENTIAL_POLICY_TYPE:
            raise ValueError("verifier-credential-policy/v1 schema or type is unsupported")
        environments = value["enabled_environments"]
        if not isinstance(environments, list):
            raise ValueError("enabled_environments must be an array")
        return cls(
            credential_class=value["credential_class"],
            provider=value["provider"],
            audience=value["audience"],
            enabled_environments=tuple(environments),
            access_mode=value["access_mode"],
            provider_mutation_allowed=value["provider_mutation_allowed"],
            max_ttl_seconds=value["max_ttl_seconds"],
            policy_revision=value["policy_revision"],
            policy_digest=value["policy_digest"],
        )


@dataclass(frozen=True, slots=True)
class VerifierCredentialDecision:
    """Serializable authorization metadata for out-of-band verifier credential delivery.

    The decision is not a credential. It deliberately has no field capable of carrying
    token bytes, a secret handle, an environment variable name, or ambient credential state.
    """

    decision_id: str
    verifier_id: str
    verifier_identity_digest: str
    verification_boundary_digest: str
    runner_observation_digest: str
    target_digest: str
    execution_id: str
    execution_epoch: int
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
            "verifier_id",
            "verifier_identity_digest",
            "verification_boundary_digest",
            "runner_observation_digest",
            "target_digest",
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
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        _, valid_from = _require_timestamp(self.valid_from, field="valid_from")
        _, expires_at = _require_timestamp(self.expires_at, field="expires_at")
        if expires_at <= valid_from:
            raise ValueError("verifier credential expiry must be after valid_from")
        if self.access_mode != READ_ONLY_ACCESS_MODE:
            raise ValueError("Phase-E verifier decision must be READ_ONLY")
        if self.provider_mutation_allowed is not False:
            raise ValueError("Phase-E verifier decision cannot allow provider mutation")
        if self.decision_id != self._logical_identity():
            raise ValueError("decision_id does not match verifier credential decision identity")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise ValueError("decision_digest does not match verifier credential decision")

    @classmethod
    def create(
        cls,
        *,
        verifier: VerifierIdentity,
        boundary: IndependentVerificationBoundary,
        policy: VerifierCredentialPolicy,
        valid_from: str,
        expires_at: str,
        decision_revision: str,
    ) -> Self:
        if not isinstance(verifier, VerifierIdentity):
            raise ValueError("verifier must be VerifierIdentity")
        if not isinstance(boundary, IndependentVerificationBoundary):
            raise ValueError("boundary must be IndependentVerificationBoundary")
        if not isinstance(policy, VerifierCredentialPolicy):
            raise ValueError("policy must be VerifierCredentialPolicy")
        _require_text(decision_revision, field="decision_revision")

        _, start = _require_timestamp(valid_from, field="valid_from")
        _, end = _require_timestamp(expires_at, field="expires_at")
        if end <= start:
            raise VerifierCredentialDenied("VERIFIER_CREDENTIAL_INVALID_TTL")
        if (end - start).total_seconds() > policy.max_ttl_seconds:
            raise VerifierCredentialDenied("VERIFIER_CREDENTIAL_TTL_EXCEEDS_POLICY")
        if verifier.verifier_id != boundary.verifier_id:
            raise VerifierCredentialDenied("VERIFIER_IDENTITY_BINDING_MISMATCH")
        if verifier.identity_digest != boundary.verifier_identity_digest:
            raise VerifierCredentialDenied("VERIFIER_IDENTITY_DIGEST_MISMATCH")
        if verifier.credential_class != boundary.verifier_credential_class:
            raise VerifierCredentialDenied("VERIFIER_BOUNDARY_CREDENTIAL_CLASS_MISMATCH")
        if verifier.credential_class != policy.credential_class:
            raise VerifierCredentialDenied("VERIFIER_CREDENTIAL_CLASS_NOT_ALLOWED")
        if verifier.environment != boundary.environment or verifier.environment not in policy.enabled_environments:
            raise VerifierCredentialDenied("VERIFIER_ENVIRONMENT_NOT_ALLOWED")
        if verifier.provider != policy.provider:
            raise VerifierCredentialDenied("VERIFIER_PROVIDER_NOT_ALLOWED")
        if boundary.provider_mutation_allowed is not False:
            raise VerifierCredentialDenied("VERIFIER_BOUNDARY_MUTATION_ALLOWED")
        if boundary.verifier_credential_class == boundary.runner_credential_class:
            raise VerifierCredentialDenied("VERIFIER_CREDENTIAL_NOT_INDEPENDENT")

        base = {
            "verifier_id": verifier.verifier_id,
            "verifier_identity_digest": verifier.identity_digest,
            "verification_boundary_digest": boundary.boundary_digest,
            "runner_observation_digest": boundary.runner_observation_digest,
            "target_digest": boundary.target_digest,
            "execution_id": boundary.execution_id,
            "execution_epoch": boundary.execution_epoch,
            "credential_class": policy.credential_class,
            "provider": policy.provider,
            "audience": policy.audience,
            "environment": boundary.environment,
            "access_mode": READ_ONLY_ACCESS_MODE,
            "provider_mutation_allowed": False,
            "valid_from": valid_from,
            "expires_at": expires_at,
            "policy_digest": policy.policy_digest,
            "policy_revision": policy.policy_revision,
            "decision_revision": decision_revision,
        }
        decision_id = _digest(
            {
                "decision_type": VERIFIER_CREDENTIAL_DECISION_IDENTITY_TYPE,
                "verifier_id": verifier.verifier_id,
                "verification_boundary_digest": boundary.boundary_digest,
                "policy_digest": policy.policy_digest,
                "valid_from": valid_from,
                "expires_at": expires_at,
            }
        )
        claims = {
            "schema_version": 1,
            "decision_type": VERIFIER_CREDENTIAL_DECISION_TYPE,
            "decision_id": decision_id,
            **base,
        }
        return cls(decision_id=decision_id, **base, decision_digest=_digest(claims))

    def _logical_identity(self) -> str:
        return _digest(
            {
                "decision_type": VERIFIER_CREDENTIAL_DECISION_IDENTITY_TYPE,
                "verifier_id": self.verifier_id,
                "verification_boundary_digest": self.verification_boundary_digest,
                "policy_digest": self.policy_digest,
                "valid_from": self.valid_from,
                "expires_at": self.expires_at,
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "decision_type": VERIFIER_CREDENTIAL_DECISION_TYPE,
            "decision_id": self.decision_id,
            "verifier_id": self.verifier_id,
            "verifier_identity_digest": self.verifier_identity_digest,
            "verification_boundary_digest": self.verification_boundary_digest,
            "runner_observation_digest": self.runner_observation_digest,
            "target_digest": self.target_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
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

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _DECISION_FIELDS, contract=VERIFIER_CREDENTIAL_DECISION_TYPE)
        if value["schema_version"] != 1 or value["decision_type"] != VERIFIER_CREDENTIAL_DECISION_TYPE:
            raise ValueError("verifier-credential-decision/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _DECISION_FIELDS
                if key not in {"schema_version", "decision_type"}
            }
        )
