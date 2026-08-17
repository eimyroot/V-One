from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from voodoo_product.dispatch_inbox import DispatchInboxAdmission
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.execution_lease import (
    FENCE_CURRENT,
    MAX_LEASE_SECONDS,
    ExecutionFenceDenied,
    ExecutionLease,
    assert_next_execution_epoch,
)
from voodoo_product.trusted_clock import ClockWitness


def digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_admission(
    *,
    admission_id: str | None = None,
    dispatch_id: str = "1" * 64,
    execution_id: str = "exec_c4",
    environment: str = "local",
) -> DispatchInboxAdmission:
    claims: dict[str, object] = {
        "schema_version": 1,
        "admission_type": "dispatch-inbox-admission/v1",
        "admission_id": admission_id or "2" * 64,
        "dispatch_id": dispatch_id,
        "envelope_digest": "3" * 64,
        "outbox_id": "out_c4",
        "outbox_entry_digest": "4" * 64,
        "execution_id": execution_id,
        "workspace_id": "wrk_main",
        "environment": environment,
        "execution_capsule_digest": "5" * 64,
        "runner_class": "sandcloud.isolated-linux/v1",
        "admission_revision": "dispatch-inbox/c3-r1",
    }
    # Admission identity is normally derived by C3. For this focused C4 test, build through the
    # strict parser only after reproducing the exact identity-domain digest.
    claims["admission_id"] = digest(
        {
            "identity_type": "dispatch-inbox-admission-id/v1",
            "dispatch_id": claims["dispatch_id"],
            "envelope_digest": claims["envelope_digest"],
            "outbox_entry_digest": claims["outbox_entry_digest"],
        }
    )
    claims["admission_digest"] = digest(claims)
    return DispatchInboxAdmission.from_dict(claims)


def make_clock(
    observed_at: str,
    *,
    environment: str = "local",
) -> ClockWitness:
    return ClockWitness.create(
        source_identity="trusted-clock/test",
        authority_revision="trusted-clock/test-r1",
        environment=environment,
        observed_at=datetime.fromisoformat(observed_at).astimezone(UTC),
    )


def make_lease(
    *,
    admission: DispatchInboxAdmission | None = None,
    epoch: int = 1,
    observed_at: str = "2026-08-17T05:30:00.000+00:00",
    lease_seconds: int = 60,
    revision: str = "execution-lease/c4-r1",
) -> ExecutionLease:
    resolved_admission = admission or make_admission()
    return ExecutionLease.create_candidate(
        admission=resolved_admission,
        execution_epoch=epoch,
        clock_witness=make_clock(
            observed_at,
            environment=resolved_admission.environment,
        ),
        lease_seconds=lease_seconds,
        lease_revision=revision,
    )


def claims_without_digest(raw: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in raw.items() if key != "lease_digest"}


def test_execution_lease_binds_exact_c3_admission_and_round_trips() -> None:
    admission = make_admission()
    clock = make_clock("2026-08-17T05:30:00.000+00:00")

    lease = ExecutionLease.create_candidate(
        admission=admission,
        execution_epoch=1,
        clock_witness=clock,
        lease_seconds=60,
        lease_revision="execution-lease/c4-r1",
    )

    assert lease.dispatch_id == admission.dispatch_id
    assert lease.admission_id == admission.admission_id
    assert lease.admission_digest == admission.admission_digest
    assert lease.execution_id == admission.execution_id
    assert lease.workspace_id == admission.workspace_id
    assert lease.environment == admission.environment
    assert lease.execution_capsule_digest == admission.execution_capsule_digest
    assert lease.runner_class == admission.runner_class
    assert lease.execution_epoch == 1
    assert lease.acquired_at == "2026-08-17T05:30:00.000+00:00"
    assert lease.expires_at == "2026-08-17T05:31:00.000+00:00"
    assert lease.clock_witness_digest == clock.witness_digest
    lease.assert_bound_to(admission)
    assert ExecutionLease.from_dict(lease.to_dict()) == lease


def test_execution_epoch_transition_is_strictly_monotonic_without_gaps() -> None:
    assert_next_execution_epoch(previous_epoch=None, candidate_epoch=1)
    assert_next_execution_epoch(previous_epoch=1, candidate_epoch=2)
    assert_next_execution_epoch(previous_epoch=8, candidate_epoch=9)

    for previous, candidate in ((None, 2), (1, 1), (2, 1), (2, 4)):
        with pytest.raises(ExecutionFenceDenied) as denied:
            assert_next_execution_epoch(
                previous_epoch=previous,
                candidate_epoch=candidate,
            )
        assert denied.value.reason == "EXECUTION_EPOCH_TRANSITION_INVALID"


def test_same_admission_and_epoch_keep_same_logical_lease_identity() -> None:
    admission = make_admission()
    first = make_lease(admission=admission, epoch=3)
    changed_revision = make_lease(
        admission=admission,
        epoch=3,
        revision="execution-lease/c4-r2",
    )

    assert first.lease_id == changed_revision.lease_id
    assert first.lease_digest != changed_revision.lease_digest


def test_candidate_lease_is_bounded_and_clock_environment_must_match() -> None:
    admission = make_admission()

    with pytest.raises(ValueError, match="between 1"):
        ExecutionLease.create_candidate(
            admission=admission,
            execution_epoch=1,
            clock_witness=make_clock("2026-08-17T05:30:00.000+00:00"),
            lease_seconds=0,
            lease_revision="execution-lease/c4-r1",
        )
    with pytest.raises(ValueError, match="between 1"):
        ExecutionLease.create_candidate(
            admission=admission,
            execution_epoch=1,
            clock_witness=make_clock("2026-08-17T05:30:00.000+00:00"),
            lease_seconds=MAX_LEASE_SECONDS + 1,
            lease_revision="execution-lease/c4-r1",
        )
    with pytest.raises(ExecutionFenceDenied) as denied:
        ExecutionLease.create_candidate(
            admission=admission,
            execution_epoch=1,
            clock_witness=make_clock(
                "2026-08-17T05:30:00.000+00:00",
                environment="staging",
            ),
            lease_seconds=60,
            lease_revision="execution-lease/c4-r1",
        )
    assert denied.value.reason == "CLOCK_ENVIRONMENT_MISMATCH"


def test_current_unexpired_epoch_passes_completion_fence() -> None:
    lease = make_lease(epoch=7, lease_seconds=60)

    assert (
        lease.assert_completion_fence(
            current_execution_epoch=7,
            clock_witness=make_clock("2026-08-17T05:30:59.999+00:00"),
        )
        == FENCE_CURRENT
    )


def test_superseded_epoch_is_stale_and_cannot_complete() -> None:
    lease = make_lease(epoch=7)

    with pytest.raises(ExecutionFenceDenied) as denied:
        lease.assert_completion_fence(
            current_execution_epoch=8,
            clock_witness=make_clock("2026-08-17T05:30:30.000+00:00"),
        )
    assert denied.value.reason == "STALE_EXECUTION_EPOCH"


def test_epoch_regression_fails_closed() -> None:
    lease = make_lease(epoch=7)

    with pytest.raises(ExecutionFenceDenied) as denied:
        lease.assert_completion_fence(
            current_execution_epoch=6,
            clock_witness=make_clock("2026-08-17T05:30:30.000+00:00"),
        )
    assert denied.value.reason == "EXECUTION_EPOCH_REGRESSION"


def test_expired_lease_cannot_complete_even_if_epoch_is_current() -> None:
    lease = make_lease(epoch=2, lease_seconds=60)

    with pytest.raises(ExecutionFenceDenied) as denied:
        lease.assert_completion_fence(
            current_execution_epoch=2,
            clock_witness=make_clock("2026-08-17T05:31:00.000+00:00"),
        )
    assert denied.value.reason == "LEASE_EXPIRED"


def test_completion_clock_before_acquire_or_wrong_environment_fails_closed() -> None:
    lease = make_lease(epoch=2)

    with pytest.raises(ExecutionFenceDenied) as before:
        lease.assert_completion_fence(
            current_execution_epoch=2,
            clock_witness=make_clock("2026-08-17T05:29:59.999+00:00"),
        )
    assert before.value.reason == "CLOCK_BEFORE_LEASE"

    with pytest.raises(ExecutionFenceDenied) as mismatch:
        lease.assert_completion_fence(
            current_execution_epoch=2,
            clock_witness=make_clock(
                "2026-08-17T05:30:30.000+00:00",
                environment="staging",
            ),
        )
    assert mismatch.value.reason == "CLOCK_ENVIRONMENT_MISMATCH"


def test_lease_rejects_admission_tamper_digest_tamper_and_unknown_fields() -> None:
    admission = make_admission()
    lease = make_lease(admission=admission)

    other = make_admission(execution_id="exec_other")
    with pytest.raises(ExecutionFenceDenied) as denied:
        lease.assert_bound_to(other)
    assert denied.value.reason == "LEASE_ADMISSION_BINDING_MISMATCH"

    tampered = lease.to_dict()
    tampered["runner_class"] = "unbounded-runner/v1"
    with pytest.raises(ValueError, match="lease_digest"):
        ExecutionLease.from_dict(tampered)

    self_consistent_identity_tamper = lease.to_dict()
    self_consistent_identity_tamper["lease_id"] = "0" * 64
    self_consistent_identity_tamper["lease_digest"] = digest(
        claims_without_digest(self_consistent_identity_tamper)
    )
    with pytest.raises(ValueError, match="lease_id"):
        ExecutionLease.from_dict(self_consistent_identity_tamper)

    unknown = lease.to_dict()
    unknown["runner_identity"] = "runner_not_allowed_in_c4"
    with pytest.raises(ValueError, match="fields are invalid"):
        ExecutionLease.from_dict(unknown)


def test_c4_contract_does_not_wire_lease_into_current_runtime() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "voodoo_product/service.py",
        "voodoo_product/execution.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "execution_lease" not in source
        assert "ExecutionLease" not in source
