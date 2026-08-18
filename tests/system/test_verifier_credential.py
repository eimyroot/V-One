from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.github_read_provider import GitHubRefObservation
from voodoo_product.runner_identity import (
    DENY_ALL_NETWORK_DEFAULT,
    READ_ONLY_EFFECT_CLASS,
    RUNNER_BOUNDARY_TYPE,
    RunnerBoundary,
    RunnerIdentity,
)
from voodoo_product.verifier_credential import (
    READ_ONLY_ACCESS_MODE,
    VerifierCredentialDecision,
    VerifierCredentialDenied,
    VerifierCredentialPolicy,
)
from voodoo_product.verifier_identity import IndependentVerificationBoundary, VerifierIdentity

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
D6 = "6" * 64
DA = "a" * 64
DB = "b" * 64
DC = "c" * 64


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _bundle() -> tuple[VerifierIdentity, IndependentVerificationBoundary]:
    runner = RunnerIdentity.create(
        runner_class="github-actions.docker-isolated/v1",
        provider="github-actions",
        provider_instance_id="gha:runner:e2",
        environment="staging",
        rootfs_digest=DA,
        resource_limit_profile_digest=DB,
        network_policy_digest=DC,
        identity_revision="runner-identity/e2-test-r1",
    )
    boundary_claims: dict[str, Any] = {
        "schema_version": 1,
        "boundary_type": RUNNER_BOUNDARY_TYPE,
        "runner_id": runner.runner_id,
        "runner_identity_digest": runner.identity_digest,
        "lease_id": D1,
        "lease_digest": D2,
        "admission_id": D3,
        "execution_id": "exec_e2",
        "execution_epoch": 1,
        "execution_capsule_digest": D4,
        "capability_definition_identity": D5,
        "environment": "staging",
        "runner_class": runner.runner_class,
        "credential_class": "github.actions-token.read/v1",
        "effect_ceiling": READ_ONLY_EFFECT_CLASS,
        "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
        "provider_mutation_allowed": False,
        "boundary_revision": "runner-boundary/e2-test-r1",
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
        "target_digest": D6,
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
        "clock_source_identity": "trusted-clock/e2-test-r1",
        "clock_witness_digest": DC,
        "observed_at": "2026-08-18T11:30:00.000+00:00",
        "observation_revision": "github-ref-observation/e2-test-r1",
    }
    observation = GitHubRefObservation(
        **{
            key: value
            for key, value in observation_claims.items()
            if key not in {"schema_version", "observation_type"}
        },
        observation_digest=_digest(observation_claims),
    )
    verifier = VerifierIdentity.create(
        verifier_class="github-actions.docker-isolated-verifier/v1",
        provider="github-actions",
        provider_instance_id="gha:verifier:e2",
        environment="staging",
        credential_class="github.actions-token.verifier-read/v1",
        rootfs_digest=DA,
        resource_limit_profile_digest=DB,
        network_policy_digest=DC,
        identity_revision="verifier-identity/e2-r1",
    )
    verification_boundary = IndependentVerificationBoundary.create(
        verifier=verifier,
        runner_identity=runner,
        runner_boundary=runner_boundary,
        runner_observation=observation,
        boundary_revision="independent-verification-boundary/e2-r1",
    )
    return verifier, verification_boundary


def _policy(*, credential_class: str = "github.actions-token.verifier-read/v1") -> VerifierCredentialPolicy:
    return VerifierCredentialPolicy.create(
        credential_class=credential_class,
        provider="github-actions",
        audience="api.github.com",
        enabled_environments=("staging",),
        max_ttl_seconds=300,
        policy_revision="verifier-credential-policy/e2-r1",
    )


def test_verifier_policy_is_read_only_and_round_trippable() -> None:
    policy = _policy()
    assert policy.access_mode == READ_ONLY_ACCESS_MODE
    assert policy.provider_mutation_allowed is False
    assert VerifierCredentialPolicy.from_dict(policy.to_dict()) == policy


def test_verifier_decision_binds_exact_identity_boundary_and_runner_observation() -> None:
    verifier, boundary = _bundle()
    decision = VerifierCredentialDecision.create(
        verifier=verifier,
        boundary=boundary,
        policy=_policy(),
        valid_from="2026-08-18T11:35:00.000+00:00",
        expires_at="2026-08-18T11:40:00.000+00:00",
        decision_revision="verifier-credential-decision/e2-r1",
    )
    assert decision.verifier_id == verifier.verifier_id
    assert decision.verification_boundary_digest == boundary.boundary_digest
    assert decision.runner_observation_digest == boundary.runner_observation_digest
    assert decision.target_digest == boundary.target_digest
    assert decision.access_mode == READ_ONLY_ACCESS_MODE
    assert decision.provider_mutation_allowed is False
    assert VerifierCredentialDecision.from_dict(decision.to_dict()) == decision


def test_verifier_decision_contains_no_secret_or_runner_credential_material() -> None:
    verifier, boundary = _bundle()
    decision = VerifierCredentialDecision.create(
        verifier=verifier,
        boundary=boundary,
        policy=_policy(),
        valid_from="2026-08-18T11:35:00.000+00:00",
        expires_at="2026-08-18T11:40:00.000+00:00",
        decision_revision="verifier-credential-decision/e2-r1",
    )
    payload = decision.to_dict()
    forbidden = {"token", "secret", "secret_handle", "environment_variable", "runner_credential_class"}
    assert forbidden.isdisjoint(payload)
    assert payload["credential_class"] != boundary.runner_credential_class


def test_verifier_decision_rejects_runner_credential_class() -> None:
    verifier, boundary = _bundle()
    with pytest.raises(VerifierCredentialDenied, match="VERIFIER_CREDENTIAL_CLASS_NOT_ALLOWED"):
        VerifierCredentialDecision.create(
            verifier=verifier,
            boundary=boundary,
            policy=_policy(credential_class=boundary.runner_credential_class),
            valid_from="2026-08-18T11:35:00.000+00:00",
            expires_at="2026-08-18T11:40:00.000+00:00",
            decision_revision="verifier-credential-decision/e2-r1",
        )


def test_verifier_decision_rejects_ttl_above_policy() -> None:
    verifier, boundary = _bundle()
    with pytest.raises(VerifierCredentialDenied, match="VERIFIER_CREDENTIAL_TTL_EXCEEDS_POLICY"):
        VerifierCredentialDecision.create(
            verifier=verifier,
            boundary=boundary,
            policy=_policy(),
            valid_from="2026-08-18T11:35:00.000+00:00",
            expires_at="2026-08-18T11:40:01.000+00:00",
            decision_revision="verifier-credential-decision/e2-r1",
        )
