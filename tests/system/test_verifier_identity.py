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
from voodoo_product.verifier_identity import (
    INDEPENDENCE_CLASS,
    INDEPENDENT_VERIFICATION_BOUNDARY_TYPE,
    IndependentVerificationBoundary,
    IndependentVerificationBoundaryDenied,
    VerifierIdentity,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64
DIGEST_E = "e" * 64
DIGEST_F = "f" * 64
DIGEST_1 = "1" * 64
DIGEST_2 = "2" * 64
DIGEST_3 = "3" * 64
DIGEST_4 = "4" * 64
DIGEST_5 = "5" * 64
DIGEST_6 = "6" * 64


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _runner_identity() -> RunnerIdentity:
    return RunnerIdentity.create(
        runner_class="github-actions.docker-isolated/v1",
        provider="github-actions",
        provider_instance_id="gha:runner:1",
        environment="staging",
        rootfs_digest=DIGEST_A,
        resource_limit_profile_digest=DIGEST_B,
        network_policy_digest=DIGEST_C,
        identity_revision="runner-identity/e1-test-r1",
    )


def _runner_boundary(
    identity: RunnerIdentity,
    *,
    execution_epoch: int = 1,
    credential_class: str = "github.actions-token.read/v1",
) -> RunnerBoundary:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "boundary_type": RUNNER_BOUNDARY_TYPE,
        "runner_id": identity.runner_id,
        "runner_identity_digest": identity.identity_digest,
        "lease_id": DIGEST_D,
        "lease_digest": DIGEST_E,
        "admission_id": DIGEST_F,
        "execution_id": "exec_e1",
        "execution_epoch": execution_epoch,
        "execution_capsule_digest": DIGEST_1,
        "capability_definition_identity": DIGEST_2,
        "environment": identity.environment,
        "runner_class": identity.runner_class,
        "credential_class": credential_class,
        "effect_ceiling": READ_ONLY_EFFECT_CLASS,
        "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
        "provider_mutation_allowed": False,
        "boundary_revision": f"runner-boundary/e1-test-r{execution_epoch}",
    }
    values = {
        key: item
        for key, item in claims.items()
        if key not in {"schema_version", "boundary_type"}
    }
    return RunnerBoundary(**values, boundary_digest=_digest(claims))


def _runner_observation(
    identity: RunnerIdentity,
    boundary: RunnerBoundary,
) -> GitHubRefObservation:
    claims: dict[str, Any] = {
        "schema_version": 1,
        "observation_type": "github-ref-observation/v1",
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/main",
        "commit_sha": "a" * 40,
        "target_digest": DIGEST_3,
        "provider": identity.provider,
        "provider_instance_id": identity.provider_instance_id,
        "runner_id": identity.runner_id,
        "runner_boundary_digest": boundary.boundary_digest,
        "credential_decision_digest": DIGEST_4,
        "runtime_activation_digest": DIGEST_5,
        "lease_id": boundary.lease_id,
        "lease_digest": boundary.lease_digest,
        "execution_id": boundary.execution_id,
        "execution_epoch": boundary.execution_epoch,
        "execution_capsule_digest": boundary.execution_capsule_digest,
        "capability_definition_identity": boundary.capability_definition_identity,
        "source_identity": "github-api/git-ref/v1",
        "clock_source_identity": "trusted-clock/e1-test-r1",
        "clock_witness_digest": DIGEST_6,
        "observed_at": "2026-08-18T11:20:00.000+00:00",
        "observation_revision": "github-ref-observation/e1-test-r1",
    }
    values = {
        key: item
        for key, item in claims.items()
        if key not in {"schema_version", "observation_type"}
    }
    return GitHubRefObservation(**values, observation_digest=_digest(claims))


def _verifier(
    *,
    provider_instance_id: str = "gha:verifier:1",
    credential_class: str = "github.actions-token.verifier-read/v1",
) -> VerifierIdentity:
    return VerifierIdentity.create(
        verifier_class="github-actions.docker-isolated-verifier/v1",
        provider="github-actions",
        provider_instance_id=provider_instance_id,
        environment="staging",
        credential_class=credential_class,
        rootfs_digest=DIGEST_A,
        resource_limit_profile_digest=DIGEST_B,
        network_policy_digest=DIGEST_C,
        identity_revision="verifier-identity/e1-r1",
    )


def _bundle() -> tuple[
    RunnerIdentity,
    RunnerBoundary,
    GitHubRefObservation,
    VerifierIdentity,
]:
    identity = _runner_identity()
    boundary = _runner_boundary(identity)
    observation = _runner_observation(identity, boundary)
    return identity, boundary, observation, _verifier()


def test_verifier_identity_is_content_addressed_and_round_trippable() -> None:
    verifier = _verifier()

    assert VerifierIdentity.from_dict(verifier.to_dict()) == verifier
    assert verifier.verifier_id != _runner_identity().runner_id
    assert verifier.identity_digest == _digest(
        {key: value for key, value in verifier.to_dict().items() if key != "identity_digest"}
    )


def test_verifier_identity_contains_no_authority_or_secret_material() -> None:
    payload = _verifier().to_dict()

    forbidden = {"token", "secret", "grant_id", "lease_id", "permissions"}
    assert forbidden.isdisjoint(payload)


def test_independent_boundary_binds_exact_runner_evidence() -> None:
    identity, runner_boundary, observation, verifier = _bundle()

    boundary = IndependentVerificationBoundary.create(
        verifier=verifier,
        runner_identity=identity,
        runner_boundary=runner_boundary,
        runner_observation=observation,
        boundary_revision="independent-verification-boundary/e1-r1",
    )

    assert boundary.verifier_id != boundary.runner_id
    assert boundary.verifier_provider_instance_id != boundary.runner_provider_instance_id
    assert boundary.verifier_credential_class != boundary.runner_credential_class
    assert boundary.runner_observation_digest == observation.observation_digest
    assert boundary.effect_ceiling == READ_ONLY_EFFECT_CLASS
    assert boundary.network_egress_default == DENY_ALL_NETWORK_DEFAULT
    assert boundary.provider_mutation_allowed is False
    assert boundary.independence_class == INDEPENDENCE_CLASS
    assert IndependentVerificationBoundary.from_dict(boundary.to_dict()) == boundary
    assert boundary.to_dict()["boundary_type"] == INDEPENDENT_VERIFICATION_BOUNDARY_TYPE


def test_independent_boundary_rejects_same_provider_instance() -> None:
    identity, runner_boundary, observation, _ = _bundle()
    verifier = _verifier(provider_instance_id=identity.provider_instance_id)

    with pytest.raises(
        IndependentVerificationBoundaryDenied,
        match="VERIFIER_PROVIDER_INSTANCE_NOT_INDEPENDENT",
    ):
        IndependentVerificationBoundary.create(
            verifier=verifier,
            runner_identity=identity,
            runner_boundary=runner_boundary,
            runner_observation=observation,
            boundary_revision="independent-verification-boundary/e1-r1",
        )


def test_independent_boundary_rejects_same_credential_class() -> None:
    identity, runner_boundary, observation, _ = _bundle()
    verifier = _verifier(credential_class=runner_boundary.credential_class)

    with pytest.raises(
        IndependentVerificationBoundaryDenied,
        match="VERIFIER_CREDENTIAL_CLASS_NOT_INDEPENDENT",
    ):
        IndependentVerificationBoundary.create(
            verifier=verifier,
            runner_identity=identity,
            runner_boundary=runner_boundary,
            runner_observation=observation,
            boundary_revision="independent-verification-boundary/e1-r1",
        )


def test_independent_boundary_rejects_runner_observation_substitution() -> None:
    identity, _, observation, verifier = _bundle()
    substituted_boundary = _runner_boundary(identity, execution_epoch=2)

    with pytest.raises(
        IndependentVerificationBoundaryDenied,
        match="RUNNER_OBSERVATION_BOUNDARY_MISMATCH",
    ):
        IndependentVerificationBoundary.create(
            verifier=verifier,
            runner_identity=identity,
            runner_boundary=substituted_boundary,
            runner_observation=observation,
            boundary_revision="independent-verification-boundary/e1-r1",
        )
