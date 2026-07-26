from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .evidence_primitives import canonical_json

_MANIFEST_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")
_GIT_OBJECT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_PLATFORM_PATTERN = re.compile(r"^[a-z0-9._-]+/[a-z0-9._-]+$")


class EvidenceVerificationError(ValueError):
    """Fail-closed validation error for one checkpoint evidence invariant."""

    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


@dataclass(frozen=True)
class ManifestEntry:
    digest: str
    relative_path: str


class CheckpointEvidenceVerifier:
    """Verify an immutable VOODOO checkpoint and emit a deterministic proof graph."""

    def __init__(self, checkpoint: Path) -> None:
        self.root = checkpoint
        self.checks: list[dict[str, Any]] = []
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []
        self.claims: dict[str, Any] = {}
        self.manifest: dict[str, str] = {}
        self._manifest_digest = ""
        self._repository: dict[str, Any] = {}
        self._completion: dict[str, str] = {}

    def verify(self) -> dict[str, Any]:
        if not self._run("checkpoint_root", self._verify_root):
            return self._report()
        if not self._run("manifest", self._verify_outer_manifest):
            return self._report()
        if not self._run("provenance", self._verify_provenance):
            return self._report()
        if not self._run("git_bundle", self._verify_git_bundle_and_source):
            return self._report()
        if not self._run("source_archive", self._verify_source_archive):
            return self._report()
        if not self._run("runtime_evidence", self._verify_runtime_evidence):
            return self._report()
        self._run("nested_manifests", self._inspect_nested_manifests)
        return self._report()

    def _run(self, name: str, operation: Callable[[], dict[str, Any]]) -> bool:
        try:
            details = operation()
        except EvidenceVerificationError as exc:
            issue = {"code": exc.code, "message": exc.message}
            if exc.path is not None:
                issue["path"] = exc.path
            self.errors.append(issue)
            self.checks.append({"name": name, "ok": False, "details": issue})
            return False
        except (OSError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
            issue = {
                "code": f"{name}_io_error",
                "message": f"{type(exc).__name__}: {exc}",
            }
            self.errors.append(issue)
            self.checks.append({"name": name, "ok": False, "details": issue})
            return False
        self.checks.append({"name": name, "ok": True, "details": details})
        return True

    def _verify_root(self) -> dict[str, Any]:
        try:
            root_stat = os.lstat(self.root)
        except FileNotFoundError as exc:
            raise EvidenceVerificationError(
                "checkpoint_missing",
                "checkpoint path does not exist",
                path=str(self.root),
            ) from exc
        if stat.S_ISLNK(root_stat.st_mode):
            raise EvidenceVerificationError(
                "checkpoint_symlink",
                "checkpoint root must not be a symlink",
                path=str(self.root),
            )
        if not stat.S_ISDIR(root_stat.st_mode):
            raise EvidenceVerificationError(
                "checkpoint_not_directory",
                "checkpoint path must be a directory",
                path=str(self.root),
            )
        self.root = self.root.resolve(strict=True)
        return {"path": str(self.root)}

    def _verify_outer_manifest(self) -> dict[str, Any]:
        manifest_path = "ops/SHA256SUMS"
        manifest_file = self._safe_regular_file(manifest_path)
        entries = self._parse_manifest(manifest_file)
        self._manifest_digest = _sha256_file(manifest_file)

        actual_files = self._list_regular_files(self.root)
        actual_payloads = actual_files - {manifest_path}
        expected_payloads = set(entries)
        missing = sorted(expected_payloads - actual_payloads)
        unexpected = sorted(actual_payloads - expected_payloads)
        if missing or unexpected:
            raise EvidenceVerificationError(
                "manifest_coverage_mismatch",
                f"missing={missing}; unexpected={unexpected}",
                path=manifest_path,
            )

        mismatches: list[str] = []
        for relative_path, expected_digest in entries.items():
            actual_digest = _sha256_file(self._safe_regular_file(relative_path))
            if actual_digest != expected_digest:
                mismatches.append(relative_path)
        if mismatches:
            raise EvidenceVerificationError(
                "manifest_digest_mismatch",
                f"SHA-256 mismatch for: {sorted(mismatches)}",
                path=manifest_path,
            )

        self.manifest = entries
        return {
            "manifest": manifest_path,
            "manifest_sha256": self._manifest_digest,
            "payload_files": len(entries),
            "physical_files": len(actual_files),
            "coverage": "FULL",
        }

    def _verify_provenance(self) -> dict[str, Any]:
        completion_path = "ops/provenance/CHECKPOINT_COMPLETE.txt"
        repository_path = "ops/provenance/repository.json"
        completion = _parse_key_value_file(self._safe_regular_file(completion_path))
        repository_text = self._safe_regular_file(repository_path).read_text(encoding="utf-8")
        repository = json.loads(repository_text)
        if not isinstance(repository, dict):
            raise EvidenceVerificationError(
                "repository_json_type",
                "repository.json must contain one JSON object",
                path=repository_path,
            )

        required = {
            "CHECKPOINT_CLASS",
            "RELEASE_VERIFIED",
            "HEAD",
            "TREE",
            "PARENT",
            "BRANCH",
            "TRACKED_FILES",
            "IMAGE",
            "IMAGE_ID",
            "IMAGE_PLATFORM",
            "PRODUCT_IMAGE_SMOKE",
            "DOCKER_HEALTHCHECK",
            "WORKTREE",
            "LOCAL_ORIGIN",
            "GITHUB_PUSH",
            "PRODUCTION_EFFECT",
            "GENERATED_AT",
        }
        missing = sorted(required - set(completion))
        if missing:
            raise EvidenceVerificationError(
                "completion_keys_missing",
                f"missing completion keys: {missing}",
                path=completion_path,
            )

        for key in ("HEAD", "TREE", "PARENT"):
            if not _GIT_OBJECT_PATTERN.fullmatch(completion[key]):
                raise EvidenceVerificationError(
                    "invalid_git_object_id",
                    f"{key} must be a 40-character lowercase Git object ID",
                    path=completion_path,
                )
        if not _SHA256_PATTERN.fullmatch(completion["IMAGE_ID"]):
            raise EvidenceVerificationError(
                "invalid_image_id",
                "IMAGE_ID must be a sha256 digest",
                path=completion_path,
            )
        if not _PLATFORM_PATTERN.fullmatch(completion["IMAGE_PLATFORM"]):
            raise EvidenceVerificationError(
                "invalid_image_platform",
                "IMAGE_PLATFORM must use os/architecture form",
                path=completion_path,
            )
        try:
            tracked_files = int(completion["TRACKED_FILES"])
        except ValueError as exc:
            raise EvidenceVerificationError(
                "invalid_tracked_files",
                "TRACKED_FILES must be an integer",
                path=completion_path,
            ) from exc
        if tracked_files < 1:
            raise EvidenceVerificationError(
                "invalid_tracked_files",
                "TRACKED_FILES must be positive",
                path=completion_path,
            )
        _parse_utc_timestamp(completion["GENERATED_AT"], path=completion_path)

        repository_claim = repository.get("repository")
        runtime_claim = repository.get("runtime")
        if not isinstance(repository_claim, dict) or not isinstance(runtime_claim, dict):
            raise EvidenceVerificationError(
                "repository_json_sections",
                "repository.json must contain repository and runtime objects",
                path=repository_path,
            )

        expected_pairs = {
            "checkpoint_class": completion["CHECKPOINT_CLASS"],
            "generated_at": completion["GENERATED_AT"],
        }
        for key, expected in expected_pairs.items():
            if repository.get(key) != expected:
                raise EvidenceVerificationError(
                    "provenance_mismatch",
                    f"repository.json {key} does not match completion marker",
                    path=repository_path,
                )
        if repository.get("release_verified") is not _yes_no_to_bool(
            completion["RELEASE_VERIFIED"]
        ):
            raise EvidenceVerificationError(
                "release_claim_mismatch",
                "release verification claims are inconsistent",
                path=repository_path,
            )

        repository_pairs: dict[str, object] = {
            "head": completion["HEAD"],
            "tree": completion["TREE"],
            "parent": completion["PARENT"],
            "branch": completion["BRANCH"],
            "tracked_files": tracked_files,
            "worktree": completion["WORKTREE"],
            "local_origin": completion["LOCAL_ORIGIN"],
            "github_push": completion["GITHUB_PUSH"],
        }
        _require_mapping_values(repository_claim, repository_pairs, path=repository_path)

        runtime_pairs: dict[str, object] = {
            "image": completion["IMAGE"],
            "image_id": completion["IMAGE_ID"],
            "platform": completion["IMAGE_PLATFORM"],
            "product_image_smoke": completion["PRODUCT_IMAGE_SMOKE"],
            "docker_healthcheck": completion["DOCKER_HEALTHCHECK"],
        }
        _require_mapping_values(runtime_claim, runtime_pairs, path=repository_path)

        production_effects = runtime_claim.get("production_effects")
        if completion["PRODUCTION_EFFECT"] == "NONE" and production_effects != "DISABLED":
            raise EvidenceVerificationError(
                "production_effect_mismatch",
                "NONE production effect requires DISABLED runtime production effects",
                path=repository_path,
            )

        self._completion = completion
        self._repository = repository
        self.claims = {
            "checkpoint_class": completion["CHECKPOINT_CLASS"],
            "release_verified": repository["release_verified"],
            "generated_at": completion["GENERATED_AT"],
            "repository": repository_claim,
            "runtime": runtime_claim,
            "change": repository.get("change", {}),
            "limitations": repository.get("limitations", []),
        }
        return {
            "completion_marker": completion_path,
            "repository_json": repository_path,
            "head": completion["HEAD"],
            "tree": completion["TREE"],
            "image_id": completion["IMAGE_ID"],
        }

    def _verify_git_bundle_and_source(self) -> dict[str, Any]:
        bundle_paths = sorted(
            path
            for path in self.manifest
            if path.startswith("ops/artifacts/") and path.endswith(".bundle")
        )
        if len(bundle_paths) != 1:
            raise EvidenceVerificationError(
                "bundle_count",
                f"expected exactly one Git bundle, found {len(bundle_paths)}",
            )
        bundle_path = bundle_paths[0]
        bundle_file = self._safe_regular_file(bundle_path)
        git = shutil.which("git")
        if git is None:
            raise EvidenceVerificationError("git_unavailable", "git executable is required")

        heads = _run_git(git, ["bundle", "list-heads", str(bundle_file)], cwd=self.root)
        if heads.returncode != 0:
            raise EvidenceVerificationError(
                "bundle_heads_failed",
                heads.stderr.strip() or heads.stdout.strip(),
                path=bundle_path,
            )
        expected_ref = f"refs/heads/{self._completion['BRANCH']}"
        matching = []
        for line in heads.stdout.splitlines():
            object_id, separator, ref = line.partition(" ")
            if separator and ref == expected_ref:
                matching.append(object_id)
        if matching != [self._completion["HEAD"]]:
            raise EvidenceVerificationError(
                "bundle_ref_mismatch",
                f"expected {expected_ref} at {self._completion['HEAD']}, got {matching}",
                path=bundle_path,
            )

        with tempfile.TemporaryDirectory(prefix="voodoo-proofgraph-git-") as temporary:
            bare = Path(temporary) / "repository.git"
            init = _run_git(git, ["init", "--bare", "--quiet", str(bare)], cwd=self.root)
            if init.returncode != 0:
                raise EvidenceVerificationError(
                    "temporary_git_init_failed",
                    init.stderr.strip() or init.stdout.strip(),
                )
            verify = _run_git(
                git,
                ["-C", str(bare), "bundle", "verify", str(bundle_file)],
                cwd=self.root,
            )
            if verify.returncode != 0:
                raise EvidenceVerificationError(
                    "bundle_verify_failed",
                    verify.stderr.strip() or verify.stdout.strip(),
                    path=bundle_path,
                )
            local_ref = "refs/heads/checkpoint"
            fetch = _run_git(
                git,
                [
                    "-C",
                    str(bare),
                    "fetch",
                    "--quiet",
                    str(bundle_file),
                    f"{expected_ref}:{local_ref}",
                ],
                cwd=self.root,
            )
            if fetch.returncode != 0:
                raise EvidenceVerificationError(
                    "bundle_fetch_failed",
                    fetch.stderr.strip() or fetch.stdout.strip(),
                    path=bundle_path,
                )

            head = _git_value(git, bare, ["rev-parse", local_ref])
            tree = _git_value(git, bare, ["rev-parse", f"{local_ref}^{{tree}}"])
            parent = _git_value(git, bare, ["rev-parse", f"{local_ref}^"])
            subject = _git_value(git, bare, ["show", "-s", "--format=%s", local_ref])
            object_format = _git_value(git, bare, ["rev-parse", "--show-object-format"])

            if head != self._completion["HEAD"]:
                raise EvidenceVerificationError("bundle_head_mismatch", "bundle HEAD mismatch")
            if tree != self._completion["TREE"]:
                raise EvidenceVerificationError("bundle_tree_mismatch", "bundle tree mismatch")
            if parent != self._completion["PARENT"]:
                raise EvidenceVerificationError("bundle_parent_mismatch", "bundle parent mismatch")
            if subject != self._repository["repository"].get("subject"):
                raise EvidenceVerificationError(
                    "bundle_subject_mismatch",
                    "bundle subject mismatch",
                )
            if object_format not in {"sha1", "sha256"}:
                raise EvidenceVerificationError(
                    "unsupported_git_object_format",
                    f"unsupported Git object format: {object_format}",
                )

            tree_result = _run_git(
                git,
                ["-C", str(bare), "ls-tree", "-r", "-z", local_ref],
                cwd=self.root,
                text=False,
            )
            if tree_result.returncode != 0:
                raise EvidenceVerificationError(
                    "git_tree_read_failed",
                    tree_result.stderr.decode(errors="replace").strip(),
                )
            entries = _parse_git_tree(tree_result.stdout)

        expected_count = int(self._completion["TRACKED_FILES"])
        if len(entries) != expected_count:
            raise EvidenceVerificationError(
                "tracked_file_count_mismatch",
                f"expected {expected_count}, bundle contains {len(entries)}",
            )
        source_root = self.root / "source"
        source_files = self._list_regular_files(source_root)
        expected_files = {entry[3] for entry in entries}
        if source_files != expected_files:
            missing = sorted(expected_files - source_files)
            unexpected = sorted(source_files - expected_files)
            raise EvidenceVerificationError(
                "source_coverage_mismatch",
                f"missing={missing}; unexpected={unexpected}",
                path="source",
            )

        mismatches: list[str] = []
        mode_mismatches: list[str] = []
        for mode, object_type, expected_id, relative_path in entries:
            if object_type != "blob" or mode == "120000":
                raise EvidenceVerificationError(
                    "unsupported_git_entry",
                    f"unsupported Git entry {mode} {object_type}",
                    path=relative_path,
                )
            source_file = self._safe_regular_file(f"source/{relative_path}")
            actual_id = _git_blob_id(source_file.read_bytes(), object_format)
            if actual_id != expected_id:
                mismatches.append(relative_path)
            executable = bool(source_file.stat().st_mode & stat.S_IXUSR)
            expected_executable = mode == "100755"
            if executable != expected_executable:
                mode_mismatches.append(relative_path)
        if mismatches or mode_mismatches:
            raise EvidenceVerificationError(
                "source_tree_mismatch",
                f"blob_mismatches={mismatches}; mode_mismatches={mode_mismatches}",
                path="source",
            )

        return {
            "bundle": bundle_path,
            "ref": expected_ref,
            "head": head,
            "tree": tree,
            "parent": parent,
            "subject": subject,
            "object_format": object_format,
            "tracked_files": len(entries),
            "source_tree": "VERIFIED",
        }

    def _verify_source_archive(self) -> dict[str, Any]:
        archive_paths = sorted(
            path
            for path in self.manifest
            if path.startswith("ops/artifacts/source-") and path.endswith(".tar.gz")
        )
        if len(archive_paths) != 1:
            raise EvidenceVerificationError(
                "source_archive_count",
                f"expected exactly one source archive, found {len(archive_paths)}",
            )
        archive_path = archive_paths[0]
        archive_file = self._safe_regular_file(archive_path)
        source_root = self.root / "source"
        source_files = self._list_regular_files(source_root)
        expected_prefix = f"voodoo-one-{self._completion['HEAD'][:12]}"
        archive_files: dict[str, tuple[str, bool]] = {}

        try:
            with tarfile.open(archive_file, mode="r:gz") as archive:
                for member in archive.getmembers():
                    pure = PurePosixPath(member.name)
                    if pure.is_absolute() or ".." in pure.parts:
                        raise EvidenceVerificationError(
                            "source_archive_unsafe_path",
                            f"unsafe archive path: {member.name}",
                            path=archive_path,
                        )
                    if member.issym() or member.islnk() or member.isdev():
                        raise EvidenceVerificationError(
                            "source_archive_unsupported_member",
                            f"unsupported archive member: {member.name}",
                            path=archive_path,
                        )
                    if member.isdir():
                        continue
                    if not member.isfile() or len(pure.parts) < 2:
                        raise EvidenceVerificationError(
                            "source_archive_invalid_member",
                            f"invalid archive member: {member.name}",
                            path=archive_path,
                        )
                    if pure.parts[0] != expected_prefix:
                        raise EvidenceVerificationError(
                            "source_archive_prefix",
                            f"expected archive prefix {expected_prefix}",
                            path=archive_path,
                        )
                    relative_path = PurePosixPath(*pure.parts[1:]).as_posix()
                    if relative_path in archive_files:
                        raise EvidenceVerificationError(
                            "source_archive_duplicate",
                            f"duplicate archive member: {relative_path}",
                            path=archive_path,
                        )
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise EvidenceVerificationError(
                            "source_archive_read_failed",
                            f"could not read archive member: {member.name}",
                            path=archive_path,
                        )
                    with extracted:
                        digest = _sha256_stream(extracted)
                    archive_files[relative_path] = (
                        digest,
                        bool(member.mode & stat.S_IXUSR),
                    )
        except tarfile.TarError as exc:
            raise EvidenceVerificationError(
                "source_archive_invalid",
                str(exc),
                path=archive_path,
            ) from exc

        if set(archive_files) != source_files:
            missing = sorted(source_files - set(archive_files))
            unexpected = sorted(set(archive_files) - source_files)
            raise EvidenceVerificationError(
                "source_archive_coverage_mismatch",
                f"missing={missing}; unexpected={unexpected}",
                path=archive_path,
            )
        mismatches: list[str] = []
        for relative_path, (archive_digest, archive_executable) in archive_files.items():
            source_file = self._safe_regular_file(f"source/{relative_path}")
            source_digest = _sha256_file(source_file)
            source_executable = bool(source_file.stat().st_mode & stat.S_IXUSR)
            if archive_digest != source_digest or archive_executable != source_executable:
                mismatches.append(relative_path)
        if mismatches:
            raise EvidenceVerificationError(
                "source_archive_content_mismatch",
                f"archive/source mismatch: {sorted(mismatches)}",
                path=archive_path,
            )
        return {
            "archive": archive_path,
            "prefix": expected_prefix,
            "files": len(archive_files),
            "content": "VERIFIED",
        }

    def _verify_runtime_evidence(self) -> dict[str, Any]:
        runtime_root = "ops/evidence/runtime"
        runtime_readme = _parse_key_value_file(
            self._safe_regular_file(f"{runtime_root}/README.txt"),
            stop_at="LIMITATIONS:",
            ignore_non_key_lines=True,
        )
        expected = {
            "STATUS": "VERIFIED_NATIVE_DOCKER_RUNTIME",
            "RELEASE_VERIFIED": self._completion["RELEASE_VERIFIED"],
            "HEAD": self._completion["HEAD"],
            "TREE": self._completion["TREE"],
            "BRANCH": self._completion["BRANCH"],
            "IMAGE": self._completion["IMAGE"],
            "IMAGE_ID": self._completion["IMAGE_ID"],
            "PRODUCT_IMAGE_SMOKE": self._completion["PRODUCT_IMAGE_SMOKE"],
            "DOCKER_HEALTHCHECK": self._completion["DOCKER_HEALTHCHECK"],
            "WORKTREE": self._completion["WORKTREE"],
            "LOCAL_ORIGIN": self._completion["LOCAL_ORIGIN"],
            "GITHUB_PUSH": self._completion["GITHUB_PUSH"],
            "PRODUCTION_EFFECTS": "DISABLED",
        }
        for key, value in expected.items():
            if runtime_readme.get(key) != value:
                raise EvidenceVerificationError(
                    "runtime_claim_mismatch",
                    f"runtime README {key} mismatch",
                    path=f"{runtime_root}/README.txt",
                )

        inspect_path = f"{runtime_root}/06_IMAGE_INSPECT.json"
        image_inspect_text = self._safe_regular_file(inspect_path).read_text(encoding="utf-8")
        image_inspect = json.loads(image_inspect_text)
        if not isinstance(image_inspect, list) or len(image_inspect) != 1:
            raise EvidenceVerificationError(
                "image_inspect_shape",
                "image inspect evidence must contain exactly one image",
                path=inspect_path,
            )
        image = image_inspect[0]
        if not isinstance(image, dict):
            raise EvidenceVerificationError(
                "image_inspect_shape",
                "image inspect entry must be an object",
                path=inspect_path,
            )
        platform = self._completion["IMAGE_PLATFORM"].split("/", maxsplit=1)
        image_expected: dict[str, object] = {
            "Id": self._completion["IMAGE_ID"],
            "Os": platform[0],
            "Architecture": platform[1],
        }
        _require_mapping_values(image, image_expected, path=inspect_path)
        config = image.get("Config")
        if not isinstance(config, dict) or config.get("User") != "voodoo":
            raise EvidenceVerificationError(
                "image_user_mismatch",
                "verified image must run as voodoo",
                path=inspect_path,
            )

        runtime_bundle_paths = sorted(
            path
            for path in self.manifest
            if path.startswith("ops/artifacts/voodoo-one-docker-runtime-")
            and path.endswith(".tar.gz")
        )
        if len(runtime_bundle_paths) != 1:
            raise EvidenceVerificationError(
                "runtime_bundle_count",
                f"expected exactly one runtime bundle, found {len(runtime_bundle_paths)}",
            )
        expected_bundle_digest = self._repository["runtime"].get("evidence_bundle_sha256")
        if self.manifest[runtime_bundle_paths[0]] != expected_bundle_digest:
            raise EvidenceVerificationError(
                "runtime_bundle_digest_mismatch",
                "runtime bundle digest does not match provenance",
                path=runtime_bundle_paths[0],
            )
        return {
            "runtime_readme": f"{runtime_root}/README.txt",
            "image_inspect": inspect_path,
            "image_id": image["Id"],
            "platform": self._completion["IMAGE_PLATFORM"],
            "runtime_bundle": runtime_bundle_paths[0],
            "runtime_bundle_sha256": expected_bundle_digest,
        }

    def _inspect_nested_manifests(self) -> dict[str, Any]:
        summaries: list[dict[str, Any]] = []
        for scope in ("runtime", "commit"):
            base = f"ops/evidence/{scope}"
            manifest_relative = f"{base}/SHA256SUMS"
            if manifest_relative not in self.manifest:
                continue
            entries = self._parse_manifest(self._safe_regular_file(manifest_relative))
            mismatches: list[dict[str, str]] = []
            for relative_path, expected_digest in entries.items():
                nested_path = f"{base}/{relative_path}"
                actual_digest = _sha256_file(self._safe_regular_file(nested_path))
                if actual_digest != expected_digest:
                    mismatches.append(
                        {
                            "path": nested_path,
                            "declared_sha256": expected_digest,
                            "actual_sha256": actual_digest,
                        }
                    )
            summary: dict[str, Any] = {
                "scope": scope,
                "entries": len(entries),
                "mismatches": mismatches,
                "authoritative": False,
                "covered_by_outer_manifest": True,
            }
            summaries.append(summary)
            for mismatch in mismatches:
                self.warnings.append(
                    {
                        "code": "nested_post_manifest_mutation",
                        "message": (
                            f"non-authoritative {scope} manifest differs; "
                            "the outer checkpoint manifest covers the retained bytes"
                        ),
                        "path": mismatch["path"],
                    }
                )

        runtime_exception_path = "ops/evidence/03_RUNTIME_LOG_MANIFEST_EXCEPTION.txt"
        if runtime_exception_path in self.manifest:
            exception = _parse_key_value_file(self._safe_regular_file(runtime_exception_path))
            required = {
                "DECLARED_RUNTIME_LOG_SHA256",
                "ACTUAL_BUNDLED_RUNTIME_LOG_SHA256",
                "RUNTIME_LOG_INTERNAL_MANIFEST_MATCH",
                "RUNTIME_LOG_EXCEPTION",
            }
            if required - set(exception):
                raise EvidenceVerificationError(
                    "runtime_manifest_exception_incomplete",
                    "runtime manifest exception evidence is incomplete",
                    path=runtime_exception_path,
                )
            if exception["RUNTIME_LOG_EXCEPTION"] != "EXPECTED_POST_MANIFEST_APPEND":
                raise EvidenceVerificationError(
                    "runtime_manifest_exception_unrecognized",
                    "runtime manifest exception is not recognized",
                    path=runtime_exception_path,
                )
        return {"scopes": summaries, "warning_count": len(self.warnings)}

    def _report(self) -> dict[str, Any]:
        valid = not self.errors and all(check["ok"] for check in self.checks)
        graph = self._proof_graph() if self._completion else {"nodes": [], "edges": []}
        return {
            "schema_version": 1,
            "valid": valid,
            "checkpoint": str(self.root),
            "claims": self.claims,
            "proof_graph": graph,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def _proof_graph(self) -> dict[str, list[dict[str, Any]]]:
        repository = self._repository.get("repository", {})
        runtime = self._repository.get("runtime", {})
        checkpoint_id = f"checkpoint:sha256:{self._manifest_digest}"
        commit_id = f"commit:{self._completion['HEAD']}"
        tree_id = f"tree:{self._completion['TREE']}"
        image_id = f"image:{self._completion['IMAGE_ID']}"
        nodes = [
            {
                "id": checkpoint_id,
                "type": "checkpoint",
                "claims": {
                    "class": self._completion["CHECKPOINT_CLASS"],
                    "release_verified": self._repository.get("release_verified"),
                    "generated_at": self._completion["GENERATED_AT"],
                },
            },
            {
                "id": commit_id,
                "type": "git_commit",
                "claims": {
                    "branch": self._completion["BRANCH"],
                    "parent": self._completion["PARENT"],
                    "subject": repository.get("subject"),
                },
            },
            {
                "id": tree_id,
                "type": "source_tree",
                "claims": {"tracked_files": repository.get("tracked_files")},
            },
            {
                "id": image_id,
                "type": "container_image",
                "claims": {
                    "name": runtime.get("image"),
                    "platform": runtime.get("platform"),
                    "healthcheck": runtime.get("docker_healthcheck"),
                    "smoke": runtime.get("product_image_smoke"),
                },
            },
        ]
        edges = [
            {"from": checkpoint_id, "relation": "attests", "to": commit_id},
            {"from": checkpoint_id, "relation": "attests", "to": tree_id},
            {"from": checkpoint_id, "relation": "attests", "to": image_id},
            {"from": commit_id, "relation": "has_tree", "to": tree_id},
            {"from": image_id, "relation": "built_from", "to": commit_id},
        ]
        return {"nodes": nodes, "edges": edges}

    def _safe_regular_file(self, relative_path: str) -> Path:
        parts = _safe_relative_parts(relative_path)
        current = self.root
        for index, part in enumerate(parts):
            current = current / part
            try:
                current_stat = os.lstat(current)
            except FileNotFoundError as exc:
                raise EvidenceVerificationError(
                    "evidence_file_missing",
                    "required evidence file is missing",
                    path=relative_path,
                ) from exc
            if stat.S_ISLNK(current_stat.st_mode):
                raise EvidenceVerificationError(
                    "evidence_symlink",
                    "evidence paths must not contain symlinks",
                    path=relative_path,
                )
            is_last = index == len(parts) - 1
            if not is_last and not stat.S_ISDIR(current_stat.st_mode):
                raise EvidenceVerificationError(
                    "evidence_parent_not_directory",
                    "evidence parent component is not a directory",
                    path=relative_path,
                )
            if is_last and not stat.S_ISREG(current_stat.st_mode):
                raise EvidenceVerificationError(
                    "evidence_not_regular_file",
                    "evidence target must be a regular file",
                    path=relative_path,
                )
        return current

    def _list_regular_files(self, root: Path) -> set[str]:
        try:
            root_stat = os.lstat(root)
        except FileNotFoundError as exc:
            raise EvidenceVerificationError(
                "evidence_directory_missing",
                "required evidence directory is missing",
                path=str(root),
            ) from exc
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise EvidenceVerificationError(
                "evidence_directory_invalid",
                "evidence directory must be a real directory",
                path=str(root),
            )

        files: set[str] = set()
        for directory, directory_names, file_names in os.walk(root, followlinks=False):
            directory_path = Path(directory)
            for name in directory_names:
                candidate = directory_path / name
                candidate_stat = os.lstat(candidate)
                if stat.S_ISLNK(candidate_stat.st_mode):
                    raise EvidenceVerificationError(
                        "evidence_symlink",
                        "checkpoint directories must not contain symlinks",
                        path=candidate.relative_to(self.root).as_posix(),
                    )
                if not stat.S_ISDIR(candidate_stat.st_mode):
                    raise EvidenceVerificationError(
                        "evidence_special_directory_entry",
                        "checkpoint directory entry is not a directory",
                        path=candidate.relative_to(self.root).as_posix(),
                    )
            for name in file_names:
                candidate = directory_path / name
                candidate_stat = os.lstat(candidate)
                if stat.S_ISLNK(candidate_stat.st_mode) or not stat.S_ISREG(candidate_stat.st_mode):
                    raise EvidenceVerificationError(
                        "evidence_special_file",
                        "checkpoint payloads must be regular files",
                        path=candidate.relative_to(self.root).as_posix(),
                    )
                files.add(candidate.relative_to(root).as_posix())
        return files

    def _parse_manifest(self, path: Path) -> dict[str, str]:
        entries: list[ManifestEntry] = []
        seen: set[str] = set()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = _MANIFEST_PATTERN.fullmatch(line)
            if match is None:
                raise EvidenceVerificationError(
                    "manifest_line_invalid",
                    f"invalid SHA256SUMS line {line_number}",
                    path=str(path.relative_to(self.root)),
                )
            digest, relative_path = match.groups()
            normalized = PurePosixPath(*_safe_relative_parts(relative_path)).as_posix()
            if normalized in seen:
                raise EvidenceVerificationError(
                    "manifest_duplicate_path",
                    f"duplicate manifest path: {normalized}",
                    path=str(path.relative_to(self.root)),
                )
            seen.add(normalized)
            entries.append(ManifestEntry(digest=digest, relative_path=normalized))
        if not entries:
            raise EvidenceVerificationError(
                "manifest_empty",
                "SHA256SUMS must not be empty",
                path=str(path.relative_to(self.root)),
            )
        paths = [entry.relative_path for entry in entries]
        if paths != sorted(paths):
            raise EvidenceVerificationError(
                "manifest_not_sorted",
                "SHA256SUMS paths must be sorted",
                path=str(path.relative_to(self.root)),
            )
        return {entry.relative_path: entry.digest for entry in entries}


def verify_checkpoint(checkpoint: str | Path) -> dict[str, Any]:
    """Verify one local checkpoint without changing it or any product runtime state."""

    return CheckpointEvidenceVerifier(Path(checkpoint)).verify()


def render_report(report: dict[str, Any], *, canonical: bool = False) -> str:
    """Render a verifier report in stable canonical or human-readable JSON form."""

    if canonical:
        return canonical_json(report)
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)


def _safe_relative_parts(relative_path: str) -> tuple[str, ...]:
    if not relative_path or "\x00" in relative_path or "\\" in relative_path:
        raise EvidenceVerificationError(
            "unsafe_relative_path",
            "evidence paths must be non-empty POSIX relative paths",
            path=relative_path,
        )
    pure = PurePosixPath(relative_path)
    parts = pure.parts
    if pure.is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
        raise EvidenceVerificationError(
            "unsafe_relative_path",
            "absolute paths and traversal components are prohibited",
            path=relative_path,
        )
    return parts


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return _sha256_stream(stream)


def _sha256_stream(stream: Any) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _parse_key_value_file(
    path: Path,
    *,
    stop_at: str | None = None,
    ignore_non_key_lines: bool = False,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if stop_at is not None and line == stop_at:
            break
        if not line:
            continue
        key, separator, value = line.partition("=")
        if not separator:
            if ignore_non_key_lines:
                continue
            raise EvidenceVerificationError(
                "key_value_line_invalid",
                f"invalid key-value line {line_number}",
                path=str(path),
            )
        if not key or key in values:
            raise EvidenceVerificationError(
                "key_value_line_invalid",
                f"invalid or duplicate key-value line {line_number}",
                path=str(path),
            )
        values[key] = value
    return values


def _parse_utc_timestamp(value: str, *, path: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceVerificationError(
            "invalid_timestamp",
            f"invalid ISO-8601 timestamp: {value}",
            path=path,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise EvidenceVerificationError(
            "invalid_timestamp_timezone",
            "timestamp must be UTC and timezone-aware",
            path=path,
        )
    return parsed


def _yes_no_to_bool(value: str) -> bool:
    if value == "YES":
        return True
    if value == "NO":
        return False
    raise EvidenceVerificationError(
        "invalid_yes_no",
        f"expected YES or NO, got {value}",
    )


def _require_mapping_values(
    mapping: dict[str, Any], expected: dict[str, object], *, path: str
) -> None:
    for key, value in expected.items():
        if mapping.get(key) != value:
            raise EvidenceVerificationError(
                "provenance_mismatch",
                f"{key} does not match the authoritative completion marker",
                path=path,
            )


def _run_git(
    git: str,
    arguments: list[str],
    *,
    cwd: Path,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    return subprocess.run(
        [git, *arguments],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=text,
        timeout=60,
    )


def _git_value(git: str, bare: Path, arguments: list[str]) -> str:
    result = _run_git(git, ["-C", str(bare), *arguments], cwd=bare.parent)
    if result.returncode != 0:
        raise EvidenceVerificationError(
            "git_command_failed",
            result.stderr.strip() or result.stdout.strip(),
        )
    return result.stdout.strip()


def _parse_git_tree(raw: bytes) -> list[tuple[str, str, str, str]]:
    entries: list[tuple[str, str, str, str]] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        metadata, separator, raw_path = item.partition(b"\t")
        if not separator:
            raise EvidenceVerificationError("git_tree_invalid", "invalid git ls-tree output")
        try:
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            relative_path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise EvidenceVerificationError("git_tree_invalid", "invalid git tree entry") from exc
        normalized = PurePosixPath(*_safe_relative_parts(relative_path)).as_posix()
        entries.append((mode, object_type, object_id, normalized))
    return entries


def _git_blob_id(payload: bytes, object_format: str) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    if object_format == "sha1":
        return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()
    if object_format == "sha256":
        return hashlib.sha256(header + payload).hexdigest()
    raise EvidenceVerificationError(
        "unsupported_git_object_format",
        f"unsupported Git object format: {object_format}",
    )
