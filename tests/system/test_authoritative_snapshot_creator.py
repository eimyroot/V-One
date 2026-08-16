from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from voodoo_product.audit import AuditLedger
from voodoo_product.authorization_snapshot_creator import (
    AuthoritativeSnapshotCreator,
    ImmutableCapabilitySelectionAuthority,
    SnapshotAuthorizationDenied,
)
from voodoo_product.authorization_snapshot_store import AuthorizationSnapshotStore
from voodoo_product.capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from voodoo_product.config import ProductConfig
from voodoo_product.execution_contract import ExecutionTarget
from voodoo_product.permission_authority import CurrentPrincipalPermissionAuthority
from voodoo_product.policy_authority import ImmutablePolicyAuthority, PolicyRevision
from voodoo_product.security import Principal
from voodoo_product.service import ProductService
from voodoo_product.target_binding import TargetBinderRegistry
from voodoo_product.trusted_clock import TrustedClockAuthority


class ArtifactBinder:
    binder_id = "artifact-from-approved-request/v1"
    target_kind = "artifact_path"

    def bind(self, *, approved_payload: dict[str, Any]) -> ExecutionTarget:
        artifact = approved_payload.get("artifact")
        if not isinstance(artifact, str) or not artifact:
            raise ValueError("approved payload has no artifact")
        return ExecutionTarget.create(
            target_kind=self.target_kind,
            target_claims={"path": artifact, "replace": False},
        )


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def read(self) -> datetime:
        return self.value


class FixedRevocationAuthority:
    def __init__(self, epoch: int = 7, *, denied: bool = False) -> None:
        self.epoch = epoch
        self.denied = denied

    def current_epoch(
        self,
        connection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int:
        del connection, workspace_id, environment, capability_definition_identity
        if self.denied:
            raise PermissionError("revoked")
        return self.epoch


class FailingWitnessAuditLedger(AuditLedger):
    def append(self, connection, *, actor_id, action, target_type, target_id, payload):
        if action == "authorization_snapshot.authority_witness":
            raise RuntimeError("simulated authority witness audit failure")
        return super().append(
            connection,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )


def product(tmp_path: Path) -> ProductService:
    return ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        )
    )


def approved_request(service: ProductService) -> dict[str, str]:
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    reviewer = service.create_user(
        actor_id=bootstrap["user_id"],
        username="reviewer",
        password="VeryStrongReviewerPassword1!",
        role="operator",
    )
    executor = service.create_user(
        actor_id=bootstrap["user_id"],
        username="executor",
        password="VeryStrongExecutorPassword1!",
        role="operator",
    )
    request = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=bootstrap["workspace_id"],
        title="Snapshot creator",
        description="Bounded authority construction",
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
        actor_id=reviewer["id"],
        request_id=request["id"],
        decision="APPROVED",
        reason="reviewed",
    )
    with service.db.connect() as connection:
        approval = connection.execute(
            "SELECT created_at FROM approvals WHERE request_id = ?",
            (request["id"],),
        ).fetchone()
    assert approval is not None
    return {
        "request_id": request["id"],
        "workspace_id": bootstrap["workspace_id"],
        "requester_id": bootstrap["user_id"],
        "reviewer_id": reviewer["id"],
        "executor_id": executor["id"],
        "approval_at": str(approval["created_at"]),
    }


def creator(
    service: ProductService,
    setup: dict[str, str],
    *,
    clock_value: datetime | None = None,
    role: str = "operator",
    selection_bindings: dict[str, str] | None = None,
    revocation_authority: FixedRevocationAuthority | None = None,
    audit_ledger: AuditLedger | None = None,
) -> AuthoritativeSnapshotCreator:
    approval_at = datetime.fromisoformat(setup["approval_at"])
    observed = clock_value or (approval_at + timedelta(seconds=1))

    definition = CapabilityDefinition.create(
        capability="voodoo.echo/v1",
        target_kind="artifact_path",
        binder_id=ArtifactBinder.binder_id,
        handler_id="handler.echo/v1",
        effect_class="READ_ONLY",
        verification_class="INDEPENDENT_READBACK_REQUIRED",
        supported_environments=("local",),
        required_permissions=("execution.run",),
        production_eligible=False,
    )
    activation = CapabilityActivation.create(
        capability_definition_identity=definition.definition_identity,
        activation_generation=1,
        enabled_environments=("local",),
    )
    policy = PolicyRevision.create(
        policy_version="approval-policy.snapshot-r1",
        policy_package="approval-policy.snapshot-r1",
        approval_validity_seconds=600,
        required_approvals_by_environment={
            "development": 1,
            "local": 1,
            "production": 2,
            "staging": 1,
        },
    )
    ledger = audit_ledger or service.audit_ledger
    store = AuthorizationSnapshotStore(
        database=service.db,
        audit_ledger=ledger,
        clock=lambda: observed.astimezone(UTC).isoformat(timespec="milliseconds"),
    )
    return AuthoritativeSnapshotCreator(
        database=service.db,
        audit_ledger=ledger,
        snapshot_store=store,
        permission_authority=CurrentPrincipalPermissionAuthority(
            principal=Principal(
                user_id=setup["executor_id"],
                username="executor",
                role=role,
            ),
            authority_revision="current-role-authority/test-r1",
        ),
        policy_authority=ImmutablePolicyAuthority((policy,)),
        policy_version=policy.policy_version,
        capability_registry=ImmutableCapabilityRegistry(
            definitions=(definition,),
            activations=(activation,),
        ),
        capability_selection_authority=ImmutableCapabilitySelectionAuthority(
            bindings=selection_bindings or {"echo": definition.capability},
            authority_revision="capability-selection/test-r1",
        ),
        target_binders=TargetBinderRegistry(
            {ArtifactBinder.binder_id: ArtifactBinder()}
        ),
        trusted_clock=TrustedClockAuthority(
            source_identity="test-clock/v1",
            authority_revision="clock-authority/test-r1",
            source=FixedClock(observed),
            allowed_environments=frozenset({"local"}),
        ),
        revocation_authority=revocation_authority or FixedRevocationAuthority(),
        authorization_source_revision="snapshot-creator/test-r1",
        id_factory=lambda prefix: f"{prefix}_snapshot_creator",
    )


def test_creator_builds_and_persists_snapshot_with_exact_authority_witness(
    tmp_path: Path,
) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    subject = creator(service, setup)

    snapshot = subject.create_snapshot(
        actor_id=setup["executor_id"],
        request_id=setup["request_id"],
        idempotency_key="snapshot-key-1",
        correlation_id="corr-1",
    )

    assert snapshot.request_id == setup["request_id"]
    assert snapshot.actor_id == setup["executor_id"]
    assert snapshot.workspace_id == setup["workspace_id"]
    assert snapshot.environment == "local"
    assert snapshot.capability == "voodoo.echo/v1"
    assert snapshot.execution_target.target_kind == "artifact_path"
    assert snapshot.execution_target.target_claims["path"] == "proof/result.json"
    assert snapshot.required_permission == "execution.run"

    stored = subject.snapshot_store.get(snapshot.snapshot_id)
    assert stored == snapshot

    events = service.list_audit_events(limit=100)
    witness_events = [
        event
        for event in events
        if event["action"] == "authorization_snapshot.authority_witness"
    ]
    assert len(witness_events) == 1
    witness = witness_events[0]["payload"]
    assert witness["snapshot_digest"] == snapshot.snapshot_digest
    assert len(witness["authority_witness_set_digest"]) == 64
    assert witness["revocation_epoch"] == 7
    encoded = json.dumps(witness, sort_keys=True)
    assert "proof/result.json" not in encoded
    assert '"artifact"' not in encoded


def test_creator_idempotent_retry_returns_same_snapshot_without_duplicate_witness(
    tmp_path: Path,
) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    subject = creator(service, setup)

    first = subject.create_snapshot(
        actor_id=setup["executor_id"],
        request_id=setup["request_id"],
        idempotency_key="snapshot-key-idempotent",
        correlation_id="corr-idempotent",
    )
    second = subject.create_snapshot(
        actor_id=setup["executor_id"],
        request_id=setup["request_id"],
        idempotency_key="snapshot-key-idempotent",
        correlation_id="corr-idempotent",
    )

    assert second == first
    events = service.list_audit_events(limit=100)
    assert sum(
        event["action"] == "authorization_snapshot.authority_witness"
        for event in events
    ) == 1


def test_creator_denies_missing_execution_permission_and_commits_only_rejection_evidence(
    tmp_path: Path,
) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    subject = creator(service, setup, role="viewer")

    with pytest.raises(
        SnapshotAuthorizationDenied,
        match="EXECUTION_PERMISSION_DENIED",
    ):
        subject.create_snapshot(
            actor_id=setup["executor_id"],
            request_id=setup["request_id"],
            idempotency_key="snapshot-key-denied",
            correlation_id="corr-denied",
        )

    assert subject.snapshot_store.get_by_idempotency_key("snapshot-key-denied") is None
    events = service.list_audit_events(limit=100)
    reject = next(
        event
        for event in events
        if event["action"] == "authorization_snapshot.reject"
    )
    assert reject["payload"] == {
        "correlation_id": "corr-denied",
        "reason_code": "EXECUTION_PERMISSION_DENIED",
    }


def test_creator_denies_expired_approval_without_creating_snapshot(tmp_path: Path) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    approval_at = datetime.fromisoformat(setup["approval_at"])
    subject = creator(
        service,
        setup,
        clock_value=approval_at + timedelta(seconds=601),
    )

    with pytest.raises(SnapshotAuthorizationDenied, match="APPROVAL_EXPIRED"):
        subject.create_snapshot(
            actor_id=setup["executor_id"],
            request_id=setup["request_id"],
            idempotency_key="snapshot-key-expired",
            correlation_id="corr-expired",
        )
    assert subject.snapshot_store.get_by_idempotency_key("snapshot-key-expired") is None


def test_creator_denies_unknown_adapter_capability_selection(tmp_path: Path) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    subject = creator(
        service,
        setup,
        selection_bindings={"write_artifact": "voodoo.echo/v1"},
    )

    with pytest.raises(
        SnapshotAuthorizationDenied,
        match="CAPABILITY_SELECTION_NOT_FOUND",
    ):
        subject.create_snapshot(
            actor_id=setup["executor_id"],
            request_id=setup["request_id"],
            idempotency_key="snapshot-key-selection",
            correlation_id="corr-selection",
        )


def test_creator_denies_live_emergency_stop(tmp_path: Path) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    service.set_emergency_stop(
        actor_id=setup["requester_id"],
        active=True,
        reason="test stop",
    )
    subject = creator(service, setup)

    with pytest.raises(
        SnapshotAuthorizationDenied,
        match="EMERGENCY_STOP_ACTIVE",
    ):
        subject.create_snapshot(
            actor_id=setup["executor_id"],
            request_id=setup["request_id"],
            idempotency_key="snapshot-key-stop",
            correlation_id="corr-stop",
        )


def test_creator_requires_live_revocation_authority(tmp_path: Path) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    subject = creator(
        service,
        setup,
        revocation_authority=FixedRevocationAuthority(denied=True),
    )

    with pytest.raises(SnapshotAuthorizationDenied, match="REVOCATION_DENIED"):
        subject.create_snapshot(
            actor_id=setup["executor_id"],
            request_id=setup["request_id"],
            idempotency_key="snapshot-key-revoked",
            correlation_id="corr-revoked",
        )


def test_authority_witness_audit_failure_rolls_back_snapshot_atomically(
    tmp_path: Path,
) -> None:
    service = product(tmp_path)
    setup = approved_request(service)
    failing_ledger = FailingWitnessAuditLedger(service.db)
    subject = creator(
        service,
        setup,
        audit_ledger=failing_ledger,
    )

    with pytest.raises(RuntimeError, match="simulated authority witness audit failure"):
        subject.create_snapshot(
            actor_id=setup["executor_id"],
            request_id=setup["request_id"],
            idempotency_key="snapshot-key-audit-failure",
            correlation_id="corr-audit-failure",
        )

    assert (
        subject.snapshot_store.get_by_idempotency_key(
            "snapshot-key-audit-failure"
        )
        is None
    )


def test_snapshot_creator_is_not_composed_into_product_runtime(tmp_path: Path) -> None:
    service = product(tmp_path)

    assert not hasattr(service, "authorization_snapshot_creator")
