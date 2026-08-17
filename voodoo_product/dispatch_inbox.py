from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Self

from .dispatch_envelope import DispatchEnvelope
from .dispatch_outbox import DispatchOutboxEntry
from .evidence_primitives import canonical_json

DISPATCH_INBOX_ADMISSION_TYPE: Final = "dispatch-inbox-admission/v1"
DISPATCH_INBOX_ADMISSION_IDENTITY_TYPE: Final = "dispatch-inbox-admission-id/v1"
DUPLICATE_REDELIVERY: Final = "DUPLICATE"

_ADMISSION_FIELDS = frozenset(
    {
        "schema_version",
        "admission_type",
        "admission_id",
        "dispatch_id",
        "envelope_digest",
        "outbox_id",
        "outbox_entry_digest",
        "execution_id",
        "workspace_id",
        "environment",
        "execution_capsule_digest",
        "runner_class",
        "admission_revision",
        "admission_digest",
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


def _admission_id(
    *,
    dispatch_id: str,
    envelope_digest: str,
    outbox_entry_digest: str,
) -> str:
    return _digest(
        {
            "identity_type": DISPATCH_INBOX_ADMISSION_IDENTITY_TYPE,
            "dispatch_id": dispatch_id,
            "envelope_digest": envelope_digest,
            "outbox_entry_digest": outbox_entry_digest,
        }
    )


class DispatchInboxContentConflict(PermissionError):
    def __init__(self, reason: str = "DISPATCH_CONTENT_CONFLICT") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class DispatchInboxAdmission:
    """Immutable C3 admission contract for one exact C2 dispatch envelope.

    This value object does not itself prove durable persistence. C3 persistence must resolve the
    exact durable C1b outbox row, validate the C2 envelope against it, atomically admit the first
    logical dispatch_id, return DUPLICATE for exact redelivery, and fail closed on conflicting
    content for an already-admitted dispatch_id.
    """

    admission_id: str
    dispatch_id: str
    envelope_digest: str
    outbox_id: str
    outbox_entry_digest: str
    execution_id: str
    workspace_id: str
    environment: str
    execution_capsule_digest: str
    runner_class: str
    admission_revision: str
    admission_digest: str

    def __post_init__(self) -> None:
        for field in (
            "outbox_id",
            "execution_id",
            "workspace_id",
            "environment",
            "runner_class",
            "admission_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "admission_id",
            "dispatch_id",
            "envelope_digest",
            "outbox_entry_digest",
            "execution_capsule_digest",
            "admission_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        expected_admission_id = _admission_id(
            dispatch_id=self.dispatch_id,
            envelope_digest=self.envelope_digest,
            outbox_entry_digest=self.outbox_entry_digest,
        )
        if self.admission_id != expected_admission_id:
            raise ValueError("admission_id does not bind the accepted dispatch content")
        if self.admission_digest != _digest(self._claims_without_digest()):
            raise ValueError("admission_digest does not match dispatch inbox admission")

    @classmethod
    def create(
        cls,
        *,
        envelope: DispatchEnvelope,
        outbox_entry: DispatchOutboxEntry,
        admission_revision: str,
    ) -> Self:
        if not isinstance(envelope, DispatchEnvelope):
            raise ValueError("envelope must be DispatchEnvelope")
        if not isinstance(outbox_entry, DispatchOutboxEntry):
            raise ValueError("outbox_entry must be DispatchOutboxEntry")
        _require_text(admission_revision, field="admission_revision")

        envelope.assert_bound_to(outbox_entry)
        claims: dict[str, Any] = {
            "schema_version": 1,
            "admission_type": DISPATCH_INBOX_ADMISSION_TYPE,
            "admission_id": _admission_id(
                dispatch_id=envelope.dispatch_id,
                envelope_digest=envelope.envelope_digest,
                outbox_entry_digest=outbox_entry.entry_digest,
            ),
            "dispatch_id": envelope.dispatch_id,
            "envelope_digest": envelope.envelope_digest,
            "outbox_id": outbox_entry.outbox_id,
            "outbox_entry_digest": outbox_entry.entry_digest,
            "execution_id": outbox_entry.execution_id,
            "workspace_id": outbox_entry.workspace_id,
            "environment": outbox_entry.environment,
            "execution_capsule_digest": outbox_entry.execution_capsule_digest,
            "runner_class": outbox_entry.runner_class,
            "admission_revision": admission_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "admission_type"}
        }
        return cls(**values, admission_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _ADMISSION_FIELDS,
            contract=DISPATCH_INBOX_ADMISSION_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["admission_type"] != DISPATCH_INBOX_ADMISSION_TYPE
        ):
            raise ValueError("dispatch-inbox-admission/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _ADMISSION_FIELDS
                if key not in {"schema_version", "admission_type"}
            }
        )

    def assert_bound_to(
        self,
        *,
        envelope: DispatchEnvelope,
        outbox_entry: DispatchOutboxEntry,
    ) -> None:
        """Fail closed unless this admission binds one exact valid envelope/outbox pair."""

        if not isinstance(envelope, DispatchEnvelope):
            raise ValueError("envelope must be DispatchEnvelope")
        if not isinstance(outbox_entry, DispatchOutboxEntry):
            raise ValueError("outbox_entry must be DispatchOutboxEntry")
        envelope.assert_bound_to(outbox_entry)
        expected = {
            "dispatch_id": envelope.dispatch_id,
            "envelope_digest": envelope.envelope_digest,
            "outbox_id": outbox_entry.outbox_id,
            "outbox_entry_digest": outbox_entry.entry_digest,
            "execution_id": outbox_entry.execution_id,
            "workspace_id": outbox_entry.workspace_id,
            "environment": outbox_entry.environment,
            "execution_capsule_digest": outbox_entry.execution_capsule_digest,
            "runner_class": outbox_entry.runner_class,
        }
        actual = {
            "dispatch_id": self.dispatch_id,
            "envelope_digest": self.envelope_digest,
            "outbox_id": self.outbox_id,
            "outbox_entry_digest": self.outbox_entry_digest,
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
        }
        if actual != expected:
            raise PermissionError("dispatch inbox admission does not bind supplied content")

    def classify_redelivery(
        self,
        *,
        envelope: DispatchEnvelope,
        outbox_entry: DispatchOutboxEntry,
    ) -> str:
        """Classify a redelivery for this already-admitted logical dispatch."""

        if not isinstance(envelope, DispatchEnvelope):
            raise ValueError("envelope must be DispatchEnvelope")
        if not isinstance(outbox_entry, DispatchOutboxEntry):
            raise ValueError("outbox_entry must be DispatchOutboxEntry")
        envelope.assert_bound_to(outbox_entry)
        if envelope.dispatch_id != self.dispatch_id:
            raise ValueError("redelivery dispatch_id does not match admitted dispatch")
        try:
            self.assert_bound_to(envelope=envelope, outbox_entry=outbox_entry)
        except PermissionError as exc:
            raise DispatchInboxContentConflict() from exc
        return DUPLICATE_REDELIVERY

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "admission_type": DISPATCH_INBOX_ADMISSION_TYPE,
            "admission_id": self.admission_id,
            "dispatch_id": self.dispatch_id,
            "envelope_digest": self.envelope_digest,
            "outbox_id": self.outbox_id,
            "outbox_entry_digest": self.outbox_entry_digest,
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
            "admission_revision": self.admission_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "admission_digest": self.admission_digest}
