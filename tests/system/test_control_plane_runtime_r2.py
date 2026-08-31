from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from voodoo_product.control_plane_contracts import CorrelationContext, ProjectDescriptor
from voodoo_product.control_plane_foundation import ControlPlaneEventLog
from voodoo_product.control_plane_runtime import (
    READ_RESUMED_EVENT,
    ControlPlaneReadRuntime,
)


class _Database:
    backend_name = "sqlite"
    write_serialization = "test"

    def initialize(self) -> None:
        return None

    def connect(self):
        raise AssertionError("connect is not used by this test")

    @contextmanager
    def transaction(self):
        yield SimpleNamespace()

    def schema_version(self) -> int:
        return 1


class _AuditLedger:
    def __init__(self, db: _Database) -> None:
        self.db = db
        self.events: list[dict[str, object]] = []

    def append(
        self,
        connection,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        del connection
        event_hash = f"{len(self.events) + 1:064x}"
        self.events.append(
            {
                "actor_id": actor_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "payload": payload,
                "event_hash": event_hash,
            }
        )
        return {"event_hash": event_hash}


class _Runtime:
    def __init__(self, terminal_result: object) -> None:
        self.terminal_result = terminal_result
        self.correlation_ids: list[str] = []
        self.resumed_execution_ids: list[str] = []

    def run_read_only(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> object:
        assert actor_id == "actor-1"
        assert request_id == "request-1"
        assert idempotency_key == "idem-1"
        self.correlation_ids.append(correlation_id)
        return self.terminal_result

    def run_resumed_read_only(
        self,
        *,
        actor_id: str,
        execution_id: str,
    ) -> object:
        assert actor_id == "actor-1"
        self.resumed_execution_ids.append(execution_id)
        return self.terminal_result


def _digest(character: str) -> str:
    return character * 64


def _terminal_result(
    *,
    verification_execution_id: str = "exec-1",
    completion_digest: str | None = None,
) -> object:
    snapshot_digest = _digest("1")
    grant_digest = _digest("2")
    outbox_digest = _digest("3")
    envelope_digest = _digest("4")
    admission_digest = _digest("5")
    lease_digest = _digest("6")
    target_digest = _digest("7")
    lease_id = _digest("8")
    runner_observation_digest = _digest("9")
    capsule_digest = _digest("a")
    verifier_id = _digest("b")
    verifier_identity_digest = _digest("c")
    boundary_digest = _digest("d")
    verifier_decision_id = _digest("e")
    verifier_decision_digest = _digest("f")
    verifier_observation_digest = _digest("0")
    observed_state_digest = _digest("a")
    strength_digest = _digest("b")
    result_digest = _digest("c")

    snapshot = SimpleNamespace(
        request_id="request-1",
        actor_id="actor-1",
        execution_id="exec-1",
        snapshot_digest=snapshot_digest,
    )
    grant = SimpleNamespace(execution_id="exec-1", grant_digest=grant_digest)
    outbox = SimpleNamespace(execution_id="exec-1", entry_digest=outbox_digest)
    envelope = SimpleNamespace(execution_id="exec-1", envelope_digest=envelope_digest)
    admission = SimpleNamespace(
        execution_id="exec-1",
        admission_digest=admission_digest,
    )
    lease = SimpleNamespace(
        execution_id="exec-1",
        lease_id=lease_id,
        lease_digest=lease_digest,
        execution_epoch=3,
    )
    prepared = SimpleNamespace(
        request_id="request-1",
        execution_id="exec-1",
        execution_epoch=3,
        target_digest=target_digest,
        authorization_snapshot_digest=snapshot_digest,
        grant_digest=grant_digest,
        outbox_entry_digest=outbox_digest,
        envelope_digest=envelope_digest,
        admission_digest=admission_digest,
        lease_id=lease_id,
        lease_digest=lease_digest,
        execution_capsule_digest=capsule_digest,
        capability="github.read-ref/v1",
        snapshot=snapshot,
        grant=grant,
        outbox=outbox,
        envelope=envelope,
        admission=admission,
        lease=lease,
    )
    runner_observation = SimpleNamespace(
        execution_id="exec-1",
        execution_epoch=3,
        target_digest=target_digest,
        lease_digest=lease_digest,
        observation_digest=runner_observation_digest,
        observed_at="2026-08-31T05:29:58+00:00",
    )
    durable_completion = SimpleNamespace(
        outcome="COMPLETED",
        lease=lease,
        completion_digest=completion_digest or runner_observation_digest,
    )
    verifier_identity = SimpleNamespace(
        verifier_id=verifier_id,
        identity_digest=verifier_identity_digest,
    )
    verification_boundary = SimpleNamespace(
        execution_id="exec-1",
        execution_epoch=3,
        target_digest=target_digest,
        runner_observation_digest=runner_observation_digest,
        boundary_digest=boundary_digest,
    )
    verifier_credential_decision = SimpleNamespace(
        decision_id=verifier_decision_id,
        decision_digest=verifier_decision_digest,
        execution_id="exec-1",
        execution_epoch=3,
        target_digest=target_digest,
        runner_observation_digest=runner_observation_digest,
        verification_boundary_digest=boundary_digest,
        verifier_id=verifier_id,
        verifier_identity_digest=verifier_identity_digest,
    )
    verifier_observation = SimpleNamespace(
        observation_digest=verifier_observation_digest,
        observed_at="2026-08-31T05:29:59+00:00",
        execution_id="exec-1",
        execution_epoch=3,
        target_digest=target_digest,
        runner_observation_digest=runner_observation_digest,
        verification_boundary_digest=boundary_digest,
        verifier_id=verifier_id,
        verifier_identity_digest=verifier_identity_digest,
        verifier_credential_decision_id=verifier_decision_id,
        verifier_credential_decision_digest=verifier_decision_digest,
    )
    observed_post_state = SimpleNamespace(state_digest=observed_state_digest)
    verification_strength = SimpleNamespace(strength_digest=strength_digest)
    verification_result = SimpleNamespace(
        execution_id=verification_execution_id,
        execution_epoch=3,
        target_digest=target_digest,
        runner_observation_digest=runner_observation_digest,
        verifier_observation_digest=verifier_observation_digest,
        observed_post_state_digest=observed_state_digest,
        verification_boundary_digest=boundary_digest,
        verifier_id=verifier_id,
        verifier_identity_digest=verifier_identity_digest,
        verification_strength_digest=strength_digest,
        verdict="VERIFIED",
        reason="OBSERVED_STATE_MATCH",
        checked_at="2026-08-31T05:30:00+00:00",
        result_digest=result_digest,
    )
    return SimpleNamespace(
        prepared=prepared,
        runner_observation=runner_observation,
        durable_completion=durable_completion,
        verifier_identity=verifier_identity,
        verification_boundary=verification_boundary,
        verifier_credential_decision=verifier_credential_decision,
        verifier_observation=verifier_observation,
        observed_post_state=observed_post_state,
        verification_strength=verification_strength,
        verification_result=verification_result,
    )


def _wrapper(terminal_result: object):
    database = _Database()
    ledger = _AuditLedger(database)
    runtime = _Runtime(terminal_result)
    wrapper = ControlPlaneReadRuntime(
        runtime=runtime,
        database=database,
        event_log=ControlPlaneEventLog(ledger),
        project=ProjectDescriptor(
            project_id="v-one",
            canonical_repository="eimyroot/V-One",
        ),
    )
    return wrapper, runtime, ledger


def _correlation(*, run_id: str = "run_r2", correlation_id: str = "corr_r2"):
    return CorrelationContext(run_id=run_id, correlation_id=correlation_id)


def test_read_runtime_propagates_correlation_and_records_full_causal_chain() -> None:
    wrapper, runtime, ledger = _wrapper(_terminal_result())

    result = wrapper.run_read_only(
        actor_id="actor-1",
        request_id="request-1",
        idempotency_key="idem-1",
        correlation=_correlation(),
    )

    assert runtime.correlation_ids == ["corr_r2"]
    events = (
        result.prepared_event,
        result.runner_observation_event,
        result.completion_event,
        result.verifier_observation_event,
        result.verification_event,
    )
    assert events[0].correlation == _correlation()
    for previous, current in zip(events[:-1], events[1:], strict=True):
        assert current.correlation.run_id == "run_r2"
        assert current.correlation.correlation_id == "corr_r2"
        assert current.correlation.causation_event_id == previous.event_id
    assert result.runner_observation_event.status == "OBSERVED"
    assert result.completion_event.status == "VERIFIED"
    assert result.verifier_observation_event.status == "OBSERVED"
    assert result.verification_event.status == "VERIFIED"
    assert result.completion_event.payload()["completion_digest"] == _digest("9")
    assert len(ledger.events) == 5
    assert result.audit_event_hashes == tuple(f"{index:064x}" for index in range(1, 6))


def test_read_runtime_rejects_tampered_verification_before_audit() -> None:
    wrapper, _, ledger = _wrapper(
        _terminal_result(verification_execution_id="exec-tampered")
    )

    with pytest.raises(
        PermissionError,
        match="CONTROL_PLANE_RUNTIME_VERIFICATION_EXECUTION_ID_MISMATCH",
    ):
        wrapper.run_read_only(
            actor_id="actor-1",
            request_id="request-1",
            idempotency_key="idem-1",
            correlation=_correlation(),
        )

    assert ledger.events == []


def test_read_runtime_rejects_tampered_completion_before_audit() -> None:
    wrapper, _, ledger = _wrapper(
        _terminal_result(completion_digest=_digest("f"))
    )

    with pytest.raises(
        PermissionError,
        match="CONTROL_PLANE_RUNTIME_COMPLETION_DIGEST_MISMATCH",
    ):
        wrapper.run_read_only(
            actor_id="actor-1",
            request_id="request-1",
            idempotency_key="idem-1",
            correlation=_correlation(),
        )

    assert ledger.events == []


def test_resumed_read_runtime_uses_new_control_plane_context_and_durable_lineage() -> None:
    wrapper, runtime, ledger = _wrapper(_terminal_result())

    result = wrapper.run_resumed_read_only(
        actor_id="actor-1",
        execution_id="exec-1",
        correlation=_correlation(
            run_id="run_resume",
            correlation_id="corr_resume",
        ),
    )

    assert runtime.resumed_execution_ids == ["exec-1"]
    assert result.prepared_event.event_type == READ_RESUMED_EVENT
    assert result.prepared_event.payload()["invocation"] == "resume"
    assert result.prepared_event.payload()["execution_id"] == "exec-1"
    assert result.prepared_event.correlation.run_id == "run_resume"
    assert result.prepared_event.correlation.correlation_id == "corr_resume"
    assert (
        result.runner_observation_event.correlation.causation_event_id
        == result.prepared_event.event_id
    )
    assert len(ledger.events) == 5


def test_control_plane_identity_does_not_mutate_authority_digests() -> None:
    terminal_result = _terminal_result()
    prepared = terminal_result.prepared
    before = (
        prepared.authorization_snapshot_digest,
        prepared.grant_digest,
        prepared.outbox_entry_digest,
        prepared.envelope_digest,
        prepared.admission_digest,
        prepared.lease_digest,
    )
    wrapper, _, _ = _wrapper(terminal_result)

    wrapper.run_read_only(
        actor_id="actor-1",
        request_id="request-1",
        idempotency_key="idem-1",
        correlation=_correlation(),
    )

    after = (
        prepared.authorization_snapshot_digest,
        prepared.grant_digest,
        prepared.outbox_entry_digest,
        prepared.envelope_digest,
        prepared.admission_digest,
        prepared.lease_digest,
    )
    assert after == before


def test_event_log_database_must_match_runtime_recording_database() -> None:
    database = _Database()
    other_database = _Database()
    ledger = _AuditLedger(other_database)

    with pytest.raises(ValueError, match="must share the supplied database"):
        ControlPlaneReadRuntime(
            runtime=_Runtime(_terminal_result()),
            database=database,
            event_log=ControlPlaneEventLog(ledger),
            project=ProjectDescriptor(
                project_id="v-one",
                canonical_repository="eimyroot/V-One",
            ),
        )
