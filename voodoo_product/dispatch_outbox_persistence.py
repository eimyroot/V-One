from __future__ import annotations

from typing import Any, Final, NoReturn

from .dispatch_outbox import DispatchOutboxEntry
from .evidence_primitives import canonical_json, new_id
from .grant_consumption import (
    INSERT_CONSUMPTION,
    SELECT_CONSUMPTION_BY_JTI,
    SELECT_STORED_GRANT,
    DurableGrantService,
    GrantConsumptionDenied,
    GrantConsumptionWitness,
)
from .persistence import DatabaseIntegrityError, DatabaseStatement

MINIMUM_DISPATCH_OUTBOX_SCHEMA_VERSION: Final = 11

_REQUIRED_OUTBOX_COLUMNS: Final = {
    "outbox_id",
    "consumption_id",
    "consumption_witness_digest",
    "jti",
    "grant_id",
    "grant_digest",
    "execution_id",
    "request_id",
    "actor_id",
    "workspace_id",
    "environment",
    "capability",
    "capability_definition_identity",
    "authorization_snapshot_digest",
    "target_kind",
    "target_digest",
    "payload_digest",
    "required_permission",
    "execution_binding_digest",
    "execution_capsule_digest",
    "runner_class",
    "precondition_enforcement_class",
    "use_semantics",
    "created_at",
    "outbox_revision",
    "entry_digest",
    "entry_json",
}
_REQUIRED_OUTBOX_INDEXES: Final = {
    "idx_dispatch_outbox_v1_workspace_environment",
    "idx_dispatch_outbox_v1_created_at",
}
_REQUIRED_OUTBOX_TRIGGERS: Final = {
    "trg_dispatch_outbox_v1_binding_insert",
    "trg_dispatch_outbox_v1_immutable_update",
    "trg_dispatch_outbox_v1_immutable_delete",
}

INSERT_DISPATCH_OUTBOX = DatabaseStatement(
    name="dispatch_outbox.insert",
    mode="write",
    sqlite_sql="""
        INSERT INTO dispatch_outbox_v1(
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
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """,
)

SELECT_ORPHAN_CONSUMPTION = DatabaseStatement(
    name="dispatch_outbox.select_orphan_consumption",
    mode="read",
    sqlite_sql="""
        SELECT consumption.consumption_id
        FROM grant_consumptions_v1 AS consumption
        LEFT JOIN dispatch_outbox_v1 AS outbox
          ON outbox.consumption_id = consumption.consumption_id
        WHERE outbox.outbox_id IS NULL
        LIMIT 1
    """,
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


class DispatchOutboxPersistenceDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DurableDispatchOutboxService:
    """Atomically consume one B4 Grant and append the exact C1a outbox intent.

    The wrapped DurableGrantService remains the sole authority for Grant decoding, trusted time,
    emergency-stop/revocation checks and fresh B3 execution conformance. C1b adds only the durable
    handoff persistence boundary required before dispatch may exist.
    """

    def __init__(
        self,
        *,
        grant_service: DurableGrantService,
        outbox_revision: str,
        id_factory: Any = new_id,
    ) -> None:
        if not isinstance(grant_service, DurableGrantService):
            raise ValueError("grant_service must be DurableGrantService")
        _require_text(outbox_revision, field="outbox_revision")
        if not callable(id_factory):
            raise ValueError("id_factory is invalid")
        if grant_service.db.schema_version() < MINIMUM_DISPATCH_OUTBOX_SCHEMA_VERSION:
            raise RuntimeError("C1b requires database schema version 11 or newer")

        self.grant_service = grant_service
        self.db = grant_service.db
        self.outbox_revision = outbox_revision
        self._id_factory = id_factory

        self._validate_outbox_schema()
        self._assert_no_orphan_consumptions()

    def _validate_outbox_schema(self) -> None:
        with self.db.connect() as connection:
            columns = {
                str(row["name"])
                for row in connection.execute(
                    'PRAGMA table_info("dispatch_outbox_v1")'
                ).fetchall()
            }
            if columns != _REQUIRED_OUTBOX_COLUMNS:
                raise RuntimeError(
                    "C1b schema validation failed for dispatch_outbox_v1: "
                    f"expected {sorted(_REQUIRED_OUTBOX_COLUMNS)}, found {sorted(columns)}"
                )

            indexes = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }
            missing_indexes = _REQUIRED_OUTBOX_INDEXES - indexes
            if missing_indexes:
                raise RuntimeError(
                    "C1b schema validation failed: missing indexes "
                    f"{sorted(missing_indexes)}"
                )

            triggers = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                ).fetchall()
            }
            missing_triggers = _REQUIRED_OUTBOX_TRIGGERS - triggers
            if missing_triggers:
                raise RuntimeError(
                    "C1b schema validation failed: missing triggers "
                    f"{sorted(missing_triggers)}"
                )

    def _assert_no_orphan_consumptions(self) -> None:
        with self.db.connect() as connection:
            orphan = connection.execute(SELECT_ORPHAN_CONSUMPTION).fetchone()
        if orphan is not None:
            raise RuntimeError(
                "C1b refuses historical Grant consumption without a durable outbox intent"
            )

    def consume_and_enqueue(self, *, jti: str) -> DispatchOutboxEntry:
        """Consume and enqueue exactly once in the same serialized DB transaction."""

        _require_text(jti, field="jti")
        grant_service = self.grant_service

        with self.db.transaction() as connection:
            existing = connection.execute(
                SELECT_CONSUMPTION_BY_JTI,
                (jti,),
            ).fetchone()
            if existing is not None:
                raise GrantConsumptionDenied("GRANT_ALREADY_CONSUMED")

            row = connection.execute(SELECT_STORED_GRANT, (jti,)).fetchone()
            if row is None:
                raise GrantConsumptionDenied("GRANT_NOT_FOUND")
            grant = grant_service._decode_stored_grant(row)

            clock_witness = grant_service._trusted_clock_witness(grant)
            live_epoch = grant_service._assert_live_authority(
                connection,
                grant=grant,
                clock_witness=clock_witness,
            )
            conformance = grant_service._fresh_conformance(grant)
            witness = GrantConsumptionWitness.create(
                consumption_id=grant_service._id_factory("gcon"),
                grant=grant,
                conformance_witness=conformance,
                clock_witness=clock_witness,
                live_revocation_epoch=live_epoch,
                authority_revision=grant_service.authority_revision,
            )
            outbox = DispatchOutboxEntry.create(
                outbox_id=self._id_factory("outbox"),
                grant=grant,
                consumption_witness=witness,
                outbox_revision=self.outbox_revision,
            )

            try:
                connection.execute(
                    INSERT_CONSUMPTION,
                    (
                        witness.consumption_id,
                        grant.jti,
                        grant.grant_digest,
                        grant.execution_id,
                        grant.authorization_snapshot_digest,
                        grant.execution_capsule_digest,
                        grant.runner_class,
                        conformance.witness_digest,
                        canonical_json(conformance.to_dict()),
                        clock_witness.witness_digest,
                        canonical_json(clock_witness.to_dict()),
                        live_epoch,
                        witness.consumed_at,
                        witness.serialization_contract,
                        witness.authority_revision,
                        witness.witness_digest,
                        canonical_json(witness.to_dict()),
                    ),
                )
            except DatabaseIntegrityError as exc:
                raise GrantConsumptionDenied("GRANT_ALREADY_CONSUMED") from exc

            try:
                connection.execute(
                    INSERT_DISPATCH_OUTBOX,
                    (
                        outbox.outbox_id,
                        outbox.consumption_id,
                        outbox.consumption_witness_digest,
                        outbox.jti,
                        outbox.grant_id,
                        outbox.grant_digest,
                        outbox.execution_id,
                        outbox.request_id,
                        outbox.actor_id,
                        outbox.workspace_id,
                        outbox.environment,
                        outbox.capability,
                        outbox.capability_definition_identity,
                        outbox.authorization_snapshot_digest,
                        outbox.target_kind,
                        outbox.target_digest,
                        outbox.payload_digest,
                        outbox.required_permission,
                        outbox.execution_binding_digest,
                        outbox.execution_capsule_digest,
                        outbox.runner_class,
                        outbox.precondition_enforcement_class,
                        outbox.use_semantics,
                        outbox.created_at,
                        outbox.outbox_revision,
                        outbox.entry_digest,
                        canonical_json(outbox.to_dict()),
                    ),
                )
            except DatabaseIntegrityError as exc:
                self._deny("OUTBOX_PERSISTENCE_CONFLICT", cause=exc)

        return outbox

    @staticmethod
    def _deny(
        reason: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        error = DispatchOutboxPersistenceDenied(reason)
        if cause is None:
            raise error
        raise error from cause
