from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

from voodoo_product.checkpoint_evidence import verify_checkpoint
from voodoo_product.cli import main

ROOT = Path(__file__).resolve().parents[2]


def _run_git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(checkpoint: Path) -> None:
    manifest = checkpoint / "ops" / "SHA256SUMS"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in checkpoint.rglob("*") if path.is_file() and path != manifest)
    lines = [f"{_sha256(path)}  {path.relative_to(checkpoint).as_posix()}" for path in files]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_nested_manifest(directory: Path) -> None:
    manifest = directory / "SHA256SUMS"
    files = sorted(path for path in directory.iterdir() if path.is_file() and path != manifest)
    lines = [f"{_sha256(path)}  {path.name}" for path in files]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_checkpoint(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _run_git(repository, "init", "--quiet")
    _run_git(repository, "config", "user.name", "VOODOO Test")
    _run_git(repository, "config", "user.email", "voodoo-test@example.invalid")
    _run_git(repository, "switch", "-c", "local/test-proofgraph")

    (repository / "README.md").write_text("first\n", encoding="utf-8")
    _run_git(repository, "add", "README.md")
    _run_git(repository, "commit", "--quiet", "-m", "test: initial checkpoint parent")

    script = repository / "scripts" / "run.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    (repository / "README.md").write_text("verified source\n", encoding="utf-8")
    _run_git(repository, "add", "README.md", "scripts/run.sh")
    _run_git(repository, "commit", "--quiet", "-m", "test: checkpoint evidence")

    head = _run_git(repository, "rev-parse", "HEAD")
    tree = _run_git(repository, "rev-parse", "HEAD^{tree}")
    parent = _run_git(repository, "rev-parse", "HEAD^")
    subject = _run_git(repository, "show", "-s", "--format=%s", "HEAD")
    branch = _run_git(repository, "branch", "--show-current")

    checkpoint = tmp_path / "checkpoint"
    source = checkpoint / "source"
    source.mkdir(parents=True)
    for relative in ("README.md", "scripts/run.sh"):
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((repository / relative).read_bytes())
        destination.chmod((repository / relative).stat().st_mode & 0o777)

    artifacts = checkpoint / "ops" / "artifacts"
    artifacts.mkdir(parents=True)
    bundle = artifacts / f"repository-{head[:12]}.bundle"
    _run_git(repository, "bundle", "create", str(bundle), f"refs/heads/{branch}")

    source_archive = artifacts / f"source-{head[:12]}.tar.gz"
    with tarfile.open(source_archive, "w:gz") as archive:
        archive.add(source, arcname=f"voodoo-one-{head[:12]}")

    image_id = "sha256:" + "a" * 64
    image_name = f"voodoo-one:runtime-{head[:12]}"
    runtime = checkpoint / "ops" / "evidence" / "runtime"
    runtime.mkdir(parents=True)
    runtime_readme = "\n".join(
        [
            "VOODOO ONE DOCKER / RUNTIME CLOSURE",
            "",
            "STATUS=VERIFIED_NATIVE_DOCKER_RUNTIME",
            "RELEASE_VERIFIED=NO",
            f"HEAD={head}",
            f"TREE={tree}",
            f"BRANCH={branch}",
            f"IMAGE={image_name}",
            f"IMAGE_ID={image_id}",
            "IMAGE_OS=linux",
            "IMAGE_ARCHITECTURE=amd64",
            "PRODUCT_IMAGE_SMOKE=PASSED",
            "DOCKER_HEALTHCHECK=HEALTHY",
            "WORKTREE=CLEAN",
            "LOCAL_ORIGIN=IN_SYNC",
            "GITHUB_PUSH=NOT_PERFORMED",
            "PRODUCTION_EFFECTS=DISABLED",
            "GENERATED_AT=2026-07-22T00:00:00Z",
            "",
            "LIMITATIONS:",
            "- Test fixture only.",
        ]
    )
    (runtime / "README.txt").write_text(runtime_readme + "\n", encoding="utf-8")
    image_inspect = [
        {
            "Id": image_id,
            "RepoTags": [image_name],
            "Config": {"User": "voodoo"},
            "Architecture": "amd64",
            "Os": "linux",
        }
    ]
    (runtime / "06_IMAGE_INSPECT.json").write_text(
        json.dumps(image_inspect, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_nested_manifest(runtime)

    runtime_bundle = artifacts / f"voodoo-one-docker-runtime-{head[:12]}.tar.gz"
    with tarfile.open(runtime_bundle, "w:gz") as archive:
        archive.add(runtime, arcname=f"voodoo-one-docker-runtime-{head[:12]}")
    runtime_bundle_sha256 = _sha256(runtime_bundle)

    provenance = checkpoint / "ops" / "provenance"
    provenance.mkdir(parents=True)
    completion = "\n".join(
        [
            "CHECKPOINT_CLASS=DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE",
            "RELEASE_VERIFIED=NO",
            f"HEAD={head}",
            f"TREE={tree}",
            f"PARENT={parent}",
            f"BRANCH={branch}",
            "TRACKED_FILES=2",
            f"IMAGE={image_name}",
            f"IMAGE_ID={image_id}",
            "IMAGE_PLATFORM=linux/amd64",
            "PRODUCT_IMAGE_SMOKE=PASSED",
            "DOCKER_HEALTHCHECK=HEALTHY",
            "WORKTREE=CLEAN",
            "LOCAL_ORIGIN=IN_SYNC",
            "GITHUB_PUSH=NOT_PERFORMED",
            "PRODUCTION_EFFECT=NONE",
            "GENERATED_AT=2026-07-22T00:00:00Z",
        ]
    )
    (provenance / "CHECKPOINT_COMPLETE.txt").write_text(
        completion + "\n",
        encoding="utf-8",
    )
    repository_json = {
        "checkpoint_class": "DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE",
        "release_verified": False,
        "generated_at": "2026-07-22T00:00:00Z",
        "repository": {
            "branch": branch,
            "head": head,
            "tree": tree,
            "parent": parent,
            "subject": subject,
            "tracked_files": 2,
            "worktree": "CLEAN",
            "local_origin": "IN_SYNC",
            "github_push": "NOT_PERFORMED",
        },
        "runtime": {
            "status": "VERIFIED_NATIVE_DOCKER_RUNTIME",
            "image": image_name,
            "image_id": image_id,
            "platform": "linux/amd64",
            "product_image_smoke": "PASSED",
            "docker_healthcheck": "HEALTHY",
            "production_effects": "DISABLED",
            "evidence_bundle_sha256": runtime_bundle_sha256,
        },
        "change": {"full_tests": "PASSED"},
        "limitations": ["Test fixture only."],
    }
    (provenance / "repository.json").write_text(
        json.dumps(repository_json, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (checkpoint / "README.txt").write_text("test checkpoint\n", encoding="utf-8")
    _write_manifest(checkpoint)
    return checkpoint


def test_checkpoint_verifier_accepts_valid_checkpoint_and_builds_graph(tmp_path: Path) -> None:
    checkpoint = _build_checkpoint(tmp_path)

    report = verify_checkpoint(checkpoint)

    assert report["valid"] is True
    assert report["errors"] == []
    assert {check["name"] for check in report["checks"]} == {
        "checkpoint_root",
        "manifest",
        "provenance",
        "git_bundle",
        "source_archive",
        "runtime_evidence",
        "nested_manifests",
    }
    node_types = {node["type"] for node in report["proof_graph"]["nodes"]}
    assert node_types == {"checkpoint", "git_commit", "source_tree", "container_image"}
    assert report["claims"]["release_verified"] is False


def test_checkpoint_verifier_detects_payload_tampering(tmp_path: Path) -> None:
    checkpoint = _build_checkpoint(tmp_path)
    (checkpoint / "README.txt").write_text("tampered\n", encoding="utf-8")

    report = verify_checkpoint(checkpoint)

    assert report["valid"] is False
    assert report["errors"][0]["code"] == "manifest_digest_mismatch"


def test_checkpoint_verifier_detects_source_tree_divergence(tmp_path: Path) -> None:
    checkpoint = _build_checkpoint(tmp_path)
    (checkpoint / "source" / "README.md").write_text("different source\n", encoding="utf-8")
    _write_manifest(checkpoint)

    report = verify_checkpoint(checkpoint)

    assert report["valid"] is False
    assert report["errors"][0]["code"] == "source_tree_mismatch"


def test_checkpoint_verifier_rejects_unmanifested_payload(tmp_path: Path) -> None:
    checkpoint = _build_checkpoint(tmp_path)
    (checkpoint / "unexpected.txt").write_text("not covered\n", encoding="utf-8")

    report = verify_checkpoint(checkpoint)

    assert report["valid"] is False
    assert report["errors"][0]["code"] == "manifest_coverage_mismatch"


def test_checkpoint_verifier_rejects_manifest_traversal(tmp_path: Path) -> None:
    checkpoint = _build_checkpoint(tmp_path)
    manifest = checkpoint / "ops" / "SHA256SUMS"
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + f"{'0' * 64}  ../escape\n",
        encoding="utf-8",
    )

    report = verify_checkpoint(checkpoint)

    assert report["valid"] is False
    assert report["errors"][0]["code"] == "unsafe_relative_path"


def test_cli_emits_json_and_nonzero_for_invalid_checkpoint(
    tmp_path: Path,
    capsys: object,
) -> None:
    checkpoint = _build_checkpoint(tmp_path)
    (checkpoint / "README.txt").write_text("tampered\n", encoding="utf-8")

    exit_code = main(["evidence", "verify", str(checkpoint), "--canonical"])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    report = json.loads(captured.out)

    assert exit_code == 1
    assert report["valid"] is False


def test_checkpoint_verifier_is_dependency_neutral() -> None:
    source = (ROOT / "voodoo_product" / "checkpoint_evidence.py").read_text(encoding="utf-8")

    assert "fastapi" not in source
    assert "from .service" not in source
    assert "from .persistence" not in source
    assert "shell=True" not in source


def test_local_voodoo_launcher_uses_repository_virtualenv() -> None:
    launcher = ROOT / "scripts" / "voodoo"

    syntax = subprocess.run(
        ["sh", "-n", str(launcher)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    source = launcher.read_text(encoding="utf-8")

    assert os.access(launcher, os.X_OK)
    assert syntax.returncode == 0, syntax.stderr
    assert 'PYTHON="$ROOT/.venv/bin/python"' in source
    assert 'PYTHONPATH="$ROOT"' in source
    assert 'exec "$PYTHON" -m voodoo_product "$@"' in source
    assert "/usr/bin/env python" not in source
