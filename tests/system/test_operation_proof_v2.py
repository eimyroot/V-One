from __future__ import annotations

import hashlib
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_receipt_v2 import (
    EFFECT_RECORDED,
    EXECUTION_SUCCEEDED,
    NOT_EVALUATED,
    ExecutionReceiptV2,
)
from voodoo_product.github_read_provider import GitHubRefObservation
from voodoo_product.operation_proof_v2 import (
    OPERATION_PROOF_V2_TYPE,
    OperationProofV2,
    OperationProofV2Denied,
)
from voodoo_product.runner_identity import DENY_ALL_NETWORK_DEFAULT, READ_ONLY_EFFECT_CLASS
from voodoo_product.verification_result import (
    INDEPENDENT_PROVIDER_READBACK,
    OBSERVED_STATE_MATCH,
    VERIFIED,
    ObservedPostState,
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
DF = "f" * 64


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _receipt(**changes: Any) -> ExecutionReceiptV2:
    claims: dict[str, Any] = {
        "execution_id": "exec_e4",
        "request_id": "req_f6b",
        "environment": "staging",
        "capability": "github.delete-exact-created-ref/v1",
        "target_digest": D1,
        "authorization_snapshot_digest": D2,
        "execution_grant_digest": D3,
        "execution_capsule_digest": D4,
        "grant_consumption_witness_digest": D5,
        "dispatch_envelope_digest": D6,
        "dispatch_admission_digest": D7,
        "execution_lease_digest": D8,
        "runner_identity_digest": DA,
        "runner_boundary_digest": DB,
        "credential_access_decision_digest": DC,
        "runtime_activation_digest": DD,
        "write_effect_preflight_digest": DE,
        "provider_operation": "DELETE_REF",
        "provider_request_digest": DF,
        "provider_response_digest": D4,
        "provider_mutation_performed": True,
        "provider_mutation_count": 1,
        "automatic_retry_performed": False,
        "rollback_performed": True,
        "durable_completion_outcome": "COMPLETED",
        "durable_completion_digest": D4,
        "execution_status": EXECUTION_SUCCEEDED,
        "effect_status": EFFECT_RECORDED,
        "verification_status": NOT_EVALUATED,
        "recording_clock_witness_digest": D5,
        "recorded_at": "2026-08-18T11:59:00.000+00:00",
    }
    claims.update(changes)
    return ExecutionReceiptV2.create(
        receipt_revision="execution-receipt/f6b-test-r1",
        **claims,
    )


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
        "runner_observation_digest": runner.observation_digest,
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


def _verification_bundle(
    *,
    runner_commit: str = "a" * 40,
    verifier_commit: str = "a" * 40,
) -> tuple[
    GitHubRefObservation,
    VerifierGitHubRefObservation,
    IndependentVerificationBoundary,
    ObservedPostState,
    VerificationStrength,
    VerificationResult,
]:
    runner = _runner_observation(commit_sha=runner_commit)
    boundary = _boundary(runner)
    verifier = _verifier_observation(runner, boundary, commit_sha=verifier_commit)
    state, strength, result = verify_github_ref_readback(
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state_revision="observed-post-state/e4-test-r1",
        strength_revision="verification-strength/e4-test-r1",
        result_revision="verification-result/e4-test-r1",
    )
    return runner, verifier, boundary, state, strength, result


def _proof(
    *,
    receipt: ExecutionReceiptV2 | None = None,
    bundle: tuple[
        GitHubRefObservation,
        VerifierGitHubRefObservation,
        IndependentVerificationBoundary,
        ObservedPostState,
        VerificationStrength,
        VerificationResult,
    ]
    | None = None,
    verification: VerificationResult | None = None,
) -> OperationProofV2:
    resolved_receipt = receipt or _receipt()
    runner, verifier, boundary, state, strength, result = bundle or _verification_bundle()
    return OperationProofV2.create(
        receipt=resolved_receipt,
        runner_observation=runner,
        verifier_observation=verifier,
        boundary=boundary,
        observed_post_state=state,
        verification_strength=strength,
        verification=verification or result,
        proof_revision="operation-proof/f6b-test-r2",
    )


def test_operation_proof_v2_is_deterministic_and_round_trippable() -> None:
    proof = _proof()

    assert proof.to_dict()["proof_type"] == OPERATION_PROOF_V2_TYPE
    assert proof.final_verdict == VERIFIED
    assert OperationProofV2.from_dict(proof.to_dict()) == proof
    assert _proof().proof_digest == proof.proof_digest


def test_operation_proof_v2_rejects_forged_verified_result_without_matching_evidence() -> None:
    receipt = _receipt()
    bundle = _verification_bundle()
    forged = VerificationResult.create(
        execution_id=receipt.execution_id,
        execution_epoch=1,
        target_digest=receipt.target_digest,
        runner_observation_digest=DF,
        verifier_observation_digest=DF,
        observed_post_state_digest=DF,
        verification_boundary_digest=DF,
        verifier_id=DF,
        verifier_identity_digest=DF,
        verification_strength_digest=DF,
        verification_strength_class=INDEPENDENT_PROVIDER_READBACK,
        verdict=VERIFIED,
        reason=OBSERVED_STATE_MATCH,
        checked_at="2026-08-18T12:01:00.000+00:00",
        result_revision="verification-result/forged-r1",
    )

    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_VERIFICATION_RESULT_MISMATCH",
    ):
        _proof(receipt=receipt, bundle=bundle, verification=forged)


def test_operation_proof_v2_rejects_execution_substitution() -> None:
    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_EXECUTION_MISMATCH",
    ):
        _proof(receipt=_receipt(execution_id="exec_other"))


def test_operation_proof_v2_rejects_target_substitution() -> None:
    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_TARGET_MISMATCH",
    ):
        _proof(receipt=_receipt(target_digest=DE))


def test_operation_proof_v2_rejects_non_verified_readback() -> None:
    bundle = _verification_bundle(verifier_commit="b" * 40)

    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_INDEPENDENT_VERIFICATION_REQUIRED",
    ):
        _proof(bundle=bundle)


def test_operation_proof_v2_rejects_verification_before_receipt() -> None:
    with pytest.raises(
        OperationProofV2Denied,
        match="OPERATION_PROOF_V2_VERIFICATION_PRECEDES_RECEIPT",
    ):
        _proof(receipt=_receipt(recorded_at="2026-08-18T12:02:00.000+00:00"))


def test_operation_proof_v2_rejects_tampered_serialized_proof() -> None:
    value = deepcopy(_proof().to_dict())
    value["execution_receipt_digest"] = DE

    with pytest.raises(ValueError, match="proof_digest does not match"):
        OperationProofV2.from_dict(value)


def test_operation_proof_v2_contains_no_raw_authority_or_secret_material() -> None:
    value = _proof().to_dict()
    forbidden_exact_fields = {
        "token",
        "secret",
        "authorization_snapshot",
        "execution_grant",
        "execution_receipt",
        "provider_request",
        "provider_response",
        "credential",
    }

    assert forbidden_exact_fields.isdisjoint(value)
    assert value["provider_mutation_count"] == 1
    assert value["automatic_retry_performed"] is False
