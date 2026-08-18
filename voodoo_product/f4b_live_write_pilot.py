from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .approval_policy import CURRENT_APPROVAL_POLICY_VERSION
from .authoritative_grant import AuthoritativeGrantIssuer
from .authorization_snapshot_creator import (
    AuthoritativeSnapshotCreator,
    ImmutableCapabilitySelectionAuthority,
)
from .authorization_snapshot_store import AuthorizationSnapshotStore
from .capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from .config import ProductConfig
from .controlled_write import (
    GITHUB_CREATE_REF_CAPABILITY,
    GITHUB_CREATE_REF_HANDLER,
    MUTATION_REVERSIBLE_EFFECT_CLASS,
    ControlledWriteRequirement,
    GitHubCreateRefConditionContract,
)
from .dispatch_envelope import DispatchEnvelope
from .dispatch_inbox_persistence import DurableDispatchInboxService
from .dispatch_outbox_persistence import DurableDispatchOutboxService
from .durable_coordinator import NativeDurableCoordinator
from .durable_current_fence import DurableCurrentExecutionFence
from .evidence_primitives import canonical_json
from .execution_capsule import (
    AuthoritativeExecutionBindingAuthority,
    CapsuleActivation,
    ExecutionCapsule,
    ImmutableExecutionCapsuleRegistry,
)
from .execution_conformance import (
    ExecutionConformanceAuthority,
    HandlerConformanceEvidence,
    ImmutableHandlerConformanceRegistry,
)
from .execution_lease_persistence import DurableExecutionLeaseService
from .github_create_ref_provider import (
    GITHUB_CREATE_REF_BINDER_ID,
    GitHubCreateRefHandlerContract,
    GitHubCreateRefTargetBinder,
)
from .github_create_ref_runtime import GitHubApiCreateRefTransport
from .grant_consumption import DurableGrantService, GrantConsumptionWitness
from .isolated_runner import IsolatedRuntimeBootstrap
from .monotonic_authority import AuthorityConstraint, AuthorityScope
from .permission_authority import CurrentPrincipalPermissionAuthority
from .policy_authority import ImmutablePolicyAuthority, PolicyRevision
from .precondition_witness import (
    ATOMIC_PROVIDER_CONDITION,
    ImmutablePreconditionRequirementRegistry,
    PreconditionExpectationBinderRegistry,
    PreconditionGuard,
    PreconditionObserverRegistry,
    PreconditionRequirement,
)
from .runner_identity import RunnerIdentity
from .security import Principal
from .service import ProductService
from .target_binding import TargetBinderRegistry, TargetBinding
from .trusted_clock import TrustedClockAuthority
from .write_boundary import (
    GITHUB_CREATE_REF_CREDENTIAL_CLASS,
    WRITE_RUNNER_CLASS,
    CredentialAccessDecisionV2,
    CredentialBrokerPolicyV2,
    RunnerBoundaryV2,
)
from .write_runtime import (
    EphemeralWriteCredentialDelivery,
    WriteEffectPreflight,
    WriteRuntimeActivation,
)

ENVIRONMENT = "staging"
ADAPTER = "github-create-ref"
REVOCATION_EPOCH = 1
PRECONDITION_STATE_SCHEMA = "github-create-ref-atomic-condition-state/v1"
EXPECTATION_BINDER_ID = "github-create-ref-condition-expectation/f4b-r1"
OBSERVER_ID = "github-create-ref-condition-observer/f4b-r1"


def _digest(value: Any) -> str:
    raw = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value.strip()


def _require_digest(value: str, *, field: str) -> str:
    if (
        len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_sha1(value: str, *, field: str) -> str:
    if (
        len(value) != 40
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeError(f"{field} must be a lowercase 40-character Git object id")
    return value


class PilotRevocationAuthority:
    """Ephemeral staging authority for this bounded pilot only; never production authority."""

    def current_epoch(
        self,
        connection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int:
        del connection, workspace_id, capability_definition_identity
        if environment != ENVIRONMENT:
            raise PermissionError("F4B_REVOCATION_AUTHORITY_ENVIRONMENT_MISMATCH")
        return REVOCATION_EPOCH


class CreateRefConditionExpectationBinder:
    binder_id = EXPECTATION_BINDER_ID
    target_kind = "git_ref"
    state_schema = PRECONDITION_STATE_SCHEMA

    def __init__(self, condition: GitHubCreateRefConditionContract) -> None:
        self.condition = condition

    def bind_expected(self, *, target) -> dict[str, Any]:
        return {
            "target_digest": target.target_digest,
            "condition_contract_digest": self.condition.contract_digest,
            "operation": self.condition.operation,
            "create_semantics": self.condition.create_semantics,
        }


class CreateRefConditionObserver:
    observer_id = OBSERVER_ID
    target_kind = "git_ref"
    state_schema = PRECONDITION_STATE_SCHEMA
    source_identity = "v-one-control-plane/create-ref-condition/f4b-r1"

    def __init__(self, condition: GitHubCreateRefConditionContract) -> None:
        self.condition = condition

    def observe(self, *, target) -> dict[str, Any]:
        # This observes the immutable atomic-condition contract, not remote ref absence. The actual
        # CREATE_ONLY condition is enforced by GitHub's create-ref POST at the provider boundary.
        return {
            "target_digest": target.target_digest,
            "condition_contract_digest": self.condition.contract_digest,
            "operation": self.condition.operation,
            "create_semantics": self.condition.create_semantics,
        }


def _build_capability() -> tuple[CapabilityDefinition, CapabilityActivation]:
    definition = CapabilityDefinition.create(
        capability=GITHUB_CREATE_REF_CAPABILITY,
        target_kind="git_ref",
        binder_id=GITHUB_CREATE_REF_BINDER_ID,
        handler_id=GITHUB_CREATE_REF_HANDLER,
        effect_class=MUTATION_REVERSIBLE_EFFECT_CLASS,
        verification_class="provider-read/v1",
        supported_environments=(ENVIRONMENT,),
        required_permissions=("execution.run",),
        production_eligible=False,
    )
    activation = CapabilityActivation.create(
        capability_definition_identity=definition.definition_identity,
        activation_generation=1,
        enabled_environments=(ENVIRONMENT,),
    )
    return definition, activation


def _build_capsule(
    *,
    definition: CapabilityDefinition,
    rootfs_digest: str,
    resource_digest: str,
    network_digest: str,
    condition: GitHubCreateRefConditionContract,
) -> tuple[ExecutionCapsule, CapsuleActivation, HandlerConformanceEvidence]:
    capsule = ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest=_digest("github-create-ref-handler/f4b-live-r1"),
        module_manifest_digest=_digest("voodoo_product.github_create_ref_runtime/f4b-live-r1"),
        artifact_kind="oci-image",
        artifact_digest=rootfs_digest,
        rootfs_digest=rootfs_digest,
        dependency_lock_digest=_digest("requirements-product.lock/f4b-live-r1"),
        sbom_digest=_digest("f4b-live-create-ref-sbom/r1"),
        network_policy_digest=network_digest,
        resource_limit_profile_digest=resource_digest,
        credential_class=GITHUB_CREATE_REF_CREDENTIAL_CLASS,
        runner_class=WRITE_RUNNER_CLASS,
        precondition_enforcement_class=ATOMIC_PROVIDER_CONDITION,
        verification_class=definition.verification_class,
        verification_contract_identity=_digest("post-write-independent-readback/f4b-r1"),
        capsule_revision="execution-capsule/f4b-live-r1",
    )
    activation = CapsuleActivation.create(
        execution_capsule_digest=capsule.capsule_digest,
        activation_generation=1,
        enabled_environments=(ENVIRONMENT,),
    )
    evidence = HandlerConformanceEvidence.create(
        capability_definition_identity=definition.definition_identity,
        execution_capsule_digest=capsule.capsule_digest,
        handler_id=capsule.handler_id,
        handler_digest=capsule.handler_digest,
        runner_class=capsule.runner_class,
        credential_class=capsule.credential_class,
        precondition_enforcement_class=capsule.precondition_enforcement_class,
        verification_contract_identity=capsule.verification_contract_identity,
        atomic_provider_condition_contract_identity=condition.contract_digest,
        evidence_revision="handler-conformance/f4b-live-r1",
    )
    return capsule, activation, evidence


def _authority_from_snapshot(snapshot) -> AuthorityConstraint:
    scope = AuthorityScope.from_snapshot(snapshot)
    return AuthorityConstraint.create(
        parent_scope_digest=scope.scope_digest,
        actor_id=scope.actor_id,
        workspace_id=scope.workspace_id,
        environment=scope.environment,
        capability=scope.capability,
        capability_definition_identity=scope.capability_definition_identity,
        target_kind=scope.target_kind,
        target_digest=scope.target_digest,
        payload_digest=scope.payload_digest,
        policy_version=scope.policy_version,
        policy_identity=scope.policy_identity,
        approval_set_digest=scope.approval_set_digest,
        required_permission=scope.required_permission,
        valid_from=scope.valid_from,
        valid_until=scope.valid_until,
    )


def _load_consumption(service: ProductService, consumption_id: str) -> GrantConsumptionWitness:
    with service.db.connect() as connection:
        row = connection.execute(
            "SELECT consumption_json FROM grant_consumptions_v1 WHERE consumption_id = ?",
            (consumption_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("F4B_DURABLE_CONSUMPTION_NOT_FOUND")
    value = json.loads(str(row["consumption_json"]))
    return GrantConsumptionWitness.from_dict(value)


def run_live_write_pilot() -> dict[str, Any]:
    token = _require_env("GITHUB_TOKEN")
    repository = _require_env("VONE_TARGET_REPOSITORY")
    ref = _require_env("VONE_TARGET_REF")
    target_sha = _require_sha1(_require_env("VONE_TARGET_SHA"), field="VONE_TARGET_SHA")
    provider_instance_id = _require_env("VONE_PROVIDER_INSTANCE_ID")
    rootfs_digest = _require_digest(
        _require_env("VONE_RUNTIME_ROOTFS_DIGEST"), field="VONE_RUNTIME_ROOTFS_DIGEST"
    )
    resource_digest = _require_digest(
        _require_env("VONE_RESOURCE_LIMIT_PROFILE_DIGEST"),
        field="VONE_RESOURCE_LIMIT_PROFILE_DIGEST",
    )
    network_digest = _require_digest(
        _require_env("VONE_NETWORK_POLICY_DIGEST"), field="VONE_NETWORK_POLICY_DIGEST"
    )
    if not ref.startswith("refs/heads/vone-canary/"):
        raise RuntimeError("F4B_TARGET_REF_OUTSIDE_CANARY_NAMESPACE")

    condition = GitHubCreateRefConditionContract.create(
        contract_revision="github-create-ref-condition/f4b-live-r1"
    )
    definition, capability_activation = _build_capability()
    capsule, capsule_activation, handler_evidence = _build_capsule(
        definition=definition,
        rootfs_digest=rootfs_digest,
        resource_digest=resource_digest,
        network_digest=network_digest,
        condition=condition,
    )
    capability_registry = ImmutableCapabilityRegistry(
        definitions=(definition,), activations=(capability_activation,)
    )
    capsule_registry = ImmutableExecutionCapsuleRegistry(
        capability_registry=capability_registry,
        capsules=(capsule,),
        activations=(capsule_activation,),
    )
    handler_registry = ImmutableHandlerConformanceRegistry(
        capsule_registry=capsule_registry,
        evidence=(handler_evidence,),
    )
    conformance_authority = ExecutionConformanceAuthority(
        capsule_registry=capsule_registry,
        handler_registry=handler_registry,
        authority_revision="execution-conformance/f4b-live-r1",
    )
    execution_binding_authority = AuthoritativeExecutionBindingAuthority(
        registry=capsule_registry,
        authority_revision="execution-binding/f4b-live-r1",
    )

    database_fd, database_name = tempfile.mkstemp(
        prefix="vone-f4b-live-write-", suffix=".sqlite3"
    )
    os.close(database_fd)
    database_path = Path(database_name)
    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=database_path,
            sandbox_root=database_path.parent / f"{database_path.stem}-sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        )
    )

    bootstrap = service.bootstrap_admin(
        username="f4b-admin",
        password="F4bVeryStrongAdminPassword1!",
        token="b" * 48,
    )
    workspace = service.create_workspace(
        actor_id=bootstrap["user_id"], name="F4b staging canary", environment=ENVIRONMENT
    )
    reviewer = service.create_user(
        actor_id=bootstrap["user_id"],
        username="f4b-reviewer",
        password="F4bVeryStrongReviewerPassword1!",
        role="operator",
    )
    executor = service.create_user(
        actor_id=bootstrap["user_id"],
        username="f4b-executor",
        password="F4bVeryStrongExecutorPassword1!",
        role="operator",
    )
    approved_payload = {"repository": repository, "ref": ref, "commit_sha": target_sha}
    change = service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=workspace["id"],
        title="F4b first live canary create-ref",
        description="Single staging-only create-only GitHub canary reference",
        risk="R1",
        environment=ENVIRONMENT,
        adapter=ADAPTER,
        payload=approved_payload,
    )
    service.submit_change_request(actor_id=bootstrap["user_id"], request_id=change["id"])
    service.approve_change_request(
        actor_id=reviewer["id"],
        request_id=change["id"],
        decision="APPROVED",
        reason="explicit F4b canary authorization",
    )

    trusted_clock = TrustedClockAuthority(
        source_identity="github-actions-system-utc/f4b-r1",
        authority_revision="trusted-clock/f4b-live-r1",
        allowed_environments=frozenset({ENVIRONMENT}),
    )
    revocation_authority = PilotRevocationAuthority()
    policy = PolicyRevision.create(
        policy_version=CURRENT_APPROVAL_POLICY_VERSION,
        policy_package="v-one.approval.current-compatibility",
        approval_validity_seconds=600,
        required_approvals_by_environment={
            "development": 1,
            "local": 1,
            "production": 2,
            "staging": 1,
        },
    )
    snapshot_store = AuthorizationSnapshotStore(
        database=service.db,
        audit_ledger=service.audit_ledger,
        clock=lambda: datetime.now(UTC).isoformat(timespec="milliseconds"),
    )
    snapshot_creator = AuthoritativeSnapshotCreator(
        database=service.db,
        audit_ledger=service.audit_ledger,
        snapshot_store=snapshot_store,
        permission_authority=CurrentPrincipalPermissionAuthority(
            principal=Principal(
                user_id=executor["id"], username="f4b-executor", role="operator"
            ),
            authority_revision="current-role-authority/f4b-live-r1",
        ),
        policy_authority=ImmutablePolicyAuthority((policy,)),
        policy_version=policy.policy_version,
        capability_registry=capability_registry,
        capability_selection_authority=ImmutableCapabilitySelectionAuthority(
            bindings={ADAPTER: definition.capability},
            authority_revision="capability-selection/f4b-live-r1",
        ),
        target_binders=TargetBinderRegistry(
            {GITHUB_CREATE_REF_BINDER_ID: GitHubCreateRefTargetBinder()}
        ),
        trusted_clock=trusted_clock,
        revocation_authority=revocation_authority,
        operational_safety_service=service.operational_safety_service,
        production_effects_enabled=False,
        authorization_source_revision="snapshot-creator/f4b-live-r1",
    )
    snapshot = snapshot_creator.create_snapshot(
        actor_id=executor["id"],
        request_id=change["id"],
        idempotency_key=f"f4b:{ref}:{target_sha}",
        correlation_id="f4b-first-live-canary-create-ref-r1",
    )

    requirement = PreconditionRequirement.create(
        capability_definition_identity=definition.definition_identity,
        target_kind="git_ref",
        expectation_binder_id=EXPECTATION_BINDER_ID,
        observer_id=OBSERVER_ID,
        state_schema=PRECONDITION_STATE_SCHEMA,
        requirement_revision="precondition/f4b-live-r1",
        enforcement_class=ATOMIC_PROVIDER_CONDITION,
    )
    precondition_guard = PreconditionGuard(
        requirements=ImmutablePreconditionRequirementRegistry((requirement,)),
        expectation_binders=PreconditionExpectationBinderRegistry(
            {EXPECTATION_BINDER_ID: CreateRefConditionExpectationBinder(condition)}
        ),
        observers=PreconditionObserverRegistry(
            {OBSERVER_ID: CreateRefConditionObserver(condition)}
        ),
        trusted_clock=trusted_clock,
    )
    grant_issuer = AuthoritativeGrantIssuer(
        database=service.db,
        operational_safety_service=service.operational_safety_service,
        revocation_authority=revocation_authority,
        precondition_guard=precondition_guard,
        execution_binding_authority=execution_binding_authority,
        trusted_clock=trusted_clock,
        issuer_identity="v-one.authoritative-grant-issuer/f4b-live",
        issuer_revision="authoritative-grant-issuer/f4b-live-r1",
        grant_ttl_seconds=180,
    )
    grant_service = DurableGrantService(
        database=service.db,
        grant_issuer=grant_issuer,
        operational_safety_service=service.operational_safety_service,
        revocation_authority=revocation_authority,
        conformance_authority=conformance_authority,
        trusted_clock=trusted_clock,
        authority_revision="durable-grant/f4b-live-r1",
    )
    authority = _authority_from_snapshot(snapshot)
    grant = grant_service.issue_and_store(snapshot=snapshot, authority=authority)
    outbox_service = DurableDispatchOutboxService(
        grant_service=grant_service,
        outbox_revision="dispatch-outbox/f4b-live-r1",
    )
    outbox = outbox_service.consume_and_enqueue(jti=grant.jti)
    consumption = _load_consumption(service, outbox.consumption_id)
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox, envelope_revision="dispatch-envelope/f4b-live-r1"
    )
    inbox_service = DurableDispatchInboxService(
        database=service.db, admission_revision="dispatch-inbox/f4b-live-r1"
    )
    lease_service = DurableExecutionLeaseService(
        database=service.db,
        trusted_clock=trusted_clock,
        lease_seconds=180,
        lease_revision="execution-lease/f4b-live-r1",
        authority_revision="execution-epoch-authority/f4b-live-r1",
    )
    coordinator = NativeDurableCoordinator(
        inbox_service=inbox_service, lease_service=lease_service
    )
    admission_result = coordinator.admit(envelope=envelope)
    lease_result = coordinator.acquire(admission_id=admission_result.admission.admission_id)
    lease = lease_result.lease
    fence = DurableCurrentExecutionFence(database=service.db, trusted_clock=trusted_clock)

    bootstrap_runtime = IsolatedRuntimeBootstrap.create(
        provider="github-actions",
        provider_instance_id=provider_instance_id,
        runner_class=WRITE_RUNNER_CLASS,
        environment=ENVIRONMENT,
        rootfs_digest=rootfs_digest,
        resource_limit_profile_digest=resource_digest,
        network_policy_digest=network_digest,
        bootstrap_revision="isolated-runtime/f4b-live-r1",
    )
    identity = RunnerIdentity.create(
        runner_class=bootstrap_runtime.runner_class,
        provider=bootstrap_runtime.provider,
        provider_instance_id=bootstrap_runtime.provider_instance_id,
        environment=bootstrap_runtime.environment,
        rootfs_digest=bootstrap_runtime.rootfs_digest,
        resource_limit_profile_digest=bootstrap_runtime.resource_limit_profile_digest,
        network_policy_digest=bootstrap_runtime.network_policy_digest,
        identity_revision="runner-identity/f4b-live-r1",
    )
    controlled_requirement = ControlledWriteRequirement.create(
        definition=definition,
        capsule=capsule,
        handler_evidence=handler_evidence,
        provider_condition=condition,
        requirement_revision="controlled-write-requirement/f4b-live-r1",
    )
    boundary = RunnerBoundaryV2.create(
        identity=identity,
        lease=lease,
        capsule=capsule,
        definition=definition,
        handler_evidence=handler_evidence,
        provider_condition=condition,
        requirement=controlled_requirement,
        boundary_revision="runner-boundary/f4b-live-r1",
    )
    credential_policy = CredentialBrokerPolicyV2.create(
        boundary=boundary,
        max_ttl_seconds=120,
        policy_revision="credential-broker-policy/f4b-live-r1",
    )
    decision = CredentialAccessDecisionV2.create(
        boundary=boundary,
        lease=lease,
        policy=credential_policy,
        decision_revision="credential-access-decision/f4b-live-r1",
    )

    # Presence of the non-empty process-local GITHUB_TOKEN is the live out-of-band delivery fact.
    # The canonical delivery metadata contains no token bytes or secret handle.
    delivery_clock = trusted_clock.witness(environment=ENVIRONMENT)
    delivery = EphemeralWriteCredentialDelivery.create(
        bootstrap=bootstrap_runtime,
        identity=identity,
        boundary=boundary,
        decision=decision,
        lease=lease,
        clock_witness=delivery_clock,
        delivery_revision="credential-delivery/f4b-live-r1",
    )
    activation = WriteRuntimeActivation.create(
        bootstrap=bootstrap_runtime,
        identity=identity,
        boundary=boundary,
        decision=decision,
        delivery=delivery,
        lease=lease,
        activation_revision="write-runtime-activation/f4b-live-r1",
    )
    target = GitHubCreateRefTargetBinder().bind(approved_payload=approved_payload)
    if target.target_digest != snapshot.execution_target.target_digest:
        raise RuntimeError("F4B_SNAPSHOT_TARGET_REBIND_MISMATCH")
    target_binding = TargetBinding.create(
        binder_id=GITHUB_CREATE_REF_BINDER_ID,
        capability_definition_identity=definition.definition_identity,
        target=target,
    )
    handler = GitHubCreateRefHandlerContract(
        request_revision="github-create-ref-request/f4b-live-r1"
    )
    request = handler.prepare_request(
        target_binding=target_binding, boundary=boundary, decision=decision
    )
    preflight = WriteEffectPreflight.verify(
        grant=grant,
        consumption=consumption,
        outbox=outbox,
        envelope=envelope,
        admission=admission_result.admission,
        lease=lease,
        identity=identity,
        boundary=boundary,
        policy=credential_policy,
        decision=decision,
        delivery=delivery,
        delivery_clock_witness=delivery_clock,
        activation=activation,
        request=request,
        current_fence=fence,
        trusted_clock=trusted_clock,
        preflight_revision="write-effect-preflight/f4b-live-r1",
    )

    # Exactly one provider mutation boundary. No retry, update, force-update or delete fallback.
    transport = GitHubApiCreateRefTransport(token=token)
    provider_response = transport.create_ref(request=request)
    interpreted = handler.interpret_response(request=request, response=provider_response)
    completion = coordinator.complete(
        lease_id=lease.lease_id,
        completion_digest=interpreted.response_digest,
    )

    return {
        "pilot": "f4b-first-live-canary-create-ref/v1",
        "status": "EFFECT_RECORDED_NOT_VERIFIED",
        "environment": ENVIRONMENT,
        "provider_operation": "CREATE_REF",
        "provider_mutation_performed": True,
        "provider_mutation_count": 1,
        "automatic_retry_performed": False,
        "rollback_performed": False,
        "credential_secret_material_serialized": False,
        "credential_delivery_confirmed_out_of_band": True,
        "target": target.to_dict(),
        "authorization_snapshot_digest": snapshot.snapshot_digest,
        "execution_grant": grant.to_dict(),
        "grant_consumption": consumption.to_dict(),
        "dispatch_outbox": outbox.to_dict(),
        "dispatch_envelope": envelope.to_dict(),
        "dispatch_admission": admission_result.admission.to_dict(),
        "execution_lease": lease.to_dict(),
        "runner_identity": identity.to_dict(),
        "runner_boundary": boundary.to_dict(),
        "credential_decision": decision.to_dict(),
        "credential_delivery": delivery.to_dict(),
        "runtime_activation": activation.to_dict(),
        "create_ref_request": request.to_dict(),
        "write_effect_preflight": preflight.to_dict(),
        "provider_response": interpreted.to_dict(),
        "durable_completion": {
            "outcome": completion.outcome,
            "completion_digest": completion.completion_digest,
        },
    }


def main() -> None:
    result = run_live_write_pilot()
    print("F4B_LIVE_CANARY_CREATE_REF=EFFECT_RECORDED_NOT_VERIFIED")
    print(canonical_json(result))


if __name__ == "__main__":
    main()
