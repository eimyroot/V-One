from __future__ import annotations

import hashlib

import pytest

from voodoo_product.control_plane import (
    AcceptanceGate,
    ControlPlaneBoundary,
    ControlPlaneDecisionError,
    EvidenceReference,
    VOneControlPlaneDecision,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.operation_semantics import (
    MEMBER_ROLES,
    OperationMember,
    OperationSemantics,
    TechniqueEvidence,
)
from voodoo_product.skill_orchestration import (
    SkillOrchestrationPlan,
    select_relevant_skills,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


def digest_without(payload: dict[str, object], digest_field: str) -> str:
    return hashlib.sha256(
        canonical_json(
            {key: value for key, value in payload.items() if key != digest_field}
        ).encode("utf-8")
    ).hexdigest()


def semantics() -> OperationSemantics:
    return OperationSemantics.create(
        operation_id="system_control_plane_contract",
        capability="vone.control-plane.decide/v1",
        members=tuple(
            OperationMember(role=role, member_id=f"id_{role}") for role in MEMBER_ROLES
        ),
        techniques=tuple(
            TechniqueEvidence.from_name(name)
            for name in ("slsa", "mcp", "sigstore", "a2a", "aws_agentcore", "spiffe")
        ),
    )


def skill_plan() -> SkillOrchestrationPlan:
    return SkillOrchestrationPlan.create(
        task_id="system_control_plane_contract",
        task_type="architecture",
        source_of_truth="github:nulleimy/V-One/pull/69",
        objective="Unify V-One operation semantics, proof, and skill orchestration.",
        selected_skills=select_relevant_skills(task_type="architecture"),
        excluded_operations=(
            "runtime_plugin_trust",
            "tool_execution",
            "self_approval",
            "production_effect",
        ),
        acceptance_gates=(
            "decision_has_boundary",
            "decision_has_evidence",
            "decision_has_acceptance_gates",
            "decision_digest_matches_claims",
        ),
    )


def boundary() -> ControlPlaneBoundary:
    return ControlPlaneBoundary(
        boundary_type="contract_only",
        scope="Control-plane decision contract without runtime side effects.",
        allowed_effects=("canonical_decision_record",),
        prohibited_effects=("runtime_execution", "approval_bypass", "production_effect"),
    )


def evidence() -> tuple[EvidenceReference, ...]:
    return (
        EvidenceReference(
            evidence_type="operation_semantics",
            source="voodoo_product/operation_semantics.py",
            digest=semantics().semantics_digest,
        ),
        EvidenceReference(
            evidence_type="skill_orchestration",
            source="voodoo_product/skill_orchestration.py",
            digest=skill_plan().plan_digest,
        ),
    )


def gates(status: str = "PASS") -> tuple[AcceptanceGate, ...]:
    return (
        AcceptanceGate(
            gate="decision_has_boundary",
            status=status,
            evidence_digest=DIGEST_A,
        ),
        AcceptanceGate(
            gate="decision_has_evidence",
            status=status,
            evidence_digest=DIGEST_B,
        ),
        AcceptanceGate(
            gate="decision_has_acceptance_gates",
            status=status,
            evidence_digest=DIGEST_C,
        ),
    )


def decision(status: str = "IMPLEMENTED") -> VOneControlPlaneDecision:
    gate_status = "PENDING" if status == "IMPLEMENTED" else "PASS"
    return VOneControlPlaneDecision.create(
        decision_id="cpd_system_control_plane_contract",
        status=status,
        rationale="Contract exists, but runtime API integration is deliberately out of scope.",
        semantics=semantics(),
        skill_plan=skill_plan(),
        boundary=boundary(),
        evidence=evidence(),
        acceptance_gates=gates(gate_status),
    )


def test_control_plane_decision_is_deterministic_and_round_trippable() -> None:
    first = decision()
    second = decision()

    assert first.to_dict() == second.to_dict()
    assert first.operation_id == "system_control_plane_contract"
    assert first.capability == "vone.control-plane.decide/v1"
    assert first.decision_digest == digest_without(first.to_dict(), "decision_digest")
    assert VOneControlPlaneDecision.from_dict(first.to_dict()) == first


def test_control_plane_decision_requires_boundary_evidence_and_gates() -> None:
    with pytest.raises(ControlPlaneDecisionError, match="evidence is required"):
        VOneControlPlaneDecision.create(
            decision_id="cpd_missing_evidence",
            status="IMPLEMENTED",
            rationale="Missing evidence must fail closed.",
            semantics=semantics(),
            skill_plan=skill_plan(),
            boundary=boundary(),
            evidence=(),
            acceptance_gates=gates("PENDING"),
        )

    with pytest.raises(ControlPlaneDecisionError, match="acceptance_gates are required"):
        VOneControlPlaneDecision.create(
            decision_id="cpd_missing_gates",
            status="IMPLEMENTED",
            rationale="Missing gates must fail closed.",
            semantics=semantics(),
            skill_plan=skill_plan(),
            boundary=boundary(),
            evidence=evidence(),
            acceptance_gates=(),
        )


def test_verified_decision_requires_proof() -> None:
    with pytest.raises(ControlPlaneDecisionError, match="VERIFIED"):
        decision(status="VERIFIED")


def test_non_final_decision_requires_pending_or_blocked_gate() -> None:
    with pytest.raises(ControlPlaneDecisionError, match="non-final"):
        VOneControlPlaneDecision.create(
            decision_id="cpd_overclaimed",
            status="IMPLEMENTED",
            rationale="Implemented source must not be treated as fully verified.",
            semantics=semantics(),
            skill_plan=skill_plan(),
            boundary=boundary(),
            evidence=evidence(),
            acceptance_gates=gates("PASS"),
        )


def test_control_plane_decision_rejects_tampering() -> None:
    payload = decision().to_dict()
    payload["status"] = "VERIFIED"
    payload["decision_digest"] = digest_without(payload, "decision_digest")

    with pytest.raises(ControlPlaneDecisionError, match="VERIFIED"):
        VOneControlPlaneDecision.from_dict(payload)
