from __future__ import annotations

import hashlib
import http.client
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Final, NamedTuple
from weakref import WeakKeyDictionary

from .canonical_operation_resume import CanonicalOperationResumeService
from .canonical_operation_runtime import CanonicalOperationRuntime
from .canonical_pipeline import CanonicalOperationPipeline, CanonicalPreparedExecution
from .canonical_read_terminal import (
    CanonicalGitHubReadTerminal,
    CanonicalReadTerminalResult,
    VerifierRuntimeProfile,
)
from .capability_registry import ImmutableCapabilityRegistry
from .credential_broker import CredentialBrokerPolicy, ImmutableCredentialBroker
from .durable_current_fence import DurableCurrentExecutionFence
from .execution_capsule import ImmutableExecutionCapsuleRegistry
from .execution_contract import ExecutionTarget
from .github_actions_runtime import (
    GITHUB_API_SOURCE_IDENTITY,
    GitHubActionsIsolatedRuntimeProvider,
    GitHubApiRefReadTransport,
)
from .github_read_provider import (
    GITHUB_READ_REF_CAPABILITY,
    GITHUB_REF_TARGET_KIND,
    GitHubRefObservation,
    GitHubRefReadHandler,
)
from .isolated_runner import (
    IsolatedRunnerAdapter,
    PreparedIsolatedRuntime,
    ReadOnlyRuntimeActivation,
)
from .permission_authority import DatabasePermissionAuthority
from .runner_identity import READ_ONLY_EFFECT_CLASS
from .service import ProductService
from .trusted_clock import TrustedClockAuthority
from .verifier_credential import VerifierCredentialDecision, VerifierCredentialPolicy
from .verifier_identity import IndependentVerificationBoundary, VerifierIdentity
from .verifier_observation import (
    VerifierGitHubRefObservation,
    VerifierGitHubRefReadHandler,
)

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


@dataclass(frozen=True, slots=True)
class _CredentialBinding:
    token: str
    token_fingerprint: str
    credential_class: str
    attested_principal: str


class _CredentialPin(NamedTuple):
    token_fingerprint: str
    credential_class: str
    attested_principal: str


class _ProviderReadEffectPin(NamedTuple):
    transport_type: type
    init_method: Callable[..., None]
    read_ref_method: Callable[..., str]
    source_identity: str


_IMPORT_PROVIDER_READ_EFFECT_PIN: Final = _ProviderReadEffectPin(
    transport_type=GitHubApiRefReadTransport,
    init_method=GitHubApiRefReadTransport.__init__,
    read_ref_method=GitHubApiRefReadTransport.read_ref,
    source_identity=GITHUB_API_SOURCE_IDENTITY,
)


def _current_provider_read_effect_pin() -> _ProviderReadEffectPin:
    """Pin the exact released GET-only provider implementation before runtime retention."""

    pin = _IMPORT_PROVIDER_READ_EFFECT_PIN
    if GitHubApiRefReadTransport is not pin.transport_type:
        raise PermissionError("G8 GitHub provider transport type changed after import")
    if pin.transport_type.__init__ is not pin.init_method:
        raise PermissionError("G8 GitHub provider transport initializer changed after import")
    if pin.transport_type.read_ref is not pin.read_ref_method:
        raise PermissionError("G8 GitHub provider READ implementation changed after import")
    if pin.source_identity != GITHUB_API_SOURCE_IDENTITY:
        raise PermissionError("G8 GitHub provider source identity changed after import")
    return pin


def _new_provider_transport(*, pin: _ProviderReadEffectPin, token: str) -> object:
    if type(pin) is not _ProviderReadEffectPin:
        raise ValueError("G8 provider READ effect pin is invalid")
    instance = object.__new__(pin.transport_type)
    pin.init_method(instance, token=token)
    if type(instance) is not pin.transport_type:
        raise PermissionError("G8 provider READ transport instance type mismatch")
    return instance


def _provider_read_with_pin(
    *,
    pin: _ProviderReadEffectPin,
    token: str,
    repository: str,
    ref: str,
) -> str:
    transport = _new_provider_transport(pin=pin, token=token)
    return pin.read_ref_method(
        transport,
        repository=repository,
        ref=ref,
    )


def _build_g8_bound_github_read_transport_type() -> type:
    """Create the credential source with binding state outside caller-retained instances."""

    bindings: WeakKeyDictionary[object, object] = WeakKeyDictionary()
    initializing = object()

    def binding_for(instance: object) -> _CredentialBinding:
        try:
            binding = bindings[instance]
        except KeyError as exc:
            raise RuntimeError("G8 credential binding is unavailable") from exc
        if type(binding) is not _CredentialBinding:
            raise RuntimeError("G8 credential binding is not initialized")
        return binding

    def validated_binding(instance: object) -> _CredentialBinding:
        binding = binding_for(instance)
        token = binding.token
        current_fingerprint = _token_fingerprint(token)
        if not secrets.compare_digest(current_fingerprint, binding.token_fingerprint):
            raise PermissionError("G8 credential material changed after attestation")
        current_principal = _observe_github_credential_principal(token)
        if current_principal != binding.attested_principal:
            raise PermissionError("G8 credential principal changed after attestation")
        return binding

    class G8BoundGitHubReadTransport:
        """Closed credential source; direct provider effects are intentionally disabled.

        Binding state is closure-owned, but R1 does not trust that registry by itself. Runtime
        construction separately pins both Runner and Verifier identities into an immutable pair
        transport. Only that pair transport is retained by the provider-effect handlers.
        """

        __slots__ = ("__weakref__",)

        source_identity: ClassVar[str] = GITHUB_API_SOURCE_IDENTITY

        def __init__(
            self,
            *,
            token: str,
            credential_class: str,
        ) -> None:
            if self in bindings:
                raise RuntimeError("G8 credential source is already initialized")
            bindings[self] = initializing
            try:
                token = _require_text(token, field="token")
                provider_effect_pin = _current_provider_read_effect_pin()
                _new_provider_transport(pin=provider_effect_pin, token=token)
                credential_class = _require_text(
                    credential_class,
                    field="credential_class",
                )
                principal = _observe_github_credential_principal(token)
                binding = _CredentialBinding(
                    token=token,
                    token_fingerprint=_token_fingerprint(token),
                    credential_class=credential_class,
                    attested_principal=principal,
                )
            except Exception:
                bindings.pop(self, None)
                raise
            bindings[self] = binding

        @property
        def credential_class(self) -> str:
            return binding_for(self).credential_class

        @property
        def credential_principal_identity(self) -> str:
            return validated_binding(self).attested_principal

        @property
        def credential_fingerprint(self) -> str:
            return validated_binding(self).token_fingerprint

        def _pin_snapshot(self) -> _CredentialPin:
            binding = validated_binding(self)
            return _CredentialPin(
                token_fingerprint=binding.token_fingerprint,
                credential_class=binding.credential_class,
                attested_principal=binding.attested_principal,
            )

        def _read_ref_with_pin(
            self,
            *,
            pin: _CredentialPin,
            provider_effect_pin: _ProviderReadEffectPin,
            repository: str,
            ref: str,
        ) -> str:
            if type(pin) is not _CredentialPin:
                raise ValueError("G8 credential pin is invalid")
            if type(provider_effect_pin) is not _ProviderReadEffectPin:
                raise ValueError("G8 provider READ effect pin is invalid")
            binding = validated_binding(self)
            current_pin = _CredentialPin(
                token_fingerprint=binding.token_fingerprint,
                credential_class=binding.credential_class,
                attested_principal=binding.attested_principal,
            )
            if current_pin != pin:
                raise PermissionError("G8 credential binding changed after runtime pinning")
            token = binding.token
            return _provider_read_with_pin(
                pin=provider_effect_pin,
                token=token,
                repository=repository,
                ref=ref,
            )

        def read_ref(self, *, repository: str, ref: str) -> str:
            del repository, ref
            raise PermissionError("G8 unpinned credential source cannot perform provider READ")

        def _shares_credential_material(self, other: object) -> bool:
            if type(other) is not G8BoundGitHubReadTransport:
                raise ValueError("credential comparison requires closed G8 transport")
            self_binding = validated_binding(self)
            other_binding = validated_binding(other)
            return secrets.compare_digest(self_binding.token, other_binding.token)

    return G8BoundGitHubReadTransport


G8BoundGitHubReadTransport = _build_g8_bound_github_read_transport_type()
_G8_SOURCE_PIN_SNAPSHOT: Final = G8BoundGitHubReadTransport._pin_snapshot
_G8_SOURCE_READ_REF_WITH_PIN: Final = G8BoundGitHubReadTransport._read_ref_with_pin


class _CredentialSourceImplementationPin(NamedTuple):
    transport_type: type
    pin_snapshot_method: Callable[..., _CredentialPin]
    read_ref_with_pin_method: Callable[..., str]


def _current_credential_source_implementation_pin() -> _CredentialSourceImplementationPin:
    if G8BoundGitHubReadTransport._pin_snapshot is not _G8_SOURCE_PIN_SNAPSHOT:
        raise PermissionError("G8 credential source pin implementation changed")
    if G8BoundGitHubReadTransport._read_ref_with_pin is not _G8_SOURCE_READ_REF_WITH_PIN:
        raise PermissionError("G8 credential source READ implementation changed")
    return _CredentialSourceImplementationPin(
        transport_type=G8BoundGitHubReadTransport,
        pin_snapshot_method=_G8_SOURCE_PIN_SNAPSHOT,
        read_ref_with_pin_method=_G8_SOURCE_READ_REF_WITH_PIN,
    )


class _G8IndependentCredentialPairTransport(NamedTuple):
    """Immutable use-time guard over both independently pinned credential sources."""

    runner_transport: object
    verifier_transport: object
    role: str
    runner_pin: _CredentialPin
    verifier_pin: _CredentialPin
    source_implementation_pin: _CredentialSourceImplementationPin
    provider_effect_pin: _ProviderReadEffectPin

    @property
    def source_identity(self) -> str:
        return self.provider_effect_pin.source_identity

    def read_ref(self, *, repository: str, ref: str) -> str:
        runner_transport = self.runner_transport
        verifier_transport = self.verifier_transport
        source_implementation_pin = self.source_implementation_pin
        provider_effect_pin = self.provider_effect_pin
        if type(source_implementation_pin) is not _CredentialSourceImplementationPin:
            raise PermissionError("G8 credential source implementation pin is invalid")
        if type(provider_effect_pin) is not _ProviderReadEffectPin:
            raise PermissionError("G8 provider effect pin is invalid")
        if type(runner_transport) is not source_implementation_pin.transport_type:
            raise PermissionError("G8 Runner credential source type changed")
        if type(verifier_transport) is not source_implementation_pin.transport_type:
            raise PermissionError("G8 Verifier credential source type changed")
        if self.role not in {"runner", "verifier"}:
            raise PermissionError("G8 credential pair role is invalid")

        runner_now = source_implementation_pin.pin_snapshot_method(runner_transport)
        verifier_now = source_implementation_pin.pin_snapshot_method(verifier_transport)
        if runner_now != self.runner_pin:
            raise PermissionError("G8 Runner credential changed after runtime pinning")
        if verifier_now != self.verifier_pin:
            raise PermissionError("G8 Verifier credential changed after runtime pinning")
        if secrets.compare_digest(
            runner_now.token_fingerprint,
            verifier_now.token_fingerprint,
        ):
            raise PermissionError("G8 Runner and Verifier credential material collapsed")
        if runner_now.attested_principal == verifier_now.attested_principal:
            raise PermissionError("G8 Runner and Verifier provider principals collapsed")
        if runner_now.credential_class == verifier_now.credential_class:
            raise PermissionError("G8 Runner and Verifier credential classes collapsed")

        if self.role == "runner":
            return source_implementation_pin.read_ref_with_pin_method(
                runner_transport,
                pin=self.runner_pin,
                provider_effect_pin=provider_effect_pin,
                repository=repository,
                ref=ref,
            )
        return source_implementation_pin.read_ref_with_pin_method(
            verifier_transport,
            pin=self.verifier_pin,
            provider_effect_pin=provider_effect_pin,
            repository=repository,
            ref=ref,
        )


def _assert_pair_transport_parity(
    runner_transport: object,
    verifier_transport: object,
) -> tuple[_G8IndependentCredentialPairTransport, _G8IndependentCredentialPairTransport]:
    if type(runner_transport) is not _G8IndependentCredentialPairTransport:
        raise PermissionError("G8 Runner handler transport is not canonical")
    if type(verifier_transport) is not _G8IndependentCredentialPairTransport:
        raise PermissionError("G8 Verifier handler transport is not canonical")
    if runner_transport.role != "runner":
        raise PermissionError("G8 Runner handler credential role mismatch")
    if verifier_transport.role != "verifier":
        raise PermissionError("G8 Verifier handler credential role mismatch")
    if runner_transport.runner_transport is not verifier_transport.runner_transport:
        raise PermissionError("G8 credential-pair Runner source mismatch")
    if runner_transport.verifier_transport is not verifier_transport.verifier_transport:
        raise PermissionError("G8 credential-pair Verifier source mismatch")
    if runner_transport.runner_pin != verifier_transport.runner_pin:
        raise PermissionError("G8 credential-pair Runner pin mismatch")
    if runner_transport.verifier_pin != verifier_transport.verifier_pin:
        raise PermissionError("G8 credential-pair Verifier pin mismatch")
    if runner_transport.source_implementation_pin != verifier_transport.source_implementation_pin:
        raise PermissionError("G8 credential-pair source implementation mismatch")
    if runner_transport.provider_effect_pin != verifier_transport.provider_effect_pin:
        raise PermissionError("G8 credential-pair provider effect mismatch")
    return runner_transport, verifier_transport


class _G8RoleBoundRunnerReadHandler(GitHubRefReadHandler):
    """Runner handler that re-attests the selected credential role immediately before READ."""

    _CRITICAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"transport", "current_fence", "trusted_clock", "observation_revision"}
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._CRITICAL_FIELDS and hasattr(self, name):
            raise AttributeError(f"G8 Runner handler {name} binding is immutable")
        super().__setattr__(name, value)

    def observe_ref(
        self,
        *,
        prepared: PreparedIsolatedRuntime,
        activation: ReadOnlyRuntimeActivation,
        target: ExecutionTarget,
    ) -> GitHubRefObservation:
        transport = self.transport
        if type(transport) is not _G8IndependentCredentialPairTransport:
            raise PermissionError("G8 Runner handler transport is not canonical")
        if transport.role != "runner":
            raise PermissionError("G8 Runner handler credential role mismatch")
        fence = _assert_pristine_durable_fence(self.current_fence)
        if type(self.trusted_clock) is not TrustedClockAuthority:
            raise PermissionError("G8 Runner handler trusted clock is not canonical")
        if fence.trusted_clock is not self.trusted_clock:
            raise PermissionError("G8 Runner handler fence/clock binding mismatch")
        if prepared.decision.credential_class != transport.runner_pin.credential_class:
            raise PermissionError("G8 Runner handler credential decision mismatch")
        return super().observe_ref(
            prepared=prepared,
            activation=activation,
            target=target,
        )


class _G8RoleBoundVerifierReadHandler(VerifierGitHubRefReadHandler):
    """Verifier handler that re-attests its independently selected role before READ."""

    _CRITICAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"transport", "trusted_clock", "observation_revision"}
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._CRITICAL_FIELDS and hasattr(self, name):
            raise AttributeError(f"G8 Verifier handler {name} binding is immutable")
        super().__setattr__(name, value)

    def observe_ref(
        self,
        *,
        verifier: VerifierIdentity,
        boundary: IndependentVerificationBoundary,
        decision: VerifierCredentialDecision,
        target: ExecutionTarget,
    ) -> VerifierGitHubRefObservation:
        transport = self.transport
        if type(transport) is not _G8IndependentCredentialPairTransport:
            raise PermissionError("G8 Verifier handler transport is not canonical")
        if transport.role != "verifier":
            raise PermissionError("G8 Verifier handler credential role mismatch")
        if type(self.trusted_clock) is not TrustedClockAuthority:
            raise PermissionError("G8 Verifier handler trusted clock is not canonical")
        if verifier.credential_class != transport.verifier_pin.credential_class:
            raise PermissionError("G8 Verifier handler identity credential class mismatch")
        if decision.credential_class != transport.verifier_pin.credential_class:
            raise PermissionError("G8 Verifier handler credential decision mismatch")
        return super().observe_ref(
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            target=target,
        )


class _G8RoleBoundReadTerminal(CanonicalGitHubReadTerminal):
    """Canonical READ terminal with use-time G8 role and trust-graph invariants."""

    _CRITICAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "capability_registry",
            "capsule_registry",
            "runner_adapter",
            "runner_handler",
            "completion_coordinator",
            "verifier_profile",
            "verifier_policy",
            "verifier_handler",
            "verifier_clock",
            "observed_post_state_revision",
            "strength_revision",
            "result_revision",
        }
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._CRITICAL_FIELDS and hasattr(self, name):
            raise AttributeError(f"G8 READ terminal {name} binding is immutable")
        super().__setattr__(name, value)

    def run(self, *, prepared: CanonicalPreparedExecution) -> CanonicalReadTerminalResult:
        if type(self.runner_adapter) is not IsolatedRunnerAdapter:
            raise PermissionError("G8 READ terminal Runner adapter is not canonical")
        if type(self.runner_handler) is not _G8RoleBoundRunnerReadHandler:
            raise PermissionError("G8 READ terminal Runner handler is not role-bound")
        if type(self.verifier_handler) is not _G8RoleBoundVerifierReadHandler:
            raise PermissionError("G8 READ terminal Verifier handler is not role-bound")
        if type(self.verifier_profile) is not VerifierRuntimeProfile:
            raise PermissionError("G8 READ terminal Verifier profile is not canonical")
        if type(self.verifier_policy) is not VerifierCredentialPolicy:
            raise PermissionError("G8 READ terminal Verifier policy is not canonical")
        if type(self.verifier_clock) is not TrustedClockAuthority:
            raise PermissionError("G8 READ terminal Verifier clock is not canonical")

        runner_transport, verifier_transport = _assert_pair_transport_parity(
            self.runner_handler.transport,
            self.verifier_handler.transport,
        )
        runner_fence = _assert_pristine_durable_fence(self.runner_handler.current_fence)
        if self.runner_adapter.current_fence is not runner_fence:
            raise PermissionError("G8 READ terminal Runner fence binding mismatch")
        if self.runner_handler.trusted_clock is not runner_fence.trusted_clock:
            raise PermissionError("G8 READ terminal Runner clock binding mismatch")
        if self.verifier_handler.trusted_clock is not self.verifier_clock:
            raise PermissionError("G8 READ terminal Verifier clock binding mismatch")
        if self.verifier_profile.credential_class != verifier_transport.verifier_pin.credential_class:
            raise PermissionError("G8 READ terminal Verifier profile credential mismatch")
        if self.verifier_policy.credential_class != verifier_transport.verifier_pin.credential_class:
            raise PermissionError("G8 READ terminal Verifier policy credential mismatch")
        if runner_transport.runner_pin.credential_class == verifier_transport.verifier_pin.credential_class:
            raise PermissionError("G8 READ terminal credential roles collapsed")
        return super().run(prepared=prepared)


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

        source_implementation_pin = _current_credential_source_implementation_pin()
        provider_effect_pin = _current_provider_read_effect_pin()
        runner_pin = source_implementation_pin.pin_snapshot_method(self.runner_transport)
        verifier_pin = source_implementation_pin.pin_snapshot_method(self.verifier_transport)
        if runner_pin.credential_class != self.runner_credential_policy.credential_class:
            raise PermissionError("G8 Runner runtime pin credential class mismatch")
        if verifier_pin.credential_class != self.verifier_policy.credential_class:
            raise PermissionError("G8 Verifier runtime pin credential class mismatch")
        if secrets.compare_digest(
            runner_pin.token_fingerprint,
            verifier_pin.token_fingerprint,
        ):
            raise PermissionError("G8 Runner and Verifier runtime pin material collapsed")
        if runner_pin.attested_principal == verifier_pin.attested_principal:
            raise PermissionError("G8 Runner and Verifier runtime pin principals collapsed")

        runner_effect_transport = _G8IndependentCredentialPairTransport(
            runner_transport=self.runner_transport,
            verifier_transport=self.verifier_transport,
            role="runner",
            runner_pin=runner_pin,
            verifier_pin=verifier_pin,
            source_implementation_pin=source_implementation_pin,
            provider_effect_pin=provider_effect_pin,
        )
        verifier_effect_transport = _G8IndependentCredentialPairTransport(
            runner_transport=self.runner_transport,
            verifier_transport=self.verifier_transport,
            role="verifier",
            runner_pin=runner_pin,
            verifier_pin=verifier_pin,
            source_implementation_pin=source_implementation_pin,
            provider_effect_pin=provider_effect_pin,
        )

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
        runner_handler = _G8RoleBoundRunnerReadHandler(
            transport=runner_effect_transport,
            current_fence=runtime_fence,
            trusted_clock=self.runner_clock,
            observation_revision=self.runner_observation_revision,
        )
        verifier_handler = _G8RoleBoundVerifierReadHandler(
            transport=verifier_effect_transport,
            trusted_clock=self.verifier_clock,
            observation_revision=self.verifier_observation_revision,
        )
        read_terminal = _G8RoleBoundReadTerminal(
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


# Final G8 R1 execution hardening. These final definitions intentionally replace the earlier
# validation-only wrappers above: build_runtime resolves these names at call time. The wrappers
# snapshot validated execution-critical references into fresh, non-exported canonical objects so
# subsequent mutation of the retained public runtime graph cannot change the provider effect used
# by the in-flight call.
_G8_BASE_RUNNER_HANDLER_TYPE: Final = GitHubRefReadHandler
_G8_BASE_RUNNER_HANDLER_INIT: Final = GitHubRefReadHandler.__init__
_G8_BASE_RUNNER_HANDLER_OBSERVE: Final = GitHubRefReadHandler.observe_ref
_G8_BASE_VERIFIER_HANDLER_TYPE: Final = VerifierGitHubRefReadHandler
_G8_BASE_VERIFIER_HANDLER_INIT: Final = VerifierGitHubRefReadHandler.__init__
_G8_BASE_VERIFIER_HANDLER_OBSERVE: Final = VerifierGitHubRefReadHandler.observe_ref
_G8_BASE_READ_TERMINAL_TYPE: Final = CanonicalGitHubReadTerminal
_G8_BASE_READ_TERMINAL_INIT: Final = CanonicalGitHubReadTerminal.__init__
_G8_BASE_READ_TERMINAL_RUN: Final = CanonicalGitHubReadTerminal.run
_G8_RUNNER_ADAPTER_TYPE: Final = IsolatedRunnerAdapter
_G8_RUNNER_ADAPTER_INIT: Final = IsolatedRunnerAdapter.__init__


def _assert_g8_base_execution_implementations() -> None:
    if GitHubRefReadHandler is not _G8_BASE_RUNNER_HANDLER_TYPE:
        raise PermissionError("G8 canonical Runner handler type changed")
    if _G8_BASE_RUNNER_HANDLER_TYPE.__init__ is not _G8_BASE_RUNNER_HANDLER_INIT:
        raise PermissionError("G8 canonical Runner handler initializer changed")
    if _G8_BASE_RUNNER_HANDLER_TYPE.observe_ref is not _G8_BASE_RUNNER_HANDLER_OBSERVE:
        raise PermissionError("G8 canonical Runner observation implementation changed")
    if VerifierGitHubRefReadHandler is not _G8_BASE_VERIFIER_HANDLER_TYPE:
        raise PermissionError("G8 canonical Verifier handler type changed")
    if _G8_BASE_VERIFIER_HANDLER_TYPE.__init__ is not _G8_BASE_VERIFIER_HANDLER_INIT:
        raise PermissionError("G8 canonical Verifier handler initializer changed")
    if _G8_BASE_VERIFIER_HANDLER_TYPE.observe_ref is not _G8_BASE_VERIFIER_HANDLER_OBSERVE:
        raise PermissionError("G8 canonical Verifier observation implementation changed")
    if CanonicalGitHubReadTerminal is not _G8_BASE_READ_TERMINAL_TYPE:
        raise PermissionError("G8 canonical READ terminal type changed")
    if _G8_BASE_READ_TERMINAL_TYPE.__init__ is not _G8_BASE_READ_TERMINAL_INIT:
        raise PermissionError("G8 canonical READ terminal initializer changed")
    if _G8_BASE_READ_TERMINAL_TYPE.run is not _G8_BASE_READ_TERMINAL_RUN:
        raise PermissionError("G8 canonical READ terminal implementation changed")
    if IsolatedRunnerAdapter is not _G8_RUNNER_ADAPTER_TYPE:
        raise PermissionError("G8 canonical Runner adapter type changed")
    if _G8_RUNNER_ADAPTER_TYPE.__init__ is not _G8_RUNNER_ADAPTER_INIT:
        raise PermissionError("G8 canonical Runner adapter initializer changed")


class _G8RoleBoundRunnerReadHandler(GitHubRefReadHandler):  # noqa: F811
    """Runner READ handler with check/use continuity over a local canonical snapshot."""

    _CRITICAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"transport", "current_fence", "trusted_clock", "observation_revision"}
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._CRITICAL_FIELDS and hasattr(self, name):
            raise AttributeError(f"G8 Runner handler {name} binding is immutable")
        super().__setattr__(name, value)

    def observe_ref(
        self,
        *,
        prepared: PreparedIsolatedRuntime,
        activation: ReadOnlyRuntimeActivation,
        target: ExecutionTarget,
    ) -> GitHubRefObservation:
        _assert_g8_base_execution_implementations()
        transport = self.transport
        if type(transport) is not _G8IndependentCredentialPairTransport:
            raise PermissionError("G8 Runner handler transport is not canonical")
        if transport.role != "runner":
            raise PermissionError("G8 Runner handler credential role mismatch")
        source_fence = _assert_pristine_durable_fence(self.current_fence)
        trusted_clock = self.trusted_clock
        observation_revision = self.observation_revision
        if type(trusted_clock) is not TrustedClockAuthority:
            raise PermissionError("G8 Runner handler trusted clock is not canonical")
        if source_fence.trusted_clock is not trusted_clock:
            raise PermissionError("G8 Runner handler fence/clock binding mismatch")
        if prepared.decision.credential_class != transport.runner_pin.credential_class:
            raise PermissionError("G8 Runner handler credential decision mismatch")

        local_fence = DurableCurrentExecutionFence(
            database=source_fence.db,
            trusted_clock=trusted_clock,
        )
        _assert_pristine_durable_fence(local_fence)
        local_handler = object.__new__(_G8_BASE_RUNNER_HANDLER_TYPE)
        _G8_BASE_RUNNER_HANDLER_INIT(
            local_handler,
            transport=transport,
            current_fence=local_fence,
            trusted_clock=trusted_clock,
            observation_revision=observation_revision,
        )
        return _G8_BASE_RUNNER_HANDLER_OBSERVE(
            local_handler,
            prepared=prepared,
            activation=activation,
            target=target,
        )


_G8_HARDENED_RUNNER_HANDLER_TYPE: Final = _G8RoleBoundRunnerReadHandler


class _G8RoleBoundVerifierReadHandler(VerifierGitHubRefReadHandler):  # noqa: F811
    """Verifier READ handler with check/use continuity over a local canonical snapshot."""

    _CRITICAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"transport", "trusted_clock", "observation_revision"}
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._CRITICAL_FIELDS and hasattr(self, name):
            raise AttributeError(f"G8 Verifier handler {name} binding is immutable")
        super().__setattr__(name, value)

    def observe_ref(
        self,
        *,
        verifier: VerifierIdentity,
        boundary: IndependentVerificationBoundary,
        decision: VerifierCredentialDecision,
        target: ExecutionTarget,
    ) -> VerifierGitHubRefObservation:
        _assert_g8_base_execution_implementations()
        transport = self.transport
        if type(transport) is not _G8IndependentCredentialPairTransport:
            raise PermissionError("G8 Verifier handler transport is not canonical")
        if transport.role != "verifier":
            raise PermissionError("G8 Verifier handler credential role mismatch")
        trusted_clock = self.trusted_clock
        observation_revision = self.observation_revision
        if type(trusted_clock) is not TrustedClockAuthority:
            raise PermissionError("G8 Verifier handler trusted clock is not canonical")
        if verifier.credential_class != transport.verifier_pin.credential_class:
            raise PermissionError("G8 Verifier handler identity credential class mismatch")
        if decision.credential_class != transport.verifier_pin.credential_class:
            raise PermissionError("G8 Verifier handler credential decision mismatch")

        local_handler = object.__new__(_G8_BASE_VERIFIER_HANDLER_TYPE)
        _G8_BASE_VERIFIER_HANDLER_INIT(
            local_handler,
            transport=transport,
            trusted_clock=trusted_clock,
            observation_revision=observation_revision,
        )
        return _G8_BASE_VERIFIER_HANDLER_OBSERVE(
            local_handler,
            verifier=verifier,
            boundary=boundary,
            decision=decision,
            target=target,
        )


_G8_HARDENED_VERIFIER_HANDLER_TYPE: Final = _G8RoleBoundVerifierReadHandler


class _G8RoleBoundReadTerminal(CanonicalGitHubReadTerminal):  # noqa: F811
    """READ terminal that executes a one-call local snapshot of the validated G8 graph."""

    _CRITICAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "capability_registry",
            "capsule_registry",
            "runner_adapter",
            "runner_handler",
            "completion_coordinator",
            "verifier_profile",
            "verifier_policy",
            "verifier_handler",
            "verifier_clock",
            "observed_post_state_revision",
            "strength_revision",
            "result_revision",
        }
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._CRITICAL_FIELDS and hasattr(self, name):
            raise AttributeError(f"G8 READ terminal {name} binding is immutable")
        super().__setattr__(name, value)

    def run(self, *, prepared: CanonicalPreparedExecution) -> CanonicalReadTerminalResult:
        _assert_g8_base_execution_implementations()

        capability_registry = self.capability_registry
        capsule_registry = self.capsule_registry
        source_adapter = self.runner_adapter
        source_runner_handler = self.runner_handler
        completion_coordinator = self.completion_coordinator
        verifier_profile = self.verifier_profile
        verifier_policy = self.verifier_policy
        source_verifier_handler = self.verifier_handler
        verifier_clock = self.verifier_clock
        observed_post_state_revision = self.observed_post_state_revision
        strength_revision = self.strength_revision
        result_revision = self.result_revision

        if type(source_adapter) is not _G8_RUNNER_ADAPTER_TYPE:
            raise PermissionError("G8 READ terminal Runner adapter is not canonical")
        if type(source_runner_handler) is not _G8_HARDENED_RUNNER_HANDLER_TYPE:
            raise PermissionError("G8 READ terminal Runner handler is not role-bound")
        if type(source_verifier_handler) is not _G8_HARDENED_VERIFIER_HANDLER_TYPE:
            raise PermissionError("G8 READ terminal Verifier handler is not role-bound")
        if type(verifier_profile) is not VerifierRuntimeProfile:
            raise PermissionError("G8 READ terminal Verifier profile is not canonical")
        if type(verifier_policy) is not VerifierCredentialPolicy:
            raise PermissionError("G8 READ terminal Verifier policy is not canonical")
        if type(verifier_clock) is not TrustedClockAuthority:
            raise PermissionError("G8 READ terminal Verifier clock is not canonical")
        if type(source_adapter.provider) is not GitHubActionsIsolatedRuntimeProvider:
            raise PermissionError("G8 READ terminal Runner provider is not canonical")
        if type(source_adapter.credential_broker) is not ImmutableCredentialBroker:
            raise PermissionError("G8 READ terminal credential broker is not canonical")

        runner_transport, verifier_transport = _assert_pair_transport_parity(
            source_runner_handler.transport,
            source_verifier_handler.transport,
        )
        source_fence = _assert_pristine_durable_fence(source_runner_handler.current_fence)
        runner_clock = source_runner_handler.trusted_clock
        if type(runner_clock) is not TrustedClockAuthority:
            raise PermissionError("G8 READ terminal Runner clock is not canonical")
        if source_adapter.current_fence is not source_fence:
            raise PermissionError("G8 READ terminal Runner fence binding mismatch")
        if runner_clock is not source_fence.trusted_clock:
            raise PermissionError("G8 READ terminal Runner clock binding mismatch")
        if source_verifier_handler.trusted_clock is not verifier_clock:
            raise PermissionError("G8 READ terminal Verifier clock binding mismatch")
        if verifier_profile.credential_class != verifier_transport.verifier_pin.credential_class:
            raise PermissionError("G8 READ terminal Verifier profile credential mismatch")
        if verifier_policy.credential_class != verifier_transport.verifier_pin.credential_class:
            raise PermissionError("G8 READ terminal Verifier policy credential mismatch")
        if runner_transport.runner_pin.credential_class == verifier_transport.verifier_pin.credential_class:
            raise PermissionError("G8 READ terminal credential roles collapsed")

        local_fence = DurableCurrentExecutionFence(
            database=source_fence.db,
            trusted_clock=runner_clock,
        )
        _assert_pristine_durable_fence(local_fence)

        local_adapter = object.__new__(_G8_RUNNER_ADAPTER_TYPE)
        _G8_RUNNER_ADAPTER_INIT(
            local_adapter,
            provider=source_adapter.provider,
            credential_broker=source_adapter.credential_broker,
            current_fence=local_fence,
            identity_revision=source_adapter.identity_revision,
            boundary_revision=source_adapter.boundary_revision,
            activation_revision=source_adapter.activation_revision,
        )
        local_runner_handler = object.__new__(_G8_HARDENED_RUNNER_HANDLER_TYPE)
        _G8_BASE_RUNNER_HANDLER_INIT(
            local_runner_handler,
            transport=runner_transport,
            current_fence=local_fence,
            trusted_clock=runner_clock,
            observation_revision=source_runner_handler.observation_revision,
        )
        local_verifier_handler = object.__new__(_G8_HARDENED_VERIFIER_HANDLER_TYPE)
        _G8_BASE_VERIFIER_HANDLER_INIT(
            local_verifier_handler,
            transport=verifier_transport,
            trusted_clock=verifier_clock,
            observation_revision=source_verifier_handler.observation_revision,
        )

        local_terminal = object.__new__(_G8_BASE_READ_TERMINAL_TYPE)
        _G8_BASE_READ_TERMINAL_INIT(
            local_terminal,
            capability_registry=capability_registry,
            capsule_registry=capsule_registry,
            runner_adapter=local_adapter,
            runner_handler=local_runner_handler,
            completion_coordinator=completion_coordinator,
            verifier_profile=verifier_profile,
            verifier_policy=verifier_policy,
            verifier_handler=local_verifier_handler,
            verifier_clock=verifier_clock,
            observed_post_state_revision=observed_post_state_revision,
            strength_revision=strength_revision,
            result_revision=result_revision,
        )
        return _G8_BASE_READ_TERMINAL_RUN(local_terminal, prepared=prepared)
