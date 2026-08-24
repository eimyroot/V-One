from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from .canonical_operation_resume import CanonicalOperationResumeService
from .canonical_operation_runtime import CanonicalOperationRuntime
from .canonical_pipeline import CanonicalOperationPipeline
from .canonical_read_terminal import CanonicalGitHubReadTerminal, VerifierRuntimeProfile
from .capability_registry import ImmutableCapabilityRegistry
from .credential_broker import CredentialBrokerPolicy, ImmutableCredentialBroker
from .durable_current_fence import DurableCurrentExecutionFence
from .execution_capsule import ImmutableExecutionCapsuleRegistry
from .github_actions_runtime import (
    GitHubActionsIsolatedRuntimeProvider,
    GitHubApiRefReadTransport,
)
from .github_read_provider import (
    GITHUB_READ_REF_CAPABILITY,
    GITHUB_REF_TARGET_KIND,
    GitHubRefReadHandler,
)
from .isolated_runner import IsolatedRunnerAdapter
from .permission_authority import DatabasePermissionAuthority
from .runner_identity import READ_ONLY_EFFECT_CLASS
from .service import ProductService
from .trusted_clock import TrustedClockAuthority
from .verifier_credential import VerifierCredentialPolicy
from .verifier_observation import VerifierGitHubRefReadHandler

GITHUB_API_AUDIENCE: Final = "api.github.com"

# The default G8 pack intentionally accepts only the concrete transport whose implementation is
# hard-coded to GitHub's HTTPS GET ref endpoint. A structural GitHubReadTransport implementation is
# insufficient proof: a custom ``read_ref`` method could hide a mutation internally while satisfying
# the narrow Protocol. Exact type checking also prevents a subclass from overriding ``read_ref``.
_FORBIDDEN_TRANSPORT_METHODS: Final = frozenset(
    {
        "create_ref",
        "delete_ref",
        "update_ref",
        "write",
        "mutate",
        "execute",
        "request",
        "post",
        "put",
        "patch",
        "delete",
    }
)


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _assert_narrow_read_transport(
    transport: object,
    *,
    field: str,
) -> GitHubApiRefReadTransport:
    if type(transport) is not GitHubApiRefReadTransport:
        raise ValueError(f"{field} must be exact GitHubApiRefReadTransport")
    _require_text(transport.source_identity, field=f"{field}.source_identity")
    widened = sorted(
        name
        for name in _FORBIDDEN_TRANSPORT_METHODS
        if callable(getattr(transport, name, None))
    )
    if widened:
        raise ValueError(f"{field} exposes forbidden provider methods: {widened}")
    return transport


@dataclass(frozen=True, slots=True)
class G8ReadRuntimePack:
    """Assemble the first default provider runtime without creating a second trust graph.

    G8 owns only provider/runtime composition. G1-G7 authority, durable dispatch, terminal-profile
    selection, and lease allocation are supplied by one already-canonical ``CanonicalOperationPipeline``.
    This pack refuses parallel databases, permission authorities, capability/capsule registries,
    current fences, coordinators, or mutation-shaped provider transports.

    Credential bytes are intentionally outside V-One evidence. The two concrete GET-only transports
    privately retain explicitly supplied credentials, while this assembler never reads ambient
    environment variables and never serializes credential material into V-One evidence.
    """

    pipeline: CanonicalOperationPipeline
    capsule_registry: ImmutableExecutionCapsuleRegistry
    current_fence: DurableCurrentExecutionFence
    runner_provider: GitHubActionsIsolatedRuntimeProvider
    runner_transport: GitHubApiRefReadTransport
    runner_clock: TrustedClockAuthority
    runner_credential_policy: CredentialBrokerPolicy
    runner_credential_decision_revision: str
    runner_identity_revision: str
    runner_boundary_revision: str
    runner_activation_revision: str
    runner_observation_revision: str
    verifier_profile: VerifierRuntimeProfile
    verifier_policy: VerifierCredentialPolicy
    verifier_transport: GitHubApiRefReadTransport
    verifier_clock: TrustedClockAuthority
    verifier_observation_revision: str
    observed_post_state_revision: str
    strength_revision: str
    result_revision: str
    read_capability_definition_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.pipeline, CanonicalOperationPipeline):
            raise ValueError("pipeline must be CanonicalOperationPipeline")
        if not isinstance(self.capsule_registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("capsule_registry must be ImmutableExecutionCapsuleRegistry")
        if not isinstance(self.current_fence, DurableCurrentExecutionFence):
            raise ValueError("current_fence must be DurableCurrentExecutionFence")
        if not isinstance(self.runner_provider, GitHubActionsIsolatedRuntimeProvider):
            raise ValueError("runner_provider must be GitHubActionsIsolatedRuntimeProvider")
        if not isinstance(self.runner_clock, TrustedClockAuthority):
            raise ValueError("runner_clock must be TrustedClockAuthority")
        if not isinstance(self.runner_credential_policy, CredentialBrokerPolicy):
            raise ValueError("runner_credential_policy must be CredentialBrokerPolicy")
        if not isinstance(self.verifier_profile, VerifierRuntimeProfile):
            raise ValueError("verifier_profile must be VerifierRuntimeProfile")
        if not isinstance(self.verifier_policy, VerifierCredentialPolicy):
            raise ValueError("verifier_policy must be VerifierCredentialPolicy")
        if not isinstance(self.verifier_clock, TrustedClockAuthority):
            raise ValueError("verifier_clock must be TrustedClockAuthority")

        _assert_narrow_read_transport(self.runner_transport, field="runner_transport")
        _assert_narrow_read_transport(self.verifier_transport, field="verifier_transport")
        if self.runner_transport is self.verifier_transport:
            raise ValueError("runner and verifier transports must be distinct instances")

        for field in (
            "runner_credential_decision_revision",
            "runner_identity_revision",
            "runner_boundary_revision",
            "runner_activation_revision",
            "runner_observation_revision",
            "verifier_observation_revision",
            "observed_post_state_revision",
            "strength_revision",
            "result_revision",
        ):
            _require_text(getattr(self, field), field=field)
        _require_digest(
            self.read_capability_definition_identity,
            field="read_capability_definition_identity",
        )

    def build_runtime(
        self,
        *,
        service: ProductService,
        permission_authority: DatabasePermissionAuthority,
    ) -> CanonicalOperationRuntime:
        """Build the G8 READ-only runtime only when every canonical binding is exact."""

        if not isinstance(service, ProductService):
            raise ValueError("service must be ProductService")
        if not isinstance(permission_authority, DatabasePermissionAuthority):
            raise ValueError("permission_authority must be DatabasePermissionAuthority")
        if permission_authority.db is not service.db:
            raise ValueError("G8 permission authority must use the product database")

        pipeline = self.pipeline
        snapshot_creator = pipeline.snapshot_creator
        grant_service = pipeline.grant_service
        outbox_service = pipeline.outbox_service
        coordinator = pipeline.coordinator

        if getattr(snapshot_creator, "db", None) is not service.db:
            raise ValueError("G8 pipeline snapshot creator must use the product database")
        if getattr(snapshot_creator, "permission_authority", None) is not permission_authority:
            raise ValueError("G8 pipeline must use the product permission authority")
        if getattr(grant_service, "db", None) is not service.db:
            raise ValueError("G8 grant service must use the product database")
        if getattr(outbox_service, "db", None) is not service.db:
            raise ValueError("G8 outbox service must use the product database")
        if getattr(outbox_service, "grant_service", None) is not grant_service:
            raise ValueError("G8 outbox must use the canonical grant service")
        if not callable(getattr(coordinator, "complete", None)):
            raise ValueError("G8 canonical coordinator must implement durable completion")

        snapshot_store = getattr(snapshot_creator, "snapshot_store", None)
        if getattr(snapshot_store, "db", None) is not service.db:
            raise ValueError("G8 snapshot store must use the product database")
        if not callable(getattr(snapshot_store, "get", None)):
            raise ValueError("G8 snapshot store must implement durable get")

        capability_registry = getattr(snapshot_creator, "capability_registry", None)
        if not isinstance(capability_registry, ImmutableCapabilityRegistry):
            raise ValueError("G8 snapshot creator must expose canonical capability registry")
        if self.capsule_registry.capability_registry is not capability_registry:
            raise ValueError("G8 capsule and snapshot capability registries must be identical")

        conformance_authority = getattr(grant_service, "conformance_authority", None)
        if getattr(conformance_authority, "capsule_registry", None) is not self.capsule_registry:
            raise ValueError("G8 grant conformance must use the canonical capsule registry")
        grant_issuer = getattr(grant_service, "grant_issuer", None)
        binding_authority = getattr(grant_issuer, "execution_binding_authority", None)
        if getattr(binding_authority, "registry", None) is not self.capsule_registry:
            raise ValueError("G8 grant binding authority must use the canonical capsule registry")

        if self.current_fence.db is not service.db:
            raise ValueError("G8 current fence must use the product database")
        if self.current_fence.trusted_clock is not self.runner_clock:
            raise ValueError("G8 Runner and current fence must share the trusted clock")

        definition = capability_registry.definition_by_identity(
            self.read_capability_definition_identity
        )
        if definition.capability != GITHUB_READ_REF_CAPABILITY:
            raise PermissionError("G8 capability is not github.read-ref/v1")
        if definition.target_kind != GITHUB_REF_TARGET_KIND:
            raise PermissionError("G8 capability target is not git_ref")
        if definition.effect_class != READ_ONLY_EFFECT_CLASS:
            raise PermissionError("G8 capability is not READ_ONLY")

        capsule = self.capsule_registry.capsule_for_definition(
            self.read_capability_definition_identity
        )
        if capsule.capability_definition_identity != self.read_capability_definition_identity:
            raise PermissionError("G8 capsule capability binding mismatch")
        if capsule.credential_class != self.runner_credential_policy.credential_class:
            raise PermissionError("G8 Runner credential class does not match execution capsule")

        self._validate_runtime_ceiling(definition=definition, capsule=capsule)

        broker = ImmutableCredentialBroker(
            policies=(self.runner_credential_policy,),
            decision_revision=self.runner_credential_decision_revision,
        )
        runner_adapter = IsolatedRunnerAdapter(
            provider=self.runner_provider,
            credential_broker=broker,
            current_fence=self.current_fence,
            identity_revision=self.runner_identity_revision,
            boundary_revision=self.runner_boundary_revision,
            activation_revision=self.runner_activation_revision,
        )
        runner_handler = GitHubRefReadHandler(
            transport=self.runner_transport,
            current_fence=self.current_fence,
            trusted_clock=self.runner_clock,
            observation_revision=self.runner_observation_revision,
        )
        verifier_handler = VerifierGitHubRefReadHandler(
            transport=self.verifier_transport,
            trusted_clock=self.verifier_clock,
            observation_revision=self.verifier_observation_revision,
        )
        read_terminal = CanonicalGitHubReadTerminal(
            capability_registry=capability_registry,
            capsule_registry=self.capsule_registry,
            runner_adapter=runner_adapter,
            runner_handler=runner_handler,
            completion_coordinator=coordinator,
            verifier_profile=self.verifier_profile,
            verifier_policy=self.verifier_policy,
            verifier_handler=verifier_handler,
            verifier_clock=self.verifier_clock,
            observed_post_state_revision=self.observed_post_state_revision,
            strength_revision=self.strength_revision,
            result_revision=self.result_revision,
        )
        resume_service = CanonicalOperationResumeService(
            database=service.db,
            snapshot_store=snapshot_store,
            permission_authority=permission_authority,
            terminal_profile_registry=pipeline.terminal_profile_registry,
            current_fence=self.current_fence,
            envelope_revision=pipeline.envelope_revision,
        )

        # A09 preparers are intentionally absent. G8 has no provider WRITE or rollback path.
        return CanonicalOperationRuntime(
            pipeline=pipeline,
            read_terminal=read_terminal,
            resume_service=resume_service,
        )

    def _validate_runtime_ceiling(self, *, definition: object, capsule: object) -> None:
        runner_policy = self.runner_credential_policy
        verifier_policy = self.verifier_policy
        verifier_profile = self.verifier_profile
        definition_identity = self.read_capability_definition_identity

        if runner_policy.allowed_capability_definition_identities != (definition_identity,):
            raise PermissionError("G8 Runner policy must allow exactly the READ capability identity")
        if runner_policy.provider != "github" or runner_policy.audience != GITHUB_API_AUDIENCE:
            raise PermissionError("G8 Runner credential policy must target GitHub API READ")
        if runner_policy.provider_mutation_allowed is not False:
            raise PermissionError("G8 Runner policy allows provider mutation")

        if verifier_policy.provider != "github" or verifier_policy.audience != GITHUB_API_AUDIENCE:
            raise PermissionError("G8 Verifier credential policy must target GitHub API READ")
        if verifier_policy.provider_mutation_allowed is not False:
            raise PermissionError("G8 Verifier policy allows provider mutation")
        if verifier_profile.provider != "github":
            raise PermissionError("G8 Verifier profile provider must be github")
        if verifier_profile.credential_class != verifier_policy.credential_class:
            raise PermissionError("G8 Verifier profile/policy credential class mismatch")
        if verifier_profile.credential_class == runner_policy.credential_class:
            raise PermissionError("G8 Runner and Verifier credential classes must be distinct")
        if verifier_profile.provider_instance_id == self.runner_provider.provider_instance_id:
            raise PermissionError("G8 Runner and Verifier provider identities must be distinct")
        if verifier_profile.credential_ttl_seconds > verifier_policy.max_ttl_seconds:
            raise PermissionError("G8 Verifier credential TTL exceeds policy")

        enabled = tuple(runner_policy.enabled_environments)
        if tuple(verifier_policy.enabled_environments) != enabled:
            raise PermissionError("G8 Runner and Verifier environment ceilings must match")
        if self.runner_provider.environment not in enabled:
            raise PermissionError("G8 Runner environment is not credential-enabled")
        if any(environment not in definition.supported_environments for environment in enabled):
            raise PermissionError("G8 credential policy exceeds capability environments")
        if "production" in enabled or self.runner_provider.environment == "production":
            raise PermissionError("G8 R1 cannot enable production")

        if self.runner_provider.runner_class != capsule.runner_class:
            raise PermissionError("G8 Runner class does not match execution capsule")
        if self.runner_provider.rootfs_digest != capsule.rootfs_digest:
            raise PermissionError("G8 Runner rootfs does not match execution capsule")
        if (
            self.runner_provider.resource_limit_profile_digest
            != capsule.resource_limit_profile_digest
        ):
            raise PermissionError("G8 Runner resource profile does not match execution capsule")
        if self.runner_provider.network_policy_digest != capsule.network_policy_digest:
            raise PermissionError("G8 Runner network policy does not match execution capsule")


def create_g8_read_runtime_factory(
    pack: G8ReadRuntimePack,
) -> Callable[[ProductService, DatabasePermissionAuthority], CanonicalOperationRuntime]:
    """Adapt a validated G8 pack to ProductComposition's canonical runtime factory seam."""

    if not isinstance(pack, G8ReadRuntimePack):
        raise ValueError("pack must be G8ReadRuntimePack")

    def factory(
        service: ProductService,
        permission_authority: DatabasePermissionAuthority,
    ) -> CanonicalOperationRuntime:
        return pack.build_runtime(
            service=service,
            permission_authority=permission_authority,
        )

    return factory
