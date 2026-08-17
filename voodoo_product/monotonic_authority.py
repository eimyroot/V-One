from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .authorization_snapshot import AuthorizationSnapshot
from .evidence_primitives import canonical_json
from .execution_contract import ONE_TIME_USE, REQUIRED_EXECUTION_PERMISSION

AUTHORITY_SCOPE_TYPE: Final = "authority-scope/v1"
AUTHORITY_CONSTRAINT_TYPE: Final = "authority-constraint/v1"
MONOTONIC_AUTHORITY_DECISION_TYPE: Final = "monotonic-authority-decision/v1"
NARROW_OR_EQUAL: Final = "NARROW_OR_EQUAL"

_SCOPE_FIELDS = frozenset(
    {
        "schema_version",
        "scope_type",
        "authorization_snapshot_digest",
        "actor_id",
        "workspace_id",
        "environment",
        "capability",
        "capability_definition_identity",
        "target_kind",
        "target_digest",
        "payload_digest",
        "policy_version",
        "policy_identity",
        "approval_set_digest",
        "required_permission",
        "valid_from",
        "valid_until",
        "scope_digest",
    }
)
_CONSTRAINT_FIELDS = frozenset(
    {
        "schema_version",
        "constraint_type",
        "parent_scope_digest",
        "actor_id",
        "workspace_id",
        "environment",
        "capability",
        "capability_definition_identity",
        "target_kind",
        "target_digest",
        "payload_digest",
        "policy_version",
        "policy_identity",
        "approval_set_digest",
        "required_permission",
        "valid_from",
        "valid_until",
        "use_semantics",
        "constraint_digest",
    }
)
_DECISION_FIELDS = frozenset(
    {
        "schema_version",
        "decision_type",
        "parent_scope_digest",
        "child_constraint_digest",
        "relation",
        "decision_digest",
    }
)
_EXACT_BINDINGS = (
    "actor_id",
    "workspace_id",
    "environment",
    "capability",
    "capability_definition_identity",
    "target_kind",
    "target_digest",
    "payload_digest",
    "policy_version",
    "policy_identity",
    "approval_set_digest",
    "required_permission",
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _require_timestamp(value: object, *, field: str) -> tuple[str, datetime]:
    text = _require_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return text, parsed.astimezone(UTC)


def _require_interval(valid_from: object, valid_until: object) -> tuple[str, str]:
    start_text, start = _require_timestamp(valid_from, field="valid_from")
    end_text, end = _require_timestamp(valid_until, field="valid_until")
    if end <= start:
        raise ValueError("authority validity interval must be positive")
    return start_text, end_text


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


@dataclass(frozen=True, slots=True)
class AuthorityScope:
    authorization_snapshot_digest: str
    actor_id: str
    workspace_id: str
    environment: str
    capability: str
    capability_definition_identity: str
    target_kind: str
    target_digest: str
    payload_digest: str
    policy_version: str
    policy_identity: str
    approval_set_digest: str
    required_permission: str
    valid_from: str
    valid_until: str
    scope_digest: str

    def __post_init__(self) -> None:
        _require_digest(
            self.authorization_snapshot_digest,
            field="authorization_snapshot_digest",
        )
        for field in (
            "actor_id",
            "workspace_id",
            "environment",
            "capability",
            "capability_definition_identity",
            "target_kind",
            "policy_version",
            "required_permission",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "payload_digest",
            "policy_identity",
            "approval_set_digest",
            "scope_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.required_permission != REQUIRED_EXECUTION_PERMISSION:
            raise ValueError("required_permission must be execution.run")
        _require_interval(self.valid_from, self.valid_until)
        if self.scope_digest != _digest(self._claims_without_digest()):
            raise ValueError("scope_digest does not match authority scope")

    @classmethod
    def from_snapshot(cls, snapshot: AuthorizationSnapshot) -> Self:
        if not isinstance(snapshot, AuthorizationSnapshot):
            raise ValueError("snapshot is invalid")
        claims = {
            "schema_version": 1,
            "scope_type": AUTHORITY_SCOPE_TYPE,
            "authorization_snapshot_digest": snapshot.snapshot_digest,
            "actor_id": snapshot.actor_id,
            "workspace_id": snapshot.workspace_id,
            "environment": snapshot.environment,
            "capability": snapshot.capability,
            "capability_definition_identity": snapshot.capability_definition_identity,
            "target_kind": snapshot.target_kind,
            "target_digest": snapshot.target_digest,
            "payload_digest": snapshot.payload_digest,
            "policy_version": snapshot.policy_version,
            "policy_identity": snapshot.policy_identity,
            "approval_set_digest": snapshot.approval_set_digest,
            "required_permission": REQUIRED_EXECUTION_PERMISSION,
            "valid_from": snapshot.authorized_at,
            "valid_until": snapshot.approval_valid_until,
        }
        values = {
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "scope_type"}
        }
        return cls(**values, scope_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _SCOPE_FIELDS, contract=AUTHORITY_SCOPE_TYPE)
        if value["schema_version"] != 1 or value["scope_type"] != AUTHORITY_SCOPE_TYPE:
            raise ValueError("authority-scope/v1 schema or type is unsupported")
        return cls(
            authorization_snapshot_digest=value["authorization_snapshot_digest"],
            actor_id=value["actor_id"],
            workspace_id=value["workspace_id"],
            environment=value["environment"],
            capability=value["capability"],
            capability_definition_identity=value["capability_definition_identity"],
            target_kind=value["target_kind"],
            target_digest=value["target_digest"],
            payload_digest=value["payload_digest"],
            policy_version=value["policy_version"],
            policy_identity=value["policy_identity"],
            approval_set_digest=value["approval_set_digest"],
            required_permission=value["required_permission"],
            valid_from=value["valid_from"],
            valid_until=value["valid_until"],
            scope_digest=value["scope_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "scope_type": AUTHORITY_SCOPE_TYPE,
            "authorization_snapshot_digest": self.authorization_snapshot_digest,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "capability": self.capability,
            "capability_definition_identity": self.capability_definition_identity,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "payload_digest": self.payload_digest,
            "policy_version": self.policy_version,
            "policy_identity": self.policy_identity,
            "approval_set_digest": self.approval_set_digest,
            "required_permission": self.required_permission,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "scope_digest": self.scope_digest}


@dataclass(frozen=True, slots=True)
class AuthorityConstraint:
    parent_scope_digest: str
    actor_id: str
    workspace_id: str
    environment: str
    capability: str
    capability_definition_identity: str
    target_kind: str
    target_digest: str
    payload_digest: str
    policy_version: str
    policy_identity: str
    approval_set_digest: str
    required_permission: str
    valid_from: str
    valid_until: str
    use_semantics: str
    constraint_digest: str

    def __post_init__(self) -> None:
        _require_digest(self.parent_scope_digest, field="parent_scope_digest")
        for field in (
            "actor_id",
            "workspace_id",
            "environment",
            "capability",
            "capability_definition_identity",
            "target_kind",
            "policy_version",
            "required_permission",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "target_digest",
            "payload_digest",
            "policy_identity",
            "approval_set_digest",
            "constraint_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.required_permission != REQUIRED_EXECUTION_PERMISSION:
            raise ValueError("required_permission must be execution.run")
        if self.use_semantics != ONE_TIME_USE:
            raise ValueError("use_semantics must be ONE_TIME")
        _require_interval(self.valid_from, self.valid_until)
        if self.constraint_digest != _digest(self._claims_without_digest()):
            raise ValueError("constraint_digest does not match authority constraint")

    @classmethod
    def create(
        cls,
        *,
        parent_scope_digest: str,
        actor_id: str,
        workspace_id: str,
        environment: str,
        capability: str,
        capability_definition_identity: str,
        target_kind: str,
        target_digest: str,
        payload_digest: str,
        policy_version: str,
        policy_identity: str,
        approval_set_digest: str,
        required_permission: str,
        valid_from: str,
        valid_until: str,
        use_semantics: str = ONE_TIME_USE,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "constraint_type": AUTHORITY_CONSTRAINT_TYPE,
            "parent_scope_digest": parent_scope_digest,
            "actor_id": actor_id,
            "workspace_id": workspace_id,
            "environment": environment,
            "capability": capability,
            "capability_definition_identity": capability_definition_identity,
            "target_kind": target_kind,
            "target_digest": target_digest,
            "payload_digest": payload_digest,
            "policy_version": policy_version,
            "policy_identity": policy_identity,
            "approval_set_digest": approval_set_digest,
            "required_permission": required_permission,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "use_semantics": use_semantics,
        }
        values = {
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "constraint_type"}
        }
        return cls(**values, constraint_digest=_digest(claims))

    @classmethod
    def from_scope(
        cls,
        scope: AuthorityScope,
        *,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> Self:
        if not isinstance(scope, AuthorityScope):
            raise ValueError("scope is invalid")
        return cls.create(
            parent_scope_digest=scope.scope_digest,
            actor_id=scope.actor_id,
            workspace_id=scope.workspace_id,
            environment=scope.environment,
            capability=scope.capability,
            capability_definition_identity=scope.capability_definition_identity,
            target_kind=scope.target_kind,
            target_digest=scope.target_digest,
            payload_digest=scope.payload_digest,
            policy_version=scope.policy_version,
            policy_identity=scope.policy_identity,
            approval_set_digest=scope.approval_set_digest,
            required_permission=scope.required_permission,
            valid_from=valid_from or scope.valid_from,
            valid_until=valid_until or scope.valid_until,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _CONSTRAINT_FIELDS,
            contract=AUTHORITY_CONSTRAINT_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["constraint_type"] != AUTHORITY_CONSTRAINT_TYPE
        ):
            raise ValueError("authority-constraint/v1 schema or type is unsupported")
        return cls(
            parent_scope_digest=value["parent_scope_digest"],
            actor_id=value["actor_id"],
            workspace_id=value["workspace_id"],
            environment=value["environment"],
            capability=value["capability"],
            capability_definition_identity=value["capability_definition_identity"],
            target_kind=value["target_kind"],
            target_digest=value["target_digest"],
            payload_digest=value["payload_digest"],
            policy_version=value["policy_version"],
            policy_identity=value["policy_identity"],
            approval_set_digest=value["approval_set_digest"],
            required_permission=value["required_permission"],
            valid_from=value["valid_from"],
            valid_until=value["valid_until"],
            use_semantics=value["use_semantics"],
            constraint_digest=value["constraint_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "constraint_type": AUTHORITY_CONSTRAINT_TYPE,
            "parent_scope_digest": self.parent_scope_digest,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "capability": self.capability,
            "capability_definition_identity": self.capability_definition_identity,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "payload_digest": self.payload_digest,
            "policy_version": self.policy_version,
            "policy_identity": self.policy_identity,
            "approval_set_digest": self.approval_set_digest,
            "required_permission": self.required_permission,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "use_semantics": self.use_semantics,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._claims_without_digest(),
            "constraint_digest": self.constraint_digest,
        }


class MonotonicAuthorityViolation(PermissionError):
    def __init__(self, reason_codes: list[str] | tuple[str, ...]) -> None:
        normalized = tuple(sorted(set(reason_codes)))
        if not normalized:
            raise ValueError("monotonic authority violation requires reason codes")
        self.reason_codes = normalized
        super().__init__("monotonic authority denied: " + ",".join(normalized))


@dataclass(frozen=True, slots=True)
class MonotonicAuthorityDecision:
    parent_scope_digest: str
    child_constraint_digest: str
    relation: str
    decision_digest: str

    def __post_init__(self) -> None:
        _require_digest(self.parent_scope_digest, field="parent_scope_digest")
        _require_digest(
            self.child_constraint_digest,
            field="child_constraint_digest",
        )
        if self.relation != NARROW_OR_EQUAL:
            raise ValueError("relation must be NARROW_OR_EQUAL")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise ValueError("decision_digest does not match monotonic authority decision")

    @classmethod
    def create(
        cls,
        *,
        parent_scope_digest: str,
        child_constraint_digest: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "decision_type": MONOTONIC_AUTHORITY_DECISION_TYPE,
            "parent_scope_digest": parent_scope_digest,
            "child_constraint_digest": child_constraint_digest,
            "relation": NARROW_OR_EQUAL,
        }
        return cls(
            parent_scope_digest=parent_scope_digest,
            child_constraint_digest=child_constraint_digest,
            relation=NARROW_OR_EQUAL,
            decision_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _DECISION_FIELDS,
            contract=MONOTONIC_AUTHORITY_DECISION_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["decision_type"] != MONOTONIC_AUTHORITY_DECISION_TYPE
        ):
            raise ValueError("monotonic-authority-decision/v1 schema or type is unsupported")
        return cls(
            parent_scope_digest=value["parent_scope_digest"],
            child_constraint_digest=value["child_constraint_digest"],
            relation=value["relation"],
            decision_digest=value["decision_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "decision_type": MONOTONIC_AUTHORITY_DECISION_TYPE,
            "parent_scope_digest": self.parent_scope_digest,
            "child_constraint_digest": self.child_constraint_digest,
            "relation": self.relation,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._claims_without_digest(),
            "decision_digest": self.decision_digest,
        }


class MonotonicAuthorityChecker:
    """Prove that one derived authority constraint cannot widen its parent scope."""

    @staticmethod
    def check(
        *,
        parent: AuthorityScope,
        child: AuthorityConstraint,
    ) -> MonotonicAuthorityDecision:
        if not isinstance(parent, AuthorityScope):
            raise ValueError("parent scope is invalid")
        if not isinstance(child, AuthorityConstraint):
            raise ValueError("child constraint is invalid")

        violations: list[str] = []
        if child.parent_scope_digest != parent.scope_digest:
            violations.append("PARENT_SCOPE_BINDING_MISMATCH")

        for field in _EXACT_BINDINGS:
            if getattr(child, field) != getattr(parent, field):
                violations.append(f"{field.upper()}_WIDENING")

        _, parent_start = _require_timestamp(parent.valid_from, field="parent.valid_from")
        _, parent_end = _require_timestamp(parent.valid_until, field="parent.valid_until")
        _, child_start = _require_timestamp(child.valid_from, field="child.valid_from")
        _, child_end = _require_timestamp(child.valid_until, field="child.valid_until")

        if child_start < parent_start:
            violations.append("VALID_FROM_WIDENING")
        if child_end > parent_end:
            violations.append("VALID_UNTIL_WIDENING")
        if child_start >= parent_end:
            violations.append("CHILD_STARTS_AFTER_PARENT_EXPIRY")
        if child.use_semantics != ONE_TIME_USE:
            violations.append("USE_SEMANTICS_WIDENING")

        if violations:
            raise MonotonicAuthorityViolation(violations)

        return MonotonicAuthorityDecision.create(
            parent_scope_digest=parent.scope_digest,
            child_constraint_digest=child.constraint_digest,
        )
