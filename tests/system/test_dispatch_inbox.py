from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from voodoo_product.dispatch_envelope import DispatchEnvelope
from voodoo_product.dispatch_inbox import (
    DUPLICATE_REDELIVERY,
    DispatchInboxAdmission,
    DispatchInboxContentConflict,
)
from voodoo_product.dispatch_outbox import DispatchOutboxEntry
from voodoo_product.evidence_primitives import canonical_json


def digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_outbox(
    *,
    outbox_id: str = "out_c3",
    consumption_id: str = "gcon_c3",
    jti: str = "jti_c3",
    grant_id: str = "grt_c3",
    execution_id: str = "exec_c3",
    target_digest: str = "1" * 64,
    payload_digest: str = "2" * 64,
    runner_class: str = "sandcloud.isolated-linux/v1",
) -> DispatchOutboxEntry:
    claims: dict[str, object] = {
        "schema_version": 1,
        "entry_type": "dispatch-outbox-entry/v1",
        "outbox_id": outbox_id,
        "consumption_id": consumption_id,
        "consumption_witness_digest": "a" * 64,
        "jti": jti,
        "grant_id": grant_id,
        "grant_digest": "b" * 64,
        "execution_id": execution_id,
        "request_id": "cr_c3",
        "actor_id": "usr_admin",
        "workspace_id": "wrk_main",
        "environment": "local",
        "capability": "voodoo.write-artifact/v1",
        "capability_definition_identity": "c" * 64,
        "authorization_snapshot_digest": "d" * 64,
        "target_kind": "git_ref",
        "target_digest": target_digest,
        "payload_digest": payload_digest,
        "required_permission": "execution.run",
        "execution_binding_digest": "e" * 64,
        "execution_capsule_digest": "f" * 64,
        "runner_class": runner_class,
        "precondition_enforcement_class": "READ_THEN_COMPARE",
        "use_semantics": "ONE_TIME",
        "created_at": "2026-08-17T04:30:00.000+00:00",
        "outbox_revision": "dispatch-outbox/c1b-r1",
    }
    claims["entry_digest"] = digest(claims)
    return DispatchOutboxEntry.from_dict(claims)


def make_envelope(
    outbox: DispatchOutboxEntry,
    *,
    revision: str = "dispatch-envelope/c2-r1",
) -> DispatchEnvelope:
    return DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision=revision,
    )


def admission_claims_without_digest(raw: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in raw.items() if key != "admission_digest"}


def test_inbox_admission_is_exact_projection_of_valid_envelope_and_outbox() -> None:
    outbox = make_outbox()
    envelope = make_envelope(outbox)

    admission = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    assert admission.dispatch_id == envelope.dispatch_id
    assert admission.envelope_digest == envelope.envelope_digest
    assert admission.outbox_id == outbox.outbox_id
    assert admission.outbox_entry_digest == outbox.entry_digest
    assert admission.execution_id == outbox.execution_id
    assert admission.execution_capsule_digest == outbox.execution_capsule_digest
    assert admission.runner_class == outbox.runner_class
    admission.assert_bound_to(envelope=envelope, outbox_entry=outbox)
    assert DispatchInboxAdmission.from_dict(admission.to_dict()) == admission


def test_admission_identity_is_deterministic_for_exact_content() -> None:
    outbox = make_outbox()
    envelope = make_envelope(outbox)

    first = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )
    repeated = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    assert repeated == first
    assert repeated.admission_id == first.admission_id


def test_admission_id_is_not_caller_supplied() -> None:
    parameters = inspect.signature(DispatchInboxAdmission.create).parameters

    assert "admission_id" not in parameters
    with pytest.raises(TypeError):
        DispatchInboxAdmission.create(  # type: ignore[call-arg]
            envelope=make_envelope(make_outbox()),
            outbox_entry=make_outbox(),
            admission_revision="dispatch-inbox/c3-r1",
            admission_id="0" * 64,
        )


def test_exact_redelivery_is_duplicate_not_second_admission() -> None:
    outbox = make_outbox()
    envelope = make_envelope(outbox)
    admission = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    assert (
        admission.classify_redelivery(envelope=envelope, outbox_entry=outbox)
        == DUPLICATE_REDELIVERY
    )


def test_same_dispatch_id_with_conflicting_envelope_content_fails_closed() -> None:
    outbox = make_outbox()
    accepted = make_envelope(outbox, revision="dispatch-envelope/c2-r1")
    conflicting = make_envelope(outbox, revision="dispatch-envelope/c2-r2")
    assert conflicting.dispatch_id == accepted.dispatch_id
    assert conflicting.envelope_digest != accepted.envelope_digest

    admission = DispatchInboxAdmission.create(
        envelope=accepted,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    with pytest.raises(DispatchInboxContentConflict) as denied:
        admission.classify_redelivery(
            envelope=conflicting,
            outbox_entry=outbox,
        )
    assert denied.value.reason == "DISPATCH_CONTENT_CONFLICT"


def test_different_logical_dispatch_is_not_classified_as_redelivery() -> None:
    first_outbox = make_outbox()
    first_envelope = make_envelope(first_outbox)
    admission = DispatchInboxAdmission.create(
        envelope=first_envelope,
        outbox_entry=first_outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    second_outbox = make_outbox(
        outbox_id="out_c3_other",
        consumption_id="gcon_c3_other",
        jti="jti_c3_other",
        grant_id="grt_c3_other",
        execution_id="exec_c3_other",
        target_digest="9" * 64,
    )
    second_envelope = make_envelope(second_outbox)

    with pytest.raises(ValueError, match="dispatch_id"):
        admission.classify_redelivery(
            envelope=second_envelope,
            outbox_entry=second_outbox,
        )


def test_structural_parser_does_not_prove_authoritative_content_binding() -> None:
    outbox = make_outbox()
    envelope = make_envelope(outbox)
    admission = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    self_consistent_tamper = admission.to_dict()
    self_consistent_tamper["runner_class"] = "unbounded-runner/v1"
    self_consistent_tamper["admission_digest"] = digest(
        admission_claims_without_digest(self_consistent_tamper)
    )
    structurally_valid = DispatchInboxAdmission.from_dict(self_consistent_tamper)

    with pytest.raises(PermissionError, match="does not bind"):
        structurally_valid.assert_bound_to(
            envelope=envelope,
            outbox_entry=outbox,
        )


def test_admission_rejects_identity_digest_tamper_and_unknown_fields() -> None:
    outbox = make_outbox()
    envelope = make_envelope(outbox)
    admission = DispatchInboxAdmission.create(
        envelope=envelope,
        outbox_entry=outbox,
        admission_revision="dispatch-inbox/c3-r1",
    )

    wrong_identity = admission.to_dict()
    wrong_identity["admission_id"] = "0" * 64
    wrong_identity["admission_digest"] = digest(
        admission_claims_without_digest(wrong_identity)
    )
    with pytest.raises(ValueError, match="admission_id"):
        DispatchInboxAdmission.from_dict(wrong_identity)

    tampered = admission.to_dict()
    tampered["runner_class"] = "unbounded-runner/v1"
    with pytest.raises(ValueError, match="admission_digest"):
        DispatchInboxAdmission.from_dict(tampered)

    unknown = admission.to_dict()
    unknown["lease_id"] = "lease_not_allowed"
    with pytest.raises(ValueError, match="fields are invalid"):
        DispatchInboxAdmission.from_dict(unknown)


def test_c3_contract_does_not_wire_inbox_into_current_runtime() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "voodoo_product/service.py",
        "voodoo_product/execution.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "dispatch_inbox" not in source
        assert "DispatchInboxAdmission" not in source
