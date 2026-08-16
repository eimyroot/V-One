from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Protocol, Self, runtime_checkable

from .capability_registry import CapabilityDefinition
from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget

TARGET_BINDING_TYPE: Final = "target-binding/v1"


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


@runtime_checkable
class TargetBinder(Protocol):
    binder_id: str
    target_kind: str

    def bind(self, *, approved_payload: Mapping[str, Any]) -> ExecutionTarget: ...


@dataclass(frozen=True, slots=True)
class TargetBinding:
    binder_id: str
    capability_definition_identity: str
    target: ExecutionTarget
    binding_digest: str

    def __post_init__(self) -> None:
        _require_text(self.binder_id, field="binder_id")
        _require_digest(
            self.capability_definition_identity,
            field="capability_definition_identity",
        )
        if not isinstance(self.target, ExecutionTarget):
            raise ValueError("target is invalid")
        _require_digest(self.binding_digest, field="binding_digest")
        if self.binding_digest != _digest(self._claims_without_digest()):
            raise ValueError("binding_digest does not match target binding")

    @classmethod
    def create(
        cls,
        *,
        binder_id: str,
        capability_definition_identity: str,
        target: ExecutionTarget,
    ) -> Self:
        if not isinstance(target, ExecutionTarget):
            raise ValueError("target is invalid")
        claims = {
            "binding_type": TARGET_BINDING_TYPE,
            "binder_id": binder_id,
            "capability_definition_identity": capability_definition_identity,
            "target": target.to_dict(),
        }
        return cls(
            binder_id=binder_id,
            capability_definition_identity=capability_definition_identity,
            target=target,
            binding_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "binding_type": TARGET_BINDING_TYPE,
            "binder_id": self.binder_id,
            "capability_definition_identity": self.capability_definition_identity,
            "target": self.target.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["binding_digest"] = self.binding_digest
        return value


class TargetBinderRegistry:
    """Read-only mapping from reviewed capability definitions to deterministic binders."""

    def __init__(self, binders: Mapping[str, TargetBinder]) -> None:
        normalized: dict[str, TargetBinder] = {}
        for binder_id, binder in binders.items():
            _require_text(binder_id, field="binder_id")
            if not isinstance(binder, TargetBinder):
                raise ValueError("binder does not satisfy TargetBinder")
            if binder.binder_id != binder_id:
                raise ValueError("binder registry key does not match binder_id")
            if binder_id in normalized:
                raise ValueError("duplicate binder_id")
            normalized[binder_id] = binder
        if not normalized:
            raise ValueError("target binder registry requires at least one binder")
        self._binders = MappingProxyType(normalized)

    def resolve(self, binder_id: str) -> TargetBinder:
        _require_text(binder_id, field="binder_id")
        try:
            return self._binders[binder_id]
        except KeyError as exc:
            raise LookupError("target binder not found") from exc

    def bind(
        self,
        *,
        definition: CapabilityDefinition,
        approved_payload: Mapping[str, Any],
    ) -> TargetBinding:
        if not isinstance(definition, CapabilityDefinition):
            raise ValueError("definition is invalid")
        if not isinstance(approved_payload, Mapping):
            raise ValueError("approved_payload must be a mapping")
        binder = self.resolve(definition.binder_id)
        if binder.target_kind != definition.target_kind:
            raise ValueError("target binder kind does not match capability definition")
        target = binder.bind(approved_payload=approved_payload)
        if not isinstance(target, ExecutionTarget):
            raise ValueError("target binder returned invalid target")
        if target.target_kind != definition.target_kind:
            raise ValueError("target binder returned unexpected target kind")
        return TargetBinding.create(
            binder_id=binder.binder_id,
            capability_definition_identity=definition.definition_identity,
            target=target,
        )
