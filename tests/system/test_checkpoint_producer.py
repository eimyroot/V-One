from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

import voodoo_product.checkpoint_producer as checkpoint_producer
from tests.system.test_checkpoint_evidence_verifier import _build_checkpoint, _write_manifest
from voodoo_product.checkpoint_evidence import verify_checkpoint
from voodoo_product.checkpoint_producer import finalize_checkpoint
from voodoo_product.cli import main


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        mode = os.lstat(path).st_mode
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(stat.S_IMODE(mode)).encode("ascii"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_finalizer_publishes_verified_checkpoint_without_warnings(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is True
    assert report["errors"] == []
    assert destination.is_dir()
    verification = verify_checkpoint(destination)
    assert verification["valid"] is True
    assert verification["errors"] == []
    assert verification["warnings"] == []


def test_finalizer_freezes_snapshot_before_live_source_changes(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"

    report = finalize_checkpoint(candidate, destination)
    frozen_digest = _tree_digest(destination)
    live_log = candidate / "ops" / "evidence" / "runtime" / "README.txt"
    live_log.write_text(live_log.read_text(encoding="utf-8") + "LIVE_APPEND=YES\n", encoding="utf-8")

    assert report["finalized"] is True
    assert _tree_digest(destination) == frozen_digest
    verification = verify_checkpoint(destination)
    assert verification["valid"] is True
    assert verification["warnings"] == []


def test_finalizer_repairs_only_known_nested_manifest_warning(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    runtime_readme = candidate / "ops" / "evidence" / "runtime" / "README.txt"
    runtime_readme.write_text(
        runtime_readme.read_text(encoding="utf-8") + "LIVE_APPEND=YES\n",
        encoding="utf-8",
    )
    _write_manifest(candidate)
    destination = tmp_path / "final-checkpoint"

    candidate_report = verify_checkpoint(candidate)
    report = finalize_checkpoint(candidate, destination)

    assert candidate_report["valid"] is True
    assert [warning["code"] for warning in candidate_report["warnings"]] == [
        "nested_post_manifest_mutation"
    ]
    assert report["finalized"] is True
    final_report = verify_checkpoint(destination)
    assert final_report["valid"] is True
    assert final_report["errors"] == []
    assert final_report["warnings"] == []


def test_finalizer_preserves_candidate_bytes(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    before = _tree_digest(candidate)

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is True
    assert _tree_digest(candidate) == before


def test_finalizer_rejects_invalid_candidate_and_cleans_staging(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    (candidate / "README.txt").write_text("tampered\n", encoding="utf-8")
    destination = tmp_path / "final-checkpoint"

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "verification_failed"
    assert not destination.exists()
    assert list(tmp_path.glob(".final-checkpoint.staging-*")) == []
    assert not (tmp_path / ".final-checkpoint.finalize.lock").exists()


def test_finalizer_rejects_existing_destination(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    destination.mkdir()

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "destination_exists"


def test_finalizer_rejects_symlinked_candidate_payload(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    (candidate / "unsafe-link").symlink_to(candidate / "README.txt")
    destination = tmp_path / "final-checkpoint"

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_symlink"
    assert not destination.exists()


def test_finalizer_rejects_special_candidate_payload(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    fifo = candidate / "unsafe-fifo"
    os.mkfifo(fifo)
    destination = tmp_path / "final-checkpoint"

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_special_file"
    assert not destination.exists()


def test_finalizer_rejects_legacy_runtime_exception(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    exception = candidate / "ops" / "evidence" / "03_RUNTIME_LOG_MANIFEST_EXCEPTION.txt"
    exception.write_text(
        "RUNTIME_LOG_EXCEPTION=EXPECTED_POST_MANIFEST_APPEND\n",
        encoding="utf-8",
    )
    destination = tmp_path / "final-checkpoint"

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "legacy_runtime_exception_present"
    assert not destination.exists()


def test_finalizer_rejects_manifested_legacy_runtime_exception(tmp_path: Path) -> None:
    candidate = _build_checkpoint(tmp_path)
    exception = candidate / "ops" / "evidence" / "03_RUNTIME_LOG_MANIFEST_EXCEPTION.txt"
    exception.write_text(
        "RUNTIME_LOG_EXCEPTION=EXPECTED_POST_MANIFEST_APPEND\n",
        encoding="utf-8",
    )
    _write_manifest(candidate)
    destination = tmp_path / "final-checkpoint"

    report = finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "legacy_runtime_exception_present"
    assert not destination.exists()


def test_cli_finalizes_checkpoint_and_emits_canonical_json(
    tmp_path: Path,
    capsys: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"

    exit_code = main(
        [
            "evidence",
            "finalize",
            str(candidate),
            str(destination),
            "--canonical",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    report = json.loads(captured.out)

    assert exit_code == 0
    assert report["finalized"] is True
    assert report["destination"] == str(destination)


def test_cli_returns_nonzero_when_destination_exists(
    tmp_path: Path,
    capsys: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    destination.mkdir()

    exit_code = main(
        [
            "evidence",
            "finalize",
            str(candidate),
            str(destination),
            "--canonical",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    report = json.loads(captured.out)

    assert exit_code == 1
    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "destination_exists"


def test_finalizer_rejects_candidate_change_during_verification(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    original_verify = checkpoint_producer.verify_checkpoint
    mutated = False

    def verify_then_mutate(path: str | Path) -> dict[str, object]:
        nonlocal mutated
        report = original_verify(path)
        if not mutated and Path(path).resolve() == candidate.resolve():
            mutated = True
            readme = candidate / "README.txt"
            readme.write_text("tampered after verification\n", encoding="utf-8")
        return report

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer,
        "verify_checkpoint",
        verify_then_mutate,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_changed_during_verification"
    assert not destination.exists()


def test_finalizer_rejects_candidate_change_during_copy(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    original_copytree = checkpoint_producer.shutil.copytree

    def copy_then_mutate(*args: object, **kwargs: object) -> object:
        result = original_copytree(*args, **kwargs)
        readme = candidate / "README.txt"
        readme.write_text("tampered during copy\n", encoding="utf-8")
        return result

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer.shutil,
        "copytree",
        copy_then_mutate,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_changed_during_copy"
    assert not destination.exists()


def test_finalizer_rejects_staging_divergence(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    original_copytree = checkpoint_producer.shutil.copytree

    def copy_then_tamper(*args: object, **kwargs: object) -> object:
        result = original_copytree(*args, **kwargs)
        staging = Path(args[1])
        (staging / "README.txt").write_text("tampered staging\n", encoding="utf-8")
        return result

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer.shutil,
        "copytree",
        copy_then_tamper,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "staging_differs_from_verified_candidate"
    assert not destination.exists()


def test_finalizer_detects_removed_empty_directory_during_verification(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    empty_directory = candidate / "empty-evidence-directory"
    empty_directory.mkdir()
    destination = tmp_path / "final-checkpoint"
    original_verify = checkpoint_producer.verify_checkpoint
    removed = False

    def verify_then_remove_directory(path: str | Path) -> dict[str, object]:
        nonlocal removed
        report = original_verify(path)
        if not removed and Path(path).resolve() == candidate.resolve():
            removed = True
            empty_directory.rmdir()
        return report

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer,
        "verify_checkpoint",
        verify_then_remove_directory,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_changed_during_verification"
    assert not destination.exists()


def test_finalizer_detects_directory_mode_change_during_verification(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    directory = candidate / "source"
    original_mode = stat.S_IMODE(os.lstat(directory).st_mode)
    changed_mode = 0o700 if original_mode != 0o700 else 0o755
    destination = tmp_path / "final-checkpoint"
    original_verify = checkpoint_producer.verify_checkpoint
    changed = False

    def verify_then_chmod(path: str | Path) -> dict[str, object]:
        nonlocal changed
        report = original_verify(path)
        if not changed and Path(path).resolve() == candidate.resolve():
            changed = True
            directory.chmod(changed_mode)
        return report

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer,
        "verify_checkpoint",
        verify_then_chmod,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_changed_during_verification"
    assert not destination.exists()


def test_finalizer_detects_candidate_root_mode_change_during_verification(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    original_mode = stat.S_IMODE(os.lstat(candidate).st_mode)
    changed_mode = 0o700 if original_mode != 0o700 else 0o755
    destination = tmp_path / "final-checkpoint"
    original_verify = checkpoint_producer.verify_checkpoint
    changed = False

    def verify_then_chmod_root(path: str | Path) -> dict[str, object]:
        nonlocal changed
        report = original_verify(path)
        if not changed and Path(path).resolve() == candidate.resolve():
            changed = True
            candidate.chmod(changed_mode)
        return report

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer,
        "verify_checkpoint",
        verify_then_chmod_root,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_changed_during_verification"
    assert not destination.exists()


def test_finalizer_detects_staging_root_mode_divergence(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    original_copytree = checkpoint_producer.shutil.copytree

    def copy_then_chmod_staging_root(*args: object, **kwargs: object) -> object:
        result = original_copytree(*args, **kwargs)
        staging = Path(args[1])
        original_mode = stat.S_IMODE(os.lstat(staging).st_mode)
        changed_mode = 0o700 if original_mode != 0o700 else 0o755
        staging.chmod(changed_mode)
        return result

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer.shutil,
        "copytree",
        copy_then_chmod_staging_root,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "staging_differs_from_verified_candidate"
    assert not destination.exists()


def test_finalizer_rejects_file_replaced_by_symlink_during_copy(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    original_copytree = checkpoint_producer.shutil.copytree

    def copy_then_replace_with_symlink(*args: object, **kwargs: object) -> object:
        result = original_copytree(*args, **kwargs)
        readme = candidate / "README.txt"
        readme.unlink()
        readme.symlink_to(candidate / "source" / "README.md")
        return result

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer.shutil,
        "copytree",
        copy_then_replace_with_symlink,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    assert report["finalized"] is False
    assert report["errors"][0]["code"] == "candidate_symlink"
    assert not destination.exists()


def test_finalizer_reports_staging_cleanup_failure(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    original_copytree = checkpoint_producer.shutil.copytree

    def copy_then_tamper(*args: object, **kwargs: object) -> object:
        result = original_copytree(*args, **kwargs)
        staging = Path(args[1])
        (staging / "README.txt").write_text("tampered staging\n", encoding="utf-8")
        return result

    def fail_staging_cleanup(path: Path) -> None:
        raise OSError(f"simulated staging cleanup failure: {path}")

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer.shutil,
        "copytree",
        copy_then_tamper,
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer,
        "_remove_staging",
        fail_staging_cleanup,
    )

    report = checkpoint_producer.finalize_checkpoint(candidate, destination)

    codes = [issue["code"] for issue in report["errors"]]
    assert report["finalized"] is False
    assert codes == [
        "staging_differs_from_verified_candidate",
        "staging_cleanup_failed",
    ]
    staging_directories = list(tmp_path.glob(".final-checkpoint.staging-*"))
    assert len(staging_directories) == 1
    shutil.rmtree(staging_directories[0])


def test_cli_reports_lock_cleanup_failure_and_returns_nonzero(
    tmp_path: Path,
    monkeypatch: object,
    capsys: object,
) -> None:
    candidate = _build_checkpoint(tmp_path)
    destination = tmp_path / "final-checkpoint"
    lock_path = tmp_path / ".final-checkpoint.finalize.lock"

    def fail_lock_cleanup(path: Path) -> None:
        raise OSError(f"simulated lock cleanup failure: {path}")

    monkeypatch.setattr(  # type: ignore[attr-defined]
        checkpoint_producer,
        "_unlink_lock",
        fail_lock_cleanup,
    )

    exit_code = main(
        [
            "evidence",
            "finalize",
            str(candidate),
            str(destination),
            "--canonical",
        ]
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    report = json.loads(captured.out)

    assert exit_code == 1
    assert report["finalized"] is False
    assert report["destination_published"] is True
    assert report["errors"][0]["code"] == "lock_cleanup_failed"
    assert destination.is_dir()
    assert lock_path.exists()
    lock_path.unlink()
