from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .control_plane_contracts import ControlPlaneEvent, CorrelationContext, ProjectDescriptor
from .control_plane_foundation import ControlPlaneEventLog
from .persistence import ProductDatabaseAdapter

READ_PREPARED_EVENT = "runtime.read.prepared"
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


def _audit_hash(value: dict[str, Any]) -> str:
    event_hash = value.get("event_hash")
    if not isinstance(event_hash, str) or len(event_hash) != 64:
        raise RuntimeError("control-plane audit append returned an invalid event hash")
    return event_hash


@dataclass(frozen=True, slots=True)
class ControlPlaneReadRuntimeResult:
    """READ terminal result plus normalized control-plane and audit lineage."""

    terminal_result: object = field(repr=False, compare=False)
    prepared_event: ControlPlaneEvent
    verification_event: ControlPlaneEvent
    audit_event_hashes: tuple[str, str]


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
        prepared_event, verification_event = self._bind_read_result(
            terminal_result,
            actor_id=actor_id,
            request_id=request_id,
            correlation=correlation,
        )

        with self.database.transaction() as connection:
            prepared_audit = self.event_log.append(connection, event=prepared_event)
            verification_audit = self.event_log.append(connection, event=verification_event)

        return ControlPlaneReadRuntimeResult(
            terminal_result=terminal_result,
            prepared_event=prepared_event,
            verification_event=verification_event,
            audit_event_hashes=(
                _audit_hash(prepared_audit),
                _audit_hash(verification_audit),
            ),
        )

    def _bind_read_result(
        self,
        terminal_result: object,
        *,
        actor_id: str,
        request_id: str,
        correlation: CorrelationContext,
    ) -> tuple[ControlPlaneEvent, ControlPlaneEvent]:
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
            ("lease_digest", lease_digest, _attribute(lease, "lease_digest")),
            ("lease_epoch", execution_epoch, _attribute(lease, "execution_epoch")),
        ):
            _require_equal(field=field_name, expected=expected, actual=actual)

        runner_observation = _attribute(terminal_result, "runner_observation")
        verification_boundary = _attribute(terminal_result, "verification_boundary")
        verifier_identity = _attribute(terminal_result, "verifier_identity")
        verifier_observation = _attribute(terminal_result, "verifier_observation")
        observed_post_state = _attribute(terminal_result, "observed_post_state")
        verification_strength = _attribute(terminal_result, "verification_strength")
        verification_result = _attribute(terminal_result, "verification_result")

        runner_observation_digest = _attribute(runner_observation, "observation_digest")
        verifier_observation_digest = _attribute(verifier_observation, "observation_digest")
        boundary_digest = _attribute(verification_boundary, "boundary_digest")
        verifier_id = _attribute(verifier_identity, "verifier_id")
        verifier_identity_digest = _attribute(verifier_identity, "identity_digest")
        observed_state_digest = _attribute(observed_post_state, "state_digest")
        strength_digest = _attribute(verification_strength, "strength_digest")

        for field_name, expected, actual in (
            ("runner_execution_id", execution_id, _attribute(runner_observation, "execution_id")),
            (
                "runner_execution_epoch",
                execution_epoch,
                _attribute(runner_observation, "execution_epoch"),
            ),
            ("runner_target_digest", target_digest, _attribute(runner_observation, "target_digest")),
            ("runner_lease_digest", lease_digest, _attribute(runner_observation, "lease_digest")),
            ("verification_execution_id", execution_id, _attribute(verification_result, "execution_id")),
            (
                "verification_execution_epoch",
                execution_epoch,
                _attribute(verification_result, "execution_epoch"),
            ),
            ("verification_target_digest", target_digest, _attribute(verification_result, "target_digest")),
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
            ("verification_verifier_id", verifier_id, _attribute(verification_result, "verifier_id")),
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
            event_type=READ_PREPARED_EVENT,
            actor_id=actor_id,
            component="canonical_operation_runtime",
            action="prepare_read_only",
            resource=str(execution_id),
            status="VERIFIED",
            correlation=correlation,
            project=self.project,
            payload={
                "request_id": request_id,
                "execution_id": execution_id,
                "execution_epoch": execution_epoch,
                "capability": _attribute(prepared, "capability"),
                "authorization_snapshot_digest": snapshot_digest,
                "grant_digest": grant_digest,
                "outbox_entry_digest": outbox_digest,
                "envelope_digest": envelope_digest,
                "admission_digest": admission_digest,
                "lease_digest": lease_digest,
                "execution_capsule_digest": _attribute(prepared, "execution_capsule_digest"),
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

        verification_correlation = CorrelationContext(
            run_id=correlation.run_id,
            correlation_id=correlation.correlation_id,
            causation_event_id=prepared_event.event_id,
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
            correlation=verification_correlation,
            project=self.project,
            occurred_at=_attribute(verification_result, "checked_at"),
            payload={
                "request_id": request_id,
                "execution_id": execution_id,
                "execution_epoch": execution_epoch,
                "target_digest": target_digest,
                "verdict": verdict,
                "reason": _attribute(verification_result, "reason"),
                "runner_observation_digest": runner_observation_digest,
                "verifier_observation_digest": verifier_observation_digest,
                "observed_post_state_digest": observed_state_digest,
                "verification_boundary_digest": boundary_digest,
                "verifier_identity_digest": verifier_identity_digest,
                "verification_strength_digest": strength_digest,
                "verification_result_digest": result_digest,
            },
            evidence_refs=(
                runner_observation_digest,
                verifier_observation_digest,
                observed_state_digest,
                boundary_digest,
                verifier_identity_digest,
                strength_digest,
                result_digest,
            ),
        )
        return prepared_event, verification_event
