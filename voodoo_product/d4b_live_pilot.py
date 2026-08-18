from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .capability_registry import CapabilityDefinition
from .credential_broker import CredentialBrokerPolicy, ImmutableCredentialBroker
from .db import SQLiteProductDatabase
from .dispatch_envelope import DispatchEnvelope
from .dispatch_inbox import DispatchInboxAdmission
from .dispatch_outbox import DispatchOutboxEntry
from .durable_current_fence import DurableCurrentExecutionFence
from .evidence_primitives import canonical_json
from .execution_capsule import ExecutionCapsule
from .execution_contract import ExecutionTarget
from .execution_lease_persistence import DurableExecutionLeaseService
from .github_actions_runtime import (
    GitHubActionsIsolatedRuntimeProvider,
    GitHubApiRefReadTransport,
)
from .github_read_provider import GitHubRefReadHandler
from .isolated_runner import IsolatedRunnerAdapter
from .precondition_witness import READ_THEN_COMPARE
from .trusted_clock import TrustedClockAuthority

ENVIRONMENT = "staging"
RUNNER_CLASS = "github-actions.docker-isolated/v1"
CREDENTIAL_CLASS = "github.actions-token.read/v1"
AUTHORITY_REVISION = "execution-epoch-authority/d4b-pilot-r1"
LEASE_REVISION = "execution-lease/c4b-r1"


def _digest(value: Any) -> str:
    raw = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


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


def build_capability() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        capability="github.read-ref/v1",
        target_kind="git_ref",
        binder_id="github-read-ref-target-binder/v1",
        handler_id="github-ref-read-handler/v1",
        effect_class="READ_ONLY",
        verification_class="OBSERVE_ONLY",
        supported_environments=(ENVIRONMENT,),
        required_permissions=("execution.run",),
        production_eligible=False,
    )


def build_capsule(
    *,
    definition: CapabilityDefinition,
    rootfs_digest: str,
    resource_limit_profile_digest: str,
    network_policy_digest: str,
) -> ExecutionCapsule:
    return ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest=_digest("github-ref-read-handler/d4b-r1"),
        module_manifest_digest=_digest("voodoo_product.github_read_provider/d4b-r1"),
        artifact_kind="python-module",
        artifact_digest=_digest("v-one-d4b-live-read-pilot/r1"),
        rootfs_digest=rootfs_digest,
        dependency_lock_digest=_digest("requirements-product.lock/d4b-r1"),
        sbom_digest=_digest("d4b-live-pilot-sbom/r1"),
        network_policy_digest=network_policy_digest,
        resource_limit_profile_digest=resource_limit_profile_digest,
        credential_class=CREDENTIAL_CLASS,
        runner_class=RUNNER_CLASS,
        precondition_enforcement_class=READ_THEN_COMPARE,
        verification_class=definition.verification_class,
        verification_contract_identity=_digest("github-ref-observation/v1"),
        capsule_revision="execution-capsule/d4b-live-pilot-r1",
    )


def seed_pilot_admission(
    *,
    database: SQLiteProductDatabase,
    definition: CapabilityDefinition,
    capsule: ExecutionCapsule,
    target: ExecutionTarget,
    now: datetime,
) -> DispatchInboxAdmission:
    """Seed only the already-proven Phase-C lineage for the D4b live runtime pilot.

    This is deliberately pilot-only fixture state. It does not pretend to be a live A/B
    authority issuance path and is never exposed as production authorization evidence.
    D4b is testing the D1-D4 runtime/effect boundary over a real durable C4 lease.
    """

    review_digest = _digest("d4b-pilot-review")
    snapshot_digest = _digest("d4b-pilot-snapshot")
    consumption_digest = _digest("d4b-pilot-consumption")
    grant_digest = _digest("d4b-pilot-grant")
    conformance_digest = _digest("d4b-pilot-conformance")
    clock_digest = _digest("d4b-pilot-store-clock")
    payload_digest = _digest({"pilot": "d4b-live-read"})
    created_at = _canonical_time(now - timedelta(seconds=5))

    outbox_claims: dict[str, object] = {
        "schema_version": 1,
        "entry_type": "dispatch-outbox-entry/v1",
        "outbox_id": "out_d4b_live_read",
        "consumption_id": "gcon_d4b_live_read",
        "consumption_witness_digest": consumption_digest,
        "jti": "jti_d4b_live_read",
        "grant_id": "grt_d4b_live_read",
        "grant_digest": grant_digest,
        "execution_id": "exec_d4b_live_read",
        "request_id": "cr_d4b_live_read",
        "actor_id": "usr_d4b_pilot",
        "workspace_id": "wrk_d4b_pilot",
        "environment": ENVIRONMENT,
        "capability": definition.capability,
        "capability_definition_identity": definition.definition_identity,
        "authorization_snapshot_digest": snapshot_digest,
        "target_kind": target.target_kind,
        "target_digest": target.target_digest,
        "payload_digest": payload_digest,
        "required_permission": "execution.run",
        "execution_binding_digest": _digest("d4b-pilot-execution-binding"),
        "execution_capsule_digest": capsule.capsule_digest,
        "runner_class": RUNNER_CLASS,
        "precondition_enforcement_class": READ_THEN_COMPARE,
        "use_semantics": "ONE_TIME",
        "created_at": created_at,
        "outbox_revision": "dispatch-outbox/d4b-pilot-r1",
    }
    outbox_claims["entry_digest"] = _digest(outbox_claims)
    outbox = DispatchOutboxEntry.from_dict(outbox_claims)
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/d4b-pilot-r1",
    )
    admission = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/d4b-pilot-r1",
    )

    issued_at = _canonical_time(now - timedelta(seconds=30))
    expires_at = _canonical_time(now + timedelta(minutes=30))
    stored_at = _canonical_time(now - timedelta(seconds=29))

    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES (?, ?, 'unused', 'administrator', 1, ?)
            """,
            ("usr_d4b_pilot", "d4b-pilot", _canonical_time(now - timedelta(minutes=5))),
        )
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "wrk_d4b_pilot",
                "D4b live read pilot",
                ENVIRONMENT,
                _canonical_time(now - timedelta(minutes=5)),
            ),
        )
        connection.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES (?, ?, ?, '', 'R1', ?, 'echo', '{}', 'DRAFT', ?, ?, ?)
            """,
            (
                "cr_d4b_live_read",
                "wrk_d4b_pilot",
                "D4b live governed GitHub ref read",
                ENVIRONMENT,
                "usr_d4b_pilot",
                _canonical_time(now - timedelta(minutes=4)),
                _canonical_time(now - timedelta(minutes=4)),
            ),
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'REVIEW_REQUIRED', review_content_sha256 = ?, updated_at = ?
            WHERE id = 'cr_d4b_live_read'
            """,
            (review_digest, _canonical_time(now - timedelta(minutes=3))),
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'APPROVED', updated_at = ?
            WHERE id = 'cr_d4b_live_read'
            """,
            (_canonical_time(now - timedelta(minutes=2)),),
        )
        connection.execute(
            """
            INSERT INTO authorization_snapshots(
                id, execution_id, request_id, actor_id, workspace_id, environment,
                review_content_sha256, idempotency_key, idempotency_binding_digest,
                snapshot_digest, snapshot_json, execution_target_json,
                approval_evidence_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "authz_d4b_live_read",
                "exec_d4b_live_read",
                "cr_d4b_live_read",
                "usr_d4b_pilot",
                "wrk_d4b_pilot",
                ENVIRONMENT,
                review_digest,
                "d4b-live-read-idempotency",
                _digest("d4b-idempotency-binding"),
                snapshot_digest,
                canonical_json({"pilot_seed": True}),
                canonical_json(target.to_dict()),
                canonical_json({"pilot_seed": True}),
                _canonical_time(now - timedelta(minutes=1)),
            ),
        )
        connection.execute(
            """
            INSERT INTO execution_grants_v2(
                jti, grant_id, execution_id, request_id, workspace_id, environment,
                authorization_snapshot_digest, execution_capsule_digest, grant_digest,
                grant_json, issuance_conformance_witness_digest,
                issuance_conformance_witness_json, store_clock_witness_digest,
                store_clock_witness_json, issued_at, expires_at, revocation_epoch,
                stored_at, store_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                "jti_d4b_live_read",
                "grt_d4b_live_read",
                "exec_d4b_live_read",
                "cr_d4b_live_read",
                "wrk_d4b_pilot",
                ENVIRONMENT,
                snapshot_digest,
                capsule.capsule_digest,
                grant_digest,
                canonical_json({"pilot_seed": True}),
                conformance_digest,
                canonical_json({"pilot_seed": True}),
                clock_digest,
                canonical_json({"pilot_seed": True}),
                issued_at,
                expires_at,
                stored_at,
                "durable-grant/d4b-pilot-r1",
            ),
        )
        connection.execute(
            """
            INSERT INTO grant_consumptions_v1(
                consumption_id, jti, grant_digest, execution_id,
                authorization_snapshot_digest, execution_capsule_digest, runner_class,
                conformance_witness_digest, conformance_witness_json,
                clock_witness_digest, clock_witness_json, live_revocation_epoch,
                consumed_at, serialization_contract, authority_revision,
                consumption_digest, consumption_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                "gcon_d4b_live_read",
                "jti_d4b_live_read",
                grant_digest,
                "exec_d4b_live_read",
                snapshot_digest,
                capsule.capsule_digest,
                RUNNER_CLASS,
                conformance_digest,
                canonical_json({"pilot_seed": True}),
                clock_digest,
                canonical_json({"pilot_seed": True}),
                created_at,
                "sqlite-begin-immediate/v1",
                "durable-grant/d4b-pilot-r1",
                consumption_digest,
                canonical_json({"pilot_seed": True}),
            ),
        )
        connection.execute(
            """
            INSERT INTO dispatch_outbox_v1(
                outbox_id, consumption_id, consumption_witness_digest, jti, grant_id,
                grant_digest, execution_id, request_id, actor_id, workspace_id,
                environment, capability, capability_definition_identity,
                authorization_snapshot_digest, target_kind, target_digest,
                payload_digest, required_permission, execution_binding_digest,
                execution_capsule_digest, runner_class, precondition_enforcement_class,
                use_semantics, created_at, outbox_revision, entry_digest, entry_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?)
            """,
            (
                outbox.outbox_id,
                outbox.consumption_id,
                outbox.consumption_witness_digest,
                outbox.jti,
                outbox.grant_id,
                outbox.grant_digest,
                outbox.execution_id,
                outbox.request_id,
                outbox.actor_id,
                outbox.workspace_id,
                outbox.environment,
                outbox.capability,
                outbox.capability_definition_identity,
                outbox.authorization_snapshot_digest,
                outbox.target_kind,
                outbox.target_digest,
                outbox.payload_digest,
                outbox.required_permission,
                outbox.execution_binding_digest,
                outbox.execution_capsule_digest,
                outbox.runner_class,
                outbox.precondition_enforcement_class,
                outbox.use_semantics,
                outbox.created_at,
                outbox.outbox_revision,
                outbox.entry_digest,
                canonical_json(outbox.to_dict()),
            ),
        )
        connection.execute(
            """
            INSERT INTO dispatch_inbox_v1(
                admission_id, dispatch_id, envelope_digest, outbox_id,
                outbox_entry_digest, execution_id, workspace_id, environment,
                execution_capsule_digest, runner_class, admission_revision,
                admission_digest, admission_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admission.admission_id,
                admission.dispatch_id,
                admission.envelope_digest,
                admission.outbox_id,
                admission.outbox_entry_digest,
                admission.execution_id,
                admission.workspace_id,
                admission.environment,
                admission.execution_capsule_digest,
                admission.runner_class,
                admission.admission_revision,
                admission.admission_digest,
                canonical_json(admission.to_dict()),
            ),
        )
    return admission


def run_live_pilot() -> dict[str, Any]:
    token = _require_env("GITHUB_TOKEN")
    provider_instance_id = _require_env("VONE_PROVIDER_INSTANCE_ID")
    repository = _require_env("VONE_TARGET_REPOSITORY")
    ref = _require_env("VONE_TARGET_REF")
    rootfs_digest = _require_digest(
        _require_env("VONE_RUNTIME_ROOTFS_DIGEST"),
        field="VONE_RUNTIME_ROOTFS_DIGEST",
    )
    resource_digest = _require_digest(
        _require_env("VONE_RESOURCE_LIMIT_PROFILE_DIGEST"),
        field="VONE_RESOURCE_LIMIT_PROFILE_DIGEST",
    )
    network_digest = _require_digest(
        _require_env("VONE_NETWORK_POLICY_DIGEST"),
        field="VONE_NETWORK_POLICY_DIGEST",
    )

    target = ExecutionTarget.create(
        target_kind="git_ref",
        target_claims={"repository": repository, "ref": ref},
    )
    definition = build_capability()
    capsule = build_capsule(
        definition=definition,
        rootfs_digest=rootfs_digest,
        resource_limit_profile_digest=resource_digest,
        network_policy_digest=network_digest,
    )

    database_fd, database_name = tempfile.mkstemp(
        prefix="vone-d4b-live-read-",
        suffix=".sqlite3",
    )
    os.close(database_fd)
    database_path = Path(database_name)
    database = SQLiteProductDatabase(database_path)
    database.initialize()

    now = datetime.now(UTC)
    admission = seed_pilot_admission(
        database=database,
        definition=definition,
        capsule=capsule,
        target=target,
        now=now,
    )
    trusted_clock = TrustedClockAuthority(
        source_identity="github-actions-system-utc/d4b-r1",
        authority_revision="trusted-clock/d4b-live-pilot-r1",
        allowed_environments=frozenset({ENVIRONMENT}),
    )
    lease_service = DurableExecutionLeaseService(
        database=database,
        trusted_clock=trusted_clock,
        lease_seconds=300,
        lease_revision=LEASE_REVISION,
        authority_revision=AUTHORITY_REVISION,
    )
    lease_result = lease_service.acquire(admission_id=admission.admission_id)
    fence = DurableCurrentExecutionFence(database=database, trusted_clock=trusted_clock)

    policy = CredentialBrokerPolicy.create(
        credential_class=CREDENTIAL_CLASS,
        provider="github",
        audience="api.github.com",
        allowed_capability_definition_identities=(definition.definition_identity,),
        enabled_environments=(ENVIRONMENT,),
        policy_revision="credential-broker-policy/d4b-live-pilot-r1",
    )
    broker = ImmutableCredentialBroker(
        policies=(policy,),
        decision_revision="credential-access-decision/d4b-live-pilot-r1",
    )
    runtime_provider = GitHubActionsIsolatedRuntimeProvider(
        provider_instance_id=provider_instance_id,
        runner_class=RUNNER_CLASS,
        environment=ENVIRONMENT,
        rootfs_digest=rootfs_digest,
        resource_limit_profile_digest=resource_digest,
        network_policy_digest=network_digest,
        bootstrap_revision="runtime-bootstrap/d4b-live-pilot-r1",
        activation_revision="runtime-activation/d4b-live-pilot-r1",
    )
    adapter = IsolatedRunnerAdapter(
        provider=runtime_provider,
        credential_broker=broker,
        current_fence=fence,
        identity_revision="runner-identity/d4b-live-pilot-r1",
        boundary_revision="runner-boundary/d4b-live-pilot-r1",
        activation_revision="runtime-activation/d4b-live-pilot-r1",
    )
    prepared = adapter.prepare(
        lease=lease_result.lease,
        capsule=capsule,
        definition=definition,
    )
    activation = adapter.activate(prepared=prepared)

    transport = GitHubApiRefReadTransport(token=token)
    handler = GitHubRefReadHandler(
        transport=transport,
        current_fence=fence,
        trusted_clock=trusted_clock,
        observation_revision="github-ref-observation/d4b-live-pilot-r1",
    )
    observation = handler.observe_ref(
        prepared=prepared,
        activation=activation,
        target=target,
    )
    completion = lease_service.complete(
        lease_id=lease_result.lease.lease_id,
        completion_digest=observation.observation_digest,
    )

    return {
        "pilot": "d4b-live-governed-read/v1",
        "status": "PASS",
        "phase_d_effect_ceiling": "READ_ONLY",
        "provider_mutation_allowed": False,
        "target": target.to_dict(),
        "lease": lease_result.lease.to_dict(),
        "runtime_bootstrap": prepared.bootstrap.to_dict(),
        "runtime_activation": activation.to_dict(),
        "credential_decision": prepared.decision.to_dict(),
        "observation": observation.to_dict(),
        "durable_completion": {
            "outcome": completion.outcome,
            "completion_digest": completion.completion_digest,
        },
    }


def main() -> None:
    result = run_live_pilot()
    print("D4B_LIVE_GOVERNED_READ=PASS")
    print(canonical_json(result))


if __name__ == "__main__":
    main()
