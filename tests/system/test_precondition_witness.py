from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from voodoo_product.authorization_snapshot import PAYLOAD_DIGEST_SCHEME, AuthorizationSnapshot
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_contract import ApprovalEvidenceSet, ApprovalRecord, ExecutionTarget
from voodoo_product.monotonic_authority import (
    AuthorityConstraint,
    AuthorityScope,
    MonotonicAuthorityChecker,
    MonotonicAuthorityDecision,
)
from voodoo_product.precondition_witness import (
    ATOMIC_PROVIDER_CONDITION,
    EXACT_STATE_DIGEST,
    MATCH,
    READ_THEN_COMPARE,
    ImmutablePreconditionRequirementRegistry,
    PreconditionExpectation,
    PreconditionExpectationBinderRegistry,
    PreconditionGuard,
    PreconditionObservation,
    PreconditionObserverRegistry,
    PreconditionRequirement,
    PreconditionViolation,
    PreconditionWitness,
)
from voodoo_product.trusted_clock import ClockWitness, TrustedClockAuthority

CAPABILITY_DEFINITION_IDENTITY = "2" * 64
POLICY_IDENTITY = "3" * 64
REVIEW_DIGEST = "4" * 64
AUTHORIZED_AT = "2026-08-17T00:00:00.000+00:00"
VALID_UNTIL = "2026-08-17T00:10:00.000+00:00"
CHECKED_AT = datetime(2026, 8, 17, 0, 1, tzinfo=UTC)


def _payload_digest(payload: dict[str, object]) -> str:
    binding = {
        "schema_version": 1,
        "binding_type": PAYLOAD_DIGEST_SCHEME,
        "payload": payload,
    }
    return hashlib.sha256(canonical_json(binding).encode("utf-8")).hexdigest()


def snapshot() -> AuthorizationSnapshot:
    payload = {"resource": "repo/pr/89", "expected_revision": "head-abc"}
    target = ExecutionTarget.create(
        target_kind="github_pull_request",
        target_claims=payload,
    )
    approvals = ApprovalEvidenceSet.create(
        request_id="cr_precondition",
        payload_digest=_payload_digest(payload),
        target_digest=target.target_digest,
        capability="github.pull-request.merge/v1",
        policy_version="approval-policy/current-v1",
        approvals=(
            ApprovalRecord(
                approval_id="appr_precondition",
                approver_id="usr_reviewer",
                decision="APPROVED",
                approved_at="2026-08-16T23:59:00.000+00:00",
            ),
        ),
        approval_valid_until=VALID_UNTIL,
    )
    return AuthorizationSnapshot.create(
        snapshot_id="authz_precondition",
        execution_id="exec_precondition",
        request_id="cr_precondition",
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
        issuance_timestamp_source_identity="clock_authorization",
        authorized_at=AUTHORIZED_AT,
        authorization_source_revision="snapshot-authority/r2",
        execution_target=target,
        approval_evidence=approvals,
    )


def authority_chain() -> tuple[
    AuthorizationSnapshot,
    AuthorityScope,
    AuthorityConstraint,
    MonotonicAuthorityDecision,
]:
    parent_snapshot = snapshot()
    scope = AuthorityScope.from_snapshot(parent_snapshot)
    authority = AuthorityConstraint.from_scope(
        scope,
        valid_from="2026-08-17T00:00:30.000+00:00",
        valid_until="2026-08-17T00:05:00.000+00:00",
    )
    decision = MonotonicAuthorityChecker.check(parent=scope, child=authority)
    return parent_snapshot, scope, authority, decision


class ExpectedRevisionBinder:
    binder_id = "github-pr-revision-from-target/v1"
    target_kind = "github_pull_request"
    state_schema = "github.pull-request.revision-state/v1"

    def bind_expected(self, *, target: ExecutionTarget) -> dict[str, Any]:
        claims = target.target_claims
        return {
            "resource": claims["resource"],
            "revision": claims["expected_revision"],
        }


class FixedObserver:
    observer_id = "github-pr-authoritative-read/v1"
    target_kind = "github_pull_request"
    state_schema = "github.pull-request.revision-state/v1"
    source_identity = "github-api-read/test"

    def __init__(self, *, revision: str = "head-abc", denied: bool = False) -> None:
        self.revision = revision
        self.denied = denied

    def observe(self, *, target: ExecutionTarget) -> dict[str, Any]:
        if self.denied:
            raise PermissionError("provider read denied")
        return {
            "resource": target.target_claims["resource"],
            "revision": self.revision,
        }


class WrongSchemaBinder(ExpectedRevisionBinder):
    state_schema = "github.pull-request.wrong-state/v1"


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def read(self) -> datetime:
        return self.value


def requirement(
    *,
    enforcement_class: str = READ_THEN_COMPARE,
) -> PreconditionRequirement:
    return PreconditionRequirement.create(
        capability_definition_identity=CAPABILITY_DEFINITION_IDENTITY,
        target_kind="github_pull_request",
        expectation_binder_id=ExpectedRevisionBinder.binder_id,
        observer_id=FixedObserver.observer_id,
        state_schema=ExpectedRevisionBinder.state_schema,
        comparison_mode=EXACT_STATE_DIGEST,
        enforcement_class=enforcement_class,
        requirement_revision="precondition-requirement/test-r1",
    )


def guard(
    *,
    observer: FixedObserver | None = None,
    clock_value: datetime = CHECKED_AT,
    binder: ExpectedRevisionBinder | None = None,
    resolved_requirement: PreconditionRequirement | None = None,
) -> PreconditionGuard:
    selected_binder = binder or ExpectedRevisionBinder()
    selected_observer = observer or FixedObserver()
    return PreconditionGuard(
        requirements=ImmutablePreconditionRequirementRegistry(
            (resolved_requirement or requirement(),)
        ),
        expectation_binders=PreconditionExpectationBinderRegistry(
            {selected_binder.binder_id: selected_binder}
        ),
        observers=PreconditionObserverRegistry(
            {selected_observer.observer_id: selected_observer}
        ),
        trusted_clock=TrustedClockAuthority(
            source_identity="clock_precondition",
            authority_revision="clock/precondition-test-r1",
            source=FixedClock(clock_value),
        ),
    )


def test_matching_authoritative_prestate_emits_content_addressed_witness() -> None:
    parent_snapshot, scope, authority, decision = authority_chain()

    witness = guard().witness(
        parent=scope,
        authority=authority,
        monotonic_decision=decision,
        target=parent_snapshot.execution_target,
    )

    assert witness.parent_scope_digest == scope.scope_digest
    assert witness.authority_constraint_digest == authority.constraint_digest
    assert witness.monotonic_authority_decision_digest == decision.decision_digest
    assert witness.target_digest == authority.target_digest
    assert witness.expected_state_digest == witness.observed_state_digest
    assert witness.relation == MATCH
    assert witness.enforcement_class == READ_THEN_COMPARE
    assert witness.checked_at == "2026-08-17T00:01:00.000+00:00"
    assert PreconditionWitness.from_dict(witness.to_dict()) == witness


def test_changed_authoritative_prestate_fails_closed() -> None:
    parent_snapshot, scope, authority, decision = authority_chain()

    with pytest.raises(PreconditionViolation) as exc_info:
        guard(observer=FixedObserver(revision="head-changed")).witness(
            parent=scope,
            authority=authority,
            monotonic_decision=decision,
            target=parent_snapshot.execution_target,
        )

    assert "PRECONDITION_CHANGED" in exc_info.value.reason_codes


def test_monotonic_decision_must_bind_the_same_child_authority() -> None:
    parent_snapshot, scope, authority, _ = authority_chain()
    other_authority = AuthorityConstraint.from_scope(
        scope,
        valid_from="2026-08-17T00:00:30.000+00:00",
        valid_until="2026-08-17T00:04:00.000+00:00",
    )
    wrong_decision = MonotonicAuthorityChecker.check(
        parent=scope,
        child=other_authority,
    )

    with pytest.raises(PreconditionViolation) as exc_info:
        guard().witness(
            parent=scope,
            authority=authority,
            monotonic_decision=wrong_decision,
            target=parent_snapshot.execution_target,
        )

    assert "MONOTONIC_AUTHORITY_DECISION_MISMATCH" in exc_info.value.reason_codes


def test_scope_target_mismatch_is_denied_before_provider_read() -> None:
    _, scope, authority, decision = authority_chain()
    different_target = ExecutionTarget.create(
        target_kind="github_pull_request",
        target_claims={
            "resource": "repo/pr/90",
            "expected_revision": "head-abc",
        },
    )
    observer = FixedObserver(denied=True)

    with pytest.raises(PreconditionViolation) as exc_info:
        guard(observer=observer).witness(
            parent=scope,
            authority=authority,
            monotonic_decision=decision,
            target=different_target,
        )

    assert "TARGET_DIGEST_SCOPE_MISMATCH" in exc_info.value.reason_codes


def test_missing_requirement_fails_closed() -> None:
    parent_snapshot, scope, authority, decision = authority_chain()
    other_requirement = PreconditionRequirement.create(
        capability_definition_identity="9" * 64,
        target_kind="github_pull_request",
        expectation_binder_id=ExpectedRevisionBinder.binder_id,
        observer_id=FixedObserver.observer_id,
        state_schema=ExpectedRevisionBinder.state_schema,
        comparison_mode=EXACT_STATE_DIGEST,
        enforcement_class=READ_THEN_COMPARE,
        requirement_revision="precondition-requirement/other-r1",
    )
    guarded = PreconditionGuard(
        requirements=ImmutablePreconditionRequirementRegistry((other_requirement,)),
        expectation_binders=PreconditionExpectationBinderRegistry(
            {ExpectedRevisionBinder.binder_id: ExpectedRevisionBinder()}
        ),
        observers=PreconditionObserverRegistry(
            {FixedObserver.observer_id: FixedObserver()}
        ),
        trusted_clock=TrustedClockAuthority(
            source_identity="clock_precondition",
            authority_revision="clock/precondition-test-r1",
            source=FixedClock(CHECKED_AT),
        ),
    )

    with pytest.raises(PreconditionViolation) as exc_info:
        guarded.witness(
            parent=scope,
            authority=authority,
            monotonic_decision=decision,
            target=parent_snapshot.execution_target,
        )

    assert "PRECONDITION_REQUIREMENT_NOT_FOUND" in exc_info.value.reason_codes


def test_binder_metadata_mismatch_fails_closed() -> None:
    parent_snapshot, scope, authority, decision = authority_chain()

    with pytest.raises(PreconditionViolation) as exc_info:
        guard(binder=WrongSchemaBinder()).witness(
            parent=scope,
            authority=authority,
            monotonic_decision=decision,
            target=parent_snapshot.execution_target,
        )

    assert "EXPECTATION_BINDER_STATE_SCHEMA_MISMATCH" in exc_info.value.reason_codes


def test_provider_read_failure_is_bounded_denial() -> None:
    parent_snapshot, scope, authority, decision = authority_chain()

    with pytest.raises(PreconditionViolation) as exc_info:
        guard(observer=FixedObserver(denied=True)).witness(
            parent=scope,
            authority=authority,
            monotonic_decision=decision,
            target=parent_snapshot.execution_target,
        )

    assert exc_info.value.reason_codes == ("PRECONDITION_OBSERVER_DENIED",)


@pytest.mark.parametrize(
    ("clock_value", "reason_code"),
    [
        (
            datetime(2026, 8, 17, 0, 0, 29, 999000, tzinfo=UTC),
            "PRECONDITION_CHECK_BEFORE_AUTHORITY",
        ),
        (
            datetime(2026, 8, 17, 0, 5, tzinfo=UTC),
            "PRECONDITION_CHECK_AFTER_AUTHORITY_EXPIRY",
        ),
    ],
)
def test_precondition_check_must_be_inside_child_authority_window(
    clock_value: datetime,
    reason_code: str,
) -> None:
    parent_snapshot, scope, authority, decision = authority_chain()

    with pytest.raises(PreconditionViolation) as exc_info:
        guard(clock_value=clock_value).witness(
            parent=scope,
            authority=authority,
            monotonic_decision=decision,
            target=parent_snapshot.execution_target,
        )

    assert reason_code in exc_info.value.reason_codes


def test_atomic_enforcement_requirement_is_preserved_in_witness() -> None:
    parent_snapshot, scope, authority, decision = authority_chain()
    atomic_requirement = requirement(enforcement_class=ATOMIC_PROVIDER_CONDITION)

    witness = guard(resolved_requirement=atomic_requirement).witness(
        parent=scope,
        authority=authority,
        monotonic_decision=decision,
        target=parent_snapshot.execution_target,
    )

    assert witness.enforcement_class == ATOMIC_PROVIDER_CONDITION


def test_expectation_and_observation_are_canonical_and_round_trip() -> None:
    _, scope, authority, _ = authority_chain()
    req = requirement()
    clock_witness = ClockWitness.create(
        source_identity="clock_precondition",
        authority_revision="clock/precondition-test-r1",
        environment="local",
        observed_at=CHECKED_AT,
    )
    expectation = PreconditionExpectation.create(
        parent_scope_digest=scope.scope_digest,
        authority_constraint_digest=authority.constraint_digest,
        requirement_digest=req.requirement_digest,
        target_kind=scope.target_kind,
        target_digest=scope.target_digest,
        state_schema=req.state_schema,
        expected_state={"revision": "head-abc", "resource": "repo/pr/89"},
    )
    observation = PreconditionObservation.create(
        requirement_digest=req.requirement_digest,
        target_kind=scope.target_kind,
        target_digest=scope.target_digest,
        state_schema=req.state_schema,
        observer_id=req.observer_id,
        source_identity="github-api-read/test",
        clock_witness=clock_witness,
        observed_state={"resource": "repo/pr/89", "revision": "head-abc"},
    )

    assert PreconditionExpectation.from_dict(expectation.to_dict()) == expectation
    assert PreconditionObservation.from_dict(observation.to_dict()) == observation
    assert expectation.expected_state_digest == observation.observed_state_digest


def _direct_contracts() -> tuple[PreconditionExpectation, PreconditionObservation]:
    _, scope, authority, _ = authority_chain()
    req = requirement()
    clock_witness = ClockWitness.create(
        source_identity="clock_precondition",
        authority_revision="clock/precondition-test-r1",
        environment="local",
        observed_at=CHECKED_AT,
    )
    expectation = PreconditionExpectation.create(
        parent_scope_digest=scope.scope_digest,
        authority_constraint_digest=authority.constraint_digest,
        requirement_digest=req.requirement_digest,
        target_kind=scope.target_kind,
        target_digest=scope.target_digest,
        state_schema=req.state_schema,
        expected_state={"resource": "repo/pr/89", "revision": "head-abc"},
    )
    observation = PreconditionObservation.create(
        requirement_digest=req.requirement_digest,
        target_kind=scope.target_kind,
        target_digest=scope.target_digest,
        state_schema=req.state_schema,
        observer_id=req.observer_id,
        source_identity="github-api-read/test",
        clock_witness=clock_witness,
        observed_state={"resource": "repo/pr/89", "revision": "head-abc"},
    )
    return expectation, observation


@pytest.mark.parametrize(
    ("factory", "parser", "digest_field"),
    [
        (lambda: requirement().to_dict(), PreconditionRequirement.from_dict, "requirement_digest"),
        (
            lambda: _direct_contracts()[0].to_dict(),
            PreconditionExpectation.from_dict,
            "expectation_digest",
        ),
        (
            lambda: _direct_contracts()[1].to_dict(),
            PreconditionObservation.from_dict,
            "observation_digest",
        ),
    ],
)
def test_tampered_contract_digests_are_rejected(
    factory: Any,
    parser: Any,
    digest_field: str,
) -> None:
    value = factory()
    value[digest_field] = "f" * 64
    with pytest.raises(ValueError, match="does not match"):
        parser(value)


def test_contract_parsers_reject_unknown_fields() -> None:
    requirement_value = requirement().to_dict()
    requirement_value["unknown"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        PreconditionRequirement.from_dict(requirement_value)

    parent_snapshot, scope, authority, decision = authority_chain()
    witness = guard().witness(
        parent=scope,
        authority=authority,
        monotonic_decision=decision,
        target=parent_snapshot.execution_target,
    )
    witness_value = witness.to_dict()
    witness_value["unknown"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        PreconditionWitness.from_dict(witness_value)


def test_a10_is_not_runtime_wired() -> None:
    service_source = Path("voodoo_product/service.py").read_text(encoding="utf-8")
    execution_source = Path("voodoo_product/execution.py").read_text(encoding="utf-8")

    assert "PreconditionGuard" not in service_source
    assert "PreconditionWitness" not in service_source
    assert "PreconditionGuard" not in execution_source
    assert "PreconditionWitness" not in execution_source
