from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Self

from .dispatch_inbox import DispatchInboxAdmission
from .evidence_primitives import canonical_json
from .trusted_clock import ClockWitness

EXECUTION_LEASE_TYPE: Final = "execution-lease/v1"
EXECUTION_LEASE_IDENTITY_TYPE: Final = "execution-lease-id/v1"
FENCE_CURRENT: Final = "FENCE_CURRENT"
MAX_LEASE_SECONDS: Final = 3600

_LEASE_FIELDS = frozenset(
    {
        "schema_version",
        "lease_type",
        "lease_id",
        "dispatch_id",
        "admission_id",
        "admission_digest",
        "execution_id",
        "workspace_id",
        "environment",
        "execution_capsule_digest",
        "runner_class",
        "execution_epoch",
        "acquired_at",
        "expires_at",
        "clock_witness_digest",
        "lease_revision",
        "lease_digest",
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
    return canonical, parsed.astimezone(UTC)


def _require_epoch(value: object, *, field: str = "execution_epoch") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be an integer >= 1")
    return value


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


def _lease_id(*, admission_id: str, execution_epoch: int) -> str:
    return _digest(
        {
            "identity_type": EXECUTION_LEASE_IDENTITY_TYPE,
            "admission_id": admission_id,
            "execution_epoch": execution_epoch,
        }
    )


def assert_next_execution_epoch(
    *,
    previous_epoch: int | None,
    candidate_epoch: int,
) -> None:
    """Freeze the C4 monotonic epoch rule without claiming durable allocation.

    C4 persistence must allocate under a serialized database transaction. This helper only defines
    the allowed transition: the first epoch is 1 and each successor is exactly previous + 1.
    """

    candidate = _require_epoch(candidate_epoch, field="candidate_epoch")
    if previous_epoch is None:
        if candidate != 1:
            raise ExecutionFenceDenied("EXECUTION_EPOCH_TRANSITION_INVALID")
        return
    previous = _require_epoch(previous_epoch, field="previous_epoch")
    if candidate != previous + 1:
        raise ExecutionFenceDenied("EXECUTION_EPOCH_TRANSITION_INVALID")


class ExecutionFenceDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ExecutionLease:
    """Immutable C4 lease/fence contract for one durable C3 inbox admission.

    This object is not durable epoch authority. C4 persistence must allocate the current epoch and
    resolve it again at every completion/effect gate. Structural validity alone never proves that a
    lease is current.
    """

    lease_id: str
    dispatch_id: str
    admission_id: str
    admission_digest: str
    execution_id: str
    workspace_id: str
    environment: str
    execution_capsule_digest: str
    runner_class: str
    execution_epoch: int
    acquired_at: str
    expires_at: str
    clock_witness_digest: str
    lease_revision: str
    lease_digest: str

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "workspace_id",
            "environment",
            "runner_class",
            "lease_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "lease_id",
            "dispatch_id",
            "admission_id",
            "admission_digest",
            "execution_capsule_digest",
            "clock_witness_digest",
            "lease_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        _require_epoch(self.execution_epoch)
        _, acquired = _require_timestamp(self.acquired_at, field="acquired_at")
        _, expires = _require_timestamp(self.expires_at, field="expires_at")
        if expires <= acquired:
            raise ValueError("expires_at must be after acquired_at")
        if expires - acquired > timedelta(seconds=MAX_LEASE_SECONDS):
            raise ValueError("execution lease exceeds maximum bounded duration")
        if self.lease_id != _lease_id(
            admission_id=self.admission_id,
            execution_epoch=self.execution_epoch,
        ):
            raise ValueError("lease_id does not bind admission and execution epoch")
        if self.lease_digest != _digest(self._claims_without_digest()):
            raise ValueError("lease_digest does not match execution lease")

    @classmethod
    def create_candidate(
        cls,
        *,
        admission: DispatchInboxAdmission,
        execution_epoch: int,
        clock_witness: ClockWitness,
        lease_seconds: int,
        lease_revision: str,
    ) -> Self:
        """Build a candidate lease after an external durable allocator chose the epoch.

        The raw epoch argument is deliberately not authority. C4b must own its durable allocation,
        persist exactly one current epoch and only then use this constructor.
        """

        if not isinstance(admission, DispatchInboxAdmission):
            raise ValueError("admission must be DispatchInboxAdmission")
        if not isinstance(clock_witness, ClockWitness):
            raise ValueError("clock_witness must be ClockWitness")
        epoch = _require_epoch(execution_epoch)
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            raise ValueError("lease_seconds must be an integer")
        if lease_seconds < 1 or lease_seconds > MAX_LEASE_SECONDS:
            raise ValueError(
                f"lease_seconds must be between 1 and {MAX_LEASE_SECONDS}"
            )
        _require_text(lease_revision, field="lease_revision")
        if clock_witness.environment != admission.environment:
            raise ExecutionFenceDenied("CLOCK_ENVIRONMENT_MISMATCH")

        _, acquired = _require_timestamp(
            clock_witness.observed_at,
            field="clock_witness.observed_at",
        )
        acquired_at = acquired.isoformat(timespec="milliseconds")
        expires_at = (acquired + timedelta(seconds=lease_seconds)).isoformat(
            timespec="milliseconds"
        )
        claims: dict[str, Any] = {
            "schema_version": 1,
            "lease_type": EXECUTION_LEASE_TYPE,
            "lease_id": _lease_id(
                admission_id=admission.admission_id,
                execution_epoch=epoch,
            ),
            "dispatch_id": admission.dispatch_id,
            "admission_id": admission.admission_id,
            "admission_digest": admission.admission_digest,
            "execution_id": admission.execution_id,
            "workspace_id": admission.workspace_id,
            "environment": admission.environment,
            "execution_capsule_digest": admission.execution_capsule_digest,
            "runner_class": admission.runner_class,
            "execution_epoch": epoch,
            "acquired_at": acquired_at,
            "expires_at": expires_at,
            "clock_witness_digest": clock_witness.witness_digest,
            "lease_revision": lease_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "lease_type"}
        }
        return cls(**values, lease_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _LEASE_FIELDS, contract=EXECUTION_LEASE_TYPE)
        if value["schema_version"] != 1 or value["lease_type"] != EXECUTION_LEASE_TYPE:
            raise ValueError("execution-lease/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _LEASE_FIELDS
                if key not in {"schema_version", "lease_type"}
            }
        )

    def assert_bound_to(self, admission: DispatchInboxAdmission) -> None:
        if not isinstance(admission, DispatchInboxAdmission):
            raise ValueError("admission must be DispatchInboxAdmission")
        expected = {
            "dispatch_id": admission.dispatch_id,
            "admission_id": admission.admission_id,
            "admission_digest": admission.admission_digest,
            "execution_id": admission.execution_id,
            "workspace_id": admission.workspace_id,
            "environment": admission.environment,
            "execution_capsule_digest": admission.execution_capsule_digest,
            "runner_class": admission.runner_class,
        }
        actual = {
            "dispatch_id": self.dispatch_id,
            "admission_id": self.admission_id,
            "admission_digest": self.admission_digest,
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
        }
        if actual != expected:
            raise ExecutionFenceDenied("LEASE_ADMISSION_BINDING_MISMATCH")

    def assert_completion_fence(
        self,
        *,
        current_execution_epoch: int,
        clock_witness: ClockWitness,
    ) -> str:
        """Fail closed unless this lease is the current, unexpired epoch.

        The caller-provided current_execution_epoch is not authoritative in this contract-only slice.
        C4b must resolve it from durable state in the same safety boundary used for completion/effect.
        """

        current = _require_epoch(current_execution_epoch, field="current_execution_epoch")
        if not isinstance(clock_witness, ClockWitness):
            raise ValueError("clock_witness must be ClockWitness")
        if clock_witness.environment != self.environment:
            raise ExecutionFenceDenied("CLOCK_ENVIRONMENT_MISMATCH")
        if current < self.execution_epoch:
            raise ExecutionFenceDenied("EXECUTION_EPOCH_REGRESSION")
        if current > self.execution_epoch:
            raise ExecutionFenceDenied("STALE_EXECUTION_EPOCH")

        _, acquired = _require_timestamp(self.acquired_at, field="acquired_at")
        _, expires = _require_timestamp(self.expires_at, field="expires_at")
        _, observed = _require_timestamp(
            clock_witness.observed_at,
            field="clock_witness.observed_at",
        )
        if observed < acquired:
            raise ExecutionFenceDenied("CLOCK_BEFORE_LEASE")
        if observed >= expires:
            raise ExecutionFenceDenied("LEASE_EXPIRED")
        return FENCE_CURRENT

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "lease_type": EXECUTION_LEASE_TYPE,
            "lease_id": self.lease_id,
            "dispatch_id": self.dispatch_id,
            "admission_id": self.admission_id,
            "admission_digest": self.admission_digest,
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
            "execution_epoch": self.execution_epoch,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "clock_witness_digest": self.clock_witness_digest,
            "lease_revision": self.lease_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "lease_digest": self.lease_digest}
