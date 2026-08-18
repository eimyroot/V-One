from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from voodoo_product.credential_broker import CredentialBrokerPolicy, ImmutableCredentialBroker
from voodoo_product.d4b_live_pilot import (
    AUTHORITY_REVISION,
    CREDENTIAL_CLASS,
    ENVIRONMENT,
    LEASE_REVISION,
    RUNNER_CLASS,
    build_capability,
    build_capsule,
    seed_pilot_admission,
)
from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.durable_current_fence import DurableCurrentExecutionFence
from voodoo_product.execution_contract import ExecutionTarget
from voodoo_product.execution_lease import ExecutionFenceDenied
from voodoo_product.execution_lease_persistence import COMPLETED, DurableExecutionLeaseService
from voodoo_product.github_actions_runtime import GitHubActionsIsolatedRuntimeProvider
from voodoo_product.github_read_provider import GitHubRefReadHandler
from voodoo_product.isolated_runner import IsolatedRunnerAdapter, IsolatedRuntimeProvider
from voodoo_product.trusted_clock import TrustedClockAuthority

ROOTFS_DIGEST = "1" * 64
RESOURCE_DIGEST = "2" * 64
NETWORK_DIGEST = "3" * 64


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def read(self) -> datetime:
        return self.value


class FakeGitHubReadTransport:
    source_identity = "github-api/fake-test"

    def __init__(self, events: list[str]) -> None:
        self.events = events

    def read_ref(self, *, repository: str, ref: str) -> str:
        self.events.append(f"read:{repository}:{ref}")
        return "a" * 40


def build_runtime(tmp_path: Path):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    target = ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={"repository": "nulleimy/V-One", "ref": "refs/heads/main"},
    )
    definition = build_capability()
    capsule = build_capsule(
        definition=definition,
        rootfs_digest=ROOTFS_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
    )
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    admission = seed_pilot_admission(
        database=database,
        definition=definition,
        capsule=capsule,
        target=target,
        now=now,
    )
    clock = MutableClock(now)
    trusted_clock = TrustedClockAuthority(
        source_identity="trusted-clock/d4b-test",
        authority_revision="trusted-clock/d4b-test-r1",
        source=clock,
        allowed_environments=frozenset({ENVIRONMENT}),
    )
    lease_service = DurableExecutionLeaseService(
        database=database,
        trusted_clock=trusted_clock,
        lease_seconds=300,
        lease_revision=LEASE_REVISION,
        authority_revision=AUTHORITY_REVISION,
    )
    lease = lease_service.acquire(admission_id=admission.admission_id).lease
    fence = DurableCurrentExecutionFence(database=database, trusted_clock=trusted_clock)
    policy = CredentialBrokerPolicy.create(
        credential_class=CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        allowed_capability_definition_identities=(definition.definition_identity,),
        enabled_environments=(ENVIRONMENT,),
        policy_revision="credential-broker-policy/d4b-test-r1",
    )
    broker = ImmutableCredentialBroker(
        policies=(policy,),
        decision_revision="credential-access-decision/d4b-test-r1",
    )
    provider = GitHubActionsIsolatedRuntimeProvider(
        provider_instance_id="gha:test:1:verify:container",
        runner_class=RUNNER_CLASS,
        environment=ENVIRONMENT,
        rootfs_digest=ROOTFS_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
        bootstrap_revision="runtime-bootstrap/d4b-test-r1",
        activation_revision="runtime-activation/d4b-test-r1",
    )
    adapter = IsolatedRunnerAdapter(
        provider=provider,
        credential_broker=broker,
        current_fence=fence,
        identity_revision="runner-identity/d4b-test-r1",
        boundary_revision="runner-boundary/d4b-test-r1",
        activation_revision="runtime-activation/d4b-test-r1",
    )
    return (
        now,
        target,
        definition,
        capsule,
        database,
        clock,
        trusted_clock,
        lease_service,
        lease,
        fence,
        provider,
        adapter,
    )


def test_durable_current_fence_accepts_exact_active_lease_and_denies_expiry(tmp_path: Path) -> None:
    (
        now,
        _,
        _,
        _,
        _,
        clock,
        _,
        _,
        lease,
        fence,
        _,
        _,
    ) = build_runtime(tmp_path)

    fence.assert_current(lease=lease)
    clock.value = now + timedelta(seconds=300)

    with pytest.raises(ExecutionFenceDenied) as denied:
        fence.assert_current(lease=lease)
    assert denied.value.reason == "LEASE_EXPIRED"


def test_d3_to_d4_read_runs_under_exact_durable_fence_and_records_completion(tmp_path: Path) -> None:
    (
        _,
        target,
        definition,
        capsule,
        _,
        _,
        trusted_clock,
        lease_service,
        lease,
        fence,
        provider,
        adapter,
    ) = build_runtime(tmp_path)
    events: list[str] = []
    assert isinstance(provider, IsolatedRuntimeProvider)

    prepared = adapter.prepare(lease=lease, capsule=capsule, definition=definition)
    activation = adapter.activate(prepared=prepared)
    handler = GitHubRefReadHandler(
        transport=FakeGitHubReadTransport(events),
        current_fence=fence,
        trusted_clock=trusted_clock,
        observation_revision="github-ref-observation/d4b-test-r1",
    )

    observation = handler.observe_ref(
        prepared=prepared,
        activation=activation,
        target=target,
    )
    completion = lease_service.complete(
        lease_id=lease.lease_id,
        completion_digest=observation.observation_digest,
    )

    assert events == ["read:nulleimy/V-One:refs/heads/main"]
    assert observation.commit_sha == "a" * 40
    assert observation.lease_id == lease.lease_id
    assert observation.execution_epoch == lease.execution_epoch
    assert observation.runtime_activation_digest == activation.activation_digest
    assert completion.outcome == COMPLETED


def test_d4b_workflow_is_read_only_and_enforces_container_boundary() -> None:
    workflow = Path(".github/workflows/d4b-live-read.yml").read_text(encoding="utf-8")

    required = (
        "permissions:\n  contents: read",
        "persist-credentials: false",
        "--read-only",
        "--cap-drop=ALL",
        "no-new-privileges",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=256",
        "DOCKER-USER",
        "api.github.com",
        "D4B_LIVE_GOVERNED_READ=PASS",
    )
    for marker in required:
        assert marker in workflow

    forbidden = (
        "contents: write",
        "pull-requests: write",
        "git push",
        "gh api --method POST",
        "gh api --method PATCH",
        "gh api --method DELETE",
    )
    for marker in forbidden:
        assert marker not in workflow
