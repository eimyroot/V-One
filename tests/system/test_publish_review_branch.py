from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "publish_review_branch.py"
SPEC = importlib.util.spec_from_file_location("publish_review_branch", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)


def commit(repo: Path, message: str, filename: str, content: str) -> str:
    (repo / filename).write_text(content, encoding="utf-8")
    run("git", "add", filename, cwd=repo)
    run("git", "commit", "-m", message, cwd=repo)
    return run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()


def write_manifest(repo: Path, filename: str, content: str) -> None:
    target = repo / filename
    target.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (repo / f"{filename}.sha256").write_text(f"{digest}  {filename}\n", encoding="utf-8")


def create_repository(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    run("git", "init", "-b", "main", cwd=repo)
    run("git", "config", "user.name", "VOODOO Test", cwd=repo)
    run("git", "config", "user.email", "voodoo-test@example.invalid", cwd=repo)

    write_manifest(repo, "WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md", "technical\n")
    write_manifest(
        repo,
        "VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md",
        "product\n",
    )
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", "docs: add constitutions", cwd=repo)

    run("git", "init", "--bare", str(remote), cwd=tmp_path)
    run("git", "remote", "add", "origin", str(remote), cwd=repo)
    run("git", "push", "-u", "origin", "main", cwd=repo)

    commit(repo, "feat: first", "one.txt", "one\n")
    head = commit(repo, "feat: second", "two.txt", "two\n")
    return repo, remote, head


def tag_refs(repo: Path) -> str:
    return run(
        "git",
        "for-each-ref",
        "--format=%(refname) %(objectname)",
        "refs/tags/",
        cwd=repo,
    ).stdout


def test_policy_accepts_only_review_branches() -> None:
    policy = MODULE.PublicationPolicy()
    policy.validate_repository_url(MODULE.ALLOWED_GITHUB_REPOSITORY)
    policy.validate_target_branch("review/admin-session-revocation-v1")

    with pytest.raises(MODULE.PublicationError, match="not allowlisted"):
        policy.validate_repository_url("https://example.invalid/not-allowed.git")

    for invalid in ("main", "local/test", "review/", "review/bad branch", "review/a..b"):
        with pytest.raises(MODULE.PublicationError):
            policy.validate_target_branch(invalid)


def test_manifest_verification_detects_drift(tmp_path: Path) -> None:
    target = tmp_path / "doc.md"
    target.write_text("original\n", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (tmp_path / "doc.md.sha256").write_text(f"{digest}  doc.md\n", encoding="utf-8")

    assert MODULE.verify_sha256_manifest(tmp_path, "doc.md.sha256") == digest
    target.write_text("changed\n", encoding="utf-8")
    with pytest.raises(MODULE.PublicationError, match="SHA-256 mismatch"):
        MODULE.verify_sha256_manifest(tmp_path, "doc.md.sha256")


def test_plan_dry_run_and_execute_are_fail_closed(tmp_path: Path) -> None:
    repo, remote, head = create_repository(tmp_path)
    policy = MODULE.PublicationPolicy(allowed_repository_url=str(remote))
    plan = MODULE.build_plan(
        repo_root=repo,
        expected_head=head,
        repository_url=str(remote),
        target_branch="review/test-publication",
        base_ref="origin/main",
        expected_commit_count=2,
        policy=policy,
        fetch_origin=True,
    )

    assert plan.commit_count == 2
    assert plan.merge_commit_count == 0
    assert plan.changed_file_count == 2
    assert plan.approval.startswith(f"PUBLISH_REVIEW HEAD={head} ")

    MODULE.dry_run_publication(plan)
    absent = run(
        "git",
        "ls-remote",
        "--heads",
        str(remote),
        "refs/heads/review/test-publication",
        cwd=repo,
    ).stdout
    assert absent == ""

    with pytest.raises(MODULE.PublicationError, match="approval"):
        MODULE.execute_publication(plan, approval="wrong")

    _, remote_sha = MODULE.execute_publication(plan, approval=plan.approval)
    assert remote_sha == head


def test_freshness_fetch_refreshes_main_without_auto_following_remote_tag(
    tmp_path: Path,
) -> None:
    repo, remote, _ = create_repository(tmp_path)
    producer = tmp_path / "producer"
    run("git", "clone", "--branch", "main", str(remote), str(producer), cwd=tmp_path)
    run("git", "config", "user.name", "VOODOO Test", cwd=producer)
    run("git", "config", "user.email", "voodoo-test@example.invalid", cwd=producer)
    remote_head = commit(producer, "feat: remote freshness", "remote.txt", "remote\n")
    run("git", "tag", "remote-history", remote_head, cwd=producer)
    run("git", "push", "origin", "main", "refs/tags/remote-history", cwd=producer)

    missing = subprocess.run(
        ("git", "cat-file", "-e", f"{remote_head}^{{commit}}"),
        cwd=repo,
        check=False,
        text=True,
        capture_output=True,
    )
    assert missing.returncode != 0
    before = tag_refs(repo)
    assert before == ""

    MODULE.fetch_origin_base(repo, "origin/main")

    assert run("git", "rev-parse", "origin/main", cwd=repo).stdout.strip() == remote_head
    after = tag_refs(repo)
    assert after == before


def test_freshness_fetch_preserves_tags_under_adversarial_tag_configuration(
    tmp_path: Path,
) -> None:
    repo, remote, head = create_repository(tmp_path)
    run("git", "tag", "local-only", head, cwd=repo)
    remote_main = run("git", "rev-parse", "origin/main", cwd=repo).stdout.strip()
    run("git", "--git-dir", str(remote), "tag", "remote-only", remote_main, cwd=tmp_path)
    run("git", "config", "remote.origin.tagOpt", "--tags", cwd=repo)
    run(
        "git",
        "config",
        "--add",
        "remote.origin.fetch",
        "+refs/tags/*:refs/tags/*",
        cwd=repo,
    )
    run("git", "config", "fetch.pruneTags", "true", cwd=repo)
    before = tag_refs(repo)

    MODULE.build_plan(
        repo_root=repo,
        expected_head=head,
        repository_url=str(remote),
        target_branch="review/tag-preservation",
        base_ref="origin/main",
        expected_commit_count=2,
        policy=MODULE.PublicationPolicy(allowed_repository_url=str(remote)),
        fetch_origin=True,
    )

    after = tag_refs(repo)
    assert before == f"refs/tags/local-only {head}\n"
    assert after == before
    assert "refs/tags/remote-only" not in after


def test_freshness_fetch_rejects_unsupported_base_ref(tmp_path: Path) -> None:
    repo, _, _ = create_repository(tmp_path)

    with pytest.raises(MODULE.PublicationError, match="unsupported --base-ref"):
        MODULE.fetch_origin_base(repo, "origin/release")


def test_plan_rejects_dirty_worktree_and_unexpected_head(tmp_path: Path) -> None:
    repo, remote, head = create_repository(tmp_path)
    policy = MODULE.PublicationPolicy(allowed_repository_url=str(remote))
    untracked = repo / "untracked.txt"
    untracked.write_text("untracked\n", encoding="utf-8")

    with pytest.raises(MODULE.PublicationError, match="worktree is not clean"):
        MODULE.build_plan(
            repo_root=repo,
            expected_head=head,
            repository_url=str(remote),
            target_branch="review/dirty",
            base_ref="origin/main",
            expected_commit_count=2,
            policy=policy,
        )

    untracked.unlink()
    with pytest.raises(MODULE.PublicationError, match="unexpected HEAD"):
        MODULE.build_plan(
            repo_root=repo,
            expected_head="a" * 40,
            repository_url=str(remote),
            target_branch="review/wrong-head",
            base_ref="origin/main",
            expected_commit_count=2,
            policy=policy,
        )


def test_plan_rejects_non_ancestor_base(tmp_path: Path) -> None:
    repo, remote, head = create_repository(tmp_path)
    producer = tmp_path / "divergent-producer"
    run("git", "clone", "--branch", "main", str(remote), str(producer), cwd=tmp_path)
    run("git", "config", "user.name", "VOODOO Test", cwd=producer)
    run("git", "config", "user.email", "voodoo-test@example.invalid", cwd=producer)
    commit(producer, "feat: divergent remote", "divergent.txt", "divergent\n")
    run("git", "push", "origin", "main", cwd=producer)

    with pytest.raises(MODULE.PublicationError, match="not based on origin/main"):
        MODULE.build_plan(
            repo_root=repo,
            expected_head=head,
            repository_url=str(remote),
            target_branch="review/non-ancestor",
            base_ref="origin/main",
            expected_commit_count=2,
            policy=MODULE.PublicationPolicy(allowed_repository_url=str(remote)),
        )


def test_plan_rejects_unexpected_commit_count(tmp_path: Path) -> None:
    repo, remote, head = create_repository(tmp_path)

    with pytest.raises(MODULE.PublicationError, match="unexpected publication commit count"):
        MODULE.build_plan(
            repo_root=repo,
            expected_head=head,
            repository_url=str(remote),
            target_branch="review/wrong-count",
            base_ref="origin/main",
            expected_commit_count=1,
            policy=MODULE.PublicationPolicy(allowed_repository_url=str(remote)),
        )


def test_plan_rejects_merge_commits(tmp_path: Path) -> None:
    repo, remote, _ = create_repository(tmp_path)
    run("git", "switch", "-c", "topic", "origin/main", cwd=repo)
    commit(repo, "feat: topic", "topic.txt", "topic\n")
    run("git", "switch", "main", cwd=repo)
    run("git", "merge", "--no-ff", "topic", "-m", "merge: topic", cwd=repo)
    head = run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
    commit_count = int(
        run("git", "rev-list", "--count", "origin/main..HEAD", cwd=repo).stdout
    )

    with pytest.raises(MODULE.PublicationError, match="contains merge commits"):
        MODULE.build_plan(
            repo_root=repo,
            expected_head=head,
            repository_url=str(remote),
            target_branch="review/merge",
            base_ref="origin/main",
            expected_commit_count=commit_count,
            policy=MODULE.PublicationPolicy(allowed_repository_url=str(remote)),
        )


def test_plan_rejects_diff_check_failures(tmp_path: Path) -> None:
    repo, remote, _ = create_repository(tmp_path)
    head = commit(repo, "feat: bad whitespace", "bad.txt", "trailing space \n")

    with pytest.raises(MODULE.PublicationError, match="git diff --check"):
        MODULE.build_plan(
            repo_root=repo,
            expected_head=head,
            repository_url=str(remote),
            target_branch="review/bad-whitespace",
            base_ref="origin/main",
            expected_commit_count=3,
            policy=MODULE.PublicationPolicy(allowed_repository_url=str(remote)),
        )


def test_existing_remote_branch_blocks_new_plan(tmp_path: Path) -> None:
    repo, remote, head = create_repository(tmp_path)
    run(
        "git",
        "push",
        str(remote),
        "HEAD:refs/heads/review/existing",
        cwd=repo,
    )
    policy = MODULE.PublicationPolicy(allowed_repository_url=str(remote))

    with pytest.raises(MODULE.PublicationError, match="already exists"):
        MODULE.build_plan(
            repo_root=repo,
            expected_head=head,
            repository_url=str(remote),
            target_branch="review/existing",
            base_ref="origin/main",
            expected_commit_count=2,
            policy=policy,
            fetch_origin=True,
        )


def test_evidence_is_atomic_and_hash_verifiable(tmp_path: Path) -> None:
    payload = {
        "timestamp_utc": "2026-07-26T05:00:00+00:00",
        "head": "a" * 40,
        "status": "VERIFIED_PLAN",
    }
    evidence, sidecar = MODULE.write_evidence(tmp_path / "evidence", payload)

    expected = sidecar.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(evidence.read_bytes()).hexdigest()
    assert expected == actual
    assert evidence.stat().st_mode & 0o777 == 0o600
    assert sidecar.stat().st_mode & 0o777 == 0o600
