from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from .evidence_primitives import canonical_json
from .skill_orchestration import DEVELOPMENT_USEFULNESS_GATE

SCHEMA_VERSION = 1
DEVELOPMENT_DECISION_TYPE = "v-one-development-decision/v1"

DEVELOPMENT_STATUSES = (
    "PROPOSED",
    "IMPLEMENTED",
    "VERIFIED",
    "BLOCKED",
    "FAILED",
    "UNKNOWN",
)


class DevelopmentDecisionError(ValueError):
    """Fail-closed error for a development decision record invariant."""


@dataclass(frozen=True, slots=True)
class DevelopmentDecisionRecord:
    change_id: str
    status: str
    purpose: str
    system_benefit: str
    boundary: str
    non_scope: tuple[str, ...]
    skill_plan_digest: str
    control_plane_decision_digest: str | None
    evidence_digests: tuple[str, ...]
    acceptance_gates: tuple[str, ...]
    rollback: str
    decision_digest: str

    def __post_init__(self) -> None:
        for field in ("change_id", "purpose", "system_benefit", "boundary", "rollback"):
            _require_text(getattr(self, field), field=field)
        if self.status not in DEVELOPMENT_STATUSES:
            raise DevelopmentDecisionError("development status is unsupported")
        _require_digest(self.skill_plan_digest, field="skill_plan_digest")
        if self.control_plane_decision_digest is not None:
            _require_digest(
                self.control_plane_decision_digest,
                field="control_plane_decision_digest",
            )
        _require_text_tuple(self.non_scope, field="non_scope")
        _require_digest_tuple(self.evidence_digests, field="evidence_digests")
        _require_text_tuple(self.acceptance_gates, field="acceptance_gates")
        if self.acceptance_gates.count(DEVELOPMENT_USEFULNESS_GATE) != 1:
            raise DevelopmentDecisionError("development usefulness gate is required")
        if self.status in {"IMPLEMENTED", "VERIFIED"} and not self.evidence_digests:
            raise DevelopmentDecisionError("implemented or verified changes require evidence")
        if self.status == "VERIFIED" and self.control_plane_decision_digest is None:
            raise DevelopmentDecisionError("verified changes require a control-plane decision")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise DevelopmentDecisionError("decision_digest does not match development decision")

    @classmethod
    def create(
        cls,
        *,
        change_id: str,
        status: str,
        purpose: str,
        system_benefit: str,
        boundary: str,
        non_scope: tuple[str, ...],
        skill_plan_digest: str,
        control_plane_decision_digest: str | None,
        evidence_digests: tuple[str, ...],
        acceptance_gates: tuple[str, ...],
        rollback: str,
    ) -> Self:
        claims = {
            "schema_version": SCHEMA_VERSION,
            "decision_type": DEVELOPMENT_DECISION_TYPE,
            "change_id": change_id,
            "status": status,
            "purpose": purpose,
            "system_benefit": system_benefit,
            "boundary": boundary,
            "non_scope": list(non_scope),
            "skill_plan_digest": skill_plan_digest,
            "control_plane_decision_digest": control_plane_decision_digest,
            "evidence_digests": list(evidence_digests),
            "acceptance_gates": list(acceptance_gates),
            "rollback": rollback,
        }
        return cls(
            change_id=change_id,
            status=status,
            purpose=purpose,
            system_benefit=system_benefit,
            boundary=boundary,
            non_scope=non_scope,
            skill_plan_digest=skill_plan_digest,
            control_plane_decision_digest=control_plane_decision_digest,
            evidence_digests=evidence_digests,
            acceptance_gates=acceptance_gates,
            rollback=rollback,
            decision_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "decision_type",
                "change_id",
                "status",
                "purpose",
                "system_benefit",
                "boundary",
                "non_scope",
                "skill_plan_digest",
                "control_plane_decision_digest",
                "evidence_digests",
                "acceptance_gates",
                "rollback",
                "decision_digest",
            }
        )
        _require_exact_fields(value, expected, contract=DEVELOPMENT_DECISION_TYPE)
        if value["schema_version"] != SCHEMA_VERSION:
            raise DevelopmentDecisionError("schema_version is unsupported")
        if value["decision_type"] != DEVELOPMENT_DECISION_TYPE:
            raise DevelopmentDecisionError("decision_type is unsupported")
        return cls(
            change_id=value["change_id"],
            status=value["status"],
            purpose=value["purpose"],
            system_benefit=value["system_benefit"],
            boundary=value["boundary"],
            non_scope=tuple(value["non_scope"]),
            skill_plan_digest=value["skill_plan_digest"],
            control_plane_decision_digest=value["control_plane_decision_digest"],
            evidence_digests=tuple(value["evidence_digests"]),
            acceptance_gates=tuple(value["acceptance_gates"]),
            rollback=value["rollback"],
            decision_digest=value["decision_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision_type": DEVELOPMENT_DECISION_TYPE,
            "change_id": self.change_id,
            "status": self.status,
            "purpose": self.purpose,
            "system_benefit": self.system_benefit,
            "boundary": self.boundary,
            "non_scope": list(self.non_scope),
            "skill_plan_digest": self.skill_plan_digest,
            "control_plane_decision_digest": self.control_plane_decision_digest,
            "evidence_digests": list(self.evidence_digests),
            "acceptance_gates": list(self.acceptance_gates),
            "rollback": self.rollback,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["decision_digest"] = self.decision_digest
        return payload


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise DevelopmentDecisionError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise DevelopmentDecisionError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


def _require_text_tuple(values: tuple[str, ...], *, field: str) -> None:
    if not values or not all(isinstance(item, str) for item in values):
        raise DevelopmentDecisionError(f"{field} must be a non-empty tuple of strings")
    for item in values:
        _require_text(item, field=field)


def _require_digest_tuple(values: tuple[str, ...], *, field: str) -> None:
    if not values or not all(isinstance(item, str) for item in values):
        raise DevelopmentDecisionError(f"{field} must be a non-empty tuple of digests")
    if len(values) != len(set(values)):
        raise DevelopmentDecisionError(f"{field} entries must be unique")
    for item in values:
        _require_digest(item, field=field)


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise DevelopmentDecisionError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise DevelopmentDecisionError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
