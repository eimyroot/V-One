from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from voodoo_product import approval_evidence_statements as approval_sql
from voodoo_product import statements as sql
from voodoo_product.approval_evidence_resolver import (
    load_approval_evidence_on_connection,
)
from voodoo_product.config import ProductConfig
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import ExecutionTarget
from voodoo_product.policy_authority import PolicyRevision
from voodoo_product.service import ProductService
from voodoo_product.trusted_clock import ClockWitness


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def policy(*, validity_seconds: int = 600) -> PolicyRevision:
    return PolicyRevision.create(
        policy_version="approval-policy.authority-r1",
        policy_package="v-one.approval",
        approval_validity_seconds=validity_seconds,
        required_approvals_by_environment={
            "local": 1,
            "development": 1,
            "staging": 1,
            "production": 2,
        },
    )


def target() -> ExecutionTarget:
    return ExecutionTarget.create(
        target_kind="artifact_path",
        target_claims={"path": "proof/result.json", "replace": False},
    )


def clock(*, environment: str, observed_at: datetime) -> ClockWitness:
    return ClockWitness.create(
        source_identity="server-clock/primary-v1",
        authority_revision="clock-policy/v1",
        environment=environment,
        observed_at=observed_at,
    )


def approved_request(
    tmp_path: Path,
    *,
    environment: str = "local",
    reviewers: int = 1,
) -> tuple[ProductService, dict[str, object], list[dict[str, object]]]:
    service = ProductService(product_config(tmp_path, name=environment))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    if environment != "local":
        workspace = service.create_workspace(
            actor_id=bootstrap["user_id"],
            name=f"{environment}-workspace",
            environment=environment,
        )
        workspace_id = workspace["id"]
    else:
        workspace_id = bootstrap["workspace_id"]

    reviewer_rows = [
        service.create_user(
            actor_id=bootstrap["user_id"],
            username=f"reviewer-{index}",
            password=f"VeryStrongReviewerPassword{index}!",
            role="operator",
        )
        for index in range(reviewers)
    ]
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=workspace_id,
        title="Authoritative approval evidence",
        description="resolve exact persisted reviewed approvals",
        risk="R3",
        environment=environment,
        adapter="write_artifact",
        payload={"message": "příliš žluťoučký kůň", "path": "proof/result.json"},
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    for reviewer in reviewer_rows:
        service.approve_change_request(
            actor_id=reviewer["id"],
            request_id=request["id"],
            decision="APPROVED",
            reason="independent review complete",
        )
    return service, request, reviewer_rows


def approval_created_at(service: ProductService, request_id: str) -> datetime:
    with service.db.connect() as connection:
        row = connection.execute(
            approval_sql.SELECT_APPROVAL_EVIDENCE,
            (request_id,),
        ).fetchone()
    assert row is not None
    return datetime.fromisoformat(str(row["created_at"])).astimezone(UTC)


def test_resolver_constructs_exact_bound_evidence_from_persisted_state(tmp_path: Path) -> None:
    service, request, _ = approved_request(tmp_path)
    approved_at = approval_created_at(service, str(request["id"]))
    policy_revision = policy()
    execution_target = target()

    with service.db.transaction() as connection:
        evidence = load_approval_evidence_on_connection(
            connection,
            request_id=str(request["id"]),
            capability="voodoo.write-artifact/v1",
            execution_target=execution_target,
            policy_revision=policy_revision,
            clock_witness=clock(
                environment="local",
                observed_at=approved_at + timedelta(seconds=60),
            ),
        )

    expected_payload_digest = hashlib.sha256(
        canonical_json(
            {
                "schema_version": 1,
                "binding_type": "request-payload/v1",
                "payload": request["payload"],
            }
        ).encode("utf-8")
    ).hexdigest()
    assert evidence.request_id == request["id"]
    assert evidence.payload_digest == expected_payload_digest
    assert evidence.target_digest == execution_target.target_digest
    assert evidence.capability == "voodoo.write-artifact/v1"
    assert evidence.policy_version == policy_revision.policy_version
    assert len(evidence.approvals) == 1
    assert evidence.approval_valid_until == (
        approved_at + timedelta(seconds=policy_revision.approval_validity_seconds)
    ).isoformat(timespec="milliseconds")


def test_resolver_fails_closed_until_policy_quorum_is_persisted(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path, name="production-quorum"))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    workspace = service.create_workspace(
        actor_id=bootstrap["user_id"],
        name="production-workspace",
        environment="production",
    )
    reviewers = [
        service.create_user(
            actor_id=bootstrap["user_id"],
            username=f"production-reviewer-{index}",
            password=f"VeryStrongProductionReviewerPassword{index}!",
            role="operator",
        )
        for index in range(2)
    ]
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=workspace["id"],
        title="Production approval quorum",
        description="requires two independent approvals",
        risk="R4",
        environment="production",
        adapter="write_artifact",
        payload={"path": "proof/result.json"},
    )
    service.submit_change_request(actor_id=bootstrap["user_id"], request_id=request["id"])
    service.approve_change_request(
        actor_id=reviewers[0]["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="first review",
    )
    first_approved_at = approval_created_at(service, request["id"])

    with (
        service.db.transaction() as connection,
        pytest.raises(RuntimeError, match="not in approved state"),
    ):
        load_approval_evidence_on_connection(
            connection,
            request_id=request["id"],
            capability="voodoo.write-artifact/v1",
            execution_target=target(),
            policy_revision=policy(),
            clock_witness=clock(
                environment="production",
                observed_at=first_approved_at + timedelta(seconds=30),
            ),
        )

    service.approve_change_request(
        actor_id=reviewers[1]["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="second review",
    )
    with service.db.connect() as connection:
        rows = connection.execute(
            approval_sql.SELECT_APPROVAL_EVIDENCE,
            (request["id"],),
        ).fetchall()
    latest_approval = max(
        datetime.fromisoformat(str(row["created_at"])).astimezone(UTC) for row in rows
    )

    with service.db.transaction() as connection:
        evidence = load_approval_evidence_on_connection(
            connection,
            request_id=request["id"],
            capability="voodoo.write-artifact/v1",
            execution_target=target(),
            policy_revision=policy(),
            clock_witness=clock(
                environment="production",
                observed_at=latest_approval + timedelta(seconds=30),
            ),
        )
    assert len(evidence.approvals) == 2


def test_resolver_rejects_expired_or_future_approval_evidence(tmp_path: Path) -> None:
    service, request, _ = approved_request(tmp_path)
    approved_at = approval_created_at(service, str(request["id"]))
    policy_revision = policy(validity_seconds=60)

    with (
        service.db.transaction() as connection,
        pytest.raises(PermissionError, match="expired"),
    ):
        load_approval_evidence_on_connection(
            connection,
            request_id=str(request["id"]),
            capability="voodoo.write-artifact/v1",
            execution_target=target(),
            policy_revision=policy_revision,
            clock_witness=clock(
                environment="local",
                observed_at=approved_at + timedelta(seconds=60),
            ),
        )

    with (
        service.db.transaction() as connection,
        pytest.raises(RuntimeError, match="after authorization time"),
    ):
        load_approval_evidence_on_connection(
            connection,
            request_id=str(request["id"]),
            capability="voodoo.write-artifact/v1",
            execution_target=target(),
            policy_revision=policy_revision,
            clock_witness=clock(
                environment="local",
                observed_at=approved_at - timedelta(milliseconds=1),
            ),
        )


def test_resolver_rejects_persisted_requester_self_approval(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path, name="self-approval"))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Corrupt approval evidence",
        description="resolver must fail closed",
        risk="R1",
        environment="local",
        adapter="write_artifact",
        payload={"path": "proof/result.json"},
    )
    submitted = service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=request["id"],
    )
    created_at = "2026-08-16T20:30:00.000+00:00"

    with service.db.transaction() as connection:
        connection.execute(
            sql.INSERT_APPROVAL,
            (
                "appr_corrupt",
                request["id"],
                bootstrap["user_id"],
                "APPROVED",
                "invalid self approval",
                submitted["review_content_sha256"],
                created_at,
            ),
        )
        connection.execute(
            sql.UPDATE_CHANGE_REQUEST_STATUS,
            ("APPROVED", created_at, request["id"]),
        )

    with (
        service.db.transaction() as connection,
        pytest.raises(PermissionError, match="requester approval"),
    ):
        load_approval_evidence_on_connection(
            connection,
            request_id=request["id"],
            capability="voodoo.write-artifact/v1",
            execution_target=target(),
            policy_revision=policy(),
            clock_witness=clock(
                environment="local",
                observed_at=datetime(2026, 8, 16, 20, 31, tzinfo=UTC),
            ),
        )
