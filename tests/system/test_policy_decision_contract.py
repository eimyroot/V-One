from __future__ import annotations

import hashlib

import pytest

from voodoo_product.policy_decision import (
    PolicyDecision,
    PolicyDecisionError,
    PolicyObligation,
)

DIGEST_A = hashlib.sha256(b"policy").hexdigest()
DIGEST_B = hashlib.sha256(b"input").hexdigest()


def test_policy_decision_round_trips_with_digest() -> None:
    decision = PolicyDecision.create(
        decision_id="policy-001",
        policy_package="v-one/control-plane",
        policy_version="2026.08.15",
        bundle_digest=DIGEST_A,
        input_schema_version=1,
        input_digest=DIGEST_B,
        outcome="allow",
        reasons=("all required gates passed",),
        violated_rules=(),
        obligations=(),
        purpose="decide whether a bounded action may continue",
        system_benefit="keeps policy outcomes machine-verifiable",
    )

    assert PolicyDecision.from_dict(decision.to_dict()) == decision


def test_policy_decision_rejects_unknown_outcome() -> None:
    with pytest.raises(PolicyDecisionError):
        PolicyDecision.create(
            decision_id="policy-001",
            policy_package="v-one/control-plane",
            policy_version="2026.08.15",
            bundle_digest=DIGEST_A,
            input_schema_version=1,
            input_digest=DIGEST_B,
            outcome="maybe",
            reasons=("unknown policy outcome must fail closed",),
            violated_rules=(),
            obligations=(),
            purpose="reject unsupported outcomes",
            system_benefit="prevents ambiguous authorization states",
        )


def test_policy_decision_rejects_allow_with_violations() -> None:
    with pytest.raises(PolicyDecisionError):
        PolicyDecision.create(
            decision_id="policy-001",
            policy_package="v-one/control-plane",
            policy_version="2026.08.15",
            bundle_digest=DIGEST_A,
            input_schema_version=1,
            input_digest=DIGEST_B,
            outcome="allow",
            reasons=("rule violation is present",),
            violated_rules=("missing_evidence",),
            obligations=(),
            purpose="reject contradictory policy decisions",
            system_benefit="keeps allow decisions trustworthy",
        )


def test_policy_decision_rejects_needs_approval_without_obligation() -> None:
    with pytest.raises(PolicyDecisionError):
        PolicyDecision.create(
            decision_id="policy-001",
            policy_package="v-one/control-plane",
            policy_version="2026.08.15",
            bundle_digest=DIGEST_A,
            input_schema_version=1,
            input_digest=DIGEST_B,
            outcome="needs_approval",
            reasons=("human approval is required",),
            violated_rules=(),
            obligations=(),
            purpose="make approval requirements explicit",
            system_benefit="prevents hidden manual gates",
        )


def test_policy_decision_requires_usefulness() -> None:
    with pytest.raises(PolicyDecisionError):
        PolicyDecision.create(
            decision_id="policy-001",
            policy_package="v-one/control-plane",
            policy_version="2026.08.15",
            bundle_digest=DIGEST_A,
            input_schema_version=1,
            input_digest=DIGEST_B,
            outcome="needs_approval",
            reasons=("human approval is required",),
            violated_rules=(),
            obligations=(
                PolicyObligation(
                    obligation="operator must approve release",
                    purpose="record the human gate",
                    system_benefit="keeps release authorization auditable",
                ),
            ),
            purpose="make approval requirements explicit",
            system_benefit="",
        )
