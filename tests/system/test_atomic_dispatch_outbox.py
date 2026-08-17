from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

from voodoo_product.authoritative_grant import ExecutionGrantV2
from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.dispatch_outbox import DispatchOutboxEntry
from voodoo_product.dispatch_outbox_persistence import (
    DispatchOutboxPersistenceDenied,
    DurableDispatchOutboxService,
)
from voodoo_product.evidence_primitives import canonical_json, new_id
from voodoo_product.grant_consumption import DurableGrantService, GrantConsumptionDenied
from voodoo_product.persistence import DatabaseIntegrityError

SNAPSHOT_DIGEST = "a" * 64
REVIEW_DIGEST = "b" * 64
CONFORMANCE_DIGEST = "c" * 64
CLOCK_DIGEST = "d" * 64
CONSUMED_AT = "2026-08-17T04:00:10.000+00:00"


@dataclass(frozen=True)
class FakeConformanceWitness:
    witness_digest: str = CONFORMANCE_DIGEST

    def to_dict(self) -> dict[str, object]:
        return {"witness_digest": self.witness_digest}


@dataclass(frozen=True)
class FakeClockWitness:
    witness_digest: str = CLOCK_DIGEST
    observed_at: str = CONSUMED_AT

    def to_dict(self) -> dict[str, object]:
        return {
            "witness_digest": self.witness_digest,
            "observed_at": self.observed_at,
        }


def make_grant() -> ExecutionGrantV2:
    return ExecutionGrantV2._issue(
        grant_id="grt_c1b",
        jti="jti_c1b",
        execution_id="exec_c1b",
        request_id="cr_c1b",
        authorization_snapshot_digest=SNAPSHOT_DIGEST,
        snapshot_authority_witness_set_digest="e" * 64,
        snapshot_authority_event_hash="f" * 64,
        parent_scope_digest="0" * 64,
        authority_constraint_digest="1" * 64,
        monotonic_authority_decision_digest="2" * 64,
        actor_id="usr_admin",
        workspace_id="wrk_main",
        environment="local",
        capability="voodoo.write-artifact/v1",
        capability_definition_identity="3" * 64,
        target_kind="git_ref",
        target_digest="4" * 64,
        payload_digest="5" * 64,
        policy_version="approval-policy/current-v1",
        policy_identity="6" * 64,
        approval_set_digest="7" * 64,
        required_permission="execution.run",
        precondition_requirement_digest="8" * 64,
        precondition_expectation_digest="9" * 64,
        precondition_observation_digest="a" * 64,
        precondition_witness_digest="b" * 64,
        precondition_enforcement_class="READ_THEN_COMPARE",
        precondition_checked_at="2026-08-17T03:59:59.000+00:00",
        execution_binding_digest="c" * 64,
        execution_capsule_digest="d" * 64,
        runner_class="sandcloud.isolated-linux/v1",
        execution_binding_authority_revision="execution-binding/test-r1",
        issued_at="2026-08-17T04:00:00.000+00:00",
        expires_at="2026-08-17T04:05:00.000+00:00",
        revocation_epoch=7,
        use_semantics="ONE_TIME",
        issuer_identity="grant-issuer/test",
        issuer_revision="grant-issuer/test-r1",
    )


def seed_grant(database: SQLiteProductDatabase, grant: ExecutionGrantV2) -> None:
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_admin', 'admin', 'unused', 'administrator', 1,
                    '2026-08-17T03:00:00.000+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES ('wrk_main', 'Main', 'local', '2026-08-17T03:00:00.000+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES (
                'cr_c1b', 'wrk_main', 'C1b', '', 'R1', 'local', 'echo', '{}',
                'DRAFT', 'usr_admin',
                '2026-08-17T03:00:00.000+00:00',
                '2026-08-17T03:00:00.000+00:00'
            )
            """
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'REVIEW_REQUIRED',
                review_content_sha256 = ?,
                updated_at = '2026-08-17T03:01:00.000+00:00'
            WHERE id = 'cr_c1b'
            """,
            (REVIEW_DIGEST,),
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'APPROVED',
                updated_at = '2026-08-17T03:02:00.000+00:00'
            WHERE id = 'cr_c1b'
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
                'authz_c1b', 'exec_c1b', 'cr_c1b', 'usr_admin', 'wrk_main', 'local',
                ?, 'c1b-snapshot-idempotency', ?, ?, '{}', '{}', '{}',
                '2026-08-17T03:03:00.000+00:00'
            )
            """,
            (REVIEW_DIGEST, "e" * 64, SNAPSHOT_DIGEST),
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
                CONFORMANCE_DIGEST,
                canonical_json({"witness_digest": CONFORMANCE_DIGEST}),
                CLOCK_DIGEST,
                canonical_json({"witness_digest": CLOCK_DIGEST}),
                grant.issued_at,
                grant.expires_at,
                grant.revocation_epoch,
                "2026-08-17T04:00:01.000+00:00",
                "durable-grant/test-r1",
            ),
        )


def make_grant_service(
    database: SQLiteProductDatabase,
    grant: ExecutionGrantV2,
) -> DurableGrantService:
    service = object.__new__(DurableGrantService)
    service.db = database
    service.authority_revision = "durable-grant/test-r1"
    service._id_factory = new_id
    service._decode_stored_grant = lambda row: grant
    clock = FakeClockWitness()
    conformance = FakeConformanceWitness()
    service._trusted_clock_witness = lambda resolved_grant: clock
    service._assert_live_authority = (
        lambda connection, *, grant, clock_witness: 7
    )
    service._fresh_conformance = lambda resolved_grant: conformance
    return service


def build_dispatch_service(
    tmp_path: Path,
) -> tuple[
    DurableDispatchOutboxService,
    DurableGrantService,
    SQLiteProductDatabase,
    ExecutionGrantV2,
]:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    grant = make_grant()
    seed_grant(database, grant)
    grant_service = make_grant_service(database, grant)
    dispatch_service = DurableDispatchOutboxService(
        grant_service=grant_service,
        outbox_revision="dispatch-outbox-persistence/test-r1",
    )
    return dispatch_service, grant_service, database, grant


def test_consume_and_enqueue_commits_exact_pair(tmp_path: Path) -> None:
    service, _, database, grant = build_dispatch_service(tmp_path)

    outbox = service.consume_and_enqueue(jti=grant.jti)

    assert outbox.jti == grant.jti
    assert outbox.grant_digest == grant.grant_digest
    assert outbox.execution_id == grant.execution_id
    assert outbox.execution_capsule_digest == grant.execution_capsule_digest
    assert outbox.runner_class == grant.runner_class
    assert DispatchOutboxEntry.from_dict(outbox.to_dict()) == outbox

    with database.connect() as connection:
        consumption = connection.execute(
            "SELECT consumption_id, consumption_digest FROM grant_consumptions_v1 WHERE jti = ?",
            (grant.jti,),
        ).fetchone()
        persisted = connection.execute(
            """
            SELECT consumption_id, consumption_witness_digest, entry_digest, entry_json
            FROM dispatch_outbox_v1 WHERE jti = ?
            """,
            (grant.jti,),
        ).fetchone()
    assert consumption is not None
    assert persisted is not None
    assert persisted["consumption_id"] == consumption["consumption_id"]
    assert persisted["consumption_witness_digest"] == consumption["consumption_digest"]
    assert persisted["entry_digest"] == outbox.entry_digest
    assert canonical_json(outbox.to_dict()) == persisted["entry_json"]


def test_outbox_insert_failure_rolls_back_consumption_and_allows_retry(tmp_path: Path) -> None:
    service, _, database, grant = build_dispatch_service(tmp_path)
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER test_fail_dispatch_outbox_insert
            BEFORE INSERT ON dispatch_outbox_v1
            BEGIN
                SELECT RAISE(ABORT, 'forced C1b rollback');
            END
            """
        )

    with pytest.raises(DispatchOutboxPersistenceDenied) as denied:
        service.consume_and_enqueue(jti=grant.jti)
    assert denied.value.reason == "OUTBOX_PERSISTENCE_CONFLICT"

    with database.connect() as connection:
        consumption_count = connection.execute(
            "SELECT COUNT(*) AS count FROM grant_consumptions_v1"
        ).fetchone()["count"]
        outbox_count = connection.execute(
            "SELECT COUNT(*) AS count FROM dispatch_outbox_v1"
        ).fetchone()["count"]
        connection.execute("DROP TRIGGER test_fail_dispatch_outbox_insert")
    assert consumption_count == 0
    assert outbox_count == 0

    retried = service.consume_and_enqueue(jti=grant.jti)
    assert retried.jti == grant.jti


def test_two_atomic_consumers_have_one_consumption_and_one_outbox(tmp_path: Path) -> None:
    service, _, database, grant = build_dispatch_service(tmp_path)

    def consume(_: int) -> str:
        try:
            service.consume_and_enqueue(jti=grant.jti)
        except GrantConsumptionDenied as exc:
            return exc.reason
        return "ENQUEUED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(consume, range(2)))

    assert sorted(outcomes) == ["ENQUEUED", "GRANT_ALREADY_CONSUMED"]
    with database.connect() as connection:
        consumption_count = connection.execute(
            "SELECT COUNT(*) AS count FROM grant_consumptions_v1"
        ).fetchone()["count"]
        outbox_count = connection.execute(
            "SELECT COUNT(*) AS count FROM dispatch_outbox_v1"
        ).fetchone()["count"]
    assert consumption_count == 1
    assert outbox_count == 1


def test_outbox_intent_is_append_only(tmp_path: Path) -> None:
    service, _, database, grant = build_dispatch_service(tmp_path)
    service.consume_and_enqueue(jti=grant.jti)

    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            "UPDATE dispatch_outbox_v1 SET outbox_revision = 'rewritten' WHERE jti = ?",
            (grant.jti,),
        )
    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            "DELETE FROM dispatch_outbox_v1 WHERE jti = ?",
            (grant.jti,),
        )


def test_b4_only_consumption_is_not_retroactively_dispatch_eligible(tmp_path: Path) -> None:
    _, grant_service, database, grant = build_dispatch_service(tmp_path)
    grant_service.consume(jti=grant.jti)

    with pytest.raises(RuntimeError, match="historical Grant consumption"):
        DurableDispatchOutboxService(
            grant_service=grant_service,
            outbox_revision="dispatch-outbox-persistence/test-r1",
        )

    with database.connect() as connection:
        outbox_count = connection.execute(
            "SELECT COUNT(*) AS count FROM dispatch_outbox_v1"
        ).fetchone()["count"]
    assert outbox_count == 0


def test_unknown_grant_fails_closed(tmp_path: Path) -> None:
    service, _, _, _ = build_dispatch_service(tmp_path)

    with pytest.raises(GrantConsumptionDenied) as denied:
        service.consume_and_enqueue(jti="jti_missing")
    assert denied.value.reason == "GRANT_NOT_FOUND"
