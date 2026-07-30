from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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


def configure_adversarial_tag_fetch(repo: Path) -> None:
    for key, value in (
        ("remote.origin.tagOpt", "--tags"),
        ("remote.origin.prune", "true"),
        ("remote.origin.pruneTags", "true"),
        ("fetch.prune", "true"),
        ("fetch.pruneTags", "true"),
    ):
        run("git", "config", key, value, cwd=repo)
    run(
        "git",
        "config",
        "--add",
        "remote.origin.fetch",
        "+refs/tags/*:refs/tags/*",
        cwd=repo,
    )


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


def test_freshness_fetch_protects_complete_tag_set_under_adversarial_configuration(
    tmp_path: Path,
) -> None:
    repo, remote, head = create_repository(tmp_path)
    control = tmp_path / "generic-fetch-control"
    run(
        "git",
        "clone",
        "--no-tags",
        "--branch",
        "main",
        str(remote),
        str(control),
        cwd=tmp_path,
    )

    for candidate in (repo, control):
        candidate_head = run("git", "rev-parse", "HEAD", cwd=candidate).stdout.strip()
        run("git", "tag", "local-only", candidate_head, cwd=candidate)
        run("git", "tag", "same-name", candidate_head, cwd=candidate)
        configure_adversarial_tag_fetch(candidate)

    producer = tmp_path / "producer"
    run("git", "clone", "--no-tags", "--branch", "main", str(remote), str(producer), cwd=tmp_path)
    run("git", "config", "user.name", "VOODOO Test", cwd=producer)
    run("git", "config", "user.email", "voodoo-test@example.invalid", cwd=producer)
    remote_head = commit(producer, "feat: remote freshness", "remote.txt", "remote\n")
    run("git", "tag", "remote-only", remote_head, cwd=producer)
    run("git", "tag", "same-name", remote_head, cwd=producer)
    run(
        "git",
        "push",
        "origin",
        "main",
        "refs/tags/remote-only",
        "refs/tags/same-name",
        cwd=producer,
    )

    origin_main_before = run("git", "rev-parse", "origin/main", cwd=repo).stdout.strip()
    same_name_before = run("git", "rev-parse", "refs/tags/same-name", cwd=repo).stdout.strip()
    local_only_before = run("git", "rev-parse", "refs/tags/local-only", cwd=repo).stdout.strip()
    assert same_name_before == head
    assert local_only_before == head
    assert remote_head != same_name_before
    missing_remote_commit = subprocess.run(
        ("git", "cat-file", "-e", f"{remote_head}^{{commit}}"),
        cwd=repo,
        check=False,
        text=True,
        capture_output=True,
    )
    assert missing_remote_commit.returncode != 0
    tags_before = tag_refs(repo)
    assert "refs/tags/remote-only" not in tags_before

    MODULE.fetch_origin_base(repo, "origin/main")

    tags_after = tag_refs(repo)
    same_name_after = run("git", "rev-parse", "refs/tags/same-name", cwd=repo).stdout.strip()
    local_only_after = run("git", "rev-parse", "refs/tags/local-only", cwd=repo).stdout.strip()
    origin_main_after = run("git", "rev-parse", "origin/main", cwd=repo).stdout.strip()
    assert tags_after == tags_before
    assert "refs/tags/remote-only" not in tags_after
    assert same_name_after == same_name_before
    assert local_only_after == local_only_before
    assert origin_main_after == remote_head

    control_tags_before = tag_refs(control)
    run("git", "fetch", "--prune", "origin", cwd=control)
    control_tags_after = tag_refs(control)
    assert control_tags_after != control_tags_before
    assert f"refs/tags/remote-only {remote_head}\n" in control_tags_after
    assert f"refs/tags/same-name {remote_head}\n" in control_tags_after
    assert "refs/tags/local-only" not in control_tags_after

    print("TAG_CREATE_PROTECTED remote-only=absent/absent")
    print(f"TAG_MOVE_PROTECTED same-name={same_name_before}/{same_name_after}")
    print(f"TAG_DELETE_PROTECTED local-only={local_only_before}/{local_only_after}")
    print(f"TAG_SET_IDENTICAL before={tags_before!r} after={tags_after!r}")
    print(f"ORIGIN_MAIN_REFRESHED before={origin_main_before} after={origin_main_after}")
    print(f"NEGATIVE_CONTROL before={control_tags_before!r} after={control_tags_after!r}")


@pytest.mark.parametrize(
    "base_ref",
    (
        "origin/release",
        "main",
        "refs/heads/main",
        "origin/main^{commit}",
        "origin/main~1",
        "",
    ),
)
def test_freshness_fetch_rejects_unsupported_base_ref(
    tmp_path: Path,
    base_ref: str,
) -> None:
    repo, _, _ = create_repository(tmp_path)

    with pytest.raises(MODULE.PublicationError, match="unsupported --base-ref"):
        MODULE.fetch_origin_base(repo, base_ref)


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
    evidence_root = tmp_path / "evidence-root"
    evidence, sidecar = MODULE.write_evidence(
        evidence_root / "task",
        payload,
        evidence_root=evidence_root,
    )

    expected = sidecar.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(evidence.read_bytes()).hexdigest()
    assert expected == actual
    assert evidence.stat().st_mode & 0o777 == 0o600
    assert sidecar.stat().st_mode & 0o777 == 0o600


def test_evidence_dir_is_required() -> None:
    with pytest.raises(SystemExit) as exc:
        MODULE.parse_args(
            [
                "--expected-head",
                "a" * 40,
                "--expected-commit-count",
                "2",
                "--target-branch",
                "review/test",
            ]
        )

    assert exc.value.code == 2


def test_evidence_path_contract_accepts_canonical_descendants(tmp_path: Path) -> None:
    evidence_root = tmp_path / "V-ONE-EVIDENCE"

    assert MODULE.validate_evidence_dir(
        evidence_root,
        evidence_root=evidence_root,
    ) == evidence_root.resolve()
    assert MODULE.validate_evidence_dir(
        evidence_root / "ordinary",
        evidence_root=evidence_root,
    ) == (evidence_root / "ordinary").resolve()
    task_dir = evidence_root / "CODEX" / "REVIEW_PUBLICATION_20260730T120000Z"
    assert MODULE.validate_evidence_dir(
        task_dir,
        evidence_root=evidence_root,
    ) == task_dir.resolve()


def test_evidence_path_contract_rejects_escapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_root = tmp_path / "V-ONE-EVIDENCE"
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    invalid_paths = (
        Path("/tmp/publication-evidence"),  # noqa: S108 - intentional rejection case
        Path("~/Downloads/voodoo-review-publication-evidence"),
        tmp_path / "V-ONE",
        tmp_path / "V-ONE-EVIDENCE-EVIL",
        evidence_root / ".." / "outside",
    )

    for invalid in invalid_paths:
        with pytest.raises(MODULE.PublicationError, match="canonical durable evidence root"):
            MODULE.validate_evidence_dir(invalid, evidence_root=evidence_root)


def test_evidence_path_contract_rejects_symlink_escape(tmp_path: Path) -> None:
    evidence_root = tmp_path / "V-ONE-EVIDENCE"
    evidence_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = evidence_root / "escaped-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(MODULE.PublicationError, match="canonical durable evidence root"):
        MODULE.validate_evidence_dir(link / "task", evidence_root=evidence_root)


def test_write_evidence_rejects_legacy_default_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_root = tmp_path / "V-ONE-EVIDENCE"
    home = tmp_path / "home"
    legacy = home / "Downloads" / "voodoo-review-publication-evidence"
    monkeypatch.setenv("HOME", str(home))
    payload = {
        "timestamp_utc": "2026-07-30T12:00:00+00:00",
        "status": "BLOCKED",
    }

    with pytest.raises(MODULE.PublicationError, match="canonical durable evidence root"):
        MODULE.write_evidence(
            Path("~/Downloads/voodoo-review-publication-evidence"),
            payload,
            evidence_root=evidence_root,
        )

    assert not legacy.exists()


def _main_args(evidence_dir: Path) -> list[str]:
    return [
        "--expected-head",
        "a" * 40,
        "--expected-commit-count",
        "2",
        "--target-branch",
        "review/test",
        "--evidence-dir",
        str(evidence_dir),
    ]


def _stub_plan(evidence_root: Path, monkeypatch: pytest.MonkeyPatch) -> object:
    plan = MODULE.PublicationPlan(
        repo_root=str(evidence_root),
        head="a" * 40,
        base_ref="origin/main",
        origin_fetch_url=MODULE.ALLOWED_GITHUB_REPOSITORY,
        repository_url=MODULE.ALLOWED_GITHUB_REPOSITORY,
        target_branch="review/test",
        target_ref="refs/heads/review/test",
        commit_count=2,
        merge_commit_count=0,
        diff_shortstat="2 files changed",
        changed_file_count=2,
        approval="PUBLISH_REVIEW exact",
    )
    monkeypatch.setattr(MODULE, "build_plan", lambda **_: plan)
    monkeypatch.setattr(
        MODULE,
        "dry_run_publication",
        lambda _: SimpleNamespace(stdout="dry run", stderr=""),
    )
    return plan


def test_outside_root_is_blocked_before_plan_or_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence_root = tmp_path / "V-ONE-EVIDENCE"
    outside = tmp_path / "outside"
    monkeypatch.setattr(MODULE, "CANONICAL_EVIDENCE_ROOT", evidence_root)

    def unexpected_plan(**_: object) -> None:
        pytest.fail("build_plan reached before evidence path validation")

    monkeypatch.setattr(MODULE, "build_plan", unexpected_plan)

    assert MODULE.main(_main_args(outside)) == 2
    captured = capsys.readouterr()
    assert "PUBLICATION_STATUS=BLOCKED" in captured.err
    assert not outside.exists()


def test_valid_plan_writes_evidence_inside_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence_root = tmp_path / "V-ONE-EVIDENCE"
    task_dir = evidence_root / "CODEX" / "REVIEW_PUBLICATION_20260730T120000Z"
    monkeypatch.setattr(MODULE, "CANONICAL_EVIDENCE_ROOT", evidence_root)
    _stub_plan(evidence_root, monkeypatch)

    assert MODULE.main(_main_args(task_dir)) == 0
    captured = capsys.readouterr()
    assert "PUBLICATION_STATUS=VERIFIED_PLAN" in captured.out
    evidence_files = list(task_dir.glob("*.json"))
    sidecars = list(task_dir.glob("*.json.sha256"))
    assert len(evidence_files) == 1
    assert len(sidecars) == 1
    assert evidence_files[0].is_relative_to(evidence_root)
    assert sidecars[0].is_relative_to(evidence_root)


def test_publication_error_writes_blocked_evidence_inside_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence_root = tmp_path / "V-ONE-EVIDENCE"
    task_dir = evidence_root / "CODEX" / "REVIEW_PUBLICATION_FAILURE"
    monkeypatch.setattr(MODULE, "CANONICAL_EVIDENCE_ROOT", evidence_root)

    def fail_after_validation(**_: object) -> None:
        raise MODULE.PublicationError("deliberate failure")

    monkeypatch.setattr(MODULE, "build_plan", fail_after_validation)

    assert MODULE.main(_main_args(task_dir)) == 2
    captured = capsys.readouterr()
    assert "PUBLICATION_STATUS=BLOCKED" in captured.err
    evidence_files = list(task_dir.glob("*.json"))
    sidecars = list(task_dir.glob("*.json.sha256"))
    assert len(evidence_files) == 1
    assert len(sidecars) == 1
    assert '"status": "BLOCKED"' in evidence_files[0].read_text(encoding="utf-8")
    assert evidence_files[0].is_relative_to(evidence_root)
    assert sidecars[0].is_relative_to(evidence_root)
