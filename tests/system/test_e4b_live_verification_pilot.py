from pathlib import Path

import pytest

from voodoo_product.e4b_live_verification_pilot import evaluate_live_evidence


def test_e4b_evaluator_fails_closed_on_runner_mutation_ceiling() -> None:
    runner = {
        "pilot": "d4b-live-governed-read/v1",
        "status": "PASS",
        "phase_d_effect_ceiling": "READ_ONLY",
        "provider_mutation_allowed": True,
    }
    verifier = {
        "pilot": "e3-live-independent-verifier-observation/v1",
        "status": "PASS",
        "phase_e_effect_ceiling": "READ_ONLY",
        "provider_mutation_allowed": False,
    }

    with pytest.raises(RuntimeError, match="runner evidence allows provider mutation"):
        evaluate_live_evidence(runner_result=runner, verifier_result=verifier)


def test_e4b_evaluator_fails_closed_on_verifier_mutation_ceiling() -> None:
    runner = {
        "pilot": "d4b-live-governed-read/v1",
        "status": "PASS",
        "phase_d_effect_ceiling": "READ_ONLY",
        "provider_mutation_allowed": False,
    }
    verifier = {
        "pilot": "e3-live-independent-verifier-observation/v1",
        "status": "PASS",
        "phase_e_effect_ceiling": "READ_ONLY",
        "provider_mutation_allowed": True,
    }

    with pytest.raises(RuntimeError, match="verifier evidence allows provider mutation"):
        evaluate_live_evidence(runner_result=runner, verifier_result=verifier)


def test_e4b_evaluator_itself_has_no_provider_transport_or_secret_path() -> None:
    source = Path("voodoo_product/e4b_live_verification_pilot.py").read_text(encoding="utf-8")

    required = (
        "verify_github_ref_readback",
        "GitHubRefObservation.from_dict",
        "IndependentVerificationBoundary.from_dict",
        "VerifierGitHubRefObservation.from_dict",
        "E4B_LIVE_VERIFICATION_RESULT",
        "if verdict != VERIFIED",
    )
    for marker in required:
        assert marker in source

    forbidden = (
        "GitHubApiRefReadTransport",
        "urllib.request",
        "requests.",
        "httpx",
        '"GITHUB_TOKEN"',
        "CredentialAccessDecision",
        "VerifierCredentialDecision",
    )
    for marker in forbidden:
        assert marker not in source


def test_e4b_workflow_keeps_runner_and_verifier_separate_and_read_only() -> None:
    workflow = Path(".github/workflows/e4b-live-verification-result.yml").read_text(
        encoding="utf-8"
    )

    required = (
        "runner-observation:",
        "verifier-and-result:",
        "needs: runner-observation",
        "permissions:\n  contents: read",
        "persist-credentials: false",
        "--read-only",
        "--cap-drop=ALL",
        "no-new-privileges",
        "DOCKER-USER",
        "E4B_RUNNER_NETWORK_NEGATIVE_CHECK=PASS",
        "E4B_VERIFIER_NETWORK_NEGATIVE_CHECK=PASS",
        "python -m voodoo_product.e3_live_verifier_pilot",
        "python -m voodoo_product.e4b_live_verification_pilot",
        "E4B_LIVE_VERIFICATION_RESULT=VERIFIED",
    )
    for marker in required:
        assert marker in workflow

    forbidden = (
        "contents: write",
        "pull-requests: write",
        "git push",
        "gh api --method POST",
        "gh api --method PATCH",
        "gh api --method DELETE",
    )
    for marker in forbidden:
        assert marker not in workflow
