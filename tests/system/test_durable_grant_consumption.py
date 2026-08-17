from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from voodoo_product.audit import AuditLedger
from voodoo_product.authoritative_grant import ExecutionGrantV2
from voodoo_product.authorization_snapshot import AuthorizationSnapshot
from voodoo_product.capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.execution_capsule import (
    CapsuleActivation,
    ExecutionCapsule,
    ImmutableExecutionCapsuleRegistry,
)
from voodoo_product.execution_conformance import (
    ExecutionConformanceAuthority,
    HandlerConformanceEvidence,
    ImmutableHandlerConformanceRegistry,
)
from voodoo_product.grant_consumption import (
    DurableGrantService,
    GrantConsumptionDenied,
    GrantConsumptionWitness,
)
from voodoo_product.monotonic_authority import AuthorityConstraint
from voodoo_product.operational_safety import OperationalSafetyService
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.precondition_witness import READ_THEN_COMPARE
from voodoo_product.trusted_clock import TrustedClockAuthority

SNAPSHOT_DIGEST = "a" * 64
REVIEW_DIGEST = "b" * 64
ISSUED_AT = "2026-08-17T02:00:00.000+00:00"
EXPIRES_AT = "2026-08-17T02:05:00.000+00:00"
PRECONDITION_AT = "2026-08-17T01:59:59.000+00:00"


@dataclass
class MutableClock:
    current: datetime

    def read(self) -> datetime:
        return self.current


@dataclass
class MutableRevocationAuthority:
    epoch: int

    def current_epoch(
        self,
        connection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int:
        del connection, workspace_id, environment, capability_definition_identity
        return self.epoch


class FakeAuthoritativeIssuer:
    def __init__(
        self,
        *,
        database,
        safety,
        revocation,
        clock,
        capsule_registry,
        grants: list[ExecutionGrantV2],
    ) -> None:
        self.db = database
        self.operational_safety_service = safety
        self.revocation_authority = revocation
        self.trusted_clock = clock
        self.execution_binding_authority = SimpleNamespace(registry=capsule_registry)
        self._grants = list(grants)

    def issue(self, *, snapshot, authority) -> ExecutionGrantV2:
        del snapshot, authority
        if not self._grants:
            raise RuntimeError("test issuer exhausted")
        return self._grants.pop(0)


def make_conformance(
    *,
    revoked_capsule: bool = False,
) -> tuple[
    CapabilityDefinition,
    ExecutionCapsule,
    ImmutableExecutionCapsuleRegistry,
    ExecutionConformanceAuthority,
]:
    definition = CapabilityDefinition.create(
        capability="voodoo.write-artifact/v1",
        target_kind="git_ref",
        binder_id="git-ref-binder/v1",
        handler_id="git-ref-handler/v1",
        effect_class="bounded-write",
        verification_class="provider-read/v1",
        supported_environments=("local",),
        required_permissions=("execution.run",),
        production_eligible=False,
    )
    capability_activation = CapabilityActivation.create(
        capability_definition_identity=definition.definition_identity,
        activation_generation=1,
        enabled_environments=("local",),
    )
    capability_registry = ImmutableCapabilityRegistry(
        definitions=(definition,),
        activations=(capability_activation,),
    )

    capsule = ExecutionCapsule.create(
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        handler_id=definition.handler_id,
        handler_digest="1" * 64,
        module_manifest_digest="2" * 64,
        artifact_kind="python-module",
        artifact_digest="3" * 64,
        rootfs_digest="4" * 64,
        dependency_lock_digest="5" * 64,
        sbom_digest="6" * 64,
        network_policy_digest="7" * 64,
        resource_limit_profile_digest="8" * 64,
        credential_class="github-scoped-ephemeral/v1",
        runner_class="sandcloud.isolated-linux/v1",
        precondition_enforcement_class=READ_THEN_COMPARE,
        verification_class=definition.verification_class,
        verification_contract_identity="9" * 64,
        capsule_revision="execution-capsule/test-r1",
    )
    capsule_activation = CapsuleActivation.create(
        execution_capsule_digest=capsule.capsule_digest,
        activation_generation=1,
        enabled_environments=("local",),
        revoked=revoked_capsule,
        production_eligible=False,
    )
    capsule_registry = ImmutableExecutionCapsuleRegistry(
        capability_registry=capability_registry,
        capsules=(capsule,),
        activations=(capsule_activation,),
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
        atomic_provider_condition_contract_identity=None,
        evidence_revision="handler-evidence/test-r1",
    )
    handler_registry = ImmutableHandlerConformanceRegistry(
        capsule_registry=capsule_registry,
        evidence=(evidence,),
    )
    conformance = ExecutionConformanceAuthority(
        capsule_registry=capsule_registry,
        handler_registry=handler_registry,
        authority_revision="execution-conformance/test-r1",
    )
    return definition, capsule, capsule_registry, conformance


def make_grant(
    *,
    definition: CapabilityDefinition,
    capsule: ExecutionCapsule,
    jti: str = "jti_b4_primary",
    grant_id: str = "grt_b4_primary",
    execution_id: str = "exec_b4",
) -> ExecutionGrantV2:
    return ExecutionGrantV2._issue(
        grant_id=grant_id,
        jti=jti,
        execution_id=execution_id,
        request_id="cr_b4",
        authorization_snapshot_digest=SNAPSHOT_DIGEST,
        snapshot_authority_witness_set_digest="c" * 64,
        snapshot_authority_event_hash="d" * 64,
        parent_scope_digest="e" * 64,
        authority_constraint_digest="f" * 64,
        monotonic_authority_decision_digest="0" * 64,
        actor_id="usr_admin",
        workspace_id="wrk_main",
        environment="local",
        capability=definition.capability,
        capability_definition_identity=definition.definition_identity,
        target_kind=definition.target_kind,
        target_digest="1" * 64,
        payload_digest="2" * 64,
        policy_version="approval-policy/current-v1",
        policy_identity="3" * 64,
        approval_set_digest="4" * 64,
        required_permission="execution.run",
        precondition_requirement_digest="5" * 64,
        precondition_expectation_digest="6" * 64,
        precondition_observation_digest="7" * 64,
        precondition_witness_digest="8" * 64,
        precondition_enforcement_class=capsule.precondition_enforcement_class,
        precondition_checked_at=PRECONDITION_AT,
        execution_binding_digest="9" * 64,
        execution_capsule_digest=capsule.capsule_digest,
        runner_class=capsule.runner_class,
        execution_binding_authority_revision="execution-binding/test-r1",
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        revocation_epoch=7,
        use_semantics="ONE_TIME",
        issuer_identity="grant-issuer/test",
        issuer_revision="grant-issuer/test-r1",
    )


def seed_snapshot(database: SQLiteProductDatabase) -> None:
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_admin', 'admin', 'unused', 'administrator', 1,
                    '2026-08-17T01:00:00.000+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO workspaces(id, name, environment, created_at)
            VALUES ('wrk_main', 'Main', 'local', '2026-08-17T01:00:00.000+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES (
                'cr_b4', 'wrk_main', 'B4', '', 'R1', 'local', 'echo', '{}',
                'DRAFT', 'usr_admin',
                '2026-08-17T01:00:00.000+00:00',
                '2026-08-17T01:00:00.000+00:00'
            )
            """
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'REVIEW_REQUIRED',
                review_content_sha256 = ?,
                updated_at = '2026-08-17T01:01:00.000+00:00'
            WHERE id = 'cr_b4'
            """,
            (REVIEW_DIGEST,),
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'APPROVED',
                updated_at = '2026-08-17T01:02:00.000+00:00'
            WHERE id = 'cr_b4'
            """
        )
        connection.execute(
            """
            INSERT INTO authorization_snapshots(
                id,
                execution_id,
                request_id,
                actor_id,
                workspace_id,
                environment,
                review_content_sha256,
                idempotency_key,
                idempotency_binding_digest,
                snapshot_digest,
                snapshot_json,
                execution_target_json,
                approval_evidence_json,
                created_at
            ) VALUES (
                'authz_b4',
                'exec_b4',
                'cr_b4',
                'usr_admin',
                'wrk_main',
                'local',
                ?,
                'b4-snapshot-idempotency',
                ?,
                ?,
                '{}',
                '{}',
                '{}',
                '2026-08-17T01:03:00.000+00:00'
            )
            """,
            (REVIEW_DIGEST, "5" * 64, SNAPSHOT_DIGEST),
        )


def build_service(
    tmp_path: Path,
    *,
    grants: list[ExecutionGrantV2] | None = None,
    revoked_capsule: bool = False,
    existing_database: SQLiteProductDatabase | None = None,
    clock_source: MutableClock | None = None,
    revocation: MutableRevocationAuthority | None = None,
    safety: OperationalSafetyService | None = None,
) -> tuple[
    DurableGrantService,
    SQLiteProductDatabase,
    MutableClock,
    MutableRevocationAuthority,
    OperationalSafetyService,
    ExecutionGrantV2,
]:
    definition, capsule, capsule_registry, conformance = make_conformance(
        revoked_capsule=revoked_capsule
    )
    database = existing_database or SQLiteProductDatabase(tmp_path / "product.sqlite3")
    if existing_database is None:
        database.initialize()
        seed_snapshot(database)

    source = clock_source or MutableClock(datetime(2026, 8, 17, 2, 0, 10, tzinfo=UTC))
    clock = TrustedClockAuthority(
        source_identity="clock/b4-test",
        authority_revision="clock/b4-test-r1",
        source=source,
        allowed_environments=frozenset({"local"}),
    )
    resolved_revocation = revocation or MutableRevocationAuthority(7)
    resolved_safety = safety or OperationalSafetyService(
        database=database,
        audit_ledger=AuditLedger(database),
    )
    primary_grant = make_grant(definition=definition, capsule=capsule)
    issuer = FakeAuthoritativeIssuer(
        database=database,
        safety=resolved_safety,
        revocation=resolved_revocation,
        clock=clock,
        capsule_registry=capsule_registry,
        grants=grants or [primary_grant],
    )
    service = DurableGrantService(
        database=database,
        grant_issuer=issuer,
        operational_safety_service=resolved_safety,
        revocation_authority=resolved_revocation,
        conformance_authority=conformance,
        trusted_clock=clock,
        authority_revision="durable-grant/test-r1",
    )
    return (
        service,
        database,
        source,
        resolved_revocation,
        resolved_safety,
        primary_grant,
    )


def store(service: DurableGrantService) -> ExecutionGrantV2:
    return service.issue_and_store(
        snapshot=cast(AuthorizationSnapshot, object()),
        authority=cast(AuthorityConstraint, object()),
    )


def test_issue_store_consume_round_trip_and_replay_denial(tmp_path: Path) -> None:
    service, database, _, _, _, grant = build_service(tmp_path)

    stored = store(service)
    assert stored == grant

    witness = service.consume(jti=grant.jti)
    assert witness.jti == grant.jti
    assert witness.grant_digest == grant.grant_digest
    assert witness.execution_id == grant.execution_id
    assert witness.live_revocation_epoch == 7
    assert GrantConsumptionWitness.from_dict(witness.to_dict()) == witness

    with pytest.raises(GrantConsumptionDenied) as replay:
        service.consume(jti=grant.jti)
    assert replay.value.reason == "GRANT_ALREADY_CONSUMED"

    with database.connect() as connection:
        grant_count = connection.execute(
            "SELECT COUNT(*) AS count FROM execution_grants_v2"
        ).fetchone()
        consumption_count = connection.execute(
            "SELECT COUNT(*) AS count FROM grant_consumptions_v1"
        ).fetchone()
    assert grant_count["count"] == 1
    assert consumption_count["count"] == 1


def test_two_concurrent_consumers_have_exactly_one_winner(tmp_path: Path) -> None:
    service, database, _, _, _, grant = build_service(tmp_path)
    store(service)

    def consume(_: int) -> str:
        try:
            service.consume(jti=grant.jti)
        except GrantConsumptionDenied as exc:
            return exc.reason
        return "CONSUMED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(consume, range(2)))

    assert sorted(outcomes) == ["CONSUMED", "GRANT_ALREADY_CONSUMED"]
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT jti FROM grant_consumptions_v1 WHERE jti = ?",
            (grant.jti,),
        ).fetchall()
    assert len(rows) == 1


def test_expiry_revocation_and_emergency_stop_fail_closed(tmp_path: Path) -> None:
    service, _, source, revocation, safety, grant = build_service(tmp_path)
    store(service)

    source.current = datetime(2026, 8, 17, 2, 5, 0, tzinfo=UTC)
    with pytest.raises(GrantConsumptionDenied) as expired:
        service.consume(jti=grant.jti)
    assert expired.value.reason == "GRANT_EXPIRED"

    source.current = datetime(2026, 8, 17, 2, 0, 20, tzinfo=UTC)
    revocation.epoch = 8
    with pytest.raises(GrantConsumptionDenied) as revoked:
        service.consume(jti=grant.jti)
    assert revoked.value.reason == "REVOCATION_EPOCH_CHANGED"

    revocation.epoch = 7
    safety.set_emergency_stop(
        actor_id="usr_admin",
        active=True,
        reason="B4 test",
    )
    with pytest.raises(GrantConsumptionDenied) as stopped:
        service.consume(jti=grant.jti)
    assert stopped.value.reason == "EMERGENCY_STOP_ACTIVE"


def test_fresh_conformance_is_rechecked_at_consumption(tmp_path: Path) -> None:
    service, database, source, revocation, safety, grant = build_service(tmp_path)
    store(service)

    drifted, _, _, _, _, _ = build_service(
        tmp_path,
        revoked_capsule=True,
        existing_database=database,
        clock_source=source,
        revocation=revocation,
        safety=safety,
    )
    with pytest.raises(GrantConsumptionDenied) as denied:
        drifted.consume(jti=grant.jti)
    assert denied.value.reason == "EXECUTION_CONFORMANCE_DENIED"


def test_one_execution_cannot_receive_two_durable_grants(tmp_path: Path) -> None:
    definition, capsule, _, _ = make_conformance()
    first = make_grant(definition=definition, capsule=capsule)
    second = make_grant(
        definition=definition,
        capsule=capsule,
        jti="jti_b4_second",
        grant_id="grt_b4_second",
    )
    service, _, _, _, _, _ = build_service(tmp_path, grants=[first, second])

    store(service)
    with pytest.raises(GrantConsumptionDenied) as duplicate:
        store(service)
    assert duplicate.value.reason == "GRANT_STORE_CONFLICT"


def test_grant_and_consumption_rows_are_append_only(tmp_path: Path) -> None:
    service, database, _, _, _, grant = build_service(tmp_path)
    store(service)
    service.consume(jti=grant.jti)

    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            "UPDATE execution_grants_v2 SET store_revision = 'rewritten' WHERE jti = ?",
            (grant.jti,),
        )

    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            "DELETE FROM grant_consumptions_v1 WHERE jti = ?",
            (grant.jti,),
        )


def test_unknown_grant_and_no_public_persist_entrypoint(tmp_path: Path) -> None:
    service, _, _, _, _, _ = build_service(tmp_path)
    assert not hasattr(service, "persist")

    with pytest.raises(GrantConsumptionDenied) as unknown:
        service.consume(jti="jti_unknown")
    assert unknown.value.reason == "GRANT_NOT_FOUND"
