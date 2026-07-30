#!/usr/bin/env python3
"""Governed publication of a verified local HEAD to a new GitHub review branch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ALLOWED_GITHUB_REPOSITORY = "https://github.com/nulleimy/V-One.git"
DEFAULT_BASE_REF = "origin/main"
DEFAULT_BASE_FETCH_REFSPEC = "+refs/heads/main:refs/remotes/origin/main"
TARGET_PREFIX = "review/"
PROTECTED_BRANCHES = frozenset({"main", "master", "trunk", "develop", "production"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PublicationError(RuntimeError):
    """Raised when a publication precondition is not satisfied."""


@dataclass(frozen=True)
class PublicationPolicy:
    allowed_repository_url: str = ALLOWED_GITHUB_REPOSITORY
    target_prefix: str = TARGET_PREFIX
    protected_branches: frozenset[str] = PROTECTED_BRANCHES

    def validate_repository_url(self, repository_url: str) -> None:
        if repository_url != self.allowed_repository_url:
            raise PublicationError(
                "repository URL is not allowlisted: "
                f"expected={self.allowed_repository_url!r} actual={repository_url!r}"
            )

    def validate_target_branch(self, target_branch: str) -> None:
        if target_branch in self.protected_branches:
            raise PublicationError(f"protected branch is forbidden: {target_branch}")
        if not target_branch.startswith(self.target_prefix):
            raise PublicationError(
                f"target branch must start with {self.target_prefix!r}: {target_branch!r}"
            )
        if len(target_branch) > 160:
            raise PublicationError("target branch is too long")
        forbidden = ("..", "@{", "\\", " ", "~", "^", ":", "?", "*", "[")
        if target_branch.endswith(("/", ".")) or any(token in target_branch for token in forbidden):
            raise PublicationError(f"target branch contains an invalid Git ref pattern: {target_branch!r}")


@dataclass(frozen=True)
class PublicationPlan:
    repo_root: str
    head: str
    base_ref: str
    origin_fetch_url: str
    repository_url: str
    target_branch: str
    target_ref: str
    commit_count: int
    merge_commit_count: int
    diff_shortstat: str
    changed_file_count: int
    approval: str


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    result = subprocess.run(
        list(args),
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        command = " ".join(args)
        detail = (result.stderr or result.stdout).strip()
        raise PublicationError(f"command failed ({result.returncode}): {command}\n{detail}")
    return result


def git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(("git", *args), cwd=repo_root, check=check)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256_manifest(repo_root: Path, manifest_name: str) -> str:
    manifest_path = repo_root / manifest_name
    if not manifest_path.is_file():
        raise PublicationError(f"required SHA-256 manifest is missing: {manifest_name}")

    fields = manifest_path.read_text(encoding="utf-8").strip().split()
    if len(fields) < 2 or not SHA256_RE.fullmatch(fields[0]):
        raise PublicationError(f"invalid SHA-256 manifest format: {manifest_name}")

    expected = fields[0]
    target_name = fields[-1].removeprefix("*")
    target_path = repo_root / target_name
    if not target_path.is_file():
        raise PublicationError(f"SHA-256 target is missing: {target_name}")

    actual = sha256_file(target_path)
    if actual != expected:
        raise PublicationError(
            f"SHA-256 mismatch for {target_name}: expected={expected} actual={actual}"
        )
    return actual


def expected_approval(plan: PublicationPlan) -> str:
    return (
        "PUBLISH_REVIEW "
        f"HEAD={plan.head} "
        f"REPOSITORY={plan.repository_url} "
        f"BRANCH={plan.target_branch} "
        f"COMMITS={plan.commit_count}"
    )


def _validate_expected_head(expected_head: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise PublicationError("--expected-head must be a full lowercase 40-character Git SHA")


def fetch_origin_base(repo_root: Path, base_ref: str) -> None:
    if base_ref != DEFAULT_BASE_REF:
        raise PublicationError(
            f"unsupported --base-ref: expected={DEFAULT_BASE_REF!r} actual={base_ref!r}"
        )
    git(repo_root, "fetch", "--no-tags", "origin", DEFAULT_BASE_FETCH_REFSPEC)


def build_plan(
    *,
    repo_root: Path,
    expected_head: str,
    repository_url: str,
    target_branch: str,
    base_ref: str,
    expected_commit_count: int,
    policy: PublicationPolicy,
    fetch_origin: bool = True,
) -> PublicationPlan:
    repo_root = repo_root.resolve()
    _validate_expected_head(expected_head)
    policy.validate_repository_url(repository_url)
    policy.validate_target_branch(target_branch)

    actual_root = Path(git(repo_root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if actual_root != repo_root:
        raise PublicationError(f"working directory is not the repository root: {actual_root}")

    status = git(repo_root, "status", "--porcelain=v1", "--untracked-files=all").stdout
    if status:
        raise PublicationError(f"worktree is not clean:\n{status.rstrip()}")

    head = git(repo_root, "rev-parse", "HEAD").stdout.strip()
    if head != expected_head:
        raise PublicationError(f"unexpected HEAD: expected={expected_head} actual={head}")

    verify_sha256_manifest(
        repo_root, "WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md.sha256"
    )
    verify_sha256_manifest(
        repo_root, "VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md.sha256"
    )

    origin_fetch_url = git(repo_root, "remote", "get-url", "origin").stdout.strip()
    if origin_fetch_url != repository_url:
        raise PublicationError(
            "origin fetch URL does not match the allowlisted publication repository: "
            f"origin={origin_fetch_url!r} publication={repository_url!r}"
        )

    if fetch_origin:
        fetch_origin_base(repo_root, base_ref)

    git(repo_root, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    ancestor = git(repo_root, "merge-base", "--is-ancestor", base_ref, "HEAD", check=False)
    if ancestor.returncode != 0:
        raise PublicationError(f"HEAD is not based on {base_ref}")

    commit_count = int(git(repo_root, "rev-list", "--count", f"{base_ref}..HEAD").stdout)
    if commit_count != expected_commit_count:
        raise PublicationError(
            "unexpected publication commit count: "
            f"expected={expected_commit_count} actual={commit_count}"
        )

    merge_commit_count = int(
        git(repo_root, "rev-list", "--count", "--merges", f"{base_ref}..HEAD").stdout
    )
    if merge_commit_count != 0:
        raise PublicationError(
            f"publication range contains merge commits: {merge_commit_count}"
        )

    git(repo_root, "diff", "--check", f"{base_ref}..HEAD")
    git(repo_root, "check-ref-format", "--branch", target_branch)

    target_ref = f"refs/heads/{target_branch}"
    collision = run_command(
        ("git", "ls-remote", "--heads", repository_url, target_ref),
        cwd=repo_root,
    ).stdout.strip()
    if collision:
        raise PublicationError(f"remote target branch already exists: {target_ref}")

    diff_shortstat = git(repo_root, "diff", "--shortstat", f"{base_ref}..HEAD").stdout.strip()
    changed_files = git(repo_root, "diff", "--name-only", f"{base_ref}..HEAD").stdout
    changed_file_count = len([line for line in changed_files.splitlines() if line])

    provisional = PublicationPlan(
        repo_root=str(repo_root),
        head=head,
        base_ref=base_ref,
        origin_fetch_url=origin_fetch_url,
        repository_url=repository_url,
        target_branch=target_branch,
        target_ref=target_ref,
        commit_count=commit_count,
        merge_commit_count=merge_commit_count,
        diff_shortstat=diff_shortstat,
        changed_file_count=changed_file_count,
        approval="",
    )
    return PublicationPlan(**{**asdict(provisional), "approval": expected_approval(provisional)})


def dry_run_publication(plan: PublicationPlan) -> subprocess.CompletedProcess[str]:
    return run_command(
        (
            "git",
            "push",
            "--dry-run",
            "--no-verify",
            plan.repository_url,
            f"HEAD:{plan.target_ref}",
        ),
        cwd=Path(plan.repo_root),
    )


def execute_publication(
    plan: PublicationPlan,
    *,
    approval: str,
) -> tuple[subprocess.CompletedProcess[str], str]:
    if approval != plan.approval:
        raise PublicationError("explicit publication approval does not exactly match the verified plan")

    push = run_command(
        (
            "git",
            "push",
            "--no-verify",
            plan.repository_url,
            f"HEAD:{plan.target_ref}",
        ),
        cwd=Path(plan.repo_root),
    )
    remote = run_command(
        ("git", "ls-remote", "--heads", plan.repository_url, plan.target_ref),
        cwd=Path(plan.repo_root),
    ).stdout.strip()
    if not remote:
        raise PublicationError("remote branch verification returned no result after push")
    remote_sha = remote.split()[0]
    if remote_sha != plan.head:
        raise PublicationError(
            f"remote branch SHA mismatch after push: expected={plan.head} actual={remote_sha}"
        )
    return push, remote_sha


def write_evidence(evidence_dir: Path, payload: dict[str, object]) -> tuple[Path, Path]:
    evidence_dir = evidence_dir.expanduser().resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(evidence_dir, 0o700)

    timestamp = str(payload["timestamp_utc"]).replace(":", "").replace("-", "")
    head = str(payload.get("head", "unknown"))[:12]
    target = evidence_dir / f"review-publication-{timestamp}-{head}.json"
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=evidence_dir,
        prefix=".review-publication-",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    os.chmod(target, 0o600)

    digest = sha256_file(target)
    sidecar = target.with_suffix(target.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    os.chmod(sidecar, 0o600)
    return target, sidecar


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify and optionally publish the current immutable HEAD to a new GitHub review "
            "branch without changing Git remotes, hooks, main, tags, or release state."
        )
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--expected-commit-count", required=True, type=int)
    parser.add_argument(
        "--base-ref",
        default=DEFAULT_BASE_REF,
        help=f"publication base ref; currently only {DEFAULT_BASE_REF!r} is supported",
    )
    parser.add_argument("--repository-url", default=ALLOWED_GITHUB_REPOSITORY)
    parser.add_argument(
        "--evidence-dir",
        default="~/Downloads/voodoo-review-publication-evidence",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    evidence: dict[str, object] = {
        "schema_version": 1,
        "timestamp_utc": timestamp,
        "mode": "execute" if args.execute else "plan",
        "status": "BLOCKED",
    }

    try:
        plan = build_plan(
            repo_root=Path.cwd(),
            expected_head=args.expected_head,
            repository_url=args.repository_url,
            target_branch=args.target_branch,
            base_ref=args.base_ref,
            expected_commit_count=args.expected_commit_count,
            policy=PublicationPolicy(),
        )
        evidence.update(asdict(plan))

        dry_run = dry_run_publication(plan)
        evidence["dry_run_stdout"] = dry_run.stdout.strip()
        evidence["dry_run_stderr"] = dry_run.stderr.strip()

        if not args.execute:
            evidence["status"] = "VERIFIED_PLAN"
            evidence_path, sha_path = write_evidence(Path(args.evidence_dir), evidence)
            print("PUBLICATION_STATUS=VERIFIED_PLAN")
            print(f"HEAD={plan.head}")
            print(f"COMMITS={plan.commit_count}")
            print(f"MERGE_COMMITS={plan.merge_commit_count}")
            print(f"CHANGED_FILES={plan.changed_file_count}")
            print(f"DIFF_SHORTSTAT={plan.diff_shortstat}")
            print(f"TARGET={plan.repository_url}#{plan.target_branch}")
            print(f"REQUIRED_APPROVAL={plan.approval}")
            print(f"EVIDENCE_FILE={evidence_path}")
            print(f"EVIDENCE_SHA256_FILE={sha_path}")
            return 0

        if not args.approval:
            raise PublicationError("--execute requires --approval with the exact verified plan string")

        push, remote_sha = execute_publication(plan, approval=args.approval)
        evidence["push_stdout"] = push.stdout.strip()
        evidence["push_stderr"] = push.stderr.strip()
        evidence["remote_sha"] = remote_sha
        evidence["status"] = "IMPLEMENTED_VERIFIED_REMOTE_BRANCH"
        evidence_path, sha_path = write_evidence(Path(args.evidence_dir), evidence)

        print("PUBLICATION_STATUS=IMPLEMENTED_VERIFIED_REMOTE_BRANCH")
        print(f"REMOTE_SHA={remote_sha}")
        print(f"TARGET={plan.repository_url}#{plan.target_branch}")
        print(f"EVIDENCE_FILE={evidence_path}")
        print(f"EVIDENCE_SHA256_FILE={sha_path}")
        return 0
    except PublicationError as exc:
        evidence["error"] = str(exc)
        try:
            evidence_path, sha_path = write_evidence(Path(args.evidence_dir), evidence)
            print(f"EVIDENCE_FILE={evidence_path}", file=sys.stderr)
            print(f"EVIDENCE_SHA256_FILE={sha_path}", file=sys.stderr)
        except OSError as evidence_error:
            print(f"EVIDENCE_WRITE_ERROR={evidence_error}", file=sys.stderr)
        print("PUBLICATION_STATUS=BLOCKED", file=sys.stderr)
        print(f"BLOCK_REASON={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
