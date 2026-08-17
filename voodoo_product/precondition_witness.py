from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Final, Protocol, Self, runtime_checkable

from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget
from .monotonic_authority import (
    AuthorityConstraint,
    AuthorityScope,
    MonotonicAuthorityChecker,
    MonotonicAuthorityDecision,
    MonotonicAuthorityViolation,
)
from .trusted_clock import ClockWitness, TrustedClockAuthority

PRECONDITION_REQUIREMENT_TYPE: Final = "precondition-requirement/v1"
PRECONDITION_EXPECTATION_TYPE: Final = "precondition-expectation/v1"
PRECONDITION_OBSERVATION_TYPE: Final = "precondition-observation/v1"
PRECONDITION_WITNESS_TYPE: Final = "precondition-witness/v1"

EXACT_STATE_DIGEST: Final = "EXACT_STATE_DIGEST"
READ_THEN_COMPARE: Final = "READ_THEN_COMPARE"
ATOMIC_PROVIDER_CONDITION: Final = "ATOMIC_PROVIDER_CONDITION"
MATCH: Final = "MATCH"

_REQUIREMENT_FIELDS = frozenset(
    {
        "schema_version",
        "requirement_type",
        "capability_definition_identity",
        "target_kind",
        "expectation_binder_id",
        "observer_id",
        "state_schema",
        "comparison_mode",
        "enforcement_class",
        "requirement_revision",
        "requirement_digest",
    }
)
_EXPECTATION_FIELDS = frozenset(
    {
        "schema_version",
        "expectation_type",
        "parent_scope_digest",
        "authority_constraint_digest",
        "requirement_digest",
        "target_kind",
        "target_digest",
        "state_schema",
        "expected_state",
        "expected_state_digest",
        "expectation_digest",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version",
        "observation_type",
        "requirement_digest",
        "target_kind",
        "target_digest",
        "state_schema",
        "observer_id",
        "source_identity",
        "clock_source_identity",
        "clock_witness_digest",
        "observed_at",
        "observed_state",
        "observed_state_digest",
        "observation_digest",
    }
)
_WITNESS_FIELDS = frozenset(
    {
        "schema_version",
        "witness_type",
        "parent_scope_digest",
        "authority_constraint_digest",
        "monotonic_authority_decision_digest",
        "requirement_digest",
        "expectation_digest",
        "observation_digest",
        "target_digest",
        "expected_state_digest",
        "observed_state_digest",
        "observer_id",
        "source_identity",
        "clock_source_identity",
        "clock_witness_digest",
        "checked_at",
        "relation",
        "enforcement_class",
        "witness_digest",
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
    return text, parsed.astimezone(UTC)


def _require_json_value(value: object, *, field: str, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError(f"{field} exceeds the nesting limit")
    if value is None or type(value) in {bool, int, str}:
        return
    if isinstance(value, list):
        for item in value:
            _require_json_value(item, field=field, depth=depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field} keys must be strings")
            _require_json_value(item, field=field, depth=depth + 1)
        return
    raise ValueError(f"{field} contains an unsupported JSON value")


def _canonical_state(value: Mapping[str, Any], *, field: str) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    state = dict(value)
    _require_json_value(state, field=field)
    state_json = canonical_json(state)
    return state_json, hashlib.sha256(state_json.encode("utf-8")).hexdigest()


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


class PreconditionViolation(PermissionError):
    def __init__(self, reason_codes: Iterable[str]) -> None:
        normalized = tuple(sorted(set(reason_codes)))
        if not normalized:
            raise ValueError("precondition violation requires reason codes")
        self.reason_codes = normalized
        super().__init__("precondition denied: " + ",".join(normalized))


@dataclass(frozen=True, slots=True)
class PreconditionRequirement:
    capability_definition_identity: str
    target_kind: str
    expectation_binder_id: str
    observer_id: str
    state_schema: str
    comparison_mode: str
    enforcement_class: str
    requirement_revision: str
    requirement_digest: str

    def __post_init__(self) -> None:
        _require_digest(
            self.capability_definition_identity,
            field="capability_definition_identity",
        )
        for field in (
            "target_kind",
            "expectation_binder_id",
            "observer_id",
            "state_schema",
            "requirement_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.comparison_mode != EXACT_STATE_DIGEST:
            raise ValueError("comparison_mode must be EXACT_STATE_DIGEST")
        if self.enforcement_class not in {
            READ_THEN_COMPARE,
            ATOMIC_PROVIDER_CONDITION,
        }:
            raise ValueError("enforcement_class is unsupported")
        _require_digest(self.requirement_digest, field="requirement_digest")
        if self.requirement_digest != _digest(self._claims_without_digest()):
            raise ValueError("requirement_digest does not match precondition requirement")

    @classmethod
    def create(
        cls,
        *,
        capability_definition_identity: str,
        target_kind: str,
        expectation_binder_id: str,
        observer_id: str,
        state_schema: str,
        requirement_revision: str,
        enforcement_class: str,
        comparison_mode: str = EXACT_STATE_DIGEST,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "requirement_type": PRECONDITION_REQUIREMENT_TYPE,
            "capability_definition_identity": capability_definition_identity,
            "target_kind": target_kind,
            "expectation_binder_id": expectation_binder_id,
            "observer_id": observer_id,
            "state_schema": state_schema,
            "comparison_mode": comparison_mode,
            "enforcement_class": enforcement_class,
            "requirement_revision": requirement_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "requirement_type"}
        }
        return cls(**values, requirement_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _REQUIREMENT_FIELDS,
            contract=PRECONDITION_REQUIREMENT_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["requirement_type"] != PRECONDITION_REQUIREMENT_TYPE
        ):
            raise ValueError("precondition-requirement/v1 schema or type is unsupported")
        return cls(
            capability_definition_identity=value["capability_definition_identity"],
            target_kind=value["target_kind"],
            expectation_binder_id=value["expectation_binder_id"],
            observer_id=value["observer_id"],
            state_schema=value["state_schema"],
            comparison_mode=value["comparison_mode"],
            enforcement_class=value["enforcement_class"],
            requirement_revision=value["requirement_revision"],
            requirement_digest=value["requirement_digest"],
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "requirement_type": PRECONDITION_REQUIREMENT_TYPE,
            "capability_definition_identity": self.capability_definition_identity,
            "target_kind": self.target_kind,
            "expectation_binder_id": self.expectation_binder_id,
            "observer_id": self.observer_id,
            "state_schema": self.state_schema,
            "comparison_mode": self.comparison_mode,
            "enforcement_class": self.enforcement_class,
            "requirement_revision": self.requirement_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._claims_without_digest(),
            "requirement_digest": self.requirement_digest,
        }


class ImmutablePreconditionRequirementRegistry:
    def __init__(self, requirements: Iterable[PreconditionRequirement]) -> None:
        by_definition: dict[str, PreconditionRequirement] = {}
        for requirement in requirements:
            if not isinstance(requirement, PreconditionRequirement):
                raise ValueError("precondition registry accepts PreconditionRequirement values only")
            if requirement.capability_definition_identity in by_definition:
                raise ValueError("duplicate precondition requirement")
            by_definition[requirement.capability_definition_identity] = requirement
        if not by_definition:
            raise ValueError("precondition registry requires at least one requirement")
        self._by_definition = MappingProxyType(by_definition)

    def resolve(self, capability_definition_identity: str) -> PreconditionRequirement:
        _require_digest(
            capability_definition_identity,
            field="capability_definition_identity",
        )
        try:
            return self._by_definition[capability_definition_identity]
        except KeyError as exc:
            raise LookupError("precondition requirement not found") from exc


@runtime_checkable
class PreconditionExpectationBinder(Protocol):
    binder_id: str
    target_kind: str
    state_schema: str

    def bind_expected(self, *, target: ExecutionTarget) -> Mapping[str, Any]: ...


@runtime_checkable
class PreconditionObserver(Protocol):
    observer_id: str
    target_kind: str
    state_schema: str
    source_identity: str

    def observe(self, *, target: ExecutionTarget) -> Mapping[str, Any]: ...


class PreconditionExpectationBinderRegistry:
    def __init__(self, binders: Mapping[str, PreconditionExpectationBinder]) -> None:
        normalized: dict[str, PreconditionExpectationBinder] = {}
        for binder_id, binder in binders.items():
            _require_text(binder_id, field="binder_id")
            if not isinstance(binder, PreconditionExpectationBinder):
                raise ValueError("precondition binder does not satisfy protocol")
            if binder.binder_id != binder_id:
                raise ValueError("precondition binder registry key does not match binder_id")
            normalized[binder_id] = binder
        if not normalized:
            raise ValueError("precondition binder registry requires at least one binder")
        self._binders = MappingProxyType(normalized)

    def resolve(self, binder_id: str) -> PreconditionExpectationBinder:
        _require_text(binder_id, field="binder_id")
        try:
            return self._binders[binder_id]
        except KeyError as exc:
            raise LookupError("precondition expectation binder not found") from exc


class PreconditionObserverRegistry:
    def __init__(self, observers: Mapping[str, PreconditionObserver]) -> None:
        normalized: dict[str, PreconditionObserver] = {}
        for observer_id, observer in observers.items():
            _require_text(observer_id, field="observer_id")
            if not isinstance(observer, PreconditionObserver):
                raise ValueError("precondition observer does not satisfy protocol")
            if observer.observer_id != observer_id:
                raise ValueError("precondition observer registry key does not match observer_id")
            _require_text(observer.source_identity, field="source_identity")
            normalized[observer_id] = observer
        if not normalized:
            raise ValueError("precondition observer registry requires at least one observer")
        self._observers = MappingProxyType(normalized)

    def resolve(self, observer_id: str) -> PreconditionObserver:
        _require_text(observer_id, field="observer_id")
        try:
            return self._observers[observer_id]
        except KeyError as exc:
            raise LookupError("precondition observer not found") from exc


@dataclass(frozen=True, slots=True)
class PreconditionExpectation:
    parent_scope_digest: str
    authority_constraint_digest: str
    requirement_digest: str
    target_kind: str
    target_digest: str
    state_schema: str
    _expected_state_json: str
    expected_state_digest: str
    expectation_digest: str

    def __post_init__(self) -> None:
        for field in (
            "parent_scope_digest",
            "authority_constraint_digest",
            "requirement_digest",
            "target_digest",
            "expected_state_digest",
            "expectation_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        _require_text(self.target_kind, field="target_kind")
        _require_text(self.state_schema, field="state_schema")
        try:
            state = json.loads(self._expected_state_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("expected_state is invalid") from exc
        if not isinstance(state, dict):
            raise ValueError("expected_state must be an object")
        _require_json_value(state, field="expected_state")
        if self._expected_state_json != canonical_json(state):
            raise ValueError("expected_state is not canonical")
        actual_state_digest = hashlib.sha256(
            self._expected_state_json.encode("utf-8")
        ).hexdigest()
        if self.expected_state_digest != actual_state_digest:
            raise ValueError("expected_state_digest does not match expected_state")
        if self.expectation_digest != _digest(self._claims_without_digest()):
            raise ValueError("expectation_digest does not match precondition expectation")

    @classmethod
    def create(
        cls,
        *,
        parent_scope_digest: str,
        authority_constraint_digest: str,
        requirement_digest: str,
        target_kind: str,
        target_digest: str,
        state_schema: str,
        expected_state: Mapping[str, Any],
    ) -> Self:
        state_json, state_digest = _canonical_state(
            expected_state,
            field="expected_state",
        )
        claims = {
            "schema_version": 1,
            "expectation_type": PRECONDITION_EXPECTATION_TYPE,
            "parent_scope_digest": parent_scope_digest,
            "authority_constraint_digest": authority_constraint_digest,
            "requirement_digest": requirement_digest,
            "target_kind": target_kind,
            "target_digest": target_digest,
            "state_schema": state_schema,
            "expected_state": json.loads(state_json),
            "expected_state_digest": state_digest,
        }
        return cls(
            parent_scope_digest=parent_scope_digest,
            authority_constraint_digest=authority_constraint_digest,
            requirement_digest=requirement_digest,
            target_kind=target_kind,
            target_digest=target_digest,
            state_schema=state_schema,
            _expected_state_json=state_json,
            expected_state_digest=state_digest,
            expectation_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _EXPECTATION_FIELDS,
            contract=PRECONDITION_EXPECTATION_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["expectation_type"] != PRECONDITION_EXPECTATION_TYPE
        ):
            raise ValueError("precondition-expectation/v1 schema or type is unsupported")
        state_json, _ = _canonical_state(value["expected_state"], field="expected_state")
        return cls(
            parent_scope_digest=value["parent_scope_digest"],
            authority_constraint_digest=value["authority_constraint_digest"],
            requirement_digest=value["requirement_digest"],
            target_kind=value["target_kind"],
            target_digest=value["target_digest"],
            state_schema=value["state_schema"],
            _expected_state_json=state_json,
            expected_state_digest=value["expected_state_digest"],
            expectation_digest=value["expectation_digest"],
        )

    @property
    def expected_state(self) -> dict[str, Any]:
        return json.loads(self._expected_state_json)

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "expectation_type": PRECONDITION_EXPECTATION_TYPE,
            "parent_scope_digest": self.parent_scope_digest,
            "authority_constraint_digest": self.authority_constraint_digest,
            "requirement_digest": self.requirement_digest,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "state_schema": self.state_schema,
            "expected_state": self.expected_state,
            "expected_state_digest": self.expected_state_digest,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._claims_without_digest(),
            "expectation_digest": self.expectation_digest,
        }


@dataclass(frozen=True, slots=True)
class PreconditionObservation:
    requirement_digest: str
    target_kind: str
    target_digest: str
    state_schema: str
    observer_id: str
    source_identity: str
    clock_source_identity: str
    clock_witness_digest: str
    observed_at: str
    _observed_state_json: str
    observed_state_digest: str
    observation_digest: str

    def __post_init__(self) -> None:
        for field in (
            "requirement_digest",
            "target_digest",
            "clock_witness_digest",
            "observed_state_digest",
            "observation_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "target_kind",
            "state_schema",
            "observer_id",
            "source_identity",
            "clock_source_identity",
        ):
            _require_text(getattr(self, field), field=field)
        _require_timestamp(self.observed_at, field="observed_at")
        try:
            state = json.loads(self._observed_state_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("observed_state is invalid") from exc
        if not isinstance(state, dict):
            raise ValueError("observed_state must be an object")
        _require_json_value(state, field="observed_state")
        if self._observed_state_json != canonical_json(state):
            raise ValueError("observed_state is not canonical")
        actual_state_digest = hashlib.sha256(
            self._observed_state_json.encode("utf-8")
        ).hexdigest()
        if self.observed_state_digest != actual_state_digest:
            raise ValueError("observed_state_digest does not match observed_state")
        if self.observation_digest != _digest(self._claims_without_digest()):
            raise ValueError("observation_digest does not match precondition observation")

    @classmethod
    def create(
        cls,
        *,
        requirement_digest: str,
        target_kind: str,
        target_digest: str,
        state_schema: str,
        observer_id: str,
        source_identity: str,
        clock_witness: ClockWitness,
        observed_state: Mapping[str, Any],
    ) -> Self:
        if not isinstance(clock_witness, ClockWitness):
            raise ValueError("clock_witness is invalid")
        state_json, state_digest = _canonical_state(
            observed_state,
            field="observed_state",
        )
        claims = {
            "schema_version": 1,
            "observation_type": PRECONDITION_OBSERVATION_TYPE,
            "requirement_digest": requirement_digest,
            "target_kind": target_kind,
            "target_digest": target_digest,
            "state_schema": state_schema,
            "observer_id": observer_id,
            "source_identity": source_identity,
            "clock_source_identity": clock_witness.source_identity,
            "clock_witness_digest": clock_witness.witness_digest,
            "observed_at": clock_witness.observed_at,
            "observed_state": json.loads(state_json),
            "observed_state_digest": state_digest,
        }
        return cls(
            requirement_digest=requirement_digest,
            target_kind=target_kind,
            target_digest=target_digest,
            state_schema=state_schema,
            observer_id=observer_id,
            source_identity=source_identity,
            clock_source_identity=clock_witness.source_identity,
            clock_witness_digest=clock_witness.witness_digest,
            observed_at=clock_witness.observed_at,
            _observed_state_json=state_json,
            observed_state_digest=state_digest,
            observation_digest=_digest(claims),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _OBSERVATION_FIELDS,
            contract=PRECONDITION_OBSERVATION_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["observation_type"] != PRECONDITION_OBSERVATION_TYPE
        ):
            raise ValueError("precondition-observation/v1 schema or type is unsupported")
        state_json, _ = _canonical_state(value["observed_state"], field="observed_state")
        return cls(
            requirement_digest=value["requirement_digest"],
            target_kind=value["target_kind"],
            target_digest=value["target_digest"],
            state_schema=value["state_schema"],
            observer_id=value["observer_id"],
            source_identity=value["source_identity"],
            clock_source_identity=value["clock_source_identity"],
            clock_witness_digest=value["clock_witness_digest"],
            observed_at=value["observed_at"],
            _observed_state_json=state_json,
            observed_state_digest=value["observed_state_digest"],
            observation_digest=value["observation_digest"],
        )

    @property
    def observed_state(self) -> dict[str, Any]:
        return json.loads(self._observed_state_json)

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observation_type": PRECONDITION_OBSERVATION_TYPE,
            "requirement_digest": self.requirement_digest,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "state_schema": self.state_schema,
            "observer_id": self.observer_id,
            "source_identity": self.source_identity,
            "clock_source_identity": self.clock_source_identity,
            "clock_witness_digest": self.clock_witness_digest,
            "observed_at": self.observed_at,
            "observed_state": self.observed_state,
            "observed_state_digest": self.observed_state_digest,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._claims_without_digest(),
            "observation_digest": self.observation_digest,
        }


@dataclass(frozen=True, slots=True)
class PreconditionWitness:
    parent_scope_digest: str
    authority_constraint_digest: str
    monotonic_authority_decision_digest: str
    requirement_digest: str
    expectation_digest: str
    observation_digest: str
    target_digest: str
    expected_state_digest: str
    observed_state_digest: str
    observer_id: str
    source_identity: str
    clock_source_identity: str
    clock_witness_digest: str
    checked_at: str
    relation: str
    enforcement_class: str
    witness_digest: str

    def __post_init__(self) -> None:
        for field in (
            "parent_scope_digest",
            "authority_constraint_digest",
            "monotonic_authority_decision_digest",
            "requirement_digest",
            "expectation_digest",
            "observation_digest",
            "target_digest",
            "expected_state_digest",
            "observed_state_digest",
            "clock_witness_digest",
            "witness_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "observer_id",
            "source_identity",
            "clock_source_identity",
        ):
            _require_text(getattr(self, field), field=field)
        _require_timestamp(self.checked_at, field="checked_at")
        if self.relation != MATCH:
            raise ValueError("relation must be MATCH")
        if self.expected_state_digest != self.observed_state_digest:
            raise ValueError("MATCH witness requires equal state digests")
        if self.enforcement_class not in {
            READ_THEN_COMPARE,
            ATOMIC_PROVIDER_CONDITION,
        }:
            raise ValueError("enforcement_class is unsupported")
        if self.witness_digest != _digest(self._claims_without_digest()):
            raise ValueError("witness_digest does not match precondition witness")

    @classmethod
    def create(
        cls,
        *,
        parent: AuthorityScope,
        authority: AuthorityConstraint,
        monotonic_decision: MonotonicAuthorityDecision,
        requirement: PreconditionRequirement,
        expectation: PreconditionExpectation,
        observation: PreconditionObservation,
    ) -> Self:
        if not isinstance(parent, AuthorityScope):
            raise ValueError("parent scope is invalid")
        if not isinstance(authority, AuthorityConstraint):
            raise ValueError("authority constraint is invalid")
        if not isinstance(monotonic_decision, MonotonicAuthorityDecision):
            raise ValueError("monotonic authority decision is invalid")
        if not isinstance(requirement, PreconditionRequirement):
            raise ValueError("precondition requirement is invalid")
        if not isinstance(expectation, PreconditionExpectation):
            raise ValueError("precondition expectation is invalid")
        if not isinstance(observation, PreconditionObservation):
            raise ValueError("precondition observation is invalid")

        violations = _binding_violations(
            parent=parent,
            authority=authority,
            monotonic_decision=monotonic_decision,
            requirement=requirement,
            expectation=expectation,
            observation=observation,
        )
        if expectation.expected_state_digest != observation.observed_state_digest:
            violations.append("PRECONDITION_CHANGED")

        _, scope_start = _require_timestamp(authority.valid_from, field="authority.valid_from")
        _, scope_end = _require_timestamp(authority.valid_until, field="authority.valid_until")
        _, checked_at = _require_timestamp(observation.observed_at, field="observed_at")
        if checked_at < scope_start:
            violations.append("PRECONDITION_CHECK_BEFORE_AUTHORITY")
        if checked_at >= scope_end:
            violations.append("PRECONDITION_CHECK_AFTER_AUTHORITY_EXPIRY")

        if violations:
            raise PreconditionViolation(violations)

        claims = {
            "schema_version": 1,
            "witness_type": PRECONDITION_WITNESS_TYPE,
            "parent_scope_digest": parent.scope_digest,
            "authority_constraint_digest": authority.constraint_digest,
            "monotonic_authority_decision_digest": monotonic_decision.decision_digest,
            "requirement_digest": requirement.requirement_digest,
            "expectation_digest": expectation.expectation_digest,
            "observation_digest": observation.observation_digest,
            "target_digest": authority.target_digest,
            "expected_state_digest": expectation.expected_state_digest,
            "observed_state_digest": observation.observed_state_digest,
            "observer_id": observation.observer_id,
            "source_identity": observation.source_identity,
            "clock_source_identity": observation.clock_source_identity,
            "clock_witness_digest": observation.clock_witness_digest,
            "checked_at": observation.observed_at,
            "relation": MATCH,
            "enforcement_class": requirement.enforcement_class,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "witness_type"}
        }
        return cls(**values, witness_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _WITNESS_FIELDS,
            contract=PRECONDITION_WITNESS_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["witness_type"] != PRECONDITION_WITNESS_TYPE
        ):
            raise ValueError("precondition-witness/v1 schema or type is unsupported")
        return cls(
            parent_scope_digest=value["parent_scope_digest"],
            authority_constraint_digest=value["authority_constraint_digest"],
            monotonic_authority_decision_digest=value[
                "monotonic_authority_decision_digest"
            ],
            requirement_digest=value["requirement_digest"],
            expectation_digest=value["expectation_digest"],
            observation_digest=value["observation_digest"],
            target_digest=value["target_digest"],
            expected_state_digest=value["expected_state_digest"],
            observed_state_digest=value["observed_state_digest"],
            observer_id=value["observer_id"],
            source_identity=value["source_identity"],
            clock_source_identity=value["clock_source_identity"],
            clock_witness_digest=value["clock_witness_digest"],
            checked_at=value["checked_at"],
            relation=value["relation"],
            enforcement_class=value["enforcement_class"],
            witness_digest=value["witness_digest"],
        )

    def validate_bindings(
        self,
        *,
        parent: AuthorityScope,
        authority: AuthorityConstraint,
        monotonic_decision: MonotonicAuthorityDecision,
        requirement: PreconditionRequirement,
        expectation: PreconditionExpectation,
        observation: PreconditionObservation,
    ) -> None:
        violations = _binding_violations(
            parent=parent,
            authority=authority,
            monotonic_decision=monotonic_decision,
            requirement=requirement,
            expectation=expectation,
            observation=observation,
        )
        expected = {
            "parent_scope_digest": parent.scope_digest,
            "authority_constraint_digest": authority.constraint_digest,
            "monotonic_authority_decision_digest": monotonic_decision.decision_digest,
            "requirement_digest": requirement.requirement_digest,
            "expectation_digest": expectation.expectation_digest,
            "observation_digest": observation.observation_digest,
            "target_digest": authority.target_digest,
            "expected_state_digest": expectation.expected_state_digest,
            "observed_state_digest": observation.observed_state_digest,
            "observer_id": observation.observer_id,
            "source_identity": observation.source_identity,
            "clock_source_identity": observation.clock_source_identity,
            "clock_witness_digest": observation.clock_witness_digest,
            "checked_at": observation.observed_at,
            "enforcement_class": requirement.enforcement_class,
        }
        for field, expected_value in expected.items():
            if getattr(self, field) != expected_value:
                violations.append(f"WITNESS_{field.upper()}_MISMATCH")
        if expectation.expected_state_digest != observation.observed_state_digest:
            violations.append("PRECONDITION_CHANGED")
        _, authority_start = _require_timestamp(
            authority.valid_from,
            field="authority.valid_from",
        )
        _, authority_end = _require_timestamp(
            authority.valid_until,
            field="authority.valid_until",
        )
        _, checked_at = _require_timestamp(observation.observed_at, field="observed_at")
        if checked_at < authority_start:
            violations.append("PRECONDITION_CHECK_BEFORE_AUTHORITY")
        if checked_at >= authority_end:
            violations.append("PRECONDITION_CHECK_AFTER_AUTHORITY_EXPIRY")
        if violations:
            raise PreconditionViolation(violations)

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "witness_type": PRECONDITION_WITNESS_TYPE,
            "parent_scope_digest": self.parent_scope_digest,
            "authority_constraint_digest": self.authority_constraint_digest,
            "monotonic_authority_decision_digest": self.monotonic_authority_decision_digest,
            "requirement_digest": self.requirement_digest,
            "expectation_digest": self.expectation_digest,
            "observation_digest": self.observation_digest,
            "target_digest": self.target_digest,
            "expected_state_digest": self.expected_state_digest,
            "observed_state_digest": self.observed_state_digest,
            "observer_id": self.observer_id,
            "source_identity": self.source_identity,
            "clock_source_identity": self.clock_source_identity,
            "clock_witness_digest": self.clock_witness_digest,
            "checked_at": self.checked_at,
            "relation": self.relation,
            "enforcement_class": self.enforcement_class,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._claims_without_digest(),
            "witness_digest": self.witness_digest,
        }


def _binding_violations(
    *,
    parent: AuthorityScope,
    authority: AuthorityConstraint,
    monotonic_decision: MonotonicAuthorityDecision,
    requirement: PreconditionRequirement,
    expectation: PreconditionExpectation,
    observation: PreconditionObservation,
) -> list[str]:
    violations: list[str] = []
    try:
        computed_decision = MonotonicAuthorityChecker.check(
            parent=parent,
            child=authority,
        )
    except MonotonicAuthorityViolation:
        violations.append("MONOTONIC_AUTHORITY_INVALID")
    else:
        if computed_decision.decision_digest != monotonic_decision.decision_digest:
            violations.append("MONOTONIC_AUTHORITY_DECISION_MISMATCH")
    if monotonic_decision.parent_scope_digest != parent.scope_digest:
        violations.append("MONOTONIC_PARENT_SCOPE_MISMATCH")
    if monotonic_decision.child_constraint_digest != authority.constraint_digest:
        violations.append("MONOTONIC_CHILD_CONSTRAINT_MISMATCH")
    if requirement.capability_definition_identity != authority.capability_definition_identity:
        violations.append("CAPABILITY_DEFINITION_BINDING_MISMATCH")
    if requirement.target_kind != authority.target_kind:
        violations.append("REQUIREMENT_TARGET_KIND_MISMATCH")
    if expectation.parent_scope_digest != parent.scope_digest:
        violations.append("EXPECTATION_PARENT_SCOPE_MISMATCH")
    if expectation.authority_constraint_digest != authority.constraint_digest:
        violations.append("EXPECTATION_AUTHORITY_CONSTRAINT_MISMATCH")
    if expectation.requirement_digest != requirement.requirement_digest:
        violations.append("EXPECTATION_REQUIREMENT_MISMATCH")
    if observation.requirement_digest != requirement.requirement_digest:
        violations.append("OBSERVATION_REQUIREMENT_MISMATCH")
    for name, value in (
        ("EXPECTATION_TARGET_KIND_MISMATCH", expectation.target_kind),
        ("OBSERVATION_TARGET_KIND_MISMATCH", observation.target_kind),
    ):
        if value != authority.target_kind:
            violations.append(name)
    for name, value in (
        ("EXPECTATION_TARGET_DIGEST_MISMATCH", expectation.target_digest),
        ("OBSERVATION_TARGET_DIGEST_MISMATCH", observation.target_digest),
    ):
        if value != authority.target_digest:
            violations.append(name)
    if expectation.state_schema != requirement.state_schema:
        violations.append("EXPECTATION_STATE_SCHEMA_MISMATCH")
    if observation.state_schema != requirement.state_schema:
        violations.append("OBSERVATION_STATE_SCHEMA_MISMATCH")
    if observation.observer_id != requirement.observer_id:
        violations.append("OBSERVER_BINDING_MISMATCH")
    return violations


class PreconditionGuard:
    """Build an execution-time witness only when authoritative pre-state still matches."""

    def __init__(
        self,
        *,
        requirements: ImmutablePreconditionRequirementRegistry,
        expectation_binders: PreconditionExpectationBinderRegistry,
        observers: PreconditionObserverRegistry,
        trusted_clock: TrustedClockAuthority,
    ) -> None:
        if not isinstance(requirements, ImmutablePreconditionRequirementRegistry):
            raise ValueError("requirements registry is invalid")
        if not isinstance(expectation_binders, PreconditionExpectationBinderRegistry):
            raise ValueError("expectation binder registry is invalid")
        if not isinstance(observers, PreconditionObserverRegistry):
            raise ValueError("observer registry is invalid")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock is invalid")
        self.requirements = requirements
        self.expectation_binders = expectation_binders
        self.observers = observers
        self.trusted_clock = trusted_clock

    def witness(
        self,
        *,
        parent: AuthorityScope,
        authority: AuthorityConstraint,
        monotonic_decision: MonotonicAuthorityDecision,
        target: ExecutionTarget,
    ) -> PreconditionWitness:
        if not isinstance(parent, AuthorityScope):
            raise ValueError("parent scope is invalid")
        if not isinstance(authority, AuthorityConstraint):
            raise ValueError("authority constraint is invalid")
        if not isinstance(monotonic_decision, MonotonicAuthorityDecision):
            raise ValueError("monotonic authority decision is invalid")
        if not isinstance(target, ExecutionTarget):
            raise ValueError("target is invalid")

        initial_violations: list[str] = []
        try:
            computed_decision = MonotonicAuthorityChecker.check(
                parent=parent,
                child=authority,
            )
        except MonotonicAuthorityViolation as exc:
            raise PreconditionViolation(["MONOTONIC_AUTHORITY_INVALID"]) from exc
        if computed_decision.decision_digest != monotonic_decision.decision_digest:
            initial_violations.append("MONOTONIC_AUTHORITY_DECISION_MISMATCH")
        if target.target_kind != authority.target_kind:
            initial_violations.append("TARGET_KIND_SCOPE_MISMATCH")
        if target.target_digest != authority.target_digest:
            initial_violations.append("TARGET_DIGEST_SCOPE_MISMATCH")
        if initial_violations:
            raise PreconditionViolation(initial_violations)

        try:
            requirement = self.requirements.resolve(
                authority.capability_definition_identity
            )
        except (LookupError, ValueError) as exc:
            raise PreconditionViolation(["PRECONDITION_REQUIREMENT_NOT_FOUND"]) from exc

        requirement_violations: list[str] = []
        if requirement.target_kind != authority.target_kind:
            requirement_violations.append("REQUIREMENT_TARGET_KIND_MISMATCH")
        if (
            requirement.capability_definition_identity
            != authority.capability_definition_identity
        ):
            requirement_violations.append("CAPABILITY_DEFINITION_BINDING_MISMATCH")
        if requirement_violations:
            raise PreconditionViolation(requirement_violations)

        try:
            binder = self.expectation_binders.resolve(
                requirement.expectation_binder_id
            )
        except (LookupError, ValueError) as exc:
            raise PreconditionViolation(["EXPECTATION_BINDER_NOT_FOUND"]) from exc
        try:
            observer = self.observers.resolve(requirement.observer_id)
        except (LookupError, ValueError) as exc:
            raise PreconditionViolation(["PRECONDITION_OBSERVER_NOT_FOUND"]) from exc

        source_violations: list[str] = []
        if binder.target_kind != requirement.target_kind:
            source_violations.append("EXPECTATION_BINDER_TARGET_KIND_MISMATCH")
        if binder.state_schema != requirement.state_schema:
            source_violations.append("EXPECTATION_BINDER_STATE_SCHEMA_MISMATCH")
        if observer.target_kind != requirement.target_kind:
            source_violations.append("OBSERVER_TARGET_KIND_MISMATCH")
        if observer.state_schema != requirement.state_schema:
            source_violations.append("OBSERVER_STATE_SCHEMA_MISMATCH")
        if source_violations:
            raise PreconditionViolation(source_violations)

        try:
            expected_state = binder.bind_expected(target=target)
            expectation = PreconditionExpectation.create(
                parent_scope_digest=parent.scope_digest,
                authority_constraint_digest=authority.constraint_digest,
                requirement_digest=requirement.requirement_digest,
                target_kind=target.target_kind,
                target_digest=target.target_digest,
                state_schema=requirement.state_schema,
                expected_state=expected_state,
            )
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            raise PreconditionViolation(["EXPECTATION_BINDER_DENIED"]) from exc

        try:
            observed_state = observer.observe(target=target)
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            raise PreconditionViolation(["PRECONDITION_OBSERVER_DENIED"]) from exc

        try:
            clock_witness = self.trusted_clock.witness(environment=authority.environment)
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            raise PreconditionViolation(["TRUSTED_CLOCK_DENIED"]) from exc
        if clock_witness.source_identity != self.trusted_clock.source_identity:
            raise PreconditionViolation(["TRUSTED_CLOCK_BINDING_MISMATCH"])

        try:
            observation = PreconditionObservation.create(
                requirement_digest=requirement.requirement_digest,
                target_kind=target.target_kind,
                target_digest=target.target_digest,
                state_schema=requirement.state_schema,
                observer_id=observer.observer_id,
                source_identity=observer.source_identity,
                clock_witness=clock_witness,
                observed_state=observed_state,
            )
        except (TypeError, ValueError) as exc:
            raise PreconditionViolation(["PRECONDITION_OBSERVATION_INVALID"]) from exc

        return PreconditionWitness.create(
            parent=parent,
            authority=authority,
            monotonic_decision=monotonic_decision,
            requirement=requirement,
            expectation=expectation,
            observation=observation,
        )
