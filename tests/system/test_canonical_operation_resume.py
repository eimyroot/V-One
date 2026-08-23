from __future__ import annotations

import inspect
from contextlib import AbstractContextManager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from voodoo_product import canonical_operation_resume as resume_module
from voodoo_product.canonical_operation_resume import (
    RESUME_READ_STATEMENTS,
    CanonicalOperationResumeDenied,
    CanonicalOperationResumeService,
)
from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.execution_contract import REQUIRED_EXECUTION_PERMISSION
from voodoo_product.terminal_profile import READ_ONLY_TERMINAL_PROFILE


def digest(character: str) -> str:
    return character * 64


D1 = digest("1")
D2 = digest("2")
D3 = digest("3")
D4 = digest("4")
D5 = digest("5")
D6 = digest("6")
D7 = digest("7")
D8 = digest("8")
D9 = digest("9")
DA = digest("a")
DB = digest("b")
DC = digest("c")
DD = digest("d")
DE = digest("e")
DF = digest("f")


class Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchone(self) -> dict[str, Any] | None:
        return None if not self.rows else self.rows[0]

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.rows)


class Connection:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database

    def execute(self, statement: Any, parameters: Any = ()) -> Cursor:
        self.database.executed.append((statement.name, statement.mode, tuple(parameters)))
        return Cursor(self.database.rows.get(statement.name, []))

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


class FakeDatabase:
    backend_name = "sqlite"
    write_serialization = "global"

    def __init__(self, rows: dict[str, list[dict[str, Any]]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, str, tuple[Any, ...]]] = []

    def initialize(self) -> None:
        return None

    def connect(self) -> Connection:
        return Connection(self)

    def transaction(self) -> AbstractContextManager[Any]:
        return self.connect()

    def schema_version(self) -> int:
        return 14


class StoredValue(SimpleNamespace):
    def __init__(self, *, raw: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._raw = raw

    def to_dict(self) -> dict[str, Any]:
        return dict(self._raw)


class AdmissionValue(StoredValue):
    def __init__(self, *, events: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.events = events

    def assert_bound_to(self, *, envelope: object, outbox_entry: object) -> None:
        self.events.append("admission.bind")
        assert envelope.envelope_digest == self.envelope_digest
        assert outbox_entry.outbox_id == self.outbox_id
        assert outbox_entry.entry_digest == self.outbox_entry_digest


class LeaseValue(StoredValue):
    def __init__(self, *, events: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.events = events

    def assert_bound_to(self, admission: object) -> None:
        self.events.append("lease.bind")
        assert admission.admission_id == self.admission_id
        assert admission.admission_digest == self.admission_digest


class SnapshotStore:
    def __init__(self, db: object, snapshot: object) -> None:
        self.db = db
        self.snapshot = snapshot
        self.requested: list[str] = []

    def get(self, snapshot_id: str) -> object:
        self.requested.append(snapshot_id)
        return self.snapshot


class PermissionAuthority:
    def __init__(self, db: object, *, granted: bool = True) -> None:
        self.db = db
        self.granted = granted
        self.queries: list[object] = []

    def decide(self, query: object) -> object:
        self.queries.append(query)
        return SimpleNamespace(granted=self.granted)


class TerminalRegistry:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[tuple[str, str]] = []

    def resolve(self, *, capability_definition_identity: str, capability: str) -> object:
        self.events.append("profile.resolve")
        self.calls.append((capability_definition_identity, capability))
        return SimpleNamespace(
            terminal_profile=READ_ONLY_TERMINAL_PROFILE,
            binding_digest=D9,
        )


class CurrentFence:
    def __init__(self, db: object, events: list[str]) -> None:
        self.db = db
        self.events = events
        self.leases: list[object] = []

    def assert_current(self, *, lease: object) -> None:
        self.events.append("fence.current")
        self.leases.append(lease)


def fixture_state() -> tuple[
    FakeDatabase,
    object,
    StoredValue,
    StoredValue,
    AdmissionValue,
    LeaseValue,
    list[str],
]:
    events: list[str] = []
    snapshot = SimpleNamespace(
        snapshot_id="snap-1",
        snapshot_digest=D1,
        execution_id="exec-1",
        request_id="req-1",
        actor_id="actor-1",
        workspace_id="ws-1",
        environment="staging",
        capability="github.read-ref/v1",
        capability_definition_identity=D2,
        target_kind="git_ref",
        target_digest=D3,
        payload_digest=D4,
        policy_version="policy-v1",
        policy_identity=D5,
        approval_set_digest=D6,
    )
    grant = StoredValue(
        raw={"kind": "grant"},
        jti="jti-1",
        grant_id="grant-1",
        grant_digest=D7,
        execution_id="exec-1",
        request_id="req-1",
        actor_id="actor-1",
        workspace_id="ws-1",
        environment="staging",
        capability="github.read-ref/v1",
        capability_definition_identity=D2,
        authorization_snapshot_digest=D1,
        target_kind="git_ref",
        target_digest=D3,
        payload_digest=D4,
        policy_version="policy-v1",
        policy_identity=D5,
        approval_set_digest=D6,
        required_permission=REQUIRED_EXECUTION_PERMISSION,
        execution_binding_digest=D8,
        execution_capsule_digest=DA,
        runner_class="github-actions.runner/v1",
        precondition_enforcement_class="READ_THEN_COMPARE",
        use_semantics="ONE_TIME",
        issued_at="2026-08-23T08:00:00.000+00:00",
        expires_at="2026-08-23T08:01:00.000+00:00",
        revocation_epoch=7,
    )
    outbox = StoredValue(
        raw={"kind": "outbox"},
        outbox_id="outbox-1",
        consumption_id="consumption-1",
        consumption_witness_digest=DB,
        jti=grant.jti,
        grant_id=grant.grant_id,
        grant_digest=grant.grant_digest,
        execution_id=grant.execution_id,
        request_id=grant.request_id,
        actor_id=grant.actor_id,
        workspace_id=grant.workspace_id,
        environment=grant.environment,
        capability=grant.capability,
        capability_definition_identity=grant.capability_definition_identity,
        authorization_snapshot_digest=grant.authorization_snapshot_digest,
        target_kind=grant.target_kind,
        target_digest=grant.target_digest,
        payload_digest=grant.payload_digest,
        required_permission=grant.required_permission,
        execution_binding_digest=grant.execution_binding_digest,
        execution_capsule_digest=grant.execution_capsule_digest,
        runner_class=grant.runner_class,
        precondition_enforcement_class=grant.precondition_enforcement_class,
        use_semantics=grant.use_semantics,
        created_at="2026-08-23T08:00:00.000+00:00",
        outbox_revision="outbox-r1",
        entry_digest=DC,
    )
    admission = AdmissionValue(
        events=events,
        raw={"kind": "admission"},
        admission_id=DD,
        dispatch_id=DE,
        envelope_digest=DF,
        outbox_id=outbox.outbox_id,
        outbox_entry_digest=outbox.entry_digest,
        execution_id=outbox.execution_id,
        workspace_id=outbox.workspace_id,
        environment=outbox.environment,
        execution_capsule_digest=outbox.execution_capsule_digest,
        runner_class=outbox.runner_class,
        admission_revision="admission-r1",
        admission_digest=D8,
    )
    lease = LeaseValue(
        events=events,
        raw={"kind": "lease"},
        lease_id=DB,
        admission_id=admission.admission_id,
        dispatch_id=admission.dispatch_id,
        admission_digest=admission.admission_digest,
        execution_id=admission.execution_id,
        workspace_id=admission.workspace_id,
        environment=admission.environment,
        execution_capsule_digest=admission.execution_capsule_digest,
        runner_class=admission.runner_class,
        execution_epoch=1,
        acquired_at="2026-08-23T08:00:00.000+00:00",
        expires_at="2026-08-23T08:30:00.000+00:00",
        clock_witness_digest=DE,
        lease_revision="lease-r1",
        lease_digest=DF,
    )

    def encoded(value: StoredValue) -> str:
        return resume_module.canonical_json(value.to_dict())

    rows = {
        "canonical_resume.select_snapshot_id_by_execution": [{"id": snapshot.snapshot_id}],
        "canonical_resume.select_grant_by_execution": [
            {
                "jti": grant.jti,
                "grant_id": grant.grant_id,
                "execution_id": grant.execution_id,
                "request_id": grant.request_id,
                "workspace_id": grant.workspace_id,
                "environment": grant.environment,
                "authorization_snapshot_digest": grant.authorization_snapshot_digest,
                "execution_capsule_digest": grant.execution_capsule_digest,
                "grant_digest": grant.grant_digest,
                "grant_json": encoded(grant),
                "issued_at": grant.issued_at,
                "expires_at": grant.expires_at,
                "revocation_epoch": grant.revocation_epoch,
            }
        ],
        "canonical_resume.select_outbox_by_execution": [
            {
                **{
                    field: getattr(outbox, field)
                    for field in (
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
                    )
                },
                "entry_json": encoded(outbox),
            }
        ],
        "canonical_resume.select_inbox_by_execution": [
            {
                **{
                    field: getattr(admission, field)
                    for field in (
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
                    )
                },
                "admission_json": encoded(admission),
            }
        ],
        "canonical_resume.select_epoch_state_by_execution": [
            {
                "admission_id": admission.admission_id,
                "admission_digest": admission.admission_digest,
                "execution_id": lease.execution_id,
                "workspace_id": lease.workspace_id,
                "environment": lease.environment,
                "execution_capsule_digest": lease.execution_capsule_digest,
                "runner_class": lease.runner_class,
                "current_epoch": lease.execution_epoch,
                "current_lease_id": lease.lease_id,
                "current_lease_digest": lease.lease_digest,
                "current_lease_acquired_at": lease.acquired_at,
                "current_lease_expires_at": lease.expires_at,
                "status": "ACTIVE",
            }
        ],
        "canonical_resume.select_lease_by_id": [
            {
                **{
                    field: getattr(lease, field)
                    for field in (
                        "lease_id",
                        "admission_id",
                        "dispatch_id",
                        "admission_digest",
                        "execution_id",
                        "workspace_id",
                        "environment",
                        "execution_capsule_digest",
                        "runner_class",
                        "execution_epoch",
                        "acquired_at",
                        "expires_at",
                        "clock_witness_digest",
                        "lease_revision",
                        "lease_digest",
                    )
                },
                "lease_json": encoded(lease),
            }
        ],
    }
    return FakeDatabase(rows), snapshot, grant, outbox, admission, lease, events


def make_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    granted: bool = True,
) -> tuple[
    CanonicalOperationResumeService,
    FakeDatabase,
    SnapshotStore,
    PermissionAuthority,
    TerminalRegistry,
    CurrentFence,
    object,
    StoredValue,
    StoredValue,
    AdmissionValue,
    LeaseValue,
    list[str],
]:
    db, snapshot, grant, outbox, admission, lease, events = fixture_state()
    snapshot_store = SnapshotStore(db, snapshot)
    permission = PermissionAuthority(db, granted=granted)
    profiles = TerminalRegistry(events)
    fence = CurrentFence(db, events)

    monkeypatch.setattr(
        resume_module.ExecutionGrantV2,
        "from_dict",
        staticmethod(lambda _: grant),
    )
    monkeypatch.setattr(
        resume_module.DispatchOutboxEntry,
        "from_dict",
        staticmethod(lambda _: outbox),
    )
    monkeypatch.setattr(
        resume_module.DispatchInboxAdmission,
        "from_dict",
        staticmethod(lambda _: admission),
    )
    monkeypatch.setattr(
        resume_module.ExecutionLease,
        "from_dict",
        staticmethod(lambda _: lease),
    )

    def create_envelope(*, outbox_entry: object, envelope_revision: str) -> object:
        events.append("envelope.create")
        assert outbox_entry is outbox
        assert envelope_revision == "dispatch-envelope/reconciliation-r1"
        return SimpleNamespace(envelope_digest=admission.envelope_digest)

    monkeypatch.setattr(
        resume_module.DispatchEnvelope,
        "create",
        staticmethod(create_envelope),
    )

    service = CanonicalOperationResumeService(
        database=db,
        snapshot_store=snapshot_store,  # type: ignore[arg-type]
        permission_authority=permission,  # type: ignore[arg-type]
        terminal_profile_registry=profiles,
        current_fence=fence,  # type: ignore[arg-type]
        envelope_revision="dispatch-envelope/reconciliation-r1",
    )
    return (
        service,
        db,
        snapshot_store,
        permission,
        profiles,
        fence,
        snapshot,
        grant,
        outbox,
        admission,
        lease,
        events,
    )


def test_resume_rebuilds_exact_current_context_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        db,
        snapshot_store,
        permission,
        profiles,
        fence,
        snapshot,
        grant,
        outbox,
        admission,
        lease,
        events,
    ) = make_service(monkeypatch)

    prepared = service.resume(actor_id="actor-1", execution_id="exec-1")

    assert snapshot_store.requested == ["snap-1"]
    assert len(permission.queries) == 1
    query = permission.queries[0]
    assert query.actor_id == "actor-1"
    assert query.workspace_id == "ws-1"
    assert query.environment == "staging"
    assert query.permission == REQUIRED_EXECUTION_PERMISSION
    assert profiles.calls == [(D2, "github.read-ref/v1")]
    assert fence.leases == [lease]
    assert events == ["envelope.create", "admission.bind", "lease.bind", "profile.resolve", "fence.current"]
    assert all(mode == "read" for _, mode, _ in db.executed)
    assert [name for name, _, _ in db.executed] == [
        "canonical_resume.select_snapshot_id_by_execution",
        "canonical_resume.select_grant_by_execution",
        "canonical_resume.select_outbox_by_execution",
        "canonical_resume.select_inbox_by_execution",
        "canonical_resume.select_epoch_state_by_execution",
        "canonical_resume.select_lease_by_id",
    ]
    assert prepared.snapshot is snapshot
    assert prepared.grant is grant
    assert prepared.outbox is outbox
    assert prepared.admission is admission
    assert prepared.lease is lease
    assert prepared.execution_id == "exec-1"
    assert prepared.terminal_profile == READ_ONLY_TERMINAL_PROFILE
    assert prepared.terminal_profile_binding_digest == D9


def test_resume_rejects_different_original_actor_before_live_permission_or_chain_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, _, permission, _, fence, *_ = make_service(monkeypatch)

    with pytest.raises(CanonicalOperationResumeDenied, match="ACTOR_MISMATCH"):
        service.resume(actor_id="actor-2", execution_id="exec-1")

    assert permission.queries == []
    assert fence.leases == []
    assert [name for name, _, _ in db.executed] == [
        "canonical_resume.select_snapshot_id_by_execution"
    ]


def test_resume_rechecks_current_database_permission_before_durable_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, _, permission, _, fence, *_ = make_service(monkeypatch, granted=False)

    with pytest.raises(CanonicalOperationResumeDenied, match="LIVE_EXECUTION_PERMISSION_DENIED"):
        service.resume(actor_id="actor-1", execution_id="exec-1")

    assert len(permission.queries) == 1
    assert fence.leases == []
    assert [name for name, _, _ in db.executed] == [
        "canonical_resume.select_snapshot_id_by_execution"
    ]


def test_resume_rejects_completed_execution_before_profile_or_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, _, _, profiles, fence, *_ = make_service(monkeypatch)
    db.rows["canonical_resume.select_epoch_state_by_execution"][0]["status"] = "COMPLETED"

    with pytest.raises(CanonicalOperationResumeDenied, match="EXECUTION_NOT_ACTIVE"):
        service.resume(actor_id="actor-1", execution_id="exec-1")

    assert profiles.calls == []
    assert fence.leases == []


def test_resume_rejects_corrupt_outbox_projection_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, _, _, profiles, fence, *_ = make_service(monkeypatch)
    db.rows["canonical_resume.select_outbox_by_execution"][0]["grant_digest"] = D8

    with pytest.raises(CanonicalOperationResumeDenied, match="OUTBOX_ROW_INVALID"):
        service.resume(actor_id="actor-1", execution_id="exec-1")

    assert profiles.calls == []
    assert fence.leases == []


def test_resume_contract_has_no_caller_profile_or_mutation_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, *_ = make_service(monkeypatch)

    assert "terminal_profile" not in inspect.signature(service.resume).parameters
    for forbidden in (
        "write",
        "mutate",
        "execute",
        "create_ref",
        "delete_ref",
        "reacquire",
        "consume",
        "enqueue",
    ):
        assert not hasattr(service, forbidden)
    assert all(statement.mode == "read" for statement in RESUME_READ_STATEMENTS)


def test_resume_read_statements_compile_against_released_sqlite_schema(tmp_path: Path) -> None:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()

    with database.connect() as connection:
        for statement in RESUME_READ_STATEMENTS:
            rows = connection.execute(statement, ("missing",)).fetchall()
            assert rows == []
