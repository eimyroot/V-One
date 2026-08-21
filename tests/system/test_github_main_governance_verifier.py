from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_github_main_governance as verifier  # noqa: E402

GITHUB_ACTIONS_APP_ID = 15368
UPLOAD_ARTIFACT_PIN = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"


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
            "ruleset_source_type": "Repository",
            "ruleset_source": "nulleimy/V-One",
            "ruleset_id": 17,
            "parameters": {"required_review_thread_resolution": True},
        },
        {
            "type": "required_status_checks",
            "ruleset_source_type": "Repository",
            "ruleset_source": "nulleimy/V-One",
            "ruleset_id": 17,
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": "verify", "integration_id": GITHUB_ACTIONS_APP_ID}
                ],
            },
        },
        {
            "type": "non_fast_forward",
            "ruleset_source_type": "Repository",
            "ruleset_source": "nulleimy/V-One",
            "ruleset_id": 17,
        },
        {
            "type": "deletion",
            "ruleset_source_type": "Repository",
            "ruleset_source": "nulleimy/V-One",
            "ruleset_id": 17,
        },
    ]


def passing_details() -> list[dict[str, object]]:
    return [{"id": 17, "enforcement": "active", "bypass_actors": []}]


def provider_ids() -> dict[str, set[int]]:
    return {"verify": {GITHUB_ACTIONS_APP_ID}}


def evaluate(
    rules: list[dict[str, object]] | None = None,
    details: list[dict[str, object]] | None = None,
    providers: dict[str, set[int]] | None = None,
) -> dict[str, object]:
    return verifier.evaluate_ruleset_state(
        baseline(),
        rules if rules is not None else passing_rules(),
        details if details is not None else passing_details(),
        providers if providers is not None else provider_ids(),
    )


def test_machine_baseline_matches_verifier_contract() -> None:
    actual = json.loads(
        (ROOT / ".github" / "governance" / "main-branch-baseline.v1.json").read_text(
            encoding="utf-8"
        )
    )

    expected = baseline()
    assert actual["schema"] == expected["schema"]
    assert actual["repository"] == expected["repository"]
    assert actual["branch"] == expected["branch"]
    assert actual["desired"] == expected["desired"]
    assert actual["evidence_policy"]["live_github_configuration_required"] is True
    assert actual["evidence_policy"]["unknown_fails_closed"] is True


def test_g0_workflow_is_manual_read_only_and_retains_fail_closed_evidence() -> None:
    text = (ROOT / ".github" / "workflows" / "g0-governance-verify.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "push:" not in text
    assert "contents: read" in text
    assert "checks: read" in text
    assert "persist-credentials: false" in text
    assert "VONE_GITHUB_GOVERNANCE_TOKEN" in text
    assert "continue-on-error: true" in text
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_PIN}" in text
    assert "g0-governance-evidence.json" in text
    assert "g0-governance-evidence.sha256" in text
    assert "Enforce G0 verdict" in text
    assert "test \"$G0_OUTCOME\" = \"success\"" in text


def test_verified_requires_complete_active_rule_set() -> None:
    result = evaluate()

    assert result["ok"] is True
    assert all(result["checks"].values())
    assert result["unknown_reasons"] == []
    assert result["observed"]["required_status_checks"] == ["verify"]
    assert result["observed"]["provider_app_ids"] == {"verify": [GITHUB_ACTIONS_APP_ID]}


def test_missing_required_verify_check_fails_closed() -> None:
    rules = passing_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    parameters = status_rule["parameters"]
    assert isinstance(parameters, dict)
    parameters["required_status_checks"] = [
        {"context": "other", "integration_id": GITHUB_ACTIONS_APP_ID}
    ]

    result = evaluate(rules=rules)

    assert result["ok"] is False
    assert result["checks"]["required_status_checks"] is False


def test_any_source_required_check_fails_provider_binding() -> None:
    rules = passing_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    parameters = status_rule["parameters"]
    assert isinstance(parameters, dict)
    parameters["required_status_checks"] = [{"context": "verify"}]

    result = evaluate(rules=rules)

    assert result["ok"] is False
    assert result["checks"]["required_check_provider"] is False
    assert result["unknown_reasons"] == []


def test_wrong_app_required_check_fails_provider_binding() -> None:
    rules = passing_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    parameters = status_rule["parameters"]
    assert isinstance(parameters, dict)
    parameters["required_status_checks"] = [{"context": "verify", "integration_id": 999999}]

    result = evaluate(rules=rules)

    assert result["ok"] is False
    assert result["checks"]["required_check_provider"] is False


def test_missing_provider_observation_is_unknown_not_blocked() -> None:
    result = evaluate(providers={})

    assert result["ok"] is False
    assert "REQUIRED_CHECK_PROVIDER_EVIDENCE_INCOMPLETE" in result["unknown_reasons"]

    report = verifier.build_report(
        baseline(),
        active_rules=passing_rules(),
        ruleset_details=passing_details(),
        provider_app_ids={},
    )
    assert report["verdict"] == "UNKNOWN"


def test_non_strict_status_checks_fail_latest_head_requirement() -> None:
    rules = passing_rules()
    status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
    parameters = status_rule["parameters"]
    assert isinstance(parameters, dict)
    parameters["strict_required_status_checks_policy"] = False

    result = evaluate(rules=rules)

    assert result["ok"] is False
    assert result["checks"]["require_latest_head_checks"] is False


def test_missing_conversation_resolution_fails_closed() -> None:
    rules = passing_rules()
    pull_request_rule = next(rule for rule in rules if rule["type"] == "pull_request")
    parameters = pull_request_rule["parameters"]
    assert isinstance(parameters, dict)
    parameters["required_review_thread_resolution"] = False

    result = evaluate(rules=rules)

    assert result["ok"] is False
    assert result["checks"]["conversation_resolution_required"] is False


def test_force_push_or_delete_permission_fails_closed() -> None:
    rules = [
        rule for rule in passing_rules() if rule["type"] not in {"non_fast_forward", "deletion"}
    ]

    result = evaluate(rules=rules)

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

    result = evaluate(details=details)

    assert result["ok"] is False
    assert result["checks"]["ordinary_admin_bypass_disabled"] is False
    assert result["unknown_reasons"] == []


def test_hidden_bypass_actor_property_is_unknown_not_empty() -> None:
    details = [{"id": 17, "enforcement": "active"}]

    result = evaluate(details=details)

    assert result["ok"] is False
    assert result["checks"]["ordinary_admin_bypass_disabled"] is False
    assert "RULESET_BYPASS_EVIDENCE_INCOMPLETE" in result["unknown_reasons"]

    report = verifier.build_report(
        baseline(),
        active_rules=passing_rules(),
        ruleset_details=details,
        provider_app_ids=provider_ids(),
    )
    assert report["verdict"] == "UNKNOWN"


def test_unknown_live_read_is_not_promoted_to_pass() -> None:
    report = verifier.build_report(baseline(), error="GitHub API unavailable")

    assert report["verdict"] == "UNKNOWN"
    assert report["checks"] == {}
    assert report["unknown_reasons"] == ["LIVE_EVIDENCE_UNAVAILABLE"]
    assert report["error"] == "GitHub API unavailable"


def test_blocked_report_is_distinct_from_unknown() -> None:
    report = verifier.build_report(
        baseline(),
        active_rules=[],
        ruleset_details=[],
        provider_app_ids=provider_ids(),
        sources=["https://api.github.com/example"],
    )

    assert report["verdict"] == "BLOCKED"
    assert report["unknown_reasons"] == []
    assert report["error"] is None


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://api.github.com/repos/nulleimy/V-One",
        "https://api.github.com.evil.example/repos/nulleimy/V-One",
        "https://user@example.com@api.github.com/repos/nulleimy/V-One",
    ],
)
def test_live_verifier_rejects_noncanonical_github_urls(url: str) -> None:
    with pytest.raises(verifier.GitHubEvidenceError, match="refusing"):
        verifier.github_get(url, token=None, api_version="2022-11-28")
