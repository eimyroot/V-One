from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from voodoo_product import g8_read_runtime as g8_module
from voodoo_product.canonical_operation_runtime import CanonicalOperationRuntime
from voodoo_product.canonical_pipeline import CanonicalOperationPipeline
from voodoo_product.canonical_read_terminal import VerifierRuntimeProfile
from voodoo_product.capability_registry import ImmutableCapabilityRegistry
from voodoo_product.config import ProductConfig
from voodoo_product.credential_broker import CredentialBrokerPolicy
from voodoo_product.durable_current_fence import DurableCurrentExecutionFence
from voodoo_product.execution_capsule import ImmutableExecutionCapsuleRegistry
from voodoo_product.g8_read_runtime import (
    G8BoundGitHubReadTransport,
    G8ReadRuntimePack,
    create_g8_read_runtime_factory,
)
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
RUNNER_TOKEN = "runner-g8-test-token"
VERIFIER_TOKEN = "verifier-g8-test-token"
RUNNER_PRINCIPAL = "github-principal/user/101"
VERIFIER_PRINCIPAL = "github-principal/user/202"

_REAL_PRINCIPAL_OBSERVER = g8_module._observe_github_credential_principal


class FixedClockSource:
    def read(self) -> datetime:
        return datetime(2026, 8, 24, 0, 0, tzinfo=UTC)


class MutationTransport(G8BoundGitHubReadTransport):
    def create_ref(self, **_: object) -> None:
        raise AssertionError("must never be reachable")


class StructuralReadTransport:
    source_identity = "github-api/structural-only/g8-test-v1"

    def read_ref(self, *, repository: str, ref: str) -> str:
        assert repository
        assert ref
        return "a" * 40


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


class BypassFence(DurableCurrentExecutionFence):
    def assert_current(self, **_: object) -> None:
        return None


class ProductServiceSubclass(ProductService):
    pass


class PermissionAuthoritySubclass(DatabasePermissionAuthority):
    pass


class BypassPack(G8ReadRuntimePack):
    def build_runtime(self, **_: object) -> CanonicalOperationRuntime:
        raise AssertionError("subclass build_runtime must never be retained")


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


@pytest.fixture(autouse=True)
def provider_principal_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    def observe(token: str) -> str:
        if token == RUNNER_TOKEN:
            return RUNNER_PRINCIPAL
        if token == VERIFIER_TOKEN:
            return VERIFIER_PRINCIPAL
        principal_id = sum((index + 1) * ord(character) for index, character in enumerate(token))
        return f"github-principal/user/{principal_id}"

    monkeypatch.setattr(g8_module, "_observe_github_credential_principal", observe)


def config(tmp_path: Path, *, environment: str = "staging") -> ProductConfig:
    return ProductConfig(
        environment=environment,
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


def bound_transport(*, token: str, credential_class: str) -> G8BoundGitHubReadTransport:
    return G8BoundGitHubReadTransport(
        token=token,
        credential_class=credential_class,
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
    current_fence = DurableCurrentExecutionFence(
        database=service.db,
        trusted_clock=runner_clock,
    )
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
        runner_transport=bound_transport(
            token=RUNNER_TOKEN,
            credential_class=RUNNER_CREDENTIAL_CLASS,
        ),
        verifier_transport=bound_transport(
            token=VERIFIER_TOKEN,
            credential_class=VERIFIER_CREDENTIAL_CLASS,
        ),
    )


def pack_values(fixture: SimpleNamespace, **overrides: object) -> dict[str, object]:
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
    return values


def pack(fixture: SimpleNamespace, **overrides: object) -> G8ReadRuntimePack:
    return G8ReadRuntimePack(**pack_values(fixture, **overrides))  # type: ignore[arg-type]


def _closure_binding_registry(transport: G8BoundGitHubReadTransport) -> object:
    property_getter = type(transport).credential_class.fget
    assert property_getter is not None
    assert property_getter.__closure__ is not None
    binding_for = property_getter.__closure__[0].cell_contents
    assert binding_for.__closure__ is not None
    return binding_for.__closure__[0].cell_contents


def test_g8_bound_transport_reattests_principal_from_exact_retained_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []

    def observe(token: str) -> str:
        observed.append(token)
        return "github-principal/user/909"

    monkeypatch.setattr(g8_module, "_observe_github_credential_principal", observe)
    transport = G8BoundGitHubReadTransport(
        token="provider-attested-token",
        credential_class=RUNNER_CREDENTIAL_CLASS,
    )

    assert observed == ["provider-attested-token"]
    assert transport.credential_principal_identity == "github-principal/user/909"
    assert observed == ["provider-attested-token", "provider-attested-token"]
    assert transport.credential_class == RUNNER_CREDENTIAL_CLASS
    assert not hasattr(transport, "__dict__")

    with pytest.raises((AttributeError, TypeError)):
        transport.credential_principal_identity = "github-principal/user/1"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        transport.credential_class = "github.widened/scoped-v1"  # type: ignore[misc]


def test_g8_bound_transport_exposes_no_caller_mutable_credential_slots() -> None:
    transport = G8BoundGitHubReadTransport(
        token="closure-owned-token",
        credential_class=RUNNER_CREDENTIAL_CLASS,
    )

    for field in (
        "_G8BoundGitHubReadTransport__token",
        "_G8BoundGitHubReadTransport__token_fingerprint",
        "_G8BoundGitHubReadTransport__credential_class",
        "_G8BoundGitHubReadTransport__attested_principal",
    ):
        with pytest.raises(AttributeError):
            object.__setattr__(transport, field, "replacement")

    with pytest.raises(PermissionError, match="unpinned credential source"):
        transport.read_ref(repository="nulleimy/V-One", ref="refs/heads/main")


def test_g8_bound_transport_initialization_is_one_shot() -> None:
    transport = G8BoundGitHubReadTransport(
        token="one-shot-original-token",
        credential_class=RUNNER_CREDENTIAL_CLASS,
    )
    original_principal = transport.credential_principal_identity

    with pytest.raises(RuntimeError, match="already initialized"):
        transport.__init__(
            token=RUNNER_TOKEN,
            credential_class=VERIFIER_CREDENTIAL_CLASS,
        )

    assert transport.credential_class == RUNNER_CREDENTIAL_CLASS
    assert transport.credential_principal_identity == original_principal


def test_g8_runtime_pair_uses_pinned_get_only_provider_after_module_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_fixture(tmp_path)
    runtime = pack(fixture).build_runtime(
        service=fixture.service,
        permission_authority=fixture.permission,
    )
    runner_effect_transport = runtime.read_terminal.runner_handler.transport
    observed_tokens: list[str] = []
    requests: list[tuple[str, str, dict[str, str]]] = []

    def observe(candidate: str) -> str:
        observed_tokens.append(candidate)
        if candidate == RUNNER_TOKEN:
            return RUNNER_PRINCIPAL
        if candidate == VERIFIER_TOKEN:
            return VERIFIER_PRINCIPAL
        raise AssertionError("unexpected credential")

    class Response:
        status = 200

        @staticmethod
        def read() -> bytes:
            return b'{"object":{"sha":"' + (b"a" * 40) + b'"}}'

    class Connection:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert (host, port, timeout) == ("api.github.com", 443, 15)

        def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
            requests.append((method, path, headers))

        @staticmethod
        def getresponse() -> Response:
            return Response()

        @staticmethod
        def close() -> None:
            return None

    class ReplacementTransport:
        def __init__(self, *, token: str) -> None:
            raise AssertionError(f"module-global replacement must not receive {token!r}")

        @staticmethod
        def read_ref(*, repository: str, ref: str) -> str:
            raise AssertionError(f"replacement must not read {repository}:{ref}")

    monkeypatch.setattr(g8_module, "_observe_github_credential_principal", observe)
    monkeypatch.setattr(g8_module.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(g8_module, "GitHubApiRefReadTransport", ReplacementTransport)

    result = runner_effect_transport.read_ref(
        repository="nulleimy/V-One",
        ref="refs/heads/main",
    )

    assert result == "a" * 40
    assert observed_tokens == [RUNNER_TOKEN, VERIFIER_TOKEN, RUNNER_TOKEN]
    assert len(requests) == 1
    method, path, headers = requests[0]
    assert method == "GET"
    assert path == "/repos/nulleimy/V-One/git/ref/heads/main"
    assert headers["Authorization"] == f"Bearer {RUNNER_TOKEN}"


def test_g8_runtime_pair_rejects_introspective_closure_registry_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_fixture(tmp_path)
    runtime = pack(fixture).build_runtime(
        service=fixture.service,
        permission_authority=fixture.permission,
    )
    verifier_effect_transport = runtime.read_terminal.verifier_handler.transport
    registry = _closure_binding_registry(fixture.verifier_transport)
    registry[fixture.verifier_transport] = g8_module._CredentialBinding(  # type: ignore[index]
        token=RUNNER_TOKEN,
        token_fingerprint=g8_module._token_fingerprint(RUNNER_TOKEN),
        credential_class=VERIFIER_CREDENTIAL_CLASS,
        attested_principal=RUNNER_PRINCIPAL,
    )

    class ForbiddenProviderTransport:
        def __init__(self, *, token: str) -> None:
            raise AssertionError(f"provider READ must not be reached with {token!r}")

    monkeypatch.setattr(g8_module, "GitHubApiRefReadTransport", ForbiddenProviderTransport)

    with pytest.raises(PermissionError, match="Verifier credential changed after runtime pinning"):
        verifier_effect_transport.read_ref(
            repository="nulleimy/V-One",
            ref="refs/heads/main",
        )


def test_real_principal_observer_uses_authenticated_github_user_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, str, dict[str, str]]] = []

    class Response:
        status = 200

        @staticmethod
        def read() -> bytes:
            return b'{"id":4242,"type":"User"}'

    class Connection:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert (host, port, timeout) == ("api.github.com", 443, 15)

        def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
            requests.append((method, path, headers))

        @staticmethod
        def getresponse() -> Response:
            return Response()

        @staticmethod
        def close() -> None:
            return None

    monkeypatch.setattr(g8_module.http.client, "HTTPSConnection", Connection)

    principal = _REAL_PRINCIPAL_OBSERVER("exact-provider-token")

    assert principal == "github-principal/user/4242"
    assert len(requests) == 1
    method, path, headers = requests[0]
    assert method == "GET"
    assert path == "/user"
    assert headers["Authorization"] == "Bearer exact-provider-token"


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

    runtime_fence = runtime.resume_service.current_fence
    assert type(runtime_fence) is DurableCurrentExecutionFence
    assert runtime_fence is not fixture.current_fence
    assert runtime_fence.db is fixture.service.db
    assert runtime_fence.trusted_clock is fixture.runner_clock
    assert runtime.read_terminal.runner_adapter.current_fence is runtime_fence
    assert runtime.read_terminal.runner_handler.current_fence is runtime_fence

    runner_effect_transport = runtime.read_terminal.runner_handler.transport
    verifier_effect_transport = runtime.read_terminal.verifier_handler.transport
    assert runner_effect_transport is not fixture.runner_transport
    assert verifier_effect_transport is not fixture.verifier_transport
    assert runner_effect_transport.runner_transport is fixture.runner_transport
    assert runner_effect_transport.verifier_transport is fixture.verifier_transport
    assert verifier_effect_transport.runner_transport is fixture.runner_transport
    assert verifier_effect_transport.verifier_transport is fixture.verifier_transport
    assert runner_effect_transport.runner_pin == verifier_effect_transport.runner_pin
    assert runner_effect_transport.verifier_pin == verifier_effect_transport.verifier_pin
    assert (
        runner_effect_transport.source_implementation_pin
        == verifier_effect_transport.source_implementation_pin
    )
    assert runner_effect_transport.provider_effect_pin == verifier_effect_transport.provider_effect_pin
    with pytest.raises(AttributeError):
        runner_effect_transport.runner_pin = verifier_effect_transport.verifier_pin  # type: ignore[misc]
    with pytest.raises(AttributeError):
        runner_effect_transport.provider_effect_pin = object()  # type: ignore[misc]

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


def test_g8_factory_rejects_runtime_pack_subclass_virtual_dispatch(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    bypass = BypassPack(**pack_values(fixture))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="exact G8ReadRuntimePack"):
        create_g8_read_runtime_factory(bypass)


def test_g8_rejects_product_service_subclass(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture")
    subclass_service = ProductServiceSubclass(config(tmp_path / "subclass"))
    permission = DatabasePermissionAuthority(
        database=subclass_service.db,
        authority_revision="database-permission/g8-subclass-r1",
    )

    with pytest.raises(ValueError, match="exact ProductService"):
        pack(fixture).build_runtime(
            service=subclass_service,
            permission_authority=permission,
        )


def test_g8_rejects_permission_authority_subclass(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    subclass_permission = PermissionAuthoritySubclass(
        database=fixture.service.db,
        authority_revision="database-permission/g8-subclass-r1",
    )

    with pytest.raises(ValueError, match="exact DatabasePermissionAuthority"):
        pack(fixture).build_runtime(
            service=fixture.service,
            permission_authority=subclass_permission,
        )


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
        pack(fixture, verifier_transport=fixture.runner_transport)


def test_g8_rejects_distinct_tokens_for_same_provider_principal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_fixture(tmp_path)
    monkeypatch.setattr(
        g8_module,
        "_observe_github_credential_principal",
        lambda token: RUNNER_PRINCIPAL,
    )
    verifier = bound_transport(
        token="different-token-same-provider-principal",
        credential_class=VERIFIER_CREDENTIAL_CLASS,
    )

    with pytest.raises(ValueError, match="provider principals must be distinct"):
        pack(fixture, verifier_transport=verifier)


def test_g8_rejects_shared_underlying_credential_material(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        g8_module,
        "_observe_github_credential_principal",
        lambda token: "github-principal/user/303",
    )
    fixture = build_fixture(tmp_path)
    verifier = bound_transport(
        token=RUNNER_TOKEN,
        credential_class=VERIFIER_CREDENTIAL_CLASS,
    )

    with pytest.raises(ValueError, match="credential material must be distinct"):
        pack(fixture, verifier_transport=verifier)


def test_g8_rejects_structural_transport_even_if_interface_looks_read_only(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)

    with pytest.raises(ValueError, match="exact G8BoundGitHubReadTransport"):
        pack(fixture, runner_transport=StructuralReadTransport())


def test_g8_rejects_subclass_that_can_add_mutation_surface(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    mutating = MutationTransport(
        token="mutating-g8-test-token",
        credential_class=RUNNER_CREDENTIAL_CLASS,
    )

    with pytest.raises(ValueError, match="exact G8BoundGitHubReadTransport"):
        pack(fixture, runner_transport=mutating)


def test_g8_rejects_subclass_that_can_override_durable_fence(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    bypass = BypassFence(
        database=fixture.service.db,
        trusted_clock=fixture.runner_clock,
    )

    with pytest.raises(ValueError, match="exact DurableCurrentExecutionFence"):
        pack(fixture, current_fence=bypass)


def test_g8_rejects_instance_level_durable_fence_override(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    fixture.current_fence.assert_current = lambda **_: None

    with pytest.raises(ValueError, match="instance state is not pristine|implementation is not canonical"):
        pack(fixture)


def test_g8_rejects_transport_credential_class_mismatch(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    wrong = bound_transport(
        token="wrong-class-g8-test-token",
        credential_class="github.wrong-read/scoped-v1",
    )

    with pytest.raises(PermissionError, match="transport is not bound to Runner credential class"):
        pack(fixture, runner_transport=wrong).build_runtime(
            service=fixture.service,
            permission_authority=fixture.permission,
        )


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
    collapsed_transport = bound_transport(
        token="collapsed-verifier-token",
        credential_class=RUNNER_CREDENTIAL_CLASS,
    )

    with pytest.raises(PermissionError, match="credential classes must be distinct"):
        pack(
            fixture,
            verifier_profile=collapsed_profile,
            verifier_policy=collapsed_policy,
            verifier_transport=collapsed_transport,
        ).build_runtime(
            service=fixture.service,
            permission_authority=fixture.permission,
        )


def test_g8_rejects_production_policy_widening(tmp_path: Path) -> None:
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


def test_g8_rejects_production_product_service_before_runtime_binding(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture")
    production_service = ProductService(
        config(tmp_path / "production", environment="production")
    )
    production_permission = DatabasePermissionAuthority(
        database=production_service.db,
        authority_revision="database-permission/g8-production-test-r1",
    )

    with pytest.raises(PermissionError, match="cannot install into a production ProductService"):
        pack(fixture).build_runtime(
            service=production_service,
            permission_authority=production_permission,
        )


def test_g8_rejects_product_runner_environment_mismatch(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture")
    development_service = ProductService(
        config(tmp_path / "development", environment="development")
    )
    development_permission = DatabasePermissionAuthority(
        database=development_service.db,
        authority_revision="database-permission/g8-development-test-r1",
    )

    with pytest.raises(PermissionError, match="product and Runner environments must match"):
        pack(fixture).build_runtime(
            service=development_service,
            permission_authority=development_permission,
        )


def test_g8_rejects_current_fence_from_parallel_database(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    other_service = ProductService(config(tmp_path / "other"))
    foreign_fence = DurableCurrentExecutionFence(
        database=other_service.db,
        trusted_clock=fixture.runner_clock,
    )

    with pytest.raises(ValueError, match="current fence must use the product database"):
        pack(fixture, current_fence=foreign_fence).build_runtime(
            service=fixture.service,
            permission_authority=fixture.permission,
        )


def test_g8_role_bound_handlers_reject_direct_transport_rebinding(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    runtime = pack(fixture).build_runtime(
        service=fixture.service,
        permission_authority=fixture.permission,
    )
    assert runtime.read_terminal is not None
    runner_handler = runtime.read_terminal.runner_handler
    verifier_handler = runtime.read_terminal.verifier_handler
    runner_effect_transport = runner_handler.transport
    verifier_effect_transport = verifier_handler.transport

    with pytest.raises(AttributeError, match="Runner handler transport binding is immutable"):
        runner_handler.transport = verifier_effect_transport
    with pytest.raises(AttributeError, match="Verifier handler transport binding is immutable"):
        verifier_handler.transport = runner_effect_transport

    assert runner_handler.transport is runner_effect_transport
    assert verifier_handler.transport is verifier_effect_transport


def test_g8_role_bound_handlers_fail_closed_after_object_setattr_role_swap(
    tmp_path: Path,
) -> None:
    fixture = build_fixture(tmp_path)
    runtime = pack(fixture).build_runtime(
        service=fixture.service,
        permission_authority=fixture.permission,
    )
    assert runtime.read_terminal is not None
    runner_handler = runtime.read_terminal.runner_handler
    verifier_handler = runtime.read_terminal.verifier_handler
    runner_effect_transport = runner_handler.transport
    verifier_effect_transport = verifier_handler.transport

    object.__setattr__(runner_handler, "transport", verifier_effect_transport)
    with pytest.raises(PermissionError, match="Runner handler credential role mismatch"):
        runner_handler.observe_ref(
            prepared=object(),  # type: ignore[arg-type]
            activation=object(),  # type: ignore[arg-type]
            target=object(),  # type: ignore[arg-type]
        )

    object.__setattr__(verifier_handler, "transport", runner_effect_transport)
    with pytest.raises(PermissionError, match="Verifier handler credential role mismatch"):
        verifier_handler.observe_ref(
            verifier=object(),  # type: ignore[arg-type]
            boundary=object(),  # type: ignore[arg-type]
            decision=object(),  # type: ignore[arg-type]
            target=object(),  # type: ignore[arg-type]
        )
