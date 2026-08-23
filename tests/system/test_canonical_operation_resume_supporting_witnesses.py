from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from voodoo_product.canonical_operation_resume import (
    SELECT_CONSUMPTION_BY_ID,
    SELECT_LEASE_BY_ID,
    CanonicalOperationResumeDenied,
    CanonicalOperationResumeService,
)
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_conformance import ExecutionConformanceWitness
from voodoo_product.trusted_clock import CLOCK_WITNESS_TYPE


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _conformance_raw(
    *,
    grant_digest: str = "7" * 64,
    execution_binding_digest: str = "8" * 64,
    execution_capsule_digest: str = "a" * 64,
    capability_definition_identity: str = "2" * 64,
    target_kind: str = "git_ref",
    runner_class: str = "github-actions.runner/v1",
) -> dict[str, object]:
    claims: dict[str, object] = {
        "schema_version": 1,
        "witness_type": "execution-conformance-witness/v1",
        "grant_digest": grant_digest,
        "execution_binding_digest": execution_binding_digest,
        "execution_capsule_digest": execution_capsule_digest,
        "capability_definition_identity": capability_definition_identity,
        "capability_activation_digest": "b" * 64,
        "capsule_activation_digest": "c" * 64,
        "handler_conformance_evidence_digest": "d" * 64,
        "target_kind": target_kind,
        "runner_class": runner_class,
        "handler_id": "handler-test-r1",
        "handler_digest": "e" * 64,
        "credential_class": "READ_ONLY",
        "precondition_enforcement_class": "READ_THEN_COMPARE",
        "verification_contract_identity": "f" * 64,
        "atomic_provider_condition_contract_identity": None,
        "conformance_authority_revision": "conformance/test-r1",
    }
    return {**claims, "witness_digest": _digest(claims)}


def _clock_raw(
    *,
    environment: str = "staging",
    observed_at: str = "2026-08-23T08:00:00.000+00:00",
) -> dict[str, object]:
    claims: dict[str, object] = {
        "witness_type": CLOCK_WITNESS_TYPE,
        "source_identity": "clock-source/test-r1",
        "authority_revision": "clock/test-r1",
        "environment": environment,
        "observed_at": observed_at,
    }
    return {**claims, "witness_digest": _digest(claims)}


def _grant() -> object:
    return SimpleNamespace(
        grant_digest="7" * 64,
        execution_binding_digest="8" * 64,
        execution_capsule_digest="a" * 64,
        capability_definition_identity="2" * 64,
        target_kind="git_ref",
        runner_class="github-actions.runner/v1",
        environment="staging",
    )


def _consumption(*, conformance: object, clock: object) -> object:
    return SimpleNamespace(
        conformance_witness_digest=conformance.witness_digest,
        clock_witness_digest=clock.witness_digest,
        consumed_at="2026-08-23T08:00:00.000+00:00",
    )


def test_exact_supporting_witnesses_are_accepted() -> None:
    grant = _grant()
    conformance = ExecutionConformanceWitness.from_dict(_conformance_raw())
    clock = CanonicalOperationResumeService._decode_clock_witness(_clock_raw())
    consumption = _consumption(conformance=conformance, clock=clock)

    CanonicalOperationResumeService._validate_consumption_supporting_witnesses(
        grant=grant,
        consumption=consumption,
        conformance_witness=conformance,
        clock_witness=clock,
    )


def test_valid_foreign_conformance_witness_is_rejected() -> None:
    grant = _grant()
    conformance = ExecutionConformanceWitness.from_dict(
        _conformance_raw(grant_digest="6" * 64)
    )
    clock = CanonicalOperationResumeService._decode_clock_witness(_clock_raw())
    consumption = _consumption(conformance=conformance, clock=clock)

    with pytest.raises(
        CanonicalOperationResumeDenied,
        match="CONSUMPTION_SUPPORTING_WITNESS_MISMATCH",
    ):
        CanonicalOperationResumeService._validate_consumption_supporting_witnesses(
            grant=grant,
            consumption=consumption,
            conformance_witness=conformance,
            clock_witness=clock,
        )


def test_valid_foreign_clock_witness_is_rejected() -> None:
    grant = _grant()
    conformance = ExecutionConformanceWitness.from_dict(_conformance_raw())
    clock = CanonicalOperationResumeService._decode_clock_witness(
        _clock_raw(observed_at="2026-08-23T08:00:01.000+00:00")
    )
    consumption = _consumption(conformance=conformance, clock=clock)

    with pytest.raises(
        CanonicalOperationResumeDenied,
        match="CONSUMPTION_SUPPORTING_WITNESS_MISMATCH",
    ):
        CanonicalOperationResumeService._validate_consumption_supporting_witnesses(
            grant=grant,
            consumption=consumption,
            conformance_witness=conformance,
            clock_witness=clock,
        )


def test_exact_lease_clock_witness_is_accepted() -> None:
    clock = CanonicalOperationResumeService._decode_clock_witness(
        _clock_raw(observed_at="2026-08-23T08:10:00.000+00:00")
    )
    lease = SimpleNamespace(
        clock_witness_digest=clock.witness_digest,
        environment="staging",
        acquired_at=clock.observed_at,
    )

    CanonicalOperationResumeService._validate_lease_supporting_clock_witness(
        lease=lease,
        clock_witness=clock,
    )


def test_valid_foreign_lease_clock_witness_is_rejected() -> None:
    clock = CanonicalOperationResumeService._decode_clock_witness(
        _clock_raw(observed_at="2026-08-23T08:10:01.000+00:00")
    )
    lease = SimpleNamespace(
        clock_witness_digest=clock.witness_digest,
        environment="staging",
        acquired_at="2026-08-23T08:10:00.000+00:00",
    )

    with pytest.raises(
        CanonicalOperationResumeDenied,
        match="LEASE_CLOCK_WITNESS_MISMATCH",
    ):
        CanonicalOperationResumeService._validate_lease_supporting_clock_witness(
            lease=lease,
            clock_witness=clock,
        )


def test_clock_witness_content_digest_tampering_is_rejected() -> None:
    raw = _clock_raw()
    raw["witness_digest"] = "0" * 64

    with pytest.raises(ValueError, match="witness_digest does not match clock witness"):
        CanonicalOperationResumeService._decode_clock_witness(raw)


def test_conformance_witness_content_digest_tampering_is_rejected() -> None:
    raw = _conformance_raw()
    raw["witness_digest"] = "0" * 64

    with pytest.raises(
        ValueError,
        match="witness_digest does not match execution conformance witness",
    ):
        ExecutionConformanceWitness.from_dict(raw)


def test_resume_queries_load_supporting_json_read_only() -> None:
    assert SELECT_CONSUMPTION_BY_ID.mode == "read"
    assert "conformance_witness_json" in SELECT_CONSUMPTION_BY_ID.sqlite_sql
    assert "clock_witness_json" in SELECT_CONSUMPTION_BY_ID.sqlite_sql
    assert SELECT_LEASE_BY_ID.mode == "read"
    assert "clock_witness_json" in SELECT_LEASE_BY_ID.sqlite_sql
