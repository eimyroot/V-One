from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import ExecutionTarget
from voodoo_product.github_read_provider import GitHubRefObservation
from voodoo_product.runner_identity import (
    DENY_ALL_NETWORK_DEFAULT,
    READ_ONLY_EFFECT_CLASS,
    RUNNER_BOUNDARY_TYPE,
    RunnerBoundary,
    RunnerIdentity,
)
from voodoo_product.trusted_clock import TrustedClockAuthority
from voodoo_product.verifier_credential import VerifierCredentialDecision, VerifierCredentialPolicy
from voodoo_product.verifier_identity import IndependentVerificationBoundary, VerifierIdentity
from voodoo_product.verifier_observation import (
    VERIFIER_GITHUB_REF_OBSERVATION_TYPE,
    VerifierGitHubReadDenied,
    VerifierGitHubRefObservation,
    VerifierGitHubRefReadHandler,
)

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
DA = "a" * 64
DB = "b" * 64
DC = "c" * 64


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def read(self) -> datetime:
        return self.value


class FakeGitHubReadTransport:
    source_identity = "github-api/git-ref/e3-test"

    def __init__(self, events: list[str], *, commit_sha: str = "b" * 40) -> None:
        self.events = events
        self.commit_sha = commit_sha

    def read_ref(self, *, repository: str, ref: str) -> str:
        self.events.append(f"read:{repository}:{ref}")
        return self.commit_sha


def _runner_evidence(target: ExecutionTarget) -> tuple[RunnerIdentity, RunnerBoundary, GitHubRefObservation]:
    runner = RunnerIdentity.create(
        runner_class="github-actions.docker-isolated/v1",
        provider="github-actions",
        provider_instance_id="gha:runner:e3",
        environment="staging",
        rootfs_digest=DA,
        resource_limit_profile_digest=DB,
        network_policy_digest=DC,
        identity_revision="runner-identity/e3-test-r1",
    )
    boundary_claims: dict[str, Any] = {
        "schema_version": 1,
        "boundary_type": RUNNER_BOUNDARY_TYPE,
        "runner_id": runner.runner_id,
        "runner_identity_digest": runner.identity_digest,
        "lease_id": D1,
        "lease_digest": D2,
        "admission_id": D3,
        "execution_id": "exec_e3",
        "execution_epoch": 1,
        "execution_capsule_digest": D4,
        "capability_definition_identity": D5,
        "environment": "staging",
        "runner_class": runner.runner_class,
        "credential_class": "github.actions-token.read/v1",
        "effect_ceiling": READ_ONLY_EFFECT_CLASS,
        "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
        "provider_mutation_allowed": False,
        "boundary_revision": "runner-boundary/e3-test-r1",
    }
    runner_boundary = RunnerBoundary(
        **{
            key: value
            for key, value in boundary_claims.items()
            if key not in {"schema_version", "boundary_type"}
        },
        boundary_digest=_digest(boundary_claims),
    )
    observation_claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "github-ref-observation/v1",
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/main",
        "commit_sha": "a" * 40,
        "target_digest": target.target_digest,
        "provider": runner.provider,
        "provider_instance_id": runner.provider_instance_id,
        "runner_id": runner.runner_id,
        "runner_boundary_digest": runner_boundary.boundary_digest,
        "credential_decision_digest": DA,
        "runtime_activation_digest": DB,
        "lease_id": runner_boundary.lease_id,
        "lease_digest": runner_boundary.lease_digest,
        "execution_id": runner_boundary.execution_id,
        "execution_epoch": runner_boundary.execution_epoch,
        "execution_capsule_digest": runner_boundary.execution_capsule_digest,
        "capability_definition_identity": runner_boundary.capability_definition_identity,
        "source_identity": "github-api/git-ref/v1",
        "clock_source_identity": "trusted-clock/e3-runner-test",
        "clock_witness_digest": DC,
        "observed_at": "2026-08-18T12:00:00.000+00:00",
        "observation_revision": "github-ref-observation/e3-runner-test-r1",
    }
    observation = GitHubRefObservation(
        **{
            key: value
            for key, value in observation_claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(observation_claims),
    )
    return runner, runner_boundary, observation


def _bundle(
    *,
    valid_from: str = "2026-08-18T12:00:00.000+00:00",
    expires_at: str = "2026-08-18T12:05:00.000+00:00",
) -> tuple[
    ExecutionTarget,
    VerifierIdentity,
    IndependentVerificationBoundary,
    VerifierCredentialDecision,
]:
    target = ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={"repository": "nulleimy/V-One", "ref": "refs/heads/main"},
    )
    runner, runner_boundary, runner_observation = _runner_evidence(target)
    verifier = VerifierIdentity.create(
        verifier_class="github-actions.docker-isolated-verifier/v1",
        provider="github-actions",
        provider_instance_id="gha:verifier:e3",
        environment="staging",
        credential_class="github.actions-token.verifier-read/v1",
        rootfs_digest=DA,
        resource_limit_profile_digest=DB,
        network_policy_digest=DC,
        identity_revision="verifier-identity/e3-r1",
    )
    boundary = IndependentVerificationBoundary.create(
        verifier=verifier,
        runner_identity=runner,
        runner_boundary=runner_boundary,
        runner_observation=runner_observation,
        boundary_revision="independent-verification-boundary/e3-r1",
    )
    policy = VerifierCredentialPolicy.create(
        credential_class=verifier.credential_class,
        provider=verifier.provider,
        audience="api.github.com",
        enabled_environments=("staging",),
        max_ttl_seconds=300,
        policy_revision="verifier-credential-policy/e3-r1",
    )
    decision = VerifierCredentialDecision.create(
        verifier=verifier,
        boundary=boundary,
        policy=policy,
        valid_from=valid_from,
        expires_at=expires_at,
        decision_revision="verifier-credential-decision/e3-r1",
    )
    return target, verifier, boundary, decision


def _handler(clock: MutableClock, events: list[str]) -> VerifierGitHubRefReadHandler:
    trusted_clock = TrustedClockAuthority(
        source_identity="trusted-clock/e3-verifier-test",
        authority_revision="trusted-clock/e3-r1",
        source=clock,
        allowed_environments=frozenset({"staging"}),
    )
    return VerifierGitHubRefReadHandler(
        transport=FakeGitHubReadTransport(events),
        trusted_clock=trusted_clock,
        observation_revision="verifier-github-ref-observation/e3-r1",
    )


def test_independent_verifier_observation_is_content_addressed_and_round_trippable() -> None:
    target, verifier, boundary, decision = _bundle()
    events: list[str] = []
    clock = MutableClock(datetime(2026, 8, 18, 12, 1, tzinfo=UTC))

    observation = _handler(clock, events).observe_ref(
        verifier=verifier,
        boundary=boundary,
        decision=decision,
        target=target,
    )

    assert events == ["read:nulleimy/V-One:refs/heads/main"]
    assert observation.commit_sha == "b" * 40
    assert observation.observation_digest == _digest(
        {key: value for key, value in observation.to_dict().items() if key != "observation_digest"}
    )
    assert observation.to_dict()["observation_type"] == VERIFIER_GITHUB_REF_OBSERVATION_TYPE
    assert VerifierGitHubRefObservation.from_dict(observation.to_dict()) == observation


def test_verifier_observation_binds_independent_identity_decision_and_runner_evidence() -> None:
    target, verifier, boundary, decision = _bundle()
    events: list[str] = []
    clock = MutableClock(datetime(2026, 8, 18, 12, 1, tzinfo=UTC))

    observation = _handler(clock, events).observe_ref(
        verifier=verifier,
        boundary=boundary,
        decision=decision,
        target=target,
    )

    assert observation.verifier_id == verifier.verifier_id
    assert observation.verifier_identity_digest == verifier.identity_digest
    assert observation.verification_boundary_digest == boundary.boundary_digest
    assert observation.verifier_credential_decision_digest == decision.decision_digest
    assert observation.runner_observation_digest == boundary.runner_observation_digest
    assert observation.target_digest == target.target_digest
    assert observation.execution_id == boundary.execution_id
    assert observation.execution_epoch == boundary.execution_epoch


def test_expired_verifier_credential_fails_before_provider_read() -> None:
    target, verifier, boundary, decision = _bundle(
        valid_from="2026-08-18T11:55:00.000+00:00",
        expires_at="2026-08-18T12:00:00.000+00:00",
    )
    events: list[str] = []
    clock = MutableClock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))

    with pytest.raises(VerifierGitHubReadDenied, match="VERIFIER_CREDENTIAL_EXPIRED"):
        _handler(clock, events).observe_ref(
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            target=target,
        )

    assert events == []


def test_target_substitution_fails_before_provider_read() -> None:
    _, verifier, boundary, decision = _bundle()
    substituted = ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={"repository": "nulleimy/V-One", "ref": "refs/heads/other"},
    )
    events: list[str] = []
    clock = MutableClock(datetime(2026, 8, 18, 12, 1, tzinfo=UTC))

    with pytest.raises(VerifierGitHubReadDenied, match="VERIFIER_TARGET_BINDING_MISMATCH"):
        _handler(clock, events).observe_ref(
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            target=substituted,
        )

    assert events == []


def test_verifier_observation_contains_no_secret_or_runner_authority_fields() -> None:
    target, verifier, boundary, decision = _bundle()
    events: list[str] = []
    clock = MutableClock(datetime(2026, 8, 18, 12, 1, tzinfo=UTC))
    payload = _handler(clock, events).observe_ref(
        verifier=verifier,
        boundary=boundary,
        decision=decision,
        target=target,
    ).to_dict()

    forbidden = {
        "token",
        "secret",
        "lease_id",
        "lease_digest",
        "runner_id",
        "runner_boundary_digest",
        "runtime_activation_digest",
        "verification_result",
    }
    assert forbidden.isdisjoint(payload)
    assert payload["runner_observation_digest"] == boundary.runner_observation_digest
