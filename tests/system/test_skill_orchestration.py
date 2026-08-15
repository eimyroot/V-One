from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.skill_orchestration import (
    PRIMARY_COORDINATOR,
    SkillOrchestrationPlan,
    select_relevant_skills,
)


def digest_without(payload: dict[str, object], digest_field: str) -> str:
    return hashlib.sha256(
        canonical_json(
            {key: value for key, value in payload.items() if key != digest_field}
        ).encode("utf-8")
    ).hexdigest()


def plan(**changes: Any) -> SkillOrchestrationPlan:
    selected = select_relevant_skills(task_type="ci_cd")
    values = {
        "task_id": "pr_69_ci_recovery",
        "task_type": "ci_cd",
        "source_of_truth": "github:nulleimy/V-One/pull/69",
        "objective": "Get PR #69 from failed checks to review-ready without scope expansion.",
        "selected_skills": selected,
        "excluded_operations": (
            "merge",
            "deploy",
            "production_effect",
            "runtime_authorization_change",
        ),
        "acceptance_gates": (
            "github_actions_green",
            "full_pytest_passes",
            "ruff_passes",
            "documentation_does_not_overclaim_runtime_authority",
        ),
    }
    values.update(changes)
    return SkillOrchestrationPlan.create(**values)


def test_relevant_skill_selection_uses_one_primary_coordinator() -> None:
    selected = select_relevant_skills(task_type="ci_cd")

    assert PRIMARY_COORDINATOR in selected
    assert "systematic-debugging-and-root-cause-engineer" in selected
    assert "quality-evidence-verifier" in selected
    assert "supply-chain-provenance-governor" in selected


def test_skill_orchestration_plan_is_deterministic_and_round_trippable() -> None:
    first = plan()
    second = plan(selected_skills=tuple(reversed(select_relevant_skills(task_type="ci_cd"))))

    assert first.to_dict() == second.to_dict()
    assert first.primary_coordinator == PRIMARY_COORDINATOR
    assert first.plan_digest == digest_without(first.to_dict(), "plan_digest")
    assert SkillOrchestrationPlan.from_dict(first.to_dict()) == first


def test_skill_orchestration_plan_covers_catalog_with_reasons() -> None:
    value = plan()

    assert value.selections == tuple(sorted(value.selections, key=lambda item: item.skill))
    assert all(selection.reason for selection in value.selections)
    assert all(selection.purpose for selection in value.selections)
    assert all(selection.authority for selection in value.selections)


def test_skill_orchestration_rejects_unknown_selected_skill() -> None:
    with pytest.raises(ValueError, match="unknown"):
        plan(selected_skills=("made-up-skill",))


def test_skill_orchestration_rejects_selected_irrelevant_skill() -> None:
    with pytest.raises(ValueError, match="not relevant"):
        plan(selected_skills=("product-value-and-discovery-governor",))


def test_skill_orchestration_rejects_tampered_skill_authority() -> None:
    value = plan().to_dict()
    value["selections"][0]["authority"] = "competing_authority"
    value["plan_digest"] = digest_without(value, "plan_digest")

    with pytest.raises(ValueError, match="authority"):
        SkillOrchestrationPlan.from_dict(value)


def test_skill_orchestration_rejects_competing_selected_coordinator() -> None:
    value = plan()

    with pytest.raises(ValueError, match="role"):
        tuple(
            replace(item, role="coordinator")
            if item.skill == "quality-evidence-verifier"
            else item
            for item in value.selections
        )
