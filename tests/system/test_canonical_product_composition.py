from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from voodoo_product.a09_rollback_orchestration import A09RollbackPreparer
from voodoo_product.a09_write_orchestration import A09CreateRefPreparer
from voodoo_product.canonical_operation_runtime import CanonicalOperationRuntime
from voodoo_product.canonical_pipeline import CanonicalOperationPipeline
from voodoo_product.canonical_read_terminal import CanonicalGitHubReadTerminal
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.permission_authority import DatabasePermissionAuthority
from voodoo_product.terminal_profile import (
    BOUNDED_MUTATION_TERMINAL_PROFILE,
    READ_ONLY_TERMINAL_PROFILE,
)


class FakePipeline(CanonicalOperationPipeline):
    def __init__(self, prepared: object | None = None) -> None:
        self.prepared = prepared

    def prepare(self, **_: object) -> object:
        if self.prepared is None:
            raise AssertionError("prepare should not be called")
        return self.prepared


class FakeReadTerminal(CanonicalGitHubReadTerminal):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def run(self, *, prepared: object) -> object:
        self.events.append("read")
        return SimpleNamespace(prepared=prepared, verification_result="VERIFIED")


class FakeCreatePreparer(A09CreateRefPreparer):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def prepare(self, *, prepared: object) -> object:
        self.events.append("create-preflight")
        return SimpleNamespace(prepared=prepared, preflight="CREATE_PREFLIGHT")


class FakeRollbackPreparer(A09RollbackPreparer):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def prepare(self, *, prepared: object, observed_ref_sha: str, predelete_observation_digest: str) -> object:
        self.events.append("rollback-preflight")
        return SimpleNamespace(
            prepared=prepared,
            observed_ref_sha=observed_ref_sha,
            predelete_observation_digest=predelete_observation_digest,
            preflight="ROLLBACK_PREFLIGHT",
        )


def config(tmp_path: Path) -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def prepared(*, profile: str, capability: str) -> object:
    return SimpleNamespace(terminal_profile=profile, capability=capability)


def test_canonical_runtime_routes_read_without_caller_profile() -> None:
    events: list[str] = []
    runtime = CanonicalOperationRuntime(
        pipeline=FakePipeline(
            prepared=prepared(
                profile=READ_ONLY_TERMINAL_PROFILE,
                capability="github.read-ref/v1",
            )
        ),
        read_terminal=FakeReadTerminal(events),
    )

    result = runtime.run_read_only(
        actor_id="usr-1",
        request_id="req-1",
        idempotency_key="idem-1",
        correlation_id="corr-1",
    )

    assert events == ["read"]
    assert result.verification_result == "VERIFIED"
    assert "terminal_profile" not in runtime.run_read_only.__annotations__


def test_canonical_runtime_routes_write_only_to_a09_preflight() -> None:
    events: list[str] = []
    runtime = CanonicalOperationRuntime(
        pipeline=FakePipeline(
            prepared=prepared(
                profile=BOUNDED_MUTATION_TERMINAL_PROFILE,
                capability="github.create-ref/v1",
            )
        ),
        create_ref_preparer=FakeCreatePreparer(events),
    )

    result = runtime.prepare_create_ref(
        actor_id="usr-1",
        request_id="req-1",
        idempotency_key="idem-1",
        correlation_id="corr-1",
    )

    assert events == ["create-preflight"]
    assert result.preflight == "CREATE_PREFLIGHT"
    assert not hasattr(runtime, "execute_create_ref")
    assert not hasattr(runtime, "execute_rollback")


def test_canonical_runtime_rejects_profile_route_mismatch_before_terminal() -> None:
    events: list[str] = []
    runtime = CanonicalOperationRuntime(
        pipeline=FakePipeline(
            prepared=prepared(
                profile=BOUNDED_MUTATION_TERMINAL_PROFILE,
                capability="github.create-ref/v1",
            )
        ),
        read_terminal=FakeReadTerminal(events),
    )

    with pytest.raises(PermissionError, match="CANONICAL_RUNTIME_READ_PROFILE_MISMATCH"):
        runtime.run_read_only(
            actor_id="usr-1",
            request_id="req-1",
            idempotency_key="idem-1",
            correlation_id="corr-1",
        )
    assert events == []


def test_product_composition_always_owns_database_permission_authority(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=config(tmp_path),
        repository_root=tmp_path,
    )

    assert isinstance(composition.database_permission_authority, DatabasePermissionAuthority)
    assert composition.database_permission_authority.db is composition.service.db
    assert composition.canonical_operation_runtime is None
    assert app.state.voodoo_database_permission_authority is composition.database_permission_authority
    assert app.state.voodoo_canonical_operation_runtime is None


def test_product_composition_accepts_only_same_db_same_permission_canonical_runtime(
    tmp_path: Path,
) -> None:
    app = FastAPI()

    def factory(service, permission_authority):
        pipeline = FakePipeline()
        pipeline.snapshot_creator = SimpleNamespace(
            db=service.db,
            permission_authority=permission_authority,
        )
        pipeline.grant_service = SimpleNamespace(db=service.db)
        pipeline.outbox_service = SimpleNamespace(db=service.db)
        return CanonicalOperationRuntime(pipeline=pipeline)

    composition = install_composed_product_platform(
        app,
        config=config(tmp_path),
        repository_root=tmp_path,
        canonical_runtime_factory=factory,
    )

    assert isinstance(composition.canonical_operation_runtime, CanonicalOperationRuntime)
    assert app.state.voodoo_canonical_operation_runtime is composition.canonical_operation_runtime
    assert (
        composition.canonical_operation_runtime.pipeline.snapshot_creator.permission_authority
        is composition.database_permission_authority
    )


def test_product_composition_rejects_parallel_permission_authority(tmp_path: Path) -> None:
    app = FastAPI()

    def factory(service, permission_authority):
        del permission_authority
        pipeline = FakePipeline()
        pipeline.snapshot_creator = SimpleNamespace(
            db=service.db,
            permission_authority=object(),
        )
        pipeline.grant_service = SimpleNamespace(db=service.db)
        pipeline.outbox_service = SimpleNamespace(db=service.db)
        return CanonicalOperationRuntime(pipeline=pipeline)

    with pytest.raises(
        ValueError,
        match="must use product database permission authority",
    ):
        install_composed_product_platform(
            app,
            config=config(tmp_path),
            repository_root=tmp_path,
            canonical_runtime_factory=factory,
        )
