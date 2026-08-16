from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Self

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json
from .execution_contract import REQUIRED_EXECUTION_PERMISSION

CAPABILITY_DEFINITION_TYPE: Final = "capability-definition/v1"
CAPABILITY_ACTIVATION_TYPE: Final = "capability-activation/v1"

_CAPABILITY_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*/v[1-9][0-9]*")


def _digest(value: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    capability: str
    target_kind: str
    binder_id: str
    handler_id: str
    effect_class: str
    verification_class: str
    supported_environments: tuple[str, ...]
    required_permissions: tuple[str, ...]
    production_eligible: bool
    definition_identity: str

    def __post_init__(self) -> None:
        if _CAPABILITY_PATTERN.fullmatch(self.capability) is None:
            raise ValueError("capability is invalid")
        for field in (
            "target_kind",
            "binder_id",
            "handler_id",
            "effect_class",
            "verification_class",
        ):
            _require_text(getattr(self, field), field=field)
        if (
            not self.supported_environments
            or self.supported_environments != tuple(sorted(set(self.supported_environments)))
            or any(item not in VALID_ENVIRONMENTS for item in self.supported_environments)
        ):
            raise ValueError("supported_environments are invalid")
        if (
            not self.required_permissions
            or self.required_permissions != tuple(sorted(set(self.required_permissions)))
        ):
            raise ValueError("required_permissions are invalid")
        for permission in self.required_permissions:
            _require_text(permission, field="required_permission")
        if REQUIRED_EXECUTION_PERMISSION not in self.required_permissions:
            raise ValueError("required_permissions must include execution.run")
        if type(self.production_eligible) is not bool:
            raise ValueError("production_eligible must be boolean")
        if self.production_eligible and "production" not in self.supported_environments:
            raise ValueError("production-eligible capability must support production")
        _require_digest(self.definition_identity, field="definition_identity")
        if self.definition_identity != _digest(self._claims_without_identity()):
            raise ValueError("definition_identity does not match capability definition")

    @classmethod
    def create(
        cls,
        *,
        capability: str,
        target_kind: str,
        binder_id: str,
        handler_id: str,
        effect_class: str,
        verification_class: str,
        supported_environments: Iterable[str],
        required_permissions: Iterable[str],
        production_eligible: bool,
    ) -> Self:
        environments = tuple(sorted(set(supported_environments)))
        permissions = tuple(sorted(set(required_permissions)))
        claims = {
            "definition_type": CAPABILITY_DEFINITION_TYPE,
            "capability": capability,
            "target_kind": target_kind,
            "binder_id": binder_id,
            "handler_id": handler_id,
            "effect_class": effect_class,
            "verification_class": verification_class,
            "supported_environments": list(environments),
            "required_permissions": list(permissions),
            "production_eligible": production_eligible,
        }
        return cls(
            capability=capability,
            target_kind=target_kind,
            binder_id=binder_id,
            handler_id=handler_id,
            effect_class=effect_class,
            verification_class=verification_class,
            supported_environments=environments,
            required_permissions=permissions,
            production_eligible=production_eligible,
            definition_identity=_digest(claims),
        )

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "definition_type": CAPABILITY_DEFINITION_TYPE,
            "capability": self.capability,
            "target_kind": self.target_kind,
            "binder_id": self.binder_id,
            "handler_id": self.handler_id,
            "effect_class": self.effect_class,
            "verification_class": self.verification_class,
            "supported_environments": list(self.supported_environments),
            "required_permissions": list(self.required_permissions),
            "production_eligible": self.production_eligible,
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_identity()
        value["definition_identity"] = self.definition_identity
        return value


@dataclass(frozen=True, slots=True)
class CapabilityActivation:
    capability_definition_identity: str
    activation_generation: int
    enabled_environments: tuple[str, ...]
    revoked: bool
    activation_digest: str

    def __post_init__(self) -> None:
        _require_digest(
            self.capability_definition_identity,
            field="capability_definition_identity",
        )
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
        _require_digest(self.activation_digest, field="activation_digest")
        if self.activation_digest != _digest(self._claims_without_digest()):
            raise ValueError("activation_digest does not match capability activation")

    @classmethod
    def create(
        cls,
        *,
        capability_definition_identity: str,
        activation_generation: int,
        enabled_environments: Iterable[str],
        revoked: bool = False,
    ) -> Self:
        environments = tuple(sorted(set(enabled_environments)))
        claims = {
            "activation_type": CAPABILITY_ACTIVATION_TYPE,
            "capability_definition_identity": capability_definition_identity,
            "activation_generation": activation_generation,
            "enabled_environments": list(environments),
            "revoked": revoked,
        }
        return cls(
            capability_definition_identity=capability_definition_identity,
            activation_generation=activation_generation,
            enabled_environments=environments,
            revoked=revoked,
            activation_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "activation_type": CAPABILITY_ACTIVATION_TYPE,
            "capability_definition_identity": self.capability_definition_identity,
            "activation_generation": self.activation_generation,
            "enabled_environments": list(self.enabled_environments),
            "revoked": self.revoked,
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["activation_digest"] = self.activation_digest
        return value


class ImmutableCapabilityRegistry:
    """Read-only capability definitions plus exact activation generations."""

    def __init__(
        self,
        *,
        definitions: Iterable[CapabilityDefinition],
        activations: Iterable[CapabilityActivation],
    ) -> None:
        by_capability: dict[str, CapabilityDefinition] = {}
        by_identity: dict[str, CapabilityDefinition] = {}
        for definition in definitions:
            if not isinstance(definition, CapabilityDefinition):
                raise ValueError("definition is invalid")
            if definition.capability in by_capability:
                raise ValueError("duplicate capability")
            if definition.definition_identity in by_identity:
                raise ValueError("duplicate capability definition identity")
            by_capability[definition.capability] = definition
            by_identity[definition.definition_identity] = definition

        activation_by_identity: dict[str, CapabilityActivation] = {}
        for activation in activations:
            if not isinstance(activation, CapabilityActivation):
                raise ValueError("activation is invalid")
            if activation.capability_definition_identity not in by_identity:
                raise ValueError("activation references unknown capability definition")
            if activation.capability_definition_identity in activation_by_identity:
                raise ValueError("duplicate activation for capability definition")
            definition = by_identity[activation.capability_definition_identity]
            if not set(activation.enabled_environments).issubset(
                set(definition.supported_environments)
            ):
                raise ValueError("activation enables unsupported environment")
            activation_by_identity[activation.capability_definition_identity] = activation

        if not by_capability:
            raise ValueError("capability registry requires at least one definition")
        self._by_capability = MappingProxyType(by_capability)
        self._by_identity = MappingProxyType(by_identity)
        self._activations = MappingProxyType(activation_by_identity)

    def definition(self, capability: str) -> CapabilityDefinition:
        _require_text(capability, field="capability")
        try:
            return self._by_capability[capability]
        except KeyError as exc:
            raise LookupError("capability definition not found") from exc

    def definition_by_identity(self, definition_identity: str) -> CapabilityDefinition:
        _require_text(definition_identity, field="definition_identity")
        try:
            return self._by_identity[definition_identity]
        except KeyError as exc:
            raise LookupError("capability definition identity not found") from exc

    def activation(self, definition_identity: str) -> CapabilityActivation:
        _require_text(definition_identity, field="definition_identity")
        try:
            return self._activations[definition_identity]
        except KeyError as exc:
            raise PermissionError("capability is not activated") from exc

    def resolve_for_execution(
        self,
        *,
        capability: str,
        environment: str,
    ) -> tuple[CapabilityDefinition, CapabilityActivation]:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        definition = self.definition(capability)
        activation = self.activation(definition.definition_identity)
        if activation.revoked:
            raise PermissionError("capability activation is revoked")
        if environment not in activation.enabled_environments:
            raise PermissionError("capability is not active in environment")
        if environment not in definition.supported_environments:
            raise PermissionError("capability does not support environment")
        if environment == "production" and not definition.production_eligible:
            raise PermissionError("capability is not production eligible")
        return definition, activation
