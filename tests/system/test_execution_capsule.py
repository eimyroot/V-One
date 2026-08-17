from __future__ import annotations

from pathlib import Path

import pytest

from voodoo_product.authoritative_grant import ExecutionBindingAuthority
from voodoo_product.capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from voodoo_product.execution_capsule import (
    AuthoritativeExecutionBindingAuthority,
    CapsuleActivation,
    ExecutionCapsule,
    ImmutableExecutionCapsuleRegistry,
)
from voodoo_product.precondition_witness import (
    ATOMIC_PROVIDER_CONDITION,
    READ_THEN_COMPARE,
)

DIGESTS = {
    "handler": "1" * 64,
    "module": "2" * 64,
    "artifact": "3" * 64,
    "rootfs": "4" * 64,
    "lock": "5" * 64,
    "sbom": "6" * 64,
    "network": "7" * 64,
    "resources": "8" * 64,
    "verification": "9" * 64,
}


def _definition(
    *,
    handler_id: str = "github.merge.handler/v1",
    target_kind: str = "github.pull_request",
    verification_class: str = "provider-read/v1",
    production_eligible: bool = True,
) -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability="github.pr.merge/v1",
        target_kind=target_kind,
        binder_id="github.pr.target/v1",
        handler_id=handler_id,
        effect_class="mutation.reversible",
        verification_class=verification_class,
        supported_environments=("production", "staging"),
        required_permissions=("execution.run",),
        production_eligible=production_eligible,
    )


def _capability_registry(
    definition: CapabilityDefinition,
    *,
    revoked: bool = False,
    enabled_environments: tuple[str, ...] = ("production", "staging"),
) -> ImmutableCapabilityRegistry:
    activation = CapabilityActivation.create(
        capability_definition_identity=definition.definition_identity,
        activation_generation=1,
        enabled_environments=enabled_environments,
        revoked=revoked,
    )
    return ImmutableCapabilityRegistry(
        definitions=(definition,),
        activations=(activation,),
    )


def _capsule(
    definition: CapabilityDefinition,
    *,
    handler_id: str | None = None,
    target_kind: str | None = None,
    verification_class: str | None = None,
    runner_class: str = "sandcloud.isolated-linux/v1",
    enforcement: str = READ_THEN_COMPARE,
) -> ExecutionCapsule:
    return ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=target_kind or definition.target_kind,
        handler_id=handler_id or definition.handler_id,
        handler_digest=DIGESTS["handler"],
        module_manifest_digest=DIGESTS["module"],
        artifact_kind="oci-image",
        artifact_digest=DIGESTS["artifact"],
        rootfs_digest=DIGESTS["rootfs"],
        dependency_lock_digest=DIGESTS["lock"],
        sbom_digest=DIGESTS["sbom"],
        network_policy_digest=DIGESTS["network"],
        resource_limit_profile_digest=DIGESTS["resources"],
        credential_class="github.pr.merge/scoped-v1",
        runner_class=runner_class,
        precondition_enforcement_class=enforcement,
        verification_class=verification_class or definition.verification_class,
        verification_contract_identity=DIGESTS["verification"],
        capsule_revision="capsule-r1",
    )


def _registry(
    *,
    definition: CapabilityDefinition | None = None,
    capsule: ExecutionCapsule | None = None,
    capability_revoked: bool = False,
    capsule_revoked: bool = False,
    capsule_environments: tuple[str, ...] = ("production", "staging"),
    capsule_production_eligible: bool = True,
) -> tuple[
    CapabilityDefinition,
    ExecutionCapsule,
    ImmutableExecutionCapsuleRegistry,
]:
    definition = definition or _definition()
    capability_registry = _capability_registry(
        definition,
        revoked=capability_revoked,
    )
    capsule = capsule or _capsule(definition)
    capsule_activation = CapsuleActivation.create(
        execution_capsule_digest=capsule.capsule_digest,
        activation_generation=1,
        enabled_environments=capsule_environments,
        revoked=capsule_revoked,
        production_eligible=capsule_production_eligible,
    )
    registry = ImmutableExecutionCapsuleRegistry(
        capability_registry=capability_registry,
        capsules=(capsule,),
        activations=(capsule_activation,),
    )
    return definition, capsule, registry


def test_execution_capsule_round_trip_is_exact_and_content_addressed() -> None:
    definition = _definition()
    capsule = _capsule(definition, enforcement=ATOMIC_PROVIDER_CONDITION)

    assert ExecutionCapsule.from_dict(capsule.to_dict()) == capsule
    assert capsule.capability_definition_identity == definition.definition_identity
    assert capsule.precondition_enforcement_class == ATOMIC_PROVIDER_CONDITION
    assert len(capsule.capsule_digest) == 64


def test_execution_capsule_rejects_tamper_and_unknown_fields() -> None:
    definition = _definition()
    capsule = _capsule(definition)

    tampered = capsule.to_dict()
    tampered["runner_class"] = "other.runner/v1"
    with pytest.raises(ValueError, match="capsule_digest"):
        ExecutionCapsule.from_dict(tampered)

    unknown = capsule.to_dict()
    unknown["unexpected"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        ExecutionCapsule.from_dict(unknown)


def test_registry_rejects_handler_target_and_verification_drift() -> None:
    definition = _definition()
    capability_registry = _capability_registry(definition)

    cases = (
        _capsule(definition, handler_id="other.handler/v1"),
        _capsule(definition, target_kind="github.repository"),
        _capsule(definition, verification_class="executor-assertion/v1"),
    )
    messages = ("handler", "target kind", "verification class")

    for capsule, message in zip(cases, messages, strict=True):
        activation = CapsuleActivation.create(
            execution_capsule_digest=capsule.capsule_digest,
            activation_generation=1,
            enabled_environments=("staging",),
        )
        with pytest.raises(ValueError, match=message):
            ImmutableExecutionCapsuleRegistry(
                capability_registry=capability_registry,
                capsules=(capsule,),
                activations=(activation,),
            )


def test_registry_rejects_capsule_production_scope_broader_than_capability() -> None:
    definition = _definition(production_eligible=False)
    capability_registry = _capability_registry(
        definition,
        enabled_environments=("staging",),
    )
    capsule = _capsule(definition)
    activation = CapsuleActivation.create(
        execution_capsule_digest=capsule.capsule_digest,
        activation_generation=1,
        enabled_environments=("production",),
        production_eligible=True,
    )

    with pytest.raises(ValueError, match="unsupported environment|production eligibility"):
        ImmutableExecutionCapsuleRegistry(
            capability_registry=capability_registry,
            capsules=(capsule,),
            activations=(activation,),
        )


def test_authoritative_binding_resolves_exact_capsule_and_runner_class() -> None:
    definition, capsule, registry = _registry()
    authority = AuthoritativeExecutionBindingAuthority(
        registry=registry,
        authority_revision="binding-authority-r1",
    )

    assert isinstance(authority, ExecutionBindingAuthority)

    binding = authority.resolve(
        capability_definition_identity=definition.definition_identity,
        environment="staging",
        target_kind=definition.target_kind,
    )

    assert binding.capability_definition_identity == definition.definition_identity
    assert binding.execution_capsule_digest == capsule.capsule_digest
    assert binding.runner_class == capsule.runner_class
    assert binding.authority_revision == "binding-authority-r1"


def test_authoritative_binding_denies_revoked_capsule() -> None:
    definition, _, registry = _registry(capsule_revoked=True)
    authority = AuthoritativeExecutionBindingAuthority(
        registry=registry,
        authority_revision="binding-authority-r1",
    )

    with pytest.raises(PermissionError, match="capsule activation is revoked"):
        authority.resolve(
            capability_definition_identity=definition.definition_identity,
            environment="staging",
            target_kind=definition.target_kind,
        )


def test_authoritative_binding_denies_revoked_capability() -> None:
    definition, _, registry = _registry(capability_revoked=True)
    authority = AuthoritativeExecutionBindingAuthority(
        registry=registry,
        authority_revision="binding-authority-r1",
    )

    with pytest.raises(PermissionError, match="capability activation is revoked"):
        authority.resolve(
            capability_definition_identity=definition.definition_identity,
            environment="staging",
            target_kind=definition.target_kind,
        )


def test_authoritative_binding_denies_environment_and_target_mismatch() -> None:
    definition, _, registry = _registry(
        capsule_environments=("staging",),
        capsule_production_eligible=False,
    )
    authority = AuthoritativeExecutionBindingAuthority(
        registry=registry,
        authority_revision="binding-authority-r1",
    )

    with pytest.raises(PermissionError, match="not active in environment"):
        authority.resolve(
            capability_definition_identity=definition.definition_identity,
            environment="production",
            target_kind=definition.target_kind,
        )

    with pytest.raises(PermissionError, match="target kind mismatch"):
        authority.resolve(
            capability_definition_identity=definition.definition_identity,
            environment="staging",
            target_kind="github.repository",
        )


def test_capsule_activation_rejects_invalid_production_claim() -> None:
    definition = _definition()
    capsule = _capsule(definition)

    with pytest.raises(ValueError, match="must enable production"):
        CapsuleActivation.create(
            execution_capsule_digest=capsule.capsule_digest,
            activation_generation=1,
            enabled_environments=("staging",),
            production_eligible=True,
        )


def test_any_execution_change_changes_capsule_digest() -> None:
    definition = _definition()
    capsule = _capsule(definition)

    changed = ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest="a" * 64,
        module_manifest_digest=capsule.module_manifest_digest,
        artifact_kind=capsule.artifact_kind,
        artifact_digest=capsule.artifact_digest,
        rootfs_digest=capsule.rootfs_digest,
        dependency_lock_digest=capsule.dependency_lock_digest,
        sbom_digest=capsule.sbom_digest,
        network_policy_digest=capsule.network_policy_digest,
        resource_limit_profile_digest=capsule.resource_limit_profile_digest,
        credential_class=capsule.credential_class,
        runner_class=capsule.runner_class,
        precondition_enforcement_class=capsule.precondition_enforcement_class,
        verification_class=capsule.verification_class,
        verification_contract_identity=capsule.verification_contract_identity,
        capsule_revision=capsule.capsule_revision,
    )

    assert changed.capsule_digest != capsule.capsule_digest


def test_capsule_is_not_wired_into_current_product_runtime() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    service_source = (repository_root / "voodoo_product" / "service.py").read_text()
    execution_source = (repository_root / "voodoo_product" / "execution.py").read_text()

    for symbol in (
        "ExecutionCapsule",
        "ImmutableExecutionCapsuleRegistry",
        "AuthoritativeExecutionBindingAuthority",
    ):
        assert symbol not in service_source
        assert symbol not in execution_source
