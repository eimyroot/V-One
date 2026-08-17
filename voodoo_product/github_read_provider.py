from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol, Self, runtime_checkable

from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget
from .isolated_runner import (
    CurrentExecutionFence,
    PreparedIsolatedRuntime,
    ReadOnlyRuntimeActivation,
)
from .trusted_clock import ClockWitness, TrustedClockAuthority

GITHUB_READ_REF_CAPABILITY: Final = "github.read-ref/v1"
GITHUB_REF_TARGET_KIND: Final = "git_ref"
GITHUB_REF_OBSERVATION_TYPE: Final = "github-ref-observation/v1"

_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
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
        "runner_id",
        "runner_boundary_digest",
        "credential_decision_digest",
        "runtime_activation_digest",
        "lease_id",
        "lease_digest",
        "execution_id",
        "execution_epoch",
        "execution_capsule_digest",
        "capability_definition_identity",
        "source_identity",
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


def _require_git_object_id(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if _GIT_OBJECT_ID_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field} must be a lowercase Git object id")
    return text


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


def _require_repository(value: object) -> str:
    repository = _require_text(value, field="repository")
    if _REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise ValueError("repository must use owner/name form")
    return repository


def _require_ref(value: object) -> str:
    ref = _require_text(value, field="ref")
    if not (ref.startswith("refs/heads/") or ref.startswith("refs/tags/")):
        raise ValueError("ref must be a fully-qualified heads or tags ref")
    suffix = ref.split("/", 2)[2]
    if (
        not suffix
        or suffix.startswith("/")
        or suffix.endswith("/")
        or "//" in suffix
        or ".." in suffix
        or "@{" in suffix
        or "\\" in suffix
        or any(character.isspace() or ord(character) < 32 for character in suffix)
        or any(character in "~^:?*[" for character in suffix)
    ):
        raise ValueError("ref is invalid")
    return ref


class GitHubReadDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@runtime_checkable
class GitHubReadTransport(Protocol):
    """Provider-specific READ-only port used after the D3 runtime boundary.

    Implementations may perform only the exact ref observation represented by this method.
    The port intentionally exposes no mutation method.
    """

    source_identity: str

    def read_ref(self, *, repository: str, ref: str) -> str:
        """Return the provider-observed commit object id for the exact Git ref."""
        ...


@dataclass(frozen=True, slots=True)
class GitHubRefObservation:
    repository: str
    ref: str
    commit_sha: str
    target_digest: str
    provider: str
    provider_instance_id: str
    runner_id: str
    runner_boundary_digest: str
    credential_decision_digest: str
    runtime_activation_digest: str
    lease_id: str
    lease_digest: str
    execution_id: str
    execution_epoch: int
    execution_capsule_digest: str
    capability_definition_identity: str
    source_identity: str
    clock_source_identity: str
    clock_witness_digest: str
    observed_at: str
    observation_revision: str
    observation_digest: str

    def __post_init__(self) -> None:
        _require_repository(self.repository)
        _require_ref(self.ref)
        _require_git_object_id(self.commit_sha, field="commit_sha")
        for field in (
            "target_digest",
            "runner_id",
            "runner_boundary_digest",
            "credential_decision_digest",
            "runtime_activation_digest",
            "lease_id",
            "lease_digest",
            "execution_capsule_digest",
            "capability_definition_identity",
            "clock_witness_digest",
            "observation_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "provider",
            "provider_instance_id",
            "execution_id",
            "source_identity",
            "clock_source_identity",
            "observed_at",
            "observation_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if isinstance(self.execution_epoch, bool) or not isinstance(self.execution_epoch, int):
            raise ValueError("execution_epoch must be an integer")
        if self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.observation_digest != _digest(self._claims_without_digest()):
            raise ValueError("observation_digest does not match GitHubRefObservation")

    @classmethod
    def create(
        cls,
        *,
        repository: str,
        ref: str,
        commit_sha: str,
        target: ExecutionTarget,
        prepared: PreparedIsolatedRuntime,
        activation: ReadOnlyRuntimeActivation,
        source_identity: str,
        clock_witness: ClockWitness,
        observation_revision: str,
    ) -> Self:
        if not isinstance(target, ExecutionTarget):
            raise ValueError("target must be ExecutionTarget")
        if not isinstance(prepared, PreparedIsolatedRuntime):
            raise ValueError("prepared must be PreparedIsolatedRuntime")
        if not isinstance(activation, ReadOnlyRuntimeActivation):
            raise ValueError("activation must be ReadOnlyRuntimeActivation")
        if not isinstance(clock_witness, ClockWitness):
            raise ValueError("clock_witness must be ClockWitness")
        _assert_activation_bound(prepared=prepared, activation=activation)
        repository = _require_repository(repository)
        ref = _require_ref(ref)
        commit_sha = _require_git_object_id(commit_sha, field="commit_sha")
        _require_text(source_identity, field="source_identity")
        _require_text(observation_revision, field="observation_revision")
        if clock_witness.environment != prepared.lease.environment:
            raise GitHubReadDenied("GITHUB_READ_CLOCK_ENVIRONMENT_MISMATCH")

        claims = {
            "schema_version": 1,
            "observation_type": GITHUB_REF_OBSERVATION_TYPE,
            "repository": repository,
            "ref": ref,
            "commit_sha": commit_sha,
            "target_digest": target.target_digest,
            "provider": activation.provider,
            "provider_instance_id": activation.provider_instance_id,
            "runner_id": activation.runner_id,
            "runner_boundary_digest": activation.runner_boundary_digest,
            "credential_decision_digest": activation.credential_decision_digest,
            "runtime_activation_digest": activation.activation_digest,
            "lease_id": activation.lease_id,
            "lease_digest": activation.lease_digest,
            "execution_id": activation.execution_id,
            "execution_epoch": activation.execution_epoch,
            "execution_capsule_digest": activation.execution_capsule_digest,
            "capability_definition_identity": activation.capability_definition_identity,
            "source_identity": source_identity,
            "clock_source_identity": clock_witness.source_identity,
            "clock_witness_digest": clock_witness.witness_digest,
            "observed_at": clock_witness.observed_at,
            "observation_revision": observation_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "observation_type"}
        }
        return cls(**values, observation_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _OBSERVATION_FIELDS, contract=GITHUB_REF_OBSERVATION_TYPE)
        if (
            value["schema_version"] != 1
            or value["observation_type"] != GITHUB_REF_OBSERVATION_TYPE
        ):
            raise ValueError("github-ref-observation/v1 schema or type is unsupported")
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
            "observation_type": GITHUB_REF_OBSERVATION_TYPE,
            "repository": self.repository,
            "ref": self.ref,
            "commit_sha": self.commit_sha,
            "target_digest": self.target_digest,
            "provider": self.provider,
            "provider_instance_id": self.provider_instance_id,
            "runner_id": self.runner_id,
            "runner_boundary_digest": self.runner_boundary_digest,
            "credential_decision_digest": self.credential_decision_digest,
            "runtime_activation_digest": self.runtime_activation_digest,
            "lease_id": self.lease_id,
            "lease_digest": self.lease_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "source_identity": self.source_identity,
            "clock_source_identity": self.clock_source_identity,
            "clock_witness_digest": self.clock_witness_digest,
            "observed_at": self.observed_at,
            "observation_revision": self.observation_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "observation_digest": self.observation_digest}


class GitHubRefReadHandler:
    """D4a exact GitHub ref READ handler over the D3 activated runtime boundary.

    This handler performs one provider observation only. It has no mutation operation and it
    rechecks the durable C4 current lease immediately before crossing the provider READ port.
    """

    def __init__(
        self,
        *,
        transport: GitHubReadTransport,
        current_fence: CurrentExecutionFence,
        trusted_clock: TrustedClockAuthority,
        observation_revision: str,
    ) -> None:
        if not isinstance(transport, GitHubReadTransport):
            raise ValueError("transport must implement GitHubReadTransport")
        if not isinstance(current_fence, CurrentExecutionFence):
            raise ValueError("current_fence must implement CurrentExecutionFence")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock must be TrustedClockAuthority")
        self.transport = transport
        self.current_fence = current_fence
        self.trusted_clock = trusted_clock
        self.observation_revision = _require_text(
            observation_revision,
            field="observation_revision",
        )
        _require_text(self.transport.source_identity, field="source_identity")

    def observe_ref(
        self,
        *,
        prepared: PreparedIsolatedRuntime,
        activation: ReadOnlyRuntimeActivation,
        target: ExecutionTarget,
    ) -> GitHubRefObservation:
        if not isinstance(prepared, PreparedIsolatedRuntime):
            raise ValueError("prepared must be PreparedIsolatedRuntime")
        if not isinstance(activation, ReadOnlyRuntimeActivation):
            raise ValueError("activation must be ReadOnlyRuntimeActivation")
        if not isinstance(target, ExecutionTarget):
            raise ValueError("target must be ExecutionTarget")
        _assert_activation_bound(prepared=prepared, activation=activation)
        repository, ref = _parse_git_ref_target(target)

        # This is intentionally the final control-plane decision before the provider READ.
        self.current_fence.assert_current(lease=prepared.lease)
        commit_sha = self.transport.read_ref(repository=repository, ref=ref)
        commit_sha = _require_git_object_id(commit_sha, field="commit_sha")

        clock_witness = self.trusted_clock.witness(environment=prepared.lease.environment)
        return GitHubRefObservation.create(
            repository=repository,
            ref=ref,
            commit_sha=commit_sha,
            target=target,
            prepared=prepared,
            activation=activation,
            source_identity=self.transport.source_identity,
            clock_witness=clock_witness,
            observation_revision=self.observation_revision,
        )


def _parse_git_ref_target(target: ExecutionTarget) -> tuple[str, str]:
    if target.target_kind != GITHUB_REF_TARGET_KIND:
        raise GitHubReadDenied("GITHUB_READ_TARGET_KIND_MISMATCH")
    claims = target.target_claims
    if frozenset(claims) != {"repository", "ref"}:
        raise GitHubReadDenied("GITHUB_READ_TARGET_FIELDS_INVALID")
    try:
        repository = _require_repository(claims["repository"])
        ref = _require_ref(claims["ref"])
    except ValueError as exc:
        raise GitHubReadDenied("GITHUB_READ_TARGET_INVALID") from exc
    return repository, ref


def _assert_activation_bound(
    *,
    prepared: PreparedIsolatedRuntime,
    activation: ReadOnlyRuntimeActivation,
) -> None:
    if activation.provider != prepared.bootstrap.provider:
        raise GitHubReadDenied("GITHUB_READ_PROVIDER_MISMATCH")
    if activation.provider_instance_id != prepared.bootstrap.provider_instance_id:
        raise GitHubReadDenied("GITHUB_READ_PROVIDER_INSTANCE_MISMATCH")
    if activation.runner_id != prepared.identity.runner_id:
        raise GitHubReadDenied("GITHUB_READ_RUNNER_MISMATCH")
    if activation.runner_identity_digest != prepared.identity.identity_digest:
        raise GitHubReadDenied("GITHUB_READ_RUNNER_IDENTITY_MISMATCH")
    if activation.runner_boundary_digest != prepared.boundary.boundary_digest:
        raise GitHubReadDenied("GITHUB_READ_BOUNDARY_MISMATCH")
    if activation.credential_decision_id != prepared.decision.decision_id:
        raise GitHubReadDenied("GITHUB_READ_CREDENTIAL_DECISION_MISMATCH")
    if activation.credential_decision_digest != prepared.decision.decision_digest:
        raise GitHubReadDenied("GITHUB_READ_CREDENTIAL_DECISION_MISMATCH")
    if activation.lease_id != prepared.lease.lease_id:
        raise GitHubReadDenied("GITHUB_READ_LEASE_MISMATCH")
    if activation.lease_digest != prepared.lease.lease_digest:
        raise GitHubReadDenied("GITHUB_READ_LEASE_MISMATCH")
    if activation.execution_epoch != prepared.lease.execution_epoch:
        raise GitHubReadDenied("GITHUB_READ_EPOCH_MISMATCH")
    if activation.execution_capsule_digest != prepared.boundary.execution_capsule_digest:
        raise GitHubReadDenied("GITHUB_READ_CAPSULE_MISMATCH")
    if (
        activation.capability_definition_identity
        != prepared.boundary.capability_definition_identity
    ):
        raise GitHubReadDenied("GITHUB_READ_CAPABILITY_MISMATCH")
    if prepared.decision.provider != "github":
        raise GitHubReadDenied("GITHUB_READ_CREDENTIAL_PROVIDER_MISMATCH")
    if prepared.decision.access_mode != "READ_ONLY":
        raise GitHubReadDenied("GITHUB_READ_CREDENTIAL_NOT_READ_ONLY")
    if prepared.decision.provider_mutation_allowed is not False:
        raise GitHubReadDenied("GITHUB_READ_MUTATION_ALLOWED")
