from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from voodoo_product.approval_policy import (
    CURRENT_APPROVAL_POLICY_VERSION,
    ApprovalPolicyCompatibilityError,
    ApprovalPolicyInput,
    evaluate_current_approval_policy,
    resolve_current_approval_policy,
)
from voodoo_product.evidence_primitives import canonical_json


@pytest.mark.parametrize("environment", ["local", "development", "staging"])
@pytest.mark.parametrize("risk", ["R0", "R1", "R2", "R3", "R4"])
def test_non_production_policy_reproduces_current_single_approval(
    environment: str,
    risk: str,
) -> None:
    decision = evaluate_current_approval_policy(
        ApprovalPolicyInput(environment=environment, risk=risk)
    )

    assert decision.policy_version == CURRENT_APPROVAL_POLICY_VERSION
    assert decision.profile == "CURRENT_COMPATIBILITY"
    assert decision.decision == "ALLOW_AFTER_AUTHORIZATION"
    assert decision.authorization_mode == "INDEPENDENT_APPROVAL"
    assert decision.required_approvals == 1
    assert decision.required_permissions == ("approval.review",)
    assert decision.distinct_approver_identities == 1
    assert decision.requester_may_approve is False
    assert decision.step_up_required is False
    assert decision.reason_codes == (
        "CURRENT_BEHAVIOR_COMPATIBILITY",
        f"ENVIRONMENT_{environment.upper()}",
        f"{risk}_CURRENTLY_NON_ENFORCING",
        "REQUESTER_SELF_APPROVAL_DENIED",
        "NON_PRODUCTION_ONE_APPROVAL_REQUIRED",
    )


@pytest.mark.parametrize("risk", ["R0", "R1", "R2", "R3", "R4"])
def test_production_policy_reproduces_current_dual_approval(risk: str) -> None:
    decision = evaluate_current_approval_policy(
        ApprovalPolicyInput(environment="production", risk=risk)
    )

    assert decision.required_approvals == 2
    assert decision.distinct_approver_identities == 2
    assert decision.requester_may_approve is False
    assert decision.required_permissions == ("approval.review",)
    assert decision.reason_codes == (
        "CURRENT_BEHAVIOR_COMPATIBILITY",
        "ENVIRONMENT_PRODUCTION",
        f"{risk}_CURRENTLY_NON_ENFORCING",
        "REQUESTER_SELF_APPROVAL_DENIED",
        "PRODUCTION_TWO_APPROVALS_REQUIRED",
        "PRODUCTION_EFFECTS_USE_SEPARATE_FAIL_CLOSED_GATE",
    )


def test_policy_decision_is_deterministic_and_canonically_serializable() -> None:
    policy_input = ApprovalPolicyInput(environment="local", risk="R1")

    first = evaluate_current_approval_policy(policy_input)
    second = evaluate_current_approval_policy(policy_input)

    assert first == second
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())
    assert first.to_dict() == {
        "policy_version": "approval-policy/current-v1",
        "profile": "CURRENT_COMPATIBILITY",
        "decision": "ALLOW_AFTER_AUTHORIZATION",
        "authorization_mode": "INDEPENDENT_APPROVAL",
        "required_approvals": 1,
        "required_permissions": ["approval.review"],
        "distinct_approver_identities": 1,
        "requester_may_approve": False,
        "step_up_required": False,
        "reason_codes": [
            "CURRENT_BEHAVIOR_COMPATIBILITY",
            "ENVIRONMENT_LOCAL",
            "R1_CURRENTLY_NON_ENFORCING",
            "REQUESTER_SELF_APPROVAL_DENIED",
            "NON_PRODUCTION_ONE_APPROVAL_REQUIRED",
        ],
    }


def test_current_risk_class_is_explainable_but_does_not_change_approval_count() -> None:
    decisions = {
        risk: evaluate_current_approval_policy(
            ApprovalPolicyInput(environment="staging", risk=risk)
        )
        for risk in ("R0", "R1", "R2", "R3", "R4")
    }

    assert {decision.required_approvals for decision in decisions.values()} == {1}
    for risk, decision in decisions.items():
        assert f"{risk}_CURRENTLY_NON_ENFORCING" in decision.reason_codes


@pytest.mark.parametrize("environment", ["", "LOCAL", "prod", "unknown", None])
def test_policy_input_rejects_unknown_environment(environment: object) -> None:
    with pytest.raises(ValueError, match="unknown environment"):
        ApprovalPolicyInput(environment=environment, risk="R1")  # type: ignore[arg-type]


@pytest.mark.parametrize("risk", ["", "r1", "R5", "low", None])
def test_policy_input_rejects_unknown_risk(risk: object) -> None:
    with pytest.raises(ValueError, match="unknown risk"):
        ApprovalPolicyInput(environment="local", risk=risk)  # type: ignore[arg-type]


def test_policy_input_and_decision_are_immutable() -> None:
    policy_input = ApprovalPolicyInput(environment="local", risk="R1")
    decision = evaluate_current_approval_policy(policy_input)

    with pytest.raises(FrozenInstanceError):
        policy_input.risk = "R2"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        decision.required_approvals = 2  # type: ignore[misc]


def test_runtime_compatibility_resolver_accepts_exact_current_decision() -> None:
    policy_input = ApprovalPolicyInput(environment="staging", risk="R2")

    decision = resolve_current_approval_policy(policy_input)

    assert decision == evaluate_current_approval_policy(policy_input)


def test_runtime_compatibility_resolver_fails_closed_on_policy_drift() -> None:
    policy_input = ApprovalPolicyInput(environment="production", risk="R4")

    def incompatible_evaluator(value: ApprovalPolicyInput):
        current = evaluate_current_approval_policy(value)
        return replace(current, required_approvals=1, distinct_approver_identities=1)

    with pytest.raises(ApprovalPolicyCompatibilityError, match="diverged"):
        resolve_current_approval_policy(
            policy_input,
            evaluator=incompatible_evaluator,
        )


def test_runtime_compatibility_resolver_rejects_invalid_evaluator_result() -> None:
    with pytest.raises(ApprovalPolicyCompatibilityError, match="diverged"):
        resolve_current_approval_policy(
            ApprovalPolicyInput(environment="local", risk="R0"),
            evaluator=lambda _: None,  # type: ignore[arg-type,return-value]
        )
