from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Protocol, Self, runtime_checkable

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json

CLOCK_WITNESS_TYPE: Final = "clock-witness/v1"


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


@runtime_checkable
class ClockSource(Protocol):
    def read(self) -> datetime: ...


class SystemUtcClockSource:
    def read(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ClockWitness:
    source_identity: str
    authority_revision: str
    environment: str
    observed_at: str
    witness_digest: str

    def __post_init__(self) -> None:
        _require_text(self.source_identity, field="source_identity")
        _require_text(self.authority_revision, field="authority_revision")
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        try:
            parsed = datetime.fromisoformat(self.observed_at)
        except ValueError as exc:
            raise ValueError("observed_at is invalid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
        if self.observed_at != canonical:
            raise ValueError("observed_at must use canonical UTC millisecond form")
        _require_digest(self.witness_digest, field="witness_digest")
        if self.witness_digest != _digest(self._claims_without_digest()):
            raise ValueError("witness_digest does not match clock witness")

    @classmethod
    def create(
        cls,
        *,
        source_identity: str,
        authority_revision: str,
        environment: str,
        observed_at: datetime,
    ) -> Self:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("clock source returned naive time")
        canonical = observed_at.astimezone(UTC).isoformat(timespec="milliseconds")
        claims = {
            "witness_type": CLOCK_WITNESS_TYPE,
            "source_identity": source_identity,
            "authority_revision": authority_revision,
            "environment": environment,
            "observed_at": canonical,
        }
        return cls(
            source_identity=source_identity,
            authority_revision=authority_revision,
            environment=environment,
            observed_at=canonical,
            witness_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "witness_type": CLOCK_WITNESS_TYPE,
            "source_identity": self.source_identity,
            "authority_revision": self.authority_revision,
            "environment": self.environment,
            "observed_at": self.observed_at,
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["witness_digest"] = self.witness_digest
        return value


class TrustedClockAuthority:
    """Server-constructed authority over an explicit clock-source identity."""

    def __init__(
        self,
        *,
        source_identity: str,
        authority_revision: str,
        source: ClockSource | None = None,
        allowed_environments: frozenset[str] = frozenset(VALID_ENVIRONMENTS),
    ) -> None:
        _require_text(source_identity, field="source_identity")
        _require_text(authority_revision, field="authority_revision")
        if not allowed_environments or not allowed_environments.issubset(VALID_ENVIRONMENTS):
            raise ValueError("allowed_environments are invalid")
        resolved_source = source or SystemUtcClockSource()
        if not isinstance(resolved_source, ClockSource):
            raise ValueError("source does not satisfy ClockSource")
        self._source_identity = source_identity
        self._authority_revision = authority_revision
        self._source = resolved_source
        self._allowed_environments = allowed_environments

    @property
    def source_identity(self) -> str:
        return self._source_identity

    def witness(self, *, environment: str) -> ClockWitness:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        if environment not in self._allowed_environments:
            raise PermissionError("clock source is not authorized for environment")
        observed_at = self._source.read()
        if not isinstance(observed_at, datetime):
            raise RuntimeError("clock source returned invalid value")
        return ClockWitness.create(
            source_identity=self._source_identity,
            authority_revision=self._authority_revision,
            environment=environment,
            observed_at=observed_at,
        )
