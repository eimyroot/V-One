from __future__ import annotations

import ast
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from voodoo_product.authoritative_grant import ExecutionGrantV2
from voodoo_product.capability_registry import CapabilityDefinition
from voodoo_product.controlled_write import (
    GITHUB_CREATE_REF_CAPABILITY,
    GITHUB_CREATE_REF_HANDLER,
    MUTATION_REVERSIBLE_EFFECT_CLASS,
    ControlledWriteRequirement,
    GitHubCreateRefConditionContract,
)
from voodoo_product.dispatch_envelope import DispatchEnvelope
from voodoo_product.dispatch_inbox import DispatchInboxAdmission
from voodoo_product.dispatch_outbox import DispatchOutboxEntry
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_capsule import ExecutionCapsule
from voodoo_product.execution_conformance import HandlerConformanceEvidence
from voodoo_product.execution_lease import ExecutionLease
from voodoo_product.github_create_ref_provider import (
    GITHUB_CREATE_REF_BINDER_ID,
    GitHubCreateRefHandlerContract,
    GitHubCreateRefRequest,
    GitHubCreateRefTargetBinder,
)
from voodoo_product.grant_consumption import GrantConsumptionWitness
from voodoo_product.isolated_runner import IsolatedRuntimeBootstrap, READ_ONLY_MOUNT_MODE
from voodoo_product.precondition_witness import ATOMIC_PROVIDER_CONDITION
from voodoo_product.runner_identity import DENY_ALL_NETWORK_DEFAULT, RunnerIdentity
from voodoo_product.target_binding import TargetBinding
from voodoo_product.trusted_clock import ClockWitness, TrustedClockAuthority
from voodoo_product.write_boundary import (
    GITHUB_CREATE_REF_CREDENTIAL_CLASS,
    WRITE_BOUNDED_ACCESS_MODE,
    WRITE_RUNNER_CLASS,
    CredentialAccessDecisionV2,
    CredentialBrokerPolicyV2,
    RunnerBoundaryV2,
)
from voodoo_product.write_runtime import (
    EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE,
    WRITE_EFFECT_PREFLIGHT_TYPE,
    WRITE_RUNTIME_ACTIVATION_TYPE,
    EphemeralWriteCredentialDelivery,
    WriteEffectPreflight,
    WriteEffectPreflightDenied,
    WriteRuntimeActivation,
    WriteRuntimeDenied,
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


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _clock(at: str) -> ClockWitness:
    return ClockWitness.create(
        source_identity="clock/test-f4a",
        authority_revision="clock/f4a-r1",
        environment="staging",
        observed_at=datetime.fromisoformat(at).astimezone(UTC),
    )


class _FixedClock:
    def __init__(self, at: str) -> None:
        self.at = datetime.fromisoformat(at).astimezone(UTC)

    def read(self) -> datetime:
        return self.at


class _Fence:
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.calls = 0

    def assert_current(self, *, lease: ExecutionLease) -> None:
        self.calls += 1
        if self.reject:
            raise PermissionError("STALE_EFFECT_FENCE")


def _trusted_clock(at: str) -> TrustedClockAuthority:
    return TrustedClockAuthority(
        source_identity="clock/test-f4a",
        authority_revision="clock/f4a-r1",
        source=_FixedClock(at),
        allowed_environments=frozenset({"staging"}),
    )


def _definition() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability=GITHUB_CREATE_REF_CAPABILITY,
        target_kind="git_ref",
        binder_id=GITHUB_CREATE_REF_BINDER_ID,
        handler_id=GITHUB_CREATE_REF_HANDLER,
        effect_class=MUTATION_REVERSIBLE_EFFECT_CLASS,
        verification_class="provider-read/v1",
        supported_environments=("staging",),
        required_permissions=("execution.run",),
        production_eligible=False,
    )


def _capsule(definition: CapabilityDefinition) -> ExecutionCapsule:
    return ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest=DIGESTS["handler"],
        module_manifest_digest=DIGESTS["module"],
        artifact_kind="oci-image",
        artifact_digest=DIGESTS["artifact"],
        rootfs_digest=DIGESTS["rootfs"],
        dependency_lock_digest=DIGESTS["lock"],
        sbom_digest=DIGESTS["sbom"],
        network_policy_digest=DIGESTS["network"],
        resource_limit_profile_digest=DIGESTS["resources"],
        credential_class=GITHUB_CREATE_REF_CREDENTIAL_CLASS,
        runner_class=WRITE_RUNNER_CLASS,
        precondition_enforcement_class=ATOMIC_PROVIDER_CONDITION,
        verification_class=definition.verification_class,
        verification_contract_identity=DIGESTS["verification"],
        capsule_revision="f4a-write-capsule-r1",
    )


def _condition() -> GitHubCreateRefConditionContract:
    return GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f4a-r1"
    )


def _handler_evidence(
    capsule: ExecutionCapsule,
    condition: GitHubCreateRefConditionContract,
) -> HandlerConformanceEvidence:
    return HandlerConformanceEvidence.create(
        capability_definition_identity=capsule.capability_definition_identity,
        execution_capsule_digest=capsule.capsule_digest,
        handler_id=capsule.handler_id,
        handler_digest=capsule.handler_digest,
        runner_class=capsule.runner_class,
        credential_class=capsule.credential_class,
        precondition_enforcement_class=capsule.precondition_enforcement_class,
        verification_contract_identity=capsule.verification_contract_identity,
        atomic_provider_condition_contract_identity=condition.contract_digest,
        evidence_revision="f4a-handler-conformance-r1",
    )


def _requirement(
    definition: CapabilityDefinition,
    capsule: ExecutionCapsule,
    evidence: HandlerConformanceEvidence,
    condition: GitHubCreateRefConditionContract,
) -> ControlledWriteRequirement:
    return ControlledWriteRequirement.create(
        definition=definition,
        capsule=capsule,
        handler_evidence=evidence,
        provider_condition=condition,
        requirement_revision="controlled-write-requirement/f4a-r1",
    )


def _grant(
    *,
    definition: CapabilityDefinition,
    capsule: ExecutionCapsule,
    target_digest: str,
) -> ExecutionGrantV2:
    return ExecutionGrantV2._issue(
        grant_id="grt_f4a",
        jti="jti_f4a",
        execution_id="exec_f4a",
        request_id="cr_f4a",
        authorization_snapshot_digest="a" * 64,
        snapshot_authority_witness_set_digest="b" * 64,
        snapshot_authority_event_hash="c" * 64,
        parent_scope_digest="d" * 64,
        authority_constraint_digest="e" * 64,
        monotonic_authority_decision_digest="f" * 64,
        actor_id="usr_f4a",
        workspace_id="wrk_f4a",
        environment="staging",
        capability=definition.capability,
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        target_digest=target_digest,
        payload_digest="0" * 64,
        policy_version="approval-policy/f4a-r1",
        policy_identity="1" * 64,
        approval_set_digest="2" * 64,
        required_permission="execution.run",
        precondition_requirement_digest="3" * 64,
        precondition_expectation_digest="4" * 64,
        precondition_observation_digest="5" * 64,
        precondition_witness_digest="6" * 64,
        precondition_enforcement_class=ATOMIC_PROVIDER_CONDITION,
        precondition_checked_at="2026-08-18T17:00:00.000+00:00",
        execution_binding_digest="7" * 64,
        execution_capsule_digest=capsule.capsule_digest,
        runner_class=WRITE_RUNNER_CLASS,
        execution_binding_authority_revision="execution-binding/f4a-r1",
        issued_at="2026-08-18T17:00:01.000+00:00",
        expires_at="2026-08-18T17:04:00.000+00:00",
        revocation_epoch=7,
        use_semantics="ONE_TIME",
        issuer_identity="grant-issuer/f4a",
        issuer_revision="grant-issuer/f4a-r1",
    )


def _consumption(grant: ExecutionGrantV2) -> GrantConsumptionWitness:
    claims: dict[str, object] = {
        "schema_version": 1,
        "witness_type": "grant-consumption-witness/v1",
        "consumption_id": "gcon_f4a",
        "jti": grant.jti,
        "grant_id": grant.grant_id,
        "grant_digest": grant.grant_digest,
        "execution_id": grant.execution_id,
        "authorization_snapshot_digest": grant.authorization_snapshot_digest,
        "execution_capsule_digest": grant.execution_capsule_digest,
        "runner_class": grant.runner_class,
        "conformance_witness_digest": "8" * 64,
        "clock_witness_digest": "9" * 64,
        "live_revocation_epoch": grant.revocation_epoch,
        "consumed_at": "2026-08-18T17:00:02.000+00:00",
        "serialization_contract": "sqlite-begin-immediate/v1",
        "authority_revision": "durable-grant/f4a-r1",
    }
    values = {
        key: item
        for key, item in claims.items()
        if key not in {"schema_version", "witness_type"}
    }
    return GrantConsumptionWitness(**values, witness_digest=_digest(claims))  # type: ignore[arg-type]


def _bundle() -> dict[str, object]:
    definition = _definition()
    capsule = _capsule(definition)
    condition = _condition()
    evidence = _handler_evidence(capsule, condition)
    requirement = _requirement(definition, capsule, evidence, condition)
    target = GitHubCreateRefTargetBinder().bind(
        approved_payload={
            "repository": "nulleimy/V-One",
            "ref": "refs/heads/vone-canary/f4a-test",
            "commit_sha": "a" * 40,
        }
    )
    target_binding = TargetBinding.create(
        binder_id=GITHUB_CREATE_REF_BINDER_ID,
        capability_definition_identity=definition.definition_identity,
        target=target,
    )
    grant = _grant(
        definition=definition,
        capsule=capsule,
        target_digest=target.target_digest,
    )
    consumption = _consumption(grant)
    outbox = DispatchOutboxEntry.create(
        outbox_id="out_f4a",
        grant=grant,
        consumption_witness=consumption,
        outbox_revision="dispatch-outbox/f4a-r1",
    )
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/f4a-r1",
    )
    admission = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/f4a-r1",
    )
    lease = ExecutionLease.create_candidate(
        admission=admission,
        execution_epoch=1,
        clock_witness=_clock("2026-08-18T17:00:03.000+00:00"),
        lease_seconds=300,
        lease_revision="execution-lease/f4a-r1",
    )
    bootstrap = IsolatedRuntimeBootstrap.create(
        provider="github-actions",
        provider_instance_id="gha:f4a:1",
        runner_class=WRITE_RUNNER_CLASS,
        environment="staging",
        rootfs_digest=capsule.rootfs_digest,
        resource_limit_profile_digest=capsule.resource_limit_profile_digest,
        network_policy_digest=capsule.network_policy_digest,
        bootstrap_revision="isolated-runtime/f4a-r1",
    )
    identity = RunnerIdentity.create(
        runner_class=bootstrap.runner_class,
        provider=bootstrap.provider,
        provider_instance_id=bootstrap.provider_instance_id,
        environment=bootstrap.environment,
        rootfs_digest=bootstrap.rootfs_digest,
        resource_limit_profile_digest=bootstrap.resource_limit_profile_digest,
        network_policy_digest=bootstrap.network_policy_digest,
        identity_revision="runner-identity/f4a-r1",
    )
    boundary = RunnerBoundaryV2.create(
        identity=identity,
        lease=lease,
        capsule=capsule,
        definition=definition,
        handler_evidence=evidence,
        provider_condition=condition,
        requirement=requirement,
        boundary_revision="runner-boundary/f4a-r1",
    )
    policy = CredentialBrokerPolicyV2.create(
        boundary=boundary,
        max_ttl_seconds=120,
        policy_revision="credential-broker-policy/f4a-r1",
    )
    decision = CredentialAccessDecisionV2.create(
        boundary=boundary,
        lease=lease,
        policy=policy,
        decision_revision="credential-access-decision/f4a-r1",
    )
    delivery_clock_witness = _clock("2026-08-18T17:00:04.000+00:00")
    delivery = EphemeralWriteCredentialDelivery.create(
        bootstrap=bootstrap,
        identity=identity,
        boundary=boundary,
        decision=decision,
        lease=lease,
        clock_witness=delivery_clock_witness,
        delivery_revision="credential-delivery/f4a-r1",
    )
    activation = WriteRuntimeActivation.create(
        bootstrap=bootstrap,
        identity=identity,
        boundary=boundary,
        decision=decision,
        delivery=delivery,
        lease=lease,
        activation_revision="write-runtime-activation/f4a-r1",
    )
    request = GitHubCreateRefHandlerContract(
        request_revision="github-create-ref-request/f4a-r1"
    ).prepare_request(
        target_binding=target_binding,
        boundary=boundary,
        decision=decision,
    )
    return {
        "grant": grant,
        "consumption": consumption,
        "outbox": outbox,
        "envelope": envelope,
        "admission": admission,
        "lease": lease,
        "identity": identity,
        "boundary": boundary,
        "policy": policy,
        "decision": decision,
        "delivery": delivery,
        "delivery_clock_witness": delivery_clock_witness,
        "activation": activation,
        "request": request,
    }


def _verify(bundle: dict[str, object], *, fence: _Fence, now: str) -> WriteEffectPreflight:
    return WriteEffectPreflight.verify(
        grant=bundle["grant"],  # type: ignore[arg-type]
        consumption=bundle["consumption"],  # type: ignore[arg-type]
        outbox=bundle["outbox"],  # type: ignore[arg-type]
        envelope=bundle["envelope"],  # type: ignore[arg-type]
        admission=bundle["admission"],  # type: ignore[arg-type]
        lease=bundle["lease"],  # type: ignore[arg-type]
        identity=bundle["identity"],  # type: ignore[arg-type]
        boundary=bundle["boundary"],  # type: ignore[arg-type]
        policy=bundle["policy"],  # type: ignore[arg-type]
        decision=bundle["decision"],  # type: ignore[arg-type]
        delivery=bundle["delivery"],  # type: ignore[arg-type]
        delivery_clock_witness=bundle["delivery_clock_witness"],  # type: ignore[arg-type]
        activation=bundle["activation"],  # type: ignore[arg-type]
        request=bundle["request"],  # type: ignore[arg-type]
        current_fence=fence,
        trusted_clock=_trusted_clock(now),
        preflight_revision="write-effect-preflight/f4a-r1",
    )


def test_write_delivery_and_activation_are_exact_serializable_metadata() -> None:
    bundle = _bundle()
    delivery = bundle["delivery"]
    activation = bundle["activation"]

    assert isinstance(delivery, EphemeralWriteCredentialDelivery)
    assert isinstance(activation, WriteRuntimeActivation)
    assert delivery.to_dict()["delivery_type"] == EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE
    assert delivery.secret_material_exposed is False
    assert EphemeralWriteCredentialDelivery.from_dict(delivery.to_dict()) == delivery
    assert activation.to_dict()["activation_type"] == WRITE_RUNTIME_ACTIVATION_TYPE
    assert activation.workspace_mount_mode == READ_ONLY_MOUNT_MODE
    assert activation.network_egress_default == DENY_ALL_NETWORK_DEFAULT
    assert activation.access_mode == WRITE_BOUNDED_ACCESS_MODE
    assert activation.provider_mutation_allowed is True
    assert activation.max_provider_mutations == 1
    assert WriteRuntimeActivation.from_dict(activation.to_dict()) == activation


def test_f4a_source_contains_no_secret_or_live_provider_transport() -> None:
    source = Path("voodoo_product/write_runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert not imported_roots.intersection(
        {"httpx", "requests", "subprocess", "urllib", "socket"}
    )
    assert "GITHUB_TOKEN" not in source
    assert "github.token" not in source
    assert "def create_ref(" not in source
    assert "ExecutionReceipt" in source
    assert "VerificationResult" in source
    assert "OperationProof" in source

    forbidden_fields = {"token", "secret", "secret_handle", "credential_bytes"}
    delivery_fields = set(EphemeralWriteCredentialDelivery.__dataclass_fields__)
    activation_fields = set(WriteRuntimeActivation.__dataclass_fields__)
    assert not forbidden_fields.intersection(delivery_fields)
    assert not forbidden_fields.intersection(activation_fields)


def test_write_effect_preflight_binds_full_chain_and_checks_current_fence() -> None:
    bundle = _bundle()
    fence = _Fence()
    preflight = _verify(bundle, fence=fence, now="2026-08-18T17:00:05.000+00:00")

    assert fence.calls == 1
    assert preflight.to_dict()["preflight_type"] == WRITE_EFFECT_PREFLIGHT_TYPE
    assert preflight.environment == "staging"
    assert preflight.effect_ceiling == MUTATION_REVERSIBLE_EFFECT_CLASS
    assert preflight.provider_operation == "CREATE_REF"
    assert preflight.max_provider_mutations == 1
    assert WriteEffectPreflight.from_dict(preflight.to_dict()) == preflight


def test_write_effect_preflight_fails_closed_on_stale_current_fence() -> None:
    bundle = _bundle()
    fence = _Fence(reject=True)
    with pytest.raises(PermissionError, match="STALE_EFFECT_FENCE"):
        _verify(bundle, fence=fence, now="2026-08-18T17:00:05.000+00:00")
    assert fence.calls == 1


def test_write_effect_preflight_rejects_expired_credential_before_effect_fence() -> None:
    bundle = _bundle()
    fence = _Fence()
    with pytest.raises(WriteEffectPreflightDenied, match="F4A_CREDENTIAL_EXPIRED"):
        _verify(bundle, fence=fence, now="2026-08-18T17:02:03.000+00:00")
    assert fence.calls == 0


def test_write_effect_preflight_rejects_target_substitution() -> None:
    bundle = _bundle()
    request = bundle["request"]
    assert isinstance(request, GitHubCreateRefRequest)
    altered = request.to_dict()
    altered["target_digest"] = "f" * 64
    claims = {key: value for key, value in altered.items() if key != "request_digest"}
    altered["request_digest"] = _digest(claims)
    bundle["request"] = GitHubCreateRefRequest.from_dict(altered)

    fence = _Fence()
    with pytest.raises(WriteEffectPreflightDenied, match="F4A_TARGET_LINEAGE_MISMATCH"):
        _verify(bundle, fence=fence, now="2026-08-18T17:00:05.000+00:00")
    assert fence.calls == 0


def test_write_effect_preflight_rejects_colluding_runtime_instance_substitution() -> None:
    bundle = _bundle()
    delivery = bundle["delivery"]
    activation = bundle["activation"]
    assert isinstance(delivery, EphemeralWriteCredentialDelivery)
    assert isinstance(activation, WriteRuntimeActivation)

    altered_delivery = delivery.to_dict()
    altered_delivery["provider_instance_id"] = "gha:f4a:other"
    delivery_claims = {
        key: value
        for key, value in altered_delivery.items()
        if key != "delivery_digest"
    }
    altered_delivery["delivery_digest"] = _digest(delivery_claims)
    bundle["delivery"] = EphemeralWriteCredentialDelivery.from_dict(altered_delivery)

    altered_activation = activation.to_dict()
    altered_activation["provider_instance_id"] = "gha:f4a:other"
    altered_activation["credential_delivery_digest"] = bundle["delivery"].delivery_digest  # type: ignore[union-attr]
    activation_claims = {
        key: value
        for key, value in altered_activation.items()
        if key != "activation_digest"
    }
    altered_activation["activation_digest"] = _digest(activation_claims)
    bundle["activation"] = WriteRuntimeActivation.from_dict(altered_activation)

    with pytest.raises(WriteRuntimeDenied, match="F4A_RUNTIME_ACTIVATION_BINDING_MISMATCH"):
        _verify(bundle, fence=_Fence(), now="2026-08-18T17:00:05.000+00:00")
