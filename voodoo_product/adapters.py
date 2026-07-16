from __future__ import annotations

import contextlib
import json
import os
import secrets
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AdapterError(RuntimeError):
    pass


MAX_ARTIFACT_BYTES = 1_048_576
MAX_ARTIFACT_PATH_LENGTH = 240
MAX_ARTIFACT_PATH_PARTS = 32


@dataclass(frozen=True, slots=True)
class AdapterContext:
    workspace_id: str
    repository_root: Path
    sandbox_root: Path
    timeout_seconds: int = 120


def _safe_relative_path(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise AdapterError("path escapes the governed sandbox")
    if not candidate.parts:
        raise AdapterError("artifact path is empty")
    if len(value) > MAX_ARTIFACT_PATH_LENGTH or len(candidate.parts) > MAX_ARTIFACT_PATH_PARTS:
        raise AdapterError("artifact path exceeds the governed limit")
    return candidate


def _write_sandbox_file(
    *, sandbox_root: Path, workspace_id: str, relative_path: Path, content: bytes
) -> str:
    if not hasattr(os, "O_NOFOLLOW"):
        raise AdapterError("sandbox writes require O_NOFOLLOW support")

    root = sandbox_root.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    root_fd = os.open(root, directory_flags)
    open_fds = [root_fd]
    temporary_name: str | None = None
    try:
        with contextlib.suppress(FileExistsError):
            os.mkdir(workspace_id, mode=0o750, dir_fd=root_fd)
        current_fd = os.open(workspace_id, directory_flags, dir_fd=root_fd)
        open_fds.append(current_fd)

        for part in relative_path.parts[:-1]:
            with contextlib.suppress(FileExistsError):
                os.mkdir(part, mode=0o750, dir_fd=current_fd)
            next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            open_fds.append(next_fd)
            current_fd = next_fd

        temporary_name = f".{relative_path.name}.{secrets.token_hex(8)}.tmp"
        file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
        file_fd = os.open(temporary_name, file_flags, 0o640, dir_fd=current_fd)
        with os.fdopen(file_fd, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name,
            relative_path.name,
            src_dir_fd=current_fd,
            dst_dir_fd=current_fd,
        )
        temporary_name = None
        os.fsync(current_fd)
    except (OSError, ValueError) as exc:
        raise AdapterError("sandbox write failed closed") from exc
    finally:
        if temporary_name is not None:
            with contextlib.suppress(OSError):
                os.unlink(temporary_name, dir_fd=open_fds[-1])
        for descriptor in reversed(open_fds):
            os.close(descriptor)

    return str(Path(workspace_id) / relative_path)


def execute_adapter(
    adapter: str,
    payload: dict[str, Any],
    *,
    context: AdapterContext,
) -> dict[str, Any]:
    if adapter == "echo":
        return {"effect": "INERT", "echo": payload}

    if adapter == "write_artifact":
        relative_path = _safe_relative_path(str(payload.get("path", "artifact.json")))
        content = payload.get("content", {})
        if isinstance(content, str):
            encoded = content
        else:
            encoded = json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False)
        encoded_bytes = encoded.encode("utf-8")
        if len(encoded_bytes) > MAX_ARTIFACT_BYTES:
            raise AdapterError("artifact exceeds the governed size limit")
        governed_path = _write_sandbox_file(
            sandbox_root=context.sandbox_root,
            workspace_id=context.workspace_id,
            relative_path=relative_path,
            content=encoded_bytes,
        )
        return {
            "effect": "FILESYSTEM_WRITE",
            "path": governed_path,
            "bytes": len(encoded_bytes),
        }

    if adapter == "run_validation":
        preset = str(payload.get("preset", "python_compile"))
        presets: dict[str, tuple[list[str], Path]] = {
            "python_compile": (
                [sys.executable, "-m", "compileall", "-q", "."],
                context.repository_root,
            ),
            "pytest": ([sys.executable, "-m", "pytest", "-q"], context.repository_root),
            "frontend_build": (["npm", "run", "build"], context.repository_root / "frontend"),
        }
        if preset not in presets:
            raise AdapterError("validation preset is not allowlisted")
        command, cwd = presets[preset]
        if not cwd.exists():
            raise AdapterError(f"validation working directory is missing: {cwd}")
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=context.timeout_seconds,
            check=False,
            env={"PATH": str(Path(sys.executable).parent) + ":/usr/local/bin:/usr/bin:/bin"},
        )
        output_limit = 32_000
        return {
            "effect": "LOCAL_PROCESS",
            "preset": preset,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-output_limit:],
            "stderr": completed.stderr[-output_limit:],
            "success": completed.returncode == 0,
        }

    raise AdapterError(f"adapter is not registered: {adapter}")
