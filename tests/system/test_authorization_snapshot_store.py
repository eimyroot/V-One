from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI

from voodoo_product.approval_policy import CURRENT_APPROVAL_POLICY_VERSION
from voodoo_product.audit import AuditLedger
from voodoo_product.authorization_snapshot import (
    PAYLOAD_DIGEST_SCHEME,
    AuthorizationSnapshot,
)
from voodoo_product.authorization_snapshot_store import (
    AuthorizationSnapshotConflict,
    AuthorizationSnapshotSourceError,
    AuthorizationSnapshotStore,
)
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import (
    ApprovalEvidenceSet,
    ApprovalRecord,
    ExecutionTarget,
)
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.service import ProductService

SOURCE_REVISION = "16d8c8d016b48b43e294de4ebb7577637191a18b"


def product_service(tmp_path) -> ProductService:
    return ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        )
    )


def approved_request(service: ProductService) -> tuple[dict, dict, dict]:
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    operator = service.create_user(
        actor_id=bootstrap["user_id"],
        username="operator",
        password="VeryStrongOperatorPassword1!",
        role="operator",
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Snapshot storage fixture",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"artifact": "proof/result.json"},
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    service.approve_change_request(
        actor_id=operator["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="snapshot storage fixture",
    )
    return bootstrap, operator, service.get_change_request(request["id"])


def build_snapshot(
    service: ProductService,
    *,
    bootstrap: dict,
    operator: dict,
    request: dict,
    snapshot_id: str = "authz_store",
    execution_id: str = "exec_store",
    policy_identity: str | None = None,
    review_content_sha256: str | None = None,
) -> AuthorizationSnapshot:
    payload_digest = hashlib.sha256(
        canonical_json(
            {
                "schema_version": 1,
                "binding_type": PAYLOAD_DIGEST_SCHEME,
                "payload": request["payload"],
            }
        ).encode("utf-8")
    ).hexdigest()
    target = ExecutionTarget.create(
        target_kind="artifact_path",
        target_claims={"path": "proof/result.json", "replace": False},
    )
    with service.db.connect() as connection:
        approval = connection.execute(
            """
            SELECT id, approver_id, decision, created_at
            FROM approvals
            WHERE request_id = ?
            """,
            (request["id"],),
        ).fetchone()
    assert approval is not None
    approved_at = datetime.fromisoformat(str(approval["created_at"]))
    authorized_at = (approved_at + timedelta(seconds=1)).isoformat(timespec="milliseconds")
    valid_until = (approved_at + timedelta(minutes=10)).isoformat(timespec="milliseconds")
    approval_evidence = ApprovalEvidenceSet.create(
        request_id=request["id"],
        payload_digest=payload_digest,
        target_digest=target.target_digest,
        capability="voodoo.validate/v1",
        policy_version="approval-policy.test-v1",
        approvals=(
            ApprovalRecord(
                approval_id=str(approval["id"]),
                approver_id=str(approval["approver_id"]),
                decision=str(approval["decision"]),
                approved_at=str(approval["created_at"]),
            ),
        ),
        approval_valid_until=valid_until,
    )
    return AuthorizationSnapshot.create(
        snapshot_id=snapshot_id,
        execution_id=execution_id,
        request_id=request["id"],
        review_content_sha256=(
            review_content_sha256 or str(request["review_content_sha256"])
        ),
        actor_id=operator["id"],
        workspace_id=bootstrap["workspace_id"],
        environment="local",
        capability=approval_evidence.capability,
        capability_definition_identity=hashlib.sha256(
            b"test-capability-definition"
        ).hexdigest(),
        payload_digest=payload_digest,
        payload_digest_scheme=PAYLOAD_DIGEST_SCHEME,
        execution_target_identity=target.target_digest,
        policy_version=approval_evidence.policy_version,
        policy_identity=(
            policy_identity
            or hashlib.sha256(b"test-immutable-approval-policy").hexdigest()
        ),
        approval_evidence_identity=approval_evidence.approval_set_digest,
        issuance_timestamp_source_identity="server-clock-policy.test-v1",
        authorized_at=authorized_at,
        authorization_source_revision=SOURCE_REVISION,
        execution_target=target,
        approval_evidence=approval_evidence,
    )


def store(service: ProductService) -> AuthorizationSnapshotStore:
    return AuthorizationSnapshotStore(
        database=service.db,
        audit_ledger=AuditLedger(service.db),
        clock=lambda: "2026-08-12T12:20:00.000+00:00",
    )


def test_store_persists_exact_snapshot_and_child_bytes_with_bounded_audit(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
    )

    persisted = store(service).persist_prevalidated(
        snapshot=snapshot,
        idempotency_key="snapshot-store-key",
        correlation_id="corr_snapshot_store",
    )

    assert persisted == snapshot
    loaded = store(service).get(snapshot.snapshot_id)
    assert loaded == snapshot
    assert loaded.execution_target_json == snapshot.execution_target_json
    assert loaded.approval_evidence_json == snapshot.approval_evidence_json

    events = service.list_audit_events()
    event = next(item for item in events if item["action"] == "authorization_snapshot.create")
    assert event["target_id"] == snapshot.snapshot_id
    assert event["payload"]["snapshot_digest"] == snapshot.snapshot_digest
    assert event["payload"]["review_content_sha256"] == snapshot.review_content_sha256
    assert event["payload"]["correlation_id"] == "corr_snapshot_store"
    assert "payload" not in event["payload"]
    assert "target_claims" not in event["payload"]


def test_store_idempotency_returns_original_snapshot_for_same_authorization_inputs(
    tmp_path,
) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    first = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
    )
    retry = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
        snapshot_id="authz_retry",
        execution_id="exec_retry",
    )
    storage = store(service)

    original = storage.persist_prevalidated(
        snapshot=first,
        idempotency_key="same-inputs",
        correlation_id="corr_first",
    )
    returned = storage.persist_prevalidated(
        snapshot=retry,
        idempotency_key="same-inputs",
        correlation_id="corr_retry",
    )

    assert returned == original
    with service.db.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM authorization_snapshots"
        ).fetchone()["count"]
    assert count == 1
    events = [
        item
        for item in service.list_audit_events()
        if item["action"] == "authorization_snapshot.create"
    ]
    assert len(events) == 1


def test_store_idempotency_conflicts_when_authorization_inputs_change(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    first = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
    )
    changed = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
        snapshot_id="authz_changed",
        execution_id="exec_changed",
        policy_identity="f" * 64,
    )
    storage = store(service)
    storage.persist_prevalidated(
        snapshot=first,
        idempotency_key="content-bound",
        correlation_id="corr_first",
    )

    with pytest.raises(AuthorizationSnapshotConflict, match="different authorization inputs"):
        storage.persist_prevalidated(
            snapshot=changed,
            idempotency_key="content-bound",
            correlation_id="corr_changed",
        )


def test_store_fails_closed_when_current_request_binding_does_not_match(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
        review_content_sha256="f" * 64,
    )

    with pytest.raises(AuthorizationSnapshotSourceError, match="bindings mismatch"):
        store(service).persist_prevalidated(
            snapshot=snapshot,
            idempotency_key="mismatched-review",
            correlation_id="corr_mismatch",
        )


def test_store_fails_closed_when_request_is_not_approved(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, _ = approved_request(service)
    draft = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Pending snapshot",
        description="",
        risk="R1",
        environment="local",
        adapter="echo",
        payload={"artifact": "proof/pending.json"},
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=draft["id"],
    )
    pending = service.get_change_request(draft["id"])
    payload_digest = hashlib.sha256(
        canonical_json(
            {
                "schema_version": 1,
                "binding_type": PAYLOAD_DIGEST_SCHEME,
                "payload": pending["payload"],
            }
        ).encode("utf-8")
    ).hexdigest()
    target = ExecutionTarget.create(
        target_kind="artifact_path",
        target_claims={"path": "proof/pending.json", "replace": False},
    )
    evidence = ApprovalEvidenceSet.create(
        request_id=pending["id"],
        payload_digest=payload_digest,
        target_digest=target.target_digest,
        capability="voodoo.validate/v1",
        policy_version="approval-policy.test-v1",
        approvals=(
            ApprovalRecord(
                approval_id="appr_unpersisted_fixture",
                approver_id=operator["id"],
                decision="APPROVED",
                approved_at="2026-08-12T12:00:00.000+00:00",
            ),
        ),
        approval_valid_until="2026-08-12T12:10:00.000+00:00",
    )
    snapshot = AuthorizationSnapshot.create(
        snapshot_id="authz_pending",
        execution_id="exec_pending",
        request_id=pending["id"],
        review_content_sha256=str(pending["review_content_sha256"]),
        actor_id=operator["id"],
        workspace_id=bootstrap["workspace_id"],
        environment="local",
        capability=evidence.capability,
        capability_definition_identity="c" * 64,
        payload_digest=payload_digest,
        payload_digest_scheme=PAYLOAD_DIGEST_SCHEME,
        execution_target_identity=target.target_digest,
        policy_version=evidence.policy_version,
        policy_identity="d" * 64,
        approval_evidence_identity=evidence.approval_set_digest,
        issuance_timestamp_source_identity="server-clock-policy.test-v1",
        authorized_at="2026-08-12T12:05:00.000+00:00",
        authorization_source_revision=SOURCE_REVISION,
        execution_target=target,
        approval_evidence=evidence,
    )

    with pytest.raises(AuthorizationSnapshotSourceError, match="not in an approved"):
        store(service).persist_prevalidated(
            snapshot=snapshot,
            idempotency_key="pending-request",
            correlation_id="corr_pending",
        )


def test_database_triggers_make_snapshot_rows_immutable(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
    )
    store(service).persist_prevalidated(
        snapshot=snapshot,
        idempotency_key="immutable-row",
        correlation_id="corr_immutable",
    )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "UPDATE authorization_snapshots SET environment = 'staging' WHERE id = ?",
            (snapshot.snapshot_id,),
        )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "DELETE FROM authorization_snapshots WHERE id = ?",
            (snapshot.snapshot_id,),
        )


def test_storage_boundary_does_not_reuse_mutable_current_policy_as_authority(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
    )

    assert snapshot.policy_version != CURRENT_APPROVAL_POLICY_VERSION
    assert "CURRENT_COMPATIBILITY" not in snapshot.policy_identity
    assert store(service).get_by_idempotency_key("missing") is None


def test_snapshot_and_audit_are_atomic_when_audit_append_fails(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
    )

    class FailingAuditLedger(AuditLedger):
        def append(self, *args, **kwargs):
            raise RuntimeError("forced audit failure")

    storage = AuthorizationSnapshotStore(
        database=service.db,
        audit_ledger=FailingAuditLedger(service.db),
        clock=lambda: "2026-08-12T12:20:00.000+00:00",
    )
    with pytest.raises(RuntimeError, match="forced audit failure"):
        storage.persist_prevalidated(
            snapshot=snapshot,
            idempotency_key="atomic-audit",
            correlation_id="corr_atomic",
        )

    with service.db.connect() as connection:
        row = connection.execute(
            "SELECT id FROM authorization_snapshots WHERE id = ?",
            (snapshot.snapshot_id,),
        ).fetchone()
    assert row is None


def test_snapshot_storage_is_not_composed_into_product_runtime(tmp_path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        ),
        repository_root=tmp_path,
    )

    assert not hasattr(composition, "authorization_snapshot_store")
    assert not hasattr(app.state, "voodoo_authorization_snapshot_store")
    assert all(
        "authorization-snapshot" not in getattr(route, "path", "")
        for route in app.routes
    )
