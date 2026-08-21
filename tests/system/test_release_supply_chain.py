from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.validate_release_candidate import main, validate_release_candidate_version
from voodoo_product.version import RELEASE_CANDIDATE_VERSION, __version__

ROOT = Path(__file__).resolve().parents[2]


def test_release_candidate_version_is_derived_from_development_version() -> None:
    assert __version__ == "0.9.0-rc2-dev"
    assert __version__.removesuffix("-dev") == RELEASE_CANDIDATE_VERSION
    assert validate_release_candidate_version(RELEASE_CANDIDATE_VERSION) == "0.9.0-rc2"


@pytest.mark.parametrize(
    "candidate",
    [
        "0.9.0",
        "v0.9.0-rc2",
        "0.9.0-rc02",
        "0.9.0-rc3",
        "0.9.0-rc2/../../artifact",
        "0.9.0-rc2\nforged-log-entry",
    ],
)
def test_release_candidate_version_rejects_noncanonical_or_unbound_values(
    candidate: str,
) -> None:
    with pytest.raises(ValueError):
        validate_release_candidate_version(candidate)


def test_release_candidate_cli_does_not_echo_rejected_input(capsys: pytest.CaptureFixture[str]) -> None:
    forged = "0.9.0-rc2\nforged-log-entry"

    assert main([forged]) == 2

    captured = capsys.readouterr()
    assert forged not in captured.err
    assert "release candidate rejected" in captured.err


def test_product_image_smoke_uses_running_container_python_for_health_payload() -> None:
    script = (ROOT / "scripts/smoke_product_image.sh").read_text(encoding="utf-8")

    assert 'docker exec --interactive "$container" python -c' in script
    assert "\n  python -c " not in script


def test_product_image_smoke_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", "scripts/smoke_product_image.sh"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_product_image_smoke_script_rejects_option_like_image_before_docker() -> None:
    result = subprocess.run(
        ["bash", "scripts/smoke_product_image.sh", "--privileged", "test-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "safe identifier characters" in result.stderr


def test_ci_and_release_candidate_share_the_hardened_image_smoke_gate() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release-candidate.yml").read_text(encoding="utf-8")

    assert "bash scripts/smoke_product_image.sh" in ci
    assert "bash scripts/smoke_product_image.sh" in release
    checkout = "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7"
    setup_python = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6"
    upload = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7"
    final_sums = (
        'sha256sum "v-one-${RC_VERSION}.tar.gz" sbom.cdx.json '
        "g0-governance-evidence.json > SHA256SUMS.txt"
    )
    assert checkout in ci
    assert checkout in release
    assert setup_python in ci
    assert setup_python in release
    assert upload in release
    assert "github.ref == 'refs/heads/main'" in release
    assert 'VOODOO_ALLOW_PRODUCTION_EFFECTS: "false"' in release
    assert release.index("Validate release candidate version") < release.index("docker build")
    assert release.index("-o dist/sbom.cdx.json") < release.index(final_sums)
    assert "sha256sum --check SHA256SUMS.txt" in release


def test_release_candidate_is_fail_closed_on_live_g0_governance() -> None:
    release = (ROOT / ".github/workflows/release-candidate.yml").read_text(encoding="utf-8")

    assert "Verify G0 main governance" in release
    assert "VONE_GITHUB_GOVERNANCE_TOKEN" in release
    assert "scripts/verify_github_main_governance.py" in release
    assert "--token-env VONE_GITHUB_GOVERNANCE_TOKEN" in release
    assert '--expected-source-sha "${GITHUB_SHA}"' in release
    assert "--output g0-governance-evidence.json" in release
    assert release.index("Verify G0 main governance") < release.index(
        "Validate release candidate version"
    )
    assert release.index("Verify G0 main governance") < release.index("docker build")
    assert "cp g0-governance-evidence.json dist/" in release
    assert (
        'sha256sum "v-one-${RC_VERSION}.tar.gz" sbom.cdx.json '
        "g0-governance-evidence.json > SHA256SUMS.txt"
    ) in release


def test_product_readiness_retains_g0_governance_evidence_surface() -> None:
    required_g0_artifacts = (
        ".github/governance/main-branch-baseline.v1.json",
        ".github/workflows/g0-governance-verify.yml",
        "docs/governance/GITHUB_MAIN_GOVERNANCE_BASELINE_V1.md",
        "scripts/verify_github_main_governance.py",
        "tests/system/test_github_main_governance_verifier.py",
    )

    missing = [path for path in required_g0_artifacts if not (ROOT / path).is_file()]
    assert missing == []

    readiness = (ROOT / "scripts/product_readiness_gate.py").read_text(encoding="utf-8")
    assert '"tests/system/test_release_supply_chain.py"' in readiness
