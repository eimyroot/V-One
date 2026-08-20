from __future__ import annotations

from types import SimpleNamespace

import pytest

from voodoo_product import canonical_pipeline as pipeline_module
from voodoo_product.canonical_pipeline import CanonicalOperationPipeline

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
D6 = "6" * 64
D7 = "7" * 64
D8 = "8" * 64
D9 = "9" * 64
DA = "a" * 64
DB = "b" * 64


class SnapshotService:
    def __init__(self, db: object, calls: list[str]) -> None:
        self.db = db
        self.calls = calls

    def create_snapshot(self, **kwargs: object) -> object:
        self.calls.append("snapshot")
        return SimpleNamespace(
            actor_id=kwargs["actor_id"],
            request_id=kwargs["request_id"],
            snapshot_digest=D1,
            execution_id="exec-1",
        )


class GrantService:
    def __init__(self, db: object, calls: list[str]) -> None:
        self.db = db
        self.calls = calls
        self.last_authority: object | None = None

    def issue_and_store(self, *, snapshot: object, authority: object) -> object:
        self.calls.append("grant")
        self.last_authority = authority
        return SimpleNamespace(
            authorization_snapshot_digest=snapshot.snapshot_digest,
            execution_id=snapshot.execution_id,
            jti="jti-1",
            grant_digest=D2,
            capability="github.ref.read/v1",
            target_digest=D3,
        )


class OutboxService:
    def __init__(self, db: object, grant_service: object, calls: list[str]) -> None:
        self.db = db
        self.grant_service = grant_service
        self.calls = calls
        self.last_jti: str | None = None
        self.target_digest = D3

    def consume_and_enqueue(self, *, jti: str) -> object:
        self.calls.append("outbox")
        self.last_jti = jti
        return SimpleNamespace(
            grant_digest=D2,
            execution_id="exec-1",
            authorization_snapshot_digest=D1,
            capability="github.ref.read/v1",
            target_digest=self.target_digest,
        )


class FakeEnvelope:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls
        self.dispatch_id = D4
        self.execution_id = "exec-1"
        self.request_id = "req-1"
        self.capability = "github.ref.read/v1"
        self.target_digest = D3
        self.authorization_snapshot_digest = D1
        self.grant_digest = D2
        self.jti = "jti-1"
        self.outbox_entry_digest = D5
        self.execution_capsule_digest = D6
        self.envelope_digest = D7

    def assert_bound_to(self, outbox: object) -> None:
        assert outbox is not None
        self._calls.append("envelope-bound")


class Coordinator:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.last_admission_id: str | None = None
        self.admission = SimpleNamespace(
            admission_id=D8,
            admission_digest=D9,
            dispatch_id=D4,
            execution_id="exec-1",
            execution_capsule_digest=D6,
        )
        self.lease = SimpleNamespace(
            admission_id=D8,
            execution_id="exec-1",
            execution_capsule_digest=D6,
            lease_id=DA,
            lease_digest=DB,
            execution_epoch=1,
        )

    def admit(self, *, envelope: object) -> object:
        assert envelope.dispatch_id == D4
        self.calls.append("admit")
        return SimpleNamespace(admission=self.admission)

    def acquire(self, *, admission_id: str) -> object:
        self.calls.append("acquire")
        self.last_admission_id = admission_id
        return SimpleNamespace(lease=self.lease)

    def complete(self, **_: object) -> None:
        raise AssertionError("pre-effect pipeline must never call complete")


def make_pipeline(monkeypatch: pytest.MonkeyPatch) -> tuple[
    CanonicalOperationPipeline,
    list[str],
    GrantService,
    OutboxService,
    Coordinator,
]:
    calls: list[str] = []
    db = object()
    snapshot_service = SnapshotService(db, calls)
    grant_service = GrantService(db, calls)
    outbox_service = OutboxService(db, grant_service, calls)
    coordinator = Coordinator(calls)
    scope = SimpleNamespace(scope_digest=D1)
    authority = SimpleNamespace(constraint_digest=D2)

    monkeypatch.setattr(
        pipeline_module.AuthorityScope,
        "from_snapshot",
        classmethod(lambda cls, snapshot: scope),
    )
    monkeypatch.setattr(
        pipeline_module.AuthorityConstraint,
        "from_scope",
        classmethod(lambda cls, supplied_scope: authority),
    )

    def create_envelope(*, outbox_entry: object, envelope_revision: str) -> FakeEnvelope:
        assert outbox_entry is not None
        assert envelope_revision == "dispatch-envelope/reconciliation-r1"
        calls.append("envelope")
        return FakeEnvelope(calls)

    monkeypatch.setattr(
        pipeline_module.DispatchEnvelope,
        "create",
        staticmethod(create_envelope),
    )

    pipeline = CanonicalOperationPipeline(
        snapshot_creator=snapshot_service,
        grant_service=grant_service,
        outbox_service=outbox_service,
        coordinator=coordinator,
        envelope_revision="dispatch-envelope/reconciliation-r1",
    )
    return pipeline, calls, grant_service, outbox_service, coordinator


@pytest.mark.parametrize("profile", ["READ_ONLY_VERIFIED", "BOUNDED_MUTATION_VERIFIED"])
def test_prepare_composes_one_pre_effect_authority_and_durable_path(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
) -> None:
    pipeline, calls, grant_service, outbox_service, coordinator = make_pipeline(monkeypatch)

    prepared = pipeline.prepare(
        actor_id="actor-1",
        request_id="req-1",
        idempotency_key="idem-1",
        correlation_id="corr-1",
        terminal_profile=profile,
    )

    assert calls == [
        "snapshot",
        "grant",
        "outbox",
        "envelope",
        "envelope-bound",
        "admit",
        "acquire",
    ]
    assert grant_service.last_authority is not None
    assert outbox_service.last_jti == "jti-1"
    assert coordinator.last_admission_id == D8
    assert prepared.terminal_profile == profile
    assert prepared.execution_id == "exec-1"
    assert prepared.request_id == "req-1"
    assert prepared.target_digest == D3
    assert prepared.authorization_snapshot_digest == D1
    assert prepared.grant_digest == D2
    assert prepared.execution_capsule_digest == D6
    assert prepared.execution_epoch == 1


def test_unknown_terminal_profile_fails_before_authority_or_durable_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline, calls, _, _, _ = make_pipeline(monkeypatch)

    with pytest.raises(ValueError, match="terminal_profile is unsupported"):
        pipeline.prepare(
            actor_id="actor-1",
            request_id="req-1",
            idempotency_key="idem-1",
            correlation_id="corr-1",
            terminal_profile="UNREGISTERED_PROFILE",
        )

    assert calls == []


def test_pipeline_rejects_split_durable_database_boundaries() -> None:
    db1 = object()
    db2 = object()
    calls: list[str] = []
    snapshot_service = SnapshotService(db1, calls)
    grant_service = GrantService(db2, calls)
    outbox_service = OutboxService(db2, grant_service, calls)

    with pytest.raises(ValueError, match="must share one database boundary"):
        CanonicalOperationPipeline(
            snapshot_creator=snapshot_service,
            grant_service=grant_service,
            outbox_service=outbox_service,
            coordinator=Coordinator(calls),
            envelope_revision="dispatch-envelope/reconciliation-r1",
        )


def test_pipeline_rejects_outbox_with_another_grant_service() -> None:
    db = object()
    calls: list[str] = []
    snapshot_service = SnapshotService(db, calls)
    grant_service = GrantService(db, calls)
    wrong_grant_service = GrantService(db, calls)
    outbox_service = OutboxService(db, wrong_grant_service, calls)

    with pytest.raises(ValueError, match="outbox must use the supplied grant service"):
        CanonicalOperationPipeline(
            snapshot_creator=snapshot_service,
            grant_service=grant_service,
            outbox_service=outbox_service,
            coordinator=Coordinator(calls),
            envelope_revision="dispatch-envelope/reconciliation-r1",
        )


def test_cross_binding_mismatch_fails_closed_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline, calls, _, outbox_service, _ = make_pipeline(monkeypatch)
    outbox_service.target_digest = "c" * 64

    with pytest.raises(PermissionError, match="CANONICAL_PIPELINE_TARGET_DIGEST_MISMATCH"):
        pipeline.prepare(
            actor_id="actor-1",
            request_id="req-1",
            idempotency_key="idem-1",
            correlation_id="corr-1",
            terminal_profile="READ_ONLY_VERIFIED",
        )

    assert calls == ["snapshot", "grant", "outbox"]


def test_pre_effect_pipeline_exposes_no_provider_effect_or_completion_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline, _, _, _, _ = make_pipeline(monkeypatch)

    for forbidden in (
        "execute",
        "effect",
        "mutate",
        "verify",
        "complete",
        "create_operation_proof",
        "create_operation_cell",
    ):
        assert not hasattr(pipeline, forbidden)
