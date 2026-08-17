from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from voodoo_product.dispatch_envelope import (
    DELIVERY_SEMANTICS,
    DispatchEnvelope,
)
from voodoo_product.dispatch_outbox import DispatchOutboxEntry
from voodoo_product.evidence_primitives import canonical_json


def digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_outbox(
    *,
    outbox_id: str = "out_c2",
    consumption_id: str = "gcon_c2",
    jti: str = "jti_c2",
    grant_id: str = "grt_c2",
    execution_id: str = "exec_c2",
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
        "request_id": "cr_c2",
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
        "created_at": "2026-08-17T03:30:00.000+00:00",
        "outbox_revision": "dispatch-outbox/c1b-r1",
    }
    claims["entry_digest"] = digest(claims)
    return DispatchOutboxEntry.from_dict(claims)


def envelope_claims_without_digest(raw: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in raw.items() if key != "envelope_digest"}


def test_dispatch_envelope_is_exact_projection_of_outbox() -> None:
    outbox = make_outbox()

    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )

    assert envelope.outbox_id == outbox.outbox_id
    assert envelope.outbox_entry_digest == outbox.entry_digest
    assert envelope.consumption_id == outbox.consumption_id
    assert envelope.grant_digest == outbox.grant_digest
    assert envelope.execution_id == outbox.execution_id
    assert envelope.target_digest == outbox.target_digest
    assert envelope.payload_digest == outbox.payload_digest
    assert envelope.execution_capsule_digest == outbox.execution_capsule_digest
    assert envelope.runner_class == outbox.runner_class
    assert envelope.delivery_semantics == DELIVERY_SEMANTICS
    assert envelope.outbox_created_at == outbox.created_at
    envelope.assert_bound_to(outbox)
    assert DispatchEnvelope.from_dict(envelope.to_dict()) == envelope


def test_dispatch_identity_is_stable_for_redelivery_and_protocol_revision() -> None:
    outbox = make_outbox()

    first = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )
    repeated = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )
    next_revision = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r2",
    )

    assert repeated == first
    assert next_revision.dispatch_id == first.dispatch_id
    assert next_revision.envelope_digest != first.envelope_digest


def test_dispatch_identity_changes_for_a_different_outbox() -> None:
    first = DispatchEnvelope.create(
        outbox_entry=make_outbox(),
        envelope_revision="dispatch-envelope/c2-r1",
    )
    second = DispatchEnvelope.create(
        outbox_entry=make_outbox(
            outbox_id="out_c2_other",
            consumption_id="gcon_c2_other",
            jti="jti_c2_other",
            grant_id="grt_c2_other",
            execution_id="exec_c2_other",
            target_digest="9" * 64,
        ),
        envelope_revision="dispatch-envelope/c2-r1",
    )

    assert second.outbox_entry_digest != first.outbox_entry_digest
    assert second.dispatch_id != first.dispatch_id
    assert second.envelope_digest != first.envelope_digest


def test_dispatch_id_is_not_caller_supplied() -> None:
    parameters = inspect.signature(DispatchEnvelope.create).parameters

    assert "dispatch_id" not in parameters
    with pytest.raises(TypeError):
        DispatchEnvelope.create(  # type: ignore[call-arg]
            outbox_entry=make_outbox(),
            envelope_revision="dispatch-envelope/c2-r1",
            dispatch_id="0" * 64,
        )


def test_envelope_rejects_dispatch_id_and_delivery_semantic_tamper() -> None:
    envelope = DispatchEnvelope.create(
        outbox_entry=make_outbox(),
        envelope_revision="dispatch-envelope/c2-r1",
    )

    wrong_dispatch = envelope.to_dict()
    wrong_dispatch["dispatch_id"] = "0" * 64
    wrong_dispatch["envelope_digest"] = digest(
        envelope_claims_without_digest(wrong_dispatch)
    )
    with pytest.raises(ValueError, match="dispatch_id"):
        DispatchEnvelope.from_dict(wrong_dispatch)

    reusable_delivery = envelope.to_dict()
    reusable_delivery["delivery_semantics"] = "EXACTLY_ONCE"
    reusable_delivery["envelope_digest"] = digest(
        envelope_claims_without_digest(reusable_delivery)
    )
    with pytest.raises(ValueError, match="delivery_semantics"):
        DispatchEnvelope.from_dict(reusable_delivery)


def test_structural_parser_does_not_prove_durable_outbox_binding() -> None:
    outbox = make_outbox()
    envelope = DispatchEnvelope.create(
        outbox_entry=outbox,
        envelope_revision="dispatch-envelope/c2-r1",
    )

    self_consistent_tamper = envelope.to_dict()
    self_consistent_tamper["target_digest"] = "9" * 64
    self_consistent_tamper["envelope_digest"] = digest(
        envelope_claims_without_digest(self_consistent_tamper)
    )
    structurally_valid = DispatchEnvelope.from_dict(self_consistent_tamper)

    with pytest.raises(PermissionError, match="does not bind"):
        structurally_valid.assert_bound_to(outbox)


def test_envelope_rejects_digest_tamper_and_unknown_fields() -> None:
    envelope = DispatchEnvelope.create(
        outbox_entry=make_outbox(),
        envelope_revision="dispatch-envelope/c2-r1",
    )

    tampered = envelope.to_dict()
    tampered["runner_class"] = "unbounded-runner/v1"
    with pytest.raises(ValueError, match="envelope_digest"):
        DispatchEnvelope.from_dict(tampered)

    unknown = envelope.to_dict()
    unknown["runner_endpoint"] = "https://runner.example"
    with pytest.raises(ValueError, match="fields are invalid"):
        DispatchEnvelope.from_dict(unknown)


def test_c2_does_not_wire_dispatch_into_current_runtime() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "voodoo_product/service.py",
        "voodoo_product/execution.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "dispatch_envelope" not in source
        assert "DispatchEnvelope" not in source
