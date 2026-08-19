from __future__ import annotations

import pytest

from voodoo_product.execution_contract import ExecutionTarget
from voodoo_product.rollback_control import RunnerBoundaryV3
from voodoo_product.rollback_verification import (
    ABSENT,
    GitHubRefAbsenceObservation,
    IndependentVerificationBoundaryV2,
    VerifierCredentialDecisionV2,
    VerifierGitHubRefAbsenceObservation,
    verify_github_ref_absence,
)
from voodoo_product.runner_identity import RunnerIdentity
from voodoo_product.verifier_credential import VerifierCredentialPolicy
from voodoo_product.verifier_identity import VerifierIdentity


NOW = "2026-08-19T01:10:00.000+00:00"
LATER = "2026-08-19T01:10:01.000+00:00"
EXPIRES = "2026-08-19T01:14:00.000+00:00"


def _runner_identity() -> RunnerIdentity:
    value = object.__new__(RunnerIdentity)
    object.__setattr__(value, "runner_id", "1" * 64)
    object.__setattr__(value, "identity_digest", "2" * 64)
    object.__setattr__(value, "provider_instance_id", "runner-instance-f6")
    return value


def _runner_boundary() -> RunnerBoundaryV3:
    value = object.__new__(RunnerBoundaryV3)
    object.__setattr__(value, "runner_id", "1" * 64)
    object.__setattr__(value, "runner_identity_digest", "2" * 64)
    object.__setattr__(value, "boundary_digest", "3" * 64)
    object.__setattr__(value, "execution_id", "exec-f6-rollback")
    object.__setattr__(value, "execution_epoch", 1)
    object.__setattr__(value, "credential_class", "github.delete-ref/scoped-v1")
    return value


def _verifier() -> VerifierIdentity:
    value = object.__new__(VerifierIdentity)
    object.__setattr__(value, "verifier_id", "4" * 64)
    object.__setattr__(value, "identity_digest", "5" * 64)
    object.__setattr__(value, "provider_instance_id", "verifier-instance-f6")
    object.__setattr__(value, "credential_class", "github.read-ref/verifier-f6")
    object.__setattr__(value, "provider", "github")
    object.__setattr__(value, "environment", "staging")
    return value


def _target() -> ExecutionTarget:
    return ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={
            "repository": "nulleimy/V-One",
            "ref": "refs/heads/vone-canary/f4b-pr120-32185703943",
            "expected_sha": "a" * 40,
            "original_create_response_digest": "b" * 64,
            "original_verification_result_digest": "c" * 64,
        },
    )


def test_absence_readback_produces_verified_result_only_after_independent_observation() -> None:
    runner_identity = _runner_identity()
    runner_boundary = _runner_boundary()
    verifier = _verifier()
    runner_observation = GitHubRefAbsenceObservation.create(
        target=_target(),
        runner_identity=runner_identity,
        runner_boundary=runner_boundary,
        provider_instance_id="runner-readback-instance-f6",
        source_identity="github-rest/git-ref-absence-runner/v1",
        observed_at=NOW,
        observation_revision="runner-absence/f6-r1",
    )
    boundary = IndependentVerificationBoundaryV2.create(
        verifier=verifier,
        runner_identity=runner_identity,
        runner_boundary=runner_boundary,
        runner_observation=runner_observation,
        boundary_revision="independent-verification-boundary/f6-r1",
    )
    policy = VerifierCredentialPolicy.create(
        credential_class=verifier.credential_class,
        provider="github",
        audience="api.github.com",
        enabled_environments=("staging",),
        max_ttl_seconds=300,
        policy_revision="verifier-policy/f6-r1",
    )
    decision = VerifierCredentialDecisionV2.create(
        verifier=verifier,
        boundary=boundary,
        policy=policy,
        valid_from=NOW,
        expires_at=EXPIRES,
        decision_revision="verifier-decision/f6-r1",
    )
    verifier_observation = VerifierGitHubRefAbsenceObservation.create(
        runner_observation=runner_observation,
        verifier=verifier,
        boundary=boundary,
        decision=decision,
        source_identity="github-rest/git-ref-absence-verifier/v1",
        observed_at=LATER,
        observation_revision="verifier-absence/f6-r1",
    )
    post_state, strength, result = verify_github_ref_absence(
        runner_observation=runner_observation,
        verifier_observation=verifier_observation,
        boundary=boundary,
        observed_post_state_revision="observed-post-state/f6-r1",
        strength_revision="verification-strength/f6-r1",
        result_revision="verification-result/f6-r1",
    )

    assert dict(post_state.state_claims)["presence"] == ABSENT
    assert strength.provider_mutation_allowed is False
    assert result.verdict == "VERIFIED"
    assert result.observed_post_state_digest == post_state.state_digest


def test_verifier_must_be_independent_from_runner_instance() -> None:
    runner_identity = _runner_identity()
    runner_boundary = _runner_boundary()
    verifier = _verifier()
    object.__setattr__(verifier, "provider_instance_id", runner_identity.provider_instance_id)
    runner_observation = GitHubRefAbsenceObservation.create(
        target=_target(),
        runner_identity=runner_identity,
        runner_boundary=runner_boundary,
        provider_instance_id="runner-readback-instance-f6",
        source_identity="github-rest/git-ref-absence-runner/v1",
        observed_at=NOW,
        observation_revision="runner-absence/f6-r1",
    )
    with pytest.raises(ValueError, match="provider instance"):
        IndependentVerificationBoundaryV2.create(
            verifier=verifier,
            runner_identity=runner_identity,
            runner_boundary=runner_boundary,
            runner_observation=runner_observation,
            boundary_revision="independent-verification-boundary/f6-r1",
        )
