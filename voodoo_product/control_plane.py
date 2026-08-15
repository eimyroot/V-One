from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from .evidence_primitives import canonical_json
from .operation_proof import VERIFIED as PROOF_VERIFIED
from .operation_proof import OperationProof
from .operation_semantics import OperationSemantics
from .skill_orchestration import SkillOrchestrationPlan

SCHEMA_VERSION = 1
CONTROL_PLANE_DECISION_TYPE = "v-one-control-plane-decision/v1"

DECISION_STATUSES = (
    "VERIFIED",
    "IMPLEMENTED",
    "PROPOSED",
    "BLOCKED",
    "FAILED",
    "UNKNOWN",
)

BOUNDARY_TYPES = (
    "contract_only",
    "read_only",
    "local_control_plane",
    "external_provider",
    "production_effect",
)

GATE_STATUSES = (
    "PASS",
    "FAIL",
    "PENDING",
    "BLOCKED",
)

_FINAL_STATUSES = frozenset({"VERIFIED", "FAILED", "BLOCKED"})


class ControlPlaneDecisionError(ValueError):
    """Fail-closed error for one V-One control-plane decision invariant."""


@dataclass(frozen=True, slots=True)
class ControlPlaneBoundary:
    boundary_type: str
    scope: str
    allowed_effects: tuple[str, ...]
    prohibited_effects: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.boundary_type not in BOUNDARY_TYPES:
            raise ControlPlaneDecisionError("boundary_type is unsupported")
        _require_text(self.scope, field="scope")
        _require_text_tuple(self.allowed_effects, field="allowed_effects")
        _require_text_tuple(self.prohibited_effects, field="prohibited_effects")
        overlap = set(self.allowed_effects) & set(self.prohibited_effects)
        if overlap:
            raise ControlPlaneDecisionError(f"boundary effects overlap: {sorted(overlap)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "boundary_type": self.boundary_type,
            "scope": self.scope,
            "allowed_effects": list(self.allowed_effects),
            "prohibited_effects": list(self.prohibited_effects),
        }


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    evidence_type: str
    source: str
    digest: str

    def __post_init__(self) -> None:
        _require_text(self.evidence_type, field="evidence_type")
        _require_text(self.source, field="source")
        _require_digest(self.digest, field="digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_type": self.evidence_type,
            "source": self.source,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class AcceptanceGate:
    gate: str
    status: str
    evidence_digest: str

    def __post_init__(self) -> None:
        _require_text(self.gate, field="gate")
        if self.status not in GATE_STATUSES:
            raise ControlPlaneDecisionError("gate status is unsupported")
        _require_digest(self.evidence_digest, field="evidence_digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "gate": self.gate,
            "status": self.status,
            "evidence_digest": self.evidence_digest,
        }


@dataclass(frozen=True, slots=True)
class VOneControlPlaneDecision:
    decision_id: str
    operation_id: str
    capability: str
    status: str
    rationale: str
    semantics_digest: str
    skill_plan_digest: str
    proof_digest: str | None
    boundary: ControlPlaneBoundary
    evidence: tuple[EvidenceReference, ...]
    acceptance_gates: tuple[AcceptanceGate, ...]
    decision_digest: str

    def __post_init__(self) -> None:
        for field in ("decision_id", "operation_id", "capability", "rationale"):
            _require_text(getattr(self, field), field=field)
        if self.status not in DECISION_STATUSES:
            raise ControlPlaneDecisionError("decision status is unsupported")
        _require_digest(self.semantics_digest, field="semantics_digest")
        _require_digest(self.skill_plan_digest, field="skill_plan_digest")
        if self.proof_digest is not None:
            _require_digest(self.proof_digest, field="proof_digest")
        if not isinstance(self.boundary, ControlPlaneBoundary):
            raise ControlPlaneDecisionError("boundary is invalid")
        if not self.evidence or not all(isinstance(item, EvidenceReference) for item in self.evidence):
            raise ControlPlaneDecisionError("evidence is required")
        if not self.acceptance_gates or not all(
            isinstance(item, AcceptanceGate) for item in self.acceptance_gates
        ):
            raise ControlPlaneDecisionError("acceptance_gates are required")
        _require_unique([item.evidence_type for item in self.evidence], field="evidence")
        _require_unique([item.gate for item in self.acceptance_gates], field="acceptance_gates")
        _require_status_matches_gates(self.status, self.acceptance_gates)
        if self.status == "VERIFIED" and self.proof_digest is None:
            raise ControlPlaneDecisionError("VERIFIED decisions require an operation proof")
        if self.status in {"FAILED", "BLOCKED"} and self.proof_digest is not None:
            raise ControlPlaneDecisionError("failed or blocked decisions must not carry proof")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise ControlPlaneDecisionError("decision_digest does not match decision claims")

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        status: str,
        rationale: str,
        semantics: OperationSemantics,
        skill_plan: SkillOrchestrationPlan,
        boundary: ControlPlaneBoundary,
        evidence: tuple[EvidenceReference, ...],
        acceptance_gates: tuple[AcceptanceGate, ...],
        proof: OperationProof | None = None,
    ) -> Self:
        if not isinstance(semantics, OperationSemantics):
            raise ControlPlaneDecisionError("semantics must be operation-semantics/v1")
        if not isinstance(skill_plan, SkillOrchestrationPlan):
            raise ControlPlaneDecisionError("skill_plan must be skill-orchestration-plan/v1")
        if proof is not None and not isinstance(proof, OperationProof):
            raise ControlPlaneDecisionError("proof must be operation-proof/v1")
        if proof is not None:
            _require_proof_binding(semantics=semantics, proof=proof)
        claims = {
            "schema_version": SCHEMA_VERSION,
            "decision_type": CONTROL_PLANE_DECISION_TYPE,
            "decision_id": decision_id,
            "operation_id": semantics.operation_id,
            "capability": semantics.capability,
            "status": status,
            "rationale": rationale,
            "semantics_digest": semantics.semantics_digest,
            "skill_plan_digest": skill_plan.plan_digest,
            "proof_digest": proof.proof_digest if proof is not None else None,
            "boundary": boundary.to_dict(),
            "evidence": [item.to_dict() for item in evidence],
            "acceptance_gates": [item.to_dict() for item in acceptance_gates],
        }
        return cls(
            decision_id=decision_id,
            operation_id=semantics.operation_id,
            capability=semantics.capability,
            status=status,
            rationale=rationale,
            semantics_digest=semantics.semantics_digest,
            skill_plan_digest=skill_plan.plan_digest,
            proof_digest=proof.proof_digest if proof is not None else None,
            boundary=boundary,
            evidence=evidence,
            acceptance_gates=acceptance_gates,
            decision_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "decision_type",
                "decision_id",
                "operation_id",
                "capability",
                "status",
                "rationale",
                "semantics_digest",
                "skill_plan_digest",
                "proof_digest",
                "boundary",
                "evidence",
                "acceptance_gates",
                "decision_digest",
            }
        )
        _require_exact_fields(value, expected, contract=CONTROL_PLANE_DECISION_TYPE)
        if value["schema_version"] != SCHEMA_VERSION:
            raise ControlPlaneDecisionError("schema_version is unsupported")
        if value["decision_type"] != CONTROL_PLANE_DECISION_TYPE:
            raise ControlPlaneDecisionError("decision_type is unsupported")
        boundary = _boundary_from_dict(value["boundary"])
        evidence = _evidence_from_array(value["evidence"])
        gates = _gates_from_array(value["acceptance_gates"])
        return cls(
            decision_id=value["decision_id"],
            operation_id=value["operation_id"],
            capability=value["capability"],
            status=value["status"],
            rationale=value["rationale"],
            semantics_digest=value["semantics_digest"],
            skill_plan_digest=value["skill_plan_digest"],
            proof_digest=value["proof_digest"],
            boundary=boundary,
            evidence=evidence,
            acceptance_gates=gates,
            decision_digest=value["decision_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision_type": CONTROL_PLANE_DECISION_TYPE,
            "decision_id": self.decision_id,
            "operation_id": self.operation_id,
            "capability": self.capability,
            "status": self.status,
            "rationale": self.rationale,
            "semantics_digest": self.semantics_digest,
            "skill_plan_digest": self.skill_plan_digest,
            "proof_digest": self.proof_digest,
            "boundary": self.boundary.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "acceptance_gates": [item.to_dict() for item in self.acceptance_gates],
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["decision_digest"] = self.decision_digest
        return payload


def _require_proof_binding(*, semantics: OperationSemantics, proof: OperationProof) -> None:
    if proof.operation_id != semantics.operation_id:
        raise ControlPlaneDecisionError("proof operation_id does not match semantics")
    if proof.capability != semantics.capability:
        raise ControlPlaneDecisionError("proof capability does not match semantics")
    if proof.semantics_digest != semantics.semantics_digest:
        raise ControlPlaneDecisionError("proof semantics_digest does not match semantics")
    if proof.final_verdict != PROOF_VERIFIED:
        raise ControlPlaneDecisionError("proof must be VERIFIED for a control-plane decision")


def _require_status_matches_gates(
    status: str,
    gates: tuple[AcceptanceGate, ...],
) -> None:
    gate_statuses = {item.status for item in gates}
    if status == "VERIFIED" and gate_statuses != {"PASS"}:
        raise ControlPlaneDecisionError("VERIFIED decisions require all gates to PASS")
    if status == "FAILED" and "FAIL" not in gate_statuses:
        raise ControlPlaneDecisionError("FAILED decisions require at least one failed gate")
    if status == "BLOCKED" and "BLOCKED" not in gate_statuses:
        raise ControlPlaneDecisionError("BLOCKED decisions require at least one blocked gate")
    if status not in _FINAL_STATUSES and gate_statuses <= {"PASS"}:
        raise ControlPlaneDecisionError("non-final decisions require pending or blocked evidence")


def _boundary_from_dict(value: object) -> ControlPlaneBoundary:
    if not isinstance(value, Mapping) or set(value) != {
        "boundary_type",
        "scope",
        "allowed_effects",
        "prohibited_effects",
    }:
        raise ControlPlaneDecisionError("boundary fields are invalid")
    return ControlPlaneBoundary(
        boundary_type=value["boundary_type"],
        scope=value["scope"],
        allowed_effects=tuple(value["allowed_effects"]),
        prohibited_effects=tuple(value["prohibited_effects"]),
    )


def _evidence_from_array(value: object) -> tuple[EvidenceReference, ...]:
    if not isinstance(value, list):
        raise ControlPlaneDecisionError("evidence must be an array")
    return tuple(_evidence_from_dict(item) for item in value)


def _evidence_from_dict(value: object) -> EvidenceReference:
    if not isinstance(value, Mapping) or set(value) != {
        "evidence_type",
        "source",
        "digest",
    }:
        raise ControlPlaneDecisionError("evidence fields are invalid")
    return EvidenceReference(
        evidence_type=value["evidence_type"],
        source=value["source"],
        digest=value["digest"],
    )


def _gates_from_array(value: object) -> tuple[AcceptanceGate, ...]:
    if not isinstance(value, list):
        raise ControlPlaneDecisionError("acceptance_gates must be an array")
    return tuple(_gate_from_dict(item) for item in value)


def _gate_from_dict(value: object) -> AcceptanceGate:
    if not isinstance(value, Mapping) or set(value) != {
        "gate",
        "status",
        "evidence_digest",
    }:
        raise ControlPlaneDecisionError("acceptance gate fields are invalid")
    return AcceptanceGate(
        gate=value["gate"],
        status=value["status"],
        evidence_digest=value["evidence_digest"],
    )


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ControlPlaneDecisionError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ControlPlaneDecisionError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


def _require_unique(values: list[str], *, field: str) -> None:
    if len(values) != len(set(values)):
        raise ControlPlaneDecisionError(f"{field} entries must be unique")


def _require_text_tuple(values: tuple[str, ...], *, field: str) -> None:
    if not values or not all(isinstance(item, str) for item in values):
        raise ControlPlaneDecisionError(f"{field} must be a non-empty tuple of strings")
    for item in values:
        _require_text(item, field=field)


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ControlPlaneDecisionError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ControlPlaneDecisionError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
