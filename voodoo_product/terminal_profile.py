from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Self

from .capability_registry import CapabilityDefinition
from .controlled_write import MUTATION_REVERSIBLE_EFFECT_CLASS
from .evidence_primitives import canonical_json
from .runner_identity import READ_ONLY_EFFECT_CLASS
from .vop_vocabulary import OPERATION_TERMINAL_PROFILES

CAPABILITY_TERMINAL_PROFILE_BINDING_TYPE: Final = "capability-terminal-profile-binding/v1"
READ_ONLY_TERMINAL_PROFILE: Final = "READ_ONLY_VERIFIED"
BOUNDED_MUTATION_TERMINAL_PROFILE: Final = "BOUNDED_MUTATION_VERIFIED"

_PROFILE_BY_EFFECT_CLASS: Final = MappingProxyType(
    {
        READ_ONLY_EFFECT_CLASS: READ_ONLY_TERMINAL_PROFILE,
        MUTATION_REVERSIBLE_EFFECT_CLASS: BOUNDED_MUTATION_TERMINAL_PROFILE,
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


@dataclass(frozen=True, slots=True)
class CapabilityTerminalProfileBinding:
    """Immutable allowlist binding from exact capability definition to one terminal profile.

    The binding is intentionally separate from CapabilityDefinition so adding terminal semantics
    cannot rewrite an already content-addressed capability identity. A profile is accepted only when
    the capability effect class has an explicit current mapping.
    """

    capability: str
    capability_definition_identity: str
    effect_class: str
    terminal_profile: str
    binding_revision: str
    binding_digest: str

    def __post_init__(self) -> None:
        for field in ("capability", "effect_class", "terminal_profile", "binding_revision"):
            _require_text(getattr(self, field), field=field)
        _require_digest(
            self.capability_definition_identity,
            field="capability_definition_identity",
        )
        _require_digest(self.binding_digest, field="binding_digest")
        if self.terminal_profile not in OPERATION_TERMINAL_PROFILES:
            raise ValueError("terminal_profile is unsupported")
        expected = _PROFILE_BY_EFFECT_CLASS.get(self.effect_class)
        if expected is None:
            raise PermissionError("TERMINAL_PROFILE_EFFECT_CLASS_UNSUPPORTED")
        if self.terminal_profile != expected:
            raise PermissionError("TERMINAL_PROFILE_EFFECT_CLASS_MISMATCH")
        if self.binding_digest != _digest(self._claims_without_digest()):
            raise ValueError("binding_digest does not match terminal-profile binding")

    @classmethod
    def create(
        cls,
        *,
        definition: CapabilityDefinition,
        terminal_profile: str,
        binding_revision: str,
    ) -> Self:
        if not isinstance(definition, CapabilityDefinition):
            raise ValueError("definition must be CapabilityDefinition")
        claims = {
            "schema_version": 1,
            "binding_type": CAPABILITY_TERMINAL_PROFILE_BINDING_TYPE,
            "capability": definition.capability,
            "capability_definition_identity": definition.definition_identity,
            "effect_class": definition.effect_class,
            "terminal_profile": terminal_profile,
            "binding_revision": _require_text(binding_revision, field="binding_revision"),
        }
        values = {
            key: value
            for key, value in claims.items()
            if key not in {"schema_version", "binding_type"}
        }
        return cls(**values, binding_digest=_digest(claims))

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "binding_type": CAPABILITY_TERMINAL_PROFILE_BINDING_TYPE,
            "capability": self.capability,
            "capability_definition_identity": self.capability_definition_identity,
            "effect_class": self.effect_class,
            "terminal_profile": self.terminal_profile,
            "binding_revision": self.binding_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "binding_digest": self.binding_digest}


class ImmutableCapabilityTerminalProfileRegistry:
    """Fail-closed terminal-profile allowlist keyed by content-addressed capability identity."""

    def __init__(self, bindings: Iterable[CapabilityTerminalProfileBinding]) -> None:
        by_identity: dict[str, CapabilityTerminalProfileBinding] = {}
        for binding in bindings:
            if not isinstance(binding, CapabilityTerminalProfileBinding):
                raise ValueError("terminal-profile binding is invalid")
            if binding.capability_definition_identity in by_identity:
                raise ValueError("duplicate terminal-profile capability definition identity")
            by_identity[binding.capability_definition_identity] = binding
        if not by_identity:
            raise ValueError("terminal-profile registry requires at least one binding")
        self._by_identity = MappingProxyType(by_identity)

    def resolve(
        self,
        *,
        capability_definition_identity: str,
        capability: str,
    ) -> CapabilityTerminalProfileBinding:
        definition_identity = _require_digest(
            capability_definition_identity,
            field="capability_definition_identity",
        )
        capability = _require_text(capability, field="capability")
        try:
            binding = self._by_identity[definition_identity]
        except KeyError as exc:
            raise PermissionError("TERMINAL_PROFILE_NOT_ALLOWLISTED") from exc
        if binding.capability != capability:
            raise PermissionError("TERMINAL_PROFILE_CAPABILITY_MISMATCH")
        return binding
