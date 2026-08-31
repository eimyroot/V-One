from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .control_plane_contracts import ControlPlaneEvent, CorrelationContext, ProjectDescriptor
from .control_plane_foundation import ControlPlaneEventLog
from .persistence import ProductDatabaseAdapter

READ_PREPARED_EVENT = "runtime.read.prepared"
READ_RESUMED_EVENT = "runtime.read.resumed"
READ_RUNNER_OBSERVED_EVENT = "runtime.read.runner_observed"
READ_COMPLETED_EVENT = "runtime.read.durably_completed"
READ_VERIFIER_OBSERVED_EVENT = "runtime.read.verifier_observed"
READ_VERIFIED_EVENT = "runtime.read.verified"


class _ReadRuntime(Protocol):
    def run_read_only(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> object: ...


def _attribute(value: object, name: str) -> Any:
    try:
        return getattr(value, name)
    except AttributeError as exc:
        raise RuntimeError(f"control-plane runtime object is missing {name}") from exc


def _require_equal(*, field: str, expected: object, actual: object) -> None:
    if actual != expected:
        raise PermissionError(f"CONTROL_PLANE_RUNTIME_{field.upper()}_MISMATCH")


def _require_one_of(*, field: str, actual: object, allowed: set[str]) -> str:
    if not isinstance(actual, str) or actual not in allowed:
        raise PermissionError(f"CONTROL_PLANE_RUNTIME_{field.upper()}_MISMATCH")
    return actual


def _audit_hash(value: dict[str, Any]) -> str:
    event_hash = value.get("event_hash")
    if not isinstance(event_hash, str) or len(event_hash) != 64:
        raise RuntimeError("control-plane audit append returned an invalid event hash")
    return event_hash


def _caused_by(correlation: CorrelationContext, event: ControlPlaneEvent) -> CorrelationContext:
    return CorrelationContext(
        run_id=correlation.run_id,
        correlation_id=correlation.correlation_id,
        causation_event_id=event.event_id,
    )


@dataclass(frozen=True, slots=True)
class ControlPlaneReadRuntimeResult:
    """READ terminal result plus normalized control-plane and audit lineage."""

    terminal_result: object = field(repr=False, compare=False)
    prepared_event: ControlPlaneEvent
    runner_observation_event: ControlPlaneEvent
    completion_event: ControlPlaneEvent
    verifier_observation_event: ControlPlaneEvent
    verification_event: ControlPlaneEvent
    audit_event_hashes: tuple[str, ...]


class ControlPlaneReadRuntime:
    """Correlation-aware wrapper over the canonical READ runtime.

    `run_id` and `correlation_id` are control-plane observability identities only. They never
    select capability, issue authority, modify content-addressed execution contracts, or widen
    provider permissions. The wrapped canonical runtime remains authoritative for execution.
    """

    def __init__(
        self,
        *,
        runtime: _ReadRuntime,
        database: ProductDatabaseAdapter,
        event_log: ControlPlaneEventLog,
        project: ProjectDescriptor,
    ) -> None:
        if not callable(getattr(runtime, "run_read_only", None)):
            raise ValueError("runtime must implement run_read_only")
        if not isinstance(database, ProductDatabaseAdapter):
            raise ValueError("database must implement ProductDatabaseAdapter")
        if not isinstance(event_log, ControlPlaneEventLog):
            raise ValueError("event_log must be ControlPlaneEventLog")
        if getattr(event_log.audit_ledger, "db", None) is not database:
            raise ValueError("control-plane event log must share the supplied database")
        if not isinstance(project, ProjectDescriptor):
            raise ValueError("project must be ProjectDescriptor")

        self.runtime = runtime
        self.database = database
        self.event_log = event_log
        self.project = project

    def run_read_only(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation: CorrelationContext,
    ) -> ControlPlaneReadRuntimeResult:
        if not isinstance(correlation, CorrelationContext):
            raise ValueError("correlation must be CorrelationContext")

        terminal_result = self.runtime.run_read_only(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation.correlation_id,
        )
        events = self._bind_read_result(
            terminal_result,
            actor_id=actor_id,
            request_id=request_id,
            correlation=correlation,
            invocation="fresh",
        )
        return self._record_result(terminal_result=terminal_result, events=events)

    def run_resumed_read_only(
        self,
        *,
        actor_id: str,
        execution_id: str,
        correlation: CorrelationContext,
    ) -> ControlPlaneReadRuntimeResult:
        if not isinstance(correlation, CorrelationContext):
            raise ValueError("correlation must be CorrelationContext")
        resumed = getattr(self.runtime, "run_resumed_read_only", None)
        if not callable(resumed):
            raise RuntimeError("CONTROL_PLANE_RUNTIME_RESUME_NOT_CONFIGURED")

        terminal_result = resumed(
            actor_id=actor_id,
            execution_id=execution_id,
        )
        prepared = _attribute(terminal_result, "prepared")
        _require_equal(
            field="resume_execution_id",
            expected=execution_id,
            actual=_attribute(prepared, "execution_id"),
        )
        request_id = str(_attribute(prepared, "request_id"))
        events = self._bind_read_result(
            terminal_result,
            actor_id=actor_id,
            request_id=request_id,
            correlation=correlation,
            invocation="resume",
        )
        return self._record_result(terminal_result=terminal_result, events=events)

    def _record_result(
        self,
        *,
        terminal_result: object,
        events: tuple[
            ControlPlaneEvent,
            ControlPlaneEvent,
            ControlPlaneEvent,
            ControlPlaneEvent,
            ControlPlaneEvent,
        ],
    ) -> ControlPlaneReadRuntimeResult:
        with self.database.transaction() as connection:
            audit_hashes = tuple(
                _audit_hash(self.event_log.append(connection, event=event))
                for event in events
            )

        return ControlPlaneReadRuntimeResult(
            terminal_result=terminal_result,
            prepared_event=events[0],
            runner_observation_event=events[1],
            completion_event=events[2],
            verifier_observation_event=events[3],
            verification_event=events[4],
            audit_event_hashes=audit_hashes,
        )

    def _bind_read_result(
        self,
        terminal_result: object,
        *,
        actor_id: str,
        request_id: str,
        correlation: CorrelationContext,
        invocation: str,
    ) -> tuple[
        ControlPlaneEvent,
        ControlPlaneEvent,
        ControlPlaneEvent,
        ControlPlaneEvent,
        ControlPlaneEvent,
    ]:
        if invocation not in {"fresh", "resume"}:
            raise ValueError("control-plane read invocation is unsupported")

        prepared = _attribute(terminal_result, "prepared")
        snapshot = _attribute(prepared, "snapshot")
        grant = _attribute(prepared, "grant")
        outbox = _attribute(prepared, "outbox")
        envelope = _attribute(prepared, "envelope")
        admission = _attribute(prepared, "admission")
        lease = _attribute(prepared, "lease")

        execution_id = _attribute(prepared, "execution_id")
        execution_epoch = _attribute(prepared, "execution_epoch")
        target_digest = _attribute(prepared, "target_digest")
        snapshot_digest = _attribute(prepared, "authorization_snapshot_digest")
        grant_digest = _attribute(prepared, "grant_digest")
        outbox_digest = _attribute(prepared, "outbox_entry_digest")
        envelope_digest = _attribute(prepared, "envelope_digest")
        admission_digest = _attribute(prepared, "admission_digest")
        lease_id = _attribute(prepared, "lease_id")
        lease_digest = _attribute(prepared, "lease_digest")

        for field_name, expected, actual in (
            ("request_id", request_id, _attribute(prepared, "request_id")),
            ("snapshot_request_id", request_id, _attribute(snapshot, "request_id")),
            ("actor_id", actor_id, _attribute(snapshot, "actor_id")),
            ("snapshot_execution_id", execution_id, _attribute(snapshot, "execution_id")),
            ("snapshot_digest", snapshot_digest, _attribute(snapshot, "snapshot_digest")),
            ("grant_execution_id", execution_id, _attribute(grant, "execution_id")),
            ("grant_digest", grant_digest, _attribute(grant, "grant_digest")),
            ("outbox_execution_id", execution_id, _attribute(outbox, "execution_id")),
            ("outbox_digest", outbox_digest, _attribute(outbox, "entry_digest")),
            ("envelope_execution_id", execution_id, _attribute(envelope, "execution_id")),
            ("envelope_digest", envelope_digest, _attribute(envelope, "envelope_digest")),
            ("admission_execution_id", execution_id, _attribute(admission, "execution_id")),
            ("admission_digest", admission_digest, _attribute(admission, "admission_digest")),
            ("lease_execution_id", execution_id, _attribute(lease, "execution_id")),
            ("lease_id", lease_id, _attribute(lease, "lease_id")),
            ("lease_digest", lease_digest, _attribute(lease, "lease_digest")),
            ("lease_epoch", execution_epoch, _attribute(lease, "execution_epoch")),
        ):
            _require_equal(field=field_name, expected=expected, actual=actual)

        runner_observation = _attribute(terminal_result, "runner_observation")
        durable_completion = _attribute(terminal_result, "durable_completion")
        verification_boundary = _attribute(terminal_result, "verification_boundary")
        verifier_identity = _attribute(terminal_result, "verifier_identity")
        verifier_decision = _attribute(terminal_result, "verifier_credential_decision")
        verifier_observation = _attribute(terminal_result, "verifier_observation")
        observed_post_state = _attribute(terminal_result, "observed_post_state")
        verification_strength = _attribute(terminal_result, "verification_strength")
        verification_result = _attribute(terminal_result, "verification_result")

        runner_observation_digest = _attribute(runner_observation, "observation_digest")
        completion_digest = _attribute(durable_completion, "completion_digest")
        completion_lease = _attribute(durable_completion, "lease")
        completion_outcome = _require_one_of(
            field="completion_outcome",
            actual=_attribute(durable_completion, "outcome"),
            allowed={"COMPLETED", "DUPLICATE_COMPLETION"},
        )
        boundary_digest = _attribute(verification_boundary, "boundary_digest")
        verifier_id = _attribute(verifier_identity, "verifier_id")
        verifier_identity_digest = _attribute(verifier_identity, "identity_digest")
        verifier_decision_id = _attribute(verifier_decision, "decision_id")
        verifier_decision_digest = _attribute(verifier_decision, "decision_digest")
        verifier_observation_digest = _attribute(verifier_observation, "observation_digest")
        observed_state_digest = _attribute(observed_post_state, "state_digest")
        strength_digest = _attribute(verification_strength, "strength_digest")

        for field_name, expected, actual in (
            (
                "runner_execution_id",
                execution_id,
                _attribute(runner_observation, "execution_id"),
            ),
            (
                "runner_execution_epoch",
                execution_epoch,
                _attribute(runner_observation, "execution_epoch"),
            ),
            (
                "runner_target_digest",
                target_digest,
                _attribute(runner_observation, "target_digest"),
            ),
            (
                "runner_lease_digest",
                lease_digest,
                _attribute(runner_observation, "lease_digest"),
            ),
            (
                "completion_execution_id",
                execution_id,
                _attribute(completion_lease, "execution_id"),
            ),
            ("completion_lease_id", lease_id, _attribute(completion_lease, "lease_id")),
            (
                "completion_lease_digest",
                lease_digest,
                _attribute(completion_lease, "lease_digest"),
            ),
            (
                "completion_execution_epoch",
                execution_epoch,
                _attribute(completion_lease, "execution_epoch"),
            ),
            (
                "completion_digest",
                runner_observation_digest,
                completion_digest,
            ),
            (
                "boundary_execution_id",
                execution_id,
                _attribute(verification_boundary, "execution_id"),
            ),
            (
                "boundary_execution_epoch",
                execution_epoch,
                _attribute(verification_boundary, "execution_epoch"),
            ),
            (
                "boundary_target_digest",
                target_digest,
                _attribute(verification_boundary, "target_digest"),
            ),
            (
                "boundary_runner_observation",
                runner_observation_digest,
                _attribute(verification_boundary, "runner_observation_digest"),
            ),
            (
                "verifier_decision_execution_id",
                execution_id,
                _attribute(verifier_decision, "execution_id"),
            ),
            (
                "verifier_decision_execution_epoch",
                execution_epoch,
                _attribute(verifier_decision, "execution_epoch"),
            ),
            (
                "verifier_decision_target_digest",
                target_digest,
                _attribute(verifier_decision, "target_digest"),
            ),
            (
                "verifier_decision_runner_observation",
                runner_observation_digest,
                _attribute(verifier_decision, "runner_observation_digest"),
            ),
            (
                "verifier_decision_boundary",
                boundary_digest,
                _attribute(verifier_decision, "verification_boundary_digest"),
            ),
            (
                "verifier_decision_verifier_id",
                verifier_id,
                _attribute(verifier_decision, "verifier_id"),
            ),
            (
                "verifier_decision_verifier_identity",
                verifier_identity_digest,
                _attribute(verifier_decision, "verifier_identity_digest"),
            ),
            (
                "verifier_observation_execution_id",
                execution_id,
                _attribute(verifier_observation, "execution_id"),
            ),
            (
                "verifier_observation_execution_epoch",
                execution_epoch,
                _attribute(verifier_observation, "execution_epoch"),
            ),
            (
                "verifier_observation_target_digest",
                target_digest,
                _attribute(verifier_observation, "target_digest"),
            ),
            (
                "verifier_observation_runner_observation",
                runner_observation_digest,
                _attribute(verifier_observation, "runner_observation_digest"),
            ),
            (
                "verifier_observation_boundary",
                boundary_digest,
                _attribute(verifier_observation, "verification_boundary_digest"),
            ),
            (
                "verifier_observation_verifier_id",
                verifier_id,
                _attribute(verifier_observation, "verifier_id"),
            ),
            (
                "verifier_observation_verifier_identity",
                verifier_identity_digest,
                _attribute(verifier_observation, "verifier_identity_digest"),
            ),
            (
                "verifier_observation_decision_id",
                verifier_decision_id,
                _attribute(verifier_observation, "verifier_credential_decision_id"),
            ),
            (
                "verifier_observation_decision_digest",
                verifier_decision_digest,
                _attribute(verifier_observation, "verifier_credential_decision_digest"),
            ),
            (
                "verification_execution_id",
                execution_id,
                _attribute(verification_result, "execution_id"),
            ),
            (
                "verification_execution_epoch",
                execution_epoch,
                _attribute(verification_result, "execution_epoch"),
            ),
            (
                "verification_target_digest",
                target_digest,
                _attribute(verification_result, "target_digest"),
            ),
            (
                "verification_runner_observation",
                runner_observation_digest,
                _attribute(verification_result, "runner_observation_digest"),
            ),
            (
                "verification_verifier_observation",
                verifier_observation_digest,
                _attribute(verification_result, "verifier_observation_digest"),
            ),
            (
                "verification_boundary",
                boundary_digest,
                _attribute(verification_result, "verification_boundary_digest"),
            ),
            (
                "verification_verifier_id",
                verifier_id,
                _attribute(verification_result, "verifier_id"),
            ),
            (
                "verification_verifier_identity",
                verifier_identity_digest,
                _attribute(verification_result, "verifier_identity_digest"),
            ),
            (
                "verification_observed_state",
                observed_state_digest,
                _attribute(verification_result, "observed_post_state_digest"),
            ),
            (
                "verification_strength",
                strength_digest,
                _attribute(verification_result, "verification_strength_digest"),
            ),
        ):
            _require_equal(field=field_name, expected=expected, actual=actual)

        prepared_event = ControlPlaneEvent.create(
            event_type=READ_PREPARED_EVENT if invocation == "fresh" else READ_RESUMED_EVENT,
            actor_id=actor_id,
            component="canonical_operation_runtime",
            action="prepare_read_only" if invocation == "fresh" else "resume_read_only",
            resource=str(execution_id),
            status="VERIFIED",
            correlation=correlation,
            project=self.project,
            payload={
                "invocation": invocation,
                "request_id": request_id,
                "execution_id": execution_id,
                "execution_epoch": execution_epoch,
                "capability": _attribute(prepared, "capability"),
                "authorization_snapshot_digest": snapshot_digest,
                "grant_digest": grant_digest,
                "outbox_entry_digest": outbox_digest,
                "envelope_digest": envelope_digest,
                "admission_digest": admission_digest,
                "lease_id": lease_id,
                "lease_digest": lease_digest,
                "execution_capsule_digest": _attribute(
                    prepared,
                    "execution_capsule_digest",
                ),
            },
            evidence_refs=(
                snapshot_digest,
                grant_digest,
                outbox_digest,
                envelope_digest,
                admission_digest,
                lease_digest,
            ),
        )

        runner_event = ControlPlaneEvent.create(
            event_type=READ_RUNNER_OBSERVED_EVENT,
            actor_id=actor_id,
            component="canonical_read_terminal",
            action="runner_observe_read_only",
            resource=str(execution_id),
            status="OBSERVED",
            correlation=_caused_by(correlation, prepared_event),
            project=self.project,
            occurred_at=_attribute(runner_observation, "observed_at"),
            payload={
                "invocation": invocation,
                "request_id": request_id,
                "execution_id": execution_id,
                "execution_epoch": execution_epoch,
                "target_digest": target_digest,
                "lease_id": lease_id,
                "lease_digest": lease_digest,
                "runner_observation_digest": runner_observation_digest,
            },
            evidence_refs=(
                runner_observation_digest,
                lease_digest,
                target_digest,
            ),
        )

        completion_event = ControlPlaneEvent.create(
            event_type=READ_COMPLETED_EVENT,
            actor_id=actor_id,
            component="durable_execution_lease",
            action="complete_read_only",
            resource=str(execution_id),
            status="VERIFIED",
            correlation=_caused_by(correlation, runner_event),
            project=self.project,
            payload={
                "invocation": invocation,
                "request_id": request_id,
                "execution_id": execution_id,
                "execution_epoch": execution_epoch,
                "completion_outcome": completion_outcome,
                "completion_digest": completion_digest,
                "lease_id": lease_id,
                "lease_digest": lease_digest,
            },
            evidence_refs=(
                completion_digest,
                lease_digest,
            ),
        )

        verifier_event = ControlPlaneEvent.create(
            event_type=READ_VERIFIER_OBSERVED_EVENT,
            actor_id=actor_id,
            component="canonical_read_terminal",
            action="verifier_observe_read_only",
            resource=str(execution_id),
            status="OBSERVED",
            correlation=_caused_by(correlation, completion_event),
            project=self.project,
            occurred_at=_attribute(verifier_observation, "observed_at"),
            payload={
                "invocation": invocation,
                "request_id": request_id,
                "execution_id": execution_id,
                "execution_epoch": execution_epoch,
                "target_digest": target_digest,
                "runner_observation_digest": runner_observation_digest,
                "verification_boundary_digest": boundary_digest,
                "verifier_id": verifier_id,
                "verifier_identity_digest": verifier_identity_digest,
                "verifier_credential_decision_id": verifier_decision_id,
                "verifier_credential_decision_digest": verifier_decision_digest,
                "verifier_observation_digest": verifier_observation_digest,
            },
            evidence_refs=(
                verifier_observation_digest,
                boundary_digest,
                verifier_identity_digest,
                verifier_decision_digest,
            ),
        )

        verdict = _attribute(verification_result, "verdict")
        result_digest = _attribute(verification_result, "result_digest")
        verification_event = ControlPlaneEvent.create(
            event_type=READ_VERIFIED_EVENT,
            actor_id=actor_id,
            component="canonical_read_terminal",
            action="verify_read_only",
            resource=str(execution_id),
            status="VERIFIED" if verdict == "VERIFIED" else "FAILED",
            correlation=_caused_by(correlation, verifier_event),
            project=self.project,
            occurred_at=_attribute(verification_result, "checked_at"),
            payload={
                "invocation": invocation,
                "request_id": request_id,
                "execution_id": execution_id,
                "execution_epoch": execution_epoch,
                "target_digest": target_digest,
                "verdict": verdict,
                "reason": _attribute(verification_result, "reason"),
                "runner_observation_digest": runner_observation_digest,
                "completion_digest": completion_digest,
                "verifier_observation_digest": verifier_observation_digest,
                "observed_post_state_digest": observed_state_digest,
                "verification_boundary_digest": boundary_digest,
                "verifier_identity_digest": verifier_identity_digest,
                "verifier_credential_decision_digest": verifier_decision_digest,
                "verification_strength_digest": strength_digest,
                "verification_result_digest": result_digest,
            },
            evidence_refs=(
                observed_state_digest,
                strength_digest,
                result_digest,
            ),
        )
        return (
            prepared_event,
            runner_event,
            completion_event,
            verifier_event,
            verification_event,
        )
