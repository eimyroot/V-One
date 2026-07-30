from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

import voodoo_product.checkpoint_capture as checkpoint_capture
from voodoo_product.checkpoint_capture import capture_runtime_candidate
from voodoo_product.checkpoint_evidence import verify_checkpoint
from voodoo_product.checkpoint_producer import finalize_checkpoint
from voodoo_product.cli import main

IMAGE_ID = "sha256:" + "a" * 64


def _run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _build_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _run_git(repository, "init", "--quiet")
    _run_git(repository, "config", "user.name", "VOODOO Capture Test")
    _run_git(repository, "config", "user.email", "capture@example.invalid")
    _run_git(repository, "switch", "-c", "local/capture-test")
    (repository / "README.md").write_text("parent\n", encoding="utf-8")
    _run_git(repository, "add", "README.md")
    _run_git(repository, "commit", "--quiet", "-m", "test: capture parent")
    script = repository / "scripts" / "run.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    (repository / "README.md").write_text("capture source\n", encoding="utf-8")
    (repository / "Dockerfile.product").write_text("FROM scratch\n", encoding="utf-8")
    smoke = repository / "scripts" / "smoke_product_image.sh"
    smoke.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    smoke.chmod(0o755)
    _run_git(repository, "add", ".")
    _run_git(repository, "commit", "--quiet", "-m", "test: capture source")
    return repository


class FakeRuntimeRunner:
    def __init__(
        self,
        *,
        build_returncode: int = 0,
        smoke_returncode: int = 0,
        docker_health: str = "healthy",
        production_effects: str = "DISABLED",
        image_id: str = IMAGE_ID,
        image_user: str = "voodoo",
        image_os: str = "linux",
        image_architecture: str = "amd64",
        image_preexists: bool = False,
        mutate_repository: bool = False,
        smoke_marker: str = "",
    ) -> None:
        self.build_returncode = build_returncode
        self.smoke_returncode = smoke_returncode
        self.docker_health = docker_health
        self.production_effects = production_effects
        self.image_id = image_id
        self.image_user = image_user
        self.image_os = image_os
        self.image_architecture = image_architecture
        self.image_preexists = image_preexists
        self.mutate_repository = mutate_repository
        self.smoke_marker = smoke_marker
        self.removed_images: list[str] = []
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[Any]:
        del timeout
        self.commands.append(command)
        executable = Path(command[0]).name
        if executable == "git":
            return subprocess.run(
                command,
                cwd=cwd,
                env=env,
                check=False,
                capture_output=True,
                text=text,
            )
        if executable == "docker" and command[1:3] == ["version", "--format"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"Client":{"Version":"test"},"Server":{"Version":"test"}}\n',
                stderr="",
            )
        if executable == "docker" and command[1] == "build":
            if self.mutate_repository:
                (cwd / "changed-during-capture.txt").write_text("changed\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                command,
                self.build_returncode,
                stdout="fake build\n" if self.build_returncode == 0 else "",
                stderr="" if self.build_returncode == 0 else "fake build failure\n",
            )
        if (
            executable == "docker"
            and command[1:3] == ["image", "inspect"]
            and "--format" in command
        ):
            return subprocess.CompletedProcess(
                command,
                0 if self.image_preexists else 1,
                stdout=f"{IMAGE_ID}\n" if self.image_preexists else "",
                stderr="" if self.image_preexists else "Error: No such image\n",
            )
        if executable == "docker" and command[1:3] == ["image", "inspect"]:
            image = command[-1]
            inspect = [
                {
                    "Id": self.image_id,
                    "RepoTags": [image],
                    "Config": {"User": self.image_user},
                    "Architecture": self.image_architecture,
                    "Os": self.image_os,
                }
            ]
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(inspect),
                stderr="",
            )
        if executable == "docker" and command[1:3] == ["image", "rm"]:
            self.removed_images.append(command[-1])
            return subprocess.CompletedProcess(command, 0, stdout="removed\n", stderr="")
        if executable == "bash" and command[1].endswith("smoke_product_image.sh"):
            runtime = Path(command[4])
            if self.smoke_returncode == 0 or self.docker_health:
                (runtime / "05_RUNTIME_LOG.txt").write_text("fake runtime\n", encoding="utf-8")
                (runtime / "07_CONTAINER_HEALTH.json").write_text(
                    json.dumps({"Status": self.docker_health}) + "\n",
                    encoding="utf-8",
                )
                (runtime / "07_CONTAINER_IMAGE_ID.txt").write_text(
                    self.image_id + "\n",
                    encoding="utf-8",
                )
                (runtime / "08_APPLICATION_HEALTH.json").write_text(
                    json.dumps(
                        {
                            "status": "HEALTHY",
                            "database_backend": "sqlite",
                            "schema_version": 7,
                            "production_effects": self.production_effects,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
            return subprocess.CompletedProcess(
                command,
                self.smoke_returncode,
                stdout="fake smoke\n",
                stderr=self.smoke_marker,
            )
        raise AssertionError(f"unexpected command: {command}")


def _install_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    runner: FakeRuntimeRunner,
    *,
    docker_available: bool = True,
) -> None:
    original_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "docker":
            return "/fake/docker" if docker_available else None
        if name == "bash":
            return "/bin/bash"
        return original_which(name)

    monkeypatch.setattr(checkpoint_capture.shutil, "which", fake_which)
    monkeypatch.setattr(checkpoint_capture, "_run_process", runner)


def _error_code(report: dict[str, Any]) -> str:
    return report["errors"][0]["code"]


def test_valid_capture_finalizes_and_verifies_without_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    candidate = tmp_path / "candidate"
    final = tmp_path / "final"
    runner = FakeRuntimeRunner()
    _install_fake_runtime(monkeypatch, runner)

    head = _run_git(repository, "rev-parse", "HEAD")
    tree = _run_git(repository, "rev-parse", "HEAD^{tree}")
    parent = _run_git(repository, "rev-parse", "HEAD^")
    branch = _run_git(repository, "branch", "--show-current")
    report = capture_runtime_candidate(candidate, repository=repository)

    assert report["captured"] is True
    assert report["errors"] == []
    assert report["head"] == head
    candidate_verification = verify_checkpoint(candidate)
    assert candidate_verification["valid"] is True
    assert candidate_verification["errors"] == []
    claims = candidate_verification["claims"]["repository"]
    assert claims["head"] == head
    assert claims["tree"] == tree
    assert claims["parent"] == parent
    assert claims["branch"] == branch
    assert not (candidate / "ops" / "evidence" / "runtime" / "SHA256SUMS").exists()
    build_command = next(command for command in runner.commands if "build" in command)
    assert build_command[-1].endswith("/source")
    assert build_command[-2].endswith("/source/Dockerfile.product")

    finalization = finalize_checkpoint(candidate, final)
    assert finalization["finalized"] is True
    final_verification = verify_checkpoint(final)
    assert final_verification["valid"] is True
    assert final_verification["errors"] == []
    assert final_verification["warnings"] == []
    assert _run_git(repository, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_capture_rejects_dirty_tracked_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    (repository / "README.md").write_text("dirty\n", encoding="utf-8")
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "repository_dirty"


def test_capture_rejects_untracked_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    (repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "repository_dirty"


def test_capture_rejects_detached_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _run_git(repository, "checkout", "--quiet", "--detach")
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "detached_head"


def test_capture_rejects_destination_inside_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())

    report = capture_runtime_candidate(repository / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "destination_inside_repository"


def test_capture_rejects_existing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())

    report = capture_runtime_candidate(candidate, repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "destination_exists"


def test_capture_rejects_tracked_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    link = repository / "tracked-link"
    link.symlink_to("README.md")
    _run_git(repository, "add", "tracked-link")
    _run_git(repository, "commit", "--quiet", "-m", "test: unsupported symlink")
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "unsupported_source_entry"


def test_capture_rejects_unavailable_docker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner(), docker_available=False)

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "docker_unavailable"


def test_capture_does_not_overwrite_or_remove_preexisting_image_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    runner = FakeRuntimeRunner(image_preexists=True)
    _install_fake_runtime(monkeypatch, runner)

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "image_identity_invalid"
    assert runner.removed_images == []


def test_capture_reports_docker_build_failure_and_removes_partial_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    candidate = tmp_path / "candidate"
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner(build_returncode=1))

    report = capture_runtime_candidate(candidate, repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "docker_build_failed"
    assert not candidate.exists()
    assert list(tmp_path.glob(".candidate.capture-*")) == []


def test_capture_reports_smoke_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(
        monkeypatch,
        FakeRuntimeRunner(smoke_returncode=1, docker_health=""),
    )

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "smoke_failed"


def test_capture_rejects_docker_health_not_observed_healthy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(
        monkeypatch,
        FakeRuntimeRunner(
            smoke_returncode=3,
            docker_health="starting",
            smoke_marker="VOODOO_SMOKE_ERROR=docker_health_unverified\n",
        ),
    )

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "docker_health_unverified"


def test_capture_rejects_production_effects_not_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(
        monkeypatch,
        FakeRuntimeRunner(smoke_returncode=1, production_effects="ENABLED"),
    )

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "production_effects_not_disabled"


@pytest.mark.parametrize(
    ("runner", "expected_code"),
    [
        (FakeRuntimeRunner(image_user="root"), "image_identity_invalid"),
        (FakeRuntimeRunner(image_architecture=""), "image_identity_invalid"),
        (FakeRuntimeRunner(image_id="not-a-digest"), "image_identity_invalid"),
    ],
)
def test_capture_rejects_invalid_image_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: FakeRuntimeRunner,
    expected_code: str,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(monkeypatch, runner)

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == expected_code


def test_capture_rejects_repository_change_during_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner(mutate_repository=True))

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "repository_changed_during_capture"


def test_capture_rejects_candidate_verifier_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    candidate = tmp_path / "candidate"
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())
    monkeypatch.setattr(
        checkpoint_capture,
        "verify_checkpoint",
        lambda path: {
            "valid": False,
            "checkpoint": str(path),
            "errors": [{"code": "simulated_verifier_failure"}],
            "warnings": [],
        },
    )

    report = capture_runtime_candidate(candidate, repository=repository)

    assert report["captured"] is False
    assert _error_code(report) == "candidate_verification_failed"
    assert not candidate.exists()


def test_capture_reports_partial_staging_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _build_repository(tmp_path)
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner(build_returncode=1))

    def fail_cleanup(path: Path) -> None:
        raise OSError(f"simulated cleanup failure: {path}")

    monkeypatch.setattr(checkpoint_capture, "_remove_capture_staging", fail_cleanup)

    report = capture_runtime_candidate(tmp_path / "candidate", repository=repository)

    assert report["captured"] is False
    assert [issue["code"] for issue in report["errors"]] == [
        "docker_build_failed",
        "capture_cleanup_failed",
    ]
    staging = list(tmp_path.glob(".candidate.capture-*"))
    assert len(staging) == 1
    shutil.rmtree(staging[0])


def test_capture_cli_emits_canonical_json_and_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = _build_repository(tmp_path)
    candidate = tmp_path / "candidate"
    _install_fake_runtime(monkeypatch, FakeRuntimeRunner())
    monkeypatch.chdir(repository)

    success_code = main(
        ["evidence", "capture-runtime", str(candidate), "--canonical"]
    )
    success_output = json.loads(capsys.readouterr().out)
    failure_code = main(
        ["evidence", "capture-runtime", str(candidate), "--canonical"]
    )
    failure_output = json.loads(capsys.readouterr().out)

    assert success_code == 0
    assert success_output["captured"] is True
    assert failure_code == 1
    assert failure_output["captured"] is False
    assert failure_output["errors"][0]["code"] == "destination_exists"


def test_smoke_evidence_mode_rejects_relative_directory_before_docker(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            "bash",
            "scripts/smoke_product_image.sh",
            "voodoo-one:test",
            "capture-test",
            "relative-evidence",
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "existing absolute real directory" in result.stderr


def test_capture_preserves_verifier_and_finalizer_ownership() -> None:
    root = Path(__file__).resolve().parents[2]
    capture_source = (root / "voodoo_product" / "checkpoint_capture.py").read_text(
        encoding="utf-8"
    )
    verifier_source = (root / "voodoo_product" / "checkpoint_evidence.py").read_text(
        encoding="utf-8"
    )
    finalizer_source = (root / "voodoo_product" / "checkpoint_producer.py").read_text(
        encoding="utf-8"
    )
    adr = (
        root / "docs" / "adr" / "ADR-0005-repository-owned-runtime-candidate-capture.md"
    ).read_text(encoding="utf-8")

    assert "shell=True" not in capture_source
    assert "from .checkpoint_producer" not in capture_source
    assert "checkpoint_capture" not in verifier_source
    assert "checkpoint_capture" not in finalizer_source
    assert "| Status | PROPOSED — owner review required |" in adr
    assert "A commit-bound fresh runtime checkpoint is prohibited" in adr
