from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, NoReturn, Self

from .authoritative_grant import ExecutionGrantV2, GrantRevocationEpochAuthority
from .authorization_snapshot import AuthorizationSnapshot
from .evidence_primitives import canonical_json, new_id
from .execution_conformance import ExecutionConformanceAuthority, ExecutionConformanceWitness
from .monotonic_authority import AuthorityConstraint
from .operational_safety import OperationalSafetyService
from .persistence import (
    DatabaseConnection,
    DatabaseIntegrityError,
    DatabaseStatement,
    ProductDatabaseAdapter,
)
from .trusted_clock import ClockWitness, TrustedClockAuthority

GRANT_CONSUMPTION_WITNESS_TYPE: Final = "grant-consumption-witness/v1"
SQLITE_SERIALIZATION_CONTRACT: Final = "sqlite-begin-immediate/v1"
MINIMUM_SCHEMA_VERSION: Final = 10

_REQUIRED_TABLE_COLUMNS: Final = {
    "execution_grants_v2": {
        "jti",
        "grant_id",
        "execution_id",
        "request_id",
        "workspace_id",
        "environment",
        "authorization_snapshot_digest",
        "execution_capsule_digest",
        "grant_digest",
        "grant_json",
        "issuance_conformance_witness_digest",
        "issuance_conformance_witness_json",
        "store_clock_witness_digest",
        "store_clock_witness_json",
        "issued_at",
        "expires_at",
        "revocation_epoch",
        "stored_at",
        "store_revision",
    },
    "grant_consumptions_v1": {
        "consumption_id",
        "jti",
        "grant_digest",
        "execution_id",
        "authorization_snapshot_digest",
        "execution_capsule_digest",
        "runner_class",
        "conformance_witness_digest",
        "conformance_witness_json",
        "clock_witness_digest",
        "clock_witness_json",
        "live_revocation_epoch",
        "consumed_at",
        "serialization_contract",
        "authority_revision",
        "consumption_digest",
        "consumption_json",
    },
}
_TABLE_INFO_SQL: Final = {
    "execution_grants_v2": 'PRAGMA table_info("execution_grants_v2")',
    "grant_consumptions_v1": 'PRAGMA table_info("grant_consumptions_v1")',
}
_REQUIRED_INDEXES: Final = {
    "idx_execution_grants_v2_request",
    "idx_execution_grants_v2_workspace_environment",
    "idx_grant_consumptions_v1_execution",
}
_REQUIRED_TRIGGERS: Final = {
    "trg_execution_grants_v2_snapshot_binding_insert",
    "trg_execution_grants_v2_immutable_update",
    "trg_execution_grants_v2_immutable_delete",
    "trg_grant_consumptions_v1_grant_binding_insert",
    "trg_grant_consumptions_v1_immutable_update",
    "trg_grant_consumptions_v1_immutable_delete",
}

SELECT_STORED_GRANT = DatabaseStatement(
    name="grant_consumption.select_stored_grant",
    mode="read",
    sqlite_sql="""
        SELECT
            jti,
            grant_id,
            execution_id,
            request_id,
            workspace_id,
            environment,
            authorization_snapshot_digest,
            execution_capsule_digest,
            grant_digest,
            grant_json,
            issuance_conformance_witness_digest,
            issuance_conformance_witness_json,
            store_clock_witness_digest,
            store_clock_witness_json,
            issued_at,
            expires_at,
            revocation_epoch,
            stored_at,
            store_revision
        FROM execution_grants_v2
        WHERE jti = ?
    """,
)
SELECT_CONSUMPTION_BY_JTI = DatabaseStatement(
    name="grant_consumption.select_consumption_by_jti",
    mode="read",
    sqlite_sql="""
        SELECT consumption_id, consumption_digest
        FROM grant_consumptions_v1
        WHERE jti = ?
    """,
)
INSERT_STORED_GRANT = DatabaseStatement(
    name="grant_consumption.insert_stored_grant",
    mode="write",
    sqlite_sql="""
        INSERT INTO execution_grants_v2(
            jti,
            grant_id,
            execution_id,
            request_id,
            workspace_id,
            environment,
            authorization_snapshot_digest,
            execution_capsule_digest,
            grant_digest,
            grant_json,
            issuance_conformance_witness_digest,
            issuance_conformance_witness_json,
            store_clock_witness_digest,
            store_clock_witness_json,
            issued_at,
            expires_at,
            revocation_epoch,
            stored_at,
            store_revision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
)
INSERT_CONSUMPTION = DatabaseStatement(
    name="grant_consumption.insert_consumption",
    mode="write",
    sqlite_sql="""
        INSERT INTO grant_consumptions_v1(
            consumption_id,
            jti,
            grant_digest,
            execution_id,
            authorization_snapshot_digest,
            execution_capsule_digest,
            runner_class,
            conformance_witness_digest,
            conformance_witness_json,
            clock_witness_digest,
            clock_witness_json,
            live_revocation_epoch,
            consumed_at,
            serialization_contract,
            authority_revision,
            consumption_digest,
            consumption_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
)

_WITNESS_FIELDS = frozenset(
    {
        "schema_version",
        "witness_type",
        "consumption_id",
        "jti",
        "grant_id",
        "grant_digest",
        "execution_id",
        "authorization_snapshot_digest",
        "execution_capsule_digest",
        "runner_class",
        "conformance_witness_digest",
        "clock_witness_digest",
        "live_revocation_epoch",
        "consumed_at",
        "serialization_contract",
        "authority_revision",
        "witness_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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


def _require_timestamp(value: object, *, field: str) -> tuple[str, datetime]:
    text = _require_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return canonical, parsed.astimezone(UTC)


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


@dataclass(frozen=True, slots=True)
class GrantConsumptionWitness:
    """Content-addressed proof that one durable ONE_TIME grant was consumed once."""

    consumption_id: str
    jti: str
    grant_id: str
    grant_digest: str
    execution_id: str
    authorization_snapshot_digest: str
    execution_capsule_digest: str
    runner_class: str
    conformance_witness_digest: str
    clock_witness_digest: str
    live_revocation_epoch: int
    consumed_at: str
    serialization_contract: str
    authority_revision: str
    witness_digest: str

    def __post_init__(self) -> None:
        for field in (
            "consumption_id",
            "jti",
            "grant_id",
            "execution_id",
            "runner_class",
            "serialization_contract",
            "authority_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "grant_digest",
            "authorization_snapshot_digest",
            "execution_capsule_digest",
            "conformance_witness_digest",
            "clock_witness_digest",
            "witness_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if type(self.live_revocation_epoch) is not int or self.live_revocation_epoch < 0:
            raise ValueError("live_revocation_epoch must be non-negative")
        _require_timestamp(self.consumed_at, field="consumed_at")
        if self.serialization_contract != SQLITE_SERIALIZATION_CONTRACT:
            raise ValueError("serialization_contract is unsupported")
        if self.witness_digest != _digest(self._claims_without_digest()):
            raise ValueError("witness_digest does not match grant consumption witness")

    @classmethod
    def create(
        cls,
        *,
        consumption_id: str,
        grant: ExecutionGrantV2,
        conformance_witness: ExecutionConformanceWitness,
        clock_witness: ClockWitness,
        live_revocation_epoch: int,
        authority_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "witness_type": GRANT_CONSUMPTION_WITNESS_TYPE,
            "consumption_id": consumption_id,
            "jti": grant.jti,
            "grant_id": grant.grant_id,
            "grant_digest": grant.grant_digest,
            "execution_id": grant.execution_id,
            "authorization_snapshot_digest": grant.authorization_snapshot_digest,
            "execution_capsule_digest": grant.execution_capsule_digest,
            "runner_class": grant.runner_class,
            "conformance_witness_digest": conformance_witness.witness_digest,
            "clock_witness_digest": clock_witness.witness_digest,
            "live_revocation_epoch": live_revocation_epoch,
            "consumed_at": clock_witness.observed_at,
            "serialization_contract": SQLITE_SERIALIZATION_CONTRACT,
            "authority_revision": authority_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "witness_type"}
        }
        return cls(**values, witness_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _WITNESS_FIELDS,
            contract=GRANT_CONSUMPTION_WITNESS_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["witness_type"] != GRANT_CONSUMPTION_WITNESS_TYPE
        ):
            raise ValueError("grant consumption witness schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _WITNESS_FIELDS
                if key not in {"schema_version", "witness_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "witness_type": GRANT_CONSUMPTION_WITNESS_TYPE,
            "consumption_id": self.consumption_id,
            "jti": self.jti,
            "grant_id": self.grant_id,
            "grant_digest": self.grant_digest,
            "execution_id": self.execution_id,
            "authorization_snapshot_digest": self.authorization_snapshot_digest,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
            "conformance_witness_digest": self.conformance_witness_digest,
            "clock_witness_digest": self.clock_witness_digest,
            "live_revocation_epoch": self.live_revocation_epoch,
            "consumed_at": self.consumed_at,
            "serialization_contract": self.serialization_contract,
            "authority_revision": self.authority_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "witness_digest": self.witness_digest}


class GrantConsumptionDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DurableGrantService:
    """Durably issue/store and atomically consume authoritative ExecutionGrant/v2.

    This is an authority-consumption boundary only. It does not dispatch or execute work.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        grant_issuer: Any,
        operational_safety_service: OperationalSafetyService,
        revocation_authority: GrantRevocationEpochAuthority,
        conformance_authority: ExecutionConformanceAuthority,
        trusted_clock: TrustedClockAuthority,
        authority_revision: str,
        id_factory: Any = new_id,
    ) -> None:
        if database.backend_name != "sqlite" or database.write_serialization != "global":
            raise RuntimeError(
                "B4 requires the released SQLite global-write serialization contract"
            )
        if database.schema_version() < MINIMUM_SCHEMA_VERSION:
            raise RuntimeError("B4 requires database schema version 10 or newer")
        self._validate_b4_schema(database)
        if operational_safety_service.db is not database:
            raise ValueError("grant consumption safety service must use its database")
        if not isinstance(revocation_authority, GrantRevocationEpochAuthority):
            raise ValueError("revocation_authority is invalid")
        if not isinstance(conformance_authority, ExecutionConformanceAuthority):
            raise ValueError("conformance_authority is invalid")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock is invalid")
        if not callable(id_factory):
            raise ValueError("id_factory is invalid")
        _require_text(authority_revision, field="authority_revision")

        issue = getattr(grant_issuer, "issue", None)
        if not callable(issue):
            raise ValueError("grant_issuer is invalid")
        if getattr(grant_issuer, "db", None) is not database:
            raise ValueError("grant issuer and B4 must share database")
        if (
            getattr(grant_issuer, "operational_safety_service", None)
            is not operational_safety_service
        ):
            raise ValueError("grant issuer and B4 must share operational safety authority")
        if getattr(grant_issuer, "revocation_authority", None) is not revocation_authority:
            raise ValueError("grant issuer and B4 must share revocation authority")
        if getattr(grant_issuer, "trusted_clock", None) is not trusted_clock:
            raise ValueError("grant issuer and B4 must share trusted clock")
        binding_authority = getattr(grant_issuer, "execution_binding_authority", None)
        if (
            getattr(binding_authority, "registry", None)
            is not conformance_authority.capsule_registry
        ):
            raise ValueError(
                "grant issuer binding authority and B4 conformance must share capsule registry"
            )

        self.db = database
        self.grant_issuer = grant_issuer
        self.operational_safety_service = operational_safety_service
        self.revocation_authority = revocation_authority
        self.conformance_authority = conformance_authority
        self.trusted_clock = trusted_clock
        self.authority_revision = authority_revision
        self._id_factory = id_factory

    @staticmethod
    def _validate_b4_schema(database: ProductDatabaseAdapter) -> None:
        with database.connect() as connection:
            for table, expected in _REQUIRED_TABLE_COLUMNS.items():
                columns = {
                    str(row["name"])
                    for row in connection.execute(_TABLE_INFO_SQL[table]).fetchall()
                }
                if columns != expected:
                    raise RuntimeError(
                        f"B4 schema validation failed for {table}: "
                        f"expected {sorted(expected)}, found {sorted(columns)}"
                    )
            indexes = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }
            missing_indexes = _REQUIRED_INDEXES - indexes
            if missing_indexes:
                raise RuntimeError(
                    f"B4 schema validation failed: missing indexes "
                    f"{sorted(missing_indexes)}"
                )
            triggers = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                ).fetchall()
            }
            missing_triggers = _REQUIRED_TRIGGERS - triggers
            if missing_triggers:
                raise RuntimeError(
                    f"B4 schema validation failed: missing triggers "
                    f"{sorted(missing_triggers)}"
                )

    def issue_and_store(
        self,
        *,
        snapshot: AuthorizationSnapshot,
        authority: AuthorityConstraint,
    ) -> ExecutionGrantV2:
        grant = self.grant_issuer.issue(snapshot=snapshot, authority=authority)
        if not isinstance(grant, ExecutionGrantV2):
            raise RuntimeError("grant issuer returned an invalid grant")

        with self.db.transaction() as connection:
            clock_witness = self._trusted_clock_witness(grant)
            live_epoch = self._assert_live_authority(
                connection,
                grant=grant,
                clock_witness=clock_witness,
            )
            conformance = self._fresh_conformance(grant)
            try:
                connection.execute(
                    INSERT_STORED_GRANT,
                    (
                        grant.jti,
                        grant.grant_id,
                        grant.execution_id,
                        grant.request_id,
                        grant.workspace_id,
                        grant.environment,
                        grant.authorization_snapshot_digest,
                        grant.execution_capsule_digest,
                        grant.grant_digest,
                        canonical_json(grant.to_dict()),
                        conformance.witness_digest,
                        canonical_json(conformance.to_dict()),
                        clock_witness.witness_digest,
                        canonical_json(clock_witness.to_dict()),
                        grant.issued_at,
                        grant.expires_at,
                        live_epoch,
                        clock_witness.observed_at,
                        self.authority_revision,
                    ),
                )
            except DatabaseIntegrityError as exc:
                self._deny("GRANT_STORE_CONFLICT", cause=exc)
        return grant

    def consume(self, *, jti: str) -> GrantConsumptionWitness:
        _require_text(jti, field="jti")

        with self.db.transaction() as connection:
            existing = connection.execute(
                SELECT_CONSUMPTION_BY_JTI,
                (jti,),
            ).fetchone()
            if existing is not None:
                self._deny("GRANT_ALREADY_CONSUMED")

            row = connection.execute(SELECT_STORED_GRANT, (jti,)).fetchone()
            if row is None:
                self._deny("GRANT_NOT_FOUND")
            grant = self._decode_stored_grant(row)

            clock_witness = self._trusted_clock_witness(grant)
            live_epoch = self._assert_live_authority(
                connection,
                grant=grant,
                clock_witness=clock_witness,
            )
            conformance = self._fresh_conformance(grant)
            witness = GrantConsumptionWitness.create(
                consumption_id=self._id_factory("gcon"),
                grant=grant,
                conformance_witness=conformance,
                clock_witness=clock_witness,
                live_revocation_epoch=live_epoch,
                authority_revision=self.authority_revision,
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
                self._deny("GRANT_ALREADY_CONSUMED", cause=exc)

        return witness

    def _decode_stored_grant(self, row: Any) -> ExecutionGrantV2:
        try:
            raw = json.loads(str(row["grant_json"]))
            if not isinstance(raw, dict):
                raise ValueError("stored grant is not an object")
            if canonical_json(raw) != str(row["grant_json"]):
                raise ValueError("stored grant JSON is not canonical")
            grant = ExecutionGrantV2.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            self._deny("STORED_GRANT_CORRUPT", cause=exc)

        expected = (
            grant.jti,
            grant.grant_id,
            grant.execution_id,
            grant.request_id,
            grant.workspace_id,
            grant.environment,
            grant.authorization_snapshot_digest,
            grant.execution_capsule_digest,
            grant.grant_digest,
            grant.issued_at,
            grant.expires_at,
            grant.revocation_epoch,
        )
        actual = (
            str(row["jti"]),
            str(row["grant_id"]),
            str(row["execution_id"]),
            str(row["request_id"]),
            str(row["workspace_id"]),
            str(row["environment"]),
            str(row["authorization_snapshot_digest"]),
            str(row["execution_capsule_digest"]),
            str(row["grant_digest"]),
            str(row["issued_at"]),
            str(row["expires_at"]),
            int(row["revocation_epoch"]),
        )
        if actual != expected:
            self._deny("STORED_GRANT_BINDING_MISMATCH")
        return grant

    def _trusted_clock_witness(self, grant: ExecutionGrantV2) -> ClockWitness:
        try:
            witness = self.trusted_clock.witness(environment=grant.environment)
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            self._deny("TRUSTED_CLOCK_DENIED", cause=exc)
        if witness.source_identity != self.trusted_clock.source_identity:
            self._deny("TRUSTED_CLOCK_BINDING_MISMATCH")
        return witness

    def _assert_live_authority(
        self,
        connection: DatabaseConnection,
        *,
        grant: ExecutionGrantV2,
        clock_witness: ClockWitness,
    ) -> int:
        _, now = _require_timestamp(clock_witness.observed_at, field="consumed_at")
        _, issued = _require_timestamp(grant.issued_at, field="grant.issued_at")
        _, expires = _require_timestamp(grant.expires_at, field="grant.expires_at")
        if now < issued:
            self._deny("CLOCK_PRECEDES_GRANT")
        if now >= expires:
            self._deny("GRANT_EXPIRED")

        if self.operational_safety_service.is_active(connection):
            self._deny("EMERGENCY_STOP_ACTIVE")

        try:
            live_epoch = self.revocation_authority.current_epoch(
                connection,
                workspace_id=grant.workspace_id,
                environment=grant.environment,
                capability_definition_identity=grant.capability_definition_identity,
            )
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            self._deny("REVOCATION_AUTHORITY_DENIED", cause=exc)
        if type(live_epoch) is not int or live_epoch < 0:
            self._deny("REVOCATION_EPOCH_INVALID")
        if live_epoch != grant.revocation_epoch:
            self._deny("REVOCATION_EPOCH_CHANGED")
        return live_epoch

    def _fresh_conformance(
        self,
        grant: ExecutionGrantV2,
    ) -> ExecutionConformanceWitness:
        try:
            witness = self.conformance_authority.evaluate(grant=grant)
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            self._deny("EXECUTION_CONFORMANCE_DENIED", cause=exc)
        if not isinstance(witness, ExecutionConformanceWitness):
            self._deny("EXECUTION_CONFORMANCE_INVALID")
        if witness.grant_digest != grant.grant_digest:
            self._deny("EXECUTION_CONFORMANCE_GRANT_MISMATCH")
        return witness

    @staticmethod
    def _deny(
        reason: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        error = GrantConsumptionDenied(reason)
        if cause is None:
            raise error
        raise error from cause
