from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.github_read_provider import GitHubRefObservation
from voodoo_product.runner_identity import DENY_ALL_NETWORK_DEFAULT, READ_ONLY_EFFECT_CLASS
from voodoo_product.verification_result import (
    GIT_REF_STATE_KIND,
    INDEPENDENT_PROVIDER_READBACK,
    NOT_VERIFIED,
    OBSERVED_POST_STATE_TYPE,
    OBSERVED_STATE_MATCH,
    OBSERVED_STATE_MISMATCH,
    SEQUENTIAL_READBACK_NON_ATOMIC,
    VERIFIED,
    VERIFICATION_RESULT_TYPE,
    VERIFICATION_STRENGTH_TYPE,
    ObservedPostState,
    VerificationEvidenceDenied,
    VerificationResult,
    VerificationStrength,
    verify_github_ref_readback,
)
from voodoo_product.verifier_identity import (
    INDEPENDENCE_CLASS,
    IndependentVerificationBoundary,
)
from voodoo_product.verifier_observation import VerifierGitHubRefObservation

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
D6 = "6" * 64
D7 = "7" * 64
D8 = "8" * 64
DA = "a" * 64
DB = "b" * 64
DC = "c" * 64
DD = "d" * 64
DE = "e" * 64


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _runner_observation(*, commit_sha: str = "a" * 40) -> GitHubRefObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "github-ref-observation/v1",
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/main",
        "commit_sha": commit_sha,
        "target_digest": D1,
        "provider": "github-actions",
        "provider_instance_id": "gha:runner:e4",
        "runner_id": D2,
        "runner_boundary_digest": D3,
        "credential_decision_digest": D4,
        "runtime_activation_digest": D5,
        "lease_id": D6,
        "lease_digest": D7,
        "execution_id": "exec_e4",
        "execution_epoch": 1,
        "execution_capsule_digest": D8,
        "capability_definition_identity": DA,
        "source_identity": "github-api/git-ref/v1",
        "clock_source_identity": "trusted-clock/e4-runner",
        "clock_witness_digest": DB,
        "observed_at": "2026-08-18T12:00:00.000+00:00",
        "observation_revision": "github-ref-observation/e4-test-r1",
    }
    return GitHubRefObservation(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(claims),
    )


def _boundary(runner: GitHubRefObservation) -> IndependentVerificationBoundary:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "boundary_type": "independent-verification-boundary/v1",
        "verifier_id": DC,
        "verifier_identity_digest": DD,
        "verifier_class": "github-actions.docker-isolated-verifier/v1",
        "verifier_provider": "github-actions",
        "verifier_provider_instance_id": "gha:verifier:e4",
        "verifier_credential_class": "github.actions-token.verifier-read/v1",
        "runner_id": runner.runner_id,
        "runner_identity_digest": DE,
        "runner_boundary_digest": runner.runner_boundary_digest,
        "runner_provider_instance_id": runner.provider_instance_id,
        "runner_credential_class": "github.actions-token.read/v1",
        "execution_id": runner.execution_id,
        "execution_epoch": runner.execution_epoch,
        "target_digest": runner.target_digest,
        "runner_observation_digest": runner.observation_digest,
        "environment": "staging",
        "effect_ceiling": READ_ONLY_EFFECT_CLASS,
        "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
        "provider_mutation_allowed": False,
        "independence_class": INDEPENDENCE_CLASS,
        "boundary_revision": "independent-verification-boundary/e4-test-r1",
    }
    return IndependentVerificationBoundary(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "boundary_type"}
        },
        boundary_digest=_digest(claims),
    )


def _verifier_observation(
    runner: GitHubRefObservation,
    boundary: IndependentVerificationBoundary,
    *,
    commit_sha: str = "a" * 40,
    observed_at: str = "2026-08-18T12:01:00.000+00:00",
    runner_observation_digest: str | None = None,
) -> VerifierGitHubRefObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "verifier-github-ref-observation/v1",
        "repository": runner.repository,
        "ref": runner.ref,
        "commit_sha": commit_sha,
        "target_digest": runner.target_digest,
        "provider": boundary.verifier_provider,
        "provider_instance_id": boundary.verifier_provider_instance_id,
        "verifier_id": boundary.verifier_id,
        "verifier_identity_digest": boundary.verifier_identity_digest,
        "verification_boundary_digest": boundary.boundary_digest,
        "verifier_credential_decision_id": D4,
        "verifier_credential_decision_digest": D5,
        "runner_observation_digest": (
            runner.observation_digest
            if runner_observation_digest is None
            else runner_observation_digest
        ),
        "execution_id": runner.execution_id,
        "execution_epoch": runner.execution_epoch,
        "source_identity": "github-api/git-ref/v1",
        "access_clock_source_identity": "trusted-clock/e4-verifier",
        "access_clock_witness_digest": D6,
        "credential_checked_at": observed_at,
        "clock_source_identity": "trusted-clock/e4-verifier",
        "clock_witness_digest": D7,
        "observed_at": observed_at,
        "observation_revision": "verifier-github-ref-observation/e4-test-r1",
    }
    return VerifierGitHubRefObservation(
        **{
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(claims),
    )


def _verify(
    *,
    runner_commit: str = "a" * 40,
    verifier_commit: str = "a" * 40,
    verifier_time: str = "2026-08-18T12:01:00.000+00:00",
) -> tuple[ObservedPostState, VerificationStrength, VerificationResult]:
    runner = _runner_observation(commit_sha=runner_commit)
    boundary = _boundary(runner)
    verifier = _verifier_observation(
        runner,
        boundary,
        commit_sha=verifier_commit,
        observed_at=verifier_time,
    )
    return verify_github_ref_readback(
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state_revision="observed-post-state/e4-test-r1",
        strength_revision="verification-strength/e4-test-r1",
        result_revision="verification-result/e4-test-r1",
    )


def test_matching_independent_readback_is_verified_and_round_trippable() -> None:
    state, strength, result = _verify()

    assert state.to_dict()["observed_post_state_type"] == OBSERVED_POST_STATE_TYPE
    assert state.state_kind == GIT_REF_STATE_KIND
    assert state.to_dict()["state_claims"] == {
        "commit_sha": "a" * 40,
        "ref": "refs/heads/main",
        "repository": "nulleimy/V-One",
    }
    assert ObservedPostState.from_dict(state.to_dict()) == state

    assert strength.to_dict()["strength_type"] == VERIFICATION_STRENGTH_TYPE
    assert strength.strength_class == INDEPENDENT_PROVIDER_READBACK
    assert strength.temporal_model == SEQUENTIAL_READBACK_NON_ATOMIC
    assert strength.atomic_readback is False
    assert VerificationStrength.from_dict(strength.to_dict()) == strength

    assert result.to_dict()["result_type"] == VERIFICATION_RESULT_TYPE
    assert result.verdict == VERIFIED
    assert result.reason == OBSERVED_STATE_MATCH
    assert result.observed_post_state_digest == state.state_digest
    assert result.verification_strength_digest == strength.strength_digest
    assert VerificationResult.from_dict(result.to_dict()) == result


def test_mismatching_independent_readback_is_not_verified() -> None:
    state, strength, result = _verify(
        runner_commit="a" * 40,
        verifier_commit="b" * 40,
    )

    assert state.to_dict()["state_claims"]["commit_sha"] == "b" * 40
    assert strength.atomic_readback is False
    assert result.verdict == NOT_VERIFIED
    assert result.reason == OBSERVED_STATE_MISMATCH


def test_runner_observation_substitution_fails_closed() -> None:
    runner = _runner_observation()
    boundary = _boundary(runner)
    verifier = _verifier_observation(
        runner,
        boundary,
        runner_observation_digest=DC,
    )

    with pytest.raises(
        VerificationEvidenceDenied,
        match="VERIFICATION_EVIDENCE_BINDING_MISMATCH",
    ):
        verify_github_ref_readback(
            runner_observation=runner,
            verifier_observation=verifier,
            boundary=boundary,
            observed_post_state_revision="observed-post-state/e4-test-r1",
            strength_revision="verification-strength/e4-test-r1",
            result_revision="verification-result/e4-test-r1",
        )


def test_verifier_observation_must_not_precede_runner_observation() -> None:
    runner = _runner_observation()
    boundary = _boundary(runner)
    verifier = _verifier_observation(
        runner,
        boundary,
        observed_at="2026-08-18T11:59:59.000+00:00",
    )

    with pytest.raises(
        VerificationEvidenceDenied,
        match="VERIFIER_OBSERVATION_PRECEDES_RUNNER_OBSERVATION",
    ):
        verify_github_ref_readback(
            runner_observation=runner,
            verifier_observation=verifier,
            boundary=boundary,
            observed_post_state_revision="observed-post-state/e4-test-r1",
            strength_revision="verification-strength/e4-test-r1",
            result_revision="verification-result/e4-test-r1",
        )


def test_e4_artifacts_do_not_carry_secrets_or_runner_authority() -> None:
    state, strength, result = _verify()
    payloads = (state.to_dict(), strength.to_dict(), result.to_dict())
    forbidden = {
        "token",
        "secret",
        "lease_id",
        "lease_digest",
        "grant_id",
        "grant_digest",
        "authorization_snapshot",
        "credential",
    }

    for payload in payloads:
        assert forbidden.isdisjoint(payload)

    assert strength.effect_ceiling == READ_ONLY_EFFECT_CLASS
    assert strength.provider_mutation_allowed is False
