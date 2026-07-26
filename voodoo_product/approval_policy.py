from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

VALID_ENVIRONMENTS = {"local", "development", "staging", "production"}
VALID_RISKS = {"R0", "R1", "R2", "R3", "R4"}

CURRENT_APPROVAL_POLICY_VERSION = "approval-policy/current-v1"
CURRENT_APPROVAL_PROFILE = "CURRENT_COMPATIBILITY"
CURRENT_AUTHORIZATION_MODE = "INDEPENDENT_APPROVAL"
CURRENT_REQUIRED_PERMISSION = "approval.review"
CURRENT_DECISION = "ALLOW_AFTER_AUTHORIZATION"


class ApprovalPolicyCompatibilityError(RuntimeError):
    """Raised when an injected evaluator diverges from current runtime behavior."""


@dataclass(frozen=True, slots=True)
class ApprovalPolicyInput:
    """Validated facts used by the current-behavior compatibility evaluator."""

    environment: str
    risk: str

    def __post_init__(self) -> None:
        if not isinstance(self.environment, str) or self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        if not isinstance(self.risk, str) or self.risk not in VALID_RISKS:
            raise ValueError("unknown risk")


@dataclass(frozen=True, slots=True)
class ApprovalPolicyDecision:
    """Explainable approval requirements without changing runtime enforcement."""

    policy_version: str
    profile: str
    decision: str
    authorization_mode: str
    required_approvals: int
    required_permissions: tuple[str, ...]
    distinct_approver_identities: int
    requester_may_approve: bool
    step_up_required: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation for tests and future adapters."""

        return {
            "policy_version": self.policy_version,
            "profile": self.profile,
            "decision": self.decision,
            "authorization_mode": self.authorization_mode,
            "required_approvals": self.required_approvals,
            "required_permissions": list(self.required_permissions),
            "distinct_approver_identities": self.distinct_approver_identities,
            "requester_may_approve": self.requester_may_approve,
            "step_up_required": self.step_up_required,
            "reason_codes": list(self.reason_codes),
        }


ApprovalPolicyEvaluator = Callable[[ApprovalPolicyInput], ApprovalPolicyDecision]


def current_required_approvals(environment: str) -> int:
    """Return the authoritative current approval count for one environment."""

    if not isinstance(environment, str) or environment not in VALID_ENVIRONMENTS:
        raise ValueError("unknown environment")
    return 2 if environment == "production" else 1


def evaluate_current_approval_policy(
    policy_input: ApprovalPolicyInput,
) -> ApprovalPolicyDecision:
    """Reproduce the existing environment-based approval requirements deterministically."""

    production = policy_input.environment == "production"
    required_approvals = current_required_approvals(policy_input.environment)
    environment_reason = f"ENVIRONMENT_{policy_input.environment.upper()}"
    risk_reason = f"{policy_input.risk}_CURRENTLY_NON_ENFORCING"
    approval_reason = (
        "PRODUCTION_TWO_APPROVALS_REQUIRED"
        if production
        else "NON_PRODUCTION_ONE_APPROVAL_REQUIRED"
    )

    reason_codes = (
        "CURRENT_BEHAVIOR_COMPATIBILITY",
        environment_reason,
        risk_reason,
        "REQUESTER_SELF_APPROVAL_DENIED",
        approval_reason,
    )
    if production:
        reason_codes += ("PRODUCTION_EFFECTS_USE_SEPARATE_FAIL_CLOSED_GATE",)

    return ApprovalPolicyDecision(
        policy_version=CURRENT_APPROVAL_POLICY_VERSION,
        profile=CURRENT_APPROVAL_PROFILE,
        decision=CURRENT_DECISION,
        authorization_mode=CURRENT_AUTHORIZATION_MODE,
        required_approvals=required_approvals,
        required_permissions=(CURRENT_REQUIRED_PERMISSION,),
        distinct_approver_identities=required_approvals,
        requester_may_approve=False,
        step_up_required=False,
        reason_codes=reason_codes,
    )


def resolve_current_approval_policy(
    policy_input: ApprovalPolicyInput,
    *,
    evaluator: ApprovalPolicyEvaluator = evaluate_current_approval_policy,
) -> ApprovalPolicyDecision:
    """Resolve a current-policy decision and fail closed on compatibility drift."""

    decision = evaluator(policy_input)
    expected = evaluate_current_approval_policy(policy_input)
    if not isinstance(decision, ApprovalPolicyDecision) or decision != expected:
        raise ApprovalPolicyCompatibilityError(
            "approval policy evaluator diverged from current runtime behavior"
        )
    return decision
