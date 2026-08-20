from __future__ import annotations

import pytest

from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.controlled_write import MUTATION_REVERSIBLE_EFFECT_CLASS
from voodoo_product.runner_identity import READ_ONLY_EFFECT_CLASS
from voodoo_product.terminal_profile import (
    BOUNDED_MUTATION_TERMINAL_PROFILE,
    READ_ONLY_TERMINAL_PROFILE,
    CapabilityTerminalProfileBinding,
    ImmutableCapabilityTerminalProfileRegistry,
)


def definition(*, capability: str, effect_class: str) -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability=capability,
        target_kind="git_ref",
        binder_id=f"{capability.removesuffix('/v1')}-binder/v1",
        handler_id=f"{capability.removesuffix('/v1')}-handler/v1",
        effect_class=effect_class,
        verification_class="provider-read/v1",
        supported_environments=("staging",),
        required_permissions=("execution.run",),
        production_eligible=False,
    )


def test_read_and_mutation_profiles_are_bound_to_exact_capability_identity() -> None:
    read_definition = definition(
        capability="github.read-ref/v1",
        effect_class=READ_ONLY_EFFECT_CLASS,
    )
    write_definition = definition(
        capability="github.create-ref/v1",
        effect_class=MUTATION_REVERSIBLE_EFFECT_CLASS,
    )
    read_binding = CapabilityTerminalProfileBinding.create(
        definition=read_definition,
        terminal_profile=READ_ONLY_TERMINAL_PROFILE,
        binding_revision="terminal-profile/test-r1",
    )
    write_binding = CapabilityTerminalProfileBinding.create(
        definition=write_definition,
        terminal_profile=BOUNDED_MUTATION_TERMINAL_PROFILE,
        binding_revision="terminal-profile/test-r1",
    )
    registry = ImmutableCapabilityTerminalProfileRegistry((read_binding, write_binding))

    assert registry.resolve(
        capability_definition_identity=read_definition.definition_identity,
        capability=read_definition.capability,
    ) == read_binding
    assert registry.resolve(
        capability_definition_identity=write_definition.definition_identity,
        capability=write_definition.capability,
    ) == write_binding
    assert read_binding.binding_digest != write_binding.binding_digest


def test_read_capability_cannot_be_strengthened_to_mutation_profile() -> None:
    read_definition = definition(
        capability="github.read-ref/v1",
        effect_class=READ_ONLY_EFFECT_CLASS,
    )

    with pytest.raises(PermissionError, match="TERMINAL_PROFILE_EFFECT_CLASS_MISMATCH"):
        CapabilityTerminalProfileBinding.create(
            definition=read_definition,
            terminal_profile=BOUNDED_MUTATION_TERMINAL_PROFILE,
            binding_revision="terminal-profile/test-r1",
        )


def test_mutation_capability_cannot_be_downgraded_into_wrong_terminal_semantics() -> None:
    write_definition = definition(
        capability="github.create-ref/v1",
        effect_class=MUTATION_REVERSIBLE_EFFECT_CLASS,
    )

    with pytest.raises(PermissionError, match="TERMINAL_PROFILE_EFFECT_CLASS_MISMATCH"):
        CapabilityTerminalProfileBinding.create(
            definition=write_definition,
            terminal_profile=READ_ONLY_TERMINAL_PROFILE,
            binding_revision="terminal-profile/test-r1",
        )


def test_registry_fails_closed_for_unknown_identity_or_capability_substitution() -> None:
    read_definition = definition(
        capability="github.read-ref/v1",
        effect_class=READ_ONLY_EFFECT_CLASS,
    )
    binding = CapabilityTerminalProfileBinding.create(
        definition=read_definition,
        terminal_profile=READ_ONLY_TERMINAL_PROFILE,
        binding_revision="terminal-profile/test-r1",
    )
    registry = ImmutableCapabilityTerminalProfileRegistry((binding,))

    with pytest.raises(PermissionError, match="TERMINAL_PROFILE_NOT_ALLOWLISTED"):
        registry.resolve(
            capability_definition_identity="f" * 64,
            capability=read_definition.capability,
        )
    with pytest.raises(PermissionError, match="TERMINAL_PROFILE_CAPABILITY_MISMATCH"):
        registry.resolve(
            capability_definition_identity=read_definition.definition_identity,
            capability="github.other/v1",
        )


def test_registry_rejects_duplicate_identity() -> None:
    read_definition = definition(
        capability="github.read-ref/v1",
        effect_class=READ_ONLY_EFFECT_CLASS,
    )
    binding = CapabilityTerminalProfileBinding.create(
        definition=read_definition,
        terminal_profile=READ_ONLY_TERMINAL_PROFILE,
        binding_revision="terminal-profile/test-r1",
    )

    with pytest.raises(ValueError, match="duplicate terminal-profile"):
        ImmutableCapabilityTerminalProfileRegistry((binding, binding))
