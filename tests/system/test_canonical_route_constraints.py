from __future__ import annotations

from types import SimpleNamespace

import pytest

from voodoo_product.canonical_operation_runtime import CanonicalOperationRuntime
from voodoo_product.canonical_pipeline import CanonicalOperationPipeline
from voodoo_product.github_read_provider import GITHUB_READ_REF_CAPABILITY
from voodoo_product.terminal_profile import (
    BOUNDED_MUTATION_TERMINAL_PROFILE,
    READ_ONLY_TERMINAL_PROFILE,
)

D1 = "1" * 64
D2 = "2" * 64


class SnapshotService:
    def __init__(self, db: object, calls: list[str], *, capability: str) -> None:
        self.db = db
        self.calls = calls
        self.capability = capability

    def create_snapshot(self, **kwargs: object) -> object:
        self.calls.append("snapshot")
        return SimpleNamespace(
            actor_id=kwargs["actor_id"],
            request_id=kwargs["request_id"],
            snapshot_digest=D1,
            execution_id="exec-1",
            capability=self.capability,
            capability_definition_identity=D2,
        )


class GrantService:
    def __init__(self, db: object, calls: list[str]) -> None:
        self.db = db
        self.calls = calls

    def issue_and_store(self, **_: object) -> object:
        self.calls.append("grant")
        raise AssertionError("route mismatch must stop before grant issuance")


class OutboxService:
    def __init__(self, db: object, grant_service: GrantService) -> None:
        self.db = db
        self.grant_service = grant_service

    def consume_and_enqueue(self, **_: object) -> object:
        raise AssertionError("route mismatch must stop before grant consumption")


class Coordinator:
    def admit(self, **_: object) -> object:
        raise AssertionError("route mismatch must stop before dispatch admission")

    def acquire(self, **_: object) -> object:
        raise AssertionError("route mismatch must stop before lease acquisition")


class ProfileRegistry:
    def __init__(self, calls: list[str], *, profile: str) -> None:
        self.calls = calls
        self.profile = profile

    def resolve(self, **_: object) -> object:
        self.calls.append("profile")
        return SimpleNamespace(terminal_profile=self.profile, binding_digest="a" * 64)


def pipeline(*, capability: str, profile: str) -> tuple[CanonicalOperationPipeline, list[str]]:
    calls: list[str] = []
    db = object()
    grant = GrantService(db, calls)
    return (
        CanonicalOperationPipeline(
            snapshot_creator=SnapshotService(db, calls, capability=capability),
            grant_service=grant,
            outbox_service=OutboxService(db, grant),
            coordinator=Coordinator(),
            terminal_profile_registry=ProfileRegistry(calls, profile=profile),
            envelope_revision="dispatch-envelope/g7-r1",
        ),
        calls,
    )


def test_required_profile_mismatch_stops_before_grant() -> None:
    subject, calls = pipeline(
        capability="github.create-ref/v1",
        profile=BOUNDED_MUTATION_TERMINAL_PROFILE,
    )

    with pytest.raises(
        PermissionError,
        match="CANONICAL_PIPELINE_REQUIRED_TERMINAL_PROFILE_MISMATCH",
    ):
        subject.prepare(
            actor_id="usr-1",
            request_id="req-1",
            idempotency_key="idem-1234",
            correlation_id="corr-1234",
            required_terminal_profile=READ_ONLY_TERMINAL_PROFILE,
            required_capability=GITHUB_READ_REF_CAPABILITY,
        )

    assert calls == ["snapshot", "profile"]


def test_required_capability_mismatch_stops_before_grant() -> None:
    subject, calls = pipeline(
        capability="github.other-read/v1",
        profile=READ_ONLY_TERMINAL_PROFILE,
    )

    with pytest.raises(
        PermissionError,
        match="CANONICAL_PIPELINE_REQUIRED_CAPABILITY_MISMATCH",
    ):
        subject.prepare(
            actor_id="usr-1",
            request_id="req-1",
            idempotency_key="idem-1234",
            correlation_id="corr-1234",
            required_terminal_profile=READ_ONLY_TERMINAL_PROFILE,
            required_capability=GITHUB_READ_REF_CAPABILITY,
        )

    assert calls == ["snapshot", "profile"]


class RecordingPipeline(CanonicalOperationPipeline):
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def prepare(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            terminal_profile=READ_ONLY_TERMINAL_PROFILE,
            capability=GITHUB_READ_REF_CAPABILITY,
        )


class RecordingReadTerminal:
    def run(self, *, prepared: object) -> object:
        return SimpleNamespace(prepared=prepared)


def test_runtime_supplies_read_constraints_internally() -> None:
    route_pipeline = RecordingPipeline()
    runtime = object.__new__(CanonicalOperationRuntime)
    object.__setattr__(runtime, "pipeline", route_pipeline)
    object.__setattr__(runtime, "read_terminal", RecordingReadTerminal())
    object.__setattr__(runtime, "create_ref_preparer", None)
    object.__setattr__(runtime, "rollback_preparer", None)

    runtime.run_read_only(
        actor_id="usr-1",
        request_id="req-1",
        idempotency_key="idem-1234",
        correlation_id="corr-1234",
    )

    assert route_pipeline.kwargs is not None
    assert route_pipeline.kwargs["required_terminal_profile"] == READ_ONLY_TERMINAL_PROFILE
    assert route_pipeline.kwargs["required_capability"] == GITHUB_READ_REF_CAPABILITY
