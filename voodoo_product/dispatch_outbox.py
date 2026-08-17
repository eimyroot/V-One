from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .authoritative_grant import ExecutionGrantV2
from .evidence_primitives import canonical_json
from .grant_consumption import GrantConsumptionWitness

DISPATCH_OUTBOX_ENTRY_TYPE: Final = "dispatch-outbox-entry/v1"

_OUTBOX_ENTRY_FIELDS = frozenset(
    {
        "schema_version",
        "entry_type",
        "outbox_id",
        "consumption_id",
        "consumption_witness_digest",
        "jti",
        "grant_id",
        "grant_digest",
        "execution_id",
        "request_id",
        "actor_id",
        "workspace_id",
        "environment",
        "capability",
        "capability_definition_identity",
        "authorization_snapshot_digest",
        "target_kind",
        "target_digest",
        "payload_digest",
        "required_permission",
        "execution_binding_digest",
        "execution_capsule_digest",
        "runner_class",
        "precondition_enforcement_class",
        "use_semantics",
        "created_at",
        "outbox_revision",
        "entry_digest",
    }
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


def _require_timestamp(value: object, *, field: str) -> str:
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
    return canonical


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
class DispatchOutboxEntry:
    """Content-bound dispatch intent derived from one consumed ExecutionGrant/v2.

    The object is not a dispatch, lease, Runner assignment or provider effect. It freezes the
    exact authority-bearing routing claims that C1b may later persist in the same transaction
    as GrantConsumptionWitness creation.
    """

    outbox_id: str
    consumption_id: str
    consumption_witness_digest: str
    jti: str
    grant_id: str
    grant_digest: str
    execution_id: str
    request_id: str
    actor_id: str
    workspace_id: str
    environment: str
    capability: str
    capability_definition_identity: str
    authorization_snapshot_digest: str
    target_kind: str
    target_digest: str
    payload_digest: str
    required_permission: str
    execution_binding_digest: str
    execution_capsule_digest: str
    runner_class: str
    precondition_enforcement_class: str
    use_semantics: str
    created_at: str
    outbox_revision: str
    entry_digest: str

    def __post_init__(self) -> None:
        for field in (
            "outbox_id",
            "consumption_id",
            "jti",
            "grant_id",
            "execution_id",
            "request_id",
            "actor_id",
            "workspace_id",
            "environment",
            "capability",
            "target_kind",
            "required_permission",
            "runner_class",
            "precondition_enforcement_class",
            "use_semantics",
            "outbox_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "consumption_witness_digest",
            "grant_digest",
            "capability_definition_identity",
            "authorization_snapshot_digest",
            "target_digest",
            "payload_digest",
            "execution_binding_digest",
            "execution_capsule_digest",
            "entry_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        _require_timestamp(self.created_at, field="created_at")
        if self.required_permission != "execution.run":
            raise ValueError("required_permission must be execution.run")
        if self.use_semantics != "ONE_TIME":
            raise ValueError("use_semantics must be ONE_TIME")
        if self.precondition_enforcement_class not in {
            "READ_THEN_COMPARE",
            "ATOMIC_PROVIDER_CONDITION",
        }:
            raise ValueError("precondition_enforcement_class is unsupported")
        if self.entry_digest != _digest(self._claims_without_digest()):
            raise ValueError("entry_digest does not match dispatch outbox entry")

    @classmethod
    def create(
        cls,
        *,
        outbox_id: str,
        grant: ExecutionGrantV2,
        consumption_witness: GrantConsumptionWitness,
        outbox_revision: str,
    ) -> Self:
        if not isinstance(grant, ExecutionGrantV2):
            raise ValueError("grant must be ExecutionGrantV2")
        if not isinstance(consumption_witness, GrantConsumptionWitness):
            raise ValueError("consumption_witness must be GrantConsumptionWitness")

        expected_consumption_binding = (
            grant.jti,
            grant.grant_id,
            grant.grant_digest,
            grant.execution_id,
            grant.authorization_snapshot_digest,
            grant.execution_capsule_digest,
            grant.runner_class,
        )
        actual_consumption_binding = (
            consumption_witness.jti,
            consumption_witness.grant_id,
            consumption_witness.grant_digest,
            consumption_witness.execution_id,
            consumption_witness.authorization_snapshot_digest,
            consumption_witness.execution_capsule_digest,
            consumption_witness.runner_class,
        )
        if actual_consumption_binding != expected_consumption_binding:
            raise PermissionError(
                "grant consumption witness does not bind the supplied execution grant"
            )

        claims = {
            "schema_version": 1,
            "entry_type": DISPATCH_OUTBOX_ENTRY_TYPE,
            "outbox_id": outbox_id,
            "consumption_id": consumption_witness.consumption_id,
            "consumption_witness_digest": consumption_witness.witness_digest,
            "jti": grant.jti,
            "grant_id": grant.grant_id,
            "grant_digest": grant.grant_digest,
            "execution_id": grant.execution_id,
            "request_id": grant.request_id,
            "actor_id": grant.actor_id,
            "workspace_id": grant.workspace_id,
            "environment": grant.environment,
            "capability": grant.capability,
            "capability_definition_identity": grant.capability_definition_identity,
            "authorization_snapshot_digest": grant.authorization_snapshot_digest,
            "target_kind": grant.target_kind,
            "target_digest": grant.target_digest,
            "payload_digest": grant.payload_digest,
            "required_permission": grant.required_permission,
            "execution_binding_digest": grant.execution_binding_digest,
            "execution_capsule_digest": grant.execution_capsule_digest,
            "runner_class": grant.runner_class,
            "precondition_enforcement_class": grant.precondition_enforcement_class,
            "use_semantics": grant.use_semantics,
            "created_at": consumption_witness.consumed_at,
            "outbox_revision": outbox_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "entry_type"}
        }
        return cls(**values, entry_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _OUTBOX_ENTRY_FIELDS,
            contract=DISPATCH_OUTBOX_ENTRY_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["entry_type"] != DISPATCH_OUTBOX_ENTRY_TYPE
        ):
            raise ValueError("dispatch-outbox-entry/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _OUTBOX_ENTRY_FIELDS
                if key not in {"schema_version", "entry_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "entry_type": DISPATCH_OUTBOX_ENTRY_TYPE,
            "outbox_id": self.outbox_id,
            "consumption_id": self.consumption_id,
            "consumption_witness_digest": self.consumption_witness_digest,
            "jti": self.jti,
            "grant_id": self.grant_id,
            "grant_digest": self.grant_digest,
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "capability": self.capability,
            "capability_definition_identity": self.capability_definition_identity,
            "authorization_snapshot_digest": self.authorization_snapshot_digest,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "payload_digest": self.payload_digest,
            "required_permission": self.required_permission,
            "execution_binding_digest": self.execution_binding_digest,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
            "precondition_enforcement_class": self.precondition_enforcement_class,
            "use_semantics": self.use_semantics,
            "created_at": self.created_at,
            "outbox_revision": self.outbox_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "entry_digest": self.entry_digest}
