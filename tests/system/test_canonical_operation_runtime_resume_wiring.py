from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from voodoo_product.canonical_operation_resume import CanonicalOperationResumeService
from voodoo_product.canonical_operation_runtime import CanonicalOperationRuntime
from voodoo_product.canonical_pipeline import CanonicalOperationPipeline
from voodoo_product.canonical_read_terminal import CanonicalGitHubReadTerminal
from voodoo_product.controlled_write import GITHUB_CREATE_REF_CAPABILITY
from voodoo_product.github_read_provider import GITHUB_READ_REF_CAPABILITY
from voodoo_product.terminal_profile import (
    BOUNDED_MUTATION_TERMINAL_PROFILE,
    READ_ONLY_TERMINAL_PROFILE,
)


class StubResumeService(CanonicalOperationResumeService):
    def __init__(
        self,
        *,
        db: object,
        permission_authority: object,
        terminal_profile_registry: object,
        current_fence: object,
        envelope_revision: str,
        prepared: object,
    ) -> None:
        self.db = db
        self.permission_authority = permission_authority
        self.terminal_profile_registry = terminal_profile_registry
        self.current_fence = current_fence
        self.envelope_revision = envelope_revision
        self.prepared = prepared
        self.calls: list[tuple[str, str]] = []

    def resume(self, *, actor_id: str, execution_id: str) -> object:
        self.calls.append((actor_id, execution_id))
        return self.prepared


class StubReadTerminal(CanonicalGitHubReadTerminal):
    def __init__(self, *, current_fence: object) -> None:
        self.runner_adapter = SimpleNamespace(current_fence=current_fence)
        self.calls: list[object] = []

    def run(self, *, prepared: object) -> object:
        self.calls.append(prepared)
        return SimpleNamespace(prepared=prepared)


def _unexpected_prepare(**_: object) -> object:
    raise AssertionError("pipeline.prepare path must not be used by durable resume")


def _pipeline_state() -> tuple[
    CanonicalOperationPipeline,
    object,
    object,
    object,
    object,
]:
    db = object()
    permission_authority = object()
    current_fence = object()
    terminal_profile_registry = SimpleNamespace(resolve=lambda **_: object())
    snapshot_creator = SimpleNamespace(
        db=db,
        permission_authority=permission_authority,
        create_snapshot=_unexpected_prepare,
    )
    grant_service = SimpleNamespace(
        db=db,
        issue_and_store=lambda **_: object(),
    )
    outbox_service = SimpleNamespace(
        db=db,
        grant_service=grant_service,
        consume_and_enqueue=lambda **_: object(),
    )
    coordinator = SimpleNamespace(
        admit=lambda **_: object(),
        acquire=lambda **_: object(),
    )
    pipeline = CanonicalOperationPipeline(
        snapshot_creator=snapshot_creator,
        grant_service=grant_service,
        outbox_service=outbox_service,
        coordinator=coordinator,
        terminal_profile_registry=terminal_profile_registry,
        envelope_revision="dispatch-envelope/runtime-resume-r1",
    )
    return (
        pipeline,
        db,
        permission_authority,
        terminal_profile_registry,
        current_fence,
    )


def _runtime(
    *,
    prepared_profile: str = READ_ONLY_TERMINAL_PROFILE,
    prepared_capability: str = GITHUB_READ_REF_CAPABILITY,
    with_resume: bool = True,
) -> tuple[
    CanonicalOperationRuntime,
    StubResumeService | None,
    StubReadTerminal,
    object,
]:
    pipeline, db, permission, registry, current_fence = _pipeline_state()
    prepared = SimpleNamespace(
        terminal_profile=prepared_profile,
        capability=prepared_capability,
    )
    terminal = StubReadTerminal(current_fence=current_fence)
    resume_service = (
        StubResumeService(
            db=db,
            permission_authority=permission,
            terminal_profile_registry=registry,
            current_fence=current_fence,
            envelope_revision=pipeline.envelope_revision,
            prepared=prepared,
        )
        if with_resume
        else None
    )
    runtime = CanonicalOperationRuntime(
        pipeline=pipeline,
        read_terminal=terminal,
        resume_service=resume_service,
    )
    return runtime, resume_service, terminal, prepared


def test_resume_surface_has_no_caller_terminal_profile_or_prepare_inputs() -> None:
    runtime, *_ = _runtime()

    assert set(inspect.signature(runtime.resume).parameters) == {
        "actor_id",
        "execution_id",
    }
    assert set(inspect.signature(runtime.run_resumed_read_only).parameters) == {
        "actor_id",
        "execution_id",
    }


def test_runtime_resume_delegates_to_durable_resume_service_only() -> None:
    runtime, resume_service, terminal, prepared = _runtime()
    assert resume_service is not None

    result = runtime.resume(actor_id="actor-1", execution_id="exec-1")

    assert result is prepared
    assert resume_service.calls == [("actor-1", "exec-1")]
    assert terminal.calls == []


def test_run_resumed_read_only_never_reenters_pipeline_prepare() -> None:
    runtime, resume_service, terminal, prepared = _runtime()
    assert resume_service is not None

    result = runtime.run_resumed_read_only(
        actor_id="actor-1",
        execution_id="exec-1",
    )

    assert resume_service.calls == [("actor-1", "exec-1")]
    assert terminal.calls == [prepared]
    assert result.prepared is prepared


def test_run_resumed_read_only_rejects_non_read_profile_before_terminal() -> None:
    runtime, resume_service, terminal, _ = _runtime(
        prepared_profile=BOUNDED_MUTATION_TERMINAL_PROFILE
    )
    assert resume_service is not None

    with pytest.raises(PermissionError, match="CANONICAL_RUNTIME_READ_PROFILE_MISMATCH"):
        runtime.run_resumed_read_only(
            actor_id="actor-1",
            execution_id="exec-1",
        )

    assert resume_service.calls == [("actor-1", "exec-1")]
    assert terminal.calls == []


def test_run_resumed_read_only_rejects_non_read_capability_before_terminal() -> None:
    runtime, resume_service, terminal, _ = _runtime(
        prepared_capability=GITHUB_CREATE_REF_CAPABILITY
    )
    assert resume_service is not None

    with pytest.raises(PermissionError, match="CANONICAL_RUNTIME_READ_CAPABILITY_MISMATCH"):
        runtime.run_resumed_read_only(
            actor_id="actor-1",
            execution_id="exec-1",
        )

    assert resume_service.calls == [("actor-1", "exec-1")]
    assert terminal.calls == []


def test_run_resumed_read_only_fails_before_resume_without_read_terminal() -> None:
    pipeline, db, permission, registry, current_fence = _pipeline_state()
    prepared = SimpleNamespace(
        terminal_profile=READ_ONLY_TERMINAL_PROFILE,
        capability=GITHUB_READ_REF_CAPABILITY,
    )
    resume_service = StubResumeService(
        db=db,
        permission_authority=permission,
        terminal_profile_registry=registry,
        current_fence=current_fence,
        envelope_revision=pipeline.envelope_revision,
        prepared=prepared,
    )
    runtime = CanonicalOperationRuntime(
        pipeline=pipeline,
        read_terminal=None,
        resume_service=resume_service,
    )

    with pytest.raises(RuntimeError, match="CANONICAL_READ_TERMINAL_NOT_CONFIGURED"):
        runtime.run_resumed_read_only(actor_id="actor-1", execution_id="exec-1")

    assert resume_service.calls == []


def test_runtime_resume_fails_closed_when_service_not_configured() -> None:
    runtime, resume_service, terminal, _ = _runtime(with_resume=False)
    assert resume_service is None

    with pytest.raises(RuntimeError, match="CANONICAL_OPERATION_RESUME_NOT_CONFIGURED"):
        runtime.resume(actor_id="actor-1", execution_id="exec-1")

    assert terminal.calls == []


def _prepared_read() -> object:
    return SimpleNamespace(
        terminal_profile=READ_ONLY_TERMINAL_PROFILE,
        capability=GITHUB_READ_REF_CAPABILITY,
    )


def test_runtime_rejects_resume_service_from_parallel_database() -> None:
    pipeline, _, permission, registry, current_fence = _pipeline_state()
    terminal = StubReadTerminal(current_fence=current_fence)
    resume_service = StubResumeService(
        db=object(),
        permission_authority=permission,
        terminal_profile_registry=registry,
        current_fence=current_fence,
        envelope_revision=pipeline.envelope_revision,
        prepared=_prepared_read(),
    )

    with pytest.raises(ValueError, match="share canonical pipeline database"):
        CanonicalOperationRuntime(
            pipeline=pipeline,
            read_terminal=terminal,
            resume_service=resume_service,
        )


def test_runtime_rejects_parallel_resume_permission_authority() -> None:
    pipeline, db, _, registry, current_fence = _pipeline_state()
    terminal = StubReadTerminal(current_fence=current_fence)
    resume_service = StubResumeService(
        db=db,
        permission_authority=object(),
        terminal_profile_registry=registry,
        current_fence=current_fence,
        envelope_revision=pipeline.envelope_revision,
        prepared=_prepared_read(),
    )

    with pytest.raises(ValueError, match="share canonical pipeline permission authority"):
        CanonicalOperationRuntime(
            pipeline=pipeline,
            read_terminal=terminal,
            resume_service=resume_service,
        )


def test_runtime_rejects_parallel_resume_terminal_profile_registry() -> None:
    pipeline, db, permission, _, current_fence = _pipeline_state()
    terminal = StubReadTerminal(current_fence=current_fence)
    resume_service = StubResumeService(
        db=db,
        permission_authority=permission,
        terminal_profile_registry=SimpleNamespace(resolve=lambda **_: object()),
        current_fence=current_fence,
        envelope_revision=pipeline.envelope_revision,
        prepared=_prepared_read(),
    )

    with pytest.raises(ValueError, match="share canonical terminal profile registry"):
        CanonicalOperationRuntime(
            pipeline=pipeline,
            read_terminal=terminal,
            resume_service=resume_service,
        )


def test_runtime_rejects_resume_envelope_revision_drift() -> None:
    pipeline, db, permission, registry, current_fence = _pipeline_state()
    terminal = StubReadTerminal(current_fence=current_fence)
    resume_service = StubResumeService(
        db=db,
        permission_authority=permission,
        terminal_profile_registry=registry,
        current_fence=current_fence,
        envelope_revision="dispatch-envelope/foreign-r1",
        prepared=_prepared_read(),
    )

    with pytest.raises(ValueError, match="share canonical envelope revision"):
        CanonicalOperationRuntime(
            pipeline=pipeline,
            read_terminal=terminal,
            resume_service=resume_service,
        )


def test_runtime_rejects_resume_fence_different_from_read_terminal() -> None:
    pipeline, db, permission, registry, _ = _pipeline_state()
    terminal = StubReadTerminal(current_fence=object())
    resume_service = StubResumeService(
        db=db,
        permission_authority=permission,
        terminal_profile_registry=registry,
        current_fence=object(),
        envelope_revision=pipeline.envelope_revision,
        prepared=_prepared_read(),
    )

    with pytest.raises(ValueError, match="share current execution fence"):
        CanonicalOperationRuntime(
            pipeline=pipeline,
            read_terminal=terminal,
            resume_service=resume_service,
        )
