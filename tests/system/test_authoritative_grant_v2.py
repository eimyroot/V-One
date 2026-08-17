from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from voodoo_product.authoritative_grant import (
    EXECUTION_GRANT_V2_TYPE,
    AuthoritativeGrantIssuer,
    ExecutionBinding,
    ExecutionGrantV2,
    GrantIssuanceDenied,
)
from voodoo_product.authorization_snapshot import (
    PAYLOAD_DIGEST_SCHEME,
    AuthorizationSnapshot,
)
from voodoo_product.config import ProductConfig
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import (
    ApprovalEvidenceSet,
    ApprovalRecord,
    ExecutionTarget,
)
from voodoo_product.monotonic_authority import AuthorityConstraint, AuthorityScope
from voodoo_product.precondition_witness import (
    READ_THEN_COMPARE,
    ImmutablePreconditionRequirementRegistry,
    PreconditionExpectationBinderRegistry,
    PreconditionGuard,
    PreconditionObserverRegistry,
    PreconditionRequirement,
)
from voodoo_product.service import ProductService
from voodoo_product.trusted_clock import TrustedClockAuthority

REVIEW_DIGEST = "1" * 64
CAPABILITY_DEFINITION_IDENTITY = "2" * 64
POLICY_IDENTITY = "3" * 64
AUTHORITY_WITNESS_SET_DIGEST = "4" * 64
CAPSULE_DIGEST = "5" * 64
AUTHORIZED_AT = "2026-08-17T00:00:00.000+00:00"
VALID_UNTIL = "2026-08-17T00:10:00.000+00:00"


def _payload_digest(payload: dict[str, object]) -> str:
    binding = {
        "schema_version": 1,
        "binding_type": PAYLOAD_DIGEST_SCHEME,
        "payload": payload,
    }
    return hashlib.sha256(canonical_json(binding).encode("utf-8")).hexdigest()


def snapshot() -> AuthorizationSnapshot:
    payload = {"ref": "refs/heads/main", "revision": "a" * 40}
    target = ExecutionTarget.create(
        target_kind="git_ref",
        target_claims=payload,
    )
    approvals = ApprovalEvidenceSet.create(
        request_id="cr_grant_v2",
        payload_digest=_payload_digest(payload),
        target_digest=target.target_digest,
        capability="voodoo.write-artifact/v1",
        policy_version="approval-policy/current-v1",
        approvals=(
            ApprovalRecord(
                approval_id="appr_grant_v2",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at="2026-08-16T23:59:00.000+00:00",
            ),
        ),
        approval_valid_until=VALID_UNTIL,
    )
    return AuthorizationSnapshot.create(
        snapshot_id="authz_grant_v2",
        execution_id="exec_grant_v2",
        request_id="cr_grant_v2",
        review_content_sha256=REVIEW_DIGEST,
        actor_id="usr_operator",
        workspace_id="wrk_main",
        environment="local",
        capability=approvals.capability,
        capability_definition_identity=CAPABILITY_DEFINITION_IDENTITY,
        payload_digest=approvals.payload_digest,
        payload_digest_scheme=PAYLOAD_DIGEST_SCHEME,
        execution_target_identity=target.target_digest,
        policy_version=approvals.policy_version,
        policy_identity=POLICY_IDENTITY,
        approval_evidence_identity=approvals.approval_set_digest,
        issuance_timestamp_source_identity="clock_test",
        authorized_at=AUTHORIZED_AT,
        authorization_source_revision="snapshot-authority/r2",
        execution_target=target,
        approval_evidence=approvals,
    )


class SequenceClock:
    def __init__(self, values: list[datetime]) -> None:
        self.values = list(values)

    def read(self) -> datetime:
        if not self.values:
            raise RuntimeError("test clock exhausted")
        return self.values.pop(0)


class GitRefExpectationBinder:
    binder_id = "git-ref-expectation/v1"
    target_kind = "git_ref"
    state_schema = "git-ref-state/v1"

    def bind_expected(self, *, target: ExecutionTarget) -> dict[str, Any]:
        return {"revision": target.target_claims["revision"]}


class GitRefObserver:
    observer_id = "git-ref-observer/v1"
    target_kind = "git_ref"
    state_schema = "git-ref-state/v1"
    source_identity = "provider-read/git-ref/v1"

    def __init__(self, revision: str) -> None:
        self.revision = revision

    def observe(self, *, target: ExecutionTarget) -> dict[str, Any]:
        del target
        return {"revision": self.revision}


class EmergencyStopObserver(GitRefObserver):
    def __init__(self, *, service: ProductService, revision: str) -> None:
        super().__init__(revision)
        self.service = service

    def observe(self, *, target: ExecutionTarget) -> dict[str, Any]:
        observed = super().observe(target=target)
        self.service.operational_safety_service.set_emergency_stop(
            actor_id="usr_admin",
            active=True,
            reason="activated during precondition read",
        )
        return observed


class FixedRevocationAuthority:
    def __init__(self, epoch: int) -> None:
        self.epoch = epoch

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


class SequenceRevocationAuthority:
    def __init__(self, epochs: list[int]) -> None:
        self.epochs = list(epochs)

    def current_epoch(
        self,
        connection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int:
        del connection, workspace_id, environment, capability_definition_identity
        if not self.epochs:
            raise RuntimeError("test revocation authority exhausted")
        return self.epochs.pop(0)


class StaticExecutionBindingAuthority:
    def __init__(self, *, mismatch_environment: bool = False) -> None:
        self.mismatch_environment = mismatch_environment

    def resolve(
        self,
        *,
        capability_definition_identity: str,
        environment: str,
        target_kind: str,
    ) -> ExecutionBinding:
        return ExecutionBinding.create(
            capability_definition_identity=capability_definition_identity,
            environment="production" if self.mismatch_environment else environment,
            target_kind=target_kind,
            execution_capsule_digest=CAPSULE_DIGEST,
            runner_class="sandcloud.isolated-linux/v1",
            authority_revision="execution-binding/test-r1",
        )


def product(tmp_path: Path) -> ProductService:
    return ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        )
    )


def seed_authority_witness(
    service: ProductService,
    parent_snapshot: AuthorizationSnapshot,
    *,
    revocation_epoch: int = 7,
) -> None:
    with service.db.transaction() as connection:
        service.audit_ledger.append(
            connection,
            actor_id=parent_snapshot.actor_id,
            action="authorization_snapshot.authority_witness",
            target_type="authorization_snapshot",
            target_id=parent_snapshot.snapshot_id,
            payload={
                "correlation_id": "corr_grant_v2",
                "snapshot_digest": parent_snapshot.snapshot_digest,
                "authority_witness_set_digest": AUTHORITY_WITNESS_SET_DIGEST,
                "permission_decision_digest": "6" * 64,
                "capability_selection_digest": "7" * 64,
                "capability_selection_authority_revision": "selection/test-r1",
                "policy_identity": parent_snapshot.policy_identity,
                "capability_definition_identity": (
                    parent_snapshot.capability_definition_identity
                ),
                "capability_activation_digest": "8" * 64,
                "target_binding_digest": "9" * 64,
                "approval_certificate_digest": "a" * 64,
                "clock_witness_digest": "b" * 64,
                "revocation_epoch": revocation_epoch,
                "authorization_source_revision": (
                    parent_snapshot.authorization_source_revision
                ),
            },
        )


def guard_and_clock(
    *,
    observed_revision: str = "a" * 40,
    observer: GitRefObserver | None = None,
    precondition_at: datetime | None = None,
    issuance_at: datetime | None = None,
) -> tuple[PreconditionGuard, TrustedClockAuthority]:
    sequence = SequenceClock(
        [
            precondition_at
            or datetime(2026, 8, 17, 0, 1, 0, tzinfo=UTC),
            issuance_at
            or datetime(2026, 8, 17, 0, 1, 1, tzinfo=UTC),
        ]
    )
    trusted_clock = TrustedClockAuthority(
        source_identity="clock_test",
        authority_revision="clock/test-r1",
        source=sequence,
    )
    requirement = PreconditionRequirement.create(
        capability_definition_identity=CAPABILITY_DEFINITION_IDENTITY,
        target_kind="git_ref",
        expectation_binder_id=GitRefExpectationBinder.binder_id,
        observer_id=GitRefObserver.observer_id,
        state_schema=GitRefObserver.state_schema,
        requirement_revision="precondition/test-r1",
        enforcement_class=READ_THEN_COMPARE,
    )
    resolved_observer = observer or GitRefObserver(observed_revision)
    guard = PreconditionGuard(
        requirements=ImmutablePreconditionRequirementRegistry((requirement,)),
        expectation_binders=PreconditionExpectationBinderRegistry(
            {GitRefExpectationBinder.binder_id: GitRefExpectationBinder()}
        ),
        observers=PreconditionObserverRegistry(
            {GitRefObserver.observer_id: resolved_observer}
        ),
        trusted_clock=trusted_clock,
    )
    return guard, trusted_clock


def issuer(
    service: ProductService,
    *,
    revocation_epoch: int = 7,
    revocation_authority: Any | None = None,
    observed_revision: str = "a" * 40,
    observer: GitRefObserver | None = None,
    mismatch_binding: bool = False,
    precondition_at: datetime | None = None,
    issuance_at: datetime | None = None,
    grant_ttl_seconds: int = 60,
) -> AuthoritativeGrantIssuer:
    guard, clock = guard_and_clock(
        observed_revision=observed_revision,
        observer=observer,
        precondition_at=precondition_at,
        issuance_at=issuance_at,
    )
    return AuthoritativeGrantIssuer(
        database=service.db,
        operational_safety_service=service.operational_safety_service,
        revocation_authority=(
            revocation_authority or FixedRevocationAuthority(revocation_epoch)
        ),
        precondition_guard=guard,
        execution_binding_authority=StaticExecutionBindingAuthority(
            mismatch_environment=mismatch_binding
        ),
        trusted_clock=clock,
        issuer_identity="v-one.authoritative-grant-issuer",
        issuer_revision="authoritative-grant-issuer/r1",
        grant_ttl_seconds=grant_ttl_seconds,
        id_factory=lambda prefix: f"{prefix}_grant_v2",
    )


def authority(parent_snapshot: AuthorizationSnapshot, **changes: Any) -> AuthorityConstraint:
    scope = AuthorityScope.from_snapshot(parent_snapshot)
    values = {
        "parent_scope_digest": scope.scope_digest,
        "actor_id": scope.actor_id,
        "workspace_id": scope.workspace_id,
        "environment": scope.environment,
        "capability": scope.capability,
        "capability_definition_identity": scope.capability_definition_identity,
        "target_kind": scope.target_kind,
        "target_digest": scope.target_digest,
        "payload_digest": scope.payload_digest,
        "policy_version": scope.policy_version,
        "policy_identity": scope.policy_identity,
        "approval_set_digest": scope.approval_set_digest,
        "required_permission": scope.required_permission,
        "valid_from": scope.valid_from,
        "valid_until": scope.valid_until,
    }
    values.update(changes)
    return AuthorityConstraint.create(**values)


def test_issuer_derives_authoritative_grant_v2_from_phase_a_chain(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)

    grant = issuer(service).issue(
        snapshot=parent_snapshot,
        authority=authority(parent_snapshot),
    )

    parent_scope = AuthorityScope.from_snapshot(parent_snapshot)
    assert grant.to_dict()["schema_version"] == 2
    assert grant.to_dict()["grant_type"] == EXECUTION_GRANT_V2_TYPE
    assert grant.authorization_snapshot_digest == parent_snapshot.snapshot_digest
    assert grant.snapshot_authority_witness_set_digest == AUTHORITY_WITNESS_SET_DIGEST
    assert grant.parent_scope_digest == parent_scope.scope_digest
    assert grant.authority_constraint_digest == authority(
        parent_snapshot
    ).constraint_digest
    assert grant.execution_capsule_digest == CAPSULE_DIGEST
    assert grant.runner_class == "sandcloud.isolated-linux/v1"
    assert grant.revocation_epoch == 7
    assert grant.use_semantics == "ONE_TIME"
    assert grant.required_permission == "execution.run"
    assert grant.precondition_enforcement_class == READ_THEN_COMPARE
    assert ExecutionGrantV2.from_dict(grant.to_dict()) == grant


def test_live_revocation_epoch_change_denies_issuance(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot, revocation_epoch=7)

    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(service, revocation_epoch=8).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )

    assert exc_info.value.reason_code == "REVOCATION_EPOCH_CHANGED"


def test_revocation_change_during_precondition_window_denies_issuance(
    tmp_path: Path,
) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot, revocation_epoch=7)

    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(
            service,
            revocation_authority=SequenceRevocationAuthority([7, 8]),
        ).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )

    assert exc_info.value.reason_code == "REVOCATION_EPOCH_CHANGED"


def test_missing_or_duplicate_snapshot_authority_evidence_denies(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()

    with pytest.raises(GrantIssuanceDenied) as missing:
        issuer(service).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )
    assert missing.value.reason_code == "SNAPSHOT_AUTHORITY_EVIDENCE_AMBIGUOUS"

    seed_authority_witness(service, parent_snapshot)
    seed_authority_witness(service, parent_snapshot)
    with pytest.raises(GrantIssuanceDenied) as duplicate:
        issuer(service).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )
    assert duplicate.value.reason_code == "SNAPSHOT_AUTHORITY_EVIDENCE_AMBIGUOUS"


def test_emergency_stop_is_live_deny_at_grant_issuance(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)
    service.operational_safety_service.set_emergency_stop(
        actor_id="usr_admin",
        active=True,
        reason="test",
    )

    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(service).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )

    assert exc_info.value.reason_code == "EMERGENCY_STOP_ACTIVE"


def test_emergency_stop_activated_during_precondition_denies_issuance(
    tmp_path: Path,
) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)

    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(
            service,
            observer=EmergencyStopObserver(
                service=service,
                revision="a" * 40,
            ),
        ).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )

    assert exc_info.value.reason_code == "EMERGENCY_STOP_ACTIVE"


def test_monotonic_widening_denies_before_grant(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)

    widened = authority(parent_snapshot, environment="production")
    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(service).issue(snapshot=parent_snapshot, authority=widened)

    assert exc_info.value.reason_code == "MONOTONIC_AUTHORITY_DENIED"


def test_changed_precondition_denies_and_no_grant_is_emitted(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)

    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(service, observed_revision="b" * 40).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )

    assert exc_info.value.reason_code == "PRECONDITION_DENIED"


def test_execution_binding_mismatch_is_fail_closed(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)

    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(service, mismatch_binding=True).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )

    assert exc_info.value.reason_code == "EXECUTION_BINDING_MISMATCH"


def test_precondition_to_grant_gap_is_bounded(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)

    with pytest.raises(GrantIssuanceDenied) as exc_info:
        issuer(
            service,
            precondition_at=datetime(2026, 8, 17, 0, 1, 0, tzinfo=UTC),
            issuance_at=datetime(2026, 8, 17, 0, 1, 31, tzinfo=UTC),
        ).issue(
            snapshot=parent_snapshot,
            authority=authority(parent_snapshot),
        )

    assert exc_info.value.reason_code == "PRECONDITION_WITNESS_STALE"


def test_grant_expiry_is_clamped_to_narrowed_authority(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)
    narrowed = authority(
        parent_snapshot,
        valid_until="2026-08-17T00:01:30.000+00:00",
    )

    grant = issuer(service, grant_ttl_seconds=60).issue(
        snapshot=parent_snapshot,
        authority=narrowed,
    )

    assert grant.issued_at == "2026-08-17T00:01:01.000+00:00"
    assert grant.expires_at == "2026-08-17T00:01:30.000+00:00"


def test_tampered_grant_digest_or_unknown_field_is_rejected(tmp_path: Path) -> None:
    service = product(tmp_path)
    parent_snapshot = snapshot()
    seed_authority_witness(service, parent_snapshot)
    value = issuer(service).issue(
        snapshot=parent_snapshot,
        authority=authority(parent_snapshot),
    ).to_dict()

    tampered = dict(value)
    tampered["grant_digest"] = "f" * 64
    with pytest.raises(ValueError, match="grant_digest"):
        ExecutionGrantV2.from_dict(tampered)

    unknown = dict(value)
    unknown["caller_override"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        ExecutionGrantV2.from_dict(unknown)


def test_legacy_execution_grant_v1_is_frozen_and_b1_is_not_runtime_wired() -> None:
    contract_source = Path("voodoo_product/execution_contract.py").read_text(
        encoding="utf-8"
    )
    service_source = Path("voodoo_product/service.py").read_text(encoding="utf-8")
    execution_source = Path("voodoo_product/execution.py").read_text(encoding="utf-8")

    assert 'EXECUTION_GRANT_TYPE = "execution-grant/v1"' in contract_source
    assert "ExecutionGrantV2" not in contract_source
    assert "AuthoritativeGrantIssuer" not in service_source
    assert "AuthoritativeGrantIssuer" not in execution_source
