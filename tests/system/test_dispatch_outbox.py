from __future__ import annotations

import hashlib

import pytest

from voodoo_product.authoritative_grant import ExecutionGrantV2
from voodoo_product.dispatch_outbox import DispatchOutboxEntry
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.grant_consumption import GrantConsumptionWitness
from voodoo_product.precondition_witness import READ_THEN_COMPARE


def digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_grant(
    *,
    grant_id: str = "grt_c1a",
    jti: str = "jti_c1a",
    execution_id: str = "exec_c1a",
    target_digest: str = "1" * 64,
) -> ExecutionGrantV2:
    return ExecutionGrantV2._issue(
        grant_id=grant_id,
        jti=jti,
        execution_id=execution_id,
        request_id="cr_c1a",
        authorization_snapshot_digest="a" * 64,
        snapshot_authority_witness_set_digest="b" * 64,
        snapshot_authority_event_hash="c" * 64,
        parent_scope_digest="d" * 64,
        authority_constraint_digest="e" * 64,
        monotonic_authority_decision_digest="f" * 64,
        actor_id="usr_admin",
        workspace_id="wrk_main",
        environment="local",
        capability="voodoo.write-artifact/v1",
        capability_definition_identity="0" * 64,
        target_kind="git_ref",
        target_digest=target_digest,
        payload_digest="2" * 64,
        policy_version="approval-policy/current-v1",
        policy_identity="3" * 64,
        approval_set_digest="4" * 64,
        required_permission="execution.run",
        precondition_requirement_digest="5" * 64,
        precondition_expectation_digest="6" * 64,
        precondition_observation_digest="7" * 64,
        precondition_witness_digest="8" * 64,
        precondition_enforcement_class=READ_THEN_COMPARE,
        precondition_checked_at="2026-08-17T02:00:00.000+00:00",
        execution_binding_digest="9" * 64,
        execution_capsule_digest="a" * 64,
        runner_class="sandcloud.isolated-linux/v1",
        execution_binding_authority_revision="execution-binding/test-r1",
        issued_at="2026-08-17T02:00:01.000+00:00",
        expires_at="2026-08-17T02:05:00.000+00:00",
        revocation_epoch=7,
        use_semantics="ONE_TIME",
        issuer_identity="grant-issuer/test",
        issuer_revision="grant-issuer/test-r1",
    )


def make_consumption(
    grant: ExecutionGrantV2,
    *,
    consumption_id: str = "gcon_c1a",
) -> GrantConsumptionWitness:
    claims: dict[str, object] = {
        "schema_version": 1,
        "witness_type": "grant-consumption-witness/v1",
        "consumption_id": consumption_id,
        "jti": grant.jti,
        "grant_id": grant.grant_id,
        "grant_digest": grant.grant_digest,
        "execution_id": grant.execution_id,
        "authorization_snapshot_digest": grant.authorization_snapshot_digest,
        "execution_capsule_digest": grant.execution_capsule_digest,
        "runner_class": grant.runner_class,
        "conformance_witness_digest": "b" * 64,
        "clock_witness_digest": "c" * 64,
        "live_revocation_epoch": grant.revocation_epoch,
        "consumed_at": "2026-08-17T02:00:02.000+00:00",
        "serialization_contract": "sqlite-begin-immediate/v1",
        "authority_revision": "durable-grant/test-r1",
    }
    return GrantConsumptionWitness(
        consumption_id=consumption_id,
        jti=grant.jti,
        grant_id=grant.grant_id,
        grant_digest=grant.grant_digest,
        execution_id=grant.execution_id,
        authorization_snapshot_digest=grant.authorization_snapshot_digest,
        execution_capsule_digest=grant.execution_capsule_digest,
        runner_class=grant.runner_class,
        conformance_witness_digest="b" * 64,
        clock_witness_digest="c" * 64,
        live_revocation_epoch=grant.revocation_epoch,
        consumed_at="2026-08-17T02:00:02.000+00:00",
        serialization_contract="sqlite-begin-immediate/v1",
        authority_revision="durable-grant/test-r1",
        witness_digest=digest(claims),
    )


def test_outbox_entry_is_exact_projection_of_consumed_grant() -> None:
    grant = make_grant()
    consumption = make_consumption(grant)

    entry = DispatchOutboxEntry.create(
        outbox_id="out_c1a",
        grant=grant,
        consumption_witness=consumption,
        outbox_revision="dispatch-outbox/c1a-r1",
    )

    assert entry.consumption_id == consumption.consumption_id
    assert entry.consumption_witness_digest == consumption.witness_digest
    assert entry.grant_digest == grant.grant_digest
    assert entry.execution_id == grant.execution_id
    assert entry.target_digest == grant.target_digest
    assert entry.payload_digest == grant.payload_digest
    assert entry.execution_capsule_digest == grant.execution_capsule_digest
    assert entry.runner_class == grant.runner_class
    assert entry.created_at == consumption.consumed_at
    assert DispatchOutboxEntry.from_dict(entry.to_dict()) == entry


def test_outbox_entry_rejects_consumption_for_another_grant() -> None:
    grant = make_grant()
    other = make_grant(
        grant_id="grt_other",
        jti="jti_other",
        execution_id="exec_other",
    )
    other_consumption = make_consumption(other, consumption_id="gcon_other")

    with pytest.raises(
        PermissionError,
        match="consumption witness does not bind",
    ):
        DispatchOutboxEntry.create(
            outbox_id="out_c1a",
            grant=grant,
            consumption_witness=other_consumption,
            outbox_revision="dispatch-outbox/c1a-r1",
        )


def test_outbox_entry_digest_changes_when_authorized_target_changes() -> None:
    first_grant = make_grant(target_digest="1" * 64)
    second_grant = make_grant(
        grant_id="grt_c1a_2",
        jti="jti_c1a_2",
        execution_id="exec_c1a_2",
        target_digest="d" * 64,
    )

    first = DispatchOutboxEntry.create(
        outbox_id="out_c1a_1",
        grant=first_grant,
        consumption_witness=make_consumption(first_grant),
        outbox_revision="dispatch-outbox/c1a-r1",
    )
    second = DispatchOutboxEntry.create(
        outbox_id="out_c1a_2",
        grant=second_grant,
        consumption_witness=make_consumption(
            second_grant,
            consumption_id="gcon_c1a_2",
        ),
        outbox_revision="dispatch-outbox/c1a-r1",
    )

    assert first.target_digest != second.target_digest
    assert first.entry_digest != second.entry_digest


def test_outbox_entry_rejects_tamper_and_unknown_fields() -> None:
    grant = make_grant()
    entry = DispatchOutboxEntry.create(
        outbox_id="out_c1a",
        grant=grant,
        consumption_witness=make_consumption(grant),
        outbox_revision="dispatch-outbox/c1a-r1",
    )

    tampered = entry.to_dict()
    tampered["runner_class"] = "unbounded-runner/v1"
    with pytest.raises(ValueError, match="entry_digest"):
        DispatchOutboxEntry.from_dict(tampered)

    unknown = entry.to_dict()
    unknown["dispatch_now"] = True
    with pytest.raises(ValueError, match="fields are invalid"):
        DispatchOutboxEntry.from_dict(unknown)


def test_outbox_entry_parser_does_not_accept_reusable_authority() -> None:
    grant = make_grant()
    entry = DispatchOutboxEntry.create(
        outbox_id="out_c1a",
        grant=grant,
        consumption_witness=make_consumption(grant),
        outbox_revision="dispatch-outbox/c1a-r1",
    )
    reusable = entry.to_dict()
    reusable["use_semantics"] = "REUSABLE"
    reusable_claims = {
        key: value
        for key, value in reusable.items()
        if key != "entry_digest"
    }
    reusable["entry_digest"] = digest(reusable_claims)

    with pytest.raises(ValueError, match="ONE_TIME"):
        DispatchOutboxEntry.from_dict(reusable)
