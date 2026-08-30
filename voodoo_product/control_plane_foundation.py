from __future__ import annotations

from typing import Any

from .audit import AuditLedgerWriter
from .control_plane_contracts import ControlPlaneEvent, SharedStatePointer
from .persistence import DatabaseConnection


class ControlPlaneEventLog:
    """Normalized event surface backed by the existing canonical product audit ledger."""

    def __init__(self, audit_ledger: AuditLedgerWriter) -> None:
        self.audit_ledger = audit_ledger

    def append(
        self,
        connection: DatabaseConnection,
        *,
        event: ControlPlaneEvent,
    ) -> dict[str, Any]:
        return self.audit_ledger.append(
            connection,
            actor_id=event.actor_id,
            action=f"control_plane.event:{event.event_type}",
            target_type="control_plane_project",
            target_id=event.project.project_id,
            payload=event.as_dict(),
        )


class ControlPlaneReconciler:
    """Deterministically projects full-state transitions from control-plane events."""

    @staticmethod
    def apply(
        current: SharedStatePointer,
        *,
        event: ControlPlaneEvent,
    ) -> SharedStatePointer:
        if event.project.project_id != current.project_id:
            raise ValueError("event project does not match current shared-state project")

        transition = event.state_transition
        if transition is None:
            return current

        if transition.previous_state_hash != current.state_hash:
            raise ValueError("state transition does not extend the current state hash")

        return SharedStatePointer(
            project_id=current.project_id,
            revision=current.revision + 1,
            state_hash=transition.next_state_hash,
            state_json=transition.next_state_json,
            last_event_id=event.event_id,
            last_correlation_id=event.correlation.correlation_id,
            updated_at=event.occurred_at,
        )
