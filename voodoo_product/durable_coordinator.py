from __future__ import annotations

from typing import Protocol, runtime_checkable

from .dispatch_envelope import DispatchEnvelope
from .dispatch_inbox_persistence import DispatchInboxPersistenceResult
from .execution_lease_persistence import (
    DurableExecutionCompletionResult,
    DurableExecutionLeaseResult,
)


@runtime_checkable
class DurableCoordinator(Protocol):
    """Engine-independent C5 seam over the released C3/C4 durable contracts.

    The protocol deliberately exposes only already-released durable transitions. It does not
    manufacture authority, execute a handler, obtain credentials, contact a provider, or claim
    exactly-once effects.
    """

    def admit(self, *, envelope: DispatchEnvelope) -> DispatchInboxPersistenceResult:
        """Durably admit or deduplicate one C2 dispatch envelope through C3."""
        ...

    def acquire(self, *, admission_id: str) -> DurableExecutionLeaseResult:
        """Acquire or reacquire the current C4 execution epoch lease."""
        ...

    def complete(
        self,
        *,
        lease_id: str,
        completion_digest: str,
    ) -> DurableExecutionCompletionResult:
        """Record C4 durable completion only when the lease fence remains current."""
        ...


class _DurableInboxService(Protocol):
    db: object

    def admit(self, *, envelope: DispatchEnvelope) -> DispatchInboxPersistenceResult: ...


class _DurableLeaseService(Protocol):
    db: object

    def acquire(self, *, admission_id: str) -> DurableExecutionLeaseResult: ...

    def complete(
        self,
        *,
        lease_id: str,
        completion_digest: str,
    ) -> DurableExecutionCompletionResult: ...


class NativeDurableCoordinator:
    """Current native coordinator composition for Phase C.

    C3 and C4 remain the owners of persistence and concurrency semantics. This class is only a
    stable orchestration seam so a future durable engine can implement the same protocol without
    leaking engine-specific state into the V-One trust kernel.

    Commit boundaries intentionally remain visible:

    * ``admit`` commits durable inbox truth before any lease can be acquired;
    * ``acquire`` commits the current epoch/lease before any future worker may act;
    * ``complete`` delegates to the C4 fence, so a stale epoch cannot record completion.

    There is no provider-effect method in C5. Phase D must place any read-only worker behind the
    current lease/epoch fence and preserve the same authority lineage.
    """

    def __init__(
        self,
        *,
        inbox_service: _DurableInboxService,
        lease_service: _DurableLeaseService,
    ) -> None:
        inbox_db = getattr(inbox_service, "db", None)
        lease_db = getattr(lease_service, "db", None)
        if inbox_db is None or lease_db is None:
            raise ValueError("C5 services must expose their durable database boundary")
        if inbox_db is not lease_db:
            raise ValueError("C5 services must share one durable database boundary")
        if not callable(getattr(inbox_service, "admit", None)):
            raise ValueError("inbox_service must implement admit")
        if not callable(getattr(lease_service, "acquire", None)):
            raise ValueError("lease_service must implement acquire")
        if not callable(getattr(lease_service, "complete", None)):
            raise ValueError("lease_service must implement complete")

        self._inbox_service = inbox_service
        self._lease_service = lease_service

    def admit(self, *, envelope: DispatchEnvelope) -> DispatchInboxPersistenceResult:
        return self._inbox_service.admit(envelope=envelope)

    def acquire(self, *, admission_id: str) -> DurableExecutionLeaseResult:
        return self._lease_service.acquire(admission_id=admission_id)

    def complete(
        self,
        *,
        lease_id: str,
        completion_digest: str,
    ) -> DurableExecutionCompletionResult:
        return self._lease_service.complete(
            lease_id=lease_id,
            completion_digest=completion_digest,
        )
