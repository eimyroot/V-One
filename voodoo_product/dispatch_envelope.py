from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Self

from .dispatch_outbox import DispatchOutboxEntry
from .evidence_primitives import canonical_json

DISPATCH_ENVELOPE_TYPE: Final = "dispatch-envelope/v1"
DISPATCH_IDENTITY_TYPE: Final = "dispatch-id/v1"
DELIVERY_SEMANTICS: Final = "AT_LEAST_ONCE_REDELIVERY_DEDUP_REQUIRED"

_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "envelope_type",
        "dispatch_id",
        "outbox_id",
        "outbox_entry_digest",
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
        "outbox_created_at",
        "outbox_revision",
        "delivery_semantics",
        "envelope_revision",
        "envelope_digest",
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


def _dispatch_id(*, outbox_id: str, outbox_entry_digest: str) -> str:
    return _digest(
        {
            "identity_type": DISPATCH_IDENTITY_TYPE,
            "outbox_id": outbox_id,
            "outbox_entry_digest": outbox_entry_digest,
        }
    )


def _projection(entry: DispatchOutboxEntry) -> dict[str, str]:
    return {
        "outbox_id": entry.outbox_id,
        "outbox_entry_digest": entry.entry_digest,
        "consumption_id": entry.consumption_id,
        "consumption_witness_digest": entry.consumption_witness_digest,
        "jti": entry.jti,
        "grant_id": entry.grant_id,
        "grant_digest": entry.grant_digest,
        "execution_id": entry.execution_id,
        "request_id": entry.request_id,
        "actor_id": entry.actor_id,
        "workspace_id": entry.workspace_id,
        "environment": entry.environment,
        "capability": entry.capability,
        "capability_definition_identity": entry.capability_definition_identity,
        "authorization_snapshot_digest": entry.authorization_snapshot_digest,
        "target_kind": entry.target_kind,
        "target_digest": entry.target_digest,
        "payload_digest": entry.payload_digest,
        "required_permission": entry.required_permission,
        "execution_binding_digest": entry.execution_binding_digest,
        "execution_capsule_digest": entry.execution_capsule_digest,
        "runner_class": entry.runner_class,
        "precondition_enforcement_class": entry.precondition_enforcement_class,
        "use_semantics": entry.use_semantics,
        "outbox_created_at": entry.created_at,
        "outbox_revision": entry.outbox_revision,
    }


@dataclass(frozen=True, slots=True)
class DispatchEnvelope:
    """Content-bound transport envelope for one durable C1b outbox intent.

    The envelope does not grant new authority, claim delivery, assign a concrete RunnerIdentity,
    create a lease, or permit a provider effect. Its deterministic dispatch_id is the logical
    redelivery/dedup identity that C3 may consume after resolving the exact durable outbox row.
    """

    dispatch_id: str
    outbox_id: str
    outbox_entry_digest: str
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
    outbox_created_at: str
    outbox_revision: str
    delivery_semantics: str
    envelope_revision: str
    envelope_digest: str

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
            "delivery_semantics",
            "envelope_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "dispatch_id",
            "outbox_entry_digest",
            "consumption_witness_digest",
            "grant_digest",
            "capability_definition_identity",
            "authorization_snapshot_digest",
            "target_digest",
            "payload_digest",
            "execution_binding_digest",
            "execution_capsule_digest",
            "envelope_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        _require_timestamp(self.outbox_created_at, field="outbox_created_at")
        if self.required_permission != "execution.run":
            raise ValueError("required_permission must be execution.run")
        if self.use_semantics != "ONE_TIME":
            raise ValueError("use_semantics must be ONE_TIME")
        if self.precondition_enforcement_class not in {
            "READ_THEN_COMPARE",
            "ATOMIC_PROVIDER_CONDITION",
        }:
            raise ValueError("precondition_enforcement_class is unsupported")
        if self.delivery_semantics != DELIVERY_SEMANTICS:
            raise ValueError("delivery_semantics is unsupported")
        if self.dispatch_id != _dispatch_id(
            outbox_id=self.outbox_id,
            outbox_entry_digest=self.outbox_entry_digest,
        ):
            raise ValueError("dispatch_id does not bind the outbox identity")
        if self.envelope_digest != _digest(self._claims_without_digest()):
            raise ValueError("envelope_digest does not match dispatch envelope")

    @classmethod
    def create(
        cls,
        *,
        outbox_entry: DispatchOutboxEntry,
        envelope_revision: str,
    ) -> Self:
        if not isinstance(outbox_entry, DispatchOutboxEntry):
            raise ValueError("outbox_entry must be DispatchOutboxEntry")
        _require_text(envelope_revision, field="envelope_revision")

        projection = _projection(outbox_entry)
        claims: dict[str, Any] = {
            "schema_version": 1,
            "envelope_type": DISPATCH_ENVELOPE_TYPE,
            "dispatch_id": _dispatch_id(
                outbox_id=outbox_entry.outbox_id,
                outbox_entry_digest=outbox_entry.entry_digest,
            ),
            **projection,
            "delivery_semantics": DELIVERY_SEMANTICS,
            "envelope_revision": envelope_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "envelope_type"}
        }
        return cls(**values, envelope_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _ENVELOPE_FIELDS,
            contract=DISPATCH_ENVELOPE_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["envelope_type"] != DISPATCH_ENVELOPE_TYPE
        ):
            raise ValueError("dispatch-envelope/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _ENVELOPE_FIELDS
                if key not in {"schema_version", "envelope_type"}
            }
        )

    def assert_bound_to(self, outbox_entry: DispatchOutboxEntry) -> None:
        """Fail closed unless this envelope exactly projects the supplied outbox entry."""

        if not isinstance(outbox_entry, DispatchOutboxEntry):
            raise ValueError("outbox_entry must be DispatchOutboxEntry")
        expected = {
            "dispatch_id": _dispatch_id(
                outbox_id=outbox_entry.outbox_id,
                outbox_entry_digest=outbox_entry.entry_digest,
            ),
            **_projection(outbox_entry),
        }
        actual = {
            "dispatch_id": self.dispatch_id,
            "outbox_id": self.outbox_id,
            "outbox_entry_digest": self.outbox_entry_digest,
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
            "outbox_created_at": self.outbox_created_at,
            "outbox_revision": self.outbox_revision,
        }
        if actual != expected:
            raise PermissionError("dispatch envelope does not bind the supplied outbox entry")

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "envelope_type": DISPATCH_ENVELOPE_TYPE,
            "dispatch_id": self.dispatch_id,
            "outbox_id": self.outbox_id,
            "outbox_entry_digest": self.outbox_entry_digest,
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
            "outbox_created_at": self.outbox_created_at,
            "outbox_revision": self.outbox_revision,
            "delivery_semantics": self.delivery_semantics,
            "envelope_revision": self.envelope_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "envelope_digest": self.envelope_digest}
