from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .checkpoint_evidence import verify_checkpoint
from .evidence_primitives import canonical_json

_ALLOWED_CANDIDATE_WARNING_CODES = frozenset({"nested_post_manifest_mutation"})

TreeSnapshotEntry = tuple[str, int, int, str]


@dataclass(frozen=True)
class TreeSnapshot:
    root_device: int
    root_inode: int
    entries: dict[str, TreeSnapshotEntry]


class CheckpointFinalizationError(ValueError):
    """Fail-closed error raised while freezing and publishing one checkpoint."""

    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


@dataclass(frozen=True)
class FinalizationTarget:
    candidate: Path
    destination: Path
    destination_parent: Path
    lock_path: Path


def finalize_checkpoint(candidate: str | Path, destination: str | Path) -> dict[str, Any]:
    """Freeze, verify, and atomically publish one local checkpoint candidate."""

    candidate_input = Path(candidate)
    destination_input = Path(destination)
    staging: Path | None = None
    lock_fd: int | None = None
    target: FinalizationTarget | None = None
    verification: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    destination_published = False

    try:
        target = _prepare_target(candidate_input, destination_input)
        lock_fd = _acquire_lock(target.lock_path)
        _reject_legacy_runtime_exception(target.candidate)

        candidate_before_verification = _snapshot_tree(
            target.candidate,
            code_prefix="candidate",
        )
        verification = verify_checkpoint(target.candidate)
        candidate_after_verification = _snapshot_tree(
            target.candidate,
            code_prefix="candidate",
        )
        if candidate_after_verification != candidate_before_verification:
            raise CheckpointFinalizationError(
                "candidate_changed_during_verification",
                "candidate changed while its existing evidence was being verified",
                path=str(target.candidate),
            )
        if not _candidate_verification_is_acceptable(verification):
            raise CheckpointFinalizationError(
                "verification_failed",
                (
                    "candidate checkpoint must have valid outer evidence; only explicit "
                    "nested_post_manifest_mutation warnings may be repaired during finalization"
                ),
                path=str(target.candidate),
            )

        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{target.destination.name}.staging-",
                dir=target.destination_parent,
            )
        )
        shutil.copytree(
            target.candidate,
            staging,
            dirs_exist_ok=True,
            symlinks=True,
            copy_function=shutil.copy2,
        )
        candidate_after_copy = _snapshot_tree(
            target.candidate,
            code_prefix="candidate",
        )
        if candidate_after_copy != candidate_after_verification:
            raise CheckpointFinalizationError(
                "candidate_changed_during_copy",
                "candidate changed while the frozen staging copy was being created",
                path=str(target.candidate),
            )
        staging_snapshot = _snapshot_tree(staging, code_prefix="staging")
        if staging_snapshot.entries != candidate_after_verification.entries:
            raise CheckpointFinalizationError(
                "staging_differs_from_verified_candidate",
                "staging copy differs from the candidate snapshot accepted by verification",
                path=str(staging),
            )

        _reject_legacy_runtime_exception(staging)

        runtime = staging / "ops" / "evidence" / "runtime"
        _require_real_directory(runtime, code="runtime_evidence_directory_invalid")
        _write_manifest(runtime, runtime / "SHA256SUMS")

        commit = staging / "ops" / "evidence" / "commit"
        if os.path.lexists(commit):
            _require_real_directory(commit, code="commit_evidence_directory_invalid")
            _write_manifest(commit, commit / "SHA256SUMS")

        outer_manifest = staging / "ops" / "SHA256SUMS"
        outer_manifest.parent.mkdir(parents=True, exist_ok=True)
        _write_manifest(staging, outer_manifest)

        verification = verify_checkpoint(staging)
        if (
            not verification.get("valid")
            or verification.get("errors")
            or verification.get("warnings")
        ):
            raise CheckpointFinalizationError(
                "verification_failed",
                "staged checkpoint did not pass fail-closed verification without warnings",
                path=str(staging),
            )

        if os.path.lexists(target.destination):
            raise CheckpointFinalizationError(
                "destination_exists",
                "destination appeared during finalization",
                path=str(target.destination),
            )
        os.rename(staging, target.destination)
        staging = None
        destination_published = True

        normalized_verification = dict(verification)
        normalized_verification["checkpoint"] = str(target.destination)
        report = {
            "schema_version": 1,
            "finalized": True,
            "candidate": str(target.candidate),
            "destination": str(target.destination),
            "verification": normalized_verification,
            "errors": [],
        }
    except CheckpointFinalizationError as exc:
        report = _failure_report(
            candidate_input,
            destination_input,
            exc,
            verification=verification,
        )
    except OSError as exc:
        error = CheckpointFinalizationError(
            "finalization_io_error",
            f"{type(exc).__name__}: {exc}",
            path=getattr(exc, "filename", None),
        )
        report = _failure_report(
            candidate_input,
            destination_input,
            error,
            verification=verification,
        )
    finally:
        cleanup_issues = _cleanup_finalization(
            staging=staging,
            lock_fd=lock_fd,
            lock_path=target.lock_path if target is not None else None,
        )
        if report is not None and cleanup_issues:
            report["errors"] = [*report.get("errors", []), *cleanup_issues]
            report["finalized"] = False
            if destination_published:
                report["destination_published"] = True

    if report is None:
        raise RuntimeError("finalization finished without a structured report")
    return report


def _cleanup_finalization(
    *,
    staging: Path | None,
    lock_fd: int | None,
    lock_path: Path | None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    if staging is not None and os.path.lexists(staging):
        try:
            _remove_staging(staging)
        except OSError as exc:
            issues.append(
                _cleanup_issue(
                    "staging_cleanup_failed",
                    exc,
                    path=str(staging),
                )
            )

    if lock_fd is not None:
        try:
            os.close(lock_fd)
        except OSError as exc:
            issues.append(
                _cleanup_issue(
                    "lock_cleanup_failed",
                    exc,
                    path=str(lock_path) if lock_path is not None else None,
                )
            )

    if lock_path is not None and os.path.lexists(lock_path):
        try:
            _unlink_lock(lock_path)
        except OSError as exc:
            issues.append(
                _cleanup_issue(
                    "lock_cleanup_failed",
                    exc,
                    path=str(lock_path),
                )
            )

    return issues


def _cleanup_issue(
    code: str,
    error: OSError,
    *,
    path: str | None,
) -> dict[str, str]:
    issue = {
        "code": code,
        "message": f"{type(error).__name__}: {error}",
    }
    if path is not None:
        issue["path"] = path
    return issue


def _remove_staging(path: Path) -> None:
    shutil.rmtree(path)


def _unlink_lock(path: Path) -> None:
    path.unlink()


def _reject_legacy_runtime_exception(root: Path) -> None:
    relative = Path("ops/evidence/03_RUNTIME_LOG_MANIFEST_EXCEPTION.txt")
    legacy_exception = root / relative
    if os.path.lexists(legacy_exception):
        raise CheckpointFinalizationError(
            "legacy_runtime_exception_present",
            "candidate contains legacy post-manifest mutation exception evidence",
            path=relative.as_posix(),
        )


def _candidate_verification_is_acceptable(report: dict[str, Any]) -> bool:
    if report.get("valid") is not True or report.get("errors"):
        return False
    warnings = report.get("warnings")
    if not isinstance(warnings, list):
        return False
    return all(
        isinstance(warning, dict)
        and warning.get("code") in _ALLOWED_CANDIDATE_WARNING_CODES
        for warning in warnings
    )


def render_finalization_report(report: dict[str, Any], *, canonical: bool = False) -> str:
    """Render a stable finalization report."""

    if canonical:
        return canonical_json(report)
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)


def _prepare_target(candidate: Path, destination: Path) -> FinalizationTarget:
    try:
        candidate_stat = os.lstat(candidate)
    except FileNotFoundError as exc:
        raise CheckpointFinalizationError(
            "candidate_missing",
            "candidate path does not exist",
            path=str(candidate),
        ) from exc
    if stat.S_ISLNK(candidate_stat.st_mode):
        raise CheckpointFinalizationError(
            "candidate_symlink",
            "candidate root must not be a symlink",
            path=str(candidate),
        )
    if not stat.S_ISDIR(candidate_stat.st_mode):
        raise CheckpointFinalizationError(
            "candidate_not_directory",
            "candidate path must be a directory",
            path=str(candidate),
        )
    candidate_root = candidate.resolve(strict=True)
    _validate_regular_tree(candidate_root, code_prefix="candidate")

    if destination.name in {"", ".", ".."}:
        raise CheckpointFinalizationError(
            "destination_invalid",
            "destination must name one new checkpoint directory",
            path=str(destination),
        )
    try:
        destination_parent = destination.parent.resolve(strict=True)
    except FileNotFoundError as exc:
        raise CheckpointFinalizationError(
            "destination_parent_missing",
            "destination parent does not exist",
            path=str(destination.parent),
        ) from exc
    _require_real_directory(destination_parent, code="destination_parent_invalid")
    destination_path = destination_parent / destination.name
    if os.path.lexists(destination_path):
        raise CheckpointFinalizationError(
            "destination_exists",
            "destination must not already exist",
            path=str(destination_path),
        )
    if destination_parent == candidate_root or destination_parent.is_relative_to(candidate_root):
        raise CheckpointFinalizationError(
            "destination_inside_candidate",
            "destination parent must not be inside the candidate tree",
            path=str(destination_parent),
        )

    lock_path = destination_parent / f".{destination.name}.finalize.lock"
    return FinalizationTarget(
        candidate=candidate_root,
        destination=destination_path,
        destination_parent=destination_parent,
        lock_path=lock_path,
    )


def _acquire_lock(path: Path) -> int:
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise CheckpointFinalizationError(
            "finalization_locked",
            "another finalization lock already exists",
            path=str(path),
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
    except OSError:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        raise
    return descriptor


def _require_real_directory(path: Path, *, code: str) -> None:
    try:
        path_stat = os.lstat(path)
    except FileNotFoundError as exc:
        raise CheckpointFinalizationError(
            code,
            "required directory does not exist",
            path=str(path),
        ) from exc
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISDIR(path_stat.st_mode):
        raise CheckpointFinalizationError(
            code,
            "required directory must be a real directory",
            path=str(path),
        )


def _validate_regular_tree(root: Path, *, code_prefix: str) -> None:
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names.sort()
        file_names.sort()
        directory_path = Path(directory)
        for name in directory_names:
            candidate = directory_path / name
            candidate_stat = os.lstat(candidate)
            relative = candidate.relative_to(root).as_posix()
            if stat.S_ISLNK(candidate_stat.st_mode):
                raise CheckpointFinalizationError(
                    f"{code_prefix}_symlink",
                    "checkpoint trees must not contain symlinked directories",
                    path=relative,
                )
            if not stat.S_ISDIR(candidate_stat.st_mode):
                raise CheckpointFinalizationError(
                    f"{code_prefix}_special_directory_entry",
                    "checkpoint directory entries must be directories",
                    path=relative,
                )
        for name in file_names:
            candidate = directory_path / name
            candidate_stat = os.lstat(candidate)
            relative = candidate.relative_to(root).as_posix()
            if stat.S_ISLNK(candidate_stat.st_mode):
                raise CheckpointFinalizationError(
                    f"{code_prefix}_symlink",
                    "checkpoint trees must not contain symlinked files",
                    path=relative,
                )
            if not stat.S_ISREG(candidate_stat.st_mode):
                raise CheckpointFinalizationError(
                    f"{code_prefix}_special_file",
                    "checkpoint payloads must be regular files",
                    path=relative,
                )


def _snapshot_tree(root: Path, *, code_prefix: str) -> TreeSnapshot:
    try:
        root_before = os.lstat(root)
    except FileNotFoundError as exc:
        raise CheckpointFinalizationError(
            f"{code_prefix}_root_invalid",
            "checkpoint root does not exist",
            path=str(root),
        ) from exc
    if stat.S_ISLNK(root_before.st_mode) or not stat.S_ISDIR(root_before.st_mode):
        raise CheckpointFinalizationError(
            f"{code_prefix}_root_invalid",
            "checkpoint root must be a real directory",
            path=str(root),
        )

    entries: dict[str, TreeSnapshotEntry] = {
        ".": (
            "directory",
            stat.S_IMODE(root_before.st_mode),
            0,
            "",
        )
    }

    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names.sort()
        file_names.sort()
        directory_path = Path(directory)

        for name in directory_names:
            path = directory_path / name
            path_stat = os.lstat(path)
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(path_stat.st_mode):
                raise CheckpointFinalizationError(
                    f"{code_prefix}_symlink",
                    "checkpoint trees must not contain symlinked directories",
                    path=relative,
                )
            if not stat.S_ISDIR(path_stat.st_mode):
                raise CheckpointFinalizationError(
                    f"{code_prefix}_special_directory_entry",
                    "checkpoint directory entries must be directories",
                    path=relative,
                )
            entries[relative] = (
                "directory",
                stat.S_IMODE(path_stat.st_mode),
                0,
                "",
            )

        for name in file_names:
            path = directory_path / name
            relative = path.relative_to(root).as_posix()
            entries[relative] = _snapshot_regular_file(
                path,
                code_prefix=code_prefix,
                relative=relative,
            )

    try:
        root_after = os.lstat(root)
    except FileNotFoundError as exc:
        raise CheckpointFinalizationError(
            f"{code_prefix}_changed_during_snapshot",
            "checkpoint root disappeared while its tree snapshot was being recorded",
            path=str(root),
        ) from exc

    root_before_identity = (
        root_before.st_dev,
        root_before.st_ino,
        stat.S_IFMT(root_before.st_mode),
        stat.S_IMODE(root_before.st_mode),
    )
    root_after_identity = (
        root_after.st_dev,
        root_after.st_ino,
        stat.S_IFMT(root_after.st_mode),
        stat.S_IMODE(root_after.st_mode),
    )
    if root_after_identity != root_before_identity:
        raise CheckpointFinalizationError(
            f"{code_prefix}_changed_during_snapshot",
            "checkpoint root identity or permission mode changed during tree snapshot",
            path=str(root),
        )

    return TreeSnapshot(
        root_device=root_before.st_dev,
        root_inode=root_before.st_ino,
        entries=entries,
    )


def _snapshot_regular_file(
    path: Path,
    *,
    code_prefix: str,
    relative: str,
) -> TreeSnapshotEntry:
    before = os.lstat(path)
    if stat.S_ISLNK(before.st_mode):
        raise CheckpointFinalizationError(
            f"{code_prefix}_symlink",
            "checkpoint trees must not contain symlinked files",
            path=relative,
        )
    if not stat.S_ISREG(before.st_mode):
        raise CheckpointFinalizationError(
            f"{code_prefix}_special_file",
            "checkpoint payloads must be regular files",
            path=relative,
        )

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        try:
            current = os.lstat(path)
        except OSError as current_error:
            raise CheckpointFinalizationError(
                f"{code_prefix}_changed_during_snapshot",
                "checkpoint entry disappeared while its snapshot was being opened",
                path=relative,
            ) from current_error
        if stat.S_ISLNK(current.st_mode):
            raise CheckpointFinalizationError(
                f"{code_prefix}_symlink",
                "checkpoint trees must not contain symlinked files",
                path=relative,
            ) from exc
        if not stat.S_ISREG(current.st_mode):
            raise CheckpointFinalizationError(
                f"{code_prefix}_special_file",
                "checkpoint payloads must remain regular files during snapshot",
                path=relative,
            ) from exc
        raise

    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise CheckpointFinalizationError(
                f"{code_prefix}_special_file",
                "checkpoint payloads must remain regular files during snapshot",
                path=relative,
            )
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise CheckpointFinalizationError(
                f"{code_prefix}_changed_during_snapshot",
                "checkpoint entry changed while its snapshot was being opened",
                path=relative,
            )

        digest = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    current = os.lstat(path)
    if stat.S_ISLNK(current.st_mode):
        raise CheckpointFinalizationError(
            f"{code_prefix}_symlink",
            "checkpoint trees must not contain symlinked files",
            path=relative,
        )
    if not stat.S_ISREG(current.st_mode):
        raise CheckpointFinalizationError(
            f"{code_prefix}_special_file",
            "checkpoint payloads must remain regular files during snapshot",
            path=relative,
        )

    stable_fields_before = (
        opened.st_dev,
        opened.st_ino,
        stat.S_IMODE(opened.st_mode),
        opened.st_size,
        opened.st_mtime_ns,
    )
    stable_fields_after = (
        after.st_dev,
        after.st_ino,
        stat.S_IMODE(after.st_mode),
        after.st_size,
        after.st_mtime_ns,
    )
    stable_fields_current = (
        current.st_dev,
        current.st_ino,
        stat.S_IMODE(current.st_mode),
        current.st_size,
        current.st_mtime_ns,
    )
    if stable_fields_before != stable_fields_after or stable_fields_after != stable_fields_current:
        raise CheckpointFinalizationError(
            f"{code_prefix}_changed_during_snapshot",
            "checkpoint entry changed while its bytes were being snapshotted",
            path=relative,
        )

    return (
        "file",
        stat.S_IMODE(after.st_mode),
        after.st_size,
        digest.hexdigest(),
    )


def _write_manifest(root: Path, manifest: Path) -> None:
    snapshot = _snapshot_tree(root, code_prefix="staging")
    files = [
        root / relative
        for relative, entry in sorted(snapshot.entries.items())
        if entry[0] == "file" and root / relative != manifest
    ]
    if not files:
        raise CheckpointFinalizationError(
            "manifest_payload_empty",
            "manifest scope must contain at least one payload file",
            path=str(root),
        )
    lines = [
        f"{_sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in files
    ]
    with manifest.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _failure_report(
    candidate: Path,
    destination: Path,
    error: CheckpointFinalizationError,
    *,
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    issue = {"code": error.code, "message": error.message}
    if error.path is not None:
        issue["path"] = error.path
    return {
        "schema_version": 1,
        "finalized": False,
        "candidate": str(candidate),
        "destination": str(destination),
        "verification": verification,
        "errors": [issue],
    }
