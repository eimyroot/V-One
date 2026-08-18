from pathlib import Path


def test_e3_workflow_uses_separate_runner_and_verifier_jobs() -> None:
    workflow = Path(".github/workflows/e3-live-verifier-read.yml").read_text(encoding="utf-8")

    required = (
        "runner-observation:",
        "verifier-observation:",
        "needs: runner-observation",
        "permissions:\n  contents: read",
        "persist-credentials: false",
        "--read-only",
        "--cap-drop=ALL",
        "no-new-privileges",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=256",
        "DOCKER-USER",
        "E3_RUNNER_NETWORK_NEGATIVE_CHECK=PASS",
        "E3_VERIFIER_NETWORK_NEGATIVE_CHECK=PASS",
        "E3_LIVE_INDEPENDENT_VERIFIER_OBSERVATION=PASS",
        "github.actions-token.verifier-read/v1",
    )
    for marker in required:
        assert marker in workflow or marker in Path(
            "voodoo_product/e3_live_verifier_pilot.py"
        ).read_text(encoding="utf-8")

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


def test_e3_pilot_is_observation_only_and_does_not_construct_verification_result() -> None:
    pilot = Path("voodoo_product/e3_live_verifier_pilot.py").read_text(encoding="utf-8")
    observation = Path("voodoo_product/verifier_observation.py").read_text(encoding="utf-8")

    assert "VerifierGitHubRefReadHandler" in pilot
    assert '"provider_mutation_allowed": False' in pilot
    assert "VerificationResult" not in pilot
    assert "OperationProof" not in pilot
    assert "ObservedPostState" not in pilot
    assert "VerificationResult" in observation  # docstring explicitly denies conflation
    assert "not ObservedPostState, VerificationResult" in observation
