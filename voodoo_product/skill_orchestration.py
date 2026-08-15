from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Self

from .evidence_primitives import canonical_json

SCHEMA_VERSION = 1
SKILL_ORCHESTRATION_PLAN_TYPE = "v-one-skill-orchestration-plan/v1"
PRIMARY_COORDINATOR = "governed-workflow-orchestrator"
DEVELOPMENT_USEFULNESS_GATE = "change_has_purpose_and_system_benefit"

TASK_TYPES = (
    "bugfix",
    "feature",
    "architecture",
    "security",
    "ci_cd",
    "documentation",
    "product",
    "release",
    "incident",
)

SKILL_ROLES = (
    "coordinator",
    "canonical_owner",
    "specialist",
    "verifier",
    "supporting_overlay",
)

_SKILL_CATALOG = {
    "governed-workflow-orchestrator": {
        "role": "coordinator",
        "purpose": "Coordinates bounded, restartable, evidence-backed work into one output.",
        "authority": "workflow_framing",
        "task_types": TASK_TYPES,
    },
    "systematic-debugging-and-root-cause-engineer": {
        "role": "specialist",
        "purpose": "Finds the first causal failure before proposing a minimal fix.",
        "authority": "root_cause_diagnosis",
        "task_types": ("bugfix", "ci_cd", "incident"),
    },
    "platform-engineering-architect": {
        "role": "canonical_owner",
        "purpose": "Preserves platform boundaries, ownership, and source-of-truth shape.",
        "authority": "platform_architecture",
        "task_types": ("architecture", "feature", "product"),
    },
    "quality-evidence-verifier": {
        "role": "verifier",
        "purpose": "Checks that claimed outcomes are supported by reproducible evidence.",
        "authority": "evidence_sufficiency",
        "task_types": TASK_TYPES,
    },
    "api-and-contract-governor": {
        "role": "canonical_owner",
        "purpose": "Owns HTTP, RPC, event, schema, and compatibility contracts.",
        "authority": "api_contract",
        "task_types": ("feature", "architecture"),
    },
    "documentation-governor": {
        "role": "canonical_owner",
        "purpose": "Keeps documentation from claiming more than current evidence proves.",
        "authority": "documentation_truth",
        "task_types": ("documentation", "product", "release"),
    },
    "release-and-progressive-delivery-governor": {
        "role": "canonical_owner",
        "purpose": "Owns release integrity, rollout, rollback, and production promotion gates.",
        "authority": "release_governance",
        "task_types": ("release",),
    },
    "security-baseline": {
        "role": "specialist",
        "purpose": "Checks baseline security controls and unsafe default states.",
        "authority": "security_baseline",
        "task_types": ("security", "release", "incident"),
    },
    "application-security-and-threat-model-engineer": {
        "role": "specialist",
        "purpose": "Assesses application threat boundaries and abuse paths.",
        "authority": "application_threat_model",
        "task_types": ("security", "architecture", "feature"),
    },
    "identity-secrets-and-access-governor": {
        "role": "canonical_owner",
        "purpose": "Owns identity, secrets, access, and credential-boundary decisions.",
        "authority": "identity_and_secrets",
        "task_types": ("security", "release", "incident"),
    },
    "observability-and-telemetry-architect": {
        "role": "specialist",
        "purpose": "Designs logs, metrics, traces, correlation, and learning signals.",
        "authority": "observability_design",
        "task_types": ("architecture", "incident", "product"),
    },
    "supply-chain-provenance-governor": {
        "role": "canonical_owner",
        "purpose": "Owns source, build, artifact, attestation, and provenance controls.",
        "authority": "supply_chain_provenance",
        "task_types": ("release", "security", "ci_cd"),
    },
    "performance-and-capacity-engineer": {
        "role": "specialist",
        "purpose": "Assesses latency, throughput, resource, and scalability constraints.",
        "authority": "performance_capacity",
        "task_types": ("product", "architecture", "incident"),
    },
    "product-value-and-discovery-governor": {
        "role": "supporting_overlay",
        "purpose": "Checks product value, customer fit, and practical adoption sequence.",
        "authority": "product_discovery",
        "task_types": ("product",),
    },
}


@dataclass(frozen=True, slots=True)
class SkillSelection:
    skill: str
    role: str
    purpose: str
    authority: str
    selected: bool
    reason: str

    def __post_init__(self) -> None:
        if self.skill not in _SKILL_CATALOG:
            raise ValueError("skill is not in the governed V-One skill catalog")
        expected = _SKILL_CATALOG[self.skill]
        if self.role != expected["role"]:
            raise ValueError("skill role does not match the governed catalog")
        if self.purpose != expected["purpose"]:
            raise ValueError("skill purpose does not match the governed catalog")
        if self.authority != expected["authority"]:
            raise ValueError("skill authority does not match the governed catalog")
        if self.role not in SKILL_ROLES:
            raise ValueError("skill role is unsupported")
        _require_text(self.reason, field="reason")

    @classmethod
    def create(cls, *, skill: str, selected: bool, reason: str) -> Self:
        _require_text(skill, field="skill")
        item = _SKILL_CATALOG.get(skill)
        if item is None:
            raise ValueError("skill is not in the governed V-One skill catalog")
        return cls(
            skill=skill,
            role=item["role"],
            purpose=item["purpose"],
            authority=item["authority"],
            selected=selected,
            reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "role": self.role,
            "purpose": self.purpose,
            "authority": self.authority,
            "selected": self.selected,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SkillOrchestrationPlan:
    task_id: str
    task_type: str
    source_of_truth: str
    objective: str
    purpose: str
    system_benefit: str
    primary_coordinator: str
    selections: tuple[SkillSelection, ...]
    excluded_operations: tuple[str, ...]
    acceptance_gates: tuple[str, ...]
    plan_digest: str

    def __post_init__(self) -> None:
        for field in ("task_id", "source_of_truth", "objective", "purpose", "system_benefit"):
            _require_text(getattr(self, field), field=field)
        if self.task_type not in TASK_TYPES:
            raise ValueError("task_type is unsupported")
        if self.primary_coordinator != PRIMARY_COORDINATOR:
            raise ValueError("primary coordinator must be governed-workflow-orchestrator")
        if not self.selections:
            raise ValueError("selections are required")
        if not all(isinstance(item, SkillSelection) for item in self.selections):
            raise ValueError("selections are invalid")
        _require_exact_catalog_coverage(self.selections)
        _require_single_selected_coordinator(self.selections)
        _require_selected_relevance(self.task_type, self.selections)
        _require_no_authority_overlap(self.selections)
        _require_text_tuple(self.excluded_operations, field="excluded_operations")
        _require_text_tuple(self.acceptance_gates, field="acceptance_gates")
        _require_development_usefulness_gate(self.acceptance_gates)
        if self.plan_digest != _digest(self._claims_without_digest()):
            raise ValueError("plan_digest does not match skill orchestration plan")

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        task_type: str,
        source_of_truth: str,
        objective: str,
        purpose: str,
        system_benefit: str,
        selected_skills: tuple[str, ...],
        excluded_operations: tuple[str, ...],
        acceptance_gates: tuple[str, ...],
    ) -> Self:
        _require_text(task_id, field="task_id")
        _require_text(source_of_truth, field="source_of_truth")
        _require_text(objective, field="objective")
        _require_text(purpose, field="purpose")
        _require_text(system_benefit, field="system_benefit")
        if task_type not in TASK_TYPES:
            raise ValueError("task_type is unsupported")
        selected = frozenset(selected_skills) | {PRIMARY_COORDINATOR}
        unknown = sorted(selected - set(_SKILL_CATALOG))
        if unknown:
            raise ValueError(f"selected skills are unknown: {unknown}")
        selections = tuple(
            SkillSelection.create(
                skill=skill,
                selected=skill in selected,
                reason=_selection_reason(
                    skill=skill,
                    task_type=task_type,
                    selected=skill in selected,
                ),
            )
            for skill in sorted(_SKILL_CATALOG)
        )
        claims = {
            "schema_version": SCHEMA_VERSION,
            "plan_type": SKILL_ORCHESTRATION_PLAN_TYPE,
            "task_id": task_id,
            "task_type": task_type,
            "source_of_truth": source_of_truth,
            "objective": objective,
            "purpose": purpose,
            "system_benefit": system_benefit,
            "primary_coordinator": PRIMARY_COORDINATOR,
            "selections": [item.to_dict() for item in selections],
            "excluded_operations": list(excluded_operations),
            "acceptance_gates": list(acceptance_gates),
        }
        return cls(
            task_id=task_id,
            task_type=task_type,
            source_of_truth=source_of_truth,
            objective=objective,
            purpose=purpose,
            system_benefit=system_benefit,
            primary_coordinator=PRIMARY_COORDINATOR,
            selections=selections,
            excluded_operations=excluded_operations,
            acceptance_gates=acceptance_gates,
            plan_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        expected = {
            "schema_version",
            "plan_type",
            "task_id",
            "task_type",
            "source_of_truth",
            "objective",
            "purpose",
            "system_benefit",
            "primary_coordinator",
            "selections",
            "excluded_operations",
            "acceptance_gates",
            "plan_digest",
        }
        if set(value) != expected:
            raise ValueError("skill orchestration plan fields are invalid")
        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError("schema_version is unsupported")
        if value["plan_type"] != SKILL_ORCHESTRATION_PLAN_TYPE:
            raise ValueError("plan_type is unsupported")
        selections = value["selections"]
        if not isinstance(selections, list):
            raise ValueError("selections must be an array")
        return cls(
            task_id=value["task_id"],
            task_type=value["task_type"],
            source_of_truth=value["source_of_truth"],
            objective=value["objective"],
            purpose=value["purpose"],
            system_benefit=value["system_benefit"],
            primary_coordinator=value["primary_coordinator"],
            selections=tuple(_selection_from_dict(item) for item in selections),
            excluded_operations=tuple(value["excluded_operations"]),
            acceptance_gates=tuple(value["acceptance_gates"]),
            plan_digest=value["plan_digest"],
        )

    @property
    def selected_skills(self) -> tuple[str, ...]:
        return tuple(item.skill for item in self.selections if item.selected)

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_type": SKILL_ORCHESTRATION_PLAN_TYPE,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "source_of_truth": self.source_of_truth,
            "objective": self.objective,
            "purpose": self.purpose,
            "system_benefit": self.system_benefit,
            "primary_coordinator": self.primary_coordinator,
            "selections": [item.to_dict() for item in self.selections],
            "excluded_operations": list(self.excluded_operations),
            "acceptance_gates": list(self.acceptance_gates),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["plan_digest"] = self.plan_digest
        return payload


def select_relevant_skills(*, task_type: str) -> tuple[str, ...]:
    if task_type not in TASK_TYPES:
        raise ValueError("task_type is unsupported")
    selected = [
        skill
        for skill, item in _SKILL_CATALOG.items()
        if task_type in item["task_types"]
    ]
    return tuple(sorted(set(selected) | {PRIMARY_COORDINATOR}))


def _selection_from_dict(value: object) -> SkillSelection:
    if not isinstance(value, dict) or set(value) != {
        "skill",
        "role",
        "purpose",
        "authority",
        "selected",
        "reason",
    }:
        raise ValueError("skill selection fields are invalid")
    return SkillSelection(
        skill=value["skill"],
        role=value["role"],
        purpose=value["purpose"],
        authority=value["authority"],
        selected=value["selected"],
        reason=value["reason"],
    )


def _selection_reason(*, skill: str, task_type: str, selected: bool) -> str:
    if selected:
        if skill == PRIMARY_COORDINATOR:
            return "selected as the single coordinator for unified workflow output"
        return f"selected because it owns or supports {task_type} work"
    return f"not selected because it does not materially reduce {task_type} risk"


def _require_exact_catalog_coverage(selections: tuple[SkillSelection, ...]) -> None:
    skills = [item.skill for item in selections]
    if set(skills) != set(_SKILL_CATALOG):
        raise ValueError("skill selections must cover the governed catalog exactly")
    if len(skills) != len(set(skills)):
        raise ValueError("skill selections must not contain duplicates")
    if tuple(skills) != tuple(sorted(skills)):
        raise ValueError("skill selections must be canonically ordered")


def _require_single_selected_coordinator(selections: tuple[SkillSelection, ...]) -> None:
    selected_coordinators = [
        item.skill
        for item in selections
        if item.selected and item.role == "coordinator"
    ]
    if selected_coordinators != [PRIMARY_COORDINATOR]:
        raise ValueError("exactly one primary coordinator must be selected")


def _require_selected_relevance(
    task_type: str,
    selections: tuple[SkillSelection, ...],
) -> None:
    for item in selections:
        if not item.selected:
            continue
        if task_type not in _SKILL_CATALOG[item.skill]["task_types"]:
            raise ValueError("selected skill is not relevant for task_type")


def _require_no_authority_overlap(selections: tuple[SkillSelection, ...]) -> None:
    selected = [item for item in selections if item.selected]
    owners = [
        item.authority
        for item in selected
        if item.role in {"coordinator", "canonical_owner"}
    ]
    if len(owners) != len(set(owners)):
        raise ValueError("selected canonical authorities must not overlap")


def _require_development_usefulness_gate(acceptance_gates: tuple[str, ...]) -> None:
    if acceptance_gates.count(DEVELOPMENT_USEFULNESS_GATE) != 1:
        raise ValueError("development usefulness gate is required")


def _require_text_tuple(values: tuple[str, ...], *, field: str) -> None:
    if not values or not all(isinstance(item, str) for item in values):
        raise ValueError(f"{field} must be a non-empty tuple of strings")
    for item in values:
        _require_text(item, field=field)


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
