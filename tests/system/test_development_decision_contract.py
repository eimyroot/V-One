from __future__ import annotations

import hashlib

import pytest

from voodoo_product.development_decision import (
    DevelopmentDecisionError,
    DevelopmentDecisionRecord,
)
from voodoo_product.skill_orchestration import DEVELOPMENT_USEFULNESS_GATE

DIGEST_A = hashlib.sha256(b"skill plan").hexdigest()
DIGEST_B = hashlib.sha256(b"control plane decision").hexdigest()
DIGEST_C = hashlib.sha256(b"tests").hexdigest()


def test_development_decision_round_trips_with_digest() -> None:
    record = DevelopmentDecisionRecord.create(
        change_id="change-001",
        status="VERIFIED",
        purpose="record why a development change exists",
        system_benefit="keeps code changes tied to useful system outcomes",
        boundary="contract-only code and documentation change",
        non_scope=("production execution",),
        skill_plan_digest=DIGEST_A,
        control_plane_decision_digest=DIGEST_B,
        evidence_digests=(DIGEST_C,),
        acceptance_gates=(DEVELOPMENT_USEFULNESS_GATE, "tests_passed"),
        rollback="revert the change set before release promotion",
    )

    assert DevelopmentDecisionRecord.from_dict(record.to_dict()) == record


def test_development_decision_rejects_missing_usefulness_gate() -> None:
    with pytest.raises(DevelopmentDecisionError):
        DevelopmentDecisionRecord.create(
            change_id="change-001",
            status="IMPLEMENTED",
            purpose="record why a development change exists",
            system_benefit="keeps code changes tied to useful system outcomes",
            boundary="contract-only code and documentation change",
            non_scope=("production execution",),
            skill_plan_digest=DIGEST_A,
            control_plane_decision_digest=None,
            evidence_digests=(DIGEST_C,),
            acceptance_gates=("tests_passed",),
            rollback="revert the change set before release promotion",
        )


def test_development_decision_rejects_verified_without_control_plane_digest() -> None:
    with pytest.raises(DevelopmentDecisionError):
        DevelopmentDecisionRecord.create(
            change_id="change-001",
            status="VERIFIED",
            purpose="record why a development change exists",
            system_benefit="keeps code changes tied to useful system outcomes",
            boundary="contract-only code and documentation change",
            non_scope=("production execution",),
            skill_plan_digest=DIGEST_A,
            control_plane_decision_digest=None,
            evidence_digests=(DIGEST_C,),
            acceptance_gates=(DEVELOPMENT_USEFULNESS_GATE, "tests_passed"),
            rollback="revert the change set before release promotion",
        )
