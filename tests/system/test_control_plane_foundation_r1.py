from __future__ import annotations

from typing import Any

import pytest

from voodoo_product.control_plane_contracts import (
    GENESIS_STATE_HASH,
    ControlPlaneEvent,
    CorrelationContext,
    ImmutableProjectRegistry,
    ProjectDescriptor,
    SharedStatePointer,
    StateTransition,
)
from voodoo_product.control_plane_foundation import (
    ControlPlaneEventLog,
    ControlPlaneReconciler,
)

PROJECT = ProjectDescriptor(
    project_id="voodoo-one",
    canonical_repository="eimyroot/V-One",
    canonical_ref="refs/heads/main",
    aliases=("v-one",),
)
CORRELATION = CorrelationContext(
    run_id="run_0123456789abcdef",
    correlation_id="corr_fedcba9876543210",
)


def _event(
    *,
    transition: StateTransition | None = None,
    project: ProjectDescriptor = PROJECT,
) -> ControlPlaneEvent:
    return ControlPlaneEvent.create(
        event_id="evt_0011223344556677",
        occurred_at="2026-08-31T00:00:00.000+00:00",
        event_type="project.state.reconciled",
        actor_id="service/control-plane",
        component="control-plane",
        action="reconcile",
        resource="project/voodoo-one",
        status="VERIFIED",
        correlation=CORRELATION,
        project=project,
        payload={"source": "github", "verified": True},
        evidence_refs=("evidence/github/main@22d814d8",),
        decision_refs=("decision/control-plane-r1",),
        state_transition=transition,
    )


def test_correlation_context_generates_distinct_prefixed_identities() -> None:
    context = CorrelationContext.create()

    assert context.run_id.startswith("run_")
    assert context.correlation_id.startswith("corr_")
    assert context.run_id != context.correlation_id


def test_project_registry_resolves_alias_and_repository() -> None:
    registry = ImmutableProjectRegistry((PROJECT,))

    assert registry.resolve("v-one") is PROJECT
    assert registry.resolve_repository("eimyroot/V-One") is PROJECT
    assert registry.resolve_repository("EIMYROOT/v-one") is PROJECT


def test_project_registry_rejects_alias_collision() -> None:
    other = ProjectDescriptor(
        project_id="other",
        canonical_repository="eimyroot/Other",
        aliases=("v-one",),
    )

    with pytest.raises(ValueError, match="duplicate project identity"):
        ImmutableProjectRegistry((PROJECT, other))


def test_state_transition_recomputes_digest_and_rejects_tampering() -> None:
    valid = StateTransition.create(
        previous_state_hash=GENESIS_STATE_HASH,
        next_state={"canonical_head": "22d814d8", "status": "VERIFIED"},
    )

    assert valid.previous_state_hash == GENESIS_STATE_HASH
    assert len(valid.next_state_hash) == 64

    with pytest.raises(ValueError, match="does not match"):
        StateTransition(
            previous_state_hash=GENESIS_STATE_HASH,
            next_state_json=valid.next_state_json,
            next_state_hash="0" * 64,
        )


def test_event_envelope_carries_global_lineage_and_project_identity() -> None:
    transition = StateTransition.create(
        previous_state_hash=GENESIS_STATE_HASH,
        next_state={"canonical_head": "22d814d8", "status": "VERIFIED"},
    )

    payload = _event(transition=transition).as_dict()

    assert payload["correlation"]["run_id"] == CORRELATION.run_id
    assert payload["correlation"]["correlation_id"] == CORRELATION.correlation_id
    assert payload["project"]["canonical_repository"] == "eimyroot/V-One"
    assert payload["state_transition"]["next_state_hash"] == transition.next_state_hash


class RecordingAuditLedger:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def append(self, connection: object, **kwargs: Any) -> dict[str, Any]:
        call = {"connection": connection, **kwargs}
        self.calls.append(call)
        return {"id": "aud_0000000000000001", **kwargs}


def test_event_log_reuses_canonical_audit_ledger_surface() -> None:
    ledger = RecordingAuditLedger()
    event_log = ControlPlaneEventLog(ledger)
    connection = object()
    event = _event()

    result = event_log.append(connection, event=event)

    assert result["id"] == "aud_0000000000000001"
    assert ledger.calls == [
        {
            "connection": connection,
            "actor_id": "service/control-plane",
            "action": "control_plane.event:project.state.reconciled",
            "target_type": "control_plane_project",
            "target_id": "voodoo-one",
            "payload": event.as_dict(),
        }
    ]


def test_reconciler_projects_exact_full_state_transition() -> None:
    current = SharedStatePointer.genesis("voodoo-one")
    transition = StateTransition.create(
        previous_state_hash=current.state_hash,
        next_state={"canonical_head": "22d814d8", "status": "VERIFIED"},
    )
    event = _event(transition=transition)

    updated = ControlPlaneReconciler.apply(current, event=event)

    assert updated.revision == 1
    assert updated.state_hash == transition.next_state_hash
    assert updated.state() == {"canonical_head": "22d814d8", "status": "VERIFIED"}
    assert updated.last_event_id == event.event_id
    assert updated.last_correlation_id == CORRELATION.correlation_id


def test_reconciler_rejects_stale_state_transition() -> None:
    current = SharedStatePointer.genesis("voodoo-one")
    wrong_previous_hash = "1" * 64
    transition = StateTransition.create(
        previous_state_hash=wrong_previous_hash,
        next_state={"status": "VERIFIED"},
    )

    with pytest.raises(ValueError, match="does not extend"):
        ControlPlaneReconciler.apply(current, event=_event(transition=transition))


def test_reconciler_rejects_cross_project_event() -> None:
    other_project = ProjectDescriptor(
        project_id="other",
        canonical_repository="eimyroot/Other",
    )

    with pytest.raises(ValueError, match="does not match"):
        ControlPlaneReconciler.apply(
            SharedStatePointer.genesis("voodoo-one"),
            event=_event(project=other_project),
        )


def test_non_state_event_does_not_mutate_shared_state() -> None:
    current = SharedStatePointer.genesis("voodoo-one")

    assert ControlPlaneReconciler.apply(current, event=_event()) is current
