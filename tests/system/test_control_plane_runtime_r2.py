from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from voodoo_product.control_plane_contracts import CorrelationContext, ProjectDescriptor
from voodoo_product.control_plane_foundation import ControlPlaneEventLog
from voodoo_product.control_plane_runtime import ControlPlaneReadRuntime


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


def _digest(character: str) -> str:
    return character * 64


def _terminal_result(*, verification_execution_id: str = "exec-1") -> object:
    snapshot = SimpleNamespace(
        request_id="request-1",
        actor_id="actor-1",
        execution_id="exec-1",
        snapshot_digest=_digest("1"),
    )
    grant = SimpleNamespace(execution_id="exec-1", grant_digest=_digest("2"))
    outbox = SimpleNamespace(execution_id="exec-1", entry_digest=_digest("3"))
    envelope = SimpleNamespace(execution_id="exec-1", envelope_digest=_digest("4"))
    admission = SimpleNamespace(execution_id="exec-1", admission_digest=_digest("5"))
    lease = SimpleNamespace(
        execution_id="exec-1",
        lease_digest=_digest("6"),
        execution_epoch=3,
    )
    prepared = SimpleNamespace(
        request_id="request-1",
        execution_id="exec-1",
        execution_epoch=3,
        target_digest=_digest("7"),
        authorization_snapshot_digest=_digest("1"),
        grant_digest=_digest("2"),
        outbox_entry_digest=_digest("3"),
        envelope_digest=_digest("4"),
        admission_digest=_digest("5"),
        lease_digest=_digest("6"),
        execution_capsule_digest=_digest("8"),
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
        target_digest=_digest("7"),
        lease_digest=_digest("6"),
        observation_digest=_digest("9"),
    )
    verifier_identity = SimpleNamespace(
        verifier_id=_digest("a"),
        identity_digest=_digest("b"),
    )
    verification_boundary = SimpleNamespace(boundary_digest=_digest("c"))
    verifier_observation = SimpleNamespace(observation_digest=_digest("d"))
    observed_post_state = SimpleNamespace(state_digest=_digest("e"))
    verification_strength = SimpleNamespace(strength_digest=_digest("f"))
    verification_result = SimpleNamespace(
        execution_id=verification_execution_id,
        execution_epoch=3,
        target_digest=_digest("7"),
        runner_observation_digest=_digest("9"),
        verifier_observation_digest=_digest("d"),
        observed_post_state_digest=_digest("e"),
        verification_boundary_digest=_digest("c"),
        verifier_id=_digest("a"),
        verifier_identity_digest=_digest("b"),
        verification_strength_digest=_digest("f"),
        verdict="VERIFIED",
        reason="OBSERVED_STATE_MATCH",
        checked_at="2026-08-31T05:30:00+00:00",
        result_digest=_digest("0"),
    )
    return SimpleNamespace(
        prepared=prepared,
        runner_observation=runner_observation,
        verifier_identity=verifier_identity,
        verification_boundary=verification_boundary,
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


def test_read_runtime_propagates_correlation_and_records_causal_events() -> None:
    wrapper, runtime, ledger = _wrapper(_terminal_result())
    correlation = CorrelationContext(
        run_id="run_r2",
        correlation_id="corr_r2",
    )

    result = wrapper.run_read_only(
        actor_id="actor-1",
        request_id="request-1",
        idempotency_key="idem-1",
        correlation=correlation,
    )

    assert runtime.correlation_ids == ["corr_r2"]
    assert result.prepared_event.correlation == correlation
    assert result.verification_event.correlation.run_id == "run_r2"
    assert result.verification_event.correlation.correlation_id == "corr_r2"
    assert (
        result.verification_event.correlation.causation_event_id
        == result.prepared_event.event_id
    )
    assert result.verification_event.status == "VERIFIED"
    assert len(ledger.events) == 2
    assert result.audit_event_hashes == (f"{1:064x}", f"{2:064x}")


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
            correlation=CorrelationContext(
                run_id="run_r2",
                correlation_id="corr_r2",
            ),
        )

    assert ledger.events == []


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
        correlation=CorrelationContext(
            run_id="run_r2",
            correlation_id="corr_r2",
        ),
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
