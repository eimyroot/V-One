from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.dispatch_envelope import DispatchEnvelope
from voodoo_product.dispatch_inbox import (
    DUPLICATE_REDELIVERY,
    DispatchInboxContentConflict,
)
from voodoo_product.dispatch_inbox_persistence import (
    ADMITTED,
    DispatchInboxPersistenceDenied,
    DurableDispatchInboxService,
)
from voodoo_product.dispatch_outbox import DispatchOutboxEntry
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.persistence import DatabaseIntegrityError

REVIEW_DIGEST = "8" * 64
SNAPSHOT_DIGEST = "d" * 64
CONSUMPTION_DIGEST = "a" * 64
GRANT_DIGEST = "b" * 64
CAPSULE_DIGEST = "f" * 64


def digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_outbox(
    *,
    outbox_id: str = "out_c3b",
    consumption_id: str = "gcon_c3b",
    jti: str = "jti_c3b",
    grant_id: str = "grt_c3b",
    execution_id: str = "exec_c3b",
    target_digest: str = "1" * 64,
    payload_digest: str = "2" * 64,
) -> DispatchOutboxEntry:
    claims: dict[str, object] = {
        "schema_version": 1,
        "entry_type": "dispatch-outbox-entry/v1",
        "outbox_id": outbox_id,
        "consumption_id": consumption_id,
        "consumption_witness_digest": CONSUMPTION_DIGEST,
        "jti": jti,
        "grant_id": grant_id,
        "grant_digest": GRANT_DIGEST,
        "execution_id": execution_id,
        "request_id": "cr_c3b",
        "actor_id": "usr_admin",
        "workspace_id": "wrk_main",
        "environment": "local",
        "capability": "voodoo.write-artifact/v1",
        "capability_definition_identity": "c" * 64,
        "authorization_snapshot_digest": SNAPSHOT_DIGEST,
        "target_kind": "git_ref",
        "target_digest": target_digest,
        "payload_digest": payload_digest,
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


def seed_durable_outbox(
    database: SQLiteProductDatabase,
    outbox: DispatchOutboxEntry,
) -> None:
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
                'cr_c3b', 'wrk_main', 'C3b', '', 'R1', 'local', 'echo', '{}',
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
            WHERE id = 'cr_c3b'
            """,
            (REVIEW_DIGEST,),
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'APPROVED',
                updated_at = '2026-08-17T05:02:00.000+00:00'
            WHERE id = 'cr_c3b'
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
                'authz_c3b', ?, 'cr_c3b', 'usr_admin', 'wrk_main', 'local',
                ?, 'c3b-snapshot-idempotency', ?, ?, '{"seed":1}', '{"seed":1}',
                '{"seed":1}', '2026-08-17T05:03:00.000+00:00'
            )
            """,
            (outbox.execution_id, REVIEW_DIGEST, "9" * 64, SNAPSHOT_DIGEST),
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
            ) VALUES (?, ?, ?, 'cr_c3b', 'wrk_main', 'local', ?, ?, ?,
                      '{"seed":"grant"}', ?, '{"seed":"conformance"}', ?,
                      '{"seed":"clock"}', ?, ?, 7, ?, 'durable-grant/test-r1')
            """,
            (
                outbox.jti,
                outbox.grant_id,
                outbox.execution_id,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{"seed":"conformance"}', ?,
                      '{"seed":"clock"}', 7, ?, 'sqlite-begin-immediate/v1',
                      'durable-grant/test-r1', ?, '{"seed":"consumption"}')
            """,
            (
                outbox.consumption_id,
                outbox.jti,
                outbox.grant_digest,
                outbox.execution_id,
                outbox.authorization_snapshot_digest,
                outbox.execution_capsule_digest,
                outbox.runner_class,
                "3" * 64,
                "4" * 64,
                outbox.created_at,
                outbox.consumption_witness_digest,
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


def build_service(
    tmp_path: Path,
) -> tuple[DurableDispatchInboxService, SQLiteProductDatabase, DispatchOutboxEntry]:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    outbox = make_outbox()
    seed_durable_outbox(database, outbox)
    service = DurableDispatchInboxService(
        database=database,
        admission_revision="dispatch-inbox-persistence/c3b-r1",
    )
    return service, database, outbox


def test_first_delivery_persists_one_exact_admission(tmp_path: Path) -> None:
    service, database, outbox = build_service(tmp_path)
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )

    result = service.admit(envelope=envelope)

    assert result.outcome == ADMITTED
    result.admission.assert_bound_to(envelope=envelope, outbox_entry=outbox)
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT dispatch_id, envelope_digest, outbox_id, outbox_entry_digest,
                   admission_digest, admission_json
            FROM dispatch_inbox_v1
            WHERE dispatch_id = ?
            """,
            (envelope.dispatch_id,),
        ).fetchone()
    assert row is not None
    assert row["envelope_digest"] == envelope.envelope_digest
    assert row["outbox_id"] == outbox.outbox_id
    assert row["outbox_entry_digest"] == outbox.entry_digest
    assert row["admission_digest"] == result.admission.admission_digest
    assert row["admission_json"] == canonical_json(result.admission.to_dict())


def test_exact_redelivery_is_durable_duplicate_without_second_row(tmp_path: Path) -> None:
    service, database, outbox = build_service(tmp_path)
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )

    first = service.admit(envelope=envelope)
    duplicate = service.admit(envelope=envelope)

    assert first.outcome == ADMITTED
    assert duplicate.outcome == DUPLICATE_REDELIVERY
    assert duplicate.admission == first.admission
    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM dispatch_inbox_v1"
        ).fetchone()["count"]
    assert count == 1


def test_same_dispatch_id_with_conflicting_content_fails_closed(tmp_path: Path) -> None:
    service, database, outbox = build_service(tmp_path)
    accepted = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )
    conflicting = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r2",
    )
    assert conflicting.dispatch_id == accepted.dispatch_id
    assert conflicting.envelope_digest != accepted.envelope_digest

    service.admit(envelope=accepted)
    with pytest.raises(DispatchInboxContentConflict) as denied:
        service.admit(envelope=conflicting)
    assert denied.value.reason == "DISPATCH_CONTENT_CONFLICT"

    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM dispatch_inbox_v1"
        ).fetchone()["count"]
    assert count == 1


def test_two_concurrent_deliveries_have_one_admission_and_one_duplicate(tmp_path: Path) -> None:
    service, database, outbox = build_service(tmp_path)
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )

    def admit(_: int) -> str:
        return service.admit(envelope=envelope).outcome

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(admit, range(2)))

    assert sorted(outcomes) == [ADMITTED, DUPLICATE_REDELIVERY]
    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM dispatch_inbox_v1"
        ).fetchone()["count"]
    assert count == 1


def test_service_resolves_durable_outbox_instead_of_trusting_envelope(tmp_path: Path) -> None:
    service, _, outbox = build_service(tmp_path)
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )
    tampered = envelope.to_dict()
    tampered["target_digest"] = "9" * 64
    tampered["envelope_digest"] = digest(
        {key: value for key, value in tampered.items() if key != "envelope_digest"}
    )
    structurally_valid = DispatchEnvelope.from_dict(tampered)

    with pytest.raises(DispatchInboxPersistenceDenied) as denied:
        service.admit(envelope=structurally_valid)
    assert denied.value.reason == "OUTBOX_BINDING_MISMATCH"


def test_missing_durable_outbox_is_denied(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    missing = make_outbox(
        outbox_id="out_missing",
        consumption_id="gcon_missing",
        jti="jti_missing",
        grant_id="grt_missing",
        execution_id="exec_missing",
        target_digest="9" * 64,
    )
    envelope = DispatchEnvelope.create(
        outbox_entry=missing,
        envelope_revision="dispatch-envelope/c2-r1",
    )

    with pytest.raises(DispatchInboxPersistenceDenied) as denied:
        service.admit(envelope=envelope)
    assert denied.value.reason == "OUTBOX_NOT_FOUND"


def test_durable_inbox_is_append_only(tmp_path: Path) -> None:
    service, database, outbox = build_service(tmp_path)
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )
    service.admit(envelope=envelope)

    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            "UPDATE dispatch_inbox_v1 SET admission_revision = 'rewritten'"
        )
    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute("DELETE FROM dispatch_inbox_v1")


def test_c3b_does_not_wire_runtime_or_create_execution_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "voodoo_product/service.py",
        "voodoo_product/execution.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "dispatch_inbox_persistence" not in source
        assert "DurableDispatchInboxService" not in source
