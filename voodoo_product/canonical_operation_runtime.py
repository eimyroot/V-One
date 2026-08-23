from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .a09_rollback_orchestration import A09PreparedRollback, A09RollbackPreparer
from .a09_write_orchestration import A09CreateRefPreparer, A09PreparedCreateRef
from .canonical_pipeline import CanonicalOperationPipeline, CanonicalPreparedExecution
from .canonical_read_terminal import CanonicalGitHubReadTerminal, CanonicalReadTerminalResult
from .controlled_write import GITHUB_CREATE_REF_CAPABILITY
from .github_read_provider import GITHUB_READ_REF_CAPABILITY
from .rollback_control import GITHUB_DELETE_REF_CAPABILITY
from .terminal_profile import (
    BOUNDED_MUTATION_TERMINAL_PROFILE,
    READ_ONLY_TERMINAL_PROFILE,
)


class _Pipeline(Protocol):
    def prepare(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
        required_terminal_profile: str | None = None,
        required_capability: str | None = None,
    ) -> CanonicalPreparedExecution: ...


@dataclass(frozen=True, slots=True)
class CanonicalOperationRuntime:
    """Single profile-routed ProductComposition runtime over accepted V-One contracts.

    The runtime deliberately has no generic `execute(profile=...)` method. Terminal profile is derived
    by CanonicalOperationPipeline from the exact capability allowlist. READ is the only route that can
    execute here; bounded write routes only produce A09 preflight plans and never invoke a provider
    mutation transport. Every route passes an internal expected profile/capability constraint so a
    mismatched reviewed request fails before Grant issuance/consumption.
    """

    pipeline: CanonicalOperationPipeline
    read_terminal: CanonicalGitHubReadTerminal | None = None
    create_ref_preparer: A09CreateRefPreparer | None = None
    rollback_preparer: A09RollbackPreparer | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pipeline, CanonicalOperationPipeline):
            raise ValueError("pipeline must be CanonicalOperationPipeline")
        if self.read_terminal is not None and not isinstance(
            self.read_terminal, CanonicalGitHubReadTerminal
        ):
            raise ValueError("read_terminal is invalid")
        if self.create_ref_preparer is not None and not isinstance(
            self.create_ref_preparer, A09CreateRefPreparer
        ):
            raise ValueError("create_ref_preparer is invalid")
        if self.rollback_preparer is not None and not isinstance(
            self.rollback_preparer, A09RollbackPreparer
        ):
            raise ValueError("rollback_preparer is invalid")

    def _prepare(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
        required_terminal_profile: str,
        required_capability: str,
    ) -> CanonicalPreparedExecution:
        return self.pipeline.prepare(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            required_terminal_profile=required_terminal_profile,
            required_capability=required_capability,
        )

    def run_read_only(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> CanonicalReadTerminalResult:
        prepared = self._prepare(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            required_terminal_profile=READ_ONLY_TERMINAL_PROFILE,
            required_capability=GITHUB_READ_REF_CAPABILITY,
        )
        if prepared.terminal_profile != READ_ONLY_TERMINAL_PROFILE:
            raise PermissionError("CANONICAL_RUNTIME_READ_PROFILE_MISMATCH")
        if prepared.capability != GITHUB_READ_REF_CAPABILITY:
            raise PermissionError("CANONICAL_RUNTIME_READ_CAPABILITY_MISMATCH")
        if self.read_terminal is None:
            raise RuntimeError("CANONICAL_READ_TERMINAL_NOT_CONFIGURED")
        return self.read_terminal.run(prepared=prepared)

    def prepare_create_ref(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> A09PreparedCreateRef:
        prepared = self._prepare(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            required_terminal_profile=BOUNDED_MUTATION_TERMINAL_PROFILE,
            required_capability=GITHUB_CREATE_REF_CAPABILITY,
        )
        if prepared.terminal_profile != BOUNDED_MUTATION_TERMINAL_PROFILE:
            raise PermissionError("CANONICAL_RUNTIME_WRITE_PROFILE_MISMATCH")
        if prepared.capability != GITHUB_CREATE_REF_CAPABILITY:
            raise PermissionError("CANONICAL_RUNTIME_CREATE_REF_CAPABILITY_MISMATCH")
        if self.create_ref_preparer is None:
            raise RuntimeError("A09_CREATE_REF_PREPARER_NOT_CONFIGURED")
        return self.create_ref_preparer.prepare(prepared=prepared)

    def prepare_rollback(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
        observed_ref_sha: str,
        predelete_observation_digest: str,
    ) -> A09PreparedRollback:
        prepared = self._prepare(
            actor_id=actor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            required_terminal_profile=BOUNDED_MUTATION_TERMINAL_PROFILE,
            required_capability=GITHUB_DELETE_REF_CAPABILITY,
        )
        if prepared.terminal_profile != BOUNDED_MUTATION_TERMINAL_PROFILE:
            raise PermissionError("CANONICAL_RUNTIME_ROLLBACK_PROFILE_MISMATCH")
        if prepared.capability != GITHUB_DELETE_REF_CAPABILITY:
            raise PermissionError("CANONICAL_RUNTIME_ROLLBACK_CAPABILITY_MISMATCH")
        if self.rollback_preparer is None:
            raise RuntimeError("A09_ROLLBACK_PREPARER_NOT_CONFIGURED")
        return self.rollback_preparer.prepare(
            prepared=prepared,
            observed_ref_sha=observed_ref_sha,
            predelete_observation_digest=predelete_observation_digest,
        )
