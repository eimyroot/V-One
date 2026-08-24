from __future__ import annotations

import hashlib
import http.client
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Final

from .canonical_operation_resume import CanonicalOperationResumeService
from .canonical_operation_runtime import CanonicalOperationRuntime
from .canonical_pipeline import CanonicalOperationPipeline
from .canonical_read_terminal import CanonicalGitHubReadTerminal, VerifierRuntimeProfile
from .capability_registry import ImmutableCapabilityRegistry
from .credential_broker import CredentialBrokerPolicy, ImmutableCredentialBroker
from .durable_current_fence import DurableCurrentExecutionFence
from .execution_capsule import ImmutableExecutionCapsuleRegistry
from .github_actions_runtime import (
    GITHUB_API_SOURCE_IDENTITY,
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
_GITHUB_API_HOST: Final = "api.github.com"
_GITHUB_API_VERSION: Final = "2022-11-28"
_DURABLE_FENCE_ASSERT_CURRENT: Final = DurableCurrentExecutionFence.assert_current
_EXPECTED_DURABLE_FENCE_INSTANCE_FIELDS: Final = frozenset({"db", "trusted_clock"})


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


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _observe_github_credential_principal(token: str) -> str:
    """Resolve the GitHub principal authenticated by the exact credential material.

    R1 deliberately supports only credentials for which GitHub's authenticated-user READ endpoint
    returns a stable numeric principal id. Credentials that cannot prove a principal through this
    endpoint fail closed rather than being labeled by caller input. This is a READ-only provider
    observation and does not serialize the token or provider response into V-One evidence.
    """

    connection = http.client.HTTPSConnection(_GITHUB_API_HOST, 443, timeout=15)
    try:
        connection.request(
            "GET",
            "/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "v-one-g8-credential-principal",
                "X-GitHub-Api-Version": _GITHUB_API_VERSION,
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(
                f"G8 GitHub credential principal observation failed with HTTP {response.status}"
            )
        try:
            payload = json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("G8 GitHub credential principal response is invalid") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise RuntimeError("G8 GitHub credential principal observation failed") from exc
    finally:
        connection.close()

    if not isinstance(payload, dict):
        raise RuntimeError("G8 GitHub credential principal response is invalid")
    principal_id = payload.get("id")
    principal_type = payload.get("type")
    if isinstance(principal_id, bool) or not isinstance(principal_id, int) or principal_id < 1:
        raise RuntimeError("G8 GitHub credential principal id is invalid")
    if (
        not isinstance(principal_type, str)
        or not principal_type
        or principal_type != principal_type.strip()
    ):
        raise RuntimeError("G8 GitHub credential principal type is invalid")
    return f"github-principal/{principal_type.casefold()}/{principal_id}"


def _assert_pristine_durable_fence(fence: object) -> DurableCurrentExecutionFence:
    """Reject subclass and instance-level replacement of the released fence implementation."""

    if type(fence) is not DurableCurrentExecutionFence:
        raise ValueError("current_fence must be exact DurableCurrentExecutionFence")
    if DurableCurrentExecutionFence.assert_current is not _DURABLE_FENCE_ASSERT_CURRENT:
        raise ValueError("DurableCurrentExecutionFence implementation changed after G8 import")
    if frozenset(vars(fence)) != _EXPECTED_DURABLE_FENCE_INSTANCE_FIELDS:
        raise ValueError("current_fence instance state is not pristine")
    bound_assert_current = getattr(fence, "assert_current", None)
    if getattr(bound_assert_current, "__func__", None) is not _DURABLE_FENCE_ASSERT_CURRENT:
        raise ValueError("current_fence assert_current implementation is not canonical")
    return fence


@dataclass(frozen=True, slots=True, init=False)
class G8BoundGitHubReadTransport:
    """Closed immutable GitHub READ port with provider-attested credential provenance.

    The exact token, its fingerprint, credential class and initial provider attestation are retained
    only in frozen private slots. The credential fingerprint and provider principal are revalidated
    immediately before every provider READ, so credential substitution after composition fails closed
    at the effect boundary rather than silently collapsing Runner and Verifier authority.
    """

    __token: str
    __token_fingerprint: str
    __credential_class: str
    __attested_principal: str

    source_identity: ClassVar[str] = GITHUB_API_SOURCE_IDENTITY

    def __init__(
        self,
        *,
        token: str,
        credential_class: str,
    ) -> None:
        token = _require_text(token, field="token")
        GitHubApiRefReadTransport(token=token)
        credential_class = _require_text(
            credential_class,
            field="credential_class",
        )
        principal = _observe_github_credential_principal(token)
        object.__setattr__(self, "_G8BoundGitHubReadTransport__token", token)
        object.__setattr__(
            self,
            "_G8BoundGitHubReadTransport__token_fingerprint",
            _token_fingerprint(token),
        )
        object.__setattr__(
            self,
            "_G8BoundGitHubReadTransport__credential_class",
            credential_class,
        )
        object.__setattr__(
            self,
            "_G8BoundGitHubReadTransport__attested_principal",
            principal,
        )

    @property
    def credential_class(self) -> str:
        return self.__credential_class

    @property
    def credential_principal_identity(self) -> str:
        return self._assert_credential_current()

    def _assert_credential_current(self) -> str:
        current_fingerprint = _token_fingerprint(self.__token)
        if not secrets.compare_digest(current_fingerprint, self.__token_fingerprint):
            raise PermissionError("G8 credential material changed after attestation")
        current_principal = _observe_github_credential_principal(self.__token)
        if current_principal != self.__attested_principal:
            raise PermissionError("G8 credential principal changed after attestation")
        return current_principal

    def read_ref(self, *, repository: str, ref: str) -> str:
        self._assert_credential_current()
        return GitHubApiRefReadTransport(token=self.__token).read_ref(
            repository=repository,
            ref=ref,
        )

    def _shares_credential_material(self, other: G8BoundGitHubReadTransport) -> bool:
        if type(other) is not G8BoundGitHubReadTransport:
            raise ValueError("credential comparison requires closed G8 transport")
        self._assert_credential_current()
        other._assert_credential_current()
        return secrets.compare_digest(self.__token, other.__token)


@dataclass(frozen=True, slots=True)
class G8ReadRuntimePack:
    """Assemble the first default provider runtime without creating a second trust graph.

    G8 owns only provider/runtime composition. G1-G7 authority, durable dispatch, terminal-profile
    selection, and lease allocation are supplied by one already-canonical ``CanonicalOperationPipeline``.
    The caller-supplied durable fence is accepted only as canonical composition provenance; the
    runtime retains a newly constructed exact fence over the same canonical DB and trusted clock so
    instance-level monkeypatching of the source fence cannot cross into execution.
    """

    pipeline: CanonicalOperationPipeline
    capsule_registry: ImmutableExecutionCapsuleRegistry
    current_fence: DurableCurrentExecutionFence
    runner_provider: GitHubActionsIsolatedRuntimeProvider
    runner_transport: G8BoundGitHubReadTransport
    runner_clock: TrustedClockAuthority
    runner_credential_policy: CredentialBrokerPolicy
    runner_credential_decision_revision: str
    runner_identity_revision: str
    runner_boundary_revision: str
    runner_activation_revision: str
    runner_observation_revision: str
    verifier_profile: VerifierRuntimeProfile
    verifier_policy: VerifierCredentialPolicy
    verifier_transport: G8BoundGitHubReadTransport
    verifier_clock: TrustedClockAuthority
    verifier_observation_revision: str
    observed_post_state_revision: str
    strength_revision: str
    result_revision: str
    read_capability_definition_identity: str

    def __post_init__(self) -> None:
        if type(self.pipeline) is not CanonicalOperationPipeline:
            raise ValueError("pipeline must be exact CanonicalOperationPipeline")
        if not isinstance(self.capsule_registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("capsule_registry must be ImmutableExecutionCapsuleRegistry")
        _assert_pristine_durable_fence(self.current_fence)
        if type(self.runner_provider) is not GitHubActionsIsolatedRuntimeProvider:
            raise ValueError("runner_provider must be exact GitHubActionsIsolatedRuntimeProvider")
        if type(self.runner_clock) is not TrustedClockAuthority:
            raise ValueError("runner_clock must be exact TrustedClockAuthority")
        if type(self.runner_credential_policy) is not CredentialBrokerPolicy:
            raise ValueError("runner_credential_policy must be exact CredentialBrokerPolicy")
        if type(self.verifier_profile) is not VerifierRuntimeProfile:
            raise ValueError("verifier_profile must be exact VerifierRuntimeProfile")
        if type(self.verifier_policy) is not VerifierCredentialPolicy:
            raise ValueError("verifier_policy must be exact VerifierCredentialPolicy")
        if type(self.verifier_clock) is not TrustedClockAuthority:
            raise ValueError("verifier_clock must be exact TrustedClockAuthority")

        if type(self.runner_transport) is not G8BoundGitHubReadTransport:
            raise ValueError("runner_transport must be exact G8BoundGitHubReadTransport")
        if type(self.verifier_transport) is not G8BoundGitHubReadTransport:
            raise ValueError("verifier_transport must be exact G8BoundGitHubReadTransport")
        if self.runner_transport is self.verifier_transport:
            raise ValueError("runner and verifier transports must be distinct instances")
        if self.runner_transport._shares_credential_material(self.verifier_transport):
            raise ValueError("runner and verifier credential material must be distinct")
        runner_principal = self.runner_transport.credential_principal_identity
        verifier_principal = self.verifier_transport.credential_principal_identity
        if runner_principal == verifier_principal:
            raise ValueError("runner and verifier provider principals must be distinct")

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

        if type(service) is not ProductService:
            raise ValueError("service must be exact ProductService")
        if type(permission_authority) is not DatabasePermissionAuthority:
            raise ValueError("permission_authority must be exact DatabasePermissionAuthority")
        if service.config.environment == "production":
            raise PermissionError("G8 R1 cannot install into a production ProductService")
        if service.config.environment != self.runner_provider.environment:
            raise PermissionError("G8 product and Runner environments must match")
        if permission_authority.db is not service.db:
            raise ValueError("G8 permission authority must use the product database")

        source_fence = _assert_pristine_durable_fence(self.current_fence)
        if source_fence.db is not service.db:
            raise ValueError("G8 current fence must use the product database")
        if source_fence.trusted_clock is not self.runner_clock:
            raise ValueError("G8 Runner and current fence must share the trusted clock")

        runtime_fence = DurableCurrentExecutionFence(
            database=service.db,
            trusted_clock=self.runner_clock,
        )
        _assert_pristine_durable_fence(runtime_fence)

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
            current_fence=runtime_fence,
            identity_revision=self.runner_identity_revision,
            boundary_revision=self.runner_boundary_revision,
            activation_revision=self.runner_activation_revision,
        )
        runner_handler = GitHubRefReadHandler(
            transport=self.runner_transport,
            current_fence=runtime_fence,
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
            current_fence=runtime_fence,
            envelope_revision=pipeline.envelope_revision,
        )

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
        if self.runner_transport.credential_class != runner_policy.credential_class:
            raise PermissionError("G8 Runner transport is not bound to Runner credential class")

        if verifier_policy.provider != "github" or verifier_policy.audience != GITHUB_API_AUDIENCE:
            raise PermissionError("G8 Verifier credential policy must target GitHub API READ")
        if verifier_policy.provider_mutation_allowed is not False:
            raise PermissionError("G8 Verifier policy allows provider mutation")
        if verifier_profile.provider != "github":
            raise PermissionError("G8 Verifier profile provider must be github")
        if verifier_profile.credential_class != verifier_policy.credential_class:
            raise PermissionError("G8 Verifier profile/policy credential class mismatch")
        if self.verifier_transport.credential_class != verifier_policy.credential_class:
            raise PermissionError("G8 Verifier transport is not bound to Verifier credential class")
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
    """Adapt an exact G8 pack to ProductComposition's canonical runtime factory seam."""

    if type(pack) is not G8ReadRuntimePack:
        raise ValueError("pack must be exact G8ReadRuntimePack")

    def factory(
        service: ProductService,
        permission_authority: DatabasePermissionAuthority,
    ) -> CanonicalOperationRuntime:
        return pack.build_runtime(
            service=service,
            permission_authority=permission_authority,
        )

    return factory
