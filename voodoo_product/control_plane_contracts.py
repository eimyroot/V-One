from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .evidence_primitives import canonical_json, new_id, utc_now

EVENT_SCHEMA = "voodoo.control-plane-event.v1"
CORRELATION_SCHEMA = "voodoo.correlation-context.v1"
PROJECT_SCHEMA = "voodoo.project-descriptor.v1"
STATE_TRANSITION_SCHEMA = "voodoo.state-transition.v1"
SHARED_STATE_SCHEMA = "voodoo.shared-state-pointer.v1"

GENESIS_STATE_HASH = "GENESIS"


def _require_nonempty(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_prefixed_id(value: str, *, prefix: str, field_name: str) -> str:
    normalized = _require_nonempty(value, field_name=field_name)
    if not normalized.startswith(f"{prefix}_"):
        raise ValueError(f"{field_name} must use {prefix}_ prefix")
    return normalized


def _require_state_hash(value: str, *, field_name: str) -> str:
    if value == GENESIS_STATE_HASH:
        return value
    normalized = value.lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise ValueError(f"{field_name} must be GENESIS or a lowercase sha256 digest")
    return normalized


def _state_hash(state_json: str) -> str:
    return hashlib.sha256(state_json.encode()).hexdigest()


def _canonical_payload_json(payload: Mapping[str, Any]) -> str:
    return canonical_json(dict(payload))


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Cross-component identity carried through one governed operation graph."""

    run_id: str
    correlation_id: str
    causation_event_id: str | None = None
    schema: str = field(default=CORRELATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            _require_prefixed_id(self.run_id, prefix="run", field_name="run_id"),
        )
        object.__setattr__(
            self,
            "correlation_id",
            _require_prefixed_id(
                self.correlation_id,
                prefix="corr",
                field_name="correlation_id",
            ),
        )
        if self.causation_event_id is not None:
            object.__setattr__(
                self,
                "causation_event_id",
                _require_prefixed_id(
                    self.causation_event_id,
                    prefix="evt",
                    field_name="causation_event_id",
                ),
            )

    @classmethod
    def create(
        cls,
        *,
        run_id: str | None = None,
        correlation_id: str | None = None,
        causation_event_id: str | None = None,
    ) -> CorrelationContext:
        return cls(
            run_id=run_id or new_id("run"),
            correlation_id=correlation_id or new_id("corr"),
            causation_event_id=causation_event_id,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "causation_event_id": self.causation_event_id,
        }


@dataclass(frozen=True, slots=True)
class ProjectDescriptor:
    """Canonical project identity used by control-plane registries and events."""

    project_id: str
    canonical_repository: str
    canonical_ref: str = "refs/heads/main"
    aliases: tuple[str, ...] = ()
    schema: str = field(default=PROJECT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        project_id = _require_nonempty(self.project_id, field_name="project_id")
        repository = _require_nonempty(
            self.canonical_repository,
            field_name="canonical_repository",
        )
        canonical_ref = _require_nonempty(self.canonical_ref, field_name="canonical_ref")
        if repository.count("/") != 1 or any(character.isspace() for character in repository):
            raise ValueError("canonical_repository must use owner/repository form")
        if not canonical_ref.startswith("refs/"):
            raise ValueError("canonical_ref must be an explicit refs/... identity")

        aliases = tuple(_require_nonempty(alias, field_name="alias") for alias in self.aliases)
        if len(set(aliases)) != len(aliases):
            raise ValueError("project aliases must be unique")
        if project_id in aliases:
            raise ValueError("project_id must not also appear as an alias")

        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "canonical_repository", repository)
        object.__setattr__(self, "canonical_ref", canonical_ref)
        object.__setattr__(self, "aliases", aliases)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "canonical_repository": self.canonical_repository,
            "canonical_ref": self.canonical_ref,
            "aliases": list(self.aliases),
        }


class ImmutableProjectRegistry:
    """Fail-closed project identity resolver with collision detection."""

    def __init__(self, projects: Iterable[ProjectDescriptor]) -> None:
        by_identity: dict[str, ProjectDescriptor] = {}
        by_repository: dict[str, ProjectDescriptor] = {}

        for project in projects:
            identities = (project.project_id, *project.aliases)
            for identity in identities:
                if identity in by_identity:
                    raise ValueError(f"duplicate project identity: {identity}")
                by_identity[identity] = project
            if project.canonical_repository in by_repository:
                raise ValueError(
                    f"duplicate canonical repository: {project.canonical_repository}"
                )
            by_repository[project.canonical_repository] = project

        self._by_identity = by_identity
        self._by_repository = by_repository

    def resolve(self, identity: str) -> ProjectDescriptor:
        try:
            return self._by_identity[identity]
        except KeyError as exc:
            raise LookupError(f"unknown project identity: {identity}") from exc

    def resolve_repository(self, repository: str) -> ProjectDescriptor:
        try:
            return self._by_repository[repository]
        except KeyError as exc:
            raise LookupError(f"unknown project repository: {repository}") from exc


@dataclass(frozen=True, slots=True)
class StateTransition:
    """Full-state transition whose digest is recomputed at the trust boundary."""

    previous_state_hash: str
    next_state_json: str
    next_state_hash: str
    schema: str = field(default=STATE_TRANSITION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        previous = _require_state_hash(
            self.previous_state_hash,
            field_name="previous_state_hash",
        )
        expected_next = _state_hash(self.next_state_json)
        supplied_next = _require_state_hash(
            self.next_state_hash,
            field_name="next_state_hash",
        )
        if supplied_next == GENESIS_STATE_HASH or supplied_next != expected_next:
            raise ValueError("next_state_hash does not match next_state_json")
        try:
            parsed = json.loads(self.next_state_json)
        except json.JSONDecodeError as exc:
            raise ValueError("next_state_json must contain valid JSON") from exc
        canonical = canonical_json(parsed)
        if canonical != self.next_state_json:
            raise ValueError("next_state_json must use canonical JSON encoding")

        object.__setattr__(self, "previous_state_hash", previous)
        object.__setattr__(self, "next_state_hash", supplied_next)

    @classmethod
    def create(
        cls,
        *,
        previous_state_hash: str,
        next_state: Mapping[str, Any],
    ) -> StateTransition:
        next_state_json = _canonical_payload_json(next_state)
        return cls(
            previous_state_hash=previous_state_hash,
            next_state_json=next_state_json,
            next_state_hash=_state_hash(next_state_json),
        )

    def state(self) -> dict[str, Any]:
        value = json.loads(self.next_state_json)
        if not isinstance(value, dict):
            raise ValueError("shared state must decode to an object")
        return value

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "previous_state_hash": self.previous_state_hash,
            "next_state_hash": self.next_state_hash,
            "next_state": self.state(),
        }


@dataclass(frozen=True, slots=True)
class ControlPlaneEvent:
    """Immutable cross-system event envelope suitable for the canonical AuditLedger."""

    event_id: str
    event_type: str
    occurred_at: str
    actor_id: str
    component: str
    action: str
    resource: str
    status: str
    correlation: CorrelationContext
    project: ProjectDescriptor
    payload_json: str
    evidence_refs: tuple[str, ...] = ()
    decision_refs: tuple[str, ...] = ()
    state_transition: StateTransition | None = None
    schema: str = field(default=EVENT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_id",
            _require_prefixed_id(self.event_id, prefix="evt", field_name="event_id"),
        )
        for name in ("event_type", "occurred_at", "actor_id", "component", "action", "resource"):
            object.__setattr__(
                self,
                name,
                _require_nonempty(str(getattr(self, name)), field_name=name),
            )
        status = _require_nonempty(self.status, field_name="status").upper()
        if status not in {"OBSERVED", "VERIFIED", "REJECTED", "FAILED"}:
            raise ValueError("status must be OBSERVED, VERIFIED, REJECTED, or FAILED")
        object.__setattr__(self, "status", status)

        try:
            parsed_payload = json.loads(self.payload_json)
        except json.JSONDecodeError as exc:
            raise ValueError("payload_json must contain valid JSON") from exc
        if not isinstance(parsed_payload, dict):
            raise ValueError("event payload must decode to an object")
        if canonical_json(parsed_payload) != self.payload_json:
            raise ValueError("payload_json must use canonical JSON encoding")

        evidence_refs = tuple(
            _require_nonempty(reference, field_name="evidence_ref")
            for reference in self.evidence_refs
        )
        decision_refs = tuple(
            _require_nonempty(reference, field_name="decision_ref")
            for reference in self.decision_refs
        )
        if len(set(evidence_refs)) != len(evidence_refs):
            raise ValueError("evidence_refs must be unique")
        if len(set(decision_refs)) != len(decision_refs):
            raise ValueError("decision_refs must be unique")
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "decision_refs", decision_refs)

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        actor_id: str,
        component: str,
        action: str,
        resource: str,
        status: str,
        correlation: CorrelationContext,
        project: ProjectDescriptor,
        payload: Mapping[str, Any],
        evidence_refs: Iterable[str] = (),
        decision_refs: Iterable[str] = (),
        state_transition: StateTransition | None = None,
        event_id: str | None = None,
        occurred_at: str | None = None,
    ) -> ControlPlaneEvent:
        return cls(
            event_id=event_id or new_id("evt"),
            event_type=event_type,
            occurred_at=occurred_at or utc_now(),
            actor_id=actor_id,
            component=component,
            action=action,
            resource=resource,
            status=status,
            correlation=correlation,
            project=project,
            payload_json=_canonical_payload_json(payload),
            evidence_refs=tuple(evidence_refs),
            decision_refs=tuple(decision_refs),
            state_transition=state_transition,
        )

    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("event payload must decode to an object")
        return value

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "actor_id": self.actor_id,
            "component": self.component,
            "action": self.action,
            "resource": self.resource,
            "status": self.status,
            "correlation": self.correlation.as_dict(),
            "project": self.project.as_dict(),
            "payload": self.payload(),
            "evidence_refs": list(self.evidence_refs),
            "decision_refs": list(self.decision_refs),
            "state_transition": (
                self.state_transition.as_dict() if self.state_transition is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class SharedStatePointer:
    """Current deterministic projection derived from verified state-transition events."""

    project_id: str
    revision: int
    state_hash: str
    state_json: str
    last_event_id: str | None
    last_correlation_id: str | None
    updated_at: str | None
    schema: str = field(default=SHARED_STATE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "project_id",
            _require_nonempty(self.project_id, field_name="project_id"),
        )
        if self.revision < 0:
            raise ValueError("revision must be non-negative")
        state_hash = _require_state_hash(self.state_hash, field_name="state_hash")
        if self.revision == 0:
            if state_hash != GENESIS_STATE_HASH:
                raise ValueError("revision zero must use GENESIS state hash")
            if self.state_json != "{}":
                raise ValueError("revision zero must use empty canonical state")
            if any(
                value is not None
                for value in (self.last_event_id, self.last_correlation_id, self.updated_at)
            ):
                raise ValueError("genesis pointer must not claim event lineage")
        else:
            if state_hash == GENESIS_STATE_HASH:
                raise ValueError("non-genesis revision requires a sha256 state hash")
            if _state_hash(self.state_json) != state_hash:
                raise ValueError("state_hash does not match state_json")
            if not all((self.last_event_id, self.last_correlation_id, self.updated_at)):
                raise ValueError("non-genesis pointer requires complete event lineage")

        parsed = json.loads(self.state_json)
        if not isinstance(parsed, dict) or canonical_json(parsed) != self.state_json:
            raise ValueError("state_json must be a canonical JSON object")
        object.__setattr__(self, "state_hash", state_hash)

    @classmethod
    def genesis(cls, project_id: str) -> SharedStatePointer:
        return cls(
            project_id=project_id,
            revision=0,
            state_hash=GENESIS_STATE_HASH,
            state_json="{}",
            last_event_id=None,
            last_correlation_id=None,
            updated_at=None,
        )

    def state(self) -> dict[str, Any]:
        value = json.loads(self.state_json)
        if not isinstance(value, dict):
            raise ValueError("state_json must decode to an object")
        return value

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "revision": self.revision,
            "state_hash": self.state_hash,
            "state": self.state(),
            "last_event_id": self.last_event_id,
            "last_correlation_id": self.last_correlation_id,
            "updated_at": self.updated_at,
        }
