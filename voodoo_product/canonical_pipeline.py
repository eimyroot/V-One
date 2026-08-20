from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .dispatch_envelope import DispatchEnvelope
from .monotonic_authority import AuthorityConstraint, AuthorityScope
from .terminal_profile import ImmutableCapabilityTerminalProfileRegistry
from .vop_vocabulary import OPERATION_TERMINAL_PROFILES


class _SnapshotCreator(Protocol):
    db: object

    def create_snapshot(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> object: ...


class _GrantService(Protocol):
    db: object

    def issue_and_store(self, *, snapshot: object, authority: AuthorityConstraint) -> object: ...


class _OutboxService(Protocol):
    db: object
    grant_service: object

    def consume_and_enqueue(self, *, jti: str) -> object: ...


class _Coordinator(Protocol):
    def admit(self, *, envelope: DispatchEnvelope) -> object: ...

    def acquire(self, *, admission_id: str) -> object: ...


class _TerminalProfileRegistry(Protocol):
    def resolve(
        self,
        *,
        capability_definition_identity: str,
        capability: str,
    ) -> object: ...


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


def _require_epoch(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("execution_epoch must be an integer >= 1")
    return value


def _attribute(value: object, name: str) -> object:
    try:
        return getattr(value, name)
    except AttributeError as exc:
        raise RuntimeError(f"canonical pipeline object is missing {name}") from exc


def _require_equal(*, field: str, expected: object, actual: object) -> None:
    if actual != expected:
        raise PermissionError(f"CANONICAL_PIPELINE_{field.upper()}_MISMATCH")


@dataclass(frozen=True, slots=True)
class CanonicalPreparedExecution:
    """Immutable pre-effect checkpoint plus retained runtime objects for the terminal router.

    Reaching this value proves only that the current authority/durable-dispatch prefix was composed
    through a current execution lease. Retained objects are process-local composition context, not a
    serialized evidence contract. The summary fields remain the explicit content-bound identifiers.
    """

    terminal_profile: str
    terminal_profile_binding_digest: str
    execution_id: str
    request_id: str
    capability: str
    capability_definition_identity: str
    environment: str
    target_digest: str
    authorization_snapshot_digest: str
    grant_digest: str
    grant_jti: str
    outbox_entry_digest: str
    envelope_digest: str
    admission_digest: str
    lease_id: str
    lease_digest: str
    execution_epoch: int
    execution_capsule_digest: str
    snapshot: object = field(repr=False, compare=False)
    grant: object = field(repr=False, compare=False)
    outbox: object = field(repr=False, compare=False)
    envelope: object = field(repr=False, compare=False)
    admission: object = field(repr=False, compare=False)
    lease: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.terminal_profile not in OPERATION_TERMINAL_PROFILES:
            raise ValueError("terminal_profile is unsupported")
        for field_name in (
            "execution_id",
            "request_id",
            "capability",
            "environment",
            "grant_jti",
        ):
            _require_text(getattr(self, field_name), field=field_name)
        for field_name in (
            "terminal_profile_binding_digest",
            "capability_definition_identity",
            "target_digest",
            "authorization_snapshot_digest",
            "grant_digest",
            "outbox_entry_digest",
            "envelope_digest",
            "admission_digest",
            "lease_id",
            "lease_digest",
            "execution_capsule_digest",
        ):
            _require_digest(getattr(self, field_name), field=field_name)
        _require_epoch(self.execution_epoch)

        for name, value in (
            ("snapshot", self.snapshot),
            ("grant", self.grant),
            ("outbox", self.outbox),
            ("envelope", self.envelope),
            ("admission", self.admission),
            ("lease", self.lease),
        ):
            if value is None:
                raise ValueError(f"{name} runtime context is required")


class CanonicalOperationPipeline:
    """Compose the current V-One authority and durable-dispatch prefix exactly once.

    Terminal semantics are not caller-controlled. After the authoritative snapshot resolves the exact
    capability definition identity, this pipeline resolves one immutable terminal-profile allowlist
    binding and carries it forward. The pipeline still stops before any Runner/provider effect.
    """

    def __init__(
        self,
        *,
        snapshot_creator: _SnapshotCreator,
        grant_service: _GrantService,
        outbox_service: _OutboxService,
        coordinator: _Coordinator,
        terminal_profile_registry: _TerminalProfileRegistry,
        envelope_revision: str,
    ) -> None:
        for owner, method in (
            (snapshot_creator, "create_snapshot"),
            (grant_service, "issue_and_store"),
            (outbox_service, "consume_and_enqueue"),
            (coordinator, "admit"),
            (coordinator, "acquire"),
            (terminal_profile_registry, "resolve"),
        ):
            if not callable(getattr(owner, method, None)):
                raise ValueError(f"canonical pipeline dependency must implement {method}")

        snapshot_db = getattr(snapshot_creator, "db", None)
        grant_db = getattr(grant_service, "db", None)
        outbox_db = getattr(outbox_service, "db", None)
        if snapshot_db is None or grant_db is None or outbox_db is None:
            raise ValueError("canonical pipeline durable services must expose a database boundary")
        if snapshot_db is not grant_db or grant_db is not outbox_db:
            raise ValueError("canonical pipeline durable services must share one database boundary")
        if getattr(outbox_service, "grant_service", None) is not grant_service:
            raise ValueError("canonical pipeline outbox must use the supplied grant service")

        self.snapshot_creator = snapshot_creator
        self.grant_service = grant_service
        self.outbox_service = outbox_service
        self.coordinator = coordinator
        self.terminal_profile_registry = terminal_profile_registry
        self.envelope_revision = _require_text(
            envelope_revision,
            field="envelope_revision",
        )

    def prepare(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> CanonicalPreparedExecution:
        """Prepare one operation through durable lease acquisition, then stop pre-effect."""

        actor_id = _require_text(actor_id, field="actor_id")
        request_id = _require_text(request_id, field="request_id")
        idempotency_key = _require_text(idempotency_key, field="idempotency_key")
        correlation_id = _require_text(correlation_id, field="correlation_id")

        snapshot = self.snapshot_creator.create_snapshot(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        _require_equal(
            field="request_id",
            expected=request_id,
            actual=_attribute(snapshot, "request_id"),
        )
        _require_equal(
            field="actor_id",
            expected=actor_id,
            actual=_attribute(snapshot, "actor_id"),
        )
        capability = _require_text(_attribute(snapshot, "capability"), field="capability")
        capability_definition_identity = _require_digest(
            _attribute(snapshot, "capability_definition_identity"),
            field="capability_definition_identity",
        )
        profile_binding = self.terminal_profile_registry.resolve(
            capability_definition_identity=capability_definition_identity,
            capability=capability,
        )
        terminal_profile = _require_text(
            _attribute(profile_binding, "terminal_profile"),
            field="terminal_profile",
        )
        if terminal_profile not in OPERATION_TERMINAL_PROFILES:
            raise PermissionError("CANONICAL_PIPELINE_TERMINAL_PROFILE_UNSUPPORTED")
        terminal_profile_binding_digest = _require_digest(
            _attribute(profile_binding, "binding_digest"),
            field="terminal_profile_binding_digest",
        )

        scope = AuthorityScope.from_snapshot(snapshot)  # type: ignore[arg-type]
        authority = AuthorityConstraint.from_scope(scope)
        grant = self.grant_service.issue_and_store(
            snapshot=snapshot,
            authority=authority,
        )
        for field_name, expected, actual in (
            (
                "snapshot_digest",
                _attribute(snapshot, "snapshot_digest"),
                _attribute(grant, "authorization_snapshot_digest"),
            ),
            ("execution_id", _attribute(snapshot, "execution_id"), _attribute(grant, "execution_id")),
            ("capability", capability, _attribute(grant, "capability")),
            (
                "capability_definition_identity",
                capability_definition_identity,
                _attribute(grant, "capability_definition_identity"),
            ),
        ):
            _require_equal(field=field_name, expected=expected, actual=actual)

        outbox = self.outbox_service.consume_and_enqueue(
            jti=_require_text(_attribute(grant, "jti"), field="grant.jti")
        )
        for field_name, expected, actual in (
            ("grant_digest", _attribute(grant, "grant_digest"), _attribute(outbox, "grant_digest")),
            ("execution_id", _attribute(grant, "execution_id"), _attribute(outbox, "execution_id")),
            (
                "snapshot_digest",
                _attribute(grant, "authorization_snapshot_digest"),
                _attribute(outbox, "authorization_snapshot_digest"),
            ),
            ("capability", _attribute(grant, "capability"), _attribute(outbox, "capability")),
            (
                "capability_definition_identity",
                _attribute(grant, "capability_definition_identity"),
                _attribute(outbox, "capability_definition_identity"),
            ),
            ("target_digest", _attribute(grant, "target_digest"), _attribute(outbox, "target_digest")),
        ):
            _require_equal(field=field_name, expected=expected, actual=actual)

        envelope = DispatchEnvelope.create(
            outbox_entry=outbox,  # type: ignore[arg-type]
            envelope_revision=self.envelope_revision,
        )
        envelope.assert_bound_to(outbox)  # type: ignore[arg-type]
        inbox_result = self.coordinator.admit(envelope=envelope)
        admission = _attribute(inbox_result, "admission")
        for field_name, expected, actual in (
            ("dispatch_id", envelope.dispatch_id, _attribute(admission, "dispatch_id")),
            ("execution_id", envelope.execution_id, _attribute(admission, "execution_id")),
            (
                "capsule_digest",
                envelope.execution_capsule_digest,
                _attribute(admission, "execution_capsule_digest"),
            ),
        ):
            _require_equal(field=field_name, expected=expected, actual=actual)

        lease_result = self.coordinator.acquire(
            admission_id=_require_digest(
                _attribute(admission, "admission_id"),
                field="admission.admission_id",
            )
        )
        lease = _attribute(lease_result, "lease")
        for field_name, expected, actual in (
            ("admission_id", _attribute(admission, "admission_id"), _attribute(lease, "admission_id")),
            ("execution_id", envelope.execution_id, _attribute(lease, "execution_id")),
            (
                "capsule_digest",
                envelope.execution_capsule_digest,
                _attribute(lease, "execution_capsule_digest"),
            ),
        ):
            _require_equal(field=field_name, expected=expected, actual=actual)

        return CanonicalPreparedExecution(
            terminal_profile=terminal_profile,
            terminal_profile_binding_digest=terminal_profile_binding_digest,
            execution_id=_require_text(envelope.execution_id, field="execution_id"),
            request_id=_require_text(envelope.request_id, field="request_id"),
            capability=_require_text(envelope.capability, field="capability"),
            capability_definition_identity=_require_digest(
                envelope.capability_definition_identity,
                field="capability_definition_identity",
            ),
            environment=_require_text(envelope.environment, field="environment"),
            target_digest=_require_digest(envelope.target_digest, field="target_digest"),
            authorization_snapshot_digest=_require_digest(
                envelope.authorization_snapshot_digest,
                field="authorization_snapshot_digest",
            ),
            grant_digest=_require_digest(envelope.grant_digest, field="grant_digest"),
            grant_jti=_require_text(envelope.jti, field="grant_jti"),
            outbox_entry_digest=_require_digest(
                envelope.outbox_entry_digest,
                field="outbox_entry_digest",
            ),
            envelope_digest=_require_digest(envelope.envelope_digest, field="envelope_digest"),
            admission_digest=_require_digest(
                _attribute(admission, "admission_digest"),
                field="admission_digest",
            ),
            lease_id=_require_digest(_attribute(lease, "lease_id"), field="lease_id"),
            lease_digest=_require_digest(_attribute(lease, "lease_digest"), field="lease_digest"),
            execution_epoch=_require_epoch(_attribute(lease, "execution_epoch")),
            execution_capsule_digest=_require_digest(
                envelope.execution_capsule_digest,
                field="execution_capsule_digest",
            ),
            snapshot=snapshot,
            grant=grant,
            outbox=outbox,
            envelope=envelope,
            admission=admission,
            lease=lease,
        )
