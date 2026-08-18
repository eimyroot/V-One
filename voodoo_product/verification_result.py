from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .evidence_primitives import canonical_json
from .github_read_provider import GitHubRefObservation
from .runner_identity import READ_ONLY_EFFECT_CLASS
from .verifier_identity import INDEPENDENCE_CLASS, IndependentVerificationBoundary
from .verifier_observation import VerifierGitHubRefObservation

OBSERVED_POST_STATE_TYPE: Final = "observed-post-state/v1"
VERIFICATION_STRENGTH_TYPE: Final = "verification-strength/v1"
VERIFICATION_RESULT_TYPE: Final = "verification-result/v1"

GIT_REF_STATE_KIND: Final = "git_ref"
INDEPENDENT_PROVIDER_READBACK: Final = "INDEPENDENT_PROVIDER_READBACK"
SEQUENTIAL_READBACK_NON_ATOMIC: Final = "SEQUENTIAL_READBACK_NON_ATOMIC"

VERIFIED: Final = "VERIFIED"
NOT_VERIFIED: Final = "NOT_VERIFIED"
OBSERVED_STATE_MATCH: Final = "OBSERVED_STATE_MATCH"
OBSERVED_STATE_MISMATCH: Final = "OBSERVED_STATE_MISMATCH"

_RESULT_VERDICTS = frozenset({VERIFIED, NOT_VERIFIED})
_RESULT_REASONS = frozenset({OBSERVED_STATE_MATCH, OBSERVED_STATE_MISMATCH})

_OBSERVED_POST_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "observed_post_state_type",
        "execution_id",
        "execution_epoch",
        "target_digest",
        "state_kind",
        "state_claims",
        "provider",
        "provider_instance_id",
        "source_identity",
        "verifier_id",
        "verifier_identity_digest",
        "verification_boundary_digest",
        "verifier_observation_digest",
        "observed_at",
        "state_revision",
        "state_digest",
    }
)

_VERIFICATION_STRENGTH_FIELDS = frozenset(
    {
        "schema_version",
        "strength_type",
        "strength_class",
        "independence_class",
        "temporal_model",
        "target_binding_exact",
        "identity_separation",
        "provider_instance_separation",
        "credential_separation",
        "provider_readback",
        "atomic_readback",
        "effect_ceiling",
        "provider_mutation_allowed",
        "verification_boundary_digest",
        "verifier_observation_digest",
        "strength_revision",
        "strength_digest",
    }
)

_VERIFICATION_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "result_type",
        "execution_id",
        "execution_epoch",
        "target_digest",
        "runner_observation_digest",
        "verifier_observation_digest",
        "observed_post_state_digest",
        "verification_boundary_digest",
        "verifier_id",
        "verifier_identity_digest",
        "verification_strength_digest",
        "verification_strength_class",
        "verdict",
        "reason",
        "checked_at",
        "result_revision",
        "result_digest",
    }
)


class VerificationEvidenceDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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
        raise ValueError(
            f"{contract} fields are invalid; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _state_claims_from_mapping(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("state_claims must be a non-empty object")
    pairs: list[tuple[str, str]] = []
    for key, item in value.items():
        pairs.append(
            (
                _require_text(key, field="state_claims key"),
                _require_text(item, field=f"state_claims[{key!r}]"),
            )
        )
    ordered = tuple(sorted(pairs))
    if len({key for key, _ in ordered}) != len(ordered):
        raise ValueError("state_claims keys must be unique")
    return ordered


@dataclass(frozen=True, slots=True)
class ObservedPostState:
    """Content-addressed independent state projection derived from verifier evidence."""

    execution_id: str
    execution_epoch: int
    target_digest: str
    state_kind: str
    state_claims: tuple[tuple[str, str], ...]
    provider: str
    provider_instance_id: str
    source_identity: str
    verifier_id: str
    verifier_identity_digest: str
    verification_boundary_digest: str
    verifier_observation_digest: str
    observed_at: str
    state_revision: str
    state_digest: str

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "state_kind",
            "provider",
            "provider_instance_id",
            "source_identity",
            "state_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "verifier_id",
            "verifier_identity_digest",
            "verification_boundary_digest",
            "verifier_observation_digest",
            "state_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if not self.state_claims:
            raise ValueError("state_claims must not be empty")
        if tuple(sorted(self.state_claims)) != self.state_claims:
            raise ValueError("state_claims must be canonical and sorted")
        keys: list[str] = []
        for key, value in self.state_claims:
            keys.append(_require_text(key, field="state_claims key"))
            _require_text(value, field=f"state_claims[{key!r}]")
        if len(keys) != len(set(keys)):
            raise ValueError("state_claims keys must be unique")
        _require_timestamp(self.observed_at, field="observed_at")
        if self.state_digest != _digest(self._claims_without_digest()):
            raise ValueError("state_digest does not match ObservedPostState")

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        execution_epoch: int,
        target_digest: str,
        state_kind: str,
        state_claims: Mapping[str, str],
        provider: str,
        provider_instance_id: str,
        source_identity: str,
        verifier_id: str,
        verifier_identity_digest: str,
        verification_boundary_digest: str,
        verifier_observation_digest: str,
        observed_at: str,
        state_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "observed_post_state_type": OBSERVED_POST_STATE_TYPE,
            "execution_id": execution_id,
            "execution_epoch": execution_epoch,
            "target_digest": target_digest,
            "state_kind": state_kind,
            "state_claims": dict(sorted(state_claims.items())),
            "provider": provider,
            "provider_instance_id": provider_instance_id,
            "source_identity": source_identity,
            "verifier_id": verifier_id,
            "verifier_identity_digest": verifier_identity_digest,
            "verification_boundary_digest": verification_boundary_digest,
            "verifier_observation_digest": verifier_observation_digest,
            "observed_at": observed_at,
            "state_revision": state_revision,
        }
        return cls(
            execution_id=execution_id,
            execution_epoch=execution_epoch,
            target_digest=target_digest,
            state_kind=state_kind,
            state_claims=_state_claims_from_mapping(state_claims),
            provider=provider,
            provider_instance_id=provider_instance_id,
            source_identity=source_identity,
            verifier_id=verifier_id,
            verifier_identity_digest=verifier_identity_digest,
            verification_boundary_digest=verification_boundary_digest,
            verifier_observation_digest=verifier_observation_digest,
            observed_at=observed_at,
            state_revision=state_revision,
            state_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _OBSERVED_POST_STATE_FIELDS,
            contract=OBSERVED_POST_STATE_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["observed_post_state_type"] != OBSERVED_POST_STATE_TYPE
        ):
            raise ValueError("observed-post-state/v1 schema or type is unsupported")
        return cls(
            execution_id=value["execution_id"],
            execution_epoch=value["execution_epoch"],
            target_digest=value["target_digest"],
            state_kind=value["state_kind"],
            state_claims=_state_claims_from_mapping(value["state_claims"]),
            provider=value["provider"],
            provider_instance_id=value["provider_instance_id"],
            source_identity=value["source_identity"],
            verifier_id=value["verifier_id"],
            verifier_identity_digest=value["verifier_identity_digest"],
            verification_boundary_digest=value["verification_boundary_digest"],
            verifier_observation_digest=value["verifier_observation_digest"],
            observed_at=value["observed_at"],
            state_revision=value["state_revision"],
            state_digest=value["state_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observed_post_state_type": OBSERVED_POST_STATE_TYPE,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "target_digest": self.target_digest,
            "state_kind": self.state_kind,
            "state_claims": dict(self.state_claims),
            "provider": self.provider,
            "provider_instance_id": self.provider_instance_id,
            "source_identity": self.source_identity,
            "verifier_id": self.verifier_id,
            "verifier_identity_digest": self.verifier_identity_digest,
            "verification_boundary_digest": self.verification_boundary_digest,
            "verifier_observation_digest": self.verifier_observation_digest,
            "observed_at": self.observed_at,
            "state_revision": self.state_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "state_digest": self.state_digest}


@dataclass(frozen=True, slots=True)
class VerificationStrength:
    """Evidence-backed strength classification for one independent verification result."""

    strength_class: str
    independence_class: str
    temporal_model: str
    target_binding_exact: bool
    identity_separation: bool
    provider_instance_separation: bool
    credential_separation: bool
    provider_readback: bool
    atomic_readback: bool
    effect_ceiling: str
    provider_mutation_allowed: bool
    verification_boundary_digest: str
    verifier_observation_digest: str
    strength_revision: str
    strength_digest: str

    def __post_init__(self) -> None:
        for field in (
            "strength_class",
            "independence_class",
            "temporal_model",
            "effect_ceiling",
            "strength_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "verification_boundary_digest",
            "verifier_observation_digest",
            "strength_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.strength_class != INDEPENDENT_PROVIDER_READBACK:
            raise ValueError("verification strength class is unsupported")
        if self.independence_class != INDEPENDENCE_CLASS:
            raise ValueError("verification independence class is unsupported")
        if self.temporal_model != SEQUENTIAL_READBACK_NON_ATOMIC:
            raise ValueError("verification temporal model is unsupported")
        for field in (
            "target_binding_exact",
            "identity_separation",
            "provider_instance_separation",
            "credential_separation",
            "provider_readback",
        ):
            if getattr(self, field) is not True:
                raise ValueError(f"{field} must be true")
        if self.atomic_readback is not False:
            raise ValueError("atomic_readback must be false for E4 R1")
        if self.effect_ceiling != READ_ONLY_EFFECT_CLASS:
            raise ValueError("verification effect ceiling must be READ_ONLY")
        if self.provider_mutation_allowed is not False:
            raise ValueError("verification cannot mutate providers")
        if self.strength_digest != _digest(self._claims_without_digest()):
            raise ValueError("strength_digest does not match VerificationStrength")

    @classmethod
    def create(
        cls,
        *,
        verification_boundary_digest: str,
        verifier_observation_digest: str,
        strength_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "strength_type": VERIFICATION_STRENGTH_TYPE,
            "strength_class": INDEPENDENT_PROVIDER_READBACK,
            "independence_class": INDEPENDENCE_CLASS,
            "temporal_model": SEQUENTIAL_READBACK_NON_ATOMIC,
            "target_binding_exact": True,
            "identity_separation": True,
            "provider_instance_separation": True,
            "credential_separation": True,
            "provider_readback": True,
            "atomic_readback": False,
            "effect_ceiling": READ_ONLY_EFFECT_CLASS,
            "provider_mutation_allowed": False,
            "verification_boundary_digest": verification_boundary_digest,
            "verifier_observation_digest": verifier_observation_digest,
            "strength_revision": strength_revision,
        }
        return cls(
            **{
                key: item
                for key, item in claims.items()
                if key not in {"schema_version", "strength_type"}
            },
            strength_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _VERIFICATION_STRENGTH_FIELDS,
            contract=VERIFICATION_STRENGTH_TYPE,
        )
        if value["schema_version"] != 1 or value["strength_type"] != VERIFICATION_STRENGTH_TYPE:
            raise ValueError("verification-strength/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _VERIFICATION_STRENGTH_FIELDS
                if key not in {"schema_version", "strength_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "strength_type": VERIFICATION_STRENGTH_TYPE,
            "strength_class": self.strength_class,
            "independence_class": self.independence_class,
            "temporal_model": self.temporal_model,
            "target_binding_exact": self.target_binding_exact,
            "identity_separation": self.identity_separation,
            "provider_instance_separation": self.provider_instance_separation,
            "credential_separation": self.credential_separation,
            "provider_readback": self.provider_readback,
            "atomic_readback": self.atomic_readback,
            "effect_ceiling": self.effect_ceiling,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "verification_boundary_digest": self.verification_boundary_digest,
            "verifier_observation_digest": self.verifier_observation_digest,
            "strength_revision": self.strength_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "strength_digest": self.strength_digest}


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Independent determination derived from exact Runner and Verifier evidence."""

    execution_id: str
    execution_epoch: int
    target_digest: str
    runner_observation_digest: str
    verifier_observation_digest: str
    observed_post_state_digest: str
    verification_boundary_digest: str
    verifier_id: str
    verifier_identity_digest: str
    verification_strength_digest: str
    verification_strength_class: str
    verdict: str
    reason: str
    checked_at: str
    result_revision: str
    result_digest: str

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "verification_strength_class",
            "verdict",
            "reason",
            "result_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "runner_observation_digest",
            "verifier_observation_digest",
            "observed_post_state_digest",
            "verification_boundary_digest",
            "verifier_id",
            "verifier_identity_digest",
            "verification_strength_digest",
            "result_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        _require_timestamp(self.checked_at, field="checked_at")
        if self.verification_strength_class != INDEPENDENT_PROVIDER_READBACK:
            raise ValueError("verification strength class is unsupported")
        if self.verdict not in _RESULT_VERDICTS:
            raise ValueError("verification verdict is unsupported")
        if self.reason not in _RESULT_REASONS:
            raise ValueError("verification reason is unsupported")
        if self.verdict == VERIFIED and self.reason != OBSERVED_STATE_MATCH:
            raise ValueError("VERIFIED requires OBSERVED_STATE_MATCH")
        if self.verdict == NOT_VERIFIED and self.reason != OBSERVED_STATE_MISMATCH:
            raise ValueError("NOT_VERIFIED requires OBSERVED_STATE_MISMATCH")
        if self.result_digest != _digest(self._claims_without_digest()):
            raise ValueError("result_digest does not match VerificationResult")

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        execution_epoch: int,
        target_digest: str,
        runner_observation_digest: str,
        verifier_observation_digest: str,
        observed_post_state_digest: str,
        verification_boundary_digest: str,
        verifier_id: str,
        verifier_identity_digest: str,
        verification_strength_digest: str,
        verification_strength_class: str,
        verdict: str,
        reason: str,
        checked_at: str,
        result_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "result_type": VERIFICATION_RESULT_TYPE,
            "execution_id": execution_id,
            "execution_epoch": execution_epoch,
            "target_digest": target_digest,
            "runner_observation_digest": runner_observation_digest,
            "verifier_observation_digest": verifier_observation_digest,
            "observed_post_state_digest": observed_post_state_digest,
            "verification_boundary_digest": verification_boundary_digest,
            "verifier_id": verifier_id,
            "verifier_identity_digest": verifier_identity_digest,
            "verification_strength_digest": verification_strength_digest,
            "verification_strength_class": verification_strength_class,
            "verdict": verdict,
            "reason": reason,
            "checked_at": checked_at,
            "result_revision": result_revision,
        }
        return cls(
            **{
                key: item
                for key, item in claims.items()
                if key not in {"schema_version", "result_type"}
            },
            result_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _VERIFICATION_RESULT_FIELDS,
            contract=VERIFICATION_RESULT_TYPE,
        )
        if value["schema_version"] != 1 or value["result_type"] != VERIFICATION_RESULT_TYPE:
            raise ValueError("verification-result/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _VERIFICATION_RESULT_FIELDS
                if key not in {"schema_version", "result_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "result_type": VERIFICATION_RESULT_TYPE,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "target_digest": self.target_digest,
            "runner_observation_digest": self.runner_observation_digest,
            "verifier_observation_digest": self.verifier_observation_digest,
            "observed_post_state_digest": self.observed_post_state_digest,
            "verification_boundary_digest": self.verification_boundary_digest,
            "verifier_id": self.verifier_id,
            "verifier_identity_digest": self.verifier_identity_digest,
            "verification_strength_digest": self.verification_strength_digest,
            "verification_strength_class": self.verification_strength_class,
            "verdict": self.verdict,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "result_revision": self.result_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "result_digest": self.result_digest}


def _assert_verification_evidence_bound(
    *,
    runner_observation: GitHubRefObservation,
    verifier_observation: VerifierGitHubRefObservation,
    boundary: IndependentVerificationBoundary,
) -> None:
    if not isinstance(runner_observation, GitHubRefObservation):
        raise ValueError("runner_observation must be github-ref-observation/v1")
    if not isinstance(verifier_observation, VerifierGitHubRefObservation):
        raise ValueError(
            "verifier_observation must be verifier-github-ref-observation/v1"
        )
    if not isinstance(boundary, IndependentVerificationBoundary):
        raise ValueError(
            "boundary must be independent-verification-boundary/v1"
        )

    bindings = {
        "boundary_runner_observation": (
            boundary.runner_observation_digest,
            runner_observation.observation_digest,
        ),
        "boundary_runner_id": (boundary.runner_id, runner_observation.runner_id),
        "boundary_runner_instance": (
            boundary.runner_provider_instance_id,
            runner_observation.provider_instance_id,
        ),
        "boundary_runner_boundary": (
            boundary.runner_boundary_digest,
            runner_observation.runner_boundary_digest,
        ),
        "boundary_target": (boundary.target_digest, runner_observation.target_digest),
        "boundary_execution": (
            boundary.execution_id,
            runner_observation.execution_id,
        ),
        "boundary_epoch": (
            boundary.execution_epoch,
            runner_observation.execution_epoch,
        ),
        "verifier_boundary": (
            verifier_observation.verification_boundary_digest,
            boundary.boundary_digest,
        ),
        "verifier_runner_observation": (
            verifier_observation.runner_observation_digest,
            runner_observation.observation_digest,
        ),
        "verifier_target": (
            verifier_observation.target_digest,
            runner_observation.target_digest,
        ),
        "verifier_execution": (
            verifier_observation.execution_id,
            runner_observation.execution_id,
        ),
        "verifier_epoch": (
            verifier_observation.execution_epoch,
            runner_observation.execution_epoch,
        ),
        "verifier_id": (verifier_observation.verifier_id, boundary.verifier_id),
        "verifier_identity": (
            verifier_observation.verifier_identity_digest,
            boundary.verifier_identity_digest,
        ),
        "verifier_provider": (
            verifier_observation.provider,
            boundary.verifier_provider,
        ),
        "verifier_instance": (
            verifier_observation.provider_instance_id,
            boundary.verifier_provider_instance_id,
        ),
    }
    mismatches = sorted(
        name for name, (actual, expected) in bindings.items() if actual != expected
    )
    if mismatches:
        raise VerificationEvidenceDenied(
            f"VERIFICATION_EVIDENCE_BINDING_MISMATCH:{','.join(mismatches)}"
        )

    if (
        verifier_observation.repository != runner_observation.repository
        or verifier_observation.ref != runner_observation.ref
    ):
        raise VerificationEvidenceDenied("VERIFICATION_TARGET_CLAIMS_MISMATCH")

    _, runner_observed_at = _require_timestamp(
        runner_observation.observed_at,
        field="runner_observation.observed_at",
    )
    _, verifier_observed_at = _require_timestamp(
        verifier_observation.observed_at,
        field="verifier_observation.observed_at",
    )
    if verifier_observed_at < runner_observed_at:
        raise VerificationEvidenceDenied(
            "VERIFIER_OBSERVATION_PRECEDES_RUNNER_OBSERVATION"
        )


def verify_github_ref_readback(
    *,
    runner_observation: GitHubRefObservation,
    verifier_observation: VerifierGitHubRefObservation,
    boundary: IndependentVerificationBoundary,
    observed_post_state_revision: str,
    strength_revision: str,
    result_revision: str,
) -> tuple[ObservedPostState, VerificationStrength, VerificationResult]:
    """Create E4 verification artifacts from already-produced READ-only evidence.

    No provider call is made here. The sequential verifier readback is explicitly non-atomic.
    """

    _assert_verification_evidence_bound(
        runner_observation=runner_observation,
        verifier_observation=verifier_observation,
        boundary=boundary,
    )
    _require_text(observed_post_state_revision, field="observed_post_state_revision")
    _require_text(strength_revision, field="strength_revision")
    _require_text(result_revision, field="result_revision")

    observed_post_state = ObservedPostState.create(
        execution_id=verifier_observation.execution_id,
        execution_epoch=verifier_observation.execution_epoch,
        target_digest=verifier_observation.target_digest,
        state_kind=GIT_REF_STATE_KIND,
        state_claims={
            "repository": verifier_observation.repository,
            "ref": verifier_observation.ref,
            "commit_sha": verifier_observation.commit_sha,
        },
        provider=verifier_observation.provider,
        provider_instance_id=verifier_observation.provider_instance_id,
        source_identity=verifier_observation.source_identity,
        verifier_id=verifier_observation.verifier_id,
        verifier_identity_digest=verifier_observation.verifier_identity_digest,
        verification_boundary_digest=boundary.boundary_digest,
        verifier_observation_digest=verifier_observation.observation_digest,
        observed_at=verifier_observation.observed_at,
        state_revision=observed_post_state_revision,
    )
    strength = VerificationStrength.create(
        verification_boundary_digest=boundary.boundary_digest,
        verifier_observation_digest=verifier_observation.observation_digest,
        strength_revision=strength_revision,
    )

    matches = verifier_observation.commit_sha == runner_observation.commit_sha
    verdict = VERIFIED if matches else NOT_VERIFIED
    reason = OBSERVED_STATE_MATCH if matches else OBSERVED_STATE_MISMATCH
    result = VerificationResult.create(
        execution_id=verifier_observation.execution_id,
        execution_epoch=verifier_observation.execution_epoch,
        target_digest=verifier_observation.target_digest,
        runner_observation_digest=runner_observation.observation_digest,
        verifier_observation_digest=verifier_observation.observation_digest,
        observed_post_state_digest=observed_post_state.state_digest,
        verification_boundary_digest=boundary.boundary_digest,
        verifier_id=verifier_observation.verifier_id,
        verifier_identity_digest=verifier_observation.verifier_identity_digest,
        verification_strength_digest=strength.strength_digest,
        verification_strength_class=strength.strength_class,
        verdict=verdict,
        reason=reason,
        checked_at=verifier_observation.observed_at,
        result_revision=result_revision,
    )
    return observed_post_state, strength, result
