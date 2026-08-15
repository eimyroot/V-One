from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from .evidence_primitives import canonical_json

SCHEMA_VERSION = 1
POLICY_DECISION_TYPE = "v-one-policy-decision/v1"

POLICY_OUTCOMES = (
    "allow",
    "deny",
    "blocked",
    "needs_approval",
)


class PolicyDecisionError(ValueError):
    """Fail-closed error for one policy-as-code decision invariant."""


@dataclass(frozen=True, slots=True)
class PolicyObligation:
    obligation: str
    purpose: str
    system_benefit: str

    def __post_init__(self) -> None:
        _require_text(self.obligation, field="obligation")
        _require_text(self.purpose, field="purpose")
        _require_text(self.system_benefit, field="system_benefit")

    def to_dict(self) -> dict[str, str]:
        return {
            "obligation": self.obligation,
            "purpose": self.purpose,
            "system_benefit": self.system_benefit,
        }


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision_id: str
    policy_package: str
    policy_version: str
    bundle_digest: str
    input_schema_version: int
    input_digest: str
    outcome: str
    reasons: tuple[str, ...]
    violated_rules: tuple[str, ...]
    obligations: tuple[PolicyObligation, ...]
    purpose: str
    system_benefit: str
    decision_digest: str

    def __post_init__(self) -> None:
        for field in (
            "decision_id",
            "policy_package",
            "policy_version",
            "purpose",
            "system_benefit",
        ):
            _require_text(getattr(self, field), field=field)
        _require_digest(self.bundle_digest, field="bundle_digest")
        _require_digest(self.input_digest, field="input_digest")
        if not isinstance(self.input_schema_version, int) or self.input_schema_version < 1:
            raise PolicyDecisionError("input_schema_version is invalid")
        if self.outcome not in POLICY_OUTCOMES:
            raise PolicyDecisionError("policy outcome is unsupported")
        _require_text_tuple(self.reasons, field="reasons")
        if not all(isinstance(item, PolicyObligation) for item in self.obligations):
            raise PolicyDecisionError("obligations are invalid")
        _require_unique(self.violated_rules, field="violated_rules")
        _require_unique([item.obligation for item in self.obligations], field="obligations")
        if self.outcome == "allow" and self.violated_rules:
            raise PolicyDecisionError("allow decisions must not include violated rules")
        if self.outcome in {"deny", "blocked"} and not self.violated_rules:
            raise PolicyDecisionError("deny and blocked decisions require violated rules")
        if self.outcome == "needs_approval" and not self.obligations:
            raise PolicyDecisionError("needs_approval decisions require obligations")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise PolicyDecisionError("decision_digest does not match policy decision")

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        policy_package: str,
        policy_version: str,
        bundle_digest: str,
        input_schema_version: int,
        input_digest: str,
        outcome: str,
        reasons: tuple[str, ...],
        violated_rules: tuple[str, ...],
        obligations: tuple[PolicyObligation, ...],
        purpose: str,
        system_benefit: str,
    ) -> Self:
        claims = {
            "schema_version": SCHEMA_VERSION,
            "decision_type": POLICY_DECISION_TYPE,
            "decision_id": decision_id,
            "policy_package": policy_package,
            "policy_version": policy_version,
            "bundle_digest": bundle_digest,
            "input_schema_version": input_schema_version,
            "input_digest": input_digest,
            "outcome": outcome,
            "reasons": list(reasons),
            "violated_rules": list(violated_rules),
            "obligations": [item.to_dict() for item in obligations],
            "purpose": purpose,
            "system_benefit": system_benefit,
        }
        return cls(
            decision_id=decision_id,
            policy_package=policy_package,
            policy_version=policy_version,
            bundle_digest=bundle_digest,
            input_schema_version=input_schema_version,
            input_digest=input_digest,
            outcome=outcome,
            reasons=reasons,
            violated_rules=violated_rules,
            obligations=obligations,
            purpose=purpose,
            system_benefit=system_benefit,
            decision_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "decision_type",
                "decision_id",
                "policy_package",
                "policy_version",
                "bundle_digest",
                "input_schema_version",
                "input_digest",
                "outcome",
                "reasons",
                "violated_rules",
                "obligations",
                "purpose",
                "system_benefit",
                "decision_digest",
            }
        )
        _require_exact_fields(value, expected, contract=POLICY_DECISION_TYPE)
        if value["schema_version"] != SCHEMA_VERSION:
            raise PolicyDecisionError("schema_version is unsupported")
        if value["decision_type"] != POLICY_DECISION_TYPE:
            raise PolicyDecisionError("decision_type is unsupported")
        return cls(
            decision_id=value["decision_id"],
            policy_package=value["policy_package"],
            policy_version=value["policy_version"],
            bundle_digest=value["bundle_digest"],
            input_schema_version=value["input_schema_version"],
            input_digest=value["input_digest"],
            outcome=value["outcome"],
            reasons=tuple(value["reasons"]),
            violated_rules=tuple(value["violated_rules"]),
            obligations=tuple(_obligation_from_dict(item) for item in value["obligations"]),
            purpose=value["purpose"],
            system_benefit=value["system_benefit"],
            decision_digest=value["decision_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision_type": POLICY_DECISION_TYPE,
            "decision_id": self.decision_id,
            "policy_package": self.policy_package,
            "policy_version": self.policy_version,
            "bundle_digest": self.bundle_digest,
            "input_schema_version": self.input_schema_version,
            "input_digest": self.input_digest,
            "outcome": self.outcome,
            "reasons": list(self.reasons),
            "violated_rules": list(self.violated_rules),
            "obligations": [item.to_dict() for item in self.obligations],
            "purpose": self.purpose,
            "system_benefit": self.system_benefit,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["decision_digest"] = self.decision_digest
        return payload


def _obligation_from_dict(value: object) -> PolicyObligation:
    if not isinstance(value, Mapping) or set(value) != {
        "obligation",
        "purpose",
        "system_benefit",
    }:
        raise PolicyDecisionError("policy obligation fields are invalid")
    return PolicyObligation(
        obligation=value["obligation"],
        purpose=value["purpose"],
        system_benefit=value["system_benefit"],
    )


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise PolicyDecisionError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise PolicyDecisionError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


def _require_unique(values: tuple[str, ...] | list[str], *, field: str) -> None:
    if not all(isinstance(item, str) for item in values):
        raise PolicyDecisionError(f"{field} entries must be strings")
    if len(values) != len(set(values)):
        raise PolicyDecisionError(f"{field} entries must be unique")
    for item in values:
        _require_text(item, field=field)


def _require_text_tuple(values: tuple[str, ...], *, field: str) -> None:
    if not values or not all(isinstance(item, str) for item in values):
        raise PolicyDecisionError(f"{field} must be a non-empty tuple of strings")
    for item in values:
        _require_text(item, field=field)


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise PolicyDecisionError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PolicyDecisionError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
