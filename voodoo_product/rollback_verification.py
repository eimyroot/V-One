from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget
from .rollback_control import RunnerBoundaryV3
from .runner_identity import RunnerIdentity
from .verification_result import (
    OBSERVED_STATE_MATCH,
    VERIFIED,
    ObservedPostState,
    VerificationResult,
    VerificationStrength,
)
from .verifier_credential import (
    READ_ONLY_ACCESS_MODE,
    VerifierCredentialPolicy,
)
from .verifier_identity import INDEPENDENCE_CLASS, VerifierIdentity

GITHUB_REF_ABSENCE_OBSERVATION_TYPE: Final = "github-ref-absence-observation/v1"
VERIFIER_GITHUB_REF_ABSENCE_OBSERVATION_TYPE: Final = (
    "verifier-github-ref-absence-observation/v1"
)
INDEPENDENT_VERIFICATION_BOUNDARY_V2_TYPE: Final = (
    "independent-verification-boundary/v2"
)
VERIFIER_CREDENTIAL_DECISION_V2_TYPE: Final = "verifier-credential-decision/v2"
VERIFIER_CREDENTIAL_DECISION_IDENTITY_V2_TYPE: Final = (
    "verifier-credential-decision-id/v2"
)

GITHUB_PROVIDER: Final = "github"
GITHUB_API_AUDIENCE: Final = "api.github.com"
ABSENT: Final = "ABSENT"
HTTP_NOT_FOUND: Final = 404
GIT_REF_STATE_KIND: Final = "git_ref"
STAGING_ENVIRONMENT: Final = "staging"


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


def _target_claims(target: ExecutionTarget) -> tuple[str, str]:
    if target.target_kind != GIT_REF_STATE_KIND:
        raise ValueError("rollback verification target must be git_ref")
    claims = target.target_claims
    repository = claims.get("repository")
    ref = claims.get("ref")
    if not isinstance(repository, str) or not isinstance(ref, str):
        raise ValueError("rollback verification target must carry repository and ref")
    return repository, ref


@dataclass(frozen=True, slots=True)
class GitHubRefAbsenceObservation:
    repository: str
    ref: str
    target_digest: str
    provider: str
    provider_instance_id: str
    runner_id: str
    runner_identity_digest: str
    runner_boundary_digest: str
    execution_id: str
    execution_epoch: int
    source_identity: str
    http_status: int
    presence: str
    observed_at: str
    observation_revision: str
    observation_digest: str

    def __post_init__(self) -> None:
        for field in (
            "target_digest",
            "runner_id",
            "runner_identity_digest",
            "runner_boundary_digest",
            "observation_digest",
        ):
            _hex_digest(getattr(self, field), field=field)
        for field in (
            "repository",
            "ref",
            "provider",
            "provider_instance_id",
            "execution_id",
            "source_identity",
            "presence",
            "observation_revision",
        ):
            _text(getattr(self, field), field=field)
        _timestamp(self.observed_at, field="observed_at")
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.provider != GITHUB_PROVIDER:
            raise ValueError("absence observation provider must be github")
        if self.http_status != HTTP_NOT_FOUND or self.presence != ABSENT:
            raise ValueError("absence observation requires provider 404 / ABSENT")
        if self.observation_digest != _digest(self._claims()):
            raise ValueError("observation_digest does not match github-ref-absence-observation/v1")

    @classmethod
    def create(
        cls,
        *,
        target: ExecutionTarget,
        runner_identity: RunnerIdentity,
        runner_boundary: RunnerBoundaryV3,
        provider_instance_id: str,
        source_identity: str,
        observed_at: str,
        observation_revision: str,
    ) -> Self:
        repository, ref = _target_claims(target)
        if runner_boundary.runner_id != runner_identity.runner_id:
            raise PermissionError("ROLLBACK_ABSENCE_RUNNER_IDENTITY_MISMATCH")
        if runner_boundary.runner_identity_digest != runner_identity.identity_digest:
            raise PermissionError("ROLLBACK_ABSENCE_RUNNER_DIGEST_MISMATCH")
        claims = {
            "schema_version": 1,
            "observation_type": GITHUB_REF_ABSENCE_OBSERVATION_TYPE,
            "repository": repository,
            "ref": ref,
            "target_digest": target.target_digest,
            "provider": GITHUB_PROVIDER,
            "provider_instance_id": _text(
                provider_instance_id,
                field="provider_instance_id",
            ),
            "runner_id": runner_identity.runner_id,
            "runner_identity_digest": runner_identity.identity_digest,
            "runner_boundary_digest": runner_boundary.boundary_digest,
            "execution_id": runner_boundary.execution_id,
            "execution_epoch": runner_boundary.execution_epoch,
            "source_identity": _text(source_identity, field="source_identity"),
            "http_status": HTTP_NOT_FOUND,
            "presence": ABSENT,
            "observed_at": _text(observed_at, field="observed_at"),
            "observation_revision": _text(
                observation_revision,
                field="observation_revision",
            ),
        }
        _timestamp(claims["observed_at"], field="observed_at")
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "observation_type"}
        }
        return cls(**values, observation_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observation_type": GITHUB_REF_ABSENCE_OBSERVATION_TYPE,
            **{
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "observation_digest"
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "observation_digest": self.observation_digest}


@dataclass(frozen=True, slots=True)
class IndependentVerificationBoundaryV2:
    verifier_id: str
    verifier_identity_digest: str
    verifier_provider_instance_id: str
    verifier_credential_class: str
    runner_id: str
    runner_identity_digest: str
    runner_boundary_digest: str
    runner_provider_instance_id: str
    runner_credential_class: str
    execution_id: str
    execution_epoch: int
    target_digest: str
    runner_observation_digest: str
    environment: str
    provider_mutation_allowed: bool
    independence_class: str
    boundary_revision: str
    boundary_digest: str

    def __post_init__(self) -> None:
        for field in (
            "verifier_id",
            "verifier_identity_digest",
            "runner_id",
            "runner_identity_digest",
            "runner_boundary_digest",
            "target_digest",
            "runner_observation_digest",
            "boundary_digest",
        ):
            _hex_digest(getattr(self, field), field=field)
        for field in (
            "verifier_provider_instance_id",
            "verifier_credential_class",
            "runner_provider_instance_id",
            "runner_credential_class",
            "execution_id",
            "environment",
            "independence_class",
            "boundary_revision",
        ):
            _text(getattr(self, field), field=field)
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.environment != STAGING_ENVIRONMENT:
            raise ValueError("rollback verifier boundary is staging-only")
        if self.provider_mutation_allowed is not False:
            raise ValueError("verifier boundary cannot mutate providers")
        if self.independence_class != INDEPENDENCE_CLASS:
            raise ValueError("independence_class is unsupported")
        if self.verifier_id == self.runner_id:
            raise ValueError("VerifierIdentity must differ from RunnerIdentity")
        if self.verifier_provider_instance_id == self.runner_provider_instance_id:
            raise ValueError("Verifier provider instance must differ from Runner provider instance")
        if self.verifier_credential_class == self.runner_credential_class:
            raise ValueError("Verifier credential class must differ from Runner credential class")
        if self.boundary_digest != _digest(self._claims()):
            raise ValueError("boundary_digest does not match independent-verification-boundary/v2")

    @classmethod
    def create(
        cls,
        *,
        verifier: VerifierIdentity,
        runner_identity: RunnerIdentity,
        runner_boundary: RunnerBoundaryV3,
        runner_observation: GitHubRefAbsenceObservation,
        boundary_revision: str,
    ) -> Self:
        if runner_observation.runner_id != runner_identity.runner_id:
            raise PermissionError("ROLLBACK_VERIFY_RUNNER_ID_MISMATCH")
        if runner_observation.runner_identity_digest != runner_identity.identity_digest:
            raise PermissionError("ROLLBACK_VERIFY_RUNNER_DIGEST_MISMATCH")
        if runner_observation.runner_boundary_digest != runner_boundary.boundary_digest:
            raise PermissionError("ROLLBACK_VERIFY_RUNNER_BOUNDARY_MISMATCH")
        if verifier.environment != STAGING_ENVIRONMENT:
            raise PermissionError("ROLLBACK_VERIFY_ENVIRONMENT_MISMATCH")
        claims = {
            "schema_version": 2,
            "boundary_type": INDEPENDENT_VERIFICATION_BOUNDARY_V2_TYPE,
            "verifier_id": verifier.verifier_id,
            "verifier_identity_digest": verifier.identity_digest,
            "verifier_provider_instance_id": verifier.provider_instance_id,
            "verifier_credential_class": verifier.credential_class,
            "runner_id": runner_identity.runner_id,
            "runner_identity_digest": runner_identity.identity_digest,
            "runner_boundary_digest": runner_boundary.boundary_digest,
            "runner_provider_instance_id": runner_identity.provider_instance_id,
            "runner_credential_class": runner_boundary.credential_class,
            "execution_id": runner_boundary.execution_id,
            "execution_epoch": runner_boundary.execution_epoch,
            "target_digest": runner_observation.target_digest,
            "runner_observation_digest": runner_observation.observation_digest,
            "environment": STAGING_ENVIRONMENT,
            "provider_mutation_allowed": False,
            "independence_class": INDEPENDENCE_CLASS,
            "boundary_revision": _text(boundary_revision, field="boundary_revision"),
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "boundary_type"}
        }
        return cls(**values, boundary_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "boundary_type": INDEPENDENT_VERIFICATION_BOUNDARY_V2_TYPE,
            **{
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "boundary_digest"
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "boundary_digest": self.boundary_digest}


@dataclass(frozen=True, slots=True)
class VerifierCredentialDecisionV2:
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
            _hex_digest(getattr(self, field), field=field)
        for field in (
            "execution_id",
            "credential_class",
            "provider",
            "audience",
            "environment",
            "access_mode",
            "decision_revision",
        ):
            _text(getattr(self, field), field=field)
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        start = _timestamp(self.valid_from, field="valid_from")
        end = _timestamp(self.expires_at, field="expires_at")
        if end <= start:
            raise ValueError("verifier credential expiry must be after valid_from")
        if self.access_mode != READ_ONLY_ACCESS_MODE:
            raise ValueError("rollback verifier credential must be READ_ONLY")
        if self.provider_mutation_allowed is not False:
            raise ValueError("rollback verifier credential cannot mutate providers")
        if self.decision_digest != _digest(self._claims()):
            raise ValueError("decision_digest does not match verifier-credential-decision/v2")

    @classmethod
    def create(
        cls,
        *,
        verifier: VerifierIdentity,
        boundary: IndependentVerificationBoundaryV2,
        policy: VerifierCredentialPolicy,
        valid_from: str,
        expires_at: str,
        decision_revision: str,
    ) -> Self:
        start = _timestamp(valid_from, field="valid_from")
        end = _timestamp(expires_at, field="expires_at")
        if end <= start or (end - start).total_seconds() > policy.max_ttl_seconds:
            raise PermissionError("ROLLBACK_VERIFIER_CREDENTIAL_TTL_EXCEEDS_POLICY")
        if verifier.verifier_id != boundary.verifier_id:
            raise PermissionError("ROLLBACK_VERIFIER_IDENTITY_MISMATCH")
        if verifier.identity_digest != boundary.verifier_identity_digest:
            raise PermissionError("ROLLBACK_VERIFIER_IDENTITY_DIGEST_MISMATCH")
        if verifier.credential_class != policy.credential_class:
            raise PermissionError("ROLLBACK_VERIFIER_CREDENTIAL_CLASS_MISMATCH")
        if verifier.provider != policy.provider:
            raise PermissionError("ROLLBACK_VERIFIER_PROVIDER_MISMATCH")
        if verifier.environment not in policy.enabled_environments:
            raise PermissionError("ROLLBACK_VERIFIER_ENVIRONMENT_NOT_ALLOWED")
        if policy.access_mode != READ_ONLY_ACCESS_MODE or policy.provider_mutation_allowed is not False:
            raise PermissionError("ROLLBACK_VERIFIER_POLICY_NOT_READ_ONLY")
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
            "decision_revision": _text(decision_revision, field="decision_revision"),
        }
        decision_id = _digest(
            {
                "decision_type": VERIFIER_CREDENTIAL_DECISION_IDENTITY_V2_TYPE,
                "verifier_id": verifier.verifier_id,
                "verification_boundary_digest": boundary.boundary_digest,
                "policy_digest": policy.policy_digest,
                "valid_from": valid_from,
                "expires_at": expires_at,
            }
        )
        claims = {
            "schema_version": 2,
            "decision_type": VERIFIER_CREDENTIAL_DECISION_V2_TYPE,
            "decision_id": decision_id,
            **base,
        }
        return cls(decision_id=decision_id, **base, decision_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "decision_type": VERIFIER_CREDENTIAL_DECISION_V2_TYPE,
            **{
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "decision_digest"
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "decision_digest": self.decision_digest}


@dataclass(frozen=True, slots=True)
class VerifierGitHubRefAbsenceObservation:
    repository: str
    ref: str
    target_digest: str
    provider: str
    provider_instance_id: str
    verifier_id: str
    verifier_identity_digest: str
    verification_boundary_digest: str
    verifier_credential_decision_digest: str
    runner_observation_digest: str
    execution_id: str
    execution_epoch: int
    source_identity: str
    http_status: int
    presence: str
    observed_at: str
    observation_revision: str
    observation_digest: str

    def __post_init__(self) -> None:
        for field in (
            "target_digest",
            "verifier_id",
            "verifier_identity_digest",
            "verification_boundary_digest",
            "verifier_credential_decision_digest",
            "runner_observation_digest",
            "observation_digest",
        ):
            _hex_digest(getattr(self, field), field=field)
        for field in (
            "repository",
            "ref",
            "provider",
            "provider_instance_id",
            "execution_id",
            "source_identity",
            "presence",
            "observation_revision",
        ):
            _text(getattr(self, field), field=field)
        _timestamp(self.observed_at, field="observed_at")
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.provider != GITHUB_PROVIDER:
            raise ValueError("verifier absence observation provider must be github")
        if self.http_status != HTTP_NOT_FOUND or self.presence != ABSENT:
            raise ValueError("verifier absence observation requires provider 404 / ABSENT")
        if self.observation_digest != _digest(self._claims()):
            raise ValueError("observation_digest does not match verifier absence observation")

    @classmethod
    def create(
        cls,
        *,
        runner_observation: GitHubRefAbsenceObservation,
        verifier: VerifierIdentity,
        boundary: IndependentVerificationBoundaryV2,
        decision: VerifierCredentialDecisionV2,
        source_identity: str,
        observed_at: str,
        observation_revision: str,
    ) -> Self:
        if boundary.runner_observation_digest != runner_observation.observation_digest:
            raise PermissionError("ROLLBACK_VERIFIER_RUNNER_OBSERVATION_MISMATCH")
        if decision.verification_boundary_digest != boundary.boundary_digest:
            raise PermissionError("ROLLBACK_VERIFIER_DECISION_BOUNDARY_MISMATCH")
        if decision.verifier_identity_digest != verifier.identity_digest:
            raise PermissionError("ROLLBACK_VERIFIER_DECISION_IDENTITY_MISMATCH")
        runner_time = _timestamp(runner_observation.observed_at, field="runner_observation.observed_at")
        verifier_time = _timestamp(observed_at, field="observed_at")
        if verifier_time < runner_time:
            raise PermissionError("ROLLBACK_VERIFIER_OBSERVATION_PRECEDES_RUNNER")
        claims = {
            "schema_version": 1,
            "observation_type": VERIFIER_GITHUB_REF_ABSENCE_OBSERVATION_TYPE,
            "repository": runner_observation.repository,
            "ref": runner_observation.ref,
            "target_digest": runner_observation.target_digest,
            "provider": GITHUB_PROVIDER,
            "provider_instance_id": verifier.provider_instance_id,
            "verifier_id": verifier.verifier_id,
            "verifier_identity_digest": verifier.identity_digest,
            "verification_boundary_digest": boundary.boundary_digest,
            "verifier_credential_decision_digest": decision.decision_digest,
            "runner_observation_digest": runner_observation.observation_digest,
            "execution_id": boundary.execution_id,
            "execution_epoch": boundary.execution_epoch,
            "source_identity": _text(source_identity, field="source_identity"),
            "http_status": HTTP_NOT_FOUND,
            "presence": ABSENT,
            "observed_at": observed_at,
            "observation_revision": _text(
                observation_revision,
                field="observation_revision",
            ),
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "observation_type"}
        }
        return cls(**values, observation_digest=_digest(claims))

    def _claims(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observation_type": VERIFIER_GITHUB_REF_ABSENCE_OBSERVATION_TYPE,
            **{
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "observation_digest"
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims(), "observation_digest": self.observation_digest}


def verify_github_ref_absence(
    *,
    runner_observation: GitHubRefAbsenceObservation,
    verifier_observation: VerifierGitHubRefAbsenceObservation,
    boundary: IndependentVerificationBoundaryV2,
    observed_post_state_revision: str,
    strength_revision: str,
    result_revision: str,
) -> tuple[ObservedPostState, VerificationStrength, VerificationResult]:
    if boundary.runner_observation_digest != runner_observation.observation_digest:
        raise PermissionError("ROLLBACK_VERIFICATION_RUNNER_BINDING_MISMATCH")
    if verifier_observation.verification_boundary_digest != boundary.boundary_digest:
        raise PermissionError("ROLLBACK_VERIFICATION_BOUNDARY_MISMATCH")
    if verifier_observation.runner_observation_digest != runner_observation.observation_digest:
        raise PermissionError("ROLLBACK_VERIFICATION_OBSERVATION_BINDING_MISMATCH")
    if (
        verifier_observation.repository != runner_observation.repository
        or verifier_observation.ref != runner_observation.ref
        or verifier_observation.target_digest != runner_observation.target_digest
    ):
        raise PermissionError("ROLLBACK_VERIFICATION_TARGET_MISMATCH")
    if runner_observation.presence != ABSENT or verifier_observation.presence != ABSENT:
        raise PermissionError("ROLLBACK_VERIFICATION_ABSENCE_NOT_PROVEN")

    observed_post_state = ObservedPostState.create(
        execution_id=boundary.execution_id,
        execution_epoch=boundary.execution_epoch,
        target_digest=boundary.target_digest,
        state_kind=GIT_REF_STATE_KIND,
        state_claims={
            "repository": verifier_observation.repository,
            "ref": verifier_observation.ref,
            "presence": ABSENT,
            "http_status": str(HTTP_NOT_FOUND),
        },
        provider=GITHUB_PROVIDER,
        provider_instance_id=verifier_observation.provider_instance_id,
        source_identity=verifier_observation.source_identity,
        verifier_id=verifier_observation.verifier_id,
        verifier_identity_digest=verifier_observation.verifier_identity_digest,
        verification_boundary_digest=boundary.boundary_digest,
        verifier_observation_digest=verifier_observation.observation_digest,
        observed_at=verifier_observation.observed_at,
        state_revision=_text(
            observed_post_state_revision,
            field="observed_post_state_revision",
        ),
    )
    strength = VerificationStrength.create(
        verification_boundary_digest=boundary.boundary_digest,
        verifier_observation_digest=verifier_observation.observation_digest,
        strength_revision=_text(strength_revision, field="strength_revision"),
    )
    result = VerificationResult.create(
        execution_id=boundary.execution_id,
        execution_epoch=boundary.execution_epoch,
        target_digest=boundary.target_digest,
        runner_observation_digest=runner_observation.observation_digest,
        verifier_observation_digest=verifier_observation.observation_digest,
        observed_post_state_digest=observed_post_state.state_digest,
        verification_boundary_digest=boundary.boundary_digest,
        verifier_id=verifier_observation.verifier_id,
        verifier_identity_digest=verifier_observation.verifier_identity_digest,
        verification_strength_digest=strength.strength_digest,
        verification_strength_class=strength.strength_class,
        verdict=VERIFIED,
        reason=OBSERVED_STATE_MATCH,
        checked_at=verifier_observation.observed_at,
        result_revision=_text(result_revision, field="result_revision"),
    )
    return observed_post_state, strength, result
