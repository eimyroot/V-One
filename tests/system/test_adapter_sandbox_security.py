from __future__ import annotations

import os
from pathlib import Path

import pytest

import voodoo_product.adapters as adapters
from voodoo_product.adapters import AdapterError


def write_artifact(sandbox_root: Path, path: str, content: bytes = b"safe") -> str:
    return adapters._write_sandbox_file(
        sandbox_root=sandbox_root,
        workspace_id="ws_security",
        relative_path=Path(path),
        content=content,
    )


def test_normal_nested_sandbox_write_succeeds(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandboxes"

    governed_path = write_artifact(sandbox_root, "nested/artifact.txt", b"expected")

    assert governed_path == "ws_security/nested/artifact.txt"
    assert (sandbox_root / governed_path).read_bytes() == b"expected"


def test_workspace_identifier_cannot_escape_sandbox_root(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandboxes"

    with pytest.raises(AdapterError, match="workspace path escapes"):
        adapters._write_sandbox_file(
            sandbox_root=sandbox_root,
            workspace_id="../outside",
            relative_path=Path("artifact.txt"),
            content=b"blocked",
        )

    assert not (tmp_path / "outside" / "artifact.txt").exists()


def test_symlinked_sandbox_root_fails_closed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sandbox_root = tmp_path / "sandboxes"
    sandbox_root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(AdapterError, match="failed closed"):
        write_artifact(sandbox_root, "artifact.txt")

    assert not (outside / "ws_security" / "artifact.txt").exists()


def test_symlinked_workspace_directory_fails_closed(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandboxes"
    sandbox_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (sandbox_root / "ws_security").symlink_to(outside, target_is_directory=True)

    with pytest.raises(AdapterError, match="failed closed"):
        write_artifact(sandbox_root, "artifact.txt")

    assert not (outside / "artifact.txt").exists()


def test_symlinked_nested_directory_fails_closed(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandboxes"
    workspace_root = sandbox_root / "ws_security"
    workspace_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace_root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(AdapterError, match="failed closed"):
        write_artifact(sandbox_root, "linked/artifact.txt")

    assert not (outside / "artifact.txt").exists()


def test_symlinked_destination_fails_closed(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandboxes"
    workspace_root = sandbox_root / "ws_security"
    workspace_root.mkdir(parents=True)
    outside_file = tmp_path / "outside.txt"
    outside_file.write_bytes(b"unchanged")
    (workspace_root / "artifact.txt").symlink_to(outside_file)

    with pytest.raises(AdapterError, match="failed closed"):
        write_artifact(sandbox_root, "artifact.txt", b"blocked")

    assert outside_file.read_bytes() == b"unchanged"
    assert (workspace_root / "artifact.txt").is_symlink()


def test_directory_replacement_between_inspection_and_open_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox_root = tmp_path / "sandboxes"
    workspace_root = sandbox_root / "ws_security"
    nested = workspace_root / "nested"
    nested.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    moved_directory = outside / "moved-nested"
    original_open = os.open
    replacement_performed = False

    def replacing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal replacement_performed
        if path == "nested" and dir_fd is not None and not replacement_performed:
            nested.rename(moved_directory)
            nested.symlink_to(moved_directory, target_is_directory=True)
            replacement_performed = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(
        adapters.os,
        "supports_dir_fd",
        adapters.os.supports_dir_fd | {replacing_open},
    )
    monkeypatch.setattr(adapters.os, "open", replacing_open)

    with pytest.raises(AdapterError, match="failed closed"):
        write_artifact(sandbox_root, "nested/artifact.txt")

    assert replacement_performed
    assert not (moved_directory / "artifact.txt").exists()
