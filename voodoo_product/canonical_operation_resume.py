from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, NoReturn

from .authoritative_grant import ExecutionGrantV2
from .authorization_snapshot_store import AuthorizationSnapshotStore
from .canonical_pipeline import CanonicalPreparedExecution
from .dispatch_envelope import DispatchEnvelope
from .dispatch_inbox import DispatchInboxAdmission
from .dispatch_outbox import DispatchOutboxEntry
from .durable_current_fence import DurableCurrentExecutionFence
from .evidence_primitives import canonical_json
from .execution_conformance import ExecutionConformanceWitness
from .execution_contract import REQUIRED_EXECUTION_PERMISSION
from .execution_lease import ExecutionLease
from .grant_consumption import GrantConsumptionWitness
from .permission_authority import DatabasePermissionAuthority, PermissionQuery
from .persistence import DatabaseConnection, DatabaseRow, DatabaseStatement, ProductDatabaseAdapter
from .trusted_clock import CLOCK_WITNESS_TYPE, ClockWitness

MINIMUM_CANONICAL_RESUME_SCHEMA_VERSION = 14

SELECT_SNAPSHOT_ID_BY_EXECUTION = DatabaseStatement(
    name="canonical_resume.select_snapshot_id_by_execution",
    mode="read",
    sqlite_sql="""
        SELECT id
        FROM authorization_snapshots
        WHERE execution_id = ?
    """,
)
SELECT_GRANT_BY_EXECUTION = DatabaseStatement(
    name="canonical_resume.select_grant_by_execution",
    mode="read",
    sqlite_sql="""
        SELECT jti, grant_id, execution_id, request_id, workspace_id, environment,
               authorization_snapshot_digest, execution_capsule_digest,
               grant_digest, grant_json,
               issuance_conformance_witness_digest, issuance_conformance_witness_json,
               store_clock_witness_digest, store_clock_witness_json,
               issued_at, expires_at, revocation_epoch, stored_at
        FROM execution_grants_v2
        WHERE execution_id = ?
    """,
)
SELECT_CONSUMPTION_BY_ID = DatabaseStatement(
    name="canonical_resume.select_consumption_by_id",
    mode="read",
    sqlite_sql="""
        SELECT consumption_id, jti, grant_digest, execution_id,
               authorization_snapshot_digest, execution_capsule_digest, runner_class,
               conformance_witness_digest, conformance_witness_json,
               clock_witness_digest, clock_witness_json, live_revocation_epoch,
               consumed_at, serialization_contract, authority_revision,
               consumption_digest, consumption_json
        FROM grant_consumptions_v1
        WHERE consumption_id = ?
    """,
)
SELECT_OUTBOX_BY_EXECUTION = DatabaseStatement(
    name="canonical_resume.select_outbox_by_execution",
    mode="read",
    sqlite_sql="""
        SELECT outbox_id, consumption_id, consumption_witness_digest, jti,
               grant_id, grant_digest, execution_id, request_id, actor_id,
               workspace_id, environment, capability, capability_definition_identity,
               authorization_snapshot_digest, target_kind, target_digest, payload_digest,
               required_permission, execution_binding_digest, execution_capsule_digest,
               runner_class, precondition_enforcement_class, use_semantics, created_at,
               outbox_revision, entry_digest, entry_json
        FROM dispatch_outbox_v1
        WHERE execution_id = ?
    """,
)
SELECT_INBOX_BY_EXECUTION = DatabaseStatement(
    name="canonical_resume.select_inbox_by_execution",
    mode="read",
    sqlite_sql="""
        SELECT admission_id, dispatch_id, envelope_digest, outbox_id,
               outbox_entry_digest, execution_id, workspace_id, environment,
               execution_capsule_digest, runner_class, admission_revision,
               admission_digest, admission_json
        FROM dispatch_inbox_v1
        WHERE execution_id = ?
    """,
)
SELECT_EPOCH_STATE_BY_EXECUTION = DatabaseStatement(
    name="canonical_resume.select_epoch_state_by_execution",
    mode="read",
    sqlite_sql="""
        SELECT admission_id, admission_digest, execution_id, workspace_id,
               environment, execution_capsule_digest, runner_class, current_epoch,
               current_lease_id, current_lease_digest, current_lease_acquired_at,
               current_lease_expires_at, status
        FROM execution_epoch_state_v1
        WHERE execution_id = ?
    """,
)
SELECT_LEASE_BY_ID = DatabaseStatement(
    name="canonical_resume.select_lease_by_id",
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

RESUME_READ_STATEMENTS = (
    SELECT_SNAPSHOT_ID_BY_EXECUTION,
    SELECT_GRANT_BY_EXECUTION,
    SELECT_CONSUMPTION_BY_ID,
    SELECT_OUTBOX_BY_EXECUTION,
    SELECT_INBOX_BY_EXECUTION,
    SELECT_EPOCH_STATE_BY_EXECUTION,
    SELECT_LEASE_BY_ID,
)


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


class CanonicalOperationResumeDenied(PermissionError):
    """Fail-closed denial while rebuilding canonical process-local runtime context."""

    def __init__(self, reason: str) -> None:
        self.reason = _require_text(reason, field="reason")
        super().__init__(self.reason)


class CanonicalOperationResumeService:
    """Rebuild one canonical pre-effect context exclusively from durable V-One truth.

    The service is intentionally read-only. It does not issue or consume a grant, append an outbox,
    admit a dispatch, allocate/reacquire an epoch, create a provider runtime, or perform an effect.
    It reconstructs the process-local ``CanonicalPreparedExecution`` only after revalidating current
    database permission, every durable content binding, the current terminal-profile allowlist and
    the exact current unexpired C4 lease.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        snapshot_store: AuthorizationSnapshotStore,
        permission_authority: DatabasePermissionAuthority,
        terminal_profile_registry: object,
        current_fence: DurableCurrentExecutionFence,
        envelope_revision: str,
    ) -> None:
        if not isinstance(database, ProductDatabaseAdapter):
            raise ValueError("database must implement ProductDatabaseAdapter")
        if database.backend_name != "sqlite":
            raise RuntimeError("canonical operation resume requires released SQLite persistence")
        if database.schema_version() < MINIMUM_CANONICAL_RESUME_SCHEMA_VERSION:
            raise RuntimeError("canonical operation resume requires database schema version 14 or newer")
        if getattr(snapshot_store, "db", None) is not database:
            raise ValueError("resume snapshot store must use product database")
        if getattr(permission_authority, "db", None) is not database:
            raise ValueError("resume permission authority must use product database")
        if getattr(current_fence, "db", None) is not database:
            raise ValueError("resume current fence must use product database")
        if not callable(getattr(snapshot_store, "get", None)):
            raise ValueError("snapshot_store must implement get")
        if not callable(getattr(permission_authority, "decide", None)):
            raise ValueError("permission_authority must implement decide")
        if not callable(getattr(terminal_profile_registry, "resolve", None)):
            raise ValueError("terminal_profile_registry must implement resolve")
        if not callable(getattr(current_fence, "assert_current", None)):
            raise ValueError("current_fence must implement assert_current")

        self.db = database
        self.snapshot_store = snapshot_store
        self.permission_authority = permission_authority
        self.terminal_profile_registry = terminal_profile_registry
        self.current_fence = current_fence
        self.envelope_revision = _require_text(envelope_revision, field="envelope_revision")

    def resume(self, *, actor_id: str, execution_id: str) -> CanonicalPreparedExecution:
        actor_id = _require_text(actor_id, field="actor_id")
        execution_id = _require_text(execution_id, field="execution_id")

        snapshot = self._load_snapshot(execution_id=execution_id)
        if snapshot.execution_id != execution_id:
            self._deny("SNAPSHOT_EXECUTION_MISMATCH")
        if snapshot.actor_id != actor_id:
            self._deny("ACTOR_MISMATCH")

        decision = self.permission_authority.decide(
            PermissionQuery(
                actor_id=actor_id,
                workspace_id=snapshot.workspace_id,
                environment=snapshot.environment,
                permission=REQUIRED_EXECUTION_PERMISSION,
            )
        )
        if not decision.granted:
            self._deny("LIVE_EXECUTION_PERMISSION_DENIED")

        with self.db.connect() as connection:
            grant_row = self._one_row(
                connection,
                statement=SELECT_GRANT_BY_EXECUTION,
                value=execution_id,
                artifact="GRANT",
            )
            outbox_row = self._one_row(
                connection,
                statement=SELECT_OUTBOX_BY_EXECUTION,
                value=execution_id,
                artifact="OUTBOX",
            )
            try:
                consumption_id = _require_text(
                    str(outbox_row["consumption_id"]),
                    field="consumption_id",
                )
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                self._deny("OUTBOX_ROW_INVALID", cause=exc)
            consumption_row = self._one_row(
                connection,
                statement=SELECT_CONSUMPTION_BY_ID,
                value=consumption_id,
                artifact="CONSUMPTION",
            )
            inbox_row = self._one_row(
                connection,
                statement=SELECT_INBOX_BY_EXECUTION,
                value=execution_id,
                artifact="INBOX",
            )
            state_row = self._one_row(
                connection,
                statement=SELECT_EPOCH_STATE_BY_EXECUTION,
                value=execution_id,
                artifact="EPOCH_STATE",
            )
            current_lease_id = str(state_row["current_lease_id"])
            lease_row = self._one_row(
                connection,
                statement=SELECT_LEASE_BY_ID,
                value=current_lease_id,
                artifact="LEASE",
            )

        grant = self._decode_value(
            grant_row,
            json_field="grant_json",
            decoder=ExecutionGrantV2.from_dict,
            artifact="GRANT",
        )
        grant_issuance_conformance = self._decode_value(
            grant_row,
            json_field="issuance_conformance_witness_json",
            decoder=ExecutionConformanceWitness.from_dict,
            artifact="GRANT_ISSUANCE_CONFORMANCE",
        )
        grant_store_clock = self._decode_value(
            grant_row,
            json_field="store_clock_witness_json",
            decoder=self._decode_clock_witness,
            artifact="GRANT_STORE_CLOCK",
        )
        consumption = self._decode_value(
            consumption_row,
            json_field="consumption_json",
            decoder=GrantConsumptionWitness.from_dict,
            artifact="CONSUMPTION",
        )
        conformance_witness = self._decode_value(
            consumption_row,
            json_field="conformance_witness_json",
            decoder=ExecutionConformanceWitness.from_dict,
            artifact="CONSUMPTION_CONFORMANCE",
        )
        clock_witness = self._decode_value(
            consumption_row,
            json_field="clock_witness_json",
            decoder=self._decode_clock_witness,
            artifact="CONSUMPTION_CLOCK",
        )
        outbox = self._decode_value(
            outbox_row,
            json_field="entry_json",
            decoder=DispatchOutboxEntry.from_dict,
            artifact="OUTBOX",
        )
        admission = self._decode_value(
            inbox_row,
            json_field="admission_json",
            decoder=DispatchInboxAdmission.from_dict,
            artifact="INBOX",
        )
        lease = self._decode_value(
            lease_row,
            json_field="lease_json",
            decoder=ExecutionLease.from_dict,
            artifact="LEASE",
        )
        lease_clock_witness = self._decode_value(
            lease_row,
            json_field="clock_witness_json",
            decoder=self._decode_clock_witness,
            artifact="LEASE_CLOCK",
        )

        self._validate_grant_row(grant_row, grant=grant)
        self._validate_grant_supporting_witnesses(
            row=grant_row,
            grant=grant,
            conformance_witness=grant_issuance_conformance,
            clock_witness=grant_store_clock,
        )
        self._validate_consumption_row(consumption_row, consumption=consumption)
        self._validate_consumption_supporting_witnesses(
            grant=grant,
            consumption=consumption,
            conformance_witness=conformance_witness,
            clock_witness=clock_witness,
        )
        self._validate_outbox_row(outbox_row, outbox=outbox)
        self._validate_inbox_row(inbox_row, admission=admission)
        self._validate_lease_row(lease_row, lease=lease)
        self._validate_lease_supporting_clock_witness(
            lease=lease,
            clock_witness=lease_clock_witness,
        )
        self._validate_chain(
            snapshot=snapshot,
            grant=grant,
            consumption=consumption,
            outbox=outbox,
            admission=admission,
            lease=lease,
        )

        try:
            envelope = DispatchEnvelope.create(
                outbox_entry=outbox,
                envelope_revision=self.envelope_revision,
            )
            admission.assert_bound_to(envelope=envelope, outbox_entry=outbox)
            lease.assert_bound_to(admission)
        except (PermissionError, ValueError) as exc:
            self._deny("DURABLE_CHAIN_BINDING_MISMATCH", cause=exc)

        self._validate_epoch_state(state_row, admission=admission, lease=lease)

        try:
            terminal_binding = self.terminal_profile_registry.resolve(
                capability_definition_identity=grant.capability_definition_identity,
                capability=grant.capability,
            )
        except (PermissionError, ValueError) as exc:
            self._deny("TERMINAL_PROFILE_RESOLUTION_DENIED", cause=exc)

        try:
            self.current_fence.assert_current(lease=lease)
        except (PermissionError, RuntimeError, ValueError) as exc:
            self._deny("CURRENT_LEASE_DENIED", cause=exc)

        return CanonicalPreparedExecution(
            terminal_profile=terminal_binding.terminal_profile,
            terminal_profile_binding_digest=terminal_binding.binding_digest,
            execution_id=grant.execution_id,
            request_id=grant.request_id,
            capability=grant.capability,
            capability_definition_identity=grant.capability_definition_identity,
            environment=grant.environment,
            target_digest=grant.target_digest,
            authorization_snapshot_digest=grant.authorization_snapshot_digest,
            grant_digest=grant.grant_digest,
            grant_jti=grant.jti,
            outbox_entry_digest=outbox.entry_digest,
            envelope_digest=envelope.envelope_digest,
            admission_digest=admission.admission_digest,
            lease_id=lease.lease_id,
            lease_digest=lease.lease_digest,
            execution_epoch=lease.execution_epoch,
            execution_capsule_digest=lease.execution_capsule_digest,
            snapshot=snapshot,
            grant=grant,
            outbox=outbox,
            envelope=envelope,
            admission=admission,
            lease=lease,
        )

    def _load_snapshot(self, *, execution_id: str) -> object:
        with self.db.connect() as connection:
            row = self._one_row(
                connection,
                statement=SELECT_SNAPSHOT_ID_BY_EXECUTION,
                value=execution_id,
                artifact="SNAPSHOT",
            )
        snapshot_id = str(row["id"])
        try:
            return self.snapshot_store.get(snapshot_id)
        except (LookupError, RuntimeError, ValueError) as exc:
            self._deny("SNAPSHOT_INVALID", cause=exc)

    @classmethod
    def _one_row(
        cls,
        connection: DatabaseConnection,
        *,
        statement: DatabaseStatement,
        value: str,
        artifact: str,
    ) -> DatabaseRow:
        rows = connection.execute(statement, (value,)).fetchall()
        if not rows:
            cls._deny(f"{artifact}_NOT_FOUND")
        if len(rows) != 1:
            cls._deny(f"{artifact}_AMBIGUOUS")
        return rows[0]

    @classmethod
    def _decode_value(
        cls,
        row: DatabaseRow,
        *,
        json_field: str,
        decoder: Callable[[Mapping[str, Any]], object],
        artifact: str,
    ) -> object:
        try:
            encoded = str(row[json_field])
            raw = json.loads(encoded)
            if not isinstance(raw, dict):
                raise ValueError("stored JSON is not an object")
            if canonical_json(raw) != encoded:
                raise ValueError("stored JSON is not canonical")
            value = decoder(raw)
            to_dict = getattr(value, "to_dict", None)
            if not callable(to_dict) or canonical_json(to_dict()) != encoded:
                raise ValueError("decoded object does not match stored JSON")
            return value
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            cls._deny(f"{artifact}_ROW_INVALID", cause=exc)

    @staticmethod
    def _decode_clock_witness(value: Mapping[str, Any]) -> ClockWitness:
        expected_fields = frozenset(
            {
                "witness_type",
                "source_identity",
                "authority_revision",
                "environment",
                "observed_at",
                "witness_digest",
            }
        )
        if frozenset(value) != expected_fields or value.get("witness_type") != CLOCK_WITNESS_TYPE:
            raise ValueError("clock witness schema or type is unsupported")
        return ClockWitness(
            source_identity=value["source_identity"],
            authority_revision=value["authority_revision"],
            environment=value["environment"],
            observed_at=value["observed_at"],
            witness_digest=value["witness_digest"],
        )

    @classmethod
    def _validate_grant_row(cls, row: DatabaseRow, *, grant: object) -> None:
        cls._require_row_projection(
            row,
            expected={
                "jti": grant.jti,
                "grant_id": grant.grant_id,
                "execution_id": grant.execution_id,
                "request_id": grant.request_id,
                "workspace_id": grant.workspace_id,
                "environment": grant.environment,
                "authorization_snapshot_digest": grant.authorization_snapshot_digest,
                "execution_capsule_digest": grant.execution_capsule_digest,
                "grant_digest": grant.grant_digest,
                "issued_at": grant.issued_at,
                "expires_at": grant.expires_at,
                "revocation_epoch": grant.revocation_epoch,
            },
            reason="GRANT_ROW_INVALID",
        )

    @classmethod
    def _validate_grant_supporting_witnesses(
        cls,
        *,
        row: DatabaseRow,
        grant: object,
        conformance_witness: object,
        clock_witness: object,
    ) -> None:
        expected = {
            "issuance_conformance_witness_digest": conformance_witness.witness_digest,
            "store_clock_witness_digest": clock_witness.witness_digest,
            "stored_at": clock_witness.observed_at,
        }
        cls._require_row_projection(
            row,
            expected=expected,
            reason="GRANT_SUPPORTING_WITNESS_ROW_INVALID",
        )
        binding_expected = {
            "conformance_grant_digest": grant.grant_digest,
            "conformance_execution_binding_digest": grant.execution_binding_digest,
            "conformance_execution_capsule_digest": grant.execution_capsule_digest,
            "conformance_capability_definition_identity": grant.capability_definition_identity,
            "conformance_target_kind": grant.target_kind,
            "conformance_runner_class": grant.runner_class,
            "conformance_precondition_enforcement_class": (
                grant.precondition_enforcement_class
            ),
            "clock_environment": grant.environment,
        }
        binding_actual = {
            "conformance_grant_digest": conformance_witness.grant_digest,
            "conformance_execution_binding_digest": conformance_witness.execution_binding_digest,
            "conformance_execution_capsule_digest": conformance_witness.execution_capsule_digest,
            "conformance_capability_definition_identity": (
                conformance_witness.capability_definition_identity
            ),
            "conformance_target_kind": conformance_witness.target_kind,
            "conformance_runner_class": conformance_witness.runner_class,
            "conformance_precondition_enforcement_class": (
                conformance_witness.precondition_enforcement_class
            ),
            "clock_environment": clock_witness.environment,
        }
        if binding_actual != binding_expected:
            cls._deny("GRANT_SUPPORTING_WITNESS_MISMATCH")
        if not (grant.issued_at <= clock_witness.observed_at < grant.expires_at):
            cls._deny("GRANT_STORE_CLOCK_OUTSIDE_VALIDITY")

    @classmethod
    def _validate_consumption_row(cls, row: DatabaseRow, *, consumption: object) -> None:
        cls._require_row_projection(
            row,
            expected={
                "consumption_id": consumption.consumption_id,
                "jti": consumption.jti,
                "grant_digest": consumption.grant_digest,
                "execution_id": consumption.execution_id,
                "authorization_snapshot_digest": consumption.authorization_snapshot_digest,
                "execution_capsule_digest": consumption.execution_capsule_digest,
                "runner_class": consumption.runner_class,
                "conformance_witness_digest": consumption.conformance_witness_digest,
                "clock_witness_digest": consumption.clock_witness_digest,
                "live_revocation_epoch": consumption.live_revocation_epoch,
                "consumed_at": consumption.consumed_at,
                "serialization_contract": consumption.serialization_contract,
                "authority_revision": consumption.authority_revision,
                "consumption_digest": consumption.witness_digest,
            },
            reason="CONSUMPTION_ROW_INVALID",
        )

    @classmethod
    def _validate_consumption_supporting_witnesses(
        cls,
        *,
        grant: object,
        consumption: object,
        conformance_witness: object,
        clock_witness: object,
    ) -> None:
        expected = {
            "conformance_witness_digest": consumption.conformance_witness_digest,
            "conformance_grant_digest": grant.grant_digest,
            "conformance_execution_binding_digest": grant.execution_binding_digest,
            "conformance_execution_capsule_digest": grant.execution_capsule_digest,
            "conformance_capability_definition_identity": grant.capability_definition_identity,
            "conformance_target_kind": grant.target_kind,
            "conformance_runner_class": grant.runner_class,
            "conformance_precondition_enforcement_class": (
                grant.precondition_enforcement_class
            ),
            "clock_witness_digest": consumption.clock_witness_digest,
            "clock_environment": grant.environment,
            "clock_observed_at": consumption.consumed_at,
        }
        actual = {
            "conformance_witness_digest": conformance_witness.witness_digest,
            "conformance_grant_digest": conformance_witness.grant_digest,
            "conformance_execution_binding_digest": conformance_witness.execution_binding_digest,
            "conformance_execution_capsule_digest": conformance_witness.execution_capsule_digest,
            "conformance_capability_definition_identity": (
                conformance_witness.capability_definition_identity
            ),
            "conformance_target_kind": conformance_witness.target_kind,
            "conformance_runner_class": conformance_witness.runner_class,
            "conformance_precondition_enforcement_class": (
                conformance_witness.precondition_enforcement_class
            ),
            "clock_witness_digest": clock_witness.witness_digest,
            "clock_environment": clock_witness.environment,
            "clock_observed_at": clock_witness.observed_at,
        }
        if actual != expected:
            cls._deny("CONSUMPTION_SUPPORTING_WITNESS_MISMATCH")
        if not (grant.issued_at <= clock_witness.observed_at < grant.expires_at):
            cls._deny("CONSUMPTION_CLOCK_OUTSIDE_GRANT_VALIDITY")

    @classmethod
    def _validate_outbox_row(cls, row: DatabaseRow, *, outbox: object) -> None:
        cls._require_row_projection(
            row,
            expected={
                "outbox_id": outbox.outbox_id,
                "consumption_id": outbox.consumption_id,
                "consumption_witness_digest": outbox.consumption_witness_digest,
                "jti": outbox.jti,
                "grant_id": outbox.grant_id,
                "grant_digest": outbox.grant_digest,
                "execution_id": outbox.execution_id,
                "request_id": outbox.request_id,
                "actor_id": outbox.actor_id,
                "workspace_id": outbox.workspace_id,
                "environment": outbox.environment,
                "capability": outbox.capability,
                "capability_definition_identity": outbox.capability_definition_identity,
                "authorization_snapshot_digest": outbox.authorization_snapshot_digest,
                "target_kind": outbox.target_kind,
                "target_digest": outbox.target_digest,
                "payload_digest": outbox.payload_digest,
                "required_permission": outbox.required_permission,
                "execution_binding_digest": outbox.execution_binding_digest,
                "execution_capsule_digest": outbox.execution_capsule_digest,
                "runner_class": outbox.runner_class,
                "precondition_enforcement_class": outbox.precondition_enforcement_class,
                "use_semantics": outbox.use_semantics,
                "created_at": outbox.created_at,
                "outbox_revision": outbox.outbox_revision,
                "entry_digest": outbox.entry_digest,
            },
            reason="OUTBOX_ROW_INVALID",
        )

    @classmethod
    def _validate_inbox_row(cls, row: DatabaseRow, *, admission: object) -> None:
        cls._require_row_projection(
            row,
            expected={
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
            },
            reason="INBOX_ROW_INVALID",
        )

    @classmethod
    def _validate_lease_row(cls, row: DatabaseRow, *, lease: object) -> None:
        cls._require_row_projection(
            row,
            expected={
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
            },
            reason="LEASE_ROW_INVALID",
        )

    @classmethod
    def _validate_lease_supporting_clock_witness(
        cls,
        *,
        lease: object,
        clock_witness: object,
    ) -> None:
        expected = {
            "clock_witness_digest": lease.clock_witness_digest,
            "clock_environment": lease.environment,
            "clock_observed_at": lease.acquired_at,
        }
        actual = {
            "clock_witness_digest": clock_witness.witness_digest,
            "clock_environment": clock_witness.environment,
            "clock_observed_at": clock_witness.observed_at,
        }
        if actual != expected:
            cls._deny("LEASE_CLOCK_WITNESS_MISMATCH")

    @classmethod
    def _validate_chain(
        cls,
        *,
        snapshot: object,
        grant: object,
        consumption: object,
        outbox: object,
        admission: object,
        lease: object,
    ) -> None:
        snapshot_expected = {
            "execution_id": snapshot.execution_id,
            "request_id": snapshot.request_id,
            "actor_id": snapshot.actor_id,
            "workspace_id": snapshot.workspace_id,
            "environment": snapshot.environment,
            "capability": snapshot.capability,
            "capability_definition_identity": snapshot.capability_definition_identity,
            "target_kind": snapshot.target_kind,
            "target_digest": snapshot.target_digest,
            "payload_digest": snapshot.payload_digest,
            "policy_version": snapshot.policy_version,
            "policy_identity": snapshot.policy_identity,
            "approval_set_digest": snapshot.approval_set_digest,
            "authorization_snapshot_digest": snapshot.snapshot_digest,
        }
        grant_actual = {
            "execution_id": grant.execution_id,
            "request_id": grant.request_id,
            "actor_id": grant.actor_id,
            "workspace_id": grant.workspace_id,
            "environment": grant.environment,
            "capability": grant.capability,
            "capability_definition_identity": grant.capability_definition_identity,
            "target_kind": grant.target_kind,
            "target_digest": grant.target_digest,
            "payload_digest": grant.payload_digest,
            "policy_version": grant.policy_version,
            "policy_identity": grant.policy_identity,
            "approval_set_digest": grant.approval_set_digest,
            "authorization_snapshot_digest": grant.authorization_snapshot_digest,
        }
        if grant_actual != snapshot_expected:
            cls._deny("SNAPSHOT_GRANT_BINDING_MISMATCH")
        if grant.required_permission != REQUIRED_EXECUTION_PERMISSION:
            cls._deny("GRANT_PERMISSION_MISMATCH")

        consumption_expected = {
            "jti": grant.jti,
            "grant_id": grant.grant_id,
            "grant_digest": grant.grant_digest,
            "execution_id": grant.execution_id,
            "authorization_snapshot_digest": grant.authorization_snapshot_digest,
            "execution_capsule_digest": grant.execution_capsule_digest,
            "runner_class": grant.runner_class,
            "live_revocation_epoch": grant.revocation_epoch,
        }
        consumption_actual = {
            key: getattr(consumption, key) for key in consumption_expected
        }
        if consumption_actual != consumption_expected:
            cls._deny("GRANT_CONSUMPTION_BINDING_MISMATCH")

        outbox_consumption_expected = {
            "consumption_id": consumption.consumption_id,
            "consumption_witness_digest": consumption.witness_digest,
            "created_at": consumption.consumed_at,
        }
        outbox_consumption_actual = {
            key: getattr(outbox, key) for key in outbox_consumption_expected
        }
        if outbox_consumption_actual != outbox_consumption_expected:
            cls._deny("CONSUMPTION_OUTBOX_BINDING_MISMATCH")

        grant_expected = {
            "jti": grant.jti,
            "grant_id": grant.grant_id,
            "grant_digest": grant.grant_digest,
            "execution_id": grant.execution_id,
            "request_id": grant.request_id,
            "actor_id": grant.actor_id,
            "workspace_id": grant.workspace_id,
            "environment": grant.environment,
            "capability": grant.capability,
            "capability_definition_identity": grant.capability_definition_identity,
            "authorization_snapshot_digest": grant.authorization_snapshot_digest,
            "target_kind": grant.target_kind,
            "target_digest": grant.target_digest,
            "payload_digest": grant.payload_digest,
            "required_permission": grant.required_permission,
            "execution_binding_digest": grant.execution_binding_digest,
            "execution_capsule_digest": grant.execution_capsule_digest,
            "runner_class": grant.runner_class,
            "precondition_enforcement_class": grant.precondition_enforcement_class,
            "use_semantics": grant.use_semantics,
        }
        outbox_actual = {key: getattr(outbox, key) for key in grant_expected}
        if outbox_actual != grant_expected:
            cls._deny("GRANT_OUTBOX_BINDING_MISMATCH")

        durable_expected = {
            "execution_id": outbox.execution_id,
            "workspace_id": outbox.workspace_id,
            "environment": outbox.environment,
            "execution_capsule_digest": outbox.execution_capsule_digest,
            "runner_class": outbox.runner_class,
        }
        admission_actual = {key: getattr(admission, key) for key in durable_expected}
        lease_actual = {key: getattr(lease, key) for key in durable_expected}
        if admission_actual != durable_expected or lease_actual != durable_expected:
            cls._deny("DURABLE_EXECUTION_BINDING_MISMATCH")

    @classmethod
    def _validate_epoch_state(
        cls,
        row: DatabaseRow,
        *,
        admission: object,
        lease: object,
    ) -> None:
        if str(row["status"]) != "ACTIVE":
            cls._deny("EXECUTION_NOT_ACTIVE")
        cls._require_row_projection(
            row,
            expected={
                "admission_id": admission.admission_id,
                "admission_digest": admission.admission_digest,
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
            },
            reason="CURRENT_EXECUTION_LEASE_MISMATCH",
        )

    @classmethod
    def _require_row_projection(
        cls,
        row: DatabaseRow,
        *,
        expected: Mapping[str, object],
        reason: str,
    ) -> None:
        try:
            for field, expected_value in expected.items():
                actual = row[field]
                if isinstance(expected_value, str):
                    actual = str(actual)
                if actual != expected_value:
                    cls._deny(reason)
        except (KeyError, IndexError, TypeError) as exc:
            cls._deny(reason, cause=exc)

    @staticmethod
    def _deny(reason: str, *, cause: BaseException | None = None) -> NoReturn:
        error = CanonicalOperationResumeDenied(reason)
        if cause is None:
            raise error
        raise error from cause
