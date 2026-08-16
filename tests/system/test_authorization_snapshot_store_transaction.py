from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import pytest

from voodoo_product.audit import AuditLedger
from voodoo_product.authorization_snapshot import (
    PAYLOAD_DIGEST_SCHEME,
    AuthorizationSnapshot,
)
from voodoo_product.authorization_snapshot_store import AuthorizationSnapshotStore
from voodoo_product.config import ProductConfig
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import (
    ApprovalEvidenceSet,
    ApprovalRecord,
    ExecutionTarget,
)
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
        title="Transaction-aware snapshot storage fixture",
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
        reason="transaction-aware snapshot storage fixture",
    )
    return bootstrap, operator, service.get_change_request(request["id"])


def build_snapshot(
    service: ProductService,
    *,
    bootstrap: dict,
    operator: dict,
    request: dict,
    snapshot_id: str = "authz_outer_tx",
    execution_id: str = "exec_outer_tx",
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
        review_content_sha256=str(request["review_content_sha256"]),
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
        policy_identity=hashlib.sha256(b"test-immutable-approval-policy").hexdigest(),
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
        clock=lambda: "2026-08-16T19:50:00.000+00:00",
    )


def snapshot_create_events(service: ProductService, snapshot_id: str) -> list[dict]:
    return [
        event
        for event in service.list_audit_events()
        if event["action"] == "authorization_snapshot.create"
        and event["target_id"] == snapshot_id
    ]


def test_on_connection_persists_snapshot_and_audit_on_outer_commit(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
    )
    storage = store(service)

    with service.db.transaction() as connection:
        persisted = storage.persist_prevalidated_on_connection(
            connection,
            snapshot=snapshot,
            idempotency_key="outer-commit",
            correlation_id="corr_outer_commit",
        )
        assert persisted == snapshot
        row = connection.execute(
            "SELECT id FROM authorization_snapshots WHERE id = ?",
            (snapshot.snapshot_id,),
        ).fetchone()
        assert row is not None

    assert storage.get(snapshot.snapshot_id) == snapshot
    events = snapshot_create_events(service, snapshot.snapshot_id)
    assert len(events) == 1
    assert events[0]["payload"]["correlation_id"] == "corr_outer_commit"


def test_on_connection_does_not_commit_independently_and_outer_failure_rolls_back(
    tmp_path,
) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
        snapshot_id="authz_outer_rollback",
        execution_id="exec_outer_rollback",
    )
    storage = store(service)

    with pytest.raises(RuntimeError, match="forced outer transaction failure"):
        with service.db.transaction() as connection:
            storage.persist_prevalidated_on_connection(
                connection,
                snapshot=snapshot,
                idempotency_key="outer-rollback",
                correlation_id="corr_outer_rollback",
            )
            row = connection.execute(
                "SELECT id FROM authorization_snapshots WHERE id = ?",
                (snapshot.snapshot_id,),
            ).fetchone()
            assert row is not None
            raise RuntimeError("forced outer transaction failure")

    assert storage.get_by_idempotency_key("outer-rollback") is None
    assert snapshot_create_events(service, snapshot.snapshot_id) == []


def test_persist_prevalidated_wrapper_remains_backward_compatible(tmp_path) -> None:
    service = product_service(tmp_path)
    bootstrap, operator, request = approved_request(service)
    snapshot = build_snapshot(
        service,
        bootstrap=bootstrap,
        operator=operator,
        request=request,
        snapshot_id="authz_wrapper",
        execution_id="exec_wrapper",
    )
    storage = store(service)

    persisted = storage.persist_prevalidated(
        snapshot=snapshot,
        idempotency_key="wrapper-compat",
        correlation_id="corr_wrapper",
    )

    assert persisted == snapshot
    assert storage.get(snapshot.snapshot_id) == snapshot
    events = snapshot_create_events(service, snapshot.snapshot_id)
    assert len(events) == 1
    assert events[0]["payload"]["correlation_id"] == "corr_wrapper"
