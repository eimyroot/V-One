from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_github_main_governance as verifier  # noqa: E402


def baseline() -> dict[str, object]:
    return {
        "schema": "vone.github-main-governance/v1",
        "repository": "nulleimy/V-One",
        "branch": "main",
        "desired": {
            "pull_request_required": True,
            "required_status_checks": ["verify"],
            "required_check_provider": "github-actions",
            "workflow": "ci",
            "require_latest_head_checks": True,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "require_conversation_resolution": True,
            "ordinary_admin_bypass": False,
        },
    }


def passing_rules() -> list[dict[str, object]]:
    return [
        {
            "type": "pull_request",
            "ruleset_id": 17,
            "parameters": {"required_review_thread_resolution": True},
        },
        {
            "type": "required_status_checks",
            "ruleset_id": 17,
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": "verify"}],
            },
        },
        {"type": "non_fast_forward", "ruleset_id": 17},
        {"type": "deletion", "ruleset_id": 17},
    ]


def passing_details() -> list[dict[str, object]]:
    return [{"id": 17, "enforcement": "active", "bypass_actors": []}]


def test_verified_requires_complete_active_rule_set() -> None:
    result = verifier.evaluate_ruleset_state(baseline(), passing_rules(), passing_details())

    assert result["ok"] is True
    assert all(result["checks"].values())
    assert result["observed"]["required_status_checks"] == ["verify"]


def test_missing_required_verify_check_fails_closed() -> None:
    rules = passing_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    status_rule["parameters"]["required_status_checks"] = [{"context": "other"}]

    result = verifier.evaluate_ruleset_state(baseline(), rules, passing_details())

    assert result["ok"] is False
    assert result["checks"]["required_status_checks"] is False


def test_non_strict_status_checks_fail_latest_head_requirement() -> None:
    rules = passing_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    status_rule["parameters"]["strict_required_status_checks_policy"] = False

    result = verifier.evaluate_ruleset_state(baseline(), rules, passing_details())

    assert result["ok"] is False
    assert result["checks"]["require_latest_head_checks"] is False


def test_missing_conversation_resolution_fails_closed() -> None:
    rules = passing_rules()
    pull_request_rule = next(rule for rule in rules if rule["type"] == "pull_request")
    pull_request_rule["parameters"]["required_review_thread_resolution"] = False

    result = verifier.evaluate_ruleset_state(baseline(), rules, passing_details())

    assert result["ok"] is False
    assert result["checks"]["conversation_resolution_required"] is False


def test_force_push_or_delete_permission_fails_closed() -> None:
    rules = [
        rule for rule in passing_rules() if rule["type"] not in {"non_fast_forward", "deletion"}
    ]

    result = verifier.evaluate_ruleset_state(baseline(), rules, passing_details())

    assert result["ok"] is False
    assert result["checks"]["force_push_disabled"] is False
    assert result["checks"]["branch_delete_disabled"] is False


def test_any_ruleset_bypass_actor_fails_closed() -> None:
    details = [
        {
            "id": 17,
            "enforcement": "active",
            "bypass_actors": [
                {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
            ],
        }
    ]

    result = verifier.evaluate_ruleset_state(baseline(), passing_rules(), details)

    assert result["ok"] is False
    assert result["checks"]["ordinary_admin_bypass_disabled"] is False


def test_unknown_live_read_is_not_promoted_to_pass() -> None:
    report = verifier.build_report(baseline(), error="GitHub API unavailable")

    assert report["verdict"] == "UNKNOWN"
    assert report["checks"] == {}
    assert report["error"] == "GitHub API unavailable"


def test_blocked_report_is_distinct_from_unknown() -> None:
    report = verifier.build_report(
        baseline(),
        active_rules=[],
        ruleset_details=[],
        sources=["https://api.github.com/example"],
    )

    assert report["verdict"] == "BLOCKED"
    assert report["error"] is None
