from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, NoReturn

from .dispatch_inbox import DispatchInboxAdmission
from .evidence_primitives import canonical_json
from .execution_lease import (
    ExecutionLease,
    assert_next_execution_epoch,
)
from .persistence import (
    DatabaseIntegrityError,
    DatabaseRow,
    DatabaseStatement,
    ProductDatabaseAdapter,
)
from .trusted_clock import ClockWitness, TrustedClockAuthority

MINIMUM_EXECUTION_LEASE_SCHEMA_VERSION: Final = 13
LEASE_ACQUIRED: Final = "LEASE_ACQUIRED"
LEASE_REACQUIRED: Final = "LEASE_REACQUIRED"
COMPLETED: Final = "COMPLETED"
DUPLICATE_COMPLETION: Final = "DUPLICATE_COMPLETION"
ACTIVE: Final = "ACTIVE"

_REQUIRED_LEASE_COLUMNS: Final = {
    "lease_id",
    "admission_id",
    "dispatch_id",
    "admission_digest",
    "execution_id",
    "workspace_id",
    "environment",
    "execution_capsule_digest",
    "runner_class",
    "execution_epoch",
    "acquired_at",
    "expires_at",
    "clock_witness_digest",
    "clock_witness_json",
    "lease_revision",
    "lease_digest",
    "lease_json",
}
_REQUIRED_STATE_COLUMNS: Final = {
    "admission_id",
    "admission_digest",
    "execution_id",
    "workspace_id",
    "environment",
    "execution_capsule_digest",
    "runner_class",
    "current_epoch",
    "current_lease_id",
    "current_lease_digest",
    "current_lease_acquired_at",
    "current_lease_expires_at",
    "status",
    "completion_digest",
    "completed_at",
    "completion_clock_witness_digest",
    "completion_clock_witness_json",
    "authority_revision",
    "updated_at",
}
_REQUIRED_INDEXES: Final = {
    "idx_execution_leases_v1_admission_epoch",
    "idx_execution_leases_v1_execution",
    "idx_execution_epoch_state_v1_execution",
    "idx_execution_epoch_state_v1_status_expiry",
}
_REQUIRED_TRIGGERS: Final = {
    "trg_execution_leases_v1_admission_binding_insert",
    "trg_execution_leases_v1_immutable_update",
    "trg_execution_leases_v1_immutable_delete",
    "trg_execution_epoch_state_v1_insert_guard",
    "trg_execution_epoch_state_v1_update_guard",
    "trg_execution_epoch_state_v1_immutable_delete",
}

SELECT_INBOX_ADMISSION = DatabaseStatement(
    name="execution_epoch.select_inbox_admission",
    mode="read",
    sqlite_sql="""
        SELECT admission_id, dispatch_id, envelope_digest, outbox_id,
               outbox_entry_digest, execution_id, workspace_id, environment,
               execution_capsule_digest, runner_class, admission_revision,
               admission_digest, admission_json
        FROM dispatch_inbox_v1
        WHERE admission_id = ?
    """,
)
SELECT_EPOCH_STATE = DatabaseStatement(
    name="execution_epoch.select_state",
    mode="read",
    sqlite_sql="""
        SELECT admission_id, admission_digest, execution_id, workspace_id,
               environment, execution_capsule_digest, runner_class, current_epoch,
               current_lease_id, current_lease_digest, current_lease_acquired_at,
               current_lease_expires_at, status, completion_digest, completed_at,
               completion_clock_witness_digest, completion_clock_witness_json,
               authority_revision, updated_at
        FROM execution_epoch_state_v1
        WHERE admission_id = ?
    """,
)
SELECT_LEASE = DatabaseStatement(
    name="execution_epoch.select_lease",
    mode="read",
    sqlite_sql="""
        SELECT lease_id, admission_id, dispatch_id, admission_digest, execution_id,
               workspace_id, environment, execution_capsule_digest, runner_class,
               execution_epoch, acquired_at, expires_at, clock_witness_digest,
               clock_witness_json, lease_revision, lease_digest, lease_json
        FROM execution_leases_v1
        WHERE lease_id = ?
    """,
)
INSERT_LEASE = DatabaseStatement(
    name="execution_epoch.insert_lease",
    mode="write",
    sqlite_sql="""
        INSERT INTO execution_leases_v1(
            lease_id, admission_id, dispatch_id, admission_digest, execution_id,
            workspace_id, environment, execution_capsule_digest, runner_class,
            execution_epoch, acquired_at, expires_at, clock_witness_digest,
            clock_witness_json, lease_revision, lease_digest, lease_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
)
INSERT_EPOCH_STATE = DatabaseStatement(
    name="execution_epoch.insert_state",
    mode="write",
    sqlite_sql="""
        INSERT INTO execution_epoch_state_v1(
            admission_id, admission_digest, execution_id, workspace_id, environment,
            execution_capsule_digest, runner_class, current_epoch, current_lease_id,
            current_lease_digest, current_lease_acquired_at, current_lease_expires_at,
            status, completion_digest, completed_at,
            completion_clock_witness_digest, completion_clock_witness_json,
            authority_revision, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', NULL, NULL, NULL, NULL, ?, ?)
    """,
)
REACQUIRE_EPOCH = DatabaseStatement(
    name="execution_epoch.reacquire",
    mode="write",
    sqlite_sql="""
        UPDATE execution_epoch_state_v1
        SET current_epoch = ?, current_lease_id = ?, current_lease_digest = ?,
            current_lease_acquired_at = ?, current_lease_expires_at = ?, updated_at = ?
        WHERE admission_id = ? AND status = 'ACTIVE'
          AND current_epoch = ? AND current_lease_id = ? AND current_lease_digest = ?
        RETURNING admission_id
    """,
)
COMPLETE_EPOCH = DatabaseStatement(
    name="execution_epoch.complete",
    mode="write",
    sqlite_sql="""
        UPDATE execution_epoch_state_v1
        SET status = 'COMPLETED', completion_digest = ?, completed_at = ?,
            completion_clock_witness_digest = ?, completion_clock_witness_json = ?,
            updated_at = ?
        WHERE admission_id = ? AND status = 'ACTIVE'
          AND current_epoch = ? AND current_lease_id = ? AND current_lease_digest = ?
        RETURNING admission_id
    """,
)


class DurableExecutionLeaseDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DurableCompletionConflict(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class DurableExecutionLeaseResult:
    outcome: str
    lease: ExecutionLease

    def __post_init__(self) -> None:
        if self.outcome not in {LEASE_ACQUIRED, LEASE_REACQUIRED}:
            raise ValueError("durable execution lease outcome is unsupported")
        if not isinstance(self.lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")


@dataclass(frozen=True, slots=True)
class DurableExecutionCompletionResult:
    outcome: str
    lease: ExecutionLease
    completion_digest: str

    def __post_init__(self) -> None:
        if self.outcome not in {COMPLETED, DUPLICATE_COMPLETION}:
            raise ValueError("durable completion outcome is unsupported")
        if not isinstance(self.lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")
        _require_digest(self.completion_digest, field="completion_digest")


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


class DurableExecutionLeaseService:
    """Durable C4b epoch allocator, lease history and completion fence.

    Every state transition runs inside the released SQLite BEGIN IMMEDIATE write boundary. The
    service resolves the durable C3 admission itself, constructs trusted time itself, persists every
    epoch lease immutably and atomically advances one current-epoch row. An expired attempt can be
    superseded, but a superseded attempt can never record durable completion.

    This service does not perform provider effects. Phase D must keep effect execution behind an
    equivalent fence boundary or an effect target that understands the epoch token.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        trusted_clock: TrustedClockAuthority,
        lease_seconds: int,
        lease_revision: str,
        authority_revision: str,
    ) -> None:
        if not isinstance(database, ProductDatabaseAdapter):
            raise ValueError("database must implement ProductDatabaseAdapter")
        if database.backend_name != "sqlite" or database.write_serialization != "global":
            raise RuntimeError("C4b requires released SQLite global write serialization")
        if database.schema_version() < MINIMUM_EXECUTION_LEASE_SCHEMA_VERSION:
            raise RuntimeError("C4b requires database schema version 13 or newer")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock must be TrustedClockAuthority")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            raise ValueError("lease_seconds must be an integer")
        if lease_seconds < 1 or lease_seconds > 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        _require_text(lease_revision, field="lease_revision")
        _require_text(authority_revision, field="authority_revision")

        self.db = database
        self.trusted_clock = trusted_clock
        self.lease_seconds = lease_seconds
        self.lease_revision = lease_revision
        self.authority_revision = authority_revision
        self._validate_schema()

    def acquire(self, *, admission_id: str) -> DurableExecutionLeaseResult:
        _require_digest(admission_id, field="admission_id")

        with self.db.transaction() as connection:
            admission_row = connection.execute(
                SELECT_INBOX_ADMISSION,
                (admission_id,),
            ).fetchone()
            if admission_row is None:
                self._deny("ADMISSION_NOT_FOUND")
            admission = self._decode_admission(admission_row)
            clock_witness = self.trusted_clock.witness(environment=admission.environment)

            state = connection.execute(SELECT_EPOCH_STATE, (admission_id,)).fetchone()
            previous_epoch: int | None = None
            previous_lease: ExecutionLease | None = None
            if state is not None:
                self._assert_state_bound(state, admission=admission)
                if str(state["status"]) == "COMPLETED":
                    self._deny("EXECUTION_ALREADY_COMPLETED")
                previous_epoch = int(state["current_epoch"])
                previous_lease = self._load_lease(
                    connection,
                    lease_id=str(state["current_lease_id"]),
                    admission=admission,
                )
                self._assert_state_matches_lease(state, lease=previous_lease)
                if clock_witness.observed_at < previous_lease.expires_at:
                    self._deny("LEASE_STILL_ACTIVE")

            candidate_epoch = 1 if previous_epoch is None else previous_epoch + 1
            assert_next_execution_epoch(
                previous_epoch=previous_epoch,
                candidate_epoch=candidate_epoch,
            )
            lease = ExecutionLease.create_candidate(
                admission=admission,
                execution_epoch=candidate_epoch,
                clock_witness=clock_witness,
                lease_seconds=self.lease_seconds,
                lease_revision=self.lease_revision,
            )
            self._insert_lease(connection, lease=lease, clock_witness=clock_witness)

            if previous_lease is None:
                try:
                    connection.execute(
                        INSERT_EPOCH_STATE,
                        (
                            admission.admission_id,
                            admission.admission_digest,
                            admission.execution_id,
                            admission.workspace_id,
                            admission.environment,
                            admission.execution_capsule_digest,
                            admission.runner_class,
                            lease.execution_epoch,
                            lease.lease_id,
                            lease.lease_digest,
                            lease.acquired_at,
                            lease.expires_at,
                            self.authority_revision,
                            clock_witness.observed_at,
                        ),
                    )
                except DatabaseIntegrityError as exc:
                    self._deny("EPOCH_STATE_PERSISTENCE_CONFLICT", cause=exc)
                outcome = LEASE_ACQUIRED
            else:
                updated = connection.execute(
                    REACQUIRE_EPOCH,
                    (
                        lease.execution_epoch,
                        lease.lease_id,
                        lease.lease_digest,
                        lease.acquired_at,
                        lease.expires_at,
                        clock_witness.observed_at,
                        admission.admission_id,
                        previous_lease.execution_epoch,
                        previous_lease.lease_id,
                        previous_lease.lease_digest,
                    ),
                ).fetchone()
                if updated is None:
                    self._deny("EPOCH_STATE_CHANGED_DURING_REACQUIRE")
                outcome = LEASE_REACQUIRED

        return DurableExecutionLeaseResult(outcome=outcome, lease=lease)

    def complete(
        self,
        *,
        lease_id: str,
        completion_digest: str,
    ) -> DurableExecutionCompletionResult:
        _require_digest(lease_id, field="lease_id")
        completion = _require_digest(completion_digest, field="completion_digest")

        with self.db.transaction() as connection:
            lease_row = connection.execute(SELECT_LEASE, (lease_id,)).fetchone()
            if lease_row is None:
                self._deny("LEASE_NOT_FOUND")
            lease = self._decode_lease(lease_row)

            admission_row = connection.execute(
                SELECT_INBOX_ADMISSION,
                (lease.admission_id,),
            ).fetchone()
            if admission_row is None:
                self._deny("ADMISSION_NOT_FOUND")
            admission = self._decode_admission(admission_row)
            lease.assert_bound_to(admission)

            state = connection.execute(
                SELECT_EPOCH_STATE,
                (lease.admission_id,),
            ).fetchone()
            if state is None:
                self._deny("EPOCH_STATE_NOT_FOUND")
            self._assert_state_bound(state, admission=admission)

            current_epoch = int(state["current_epoch"])
            if current_epoch != lease.execution_epoch:
                clock = self.trusted_clock.witness(environment=lease.environment)
                lease.assert_completion_fence(
                    current_execution_epoch=current_epoch,
                    clock_witness=clock,
                )
                self._deny("CURRENT_LEASE_ID_MISMATCH")

            if str(state["current_lease_id"]) != lease.lease_id:
                self._deny("CURRENT_LEASE_ID_MISMATCH")
            self._assert_state_matches_lease(state, lease=lease)

            if str(state["status"]) == "COMPLETED":
                stored_completion = str(state["completion_digest"])
                if stored_completion != completion:
                    raise DurableCompletionConflict("COMPLETION_DIGEST_CONFLICT")
                return DurableExecutionCompletionResult(
                    outcome=DUPLICATE_COMPLETION,
                    lease=lease,
                    completion_digest=completion,
                )

            clock_witness = self.trusted_clock.witness(environment=lease.environment)
            lease.assert_completion_fence(
                current_execution_epoch=current_epoch,
                clock_witness=clock_witness,
            )
            completed = connection.execute(
                COMPLETE_EPOCH,
                (
                    completion,
                    clock_witness.observed_at,
                    clock_witness.witness_digest,
                    canonical_json(clock_witness.to_dict()),
                    clock_witness.observed_at,
                    lease.admission_id,
                    lease.execution_epoch,
                    lease.lease_id,
                    lease.lease_digest,
                ),
            ).fetchone()
            if completed is None:
                self._deny("EPOCH_STATE_CHANGED_DURING_COMPLETION")

        return DurableExecutionCompletionResult(
            outcome=COMPLETED,
            lease=lease,
            completion_digest=completion,
        )

    def _insert_lease(
        self,
        connection: object,
        *,
        lease: ExecutionLease,
        clock_witness: ClockWitness,
    ) -> None:
        try:
            connection.execute(
                INSERT_LEASE,
                (
                    lease.lease_id,
                    lease.admission_id,
                    lease.dispatch_id,
                    lease.admission_digest,
                    lease.execution_id,
                    lease.workspace_id,
                    lease.environment,
                    lease.execution_capsule_digest,
                    lease.runner_class,
                    lease.execution_epoch,
                    lease.acquired_at,
                    lease.expires_at,
                    lease.clock_witness_digest,
                    canonical_json(clock_witness.to_dict()),
                    lease.lease_revision,
                    lease.lease_digest,
                    canonical_json(lease.to_dict()),
                ),
            )
        except DatabaseIntegrityError as exc:
            self._deny("LEASE_PERSISTENCE_CONFLICT", cause=exc)

    def _load_lease(
        self,
        connection: object,
        *,
        lease_id: str,
        admission: DispatchInboxAdmission,
    ) -> ExecutionLease:
        row = connection.execute(SELECT_LEASE, (lease_id,)).fetchone()
        if row is None:
            self._deny("CURRENT_LEASE_NOT_FOUND")
        lease = self._decode_lease(row)
        lease.assert_bound_to(admission)
        return lease

    def _decode_lease(self, row: DatabaseRow) -> ExecutionLease:
        try:
            raw = json.loads(str(row["lease_json"]))
            lease = ExecutionLease.from_dict(raw)
            clock_raw = json.loads(str(row["clock_witness_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._deny("LEASE_ROW_INVALID", cause=exc)
        if not isinstance(clock_raw, dict) or clock_raw.get("witness_digest") != lease.clock_witness_digest:
            self._deny("LEASE_ROW_INVALID")
        expected = {
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
            "clock_witness_json": canonical_json(clock_raw),
            "lease_revision": lease.lease_revision,
            "lease_digest": lease.lease_digest,
            "lease_json": canonical_json(lease.to_dict()),
        }
        if {key: row[key] for key in expected} != expected:
            self._deny("LEASE_ROW_INVALID")
        return lease

    def _decode_admission(self, row: DatabaseRow) -> DispatchInboxAdmission:
        try:
            raw = json.loads(str(row["admission_json"]))
            admission = DispatchInboxAdmission.from_dict(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._deny("ADMISSION_ROW_INVALID", cause=exc)
        expected = {
            "admission_id": admission.admission_id,
            "dispatch_id": admission.dispatch_id,
            "envelope_digest": admission.envelope_digest,
            "outbox_id": admission.outbox_id,
            "outbox_entry_digest": admission.outbox_entry_digest,
            "execution_id": admission.execution_id,
            "workspace_id": admission.workspace_id,
            "environment": admission.environment,
            "execution_capsule_digest": admission.execution_capsule_digest,
            "runner_class": admission.runner_class,
            "admission_revision": admission.admission_revision,
            "admission_digest": admission.admission_digest,
            "admission_json": canonical_json(admission.to_dict()),
        }
        if {key: row[key] for key in expected} != expected:
            self._deny("ADMISSION_ROW_INVALID")
        return admission

    def _assert_state_bound(
        self,
        state: DatabaseRow,
        *,
        admission: DispatchInboxAdmission,
    ) -> None:
        expected = {
            "admission_id": admission.admission_id,
            "admission_digest": admission.admission_digest,
            "execution_id": admission.execution_id,
            "workspace_id": admission.workspace_id,
            "environment": admission.environment,
            "execution_capsule_digest": admission.execution_capsule_digest,
            "runner_class": admission.runner_class,
            "authority_revision": self.authority_revision,
        }
        if {key: state[key] for key in expected} != expected:
            self._deny("EPOCH_STATE_BINDING_INVALID")
        if str(state["status"]) not in {ACTIVE, COMPLETED}:
            self._deny("EPOCH_STATE_INVALID")

    def _assert_state_matches_lease(
        self,
        state: DatabaseRow,
        *,
        lease: ExecutionLease,
    ) -> None:
        expected = {
            "current_epoch": lease.execution_epoch,
            "current_lease_id": lease.lease_id,
            "current_lease_digest": lease.lease_digest,
            "current_lease_acquired_at": lease.acquired_at,
            "current_lease_expires_at": lease.expires_at,
        }
        if {key: state[key] for key in expected} != expected:
            self._deny("EPOCH_STATE_LEASE_BINDING_INVALID")

    def _validate_schema(self) -> None:
        with self.db.connect() as connection:
            lease_columns = {
                str(row["name"])
                for row in connection.execute('PRAGMA table_info("execution_leases_v1")').fetchall()
            }
            state_columns = {
                str(row["name"])
                for row in connection.execute('PRAGMA table_info("execution_epoch_state_v1")').fetchall()
            }
            if lease_columns != _REQUIRED_LEASE_COLUMNS:
                raise RuntimeError("C4b schema validation failed for execution_leases_v1")
            if state_columns != _REQUIRED_STATE_COLUMNS:
                raise RuntimeError("C4b schema validation failed for execution_epoch_state_v1")
            indexes = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }
            if _REQUIRED_INDEXES - indexes:
                raise RuntimeError("C4b schema validation failed: required indexes missing")
            triggers = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                ).fetchall()
            }
            if _REQUIRED_TRIGGERS - triggers:
                raise RuntimeError("C4b schema validation failed: required triggers missing")

    @staticmethod
    def _deny(
        reason: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        error = DurableExecutionLeaseDenied(reason)
        if cause is None:
            raise error
        raise error from cause
