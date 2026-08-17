from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voodoo_product.durable_coordinator import DurableCoordinator, NativeDurableCoordinator


class FakeInboxService:
    def __init__(self, database: object, calls: list[tuple[object, ...]]) -> None:
        self.db = database
        self.calls = calls
        self.result = object()

    def admit(self, *, envelope: object) -> object:
        self.calls.append(("admit", envelope))
        return self.result


class FakeLeaseService:
    def __init__(self, database: object, calls: list[tuple[object, ...]]) -> None:
        self.db = database
        self.calls = calls
        self.acquire_result = object()
        self.complete_result = object()

    def acquire(self, *, admission_id: str) -> object:
        self.calls.append(("acquire", admission_id))
        return self.acquire_result

    def complete(self, *, lease_id: str, completion_digest: str) -> object:
        self.calls.append(("complete", lease_id, completion_digest))
        return self.complete_result


def build_coordinator() -> tuple[
    NativeDurableCoordinator,
    FakeInboxService,
    FakeLeaseService,
    list[tuple[object, ...]],
]:
    database = object()
    calls: list[tuple[object, ...]] = []
    inbox = FakeInboxService(database, calls)
    leases = FakeLeaseService(database, calls)
    coordinator = NativeDurableCoordinator(
        inbox_service=inbox,
        lease_service=leases,
    )
    return coordinator, inbox, leases, calls


def test_native_coordinator_satisfies_engine_independent_protocol() -> None:
    coordinator, _, _, _ = build_coordinator()

    assert isinstance(coordinator, DurableCoordinator)


def test_coordinator_preserves_released_transition_boundaries() -> None:
    coordinator, inbox, leases, calls = build_coordinator()
    envelope = object()
    admission_id = "a" * 64
    lease_id = "b" * 64
    completion_digest = "c" * 64

    admitted = coordinator.admit(envelope=envelope)  # type: ignore[arg-type]
    acquired = coordinator.acquire(admission_id=admission_id)
    completed = coordinator.complete(
        lease_id=lease_id,
        completion_digest=completion_digest,
    )

    assert admitted is inbox.result
    assert acquired is leases.acquire_result
    assert completed is leases.complete_result
    assert calls == [
        ("admit", envelope),
        ("acquire", admission_id),
        ("complete", lease_id, completion_digest),
    ]


def test_coordinator_requires_one_shared_durable_database_boundary() -> None:
    calls: list[tuple[object, ...]] = []

    with pytest.raises(ValueError, match="share one durable database boundary"):
        NativeDurableCoordinator(
            inbox_service=FakeInboxService(object(), calls),
            lease_service=FakeLeaseService(object(), calls),
        )


def test_coordinator_rejects_services_without_durable_database_boundary() -> None:
    class MissingDatabaseInbox:
        def admit(self, *, envelope: object) -> object:
            return envelope

    class MissingDatabaseLease:
        def acquire(self, *, admission_id: str) -> object:
            return admission_id

        def complete(self, *, lease_id: str, completion_digest: str) -> object:
            return (lease_id, completion_digest)

    with pytest.raises(ValueError, match="expose their durable database boundary"):
        NativeDurableCoordinator(
            inbox_service=MissingDatabaseInbox(),  # type: ignore[arg-type]
            lease_service=MissingDatabaseLease(),  # type: ignore[arg-type]
        )


def test_c5_surface_has_no_provider_execution_entrypoint() -> None:
    public_methods = {
        name
        for name, value in NativeDurableCoordinator.__dict__.items()
        if callable(value) and not name.startswith("_")
    }

    assert public_methods == {"admit", "acquire", "complete"}


def test_c5_module_has_no_external_engine_or_provider_runtime_import() -> None:
    source_path = (
        Path(__file__).resolve().parents[2]
        / "voodoo_product"
        / "durable_coordinator.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_roots = {
        "dbos",
        "httpx",
        "requests",
        "restate",
        "subprocess",
        "temporalio",
    }
    assert not {
        module
        for module in imported_modules
        if module.split(".", 1)[0] in forbidden_roots
    }
