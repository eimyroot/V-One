from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.dispatch_envelope import DispatchEnvelope
from voodoo_product.dispatch_inbox import DispatchInboxAdmission
from voodoo_product.dispatch_outbox import DispatchOutboxEntry
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_lease import ExecutionFenceDenied
from voodoo_product.execution_lease_persistence import (
    COMPLETED,
    DUPLICATE_COMPLETION,
    LEASE_ACQUIRED,
    LEASE_REACQUIRED,
    DurableCompletionConflict,
    DurableExecutionLeaseDenied,
    DurableExecutionLeaseService,
)
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.trusted_clock import TrustedClockAuthority

REVIEW_DIGEST = "8" * 64
SNAPSHOT_DIGEST = "d" * 64
CONSUMPTION_DIGEST = "a" * 64
GRANT_DIGEST = "b" * 64
CAPSULE_DIGEST = "f" * 64


def digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class MutableClock:
    def __init__(self, value: str) -> None:
        self.value = datetime.fromisoformat(value).astimezone(UTC)

    def read(self) -> datetime:
        return self.value

    def set(self, value: str) -> None:
        self.value = datetime.fromisoformat(value).astimezone(UTC)


def make_outbox() -> DispatchOutboxEntry:
    claims: dict[str, object] = {
        "schema_version": 1,
        "entry_type": "dispatch-outbox-entry/v1",
        "outbox_id": "out_c4b",
        "consumption_id": "gcon_c4b",
        "consumption_witness_digest": CONSUMPTION_DIGEST,
        "jti": "jti_c4b",
        "grant_id": "grt_c4b",
        "grant_digest": GRANT_DIGEST,
        "execution_id": "exec_c4b",
        "request_id": "cr_c4b",
        "actor_id": "usr_admin",
        "workspace_id": "wrk_main",
        "environment": "local",
        "capability": "voodoo.write-artifact/v1",
        "capability_definition_identity": "c" * 64,
        "authorization_snapshot_digest": SNAPSHOT_DIGEST,
        "target_kind": "git_ref",
        "target_digest": "1" * 64,
        "payload_digest": "2" * 64,
        "required_permission": "execution.run",
        "execution_binding_digest": "e" * 64,
        "execution_capsule_digest": CAPSULE_DIGEST,
        "runner_class": "sandcloud.isolated-linux/v1",
        "precondition_enforcement_class": "READ_THEN_COMPARE",
        "use_semantics": "ONE_TIME",
        "created_at": "2026-08-17T05:20:00.000+00:00",
        "outbox_revision": "dispatch-outbox/c1b-r1",
    }
    claims["entry_digest"] = digest(claims)
    return DispatchOutboxEntry.from_dict(claims)


def seed_durable_admission(database: SQLiteProductDatabase) -> DispatchInboxAdmission:
    outbox = make_outbox()
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )
    admission = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_admin', 'admin', 'unused', 'administrator', 1,
                    '2026-08-17T05:00:00.000+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES ('wrk_main', 'Main', 'local', '2026-08-17T05:00:00.000+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES (
                'cr_c4b', 'wrk_main', 'C4b', '', 'R1', 'local', 'echo', '{}',
                'DRAFT', 'usr_admin',
                '2026-08-17T05:00:00.000+00:00',
                '2026-08-17T05:00:00.000+00:00'
            )
            """
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'REVIEW_REQUIRED',
                review_content_sha256 = ?,
                updated_at = '2026-08-17T05:01:00.000+00:00'
            WHERE id = 'cr_c4b'
            """,
            (REVIEW_DIGEST,),
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'APPROVED',
                updated_at = '2026-08-17T05:02:00.000+00:00'
            WHERE id = 'cr_c4b'
            """
        )
        connection.execute(
            """
            INSERT INTO authorization_snapshots(
                id, execution_id, request_id, actor_id, workspace_id, environment,
                review_content_sha256, idempotency_key, idempotency_binding_digest,
                snapshot_digest, snapshot_json, execution_target_json,
                approval_evidence_json, created_at
            ) VALUES (
                'authz_c4b', 'exec_c4b', 'cr_c4b', 'usr_admin', 'wrk_main', 'local',
                ?, 'c4b-snapshot-idempotency', ?, ?, '{"seed":1}', '{"seed":1}',
                '{"seed":1}', '2026-08-17T05:03:00.000+00:00'
            )
            """,
            (REVIEW_DIGEST, "9" * 64, SNAPSHOT_DIGEST),
        )
        connection.execute(
            """
            INSERT INTO execution_grants_v2(
                jti, grant_id, execution_id, request_id, workspace_id, environment,
                authorization_snapshot_digest, execution_capsule_digest, grant_digest,
                grant_json, issuance_conformance_witness_digest,
                issuance_conformance_witness_json, store_clock_witness_digest,
                store_clock_witness_json, issued_at, expires_at, revocation_epoch,
                stored_at, store_revision
            ) VALUES (
                'jti_c4b', 'grt_c4b', 'exec_c4b', 'cr_c4b', 'wrk_main', 'local',
                ?, ?, ?, '{"seed":"grant"}', ?, '{"seed":"conformance"}', ?,
                '{"seed":"clock"}', ?, ?, 7, ?, 'durable-grant/test-r1'
            )
            """,
            (
                SNAPSHOT_DIGEST,
                CAPSULE_DIGEST,
                GRANT_DIGEST,
                "3" * 64,
                "4" * 64,
                "2026-08-17T05:10:00.000+00:00",
                "2026-08-17T05:30:00.000+00:00",
                "2026-08-17T05:10:01.000+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO grant_consumptions_v1(
                consumption_id, jti, grant_digest, execution_id,
                authorization_snapshot_digest, execution_capsule_digest, runner_class,
                conformance_witness_digest, conformance_witness_json,
                clock_witness_digest, clock_witness_json, live_revocation_epoch,
                consumed_at, serialization_contract, authority_revision,
                consumption_digest, consumption_json
            ) VALUES (
                'gcon_c4b', 'jti_c4b', ?, 'exec_c4b', ?, ?, ?, ?,
                '{"seed":"conformance"}', ?, '{"seed":"clock"}', 7, ?,
                'sqlite-begin-immediate/v1', 'durable-grant/test-r1', ?,
                '{"seed":"consumption"}'
            )
            """,
            (
                GRANT_DIGEST,
                SNAPSHOT_DIGEST,
                CAPSULE_DIGEST,
                outbox.runner_class,
                "3" * 64,
                "4" * 64,
                outbox.created_at,
                CONSUMPTION_DIGEST,
            ),
        )
        connection.execute(
            """
            INSERT INTO dispatch_outbox_v1(
                outbox_id, consumption_id, consumption_witness_digest, jti, grant_id,
                grant_digest, execution_id, request_id, actor_id, workspace_id,
                environment, capability, capability_definition_identity,
                authorization_snapshot_digest, target_kind, target_digest,
                payload_digest, required_permission, execution_binding_digest,
                execution_capsule_digest, runner_class, precondition_enforcement_class,
                use_semantics, created_at, outbox_revision, entry_digest, entry_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?)
            """,
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
        connection.execute(
            """
            INSERT INTO dispatch_inbox_v1(
                admission_id, dispatch_id, envelope_digest, outbox_id,
                outbox_entry_digest, execution_id, workspace_id, environment,
                execution_capsule_digest, runner_class, admission_revision,
                admission_digest, admission_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
    return admission


def build_service(
    tmp_path: Path,
) -> tuple[DurableExecutionLeaseService, SQLiteProductDatabase, DispatchInboxAdmission, MutableClock]:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    admission = seed_durable_admission(database)
    clock = MutableClock("2026-08-17T05:30:00.000+00:00")
    authority = TrustedClockAuthority(
        source_identity="trusted-clock/c4b-test",
        authority_revision="trusted-clock/c4b-test-r1",
        source=clock,
        allowed_environments=frozenset({"local"}),
    )
    service = DurableExecutionLeaseService(
        database=database,
        trusted_clock=authority,
        lease_seconds=60,
        lease_revision="execution-lease/c4b-r1",
        authority_revision="execution-epoch-authority/c4b-r1",
    )
    return service, database, admission, clock


def test_fresh_database_contains_c4b_schema(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()

    assert database.schema_version() == 14
    with database.connect() as connection:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"execution_leases_v1", "execution_epoch_state_v1"}.issubset(tables)


def test_first_acquire_persists_epoch_one_and_current_state(tmp_path: Path) -> None:
    service, database, admission, _ = build_service(tmp_path)

    result = service.acquire(admission_id=admission.admission_id)

    assert result.outcome == LEASE_ACQUIRED
    assert result.lease.execution_epoch == 1
    with database.connect() as connection:
        lease_count = connection.execute(
            "SELECT COUNT(*) AS count FROM execution_leases_v1"
        ).fetchone()["count"]
        state = connection.execute(
            """
            SELECT current_epoch, current_lease_id, current_lease_digest, status
            FROM execution_epoch_state_v1 WHERE admission_id = ?
            """,
            (admission.admission_id,),
        ).fetchone()
    assert lease_count == 1
    assert tuple(state) == (
        1,
        result.lease.lease_id,
        result.lease.lease_digest,
        "ACTIVE",
    )


def test_unexpired_current_lease_blocks_reacquire(tmp_path: Path) -> None:
    service, database, admission, clock = build_service(tmp_path)
    first = service.acquire(admission_id=admission.admission_id)
    clock.set("2026-08-17T05:30:59.999+00:00")

    with pytest.raises(DurableExecutionLeaseDenied) as denied:
        service.acquire(admission_id=admission.admission_id)
    assert denied.value.reason == "LEASE_STILL_ACTIVE"
    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM execution_leases_v1"
        ).fetchone()["count"]
    assert count == 1
    assert first.lease.execution_epoch == 1


def test_expired_lease_reacquires_next_epoch_and_fences_stale_completion(
    tmp_path: Path,
) -> None:
    service, _, admission, clock = build_service(tmp_path)
    first = service.acquire(admission_id=admission.admission_id)
    clock.set("2026-08-17T05:31:00.000+00:00")

    second = service.acquire(admission_id=admission.admission_id)

    assert second.outcome == LEASE_REACQUIRED
    assert second.lease.execution_epoch == 2
    with pytest.raises(ExecutionFenceDenied) as denied:
        service.complete(lease_id=first.lease.lease_id, completion_digest="6" * 64)
    assert denied.value.reason == "STALE_EXECUTION_EPOCH"

    clock.set("2026-08-17T05:31:30.000+00:00")
    completed = service.complete(
        lease_id=second.lease.lease_id,
        completion_digest="7" * 64,
    )
    assert completed.outcome == COMPLETED


def test_concurrent_reacquire_allocates_exactly_one_successor_epoch(tmp_path: Path) -> None:
    service, database, admission, clock = build_service(tmp_path)
    service.acquire(admission_id=admission.admission_id)
    clock.set("2026-08-17T05:31:00.000+00:00")

    def acquire(_: int) -> str:
        try:
            return service.acquire(admission_id=admission.admission_id).outcome
        except DurableExecutionLeaseDenied as exc:
            return exc.reason

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(acquire, range(2)))

    assert sorted(outcomes) == sorted([LEASE_REACQUIRED, "LEASE_STILL_ACTIVE"])
    with database.connect() as connection:
        state = connection.execute(
            "SELECT current_epoch FROM execution_epoch_state_v1 WHERE admission_id = ?",
            (admission.admission_id,),
        ).fetchone()
        lease_count = connection.execute(
            "SELECT COUNT(*) AS count FROM execution_leases_v1"
        ).fetchone()["count"]
    assert state["current_epoch"] == 2
    assert lease_count == 2


def test_completion_is_atomic_idempotent_and_conflict_detecting(tmp_path: Path) -> None:
    service, _, admission, clock = build_service(tmp_path)
    lease = service.acquire(admission_id=admission.admission_id).lease
    clock.set("2026-08-17T05:30:30.000+00:00")

    first = service.complete(lease_id=lease.lease_id, completion_digest="6" * 64)
    duplicate = service.complete(lease_id=lease.lease_id, completion_digest="6" * 64)

    assert first.outcome == COMPLETED
    assert duplicate.outcome == DUPLICATE_COMPLETION
    with pytest.raises(DurableCompletionConflict) as denied:
        service.complete(lease_id=lease.lease_id, completion_digest="7" * 64)
    assert denied.value.reason == "COMPLETION_DIGEST_CONFLICT"

    with pytest.raises(DurableExecutionLeaseDenied) as reacquire_denied:
        service.acquire(admission_id=admission.admission_id)
    assert reacquire_denied.value.reason == "EXECUTION_ALREADY_COMPLETED"


def test_concurrent_conflicting_completions_have_one_durable_winner(tmp_path: Path) -> None:
    service, database, admission, clock = build_service(tmp_path)
    lease = service.acquire(admission_id=admission.admission_id).lease
    clock.set("2026-08-17T05:30:30.000+00:00")

    def complete(value: str) -> str:
        try:
            return service.complete(
                lease_id=lease.lease_id,
                completion_digest=value,
            ).outcome
        except DurableCompletionConflict as exc:
            return exc.reason

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(complete, ["6" * 64, "7" * 64]))

    assert COMPLETED in outcomes
    assert "COMPLETION_DIGEST_CONFLICT" in outcomes
    with database.connect() as connection:
        state = connection.execute(
            """
            SELECT status, completion_digest
            FROM execution_epoch_state_v1 WHERE admission_id = ?
            """,
            (admission.admission_id,),
        ).fetchone()
    assert state["status"] == "COMPLETED"
    assert state["completion_digest"] in {"6" * 64, "7" * 64}


def test_lease_history_and_epoch_state_reject_direct_mutation(tmp_path: Path) -> None:
    service, database, admission, _ = build_service(tmp_path)
    lease = service.acquire(admission_id=admission.admission_id).lease

    with pytest.raises(DatabaseIntegrityError), database.transaction() as connection:
        connection.execute(
            "UPDATE execution_leases_v1 SET execution_epoch = 99 WHERE lease_id = ?",
            (lease.lease_id,),
        )

    with pytest.raises(DatabaseIntegrityError), database.transaction() as connection:
        connection.execute(
            """
            UPDATE execution_epoch_state_v1
            SET current_epoch = current_epoch + 1, updated_at = '2026-08-17T05:30:10.000+00:00'
            WHERE admission_id = ?
            """,
            (admission.admission_id,),
        )
