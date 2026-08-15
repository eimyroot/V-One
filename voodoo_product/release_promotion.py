from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from .evidence_primitives import canonical_json

SCHEMA_VERSION = 1
RELEASE_PROMOTION_DECISION_TYPE = "v-one-release-promotion-decision/v1"

RELEASE_STATES = (
    "IMPLEMENTED",
    "VERIFIED",
    "RELEASE_CANDIDATE",
    "RELEASED",
    "BLOCKED",
)

ALLOWED_RELEASE_TRANSITIONS = frozenset(
    {
        ("IMPLEMENTED", "VERIFIED"),
        ("VERIFIED", "RELEASE_CANDIDATE"),
        ("RELEASE_CANDIDATE", "RELEASED"),
        ("IMPLEMENTED", "BLOCKED"),
        ("VERIFIED", "BLOCKED"),
        ("RELEASE_CANDIDATE", "BLOCKED"),
    }
)


class ReleasePromotionError(ValueError):
    """Fail-closed error for a release promotion invariant."""


@dataclass(frozen=True, slots=True)
class ReleasePromotionDecision:
    release_id: str
    source_state: str
    target_state: str
    purpose: str
    system_benefit: str
    evidence_digests: tuple[str, ...]
    acceptance_gates: tuple[str, ...]
    rollback_plan: str
    promoted_by: str
    decision_digest: str

    def __post_init__(self) -> None:
        for field in ("release_id", "purpose", "system_benefit", "rollback_plan", "promoted_by"):
            _require_text(getattr(self, field), field=field)
        if self.source_state not in RELEASE_STATES:
            raise ReleasePromotionError("source_state is unsupported")
        if self.target_state not in RELEASE_STATES:
            raise ReleasePromotionError("target_state is unsupported")
        if (self.source_state, self.target_state) not in ALLOWED_RELEASE_TRANSITIONS:
            raise ReleasePromotionError("release promotion transition is not allowed")
        _require_digest_tuple(self.evidence_digests, field="evidence_digests")
        _require_text_tuple(self.acceptance_gates, field="acceptance_gates")
        if self.target_state == "RELEASED" and "production_release_authorized" not in self.acceptance_gates:
            raise ReleasePromotionError("RELEASED requires production_release_authorized gate")
        if self.target_state == "BLOCKED" and "blocker_recorded" not in self.acceptance_gates:
            raise ReleasePromotionError("BLOCKED requires blocker_recorded gate")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise ReleasePromotionError("decision_digest does not match release promotion")

    @classmethod
    def create(
        cls,
        *,
        release_id: str,
        source_state: str,
        target_state: str,
        purpose: str,
        system_benefit: str,
        evidence_digests: tuple[str, ...],
        acceptance_gates: tuple[str, ...],
        rollback_plan: str,
        promoted_by: str,
    ) -> Self:
        claims = {
            "schema_version": SCHEMA_VERSION,
            "decision_type": RELEASE_PROMOTION_DECISION_TYPE,
            "release_id": release_id,
            "source_state": source_state,
            "target_state": target_state,
            "purpose": purpose,
            "system_benefit": system_benefit,
            "evidence_digests": list(evidence_digests),
            "acceptance_gates": list(acceptance_gates),
            "rollback_plan": rollback_plan,
            "promoted_by": promoted_by,
        }
        return cls(
            release_id=release_id,
            source_state=source_state,
            target_state=target_state,
            purpose=purpose,
            system_benefit=system_benefit,
            evidence_digests=evidence_digests,
            acceptance_gates=acceptance_gates,
            rollback_plan=rollback_plan,
            promoted_by=promoted_by,
            decision_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "decision_type",
                "release_id",
                "source_state",
                "target_state",
                "purpose",
                "system_benefit",
                "evidence_digests",
                "acceptance_gates",
                "rollback_plan",
                "promoted_by",
                "decision_digest",
            }
        )
        _require_exact_fields(value, expected, contract=RELEASE_PROMOTION_DECISION_TYPE)
        if value["schema_version"] != SCHEMA_VERSION:
            raise ReleasePromotionError("schema_version is unsupported")
        if value["decision_type"] != RELEASE_PROMOTION_DECISION_TYPE:
            raise ReleasePromotionError("decision_type is unsupported")
        return cls(
            release_id=value["release_id"],
            source_state=value["source_state"],
            target_state=value["target_state"],
            purpose=value["purpose"],
            system_benefit=value["system_benefit"],
            evidence_digests=tuple(value["evidence_digests"]),
            acceptance_gates=tuple(value["acceptance_gates"]),
            rollback_plan=value["rollback_plan"],
            promoted_by=value["promoted_by"],
            decision_digest=value["decision_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision_type": RELEASE_PROMOTION_DECISION_TYPE,
            "release_id": self.release_id,
            "source_state": self.source_state,
            "target_state": self.target_state,
            "purpose": self.purpose,
            "system_benefit": self.system_benefit,
            "evidence_digests": list(self.evidence_digests),
            "acceptance_gates": list(self.acceptance_gates),
            "rollback_plan": self.rollback_plan,
            "promoted_by": self.promoted_by,
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
        raise ReleasePromotionError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ReleasePromotionError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


def _require_text_tuple(values: tuple[str, ...], *, field: str) -> None:
    if not values or not all(isinstance(item, str) for item in values):
        raise ReleasePromotionError(f"{field} must be a non-empty tuple of strings")
    if len(values) != len(set(values)):
        raise ReleasePromotionError(f"{field} entries must be unique")
    for item in values:
        _require_text(item, field=field)


def _require_digest_tuple(values: tuple[str, ...], *, field: str) -> None:
    if not values or not all(isinstance(item, str) for item in values):
        raise ReleasePromotionError(f"{field} must be a non-empty tuple of digests")
    if len(values) != len(set(values)):
        raise ReleasePromotionError(f"{field} entries must be unique")
    for item in values:
        _require_digest(item, field=field)


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ReleasePromotionError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReleasePromotionError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
