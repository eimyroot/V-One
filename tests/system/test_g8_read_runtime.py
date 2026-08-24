from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from voodoo_product.canonical_operation_runtime import CanonicalOperationRuntime
from voodoo_product.canonical_pipeline import CanonicalOperationPipeline
from voodoo_product.canonical_read_terminal import VerifierRuntimeProfile
from voodoo_product.capability_registry import ImmutableCapabilityRegistry
from voodoo_product.config import ProductConfig
from voodoo_product.credential_broker import CredentialBrokerPolicy
from voodoo_product.durable_current_fence import DurableCurrentExecutionFence
from voodoo_product.execution_capsule import ImmutableExecutionCapsuleRegistry
from voodoo_product.g8_read_runtime import G8ReadRuntimePack, create_g8_read_runtime_factory
from voodoo_product.github_actions_runtime import GitHubActionsIsolatedRuntimeProvider
from voodoo_product.permission_authority import DatabasePermissionAuthority
from voodoo_product.service import ProductService
from voodoo_product.trusted_clock import TrustedClockAuthority
from voodoo_product.verifier_credential import VerifierCredentialPolicy

READ_DEFINITION_ID = "c" * 64
ROOTFS_DIGEST = "1" * 64
RESOURCE_DIGEST = "2" * 64
NETWORK_DIGEST = "3" * 64
RUNNER_CREDENTIAL_CLASS = "github.runner-read/scoped-v1"
VERIFIER_CREDENTIAL_CLASS = "github.verifier-read/scoped-v1"
RUNNER_CLASS = "github-actions.docker-isolated/v1"


class FixedClockSource:
    def read(self) -> datetime:
        return datetime(2026, 8, 24, 0, 0, tzinfo=UTC)


class ReadTransport:
    source_identity = "github-api/git-ref/g8-test-v1"

    def read_ref(self, *, repository: str, ref: str) -> str:
        assert repository
        assert ref
        return "a" * 40


class MutationTransport(ReadTransport):
    def create_ref(self, **_: object) -> None:
        raise AssertionError("must never be reachable")


class FakeCapabilityRegistry(ImmutableCapabilityRegistry):
    def __init__(self, definition: object) -> None:
        self.definition = definition

    def definition_by_identity(self, definition_identity: str) -> object:
        if definition_identity != READ_DEFINITION_ID:
            raise LookupError("definition not found")
        return self.definition


class FakeCapsuleRegistry(ImmutableExecutionCapsuleRegistry):
    def __init__(self, capability_registry: ImmutableCapabilityRegistry, capsule: object) -> None:
        self.capability_registry = capability_registry
        self.capsule = capsule

    def capsule_for_definition(self, definition_identity: str) -> object:
        if definition_identity != READ_DEFINITION_ID:
            raise LookupError("capsule not found")
        return self.capsule


class FakeFence(DurableCurrentExecutionFence):
    def __init__(self, *, db: object, trusted_clock: TrustedClockAuthority) -> None:
        self.db = db
        self.trusted_clock = trusted_clock

    def assert_current(self, **_: object) -> None:
        return None


class SnapshotStore:
    def __init__(self, db: object) -> None:
        self.db = db

    def get(self, _: str) -> object:
        raise LookupError("not seeded in composition test")


class SnapshotCreator:
    def __init__(
        self,
        *,
        db: object,
        permission_authority: DatabasePermissionAuthority,
        snapshot_store: SnapshotStore,
        capability_registry: ImmutableCapabilityRegistry,
    ) -> None:
        self.db = db
        self.permission_authority = permission_authority
        self.snapshot_store = snapshot_store
        self.capability_registry = capability_registry

    def create_snapshot(self, **_: object) -> object:
        raise AssertionError("G8 composition test must not issue authority")


class GrantService:
    def __init__(self, *, db: object, capsule_registry: ImmutableExecutionCapsuleRegistry) -> None:
        self.db = db
        self.conformance_authority = SimpleNamespace(capsule_registry=capsule_registry)
        self.grant_issuer = SimpleNamespace(
            execution_binding_authority=SimpleNamespace(registry=capsule_registry)
        )

    def issue_and_store(self, **_: object) -> object:
        raise AssertionError("G8 composition test must not issue a grant")


class OutboxService:
    def __init__(self, *, db: object, grant_service: GrantService) -> None:
        self.db = db
        self.grant_service = grant_service

    def consume_and_enqueue(self, **_: object) -> object:
        raise AssertionError("G8 composition test must not consume a grant")


class Coordinator:
    def admit(self, **_: object) -> object:
        raise AssertionError("G8 composition test must not admit dispatch")

    def acquire(self, **_: object) -> object:
        raise AssertionError("G8 composition test must not acquire a lease")

    def complete(self, **_: object) -> object:
        raise AssertionError("G8 composition test must not complete execution")


class ProfileRegistry:
    def resolve(self, **_: object) -> object:
        raise AssertionError("G8 composition test must not resolve a live request")


def config(tmp_path: Path) -> ProductConfig:
    return ProductConfig(
        environment="staging",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def clock(name: str) -> TrustedClockAuthority:
    return TrustedClockAuthority(
        source_identity=f"trusted-clock/{name}",
        authority_revision=f"trusted-clock/{name}-r1",
        source=FixedClockSource(),
        allowed_environments=frozenset({"staging"}),
    )


def build_fixture(tmp_path: Path) -> SimpleNamespace:
    service = ProductService(config(tmp_path))
    permission = DatabasePermissionAuthority(
        database=service.db,
        authority_revision="database-permission/g8-test-r1",
    )
    definition = SimpleNamespace(
        definition_identity=READ_DEFINITION_ID,
        capability="github.read-ref/v1",
        target_kind="git_ref",
        effect_class="READ_ONLY",
        supported_environments=("staging",),
        production_eligible=False,
    )
    capability_registry = FakeCapabilityRegistry(definition)
    capsule = SimpleNamespace(
        capability_definition_identity=READ_DEFINITION_ID,
        credential_class=RUNNER_CREDENTIAL_CLASS,
        runner_class=RUNNER_CLASS,
        rootfs_digest=ROOTFS_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
    )
    capsule_registry = FakeCapsuleRegistry(capability_registry, capsule)
    snapshot_store = SnapshotStore(service.db)
    snapshot_creator = SnapshotCreator(
        db=service.db,
        permission_authority=permission,
        snapshot_store=snapshot_store,
        capability_registry=capability_registry,
    )
    grant_service = GrantService(db=service.db, capsule_registry=capsule_registry)
    outbox_service = OutboxService(db=service.db, grant_service=grant_service)
    coordinator = Coordinator()
    profile_registry = ProfileRegistry()
    pipeline = CanonicalOperationPipeline(
        snapshot_creator=snapshot_creator,
        grant_service=grant_service,
        outbox_service=outbox_service,
        coordinator=coordinator,
        terminal_profile_registry=profile_registry,
        envelope_revision="dispatch-envelope/g8-r1",
    )
    runner_clock = clock("g8-runner")
    verifier_clock = clock("g8-verifier")
    current_fence = FakeFence(db=service.db, trusted_clock=runner_clock)
    runner_provider = GitHubActionsIsolatedRuntimeProvider(
        provider_instance_id="gha:g8:runner:1",
        runner_class=RUNNER_CLASS,
        environment="staging",
        rootfs_digest=ROOTFS_DIGEST,
        resource_limit_profile_digest=RESOURCE_DIGEST,
        network_policy_digest=NETWORK_DIGEST,
        bootstrap_revision="isolated-runtime-bootstrap/g8-r1",
        activation_revision="read-only-runtime-activation/g8-r1",
    )
    runner_policy = CredentialBrokerPolicy.create(
        credential_class=RUNNER_CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        allowed_capability_definition_identities=(READ_DEFINITION_ID,),
        enabled_environments=("staging",),
        policy_revision="credential-broker-policy/g8-r1",
    )
    verifier_profile = VerifierRuntimeProfile(
        verifier_class="github-actions.verifier/v1",
        provider="github",
        provider_instance_id="gha:g8:verifier:1",
        credential_class=VERIFIER_CREDENTIAL_CLASS,
        rootfs_digest="4" * 64,
        resource_limit_profile_digest="5" * 64,
        network_policy_digest="6" * 64,
        identity_revision="verifier-identity/g8-r1",
        boundary_revision="verification-boundary/g8-r1",
        decision_revision="verifier-credential/g8-r1",
        credential_ttl_seconds=60,
    )
    verifier_policy = VerifierCredentialPolicy.create(
        credential_class=VERIFIER_CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        enabled_environments=("staging",),
        max_ttl_seconds=60,
        policy_revision="verifier-policy/g8-r1",
    )
    return SimpleNamespace(
        service=service,
        permission=permission,
        definition=definition,
        capability_registry=capability_registry,
        capsule=capsule,
        capsule_registry=capsule_registry,
        pipeline=pipeline,
        runner_clock=runner_clock,
        verifier_clock=verifier_clock,
        current_fence=current_fence,
        runner_provider=runner_provider,
        runner_policy=runner_policy,
        verifier_profile=verifier_profile,
        verifier_policy=verifier_policy,
        runner_transport=ReadTransport(),
        verifier_transport=ReadTransport(),
    )


def pack(fixture: SimpleNamespace, **overrides: object) -> G8ReadRuntimePack:
    values: dict[str, object] = {
        "pipeline": fixture.pipeline,
        "capsule_registry": fixture.capsule_registry,
        "current_fence": fixture.current_fence,
        "runner_provider": fixture.runner_provider,
        "runner_transport": fixture.runner_transport,
        "runner_clock": fixture.runner_clock,
        "runner_credential_policy": fixture.runner_policy,
        "runner_credential_decision_revision": "credential-decision/g8-r1",
        "runner_identity_revision": "runner-identity/g8-r1",
        "runner_boundary_revision": "runner-boundary/g8-r1",
        "runner_activation_revision": "runner-activation/g8-r1",
        "runner_observation_revision": "runner-observation/g8-r1",
        "verifier_profile": fixture.verifier_profile,
        "verifier_policy": fixture.verifier_policy,
        "verifier_transport": fixture.verifier_transport,
        "verifier_clock": fixture.verifier_clock,
        "verifier_observation_revision": "verifier-observation/g8-r1",
        "observed_post_state_revision": "observed-post-state/g8-r1",
        "strength_revision": "verification-strength/g8-r1",
        "result_revision": "verification-result/g8-r1",
        "read_capability_definition_identity": READ_DEFINITION_ID,
    }
    values.update(overrides)
    return G8ReadRuntimePack(**values)  # type: ignore[arg-type]


def test_g8_builds_only_read_runtime_over_exact_canonical_authority(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    runtime = pack(fixture).build_runtime(
        service=fixture.service,
        permission_authority=fixture.permission,
    )

    assert isinstance(runtime, CanonicalOperationRuntime)
    assert runtime.pipeline is fixture.pipeline
    assert runtime.read_terminal is not None
    assert runtime.resume_service is not None
    assert runtime.resume_service.db is fixture.service.db
    assert runtime.resume_service.permission_authority is fixture.permission
    assert runtime.resume_service.terminal_profile_registry is fixture.pipeline.terminal_profile_registry
    assert runtime.resume_service.current_fence is fixture.current_fence
    assert runtime.read_terminal.runner_adapter.current_fence is fixture.current_fence
    assert runtime.read_terminal.runner_handler.current_fence is fixture.current_fence
    assert runtime.read_terminal.runner_handler.transport is fixture.runner_transport
    assert runtime.read_terminal.verifier_handler.transport is fixture.verifier_transport
    assert runtime.create_ref_preparer is None
    assert runtime.rollback_preparer is None

    with pytest.raises(RuntimeError, match="A09_CREATE_REF_PREPARER_NOT_CONFIGURED"):
        runtime.prepare_create_ref(
            actor_id="usr-1",
            request_id="req-1",
            idempotency_key="idem-1234",
            correlation_id="corr-1234",
        )


def test_g8_factory_uses_product_composition_arguments_without_hidden_authority(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    factory = create_g8_read_runtime_factory(pack(fixture))

    runtime = factory(fixture.service, fixture.permission)

    assert runtime.pipeline.snapshot_creator.permission_authority is fixture.permission
    assert runtime.resume_service is not None
    assert runtime.resume_service.permission_authority is fixture.permission


def test_g8_rejects_parallel_permission_authority_even_on_same_database(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    parallel = DatabasePermissionAuthority(
        database=fixture.service.db,
        authority_revision="database-permission/parallel-r1",
    )

    with pytest.raises(ValueError, match="product permission authority"):
        pack(fixture).build_runtime(service=fixture.service, permission_authority=parallel)


def test_g8_rejects_capsule_registry_fork_from_grant_authority(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    fork = FakeCapsuleRegistry(fixture.capability_registry, fixture.capsule)

    with pytest.raises(ValueError, match="grant conformance"):
        pack(fixture, capsule_registry=fork).build_runtime(
            service=fixture.service,
            permission_authority=fixture.permission,
        )


def test_g8_rejects_shared_runner_and_verifier_transport(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)

    with pytest.raises(ValueError, match="distinct instances"):
        pack(
            fixture,
            verifier_transport=fixture.runner_transport,
        )


def test_g8_rejects_mutation_shaped_transport(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)

    with pytest.raises(ValueError, match="forbidden provider methods"):
        pack(fixture, runner_transport=MutationTransport())


def test_g8_rejects_runner_verifier_credential_class_collapse(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    collapsed_profile = VerifierRuntimeProfile(
        verifier_class="github-actions.verifier/v1",
        provider="github",
        provider_instance_id="gha:g8:verifier:1",
        credential_class=RUNNER_CREDENTIAL_CLASS,
        rootfs_digest="4" * 64,
        resource_limit_profile_digest="5" * 64,
        network_policy_digest="6" * 64,
        identity_revision="verifier-identity/g8-r1",
        boundary_revision="verification-boundary/g8-r1",
        decision_revision="verifier-credential/g8-r1",
        credential_ttl_seconds=60,
    )
    collapsed_policy = VerifierCredentialPolicy.create(
        credential_class=RUNNER_CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        enabled_environments=("staging",),
        max_ttl_seconds=60,
        policy_revision="verifier-policy/g8-collapse-r1",
    )

    with pytest.raises(PermissionError, match="credential classes must be distinct"):
        pack(
            fixture,
            verifier_profile=collapsed_profile,
            verifier_policy=collapsed_policy,
        ).build_runtime(
            service=fixture.service,
            permission_authority=fixture.permission,
        )


def test_g8_rejects_production_widening(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    fixture.definition.supported_environments = ("staging", "production")
    runner_policy = CredentialBrokerPolicy.create(
        credential_class=RUNNER_CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        allowed_capability_definition_identities=(READ_DEFINITION_ID,),
        enabled_environments=("production", "staging"),
        policy_revision="credential-broker-policy/g8-prod-r1",
    )
    verifier_policy = VerifierCredentialPolicy.create(
        credential_class=VERIFIER_CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        enabled_environments=("production", "staging"),
        max_ttl_seconds=60,
        policy_revision="verifier-policy/g8-prod-r1",
    )

    with pytest.raises(PermissionError, match="cannot enable production"):
        pack(
            fixture,
            runner_credential_policy=runner_policy,
            verifier_policy=verifier_policy,
        ).build_runtime(
            service=fixture.service,
            permission_authority=fixture.permission,
        )


def test_g8_rejects_current_fence_from_parallel_database(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    other_service = ProductService(config(tmp_path / "other"))
    foreign_fence = FakeFence(db=other_service.db, trusted_clock=fixture.runner_clock)

    with pytest.raises(ValueError, match="current fence must use the product database"):
        pack(fixture, current_fence=foreign_fence).build_runtime(
            service=fixture.service,
            permission_authority=fixture.permission,
        )
