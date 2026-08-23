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
PAGE_SIZE = 100
MAX_PAGES = 100


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
    desired = baseline.get("desired")
    if not isinstance(desired, dict):
        raise ValueError("baseline desired controls are required")
    if desired.get("workflow") and not desired.get("workflow_path"):
        raise ValueError("workflow_path is required when workflow identity is required")
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


def _page_url(url: str, page: int) -> str:
    _validate_github_api_url(url)
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["per_page"] = str(PAGE_SIZE)
    query["page"] = str(page)
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def github_get_list_pages(
    url: str, *, token: str | None, api_version: str
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    sources: list[str] = []
    for page in range(1, MAX_PAGES + 1):
        page_url = _page_url(url, page)
        payload = github_get(page_url, token=token, api_version=api_version)
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise GitHubEvidenceError("paginated GitHub endpoint did not return an object list")
        items.extend(payload)
        sources.append(page_url)
        if len(payload) < PAGE_SIZE:
            return items, sources
    raise GitHubEvidenceError("GitHub pagination exceeded fail-closed page limit")


def github_get_check_run_pages(
    url: str, *, token: str | None, api_version: str
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    sources: list[str] = []
    for page in range(1, MAX_PAGES + 1):
        page_url = _page_url(url, page)
        payload = github_get(page_url, token=token, api_version=api_version)
        if not isinstance(payload, dict) or not isinstance(payload.get("check_runs"), list):
            raise GitHubEvidenceError("check-runs endpoint did not return a check_runs list")
        page_items = payload["check_runs"]
        if not all(isinstance(item, dict) for item in page_items):
            raise GitHubEvidenceError("check-runs page contains a non-object entry")
        items.extend(page_items)
        sources.append(page_url)
        if len(page_items) < PAGE_SIZE:
            return items, sources
    raise GitHubEvidenceError("check-run pagination exceeded fail-closed page limit")


def _required_status_bindings(
    active_rules: list[dict[str, Any]],
) -> tuple[set[str], bool, dict[str, set[int | None]]]:
    contexts: set[str] = set()
    integrations: dict[str, set[int | None]] = {}
    strict = False
    for rule in active_rules:
        if rule.get("type") != "required_status_checks":
            continue
        parameters = rule.get("parameters") or {}
        strict = strict or bool(parameters.get("strict_required_status_checks_policy"))
        for item in parameters.get("required_status_checks") or []:
            if not isinstance(item, dict):
                continue
            context = item.get("context")
            if not context:
                continue
            normalized = str(context)
            contexts.add(normalized)
            integration_id = item.get("integration_id")
            integrations.setdefault(normalized, set()).add(
                integration_id if isinstance(integration_id, int) else None
            )
    return contexts, strict, integrations


def _pull_request_thread_resolution(active_rules: list[dict[str, Any]]) -> bool:
    for rule in active_rules:
        if rule.get("type") != "pull_request":
            continue
        parameters = rule.get("parameters") or {}
        if parameters.get("required_review_thread_resolution") is True:
            return True
    return False


def _provider_observations_complete(
    expected_contexts: set[str], provider_observations: dict[str, list[dict[str, Any]]]
) -> bool:
    return all(bool(provider_observations.get(context)) for context in expected_contexts)


def _workflow_observation_complete(observation: dict[str, Any]) -> bool:
    return (
        isinstance(observation.get("app_id"), int)
        and isinstance(observation.get("workflow"), str)
        and isinstance(observation.get("workflow_path"), str)
        and isinstance(observation.get("head_sha"), str)
    )


def evaluate_ruleset_state(
    baseline: dict[str, Any],
    active_rules: list[dict[str, Any]],
    ruleset_details: list[dict[str, Any]],
    provider_observations: dict[str, list[dict[str, Any]]],
    branch_head_sha: str | None,
) -> dict[str, Any]:
    desired = baseline["desired"]
    rule_types = {str(rule.get("type")) for rule in active_rules if rule.get("type")}
    contexts, strict_checks, integrations = _required_status_bindings(active_rules)
    expected_contexts = set(desired.get("required_status_checks") or [])

    bypass_evidence_complete = all("bypass_actors" in ruleset for ruleset in ruleset_details)
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

    provider_evidence_required = bool(desired.get("required_check_provider"))
    provider_evidence_complete = (
        not provider_evidence_required
        or _provider_observations_complete(expected_contexts, provider_observations)
    )
    workflow_identity_required = bool(desired.get("workflow"))
    workflow_evidence_complete = not workflow_identity_required or (
        isinstance(branch_head_sha, str)
        and bool(branch_head_sha)
        and all(
            observations
            and all(_workflow_observation_complete(item) for item in observations)
            for context in expected_contexts
            for observations in [provider_observations.get(context, [])]
        )
    )

    expected_workflow = desired.get("workflow")
    expected_workflow_path = desired.get("workflow_path")
    workflow_identity_ok = not workflow_identity_required or (
        workflow_evidence_complete
        and all(
            all(
                observation["workflow"] == expected_workflow
                and observation["workflow_path"] == expected_workflow_path
                and observation["head_sha"] == branch_head_sha
                for observation in provider_observations.get(context, [])
            )
            for context in expected_contexts
        )
    )

    provider_binding_ok = not provider_evidence_required or all(
        bool(
            {
                integration_id
                for integration_id in integrations.get(context, set())
                if integration_id is not None
            }
            & {
                int(observation["app_id"])
                for observation in provider_observations.get(context, [])
                if isinstance(observation.get("app_id"), int)
            }
        )
        for context in expected_contexts
    )

    unknown_reasons: list[str] = []
    if ruleset_details and not bypass_evidence_complete:
        unknown_reasons.append("RULESET_BYPASS_EVIDENCE_INCOMPLETE")
    if not provider_evidence_complete:
        unknown_reasons.append("REQUIRED_CHECK_PROVIDER_EVIDENCE_INCOMPLETE")
    if not workflow_evidence_complete:
        unknown_reasons.append("REQUIRED_CHECK_WORKFLOW_EVIDENCE_INCOMPLETE")

    checks = {
        "pull_request_required": (
            not desired.get("pull_request_required", False) or "pull_request" in rule_types
        ),
        "required_status_checks": expected_contexts.issubset(contexts),
        "required_check_provider": provider_binding_ok,
        "required_check_workflow_identity": workflow_identity_ok,
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
        "ordinary_admin_bypass_disabled": bypass_evidence_complete
        and (desired.get("ordinary_admin_bypass") is not False or not bypass_actors),
        "rulesets_active": not inactive_rulesets,
    }

    return {
        "checks": checks,
        "observed": {
            "active_rule_types": sorted(rule_types),
            "required_status_checks": sorted(contexts),
            "required_status_check_integration_ids": {
                context: sorted(value for value in values if value is not None)
                for context, values in sorted(integrations.items())
            },
            "provider_observations": {
                context: observations
                for context, observations in sorted(provider_observations.items())
            },
            "branch_head_sha": branch_head_sha,
            "strict_required_status_checks_policy": strict_checks,
            "bypass_evidence_complete": bypass_evidence_complete,
            "bypass_actors": bypass_actors,
            "inactive_ruleset_ids": inactive_rulesets,
        },
        "unknown_reasons": unknown_reasons,
        "ok": not unknown_reasons and all(checks.values()),
    }


def _ruleset_detail_url(base: str, rule: dict[str, Any]) -> str:
    ruleset_id = rule.get("ruleset_id")
    source_type = rule.get("ruleset_source_type")
    source = rule.get("ruleset_source")
    if not isinstance(ruleset_id, int):
        raise GitHubEvidenceError("active branch rule is missing ruleset_id")
    if source_type == "Repository":
        return f"{base}/rulesets/{ruleset_id}"
    if source_type == "Organization" and isinstance(source, str) and source:
        org = urllib.parse.quote(source, safe="")
        return f"https://api.github.com/orgs/{org}/rulesets/{ruleset_id}"
    raise GitHubEvidenceError(f"unsupported ruleset source type: {source_type!r}")


def _actions_run_id(details_url: str, owner: str, repo: str) -> int:
    parsed = urllib.parse.urlparse(details_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitHubEvidenceError("check run has non-GitHub Actions details URL")
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[:4] != [owner, repo, "actions", "runs"]:
        raise GitHubEvidenceError("check run details URL does not identify an Actions run")
    try:
        return int(parts[4])
    except ValueError as exc:
        raise GitHubEvidenceError("check run details URL has invalid Actions run id") from exc


def _collect_provider_observations(
    base: str,
    owner: str,
    repo: str,
    branch_sha: str,
    contexts: list[str],
    provider_slug: str,
    *,
    token: str | None,
    api_version: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    result: dict[str, list[dict[str, Any]]] = {}
    sources: list[str] = []
    encoded_sha = urllib.parse.quote(branch_sha, safe="")
    for context in contexts:
        encoded_context = urllib.parse.quote(context, safe="")
        check_url = (
            f"{base}/commits/{encoded_sha}/check-runs"
            f"?check_name={encoded_context}&filter=all"
        )
        runs, page_sources = github_get_check_run_pages(
            check_url,
            token=token,
            api_version=api_version,
        )
        sources.extend(page_sources)
        observations: list[dict[str, Any]] = []
        seen_run_ids: set[int] = set()
        for run in runs:
            if run.get("name") != context:
                continue
            app = run.get("app")
            if not isinstance(app, dict) or app.get("slug") != provider_slug:
                continue
            app_id = app.get("id")
            details_url = run.get("details_url")
            if not isinstance(app_id, int) or not isinstance(details_url, str):
                raise GitHubEvidenceError(
                    f"check run provider evidence is incomplete for context {context!r}"
                )
            run_id = _actions_run_id(details_url, owner, repo)
            if run_id in seen_run_ids:
                continue
            seen_run_ids.add(run_id)
            run_url = f"{base}/actions/runs/{run_id}"
            workflow_run = github_get(run_url, token=token, api_version=api_version)
            if not isinstance(workflow_run, dict):
                raise GitHubEvidenceError("Actions workflow-run endpoint did not return an object")
            observations.append(
                {
                    "app_id": app_id,
                    "workflow": workflow_run.get("name"),
                    "workflow_path": workflow_run.get("path"),
                    "head_sha": workflow_run.get("head_sha"),
                    "run_id": run_id,
                }
            )
            sources.append(run_url)
        result[context] = observations
    return result, sources


def collect_live_ruleset_evidence(
    baseline: dict[str, Any], *, token: str | None, api_version: str
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    str,
    list[str],
]:
    repository = baseline["repository"]
    branch = baseline["branch"]
    owner, repo = repository.split("/", 1)
    encoded_owner = urllib.parse.quote(owner, safe="")
    encoded_repo = urllib.parse.quote(repo, safe="")
    encoded_branch = urllib.parse.quote(branch, safe="")
    base = f"https://api.github.com/repos/{encoded_owner}/{encoded_repo}"

    branch_url = f"{base}/branches/{encoded_branch}"
    branch_payload = github_get(branch_url, token=token, api_version=api_version)
    if not isinstance(branch_payload, dict):
        raise GitHubEvidenceError("branch endpoint did not return an object")
    commit = branch_payload.get("commit")
    if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str):
        raise GitHubEvidenceError("branch endpoint did not return an exact commit SHA")
    branch_head_sha = commit["sha"]

    rules_url = f"{base}/rules/branches/{encoded_branch}"
    active_rules, rule_sources = github_get_list_pages(
        rules_url,
        token=token,
        api_version=api_version,
    )

    detail_urls = sorted({_ruleset_detail_url(base, rule) for rule in active_rules})
    details: list[dict[str, Any]] = []
    sources = [branch_url, *rule_sources]
    for detail_url in detail_urls:
        detail = github_get(detail_url, token=token, api_version=api_version)
        if not isinstance(detail, dict):
            raise GitHubEvidenceError("ruleset detail endpoint did not return an object")
        details.append(detail)
        sources.append(detail_url)

    desired = baseline["desired"]
    contexts = [str(value) for value in desired.get("required_status_checks") or []]
    provider_slug = str(desired.get("required_check_provider") or "")
    provider_observations: dict[str, list[dict[str, Any]]] = {}
    if provider_slug and contexts:
        provider_observations, provider_sources = _collect_provider_observations(
            base,
            owner,
            repo,
            branch_head_sha,
            contexts,
            provider_slug,
            token=token,
            api_version=api_version,
        )
        sources.extend(provider_sources)

    return active_rules, details, provider_observations, branch_head_sha, sources


def build_report(
    baseline: dict[str, Any],
    *,
    active_rules: list[dict[str, Any]] | None = None,
    ruleset_details: list[dict[str, Any]] | None = None,
    provider_observations: dict[str, list[dict[str, Any]]] | None = None,
    branch_head_sha: str | None = None,
    expected_source_sha: str | None = None,
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
            "observed": {"verifier_source_sha": expected_source_sha},
            "unknown_reasons": ["LIVE_EVIDENCE_UNAVAILABLE"],
            "error": error,
        }

    evaluation = evaluate_ruleset_state(
        baseline,
        active_rules or [],
        ruleset_details or [],
        provider_observations or {},
        branch_head_sha,
    )
    source_evidence_complete = isinstance(expected_source_sha, str) and bool(expected_source_sha)
    source_is_current = source_evidence_complete and (
        isinstance(branch_head_sha, str) and expected_source_sha == branch_head_sha
    )
    if not source_evidence_complete:
        evaluation["unknown_reasons"].append("VERIFIER_SOURCE_EVIDENCE_INCOMPLETE")
    evaluation["checks"]["verifier_source_is_current_main"] = source_is_current
    evaluation["observed"]["verifier_source_sha"] = expected_source_sha
    evaluation["ok"] = bool(evaluation["ok"]) and source_is_current

    verdict = (
        "UNKNOWN"
        if evaluation["unknown_reasons"]
        else ("VERIFIED" if evaluation["ok"] else "BLOCKED")
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "verified_at": _utc_now(),
        "repository": baseline["repository"],
        "branch": baseline["branch"],
        "source": sources or [],
        "verdict": verdict,
        "checks": evaluation["checks"],
        "observed": evaluation["observed"],
        "unknown_reasons": evaluation["unknown_reasons"],
        "error": None,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed live verifier for the V-One GitHub main governance baseline."
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--expected-source-sha")
    parser.add_argument("--api-version", default=os.getenv("GITHUB_API_VERSION", DEFAULT_API_VERSION))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    baseline = load_baseline(args.baseline)
    token = os.getenv(args.token_env) or None

    try:
        active_rules, details, provider_observations, branch_head_sha, sources = (
            collect_live_ruleset_evidence(
                baseline,
                token=token,
                api_version=args.api_version,
            )
        )
        report = build_report(
            baseline,
            active_rules=active_rules,
            ruleset_details=details,
            provider_observations=provider_observations,
            branch_head_sha=branch_head_sha,
            expected_source_sha=args.expected_source_sha,
            sources=sources,
        )
    except GitHubEvidenceError as exc:
        report = build_report(
            baseline,
            expected_source_sha=args.expected_source_sha,
            error=str(exc),
        )

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
