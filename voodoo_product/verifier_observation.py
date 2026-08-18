from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget
from .github_read_provider import GitHubReadTransport, _parse_git_ref_target
from .trusted_clock import ClockWitness, TrustedClockAuthority
from .verifier_credential import READ_ONLY_ACCESS_MODE, VerifierCredentialDecision
from .verifier_identity import IndependentVerificationBoundary, VerifierIdentity

VERIFIER_GITHUB_REF_OBSERVATION_TYPE: Final = "verifier-github-ref-observation/v1"
_GIT_OBJECT_ID_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")

_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version",
        "observation_type",
        "repository",
        "ref",
        "commit_sha",
        "target_digest",
        "provider",
        "provider_instance_id",
        "verifier_id",
        "verifier_identity_digest",
        "verification_boundary_digest",
        "verifier_credential_decision_id",
        "verifier_credential_decision_digest",
        "runner_observation_digest",
        "execution_id",
        "execution_epoch",
        "source_identity",
        "access_clock_source_identity",
        "access_clock_witness_digest",
        "credential_checked_at",
        "clock_source_identity",
        "clock_witness_digest",
        "observed_at",
        "observation_revision",
        "observation_digest",
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


def _require_git_object_id(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if _GIT_OBJECT_ID_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field} must be a lowercase Git object id")
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


class VerifierGitHubReadDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _assert_exact_binding(
    *,
    verifier: VerifierIdentity,
    boundary: IndependentVerificationBoundary,
    decision: VerifierCredentialDecision,
    target: ExecutionTarget,
) -> None:
    if not isinstance(verifier, VerifierIdentity):
        raise ValueError("verifier must be VerifierIdentity")
    if not isinstance(boundary, IndependentVerificationBoundary):
        raise ValueError("boundary must be IndependentVerificationBoundary")
    if not isinstance(decision, VerifierCredentialDecision):
        raise ValueError("decision must be VerifierCredentialDecision")
    if not isinstance(target, ExecutionTarget):
        raise ValueError("target must be ExecutionTarget")

    if verifier.verifier_id != boundary.verifier_id:
        raise VerifierGitHubReadDenied("VERIFIER_IDENTITY_BINDING_MISMATCH")
    if verifier.identity_digest != boundary.verifier_identity_digest:
        raise VerifierGitHubReadDenied("VERIFIER_IDENTITY_DIGEST_MISMATCH")
    if verifier.verifier_class != boundary.verifier_class:
        raise VerifierGitHubReadDenied("VERIFIER_CLASS_MISMATCH")
    if verifier.provider != boundary.verifier_provider:
        raise VerifierGitHubReadDenied("VERIFIER_PROVIDER_MISMATCH")
    if verifier.provider_instance_id != boundary.verifier_provider_instance_id:
        raise VerifierGitHubReadDenied("VERIFIER_PROVIDER_INSTANCE_MISMATCH")
    if verifier.credential_class != boundary.verifier_credential_class:
        raise VerifierGitHubReadDenied("VERIFIER_CREDENTIAL_CLASS_MISMATCH")
    if verifier.environment != boundary.environment:
        raise VerifierGitHubReadDenied("VERIFIER_ENVIRONMENT_MISMATCH")

    if decision.verifier_id != verifier.verifier_id:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_IDENTITY_MISMATCH")
    if decision.verifier_identity_digest != verifier.identity_digest:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_IDENTITY_DIGEST_MISMATCH")
    if decision.verification_boundary_digest != boundary.boundary_digest:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_BOUNDARY_MISMATCH")
    if decision.runner_observation_digest != boundary.runner_observation_digest:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_RUNNER_OBSERVATION_MISMATCH")
    if decision.target_digest != boundary.target_digest or decision.target_digest != target.target_digest:
        raise VerifierGitHubReadDenied("VERIFIER_TARGET_BINDING_MISMATCH")
    if decision.execution_id != boundary.execution_id:
        raise VerifierGitHubReadDenied("VERIFIER_EXECUTION_BINDING_MISMATCH")
    if decision.execution_epoch != boundary.execution_epoch:
        raise VerifierGitHubReadDenied("VERIFIER_EXECUTION_EPOCH_MISMATCH")
    if decision.credential_class != verifier.credential_class:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_CREDENTIAL_CLASS_MISMATCH")
    if decision.provider != verifier.provider:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_PROVIDER_MISMATCH")
    if decision.environment != verifier.environment:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_ENVIRONMENT_MISMATCH")
    if decision.access_mode != READ_ONLY_ACCESS_MODE:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_NOT_READ_ONLY")
    if decision.provider_mutation_allowed is not False:
        raise VerifierGitHubReadDenied("VERIFIER_DECISION_MUTATION_ALLOWED")
    if boundary.provider_mutation_allowed is not False:
        raise VerifierGitHubReadDenied("VERIFIER_BOUNDARY_MUTATION_ALLOWED")


def _assert_credential_current(
    *,
    decision: VerifierCredentialDecision,
    clock_witness: ClockWitness,
) -> None:
    if clock_witness.environment != decision.environment:
        raise VerifierGitHubReadDenied("VERIFIER_CLOCK_ENVIRONMENT_MISMATCH")
    _, observed = _require_timestamp(clock_witness.observed_at, field="clock_witness.observed_at")
    _, valid_from = _require_timestamp(decision.valid_from, field="decision.valid_from")
    _, expires_at = _require_timestamp(decision.expires_at, field="decision.expires_at")
    if observed < valid_from:
        raise VerifierGitHubReadDenied("VERIFIER_CREDENTIAL_NOT_YET_VALID")
    if observed >= expires_at:
        raise VerifierGitHubReadDenied("VERIFIER_CREDENTIAL_EXPIRED")


@dataclass(frozen=True, slots=True)
class VerifierGitHubRefObservation:
    """Independent Phase-E provider observation produced by a Verifier.

    This is an Observation subtype only. It is not ObservedPostState, VerificationResult,
    attestation or OperationProof and therefore does not assert that the Runner result is correct.
    """

    repository: str
    ref: str
    commit_sha: str
    target_digest: str
    provider: str
    provider_instance_id: str
    verifier_id: str
    verifier_identity_digest: str
    verification_boundary_digest: str
    verifier_credential_decision_id: str
    verifier_credential_decision_digest: str
    runner_observation_digest: str
    execution_id: str
    execution_epoch: int
    source_identity: str
    access_clock_source_identity: str
    access_clock_witness_digest: str
    credential_checked_at: str
    clock_source_identity: str
    clock_witness_digest: str
    observed_at: str
    observation_revision: str
    observation_digest: str

    def __post_init__(self) -> None:
        _require_text(self.repository, field="repository")
        _require_text(self.ref, field="ref")
        _require_git_object_id(self.commit_sha, field="commit_sha")
        for field in (
            "target_digest",
            "verifier_id",
            "verifier_identity_digest",
            "verification_boundary_digest",
            "verifier_credential_decision_id",
            "verifier_credential_decision_digest",
            "runner_observation_digest",
            "access_clock_witness_digest",
            "clock_witness_digest",
            "observation_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "provider",
            "provider_instance_id",
            "execution_id",
            "source_identity",
            "access_clock_source_identity",
            "clock_source_identity",
            "observation_revision",
        ):
            _require_text(getattr(self, field), field=field)
        _require_timestamp(self.credential_checked_at, field="credential_checked_at")
        _require_timestamp(self.observed_at, field="observed_at")
        if type(self.execution_epoch) is not int or self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.observation_digest != _digest(self._claims_without_digest()):
            raise ValueError("observation_digest does not match VerifierGitHubRefObservation")

    @classmethod
    def create(
        cls,
        *,
        repository: str,
        ref: str,
        commit_sha: str,
        target: ExecutionTarget,
        verifier: VerifierIdentity,
        boundary: IndependentVerificationBoundary,
        decision: VerifierCredentialDecision,
        access_clock_witness: ClockWitness,
        observation_clock_witness: ClockWitness,
        source_identity: str,
        observation_revision: str,
    ) -> Self:
        _assert_exact_binding(
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            target=target,
        )
        _assert_credential_current(decision=decision, clock_witness=access_clock_witness)
        if observation_clock_witness.environment != verifier.environment:
            raise VerifierGitHubReadDenied("VERIFIER_OBSERVATION_CLOCK_ENVIRONMENT_MISMATCH")
        _require_text(repository, field="repository")
        _require_text(ref, field="ref")
        _require_git_object_id(commit_sha, field="commit_sha")
        _require_text(source_identity, field="source_identity")
        _require_text(observation_revision, field="observation_revision")

        claims: dict[str, Any] = {
            "schema_version": 1,
            "observation_type": VERIFIER_GITHUB_REF_OBSERVATION_TYPE,
            "repository": repository,
            "ref": ref,
            "commit_sha": commit_sha,
            "target_digest": target.target_digest,
            "provider": verifier.provider,
            "provider_instance_id": verifier.provider_instance_id,
            "verifier_id": verifier.verifier_id,
            "verifier_identity_digest": verifier.identity_digest,
            "verification_boundary_digest": boundary.boundary_digest,
            "verifier_credential_decision_id": decision.decision_id,
            "verifier_credential_decision_digest": decision.decision_digest,
            "runner_observation_digest": boundary.runner_observation_digest,
            "execution_id": boundary.execution_id,
            "execution_epoch": boundary.execution_epoch,
            "source_identity": source_identity,
            "access_clock_source_identity": access_clock_witness.source_identity,
            "access_clock_witness_digest": access_clock_witness.witness_digest,
            "credential_checked_at": access_clock_witness.observed_at,
            "clock_source_identity": observation_clock_witness.source_identity,
            "clock_witness_digest": observation_clock_witness.witness_digest,
            "observed_at": observation_clock_witness.observed_at,
            "observation_revision": observation_revision,
        }
        values = {
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        }
        return cls(**values, observation_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _OBSERVATION_FIELDS, contract=VERIFIER_GITHUB_REF_OBSERVATION_TYPE)
        if (
            value["schema_version"] != 1
            or value["observation_type"] != VERIFIER_GITHUB_REF_OBSERVATION_TYPE
        ):
            raise ValueError("verifier-github-ref-observation/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _OBSERVATION_FIELDS
                if key not in {"schema_version", "observation_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observation_type": VERIFIER_GITHUB_REF_OBSERVATION_TYPE,
            "repository": self.repository,
            "ref": self.ref,
            "commit_sha": self.commit_sha,
            "target_digest": self.target_digest,
            "provider": self.provider,
            "provider_instance_id": self.provider_instance_id,
            "verifier_id": self.verifier_id,
            "verifier_identity_digest": self.verifier_identity_digest,
            "verification_boundary_digest": self.verification_boundary_digest,
            "verifier_credential_decision_id": self.verifier_credential_decision_id,
            "verifier_credential_decision_digest": self.verifier_credential_decision_digest,
            "runner_observation_digest": self.runner_observation_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "source_identity": self.source_identity,
            "access_clock_source_identity": self.access_clock_source_identity,
            "access_clock_witness_digest": self.access_clock_witness_digest,
            "credential_checked_at": self.credential_checked_at,
            "clock_source_identity": self.clock_source_identity,
            "clock_witness_digest": self.clock_witness_digest,
            "observed_at": self.observed_at,
            "observation_revision": self.observation_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "observation_digest": self.observation_digest}


class VerifierGitHubRefReadHandler:
    """Perform one independently credentialed, READ-only GitHub ref observation."""

    def __init__(
        self,
        *,
        transport: GitHubReadTransport,
        trusted_clock: TrustedClockAuthority,
        observation_revision: str,
    ) -> None:
        if not isinstance(transport, GitHubReadTransport):
            raise ValueError("transport must implement GitHubReadTransport")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock must be TrustedClockAuthority")
        self.transport = transport
        self.trusted_clock = trusted_clock
        self.observation_revision = _require_text(observation_revision, field="observation_revision")
        _require_text(self.transport.source_identity, field="source_identity")

    def observe_ref(
        self,
        *,
        verifier: VerifierIdentity,
        boundary: IndependentVerificationBoundary,
        decision: VerifierCredentialDecision,
        target: ExecutionTarget,
    ) -> VerifierGitHubRefObservation:
        _assert_exact_binding(
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            target=target,
        )
        try:
            repository, ref = _parse_git_ref_target(target)
        except PermissionError as exc:
            raise VerifierGitHubReadDenied("VERIFIER_TARGET_INVALID") from exc

        # The verifier credential is checked against a fresh trusted clock immediately before READ.
        access_clock_witness = self.trusted_clock.witness(environment=verifier.environment)
        _assert_credential_current(decision=decision, clock_witness=access_clock_witness)
        commit_sha = _require_git_object_id(
            self.transport.read_ref(repository=repository, ref=ref),
            field="commit_sha",
        )
        observation_clock_witness = self.trusted_clock.witness(environment=verifier.environment)

        return VerifierGitHubRefObservation.create(
            repository=repository,
            ref=ref,
            commit_sha=commit_sha,
            target=target,
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            access_clock_witness=access_clock_witness,
            observation_clock_witness=observation_clock_witness,
            source_identity=self.transport.source_identity,
            observation_revision=self.observation_revision,
        )
