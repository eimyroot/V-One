from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol, runtime_checkable

from .capability_registry import CapabilityDefinition
from .credential_broker import (
    READ_ONLY_ACCESS_MODE,
    CredentialAccessDecision,
    CredentialBroker,
)
from .evidence_primitives import canonical_json
from .execution_capsule import ExecutionCapsule
from .execution_lease import ExecutionLease
from .runner_identity import (
    DENY_ALL_NETWORK_DEFAULT,
    READ_ONLY_EFFECT_CLASS,
    RunnerBoundary,
    RunnerIdentity,
)

RUNTIME_BOOTSTRAP_TYPE: Final = "isolated-runtime-bootstrap/v1"
RUNTIME_BOOTSTRAP_IDENTITY_TYPE: Final = "isolated-runtime-bootstrap-id/v1"
RUNTIME_ACTIVATION_TYPE: Final = "read-only-runtime-activation/v1"
READ_ONLY_MOUNT_MODE: Final = "READ_ONLY"

_BOOTSTRAP_FIELDS = frozenset(
    {
        "schema_version",
        "bootstrap_type",
        "bootstrap_id",
        "provider",
        "provider_instance_id",
        "runner_class",
        "environment",
        "rootfs_digest",
        "resource_limit_profile_digest",
        "network_policy_digest",
        "workspace_mount_mode",
        "network_egress_default",
        "inherited_credentials",
        "provider_mutation_allowed",
        "bootstrap_revision",
        "bootstrap_digest",
    }
)
_ACTIVATION_FIELDS = frozenset(
    {
        "schema_version",
        "activation_type",
        "provider",
        "provider_instance_id",
        "runner_id",
        "runner_identity_digest",
        "runner_boundary_digest",
        "credential_decision_id",
        "credential_decision_digest",
        "lease_id",
        "lease_digest",
        "execution_id",
        "execution_epoch",
        "execution_capsule_digest",
        "capability_definition_identity",
        "access_mode",
        "workspace_mount_mode",
        "network_egress_default",
        "provider_mutation_allowed",
        "activation_revision",
        "activation_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


class IsolatedRunnerDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class IsolatedRuntimeBootstrap:
    """Provider-reported D3 bootstrap evidence before any credential delivery.

    Bootstrap starts with a deny-all network posture, no inherited credentials and
    a read-only workspace mount. It is descriptive evidence, not authority.
    """

    bootstrap_id: str
    provider: str
    provider_instance_id: str
    runner_class: str
    environment: str
    rootfs_digest: str
    resource_limit_profile_digest: str
    network_policy_digest: str
    workspace_mount_mode: str
    network_egress_default: str
    inherited_credentials: bool
    provider_mutation_allowed: bool
    bootstrap_revision: str
    bootstrap_digest: str

    def __post_init__(self) -> None:
        for field in (
            "bootstrap_id",
            "rootfs_digest",
            "resource_limit_profile_digest",
            "network_policy_digest",
            "bootstrap_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "provider",
            "provider_instance_id",
            "runner_class",
            "environment",
            "bootstrap_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.workspace_mount_mode != READ_ONLY_MOUNT_MODE:
            raise ValueError("D3 workspace mount must be READ_ONLY")
        if self.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise ValueError("D3 network egress default must be DENY_ALL")
        if self.inherited_credentials is not False:
            raise ValueError("D3 runtime cannot inherit credentials")
        if self.provider_mutation_allowed is not False:
            raise ValueError("D3 runtime cannot allow provider mutation")
        if self.bootstrap_id != self._logical_identity():
            raise ValueError("bootstrap_id does not match isolated runtime identity")
        if self.bootstrap_digest != _digest(self._claims_without_digest()):
            raise ValueError("bootstrap_digest does not match isolated runtime bootstrap")

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        provider_instance_id: str,
        runner_class: str,
        environment: str,
        rootfs_digest: str,
        resource_limit_profile_digest: str,
        network_policy_digest: str,
        bootstrap_revision: str,
    ) -> IsolatedRuntimeBootstrap:
        logical_identity = _digest(
            {
                "identity_type": RUNTIME_BOOTSTRAP_IDENTITY_TYPE,
                "provider": provider,
                "provider_instance_id": provider_instance_id,
                "runner_class": runner_class,
                "environment": environment,
            }
        )
        claims = {
            "schema_version": 1,
            "bootstrap_type": RUNTIME_BOOTSTRAP_TYPE,
            "bootstrap_id": logical_identity,
            "provider": provider,
            "provider_instance_id": provider_instance_id,
            "runner_class": runner_class,
            "environment": environment,
            "rootfs_digest": rootfs_digest,
            "resource_limit_profile_digest": resource_limit_profile_digest,
            "network_policy_digest": network_policy_digest,
            "workspace_mount_mode": READ_ONLY_MOUNT_MODE,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "inherited_credentials": False,
            "provider_mutation_allowed": False,
            "bootstrap_revision": bootstrap_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "bootstrap_type"}
        }
        return cls(**values, bootstrap_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> IsolatedRuntimeBootstrap:
        _require_exact_fields(value, _BOOTSTRAP_FIELDS, contract=RUNTIME_BOOTSTRAP_TYPE)
        if (
            value["schema_version"] != 1
            or value["bootstrap_type"] != RUNTIME_BOOTSTRAP_TYPE
        ):
            raise ValueError("isolated-runtime-bootstrap/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _BOOTSTRAP_FIELDS
                if key not in {"schema_version", "bootstrap_type"}
            }
        )

    def _logical_identity(self) -> str:
        return _digest(
            {
                "identity_type": RUNTIME_BOOTSTRAP_IDENTITY_TYPE,
                "provider": self.provider,
                "provider_instance_id": self.provider_instance_id,
                "runner_class": self.runner_class,
                "environment": self.environment,
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "bootstrap_type": RUNTIME_BOOTSTRAP_TYPE,
            "bootstrap_id": self.bootstrap_id,
            "provider": self.provider,
            "provider_instance_id": self.provider_instance_id,
            "runner_class": self.runner_class,
            "environment": self.environment,
            "rootfs_digest": self.rootfs_digest,
            "resource_limit_profile_digest": self.resource_limit_profile_digest,
            "network_policy_digest": self.network_policy_digest,
            "workspace_mount_mode": self.workspace_mount_mode,
            "network_egress_default": self.network_egress_default,
            "inherited_credentials": self.inherited_credentials,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "bootstrap_revision": self.bootstrap_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "bootstrap_digest": self.bootstrap_digest}


@dataclass(frozen=True, slots=True)
class ReadOnlyRuntimeActivation:
    """Provider-reported activation metadata after the immediate C4 fence recheck.

    No credential material, provider response body or command output is allowed here.
    """

    provider: str
    provider_instance_id: str
    runner_id: str
    runner_identity_digest: str
    runner_boundary_digest: str
    credential_decision_id: str
    credential_decision_digest: str
    lease_id: str
    lease_digest: str
    execution_id: str
    execution_epoch: int
    execution_capsule_digest: str
    capability_definition_identity: str
    access_mode: str
    workspace_mount_mode: str
    network_egress_default: str
    provider_mutation_allowed: bool
    activation_revision: str
    activation_digest: str

    def __post_init__(self) -> None:
        for field in (
            "runner_id",
            "runner_identity_digest",
            "runner_boundary_digest",
            "credential_decision_id",
            "credential_decision_digest",
            "lease_id",
            "lease_digest",
            "execution_capsule_digest",
            "capability_definition_identity",
            "activation_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "provider",
            "provider_instance_id",
            "execution_id",
            "activation_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if isinstance(self.execution_epoch, bool) or not isinstance(self.execution_epoch, int):
            raise ValueError("execution_epoch must be an integer")
        if self.execution_epoch < 1:
            raise ValueError("execution_epoch must be >= 1")
        if self.access_mode != READ_ONLY_ACCESS_MODE:
            raise ValueError("D3 runtime activation must be READ_ONLY")
        if self.workspace_mount_mode != READ_ONLY_MOUNT_MODE:
            raise ValueError("D3 workspace mount must remain READ_ONLY")
        if self.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise ValueError("D3 network default must remain DENY_ALL")
        if self.provider_mutation_allowed is not False:
            raise ValueError("D3 runtime activation cannot allow provider mutation")
        if self.activation_digest != _digest(self._claims_without_digest()):
            raise ValueError("activation_digest does not match read-only runtime activation")

    @classmethod
    def create(
        cls,
        *,
        bootstrap: IsolatedRuntimeBootstrap,
        identity: RunnerIdentity,
        boundary: RunnerBoundary,
        decision: CredentialAccessDecision,
        lease: ExecutionLease,
        activation_revision: str,
    ) -> ReadOnlyRuntimeActivation:
        _assert_runtime_binding(
            bootstrap=bootstrap,
            identity=identity,
            boundary=boundary,
            decision=decision,
            lease=lease,
        )
        claims = {
            "schema_version": 1,
            "activation_type": RUNTIME_ACTIVATION_TYPE,
            "provider": bootstrap.provider,
            "provider_instance_id": bootstrap.provider_instance_id,
            "runner_id": identity.runner_id,
            "runner_identity_digest": identity.identity_digest,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_id": decision.decision_id,
            "credential_decision_digest": decision.decision_digest,
            "lease_id": lease.lease_id,
            "lease_digest": lease.lease_digest,
            "execution_id": lease.execution_id,
            "execution_epoch": lease.execution_epoch,
            "execution_capsule_digest": boundary.execution_capsule_digest,
            "capability_definition_identity": boundary.capability_definition_identity,
            "access_mode": READ_ONLY_ACCESS_MODE,
            "workspace_mount_mode": READ_ONLY_MOUNT_MODE,
            "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
            "provider_mutation_allowed": False,
            "activation_revision": activation_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "activation_type"}
        }
        return cls(**values, activation_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ReadOnlyRuntimeActivation:
        _require_exact_fields(value, _ACTIVATION_FIELDS, contract=RUNTIME_ACTIVATION_TYPE)
        if (
            value["schema_version"] != 1
            or value["activation_type"] != RUNTIME_ACTIVATION_TYPE
        ):
            raise ValueError("read-only-runtime-activation/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _ACTIVATION_FIELDS
                if key not in {"schema_version", "activation_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "activation_type": RUNTIME_ACTIVATION_TYPE,
            "provider": self.provider,
            "provider_instance_id": self.provider_instance_id,
            "runner_id": self.runner_id,
            "runner_identity_digest": self.runner_identity_digest,
            "runner_boundary_digest": self.runner_boundary_digest,
            "credential_decision_id": self.credential_decision_id,
            "credential_decision_digest": self.credential_decision_digest,
            "lease_id": self.lease_id,
            "lease_digest": self.lease_digest,
            "execution_id": self.execution_id,
            "execution_epoch": self.execution_epoch,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "access_mode": self.access_mode,
            "workspace_mount_mode": self.workspace_mount_mode,
            "network_egress_default": self.network_egress_default,
            "provider_mutation_allowed": self.provider_mutation_allowed,
            "activation_revision": self.activation_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "activation_digest": self.activation_digest}


@dataclass(frozen=True, slots=True)
class PreparedIsolatedRuntime:
    bootstrap: IsolatedRuntimeBootstrap
    identity: RunnerIdentity
    boundary: RunnerBoundary
    decision: CredentialAccessDecision
    lease: ExecutionLease

    def __post_init__(self) -> None:
        _assert_runtime_binding(
            bootstrap=self.bootstrap,
            identity=self.identity,
            boundary=self.boundary,
            decision=self.decision,
            lease=self.lease,
        )


@runtime_checkable
class CurrentExecutionFence(Protocol):
    def assert_current(self, *, lease: ExecutionLease) -> None:
        """Fail closed unless this exact C4 lease is still current and unexpired."""
        ...


@runtime_checkable
class IsolatedRuntimeProvider(Protocol):
    def bootstrap(
        self,
        *,
        lease: ExecutionLease,
        capsule: ExecutionCapsule,
    ) -> IsolatedRuntimeBootstrap:
        """Create a credential-free deny-all runtime and report exact observed profile claims."""
        ...

    def activate_read_only(
        self,
        *,
        prepared: PreparedIsolatedRuntime,
    ) -> ReadOnlyRuntimeActivation:
        """Activate only the already-authorized READ-only profile.

        Any usable secret delivery happens inside the provider adapter/out-of-band secret
        channel and must never be returned through this interface.
        """
        ...


class IsolatedRunnerAdapter:
    """D3 two-phase isolated-runner orchestration over D1/D2/C4 contracts.

    Phase 1 bootstraps a credential-free runtime, then creates the concrete D1 identity and
    boundary and asks D2 for a READ-only access decision. Phase 2 rechecks the durable current
    C4 lease immediately before asking the provider port to activate that exact READ-only runtime.

    The adapter does not execute a capability or perform a provider read. D4 starts provider
    observation after this activation boundary.
    """

    def __init__(
        self,
        *,
        provider: IsolatedRuntimeProvider,
        credential_broker: CredentialBroker,
        current_fence: CurrentExecutionFence,
        identity_revision: str,
        boundary_revision: str,
        activation_revision: str,
    ) -> None:
        if not isinstance(provider, IsolatedRuntimeProvider):
            raise ValueError("provider must implement IsolatedRuntimeProvider")
        if not isinstance(credential_broker, CredentialBroker):
            raise ValueError("credential_broker must implement CredentialBroker")
        if not isinstance(current_fence, CurrentExecutionFence):
            raise ValueError("current_fence must implement CurrentExecutionFence")
        self.provider = provider
        self.credential_broker = credential_broker
        self.current_fence = current_fence
        self.identity_revision = _require_text(identity_revision, field="identity_revision")
        self.boundary_revision = _require_text(boundary_revision, field="boundary_revision")
        self.activation_revision = _require_text(activation_revision, field="activation_revision")

    def prepare(
        self,
        *,
        lease: ExecutionLease,
        capsule: ExecutionCapsule,
        definition: CapabilityDefinition,
    ) -> PreparedIsolatedRuntime:
        if not isinstance(lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")
        if not isinstance(capsule, ExecutionCapsule):
            raise ValueError("capsule must be ExecutionCapsule")
        if not isinstance(definition, CapabilityDefinition):
            raise ValueError("definition must be CapabilityDefinition")
        if definition.effect_class != READ_ONLY_EFFECT_CLASS:
            raise IsolatedRunnerDenied("PHASE_D_EFFECT_NOT_READ_ONLY")
        if lease.execution_capsule_digest != capsule.capsule_digest:
            raise IsolatedRunnerDenied("RUNTIME_CAPSULE_BINDING_MISMATCH")
        if lease.runner_class != capsule.runner_class:
            raise IsolatedRunnerDenied("RUNTIME_RUNNER_CLASS_MISMATCH")

        bootstrap = self.provider.bootstrap(lease=lease, capsule=capsule)
        self._assert_bootstrap_bound(bootstrap=bootstrap, lease=lease, capsule=capsule)

        identity = RunnerIdentity.create(
            runner_class=bootstrap.runner_class,
            provider=bootstrap.provider,
            provider_instance_id=bootstrap.provider_instance_id,
            environment=bootstrap.environment,
            rootfs_digest=bootstrap.rootfs_digest,
            resource_limit_profile_digest=bootstrap.resource_limit_profile_digest,
            network_policy_digest=bootstrap.network_policy_digest,
            identity_revision=self.identity_revision,
        )
        boundary = RunnerBoundary.create(
            identity=identity,
            lease=lease,
            capsule=capsule,
            definition=definition,
            boundary_revision=self.boundary_revision,
        )
        decision = self.credential_broker.authorize(boundary=boundary, lease=lease)
        return PreparedIsolatedRuntime(
            bootstrap=bootstrap,
            identity=identity,
            boundary=boundary,
            decision=decision,
            lease=lease,
        )

    def activate(self, *, prepared: PreparedIsolatedRuntime) -> ReadOnlyRuntimeActivation:
        if not isinstance(prepared, PreparedIsolatedRuntime):
            raise ValueError("prepared must be PreparedIsolatedRuntime")
        _assert_runtime_binding(
            bootstrap=prepared.bootstrap,
            identity=prepared.identity,
            boundary=prepared.boundary,
            decision=prepared.decision,
            lease=prepared.lease,
        )

        # Intentionally the last control-plane decision before provider activation.
        self.current_fence.assert_current(lease=prepared.lease)

        activation = self.provider.activate_read_only(prepared=prepared)
        expected = ReadOnlyRuntimeActivation.create(
            bootstrap=prepared.bootstrap,
            identity=prepared.identity,
            boundary=prepared.boundary,
            decision=prepared.decision,
            lease=prepared.lease,
            activation_revision=self.activation_revision,
        )
        if activation != expected:
            raise IsolatedRunnerDenied("RUNTIME_ACTIVATION_BINDING_MISMATCH")
        return activation

    @staticmethod
    def _assert_bootstrap_bound(
        *,
        bootstrap: IsolatedRuntimeBootstrap,
        lease: ExecutionLease,
        capsule: ExecutionCapsule,
    ) -> None:
        if not isinstance(bootstrap, IsolatedRuntimeBootstrap):
            raise IsolatedRunnerDenied("RUNTIME_BOOTSTRAP_INVALID")
        if bootstrap.runner_class != lease.runner_class:
            raise IsolatedRunnerDenied("RUNTIME_RUNNER_CLASS_MISMATCH")
        if bootstrap.environment != lease.environment:
            raise IsolatedRunnerDenied("RUNTIME_ENVIRONMENT_MISMATCH")
        if bootstrap.rootfs_digest != capsule.rootfs_digest:
            raise IsolatedRunnerDenied("RUNTIME_ROOTFS_MISMATCH")
        if bootstrap.resource_limit_profile_digest != capsule.resource_limit_profile_digest:
            raise IsolatedRunnerDenied("RUNTIME_RESOURCE_PROFILE_MISMATCH")
        if bootstrap.network_policy_digest != capsule.network_policy_digest:
            raise IsolatedRunnerDenied("RUNTIME_NETWORK_POLICY_MISMATCH")
        if bootstrap.workspace_mount_mode != READ_ONLY_MOUNT_MODE:
            raise IsolatedRunnerDenied("RUNTIME_WORKSPACE_NOT_READ_ONLY")
        if bootstrap.network_egress_default != DENY_ALL_NETWORK_DEFAULT:
            raise IsolatedRunnerDenied("RUNTIME_NETWORK_NOT_DENY_ALL")
        if bootstrap.inherited_credentials is not False:
            raise IsolatedRunnerDenied("RUNTIME_INHERITED_CREDENTIALS")
        if bootstrap.provider_mutation_allowed is not False:
            raise IsolatedRunnerDenied("RUNTIME_PROVIDER_MUTATION_ALLOWED")


def _assert_runtime_binding(
    *,
    bootstrap: IsolatedRuntimeBootstrap,
    identity: RunnerIdentity,
    boundary: RunnerBoundary,
    decision: CredentialAccessDecision,
    lease: ExecutionLease,
) -> None:
    if bootstrap.provider != identity.provider:
        raise IsolatedRunnerDenied("RUNTIME_PROVIDER_IDENTITY_MISMATCH")
    if bootstrap.provider_instance_id != identity.provider_instance_id:
        raise IsolatedRunnerDenied("RUNTIME_PROVIDER_INSTANCE_MISMATCH")
    if bootstrap.runner_class != identity.runner_class:
        raise IsolatedRunnerDenied("RUNTIME_RUNNER_CLASS_MISMATCH")
    if bootstrap.environment != identity.environment:
        raise IsolatedRunnerDenied("RUNTIME_ENVIRONMENT_MISMATCH")
    if bootstrap.rootfs_digest != identity.rootfs_digest:
        raise IsolatedRunnerDenied("RUNTIME_ROOTFS_MISMATCH")
    if bootstrap.resource_limit_profile_digest != identity.resource_limit_profile_digest:
        raise IsolatedRunnerDenied("RUNTIME_RESOURCE_PROFILE_MISMATCH")
    if bootstrap.network_policy_digest != identity.network_policy_digest:
        raise IsolatedRunnerDenied("RUNTIME_NETWORK_POLICY_MISMATCH")
    if boundary.runner_id != identity.runner_id:
        raise IsolatedRunnerDenied("RUNTIME_BOUNDARY_RUNNER_MISMATCH")
    if boundary.runner_identity_digest != identity.identity_digest:
        raise IsolatedRunnerDenied("RUNTIME_BOUNDARY_IDENTITY_MISMATCH")
    if boundary.lease_id != lease.lease_id or boundary.lease_digest != lease.lease_digest:
        raise IsolatedRunnerDenied("RUNTIME_BOUNDARY_LEASE_MISMATCH")
    if boundary.execution_epoch != lease.execution_epoch:
        raise IsolatedRunnerDenied("RUNTIME_BOUNDARY_EPOCH_MISMATCH")
    if decision.runner_boundary_digest != boundary.boundary_digest:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_BOUNDARY_MISMATCH")
    if decision.runner_id != identity.runner_id:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_RUNNER_MISMATCH")
    if decision.lease_id != lease.lease_id or decision.lease_digest != lease.lease_digest:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_LEASE_MISMATCH")
    if decision.execution_epoch != lease.execution_epoch:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_EPOCH_MISMATCH")
    if decision.execution_capsule_digest != boundary.execution_capsule_digest:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_CAPSULE_MISMATCH")
    if decision.capability_definition_identity != boundary.capability_definition_identity:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_CAPABILITY_MISMATCH")
    if decision.access_mode != READ_ONLY_ACCESS_MODE:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_NOT_READ_ONLY")
    if decision.provider_mutation_allowed is not False:
        raise IsolatedRunnerDenied("RUNTIME_CREDENTIAL_MUTATION_ALLOWED")
