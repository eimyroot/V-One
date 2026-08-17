from __future__ import annotations

import json
from typing import NoReturn

from .evidence_primitives import canonical_json
from .execution_lease import ExecutionLease
from .persistence import ProductDatabaseAdapter
from .trusted_clock import TrustedClockAuthority

MINIMUM_DURABLE_CURRENT_FENCE_SCHEMA_VERSION = 13


class DurableCurrentExecutionFenceDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DurableCurrentExecutionFence:
    """Read-only D4 fence over the durable C4 current-epoch projection.

    The fence never allocates an epoch and never mutates durable state. It resolves the
    exact persisted current lease, validates its canonical row representation, obtains a
    fresh trusted clock witness and delegates expiry/stale semantics to ExecutionLease.

    This closes the missing public D3 CurrentExecutionFence composition seam for SQLite.
    It intentionally does not claim provider-side atomic fencing; Phase D performs only
    READ effects. A later provider mutation still requires an effect-boundary primitive
    such as ETag/head-SHA/CAS or another provider-native fencing token.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        trusted_clock: TrustedClockAuthority,
    ) -> None:
        if not isinstance(database, ProductDatabaseAdapter):
            raise ValueError("database must implement ProductDatabaseAdapter")
        if database.backend_name != "sqlite" or database.write_serialization != "global":
            raise RuntimeError("durable current fence requires SQLite global serialization")
        if database.schema_version() < MINIMUM_DURABLE_CURRENT_FENCE_SCHEMA_VERSION:
            raise RuntimeError("durable current fence requires database schema version 13 or newer")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock must be TrustedClockAuthority")
        self.db = database
        self.trusted_clock = trusted_clock

    def assert_current(self, *, lease: ExecutionLease) -> None:
        if not isinstance(lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")

        with self.db.connect() as connection:
            state = connection.execute(
                """
                SELECT admission_id, admission_digest, execution_id, workspace_id,
                       environment, execution_capsule_digest, runner_class,
                       current_epoch, current_lease_id, current_lease_digest,
                       current_lease_acquired_at, current_lease_expires_at, status
                FROM execution_epoch_state_v1
                WHERE admission_id = ?
                """,
                (lease.admission_id,),
            ).fetchone()
            if state is None:
                self._deny("EPOCH_STATE_NOT_FOUND")
            if str(state["status"]) != "ACTIVE":
                self._deny("EXECUTION_NOT_ACTIVE")

            expected_state = {
                "admission_id": lease.admission_id,
                "admission_digest": lease.admission_digest,
                "execution_id": lease.execution_id,
                "workspace_id": lease.workspace_id,
                "environment": lease.environment,
                "execution_capsule_digest": lease.execution_capsule_digest,
                "runner_class": lease.runner_class,
                "current_epoch": lease.execution_epoch,
                "current_lease_id": lease.lease_id,
                "current_lease_digest": lease.lease_digest,
                "current_lease_acquired_at": lease.acquired_at,
                "current_lease_expires_at": lease.expires_at,
            }
            if {key: state[key] for key in expected_state} != expected_state:
                self._deny("CURRENT_EXECUTION_LEASE_MISMATCH")

            lease_row = connection.execute(
                """
                SELECT lease_id, admission_id, dispatch_id, admission_digest,
                       execution_id, workspace_id, environment,
                       execution_capsule_digest, runner_class, execution_epoch,
                       acquired_at, expires_at, clock_witness_digest,
                       lease_revision, lease_digest, lease_json
                FROM execution_leases_v1
                WHERE lease_id = ?
                """,
                (lease.lease_id,),
            ).fetchone()
            if lease_row is None:
                self._deny("CURRENT_LEASE_NOT_FOUND")
            try:
                persisted = ExecutionLease.from_dict(json.loads(str(lease_row["lease_json"])))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                self._deny("CURRENT_LEASE_ROW_INVALID", cause=exc)
            if persisted != lease:
                self._deny("CURRENT_LEASE_ROW_INVALID")

            expected_row = {
                "lease_id": lease.lease_id,
                "admission_id": lease.admission_id,
                "dispatch_id": lease.dispatch_id,
                "admission_digest": lease.admission_digest,
                "execution_id": lease.execution_id,
                "workspace_id": lease.workspace_id,
                "environment": lease.environment,
                "execution_capsule_digest": lease.execution_capsule_digest,
                "runner_class": lease.runner_class,
                "execution_epoch": lease.execution_epoch,
                "acquired_at": lease.acquired_at,
                "expires_at": lease.expires_at,
                "clock_witness_digest": lease.clock_witness_digest,
                "lease_revision": lease.lease_revision,
                "lease_digest": lease.lease_digest,
                "lease_json": canonical_json(lease.to_dict()),
            }
            if {key: lease_row[key] for key in expected_row} != expected_row:
                self._deny("CURRENT_LEASE_ROW_INVALID")

        clock_witness = self.trusted_clock.witness(environment=lease.environment)
        lease.assert_completion_fence(
            current_execution_epoch=lease.execution_epoch,
            clock_witness=clock_witness,
        )

    @staticmethod
    def _deny(
        reason: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        error = DurableCurrentExecutionFenceDenied(reason)
        if cause is None:
            raise error
        raise error from cause
