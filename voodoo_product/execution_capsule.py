from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Self

from .approval_policy import VALID_ENVIRONMENTS
from .authoritative_grant import ExecutionBinding
from .capability_registry import ImmutableCapabilityRegistry
from .evidence_primitives import canonical_json
from .precondition_witness import ATOMIC_PROVIDER_CONDITION, READ_THEN_COMPARE

EXECUTION_CAPSULE_TYPE: Final = "execution-capsule/v1"
CAPSULE_ACTIVATION_TYPE: Final = "execution-capsule-activation/v1"

_CAPSULE_FIELDS = frozenset(
    {
        "schema_version",
        "capsule_type",
        "capability_definition_identity",
        "target_kind",
        "handler_id",
        "handler_digest",
        "module_manifest_digest",
        "artifact_kind",
        "artifact_digest",
        "rootfs_digest",
        "dependency_lock_digest",
        "sbom_digest",
        "network_policy_digest",
        "resource_limit_profile_digest",
        "credential_class",
        "runner_class",
        "precondition_enforcement_class",
        "verification_class",
        "verification_contract_identity",
        "capsule_revision",
        "capsule_digest",
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


@dataclass(frozen=True, slots=True)
class ExecutionCapsule:
    """Content-addressed exact execution environment contract.

    This contract describes what may later run. It does not execute code, acquire credentials,
    dispatch work, or prove post-state.
    """

    capability_definition_identity: str
    target_kind: str
    handler_id: str
    handler_digest: str
    module_manifest_digest: str
    artifact_kind: str
    artifact_digest: str
    rootfs_digest: str
    dependency_lock_digest: str
    sbom_digest: str
    network_policy_digest: str
    resource_limit_profile_digest: str
    credential_class: str
    runner_class: str
    precondition_enforcement_class: str
    verification_class: str
    verification_contract_identity: str
    capsule_revision: str
    capsule_digest: str

    def __post_init__(self) -> None:
        for field in (
            "capability_definition_identity",
            "handler_digest",
            "module_manifest_digest",
            "artifact_digest",
            "rootfs_digest",
            "dependency_lock_digest",
            "sbom_digest",
            "network_policy_digest",
            "resource_limit_profile_digest",
            "verification_contract_identity",
            "capsule_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "target_kind",
            "handler_id",
            "artifact_kind",
            "credential_class",
            "runner_class",
            "verification_class",
            "capsule_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.precondition_enforcement_class not in {
            READ_THEN_COMPARE,
            ATOMIC_PROVIDER_CONDITION,
        }:
            raise ValueError("precondition_enforcement_class is unsupported")
        if self.capsule_digest != _digest(self._claims_without_digest()):
            raise ValueError("capsule_digest does not match execution capsule")

    @classmethod
    def create(
        cls,
        *,
        capability_definition_identity: str,
        target_kind: str,
        handler_id: str,
        handler_digest: str,
        module_manifest_digest: str,
        artifact_kind: str,
        artifact_digest: str,
        rootfs_digest: str,
        dependency_lock_digest: str,
        sbom_digest: str,
        network_policy_digest: str,
        resource_limit_profile_digest: str,
        credential_class: str,
        runner_class: str,
        precondition_enforcement_class: str,
        verification_class: str,
        verification_contract_identity: str,
        capsule_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "capsule_type": EXECUTION_CAPSULE_TYPE,
            "capability_definition_identity": capability_definition_identity,
            "target_kind": target_kind,
            "handler_id": handler_id,
            "handler_digest": handler_digest,
            "module_manifest_digest": module_manifest_digest,
            "artifact_kind": artifact_kind,
            "artifact_digest": artifact_digest,
            "rootfs_digest": rootfs_digest,
            "dependency_lock_digest": dependency_lock_digest,
            "sbom_digest": sbom_digest,
            "network_policy_digest": network_policy_digest,
            "resource_limit_profile_digest": resource_limit_profile_digest,
            "credential_class": credential_class,
            "runner_class": runner_class,
            "precondition_enforcement_class": precondition_enforcement_class,
            "verification_class": verification_class,
            "verification_contract_identity": verification_contract_identity,
            "capsule_revision": capsule_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "capsule_type"}
        }
        return cls(**values, capsule_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _CAPSULE_FIELDS, contract=EXECUTION_CAPSULE_TYPE)
        if value["schema_version"] != 1 or value["capsule_type"] != EXECUTION_CAPSULE_TYPE:
            raise ValueError("execution-capsule/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _CAPSULE_FIELDS
                if key not in {"schema_version", "capsule_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "capsule_type": EXECUTION_CAPSULE_TYPE,
            "capability_definition_identity": self.capability_definition_identity,
            "target_kind": self.target_kind,
            "handler_id": self.handler_id,
            "handler_digest": self.handler_digest,
            "module_manifest_digest": self.module_manifest_digest,
            "artifact_kind": self.artifact_kind,
            "artifact_digest": self.artifact_digest,
            "rootfs_digest": self.rootfs_digest,
            "dependency_lock_digest": self.dependency_lock_digest,
            "sbom_digest": self.sbom_digest,
            "network_policy_digest": self.network_policy_digest,
            "resource_limit_profile_digest": self.resource_limit_profile_digest,
            "credential_class": self.credential_class,
            "runner_class": self.runner_class,
            "precondition_enforcement_class": self.precondition_enforcement_class,
            "verification_class": self.verification_class,
            "verification_contract_identity": self.verification_contract_identity,
            "capsule_revision": self.capsule_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "capsule_digest": self.capsule_digest}


@dataclass(frozen=True, slots=True)
class CapsuleActivation:
    execution_capsule_digest: str
    activation_generation: int
    enabled_environments: tuple[str, ...]
    revoked: bool
    production_eligible: bool
    activation_digest: str

    def __post_init__(self) -> None:
        _require_digest(self.execution_capsule_digest, field="execution_capsule_digest")
        if type(self.activation_generation) is not int or self.activation_generation < 1:
            raise ValueError("activation_generation must be positive")
        if (
            not self.enabled_environments
            or self.enabled_environments != tuple(sorted(set(self.enabled_environments)))
            or any(item not in VALID_ENVIRONMENTS for item in self.enabled_environments)
        ):
            raise ValueError("enabled_environments are invalid")
        if type(self.revoked) is not bool:
            raise ValueError("revoked must be boolean")
        if type(self.production_eligible) is not bool:
            raise ValueError("production_eligible must be boolean")
        if self.production_eligible and "production" not in self.enabled_environments:
            raise ValueError("production-eligible capsule must enable production")
        _require_digest(self.activation_digest, field="activation_digest")
        if self.activation_digest != _digest(self._claims_without_digest()):
            raise ValueError("activation_digest does not match capsule activation")

    @classmethod
    def create(
        cls,
        *,
        execution_capsule_digest: str,
        activation_generation: int,
        enabled_environments: Iterable[str],
        revoked: bool = False,
        production_eligible: bool = False,
    ) -> Self:
        environments = tuple(sorted(set(enabled_environments)))
        claims = {
            "activation_type": CAPSULE_ACTIVATION_TYPE,
            "execution_capsule_digest": execution_capsule_digest,
            "activation_generation": activation_generation,
            "enabled_environments": list(environments),
            "revoked": revoked,
            "production_eligible": production_eligible,
        }
        return cls(
            execution_capsule_digest=execution_capsule_digest,
            activation_generation=activation_generation,
            enabled_environments=environments,
            revoked=revoked,
            production_eligible=production_eligible,
            activation_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "activation_type": CAPSULE_ACTIVATION_TYPE,
            "execution_capsule_digest": self.execution_capsule_digest,
            "activation_generation": self.activation_generation,
            "enabled_environments": list(self.enabled_environments),
            "revoked": self.revoked,
            "production_eligible": self.production_eligible,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "activation_digest": self.activation_digest}


class ImmutableExecutionCapsuleRegistry:
    """Immutable exact capsule selection bound to capability definitions."""

    def __init__(
        self,
        *,
        capability_registry: ImmutableCapabilityRegistry,
        capsules: Iterable[ExecutionCapsule],
        activations: Iterable[CapsuleActivation],
    ) -> None:
        if not isinstance(capability_registry, ImmutableCapabilityRegistry):
            raise ValueError("capability_registry is invalid")

        by_definition: dict[str, ExecutionCapsule] = {}
        by_digest: dict[str, ExecutionCapsule] = {}
        for capsule in capsules:
            if not isinstance(capsule, ExecutionCapsule):
                raise ValueError("capsule is invalid")
            try:
                definition = capability_registry.definition_by_identity(
                    capsule.capability_definition_identity
                )
            except LookupError as exc:
                raise ValueError("capsule references unknown capability definition") from exc
            if capsule.handler_id != definition.handler_id:
                raise ValueError("capsule handler does not match capability definition")
            if capsule.target_kind != definition.target_kind:
                raise ValueError("capsule target kind does not match capability definition")
            if capsule.verification_class != definition.verification_class:
                raise ValueError("capsule verification class does not match capability definition")
            if capsule.capability_definition_identity in by_definition:
                raise ValueError("duplicate capsule for capability definition")
            if capsule.capsule_digest in by_digest:
                raise ValueError("duplicate execution capsule digest")
            by_definition[capsule.capability_definition_identity] = capsule
            by_digest[capsule.capsule_digest] = capsule

        activation_by_digest: dict[str, CapsuleActivation] = {}
        for activation in activations:
            if not isinstance(activation, CapsuleActivation):
                raise ValueError("capsule activation is invalid")
            if activation.execution_capsule_digest not in by_digest:
                raise ValueError("activation references unknown execution capsule")
            if activation.execution_capsule_digest in activation_by_digest:
                raise ValueError("duplicate activation for execution capsule")
            capsule = by_digest[activation.execution_capsule_digest]
            definition = capability_registry.definition_by_identity(
                capsule.capability_definition_identity
            )
            if not set(activation.enabled_environments).issubset(
                set(definition.supported_environments)
            ):
                raise ValueError("capsule activation enables unsupported environment")
            if activation.production_eligible and not definition.production_eligible:
                raise ValueError("capsule cannot exceed capability production eligibility")
            activation_by_digest[activation.execution_capsule_digest] = activation

        if not by_definition:
            raise ValueError("execution capsule registry requires at least one capsule")
        self.capability_registry = capability_registry
        self._by_definition = MappingProxyType(by_definition)
        self._by_digest = MappingProxyType(by_digest)
        self._activations = MappingProxyType(activation_by_digest)

    def capsule_for_definition(self, definition_identity: str) -> ExecutionCapsule:
        _require_digest(definition_identity, field="definition_identity")
        try:
            return self._by_definition[definition_identity]
        except KeyError as exc:
            raise LookupError("execution capsule not found") from exc

    def activation(self, capsule_digest: str) -> CapsuleActivation:
        _require_digest(capsule_digest, field="capsule_digest")
        try:
            return self._activations[capsule_digest]
        except KeyError as exc:
            raise PermissionError("execution capsule is not activated") from exc

    def resolve_for_binding(
        self,
        *,
        capability_definition_identity: str,
        environment: str,
        target_kind: str,
    ) -> tuple[ExecutionCapsule, CapsuleActivation]:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        definition = self.capability_registry.definition_by_identity(
            capability_definition_identity
        )
        capability_activation = self.capability_registry.activation(
            capability_definition_identity
        )
        if capability_activation.revoked:
            raise PermissionError("capability activation is revoked")
        if environment not in capability_activation.enabled_environments:
            raise PermissionError("capability is not active in environment")
        if environment not in definition.supported_environments:
            raise PermissionError("capability does not support environment")
        if environment == "production" and not definition.production_eligible:
            raise PermissionError("capability is not production eligible")

        capsule = self.capsule_for_definition(capability_definition_identity)
        activation = self.activation(capsule.capsule_digest)
        if activation.revoked:
            raise PermissionError("execution capsule activation is revoked")
        if environment not in activation.enabled_environments:
            raise PermissionError("execution capsule is not active in environment")
        if environment == "production" and not activation.production_eligible:
            raise PermissionError("execution capsule is not production eligible")
        if target_kind != definition.target_kind or target_kind != capsule.target_kind:
            raise PermissionError("execution capsule target kind mismatch")
        return capsule, activation


class AuthoritativeExecutionBindingAuthority:
    """Resolve B1 ExecutionBinding only from the immutable active capsule registry."""

    def __init__(
        self,
        *,
        registry: ImmutableExecutionCapsuleRegistry,
        authority_revision: str,
    ) -> None:
        if not isinstance(registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("registry is invalid")
        self.registry = registry
        self.authority_revision = _require_text(
            authority_revision,
            field="authority_revision",
        )

    def resolve(
        self,
        *,
        capability_definition_identity: str,
        environment: str,
        target_kind: str,
    ) -> ExecutionBinding:
        capsule, _ = self.registry.resolve_for_binding(
            capability_definition_identity=capability_definition_identity,
            environment=environment,
            target_kind=target_kind,
        )
        return ExecutionBinding.create(
            capability_definition_identity=capability_definition_identity,
            environment=environment,
            target_kind=target_kind,
            execution_capsule_digest=capsule.capsule_digest,
            runner_class=capsule.runner_class,
            authority_revision=self.authority_revision,
        )
