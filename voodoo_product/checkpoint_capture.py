from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .checkpoint_evidence import verify_checkpoint
from .evidence_primitives import canonical_json

_GIT_OBJECT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_MAX_CAPTURED_OUTPUT = 1024 * 1024
_CAPTURE_ROOT_MODE = 0o500
_AT_FDCWD = -100
_LINUX_RENAME_NOREPLACE = 1
_DARWIN_RENAME_EXCL = 0x00000004
_CAPTURE_ROOT_ENTRIES = {
    "README.txt": "file",
    "ops": "directory",
    "source": "directory",
}


class CheckpointCaptureError(ValueError):
    """Fail-closed runtime checkpoint capture error."""

    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


@dataclass(frozen=True)
class GitTreeEntry:
    mode: str
    object_type: str
    object_id: str
    relative_path: str


@dataclass(frozen=True)
class RepositoryState:
    root: Path
    branch: str
    head: str
    tree: str
    parent: str
    subject: str
    tracked_entries: tuple[GitTreeEntry, ...]
    local_origin: str


@dataclass(frozen=True)
class CaptureTarget:
    destination: Path
    parent: Path


@dataclass(frozen=True)
class RuntimeCapture:
    image: str
    image_id: str
    platform: str
    evidence_bundle_sha256: str


def capture_runtime_candidate(
    destination: str | Path,
    *,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    """Capture one verifier-compatible local runtime checkpoint candidate."""

    destination_input = Path(destination)
    repository_input = Path.cwd() if repository is None else Path(repository)
    staging: Path | None = None
    image: str | None = None
    verification: dict[str, Any] | None = None
    state: RepositoryState | None = None
    report: dict[str, Any] | None = None
    destination_published = False

    try:
        git = shutil.which("git")
        if git is None:
            raise CheckpointCaptureError("git_unavailable", "git executable is required")
        root = _resolve_repository_root(git, repository_input)
        state = _observe_repository(git, root)
        target = _prepare_target(destination_input, root)

        docker = shutil.which("docker")
        if docker is None:
            raise CheckpointCaptureError(
                "docker_unavailable",
                "docker executable is required for runtime capture",
            )
        bash = shutil.which("bash")
        if bash is None:
            raise CheckpointCaptureError(
                "smoke_failed",
                "bash executable is required for the canonical smoke gate",
            )

        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{target.destination.name}.capture-",
                dir=target.parent,
            )
        )
        staging.chmod(0o700)

        _capture_source(git, state, staging)
        _require_repository_unchanged(state, _reobserve_repository(git, root))

        token = secrets.token_hex(6)
        candidate_image = f"voodoo-one:capture-{state.head[:12]}-{token}"
        namespace = f"capture-{state.head[:12]}-{token}"
        if _SAFE_IDENTIFIER_PATTERN.fullmatch(namespace) is None:
            raise CheckpointCaptureError(
                "capture_io_error",
                "generated runtime namespace was invalid",
            )
        _require_task_image_absent(docker, candidate_image, cwd=root)
        image = candidate_image
        runtime = _capture_runtime(
            docker=docker,
            bash=bash,
            repository=state.root,
            checkpoint=staging,
            state=state,
            image=image,
            namespace=namespace,
        )
        _require_repository_unchanged(state, _reobserve_repository(git, root))

        generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        _write_provenance(staging, state, runtime, generated_at=generated_at)
        _write_checkpoint_readme(staging, state, generated_at=generated_at)
        _sanitize_capture_root(staging)
        _validate_capture_root_inventory(staging)
        _seal_capture_root(staging)
        _validate_capture_root_inventory(staging)
        _write_outer_manifest(staging)

        verification = verify_checkpoint(staging)
        if (
            verification.get("valid") is not True
            or verification.get("errors")
            or not isinstance(verification.get("warnings"), list)
        ):
            raise CheckpointCaptureError(
                "candidate_verification_failed",
                "captured candidate did not pass the existing checkpoint verifier",
                path=str(staging),
            )
        _require_repository_unchanged(state, _reobserve_repository(git, root))

        _remove_task_image(docker, image, cwd=root)
        image = None
        staging.chmod(0o700)
        try:
            _rename_directory_no_replace(staging, target.destination)
        except FileExistsError as exc:
            _seal_capture_root(staging)
            raise CheckpointCaptureError(
                "destination_exists",
                "destination appeared during capture",
                path=str(target.destination),
            ) from exc
        except OSError:
            _seal_capture_root(staging)
            raise
        staging = None
        destination_published = True
        _seal_capture_root(target.destination)
        _validate_capture_root_inventory(target.destination)

        verification = verify_checkpoint(target.destination)
        if (
            verification.get("valid") is not True
            or verification.get("errors")
            or verification.get("warnings") != []
        ):
            raise CheckpointCaptureError(
                "promoted_candidate_verification_failed",
                "promoted candidate did not pass fail-closed verification without warnings",
                path=str(target.destination),
            )
        _require_repository_unchanged(state, _reobserve_repository(git, root))

        report = {
            "schema_version": 1,
            "captured": True,
            "candidate": str(target.destination),
            "head": state.head,
            "image_id": runtime.image_id,
            "verification": verification,
            "errors": [],
        }
    except CheckpointCaptureError as exc:
        report = _failure_report(
            destination_input,
            exc,
            state=state,
            verification=verification,
            destination_published=destination_published,
        )
    except (OSError, json.JSONDecodeError, subprocess.SubprocessError, tarfile.TarError) as exc:
        error = CheckpointCaptureError(
            "capture_io_error",
            f"{type(exc).__name__}: {exc}",
            path=str(getattr(exc, "filename", "")) or None,
        )
        report = _failure_report(
            destination_input,
            error,
            state=state,
            verification=verification,
            destination_published=destination_published,
        )
    finally:
        cleanup_issues: list[dict[str, str]] = []
        if image is not None:
            try:
                docker = shutil.which("docker")
                if docker is None:
                    raise OSError("docker disappeared before image cleanup")
                cwd = state.root if state is not None else repository_input
                _remove_task_image(docker, image, cwd=cwd)
            except (CheckpointCaptureError, OSError) as exc:
                cleanup_issues.append(
                    _issue(
                        "capture_cleanup_failed",
                        f"{type(exc).__name__}: {exc}",
                        path=image,
                    )
                )
        if staging is not None and os.path.lexists(staging):
            try:
                _remove_capture_staging(staging)
            except OSError as exc:
                cleanup_issues.append(
                    _issue(
                        "capture_cleanup_failed",
                        f"{type(exc).__name__}: {exc}",
                        path=str(staging),
                    )
                )
        if report is not None and cleanup_issues:
            report["captured"] = False
            report["errors"] = [*report.get("errors", []), *cleanup_issues]

    if report is None:
        raise RuntimeError("runtime capture finished without a structured report")
    return report


def render_capture_report(report: dict[str, Any], *, canonical: bool = False) -> str:
    """Render a stable runtime capture report."""

    if canonical:
        return canonical_json(report)
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)


def _resolve_repository_root(git: str, repository: Path) -> Path:
    requested = repository.resolve(strict=True)
    result = _run_process(
        [git, "rev-parse", "--show-toplevel"],
        cwd=requested,
        env=_git_environment(),
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise CheckpointCaptureError(
            "capture_io_error",
            result.stderr.strip() or "capture must run from a Git repository root",
            path=str(requested),
        )
    observed = Path(result.stdout.strip()).resolve(strict=True)
    if observed != requested:
        raise CheckpointCaptureError(
            "capture_io_error",
            "capture command must execute against the repository root",
            path=str(requested),
        )
    return observed


def _observe_repository(git: str, root: Path) -> RepositoryState:
    branch_result = _run_process(
        [git, "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=root,
        env=_git_environment(),
        text=True,
        timeout=60,
    )
    if branch_result.returncode != 0 or not branch_result.stdout.strip():
        raise CheckpointCaptureError(
            "detached_head",
            "runtime capture requires an attached local branch",
            path=str(root),
        )
    branch = branch_result.stdout.strip()

    status = _run_process(
        [git, "status", "--porcelain=v1", "--untracked-files=all", "-z"],
        cwd=root,
        env=_git_environment(),
        text=False,
        timeout=60,
    )
    if status.returncode != 0:
        raise CheckpointCaptureError(
            "capture_io_error",
            _decode_output(status.stderr) or "git status failed",
            path=str(root),
        )
    if status.stdout:
        raise CheckpointCaptureError(
            "repository_dirty",
            "tracked, index, and untracked state must all be clean",
            path=str(root),
        )

    head = _git_value(git, root, ["rev-parse", "HEAD"])
    tree = _git_value(git, root, ["rev-parse", "HEAD^{tree}"])
    parent = _git_value(git, root, ["rev-parse", "HEAD^"])
    subject = _git_value(git, root, ["show", "-s", "--format=%s", "HEAD"])
    for value in (head, tree, parent):
        if _GIT_OBJECT_PATTERN.fullmatch(value) is None:
            raise CheckpointCaptureError(
                "capture_io_error",
                "repository identity did not use expected SHA-1 object IDs",
                path=str(root),
            )

    tree_result = _run_process(
        [git, "ls-tree", "-r", "-z", head],
        cwd=root,
        env=_git_environment(),
        text=False,
        timeout=60,
    )
    if tree_result.returncode != 0:
        raise CheckpointCaptureError(
            "capture_io_error",
            _decode_output(tree_result.stderr) or "git ls-tree failed",
            path=str(root),
        )
    entries = _parse_git_tree(tree_result.stdout)
    if not entries:
        raise CheckpointCaptureError(
            "capture_io_error",
            "repository must contain at least one tracked file",
            path=str(root),
        )
    for entry in entries:
        if entry.object_type != "blob" or entry.mode not in {"100644", "100755"}:
            raise CheckpointCaptureError(
                "unsupported_source_entry",
                f"unsupported Git entry {entry.mode} {entry.object_type}",
                path=entry.relative_path,
            )

    return RepositoryState(
        root=root,
        branch=branch,
        head=head,
        tree=tree,
        parent=parent,
        subject=subject,
        tracked_entries=entries,
        local_origin=_observe_origin_relation(git, root, branch, head),
    )


def _observe_origin_relation(git: str, root: Path, branch: str, head: str) -> str:
    origin_ref = f"refs/remotes/origin/{branch}"
    exists = _run_process(
        [git, "show-ref", "--verify", "--quiet", origin_ref],
        cwd=root,
        env=_git_environment(),
        text=True,
        timeout=60,
    )
    if exists.returncode != 0:
        return "NOT_OBSERVED"
    counts = _git_value(git, root, ["rev-list", "--left-right", "--count", f"{origin_ref}...{head}"])
    try:
        remote_only, local_only = (int(value) for value in counts.split())
    except (TypeError, ValueError) as exc:
        raise CheckpointCaptureError(
            "capture_io_error",
            "could not classify the observed origin relation",
        ) from exc
    if remote_only == 0 and local_only == 0:
        return "IN_SYNC"
    if remote_only == 0:
        return f"LOCAL_AHEAD_{local_only}"
    if local_only == 0:
        return f"LOCAL_BEHIND_{remote_only}"
    return f"DIVERGED_REMOTE_{remote_only}_LOCAL_{local_only}"


def _prepare_target(destination: Path, repository: Path) -> CaptureTarget:
    if not destination.is_absolute():
        raise CheckpointCaptureError(
            "destination_not_absolute",
            "candidate destination must be absolute",
            path=str(destination),
        )
    if destination.name in {"", ".", ".."}:
        raise CheckpointCaptureError(
            "destination_invalid",
            "candidate destination must name one new directory",
            path=str(destination),
        )
    try:
        parent = destination.parent.resolve(strict=True)
    except FileNotFoundError as exc:
        raise CheckpointCaptureError(
            "destination_parent_missing",
            "candidate destination parent must already exist",
            path=str(destination.parent),
        ) from exc
    parent_stat = os.lstat(parent)
    if stat.S_ISLNK(parent_stat.st_mode) or not stat.S_ISDIR(parent_stat.st_mode):
        raise CheckpointCaptureError(
            "destination_parent_invalid",
            "candidate destination parent must be a real directory",
            path=str(parent),
        )
    if destination.parent != parent:
        raise CheckpointCaptureError(
            "destination_parent_invalid",
            "candidate destination must not traverse symlinked parent components",
            path=str(destination.parent),
        )
    normalized = parent / destination.name
    if normalized == repository or normalized.is_relative_to(repository):
        raise CheckpointCaptureError(
            "destination_inside_repository",
            "candidate destination must be outside the repository worktree",
            path=str(normalized),
        )
    if os.path.lexists(normalized):
        raise CheckpointCaptureError(
            "destination_exists",
            "candidate destination must not already exist",
            path=str(normalized),
        )
    return CaptureTarget(destination=normalized, parent=parent)


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically rename one directory without replacing an existing destination."""

    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)

    if sys.platform.startswith("linux"):
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise OSError(
                errno.ENOSYS,
                "atomic no-replace rename is unavailable on this Linux runtime",
                str(destination),
            )
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = renameat2(
            _AT_FDCWD,
            source_bytes,
            _AT_FDCWD,
            destination_bytes,
            _LINUX_RENAME_NOREPLACE,
        )
    elif sys.platform == "darwin":
        renamex_np = getattr(libc, "renamex_np", None)
        if renamex_np is None:
            raise OSError(
                errno.ENOSYS,
                "atomic exclusive rename is unavailable on this macOS runtime",
                str(destination),
            )
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = renamex_np(source_bytes, destination_bytes, _DARWIN_RENAME_EXCL)
    else:
        raise OSError(
            errno.ENOTSUP,
            f"atomic no-replace directory rename is unsupported on {sys.platform}",
            str(destination),
        )

    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise FileExistsError(error, os.strerror(error), str(destination))
    raise OSError(error, os.strerror(error), str(destination))


def _capture_source(git: str, state: RepositoryState, checkpoint: Path) -> None:
    source = checkpoint / "source"
    artifacts = checkpoint / "ops" / "artifacts"
    source.mkdir(parents=True, mode=0o700)
    artifacts.mkdir(parents=True, mode=0o700)

    for entry in state.tracked_entries:
        result = _run_process(
            [git, "cat-file", "blob", entry.object_id],
            cwd=state.root,
            env=_git_environment(),
            text=False,
            timeout=60,
        )
        if result.returncode != 0:
            raise CheckpointCaptureError(
                "capture_io_error",
                _decode_output(result.stderr) or "git cat-file failed",
                path=entry.relative_path,
            )
        destination = source.joinpath(*PurePosixPath(entry.relative_path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_new_file(destination, result.stdout, mode=0o755 if entry.mode == "100755" else 0o644)

    short_head = state.head[:12]
    source_archive = artifacts / f"source-{short_head}.tar.gz"
    archive = _run_process(
        [
            git,
            "archive",
            "--format=tar.gz",
            f"--prefix=voodoo-one-{short_head}/",
            f"--output={source_archive}",
            state.head,
        ],
        cwd=state.root,
        env=_git_environment(),
        text=True,
        timeout=120,
    )
    if archive.returncode != 0:
        raise CheckpointCaptureError(
            "capture_io_error",
            archive.stderr.strip() or "git archive failed",
            path=str(source_archive),
        )

    bundle = artifacts / f"repository-{short_head}.bundle"
    bundle_result = _run_process(
        [
            git,
            "bundle",
            "create",
            str(bundle),
            f"refs/heads/{state.branch}",
        ],
        cwd=state.root,
        env=_git_environment(),
        text=True,
        timeout=120,
    )
    if bundle_result.returncode != 0:
        raise CheckpointCaptureError(
            "capture_io_error",
            bundle_result.stderr.strip() or "git bundle creation failed",
            path=str(bundle),
        )


def _capture_runtime(
    *,
    docker: str,
    bash: str,
    repository: Path,
    checkpoint: Path,
    state: RepositoryState,
    image: str,
    namespace: str,
) -> RuntimeCapture:
    runtime = checkpoint / "ops" / "evidence" / "runtime"
    runtime.mkdir(parents=True, mode=0o700)

    version = _run_process(
        [docker, "version", "--format", "{{json .}}"],
        cwd=repository,
        text=True,
        timeout=60,
    )
    if version.returncode != 0:
        raise CheckpointCaptureError(
            "docker_unavailable",
            version.stderr.strip() or "docker daemon is unavailable",
        )
    _write_text(runtime / "01_DOCKER_VERSION.json", _bounded_output(version.stdout))

    build_command = [
        docker,
        "build",
        "--progress=plain",
        "--tag",
        image,
        "--file",
        str(checkpoint / "source" / "Dockerfile.product"),
        str(checkpoint / "source"),
    ]
    build = _run_process(
        build_command,
        cwd=repository,
        text=True,
        timeout=1200,
    )
    _write_text(
        runtime / "02_DOCKER_BUILD.log",
        _command_log(build_command, build),
    )
    if build.returncode != 0:
        raise CheckpointCaptureError(
            "docker_build_failed",
            "canonical Docker product image build failed",
        )

    inspect = _run_process(
        [docker, "image", "inspect", image],
        cwd=repository,
        text=True,
        timeout=60,
    )
    if inspect.returncode != 0:
        raise CheckpointCaptureError(
            "image_identity_invalid",
            inspect.stderr.strip() or "docker image inspect failed",
        )
    image_inspect = json.loads(inspect.stdout)
    image_id, platform = _validate_image_inspect(image_inspect, image)
    _write_text(
        runtime / "06_IMAGE_INSPECT.json",
        json.dumps(image_inspect, indent=2, sort_keys=True) + "\n",
    )

    smoke_command = [
        bash,
        "scripts/smoke_product_image.sh",
        image,
        namespace,
        str(runtime.resolve(strict=True)),
    ]
    smoke = _run_process(
        smoke_command,
        cwd=repository,
        text=True,
        timeout=180,
    )
    _write_text(runtime / "04_PRODUCT_IMAGE_SMOKE.log", _command_log(smoke_command, smoke))
    health = _read_optional_json(runtime / "08_APPLICATION_HEALTH.json")
    if isinstance(health, dict) and health.get("production_effects") != "DISABLED":
        raise CheckpointCaptureError(
            "production_effects_not_disabled",
            "runtime health did not report production effects disabled",
        )
    combined_smoke_output = f"{smoke.stdout}\n{smoke.stderr}"
    if "VOODOO_SMOKE_ERROR=capture_cleanup_failed" in combined_smoke_output:
        raise CheckpointCaptureError(
            "capture_cleanup_failed",
            "canonical smoke gate could not clean its task-owned resources",
        )
    if smoke.returncode != 0:
        code = (
            "docker_health_unverified"
            if "VOODOO_SMOKE_ERROR=docker_health_unverified" in combined_smoke_output
            else "smoke_failed"
        )
        raise CheckpointCaptureError(code, "canonical product image smoke failed")

    container_health = _read_required_json(runtime / "07_CONTAINER_HEALTH.json")
    if not isinstance(container_health, dict) or container_health.get("Status") != "healthy":
        raise CheckpointCaptureError(
            "docker_health_unverified",
            "Docker container health state was not observed as healthy",
        )
    container_image_id = (runtime / "07_CONTAINER_IMAGE_ID.txt").read_text(
        encoding="utf-8"
    ).strip()
    if container_image_id != image_id:
        raise CheckpointCaptureError(
            "image_identity_invalid",
            "running container image identity did not match the inspected image",
        )
    if not isinstance(health, dict):
        raise CheckpointCaptureError(
            "smoke_failed",
            "application health evidence was missing or invalid",
        )
    expected_health: dict[str, object] = {
        "status": "HEALTHY",
        "database_backend": "sqlite",
        "schema_version": 8,
        "production_effects": "DISABLED",
    }
    if any(health.get(key) != value for key, value in expected_health.items()):
        if health.get("production_effects") != "DISABLED":
            raise CheckpointCaptureError(
                "production_effects_not_disabled",
                "runtime health did not report production effects disabled",
            )
        raise CheckpointCaptureError(
            "smoke_failed",
            "application health evidence did not satisfy the product smoke contract",
        )

    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    readme = "\n".join(
        [
            "VOODOO ONE DOCKER / RUNTIME CLOSURE",
            "",
            "STATUS=VERIFIED_NATIVE_DOCKER_RUNTIME",
            "RELEASE_VERIFIED=NO",
            f"HEAD={state.head}",
            f"TREE={state.tree}",
            f"BRANCH={state.branch}",
            f"IMAGE={image}",
            f"IMAGE_ID={image_id}",
            f"IMAGE_OS={platform.split('/', maxsplit=1)[0]}",
            f"IMAGE_ARCHITECTURE={platform.split('/', maxsplit=1)[1]}",
            "PRODUCT_IMAGE_SMOKE=PASSED",
            "DOCKER_HEALTHCHECK=HEALTHY",
            "WORKTREE=CLEAN",
            f"LOCAL_ORIGIN={state.local_origin}",
            "GITHUB_PUSH=NOT_PERFORMED",
            "PRODUCTION_EFFECTS=DISABLED",
            f"GENERATED_AT={generated_at}",
            "",
            "LIMITATIONS:",
            "- Local development runtime evidence only; not a release or deployment.",
            "- Image tag is task-owned and removed after candidate verification.",
        ]
    )
    _write_text(runtime / "README.txt", readme + "\n")

    runtime_bundle = (
        checkpoint
        / "ops"
        / "artifacts"
        / f"voodoo-one-docker-runtime-{state.head[:12]}.tar.gz"
    )
    with tarfile.open(runtime_bundle, mode="w:gz") as archive:
        archive.add(runtime, arcname=f"voodoo-one-docker-runtime-{state.head[:12]}")

    return RuntimeCapture(
        image=image,
        image_id=image_id,
        platform=platform,
        evidence_bundle_sha256=_sha256_file(runtime_bundle),
    )


def _validate_image_inspect(image_inspect: Any, image: str) -> tuple[str, str]:
    if not isinstance(image_inspect, list) or len(image_inspect) != 1:
        raise CheckpointCaptureError(
            "image_identity_invalid",
            "docker image inspect must return exactly one image",
        )
    entry = image_inspect[0]
    if not isinstance(entry, dict):
        raise CheckpointCaptureError(
            "image_identity_invalid",
            "docker image inspect entry must be an object",
        )
    image_id = entry.get("Id")
    operating_system = entry.get("Os")
    architecture = entry.get("Architecture")
    config = entry.get("Config")
    repo_tags = entry.get("RepoTags")
    if not isinstance(image_id, str) or _IMAGE_ID_PATTERN.fullmatch(image_id) is None:
        raise CheckpointCaptureError("image_identity_invalid", "image ID must be sha256")
    if (
        not isinstance(operating_system, str)
        or not operating_system
        or not isinstance(architecture, str)
        or not architecture
    ):
        raise CheckpointCaptureError(
            "image_identity_invalid",
            "image OS and architecture must be present",
        )
    if not isinstance(config, dict) or config.get("User") != "voodoo":
        raise CheckpointCaptureError(
            "image_identity_invalid",
            "captured image must run as voodoo",
        )
    if not isinstance(repo_tags, list) or image not in repo_tags:
        raise CheckpointCaptureError(
            "image_identity_invalid",
            "captured image tag did not match the task-owned image",
        )
    return image_id, f"{operating_system}/{architecture}"


def _write_provenance(
    checkpoint: Path,
    state: RepositoryState,
    runtime: RuntimeCapture,
    *,
    generated_at: str,
) -> None:
    provenance = checkpoint / "ops" / "provenance"
    provenance.mkdir(parents=True, mode=0o700)
    completion = "\n".join(
        [
            "CHECKPOINT_CLASS=DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE",
            "RELEASE_VERIFIED=NO",
            f"HEAD={state.head}",
            f"TREE={state.tree}",
            f"PARENT={state.parent}",
            f"BRANCH={state.branch}",
            f"TRACKED_FILES={len(state.tracked_entries)}",
            f"IMAGE={runtime.image}",
            f"IMAGE_ID={runtime.image_id}",
            f"IMAGE_PLATFORM={runtime.platform}",
            "PRODUCT_IMAGE_SMOKE=PASSED",
            "DOCKER_HEALTHCHECK=HEALTHY",
            "WORKTREE=CLEAN",
            f"LOCAL_ORIGIN={state.local_origin}",
            "GITHUB_PUSH=NOT_PERFORMED",
            "PRODUCTION_EFFECT=NONE",
            f"GENERATED_AT={generated_at}",
        ]
    )
    _write_text(provenance / "CHECKPOINT_COMPLETE.txt", completion + "\n")
    repository_json = {
        "checkpoint_class": "DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE",
        "release_verified": False,
        "generated_at": generated_at,
        "repository": {
            "branch": state.branch,
            "head": state.head,
            "tree": state.tree,
            "parent": state.parent,
            "subject": state.subject,
            "tracked_files": len(state.tracked_entries),
            "worktree": "CLEAN",
            "local_origin": state.local_origin,
            "github_push": "NOT_PERFORMED",
        },
        "runtime": {
            "status": "VERIFIED_NATIVE_DOCKER_RUNTIME",
            "image": runtime.image,
            "image_id": runtime.image_id,
            "platform": runtime.platform,
            "product_image_smoke": "PASSED",
            "docker_healthcheck": "HEALTHY",
            "production_effects": "DISABLED",
            "evidence_bundle_sha256": runtime.evidence_bundle_sha256,
        },
        "change": {"runtime_candidate_capture": "PASSED"},
        "limitations": [
            "Local development runtime evidence only; not a release or deployment.",
            "No registry push, remote write, signing, or production effect was performed.",
        ],
    }
    _write_text(
        provenance / "repository.json",
        json.dumps(repository_json, indent=2, sort_keys=True) + "\n",
    )


def _write_checkpoint_readme(
    checkpoint: Path,
    state: RepositoryState,
    *,
    generated_at: str,
) -> None:
    _write_text(
        checkpoint / "README.txt",
        "\n".join(
            [
                "VOODOO One local runtime checkpoint candidate",
                f"HEAD={state.head}",
                f"BRANCH={state.branch}",
                f"GENERATED_AT={generated_at}",
                "RELEASE_VERIFIED=NO",
                "PRODUCTION_EFFECT=NONE",
                "",
            ]
        ),
    )


def _sanitize_capture_root(checkpoint: Path) -> None:
    metadata = checkpoint / ".DS_Store"
    if not os.path.lexists(metadata):
        return
    metadata_stat = os.lstat(metadata)
    if stat.S_ISLNK(metadata_stat.st_mode) or not stat.S_ISREG(metadata_stat.st_mode):
        raise CheckpointCaptureError(
            "capture_root_metadata_invalid",
            "capture root metadata must be a regular file before removal",
            path=str(metadata),
        )
    metadata.unlink()


def _validate_capture_root_inventory(checkpoint: Path) -> None:
    with os.scandir(checkpoint) as directory_entries:
        entries = {entry.name: entry for entry in directory_entries}
    if set(entries) != set(_CAPTURE_ROOT_ENTRIES):
        raise CheckpointCaptureError(
            "capture_root_inventory_invalid",
            "capture root must contain only README.txt, ops, and source",
            path=str(checkpoint),
        )
    for name, expected_type in _CAPTURE_ROOT_ENTRIES.items():
        entry_stat = entries[name].stat(follow_symlinks=False)
        valid = (
            stat.S_ISREG(entry_stat.st_mode)
            if expected_type == "file"
            else stat.S_ISDIR(entry_stat.st_mode)
        )
        if entries[name].is_symlink() or not valid:
            raise CheckpointCaptureError(
                "capture_root_inventory_invalid",
                f"capture root entry must be a real {expected_type}",
                path=str(checkpoint / name),
            )


def _seal_capture_root(checkpoint: Path) -> None:
    checkpoint.chmod(_CAPTURE_ROOT_MODE)
    root_mode = stat.S_IMODE(os.lstat(checkpoint).st_mode)
    if root_mode != _CAPTURE_ROOT_MODE:
        raise CheckpointCaptureError(
            "capture_root_sealing_failed",
            "capture root did not retain required read/traverse-only permissions",
            path=str(checkpoint),
        )


def _write_outer_manifest(checkpoint: Path) -> None:
    manifest = checkpoint / "ops" / "SHA256SUMS"
    files: list[Path] = []
    for directory, directory_names, file_names in os.walk(checkpoint, followlinks=False):
        directory_names.sort()
        file_names.sort()
        directory_path = Path(directory)
        for name in directory_names:
            candidate = directory_path / name
            candidate_stat = os.lstat(candidate)
            if stat.S_ISLNK(candidate_stat.st_mode) or not stat.S_ISDIR(candidate_stat.st_mode):
                raise CheckpointCaptureError(
                    "capture_io_error",
                    "candidate directories must be real directories",
                    path=str(candidate),
                )
        for name in file_names:
            candidate = directory_path / name
            if candidate == manifest:
                continue
            candidate_stat = os.lstat(candidate)
            if stat.S_ISLNK(candidate_stat.st_mode) or not stat.S_ISREG(candidate_stat.st_mode):
                raise CheckpointCaptureError(
                    "capture_io_error",
                    "candidate payloads must be regular files",
                    path=str(candidate),
                )
            files.append(candidate)
    if not files:
        raise CheckpointCaptureError(
            "capture_io_error",
            "candidate manifest cannot be empty",
            path=str(checkpoint),
        )
    lines = [
        f"{_sha256_file(path)}  {path.relative_to(checkpoint).as_posix()}"
        for path in sorted(files, key=lambda item: item.relative_to(checkpoint).as_posix())
    ]
    _write_text(manifest, "\n".join(lines) + "\n")


def _require_repository_unchanged(
    expected: RepositoryState,
    observed: RepositoryState,
) -> None:
    if observed != expected:
        raise CheckpointCaptureError(
            "repository_changed_during_capture",
            "repository identity or worktree state changed during runtime capture",
            path=str(expected.root),
        )


def _reobserve_repository(git: str, root: Path) -> RepositoryState:
    try:
        return _observe_repository(git, root)
    except CheckpointCaptureError as exc:
        if exc.code in {"detached_head", "repository_dirty"}:
            raise CheckpointCaptureError(
                "repository_changed_during_capture",
                "repository identity or worktree state changed during runtime capture",
                path=str(root),
            ) from exc
        raise


def _parse_git_tree(raw: bytes) -> tuple[GitTreeEntry, ...]:
    entries: list[GitTreeEntry] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        metadata, separator, raw_path = item.partition(b"\t")
        if not separator:
            raise CheckpointCaptureError("capture_io_error", "invalid git ls-tree output")
        try:
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            relative_path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise CheckpointCaptureError(
                "unsupported_source_entry",
                "tracked paths must be valid UTF-8 regular files",
            ) from exc
        pure = PurePosixPath(relative_path)
        if (
            pure.is_absolute()
            or not pure.parts
            or any(part in {"", ".", ".."} for part in pure.parts)
            or "\\" in relative_path
            or "\x00" in relative_path
        ):
            raise CheckpointCaptureError(
                "unsupported_source_entry",
                "tracked path is unsafe",
                path=relative_path,
            )
        entries.append(
            GitTreeEntry(
                mode=mode,
                object_type=object_type,
                object_id=object_id,
                relative_path=pure.as_posix(),
            )
        )
    return tuple(entries)


def _git_value(git: str, root: Path, arguments: list[str]) -> str:
    result = _run_process(
        [git, *arguments],
        cwd=root,
        env=_git_environment(),
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise CheckpointCaptureError(
            "capture_io_error",
            result.stderr.strip() or f"git {' '.join(arguments)} failed",
            path=str(root),
        )
    return result.stdout.strip()


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    return environment


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    text: bool,
    timeout: int,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=text,
        timeout=timeout,
    )


def _remove_task_image(docker: str, image: str, *, cwd: Path) -> None:
    result = _run_process(
        [docker, "image", "rm", image],
        cwd=cwd,
        text=True,
        timeout=120,
    )
    if result.returncode != 0 and "No such image" not in result.stderr:
        raise CheckpointCaptureError(
            "capture_cleanup_failed",
            result.stderr.strip() or "task-owned Docker image cleanup failed",
            path=image,
        )


def _require_task_image_absent(docker: str, image: str, *, cwd: Path) -> None:
    result = _run_process(
        [docker, "image", "inspect", "--format", "{{.Id}}", image],
        cwd=cwd,
        text=True,
        timeout=60,
    )
    if result.returncode == 0:
        raise CheckpointCaptureError(
            "image_identity_invalid",
            "generated task image tag already exists",
            path=image,
        )
    if "No such image" not in result.stderr:
        raise CheckpointCaptureError(
            "docker_unavailable",
            result.stderr.strip() or "could not establish task image tag ownership",
            path=image,
        )


def _remove_capture_staging(path: Path) -> None:
    path_stat = os.lstat(path)
    if stat.S_ISDIR(path_stat.st_mode) and not stat.S_ISLNK(path_stat.st_mode):
        path.chmod(0o700)
    shutil.rmtree(path)


def _write_new_file(path: Path, payload: bytes, *, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    path.chmod(mode)


def _write_text(path: Path, value: str) -> None:
    _write_new_file(path, value.encode("utf-8"), mode=0o600)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_required_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise CheckpointCaptureError(
            "smoke_failed",
            "canonical smoke did not produce valid required evidence",
            path=str(path),
        ) from exc


def _read_optional_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _bounded_output(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= _MAX_CAPTURED_OUTPUT:
        return value if value.endswith("\n") else value + "\n"
    retained = encoded[-_MAX_CAPTURED_OUTPUT:].decode("utf-8", errors="replace")
    return f"OUTPUT_TRUNCATED_TO_LAST_{_MAX_CAPTURED_OUTPUT}_BYTES\n{retained}"


def _command_log(
    command: list[str],
    result: subprocess.CompletedProcess[Any],
) -> str:
    stdout = result.stdout if isinstance(result.stdout, str) else _decode_output(result.stdout)
    stderr = result.stderr if isinstance(result.stderr, str) else _decode_output(result.stderr)
    return _bounded_output(
        "\n".join(
            [
                f"COMMAND_JSON={json.dumps(command, ensure_ascii=False)}",
                f"EXIT_CODE={result.returncode}",
                "STDOUT:",
                stdout,
                "STDERR:",
                stderr,
            ]
        )
    )


def _decode_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def _failure_report(
    destination: Path,
    error: CheckpointCaptureError,
    *,
    state: RepositoryState | None,
    verification: dict[str, Any] | None,
    destination_published: bool = False,
) -> dict[str, Any]:
    report = {
        "schema_version": 1,
        "captured": False,
        "candidate": str(destination),
        "head": state.head if state is not None else None,
        "image_id": None,
        "verification": verification,
        "errors": [_issue(error.code, error.message, path=error.path)],
    }
    if destination_published:
        report["destination_published"] = True
    return report


def _issue(code: str, message: str, *, path: str | None = None) -> dict[str, str]:
    issue = {"code": code, "message": message}
    if path is not None:
        issue["path"] = path
    return issue
