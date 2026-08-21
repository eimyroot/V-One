from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / ".github" / "governance" / "main-branch-baseline.v1.json"
DEFAULT_API_VERSION = "2022-11-28"
EVIDENCE_SCHEMA = "vone.github-main-governance-evidence/v1"


class GitHubEvidenceError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_baseline(path: Path) -> dict[str, Any]:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if baseline.get("schema") != "vone.github-main-governance/v1":
        raise ValueError("unsupported governance baseline schema")
    if not baseline.get("repository") or not baseline.get("branch"):
        raise ValueError("baseline repository/branch is required")
    return baseline


def _validate_github_api_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com":
        raise GitHubEvidenceError("refusing non-GitHub API URL")
    if parsed.username is not None or parsed.password is not None or parsed.port not in {None, 443}:
        raise GitHubEvidenceError("refusing non-canonical GitHub API authority")


def github_get(url: str, *, token: str | None, api_version: str) -> Any:
    _validate_github_api_url(url)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "vone-g0-governance-verifier",
        "X-GitHub-Api-Version": api_version,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        raise GitHubEvidenceError(f"GitHub API HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise GitHubEvidenceError(f"GitHub API unavailable: {exc.reason}") from exc


def _required_status_contexts(active_rules: list[dict[str, Any]]) -> tuple[set[str], bool]:
    contexts: set[str] = set()
    strict = False
    for rule in active_rules:
        if rule.get("type") != "required_status_checks":
            continue
        parameters = rule.get("parameters") or {}
        strict = strict or bool(parameters.get("strict_required_status_checks_policy"))
        for item in parameters.get("required_status_checks") or []:
            context = item.get("context") if isinstance(item, dict) else None
            if context:
                contexts.add(str(context))
    return contexts, strict


def _pull_request_thread_resolution(active_rules: list[dict[str, Any]]) -> bool:
    for rule in active_rules:
        if rule.get("type") != "pull_request":
            continue
        parameters = rule.get("parameters") or {}
        if parameters.get("required_review_thread_resolution") is True:
            return True
    return False


def evaluate_ruleset_state(
    baseline: dict[str, Any],
    active_rules: list[dict[str, Any]],
    ruleset_details: list[dict[str, Any]],
) -> dict[str, Any]:
    desired = baseline["desired"]
    rule_types = {str(rule.get("type")) for rule in active_rules if rule.get("type")}
    contexts, strict_checks = _required_status_contexts(active_rules)
    expected_contexts = set(desired.get("required_status_checks") or [])

    bypass_actors: list[dict[str, Any]] = []
    inactive_rulesets: list[int] = []
    for ruleset in ruleset_details:
        if ruleset.get("enforcement") not in {"active", "enabled"}:
            ruleset_id = ruleset.get("id")
            if isinstance(ruleset_id, int):
                inactive_rulesets.append(ruleset_id)
        for actor in ruleset.get("bypass_actors") or []:
            if isinstance(actor, dict):
                bypass_actors.append(actor)

    checks = {
        "pull_request_required": (
            not desired.get("pull_request_required", False) or "pull_request" in rule_types
        ),
        "required_status_checks": expected_contexts.issubset(contexts),
        "require_latest_head_checks": (
            not desired.get("require_latest_head_checks", False) or strict_checks
        ),
        "force_push_disabled": (
            desired.get("allow_force_pushes") is not False or "non_fast_forward" in rule_types
        ),
        "branch_delete_disabled": (
            desired.get("allow_deletions") is not False or "deletion" in rule_types
        ),
        "conversation_resolution_required": (
            not desired.get("require_conversation_resolution", False)
            or _pull_request_thread_resolution(active_rules)
        ),
        "ordinary_admin_bypass_disabled": (
            desired.get("ordinary_admin_bypass") is not False or not bypass_actors
        ),
        "rulesets_active": not inactive_rulesets,
    }

    return {
        "checks": checks,
        "observed": {
            "active_rule_types": sorted(rule_types),
            "required_status_checks": sorted(contexts),
            "strict_required_status_checks_policy": strict_checks,
            "bypass_actors": bypass_actors,
            "inactive_ruleset_ids": inactive_rulesets,
        },
        "ok": all(checks.values()),
    }


def collect_live_ruleset_evidence(
    baseline: dict[str, Any], *, token: str | None, api_version: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    repository = baseline["repository"]
    branch = baseline["branch"]
    owner, repo = repository.split("/", 1)
    base = f"https://api.github.com/repos/{owner}/{repo}"
    rules_url = f"{base}/rules/branches/{branch}?per_page=100"
    active_rules = github_get(rules_url, token=token, api_version=api_version)
    if not isinstance(active_rules, list):
        raise GitHubEvidenceError("branch rules endpoint did not return a list")

    ruleset_ids = sorted(
        {
            int(rule["ruleset_id"])
            for rule in active_rules
            if isinstance(rule, dict) and isinstance(rule.get("ruleset_id"), int)
        }
    )
    details: list[dict[str, Any]] = []
    sources = [rules_url]
    for ruleset_id in ruleset_ids:
        detail_url = f"{base}/rulesets/{ruleset_id}"
        detail = github_get(detail_url, token=token, api_version=api_version)
        if not isinstance(detail, dict):
            raise GitHubEvidenceError(f"ruleset {ruleset_id} endpoint did not return an object")
        details.append(detail)
        sources.append(detail_url)
    return active_rules, details, sources


def build_report(
    baseline: dict[str, Any],
    *,
    active_rules: list[dict[str, Any]] | None = None,
    ruleset_details: list[dict[str, Any]] | None = None,
    sources: list[str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    if error is not None:
        return {
            "schema": EVIDENCE_SCHEMA,
            "verified_at": _utc_now(),
            "repository": baseline["repository"],
            "branch": baseline["branch"],
            "source": sources or [],
            "verdict": "UNKNOWN",
            "checks": {},
            "observed": {},
            "error": error,
        }

    evaluation = evaluate_ruleset_state(
        baseline,
        active_rules or [],
        ruleset_details or [],
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "verified_at": _utc_now(),
        "repository": baseline["repository"],
        "branch": baseline["branch"],
        "source": sources or [],
        "verdict": "VERIFIED" if evaluation["ok"] else "BLOCKED",
        "checks": evaluation["checks"],
        "observed": evaluation["observed"],
        "error": None,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed live verifier for the V-One GitHub main governance baseline."
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--api-version", default=os.getenv("GITHUB_API_VERSION", DEFAULT_API_VERSION))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    baseline = load_baseline(args.baseline)
    token = os.getenv(args.token_env) or None

    try:
        active_rules, details, sources = collect_live_ruleset_evidence(
            baseline,
            token=token,
            api_version=args.api_version,
        )
        report = build_report(
            baseline,
            active_rules=active_rules,
            ruleset_details=details,
            sources=sources,
        )
    except GitHubEvidenceError as exc:
        report = build_report(baseline, error=str(exc))

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")

    if report["verdict"] == "VERIFIED":
        return 0
    if report["verdict"] == "BLOCKED":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
