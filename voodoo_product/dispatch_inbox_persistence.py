from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, NoReturn

from .dispatch_envelope import DispatchEnvelope
from .dispatch_inbox import (
    DUPLICATE_REDELIVERY,
    DispatchInboxAdmission,
    DispatchInboxContentConflict,
)
from .dispatch_outbox import DispatchOutboxEntry
from .evidence_primitives import canonical_json
from .persistence import (
    DatabaseIntegrityError,
    DatabaseRow,
    DatabaseStatement,
    ProductDatabaseAdapter,
)

MINIMUM_DISPATCH_INBOX_SCHEMA_VERSION: Final = 12
ADMITTED: Final = "ADMITTED"

_REQUIRED_INBOX_COLUMNS: Final = {
    "admission_id",
    "dispatch_id",
    "envelope_digest",
    "outbox_id",
    "outbox_entry_digest",
    "execution_id",
    "workspace_id",
    "environment",
    "execution_capsule_digest",
    "runner_class",
    "admission_revision",
    "admission_digest",
    "admission_json",
}
_REQUIRED_INBOX_INDEXES: Final = {
    "idx_dispatch_inbox_v1_workspace_environment",
    "idx_dispatch_inbox_v1_execution",
}
_REQUIRED_INBOX_TRIGGERS: Final = {
    "trg_dispatch_inbox_v1_outbox_binding_insert",
    "trg_dispatch_inbox_v1_immutable_update",
    "trg_dispatch_inbox_v1_immutable_delete",
}

SELECT_DISPATCH_OUTBOX_BY_ID = DatabaseStatement(
    name="dispatch_inbox.select_outbox_by_id",
    mode="read",
    sqlite_sql="""
        SELECT
            outbox_id,
            consumption_id,
            consumption_witness_digest,
            jti,
            grant_id,
            grant_digest,
            execution_id,
            request_id,
            actor_id,
            workspace_id,
            environment,
            capability,
            capability_definition_identity,
            authorization_snapshot_digest,
            target_kind,
            target_digest,
            payload_digest,
            required_permission,
            execution_binding_digest,
            execution_capsule_digest,
            runner_class,
            precondition_enforcement_class,
            use_semantics,
            created_at,
            outbox_revision,
            entry_digest,
            entry_json
        FROM dispatch_outbox_v1
        WHERE outbox_id = ?
    """,
)

SELECT_DISPATCH_INBOX_BY_ID = DatabaseStatement(
    name="dispatch_inbox.select_by_dispatch_id",
    mode="read",
    sqlite_sql="""
        SELECT
            admission_id,
            dispatch_id,
            envelope_digest,
            outbox_id,
            outbox_entry_digest,
            execution_id,
            workspace_id,
            environment,
            execution_capsule_digest,
            runner_class,
            admission_revision,
            admission_digest,
            admission_json
        FROM dispatch_inbox_v1
        WHERE dispatch_id = ?
    """,
)

INSERT_DISPATCH_INBOX = DatabaseStatement(
    name="dispatch_inbox.insert",
    mode="write",
    sqlite_sql="""
        INSERT INTO dispatch_inbox_v1(
            admission_id,
            dispatch_id,
            envelope_digest,
            outbox_id,
            outbox_entry_digest,
            execution_id,
            workspace_id,
            environment,
            execution_capsule_digest,
            runner_class,
            admission_revision,
            admission_digest,
            admission_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
)


class DispatchInboxPersistenceDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class DispatchInboxPersistenceResult:
    outcome: str
    admission: DispatchInboxAdmission

    def __post_init__(self) -> None:
        if self.outcome not in {ADMITTED, DUPLICATE_REDELIVERY}:
            raise ValueError("dispatch inbox persistence outcome is unsupported")
        if not isinstance(self.admission, DispatchInboxAdmission):
            raise ValueError("admission must be DispatchInboxAdmission")


class DurableDispatchInboxService:
    """Persist one C3 inbox admission and classify exact at-least-once redelivery.

    The caller supplies only a validated DispatchEnvelope. The service resolves the authoritative
    durable C1b outbox row itself, verifies the envelope against that exact row, and uses SQLite's
    released BEGIN IMMEDIATE global-write serialization so concurrent deliveries cannot both become
    first admissions. The service creates no lease, execution epoch, Runner identity, credential or
    provider effect.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        admission_revision: str,
    ) -> None:
        if not isinstance(database, ProductDatabaseAdapter):
            raise ValueError("database must implement ProductDatabaseAdapter")
        if database.backend_name != "sqlite" or database.write_serialization != "global":
            raise RuntimeError(
                "C3b requires released SQLite global write serialization"
            )
        if database.schema_version() < MINIMUM_DISPATCH_INBOX_SCHEMA_VERSION:
            raise RuntimeError("C3b requires database schema version 12 or newer")
        if (
            not isinstance(admission_revision, str)
            or not admission_revision
            or admission_revision != admission_revision.strip()
            or "\x00" in admission_revision
        ):
            raise ValueError("admission_revision is invalid")

        self.db = database
        self.admission_revision = admission_revision
        self._validate_inbox_schema()

    def _validate_inbox_schema(self) -> None:
        with self.db.connect() as connection:
            columns = {
                str(row["name"])
                for row in connection.execute(
                    'PRAGMA table_info("dispatch_inbox_v1")'
                ).fetchall()
            }
            if columns != _REQUIRED_INBOX_COLUMNS:
                raise RuntimeError(
                    "C3b schema validation failed for dispatch_inbox_v1: "
                    f"expected {sorted(_REQUIRED_INBOX_COLUMNS)}, found {sorted(columns)}"
                )

            indexes = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }
            missing_indexes = _REQUIRED_INBOX_INDEXES - indexes
            if missing_indexes:
                raise RuntimeError(
                    "C3b schema validation failed: missing indexes "
                    f"{sorted(missing_indexes)}"
                )

            triggers = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                ).fetchall()
            }
            missing_triggers = _REQUIRED_INBOX_TRIGGERS - triggers
            if missing_triggers:
                raise RuntimeError(
                    "C3b schema validation failed: missing triggers "
                    f"{sorted(missing_triggers)}"
                )

    def admit(self, *, envelope: DispatchEnvelope) -> DispatchInboxPersistenceResult:
        """Admit the first exact dispatch and deduplicate exact redelivery durably."""

        if not isinstance(envelope, DispatchEnvelope):
            raise ValueError("envelope must be DispatchEnvelope")

        with self.db.transaction() as connection:
            outbox_row = connection.execute(
                SELECT_DISPATCH_OUTBOX_BY_ID,
                (envelope.outbox_id,),
            ).fetchone()
            if outbox_row is None:
                self._deny("OUTBOX_NOT_FOUND")
            outbox = self._decode_outbox(outbox_row)
            try:
                envelope.assert_bound_to(outbox)
            except PermissionError as exc:
                self._deny("OUTBOX_BINDING_MISMATCH", cause=exc)

            existing_row = connection.execute(
                SELECT_DISPATCH_INBOX_BY_ID,
                (envelope.dispatch_id,),
            ).fetchone()
            if existing_row is not None:
                existing = self._decode_admission(existing_row)
                try:
                    outcome = existing.classify_redelivery(
                        envelope=envelope,
                        outbox_entry=outbox,
                    )
                except DispatchInboxContentConflict:
                    raise
                except (PermissionError, ValueError) as exc:
                    self._deny("INBOX_ROW_INVALID", cause=exc)
                return DispatchInboxPersistenceResult(
                    outcome=outcome,
                    admission=existing,
                )

            admission = DispatchInboxAdmission.create(
                envelope=envelope,
                outbox_entry=outbox,
                admission_revision=self.admission_revision,
            )
            try:
                connection.execute(
                    INSERT_DISPATCH_INBOX,
                    (
                        admission.admission_id,
                        admission.dispatch_id,
                        admission.envelope_digest,
                        admission.outbox_id,
                        admission.outbox_entry_digest,
                        admission.execution_id,
                        admission.workspace_id,
                        admission.environment,
                        admission.execution_capsule_digest,
                        admission.runner_class,
                        admission.admission_revision,
                        admission.admission_digest,
                        canonical_json(admission.to_dict()),
                    ),
                )
            except DatabaseIntegrityError as exc:
                self._deny("INBOX_PERSISTENCE_CONFLICT", cause=exc)

        return DispatchInboxPersistenceResult(outcome=ADMITTED, admission=admission)

    def _decode_outbox(self, row: DatabaseRow) -> DispatchOutboxEntry:
        try:
            raw = json.loads(str(row["entry_json"]))
            outbox = DispatchOutboxEntry.from_dict(raw)
        except (TypeError, ValueError) as exc:
            self._deny("OUTBOX_ROW_INVALID", cause=exc)

        expected = {
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
            "entry_json": canonical_json(outbox.to_dict()),
        }
        actual = {key: row[key] for key in expected}
        if actual != expected:
            self._deny("OUTBOX_ROW_INVALID")
        return outbox

    def _decode_admission(self, row: DatabaseRow) -> DispatchInboxAdmission:
        try:
            raw = json.loads(str(row["admission_json"]))
            admission = DispatchInboxAdmission.from_dict(raw)
        except (TypeError, ValueError) as exc:
            self._deny("INBOX_ROW_INVALID", cause=exc)

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
        actual = {key: row[key] for key in expected}
        if actual != expected:
            self._deny("INBOX_ROW_INVALID")
        return admission

    @staticmethod
    def _deny(
        reason: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        error = DispatchInboxPersistenceDenied(reason)
        if cause is None:
            raise error
        raise error from cause
