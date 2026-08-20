from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from voodoo_product import a09_rollback_orchestration as rollback_module
from voodoo_product import a09_write_orchestration as create_module
from voodoo_product.a09_rollback_orchestration import A09RollbackPreparer
from voodoo_product.a09_write_orchestration import A09CreateRefPreparer
from voodoo_product.canonical_pipeline import CanonicalPreparedExecution
from voodoo_product.terminal_profile import (
    BOUNDED_MUTATION_TERMINAL_PROFILE,
    READ_ONLY_TERMINAL_PROFILE,
)

D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
D6 = "6" * 64
D7 = "7" * 64
D8 = "8" * 64
D9 = "9" * 64
DA = "a" * 64


def prepared(*, capability: str, profile: str = BOUNDED_MUTATION_TERMINAL_PROFILE) -> CanonicalPreparedExecution:
    target = SimpleNamespace(
        target_digest=D3,
        target_claims={
            "repository": "nulleimy/V-One",
            "ref": "refs/heads/vone-canary/a09-dynamic-target",
            "commit_sha": "a" * 40,
            "expected_sha": "a" * 40,
            "original_create_response_digest": D8,
            "original_verification_result_digest": D9,
        },
    )
    return CanonicalPreparedExecution(
        terminal_profile=profile,
        terminal_profile_binding_digest=D1,
        execution_id="exec-a09-1",
        request_id="req-a09-1",
        capability=capability,
        capability_definition_identity=D2,
        environment="staging",
        target_digest=D3,
        authorization_snapshot_digest=D4,
        grant_digest=D5,
        grant_jti="jti-a09-1",
        outbox_entry_digest=D6,
        envelope_digest=D7,
        admission_digest=D8,
        lease_id=D9,
        lease_digest=DA,
        execution_epoch=1,
        execution_capsule_digest=D1,
        snapshot=SimpleNamespace(execution_target=target),
        grant=SimpleNamespace(),
        outbox=SimpleNamespace(consumption_id=D2, consumption_witness_digest=D3),
        envelope=SimpleNamespace(),
        admission=SimpleNamespace(),
        lease=SimpleNamespace(
            acquired_at="2026-08-20T02:00:00.000+00:00",
            expires_at="2026-08-20T02:05:00.000+00:00",
        ),
    )


def test_a09_modules_contain_no_provider_mutation_transport_or_historical_target_binding() -> None:
    text = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "voodoo_product/a09_write_orchestration.py",
            "voodoo_product/a09_rollback_orchestration.py",
        )
    )
    forbidden = (
        "GitHubApiCreateRefTransport",
        "GitHubApiDeleteRefTransport",
        ".create_ref(",
        ".delete_ref(",
        "f4b-pr120",
        "pr120",
        "83f9c43357460e49b1eba82f124a13015a8e6a88",
        "32213563750",
    )
    for marker in forbidden:
        assert marker not in text


def test_a09_preparers_expose_no_generic_effect_execution_api() -> None:
    for subject in (
        object.__new__(A09CreateRefPreparer),
        object.__new__(A09RollbackPreparer),
    ):
        for forbidden in ("execute", "mutate", "apply", "create_ref", "delete_ref"):
            assert not hasattr(subject, forbidden)


def test_create_ref_preparer_rejects_read_profile_before_dependencies() -> None:
    subject = object.__new__(A09CreateRefPreparer)
    with pytest.raises(PermissionError, match="A09_CREATE_REF_TERMINAL_PROFILE_MISMATCH"):
        subject.prepare(
            prepared=prepared(
                capability="github.create-ref/v1",
                profile=READ_ONLY_TERMINAL_PROFILE,
            )
        )


def test_rollback_preparer_rejects_read_profile_before_dependencies() -> None:
    subject = object.__new__(A09RollbackPreparer)
    with pytest.raises(PermissionError, match="A09_ROLLBACK_TERMINAL_PROFILE_MISMATCH"):
        subject.prepare(
            prepared=prepared(
                capability="github.delete-exact-created-ref/v1",
                profile=READ_ONLY_TERMINAL_PROFILE,
            ),
            observed_ref_sha="a" * 40,
            predelete_observation_digest=D1,
        )


def test_create_ref_orchestration_ends_at_preflight_without_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    subject = object.__new__(A09CreateRefPreparer)
    subject.capability_registry = SimpleNamespace(
        definition_by_identity=lambda _: SimpleNamespace(capability="github.create-ref/v1")
    )
    subject.capsule_registry = SimpleNamespace(
        capsule_for_definition=lambda _: SimpleNamespace(capsule_digest=D1)
    )
    subject.handler_registry = SimpleNamespace(resolve=lambda _: SimpleNamespace())
    subject.provider_condition = SimpleNamespace()
    subject.runtime_profile = SimpleNamespace(
        provider="github-actions",
        provider_instance_id="gha:a09:create:1",
        rootfs_digest=D1,
        resource_limit_profile_digest=D2,
        network_policy_digest=D3,
        bootstrap_revision="bootstrap/a09-r1",
        identity_revision="identity/a09-r1",
        requirement_revision="requirement/a09-r1",
        boundary_revision="boundary/a09-r1",
        max_credential_ttl_seconds=60,
        credential_policy_revision="policy/a09-r1",
        credential_decision_revision="decision/a09-r1",
        credential_delivery_revision="delivery/a09-r1",
        activation_revision="activation/a09-r1",
        request_revision="request/a09-r1",
        preflight_revision="preflight/a09-r1",
    )
    witness = SimpleNamespace(observed_at="2026-08-20T02:00:01.000+00:00", witness_digest=D4)
    subject.trusted_clock = SimpleNamespace(witness=lambda **_: witness)
    subject.current_fence = SimpleNamespace()
    subject.handler_contract = SimpleNamespace(
        prepare_request=lambda **_: events.append("request") or SimpleNamespace()
    )
    subject._load_consumption = lambda **_: SimpleNamespace()  # type: ignore[method-assign]

    def fake_create(name: str, result: object):
        return lambda **_: events.append(name) or result

    monkeypatch.setattr(create_module.ControlledWriteRequirement, "create", fake_create("requirement", SimpleNamespace()))
    monkeypatch.setattr(create_module.IsolatedRuntimeBootstrap, "create", fake_create("bootstrap", SimpleNamespace()))
    monkeypatch.setattr(create_module.RunnerIdentity, "create", fake_create("identity", SimpleNamespace()))
    monkeypatch.setattr(create_module.RunnerBoundaryV2, "create", fake_create("boundary", SimpleNamespace()))
    monkeypatch.setattr(create_module.CredentialBrokerPolicyV2, "create", fake_create("policy", SimpleNamespace()))
    monkeypatch.setattr(create_module.CredentialAccessDecisionV2, "create", fake_create("decision", SimpleNamespace()))
    monkeypatch.setattr(create_module.EphemeralWriteCredentialDelivery, "create", fake_create("delivery", SimpleNamespace()))
    monkeypatch.setattr(create_module.WriteRuntimeActivation, "create", fake_create("activation", SimpleNamespace()))
    monkeypatch.setattr(create_module.TargetBinding, "create", fake_create("target-binding", SimpleNamespace()))
    monkeypatch.setattr(create_module.WriteEffectPreflight, "verify", fake_create("preflight", SimpleNamespace(preflight_digest=D5)))

    output = subject.prepare(prepared=prepared(capability="github.create-ref/v1"))

    assert events == [
        "requirement",
        "bootstrap",
        "identity",
        "boundary",
        "policy",
        "decision",
        "delivery",
        "activation",
        "target-binding",
        "request",
        "preflight",
    ]
    assert output.preflight.preflight_digest == D5


def test_rollback_orchestration_requires_current_fence_and_ends_at_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    subject = object.__new__(A09RollbackPreparer)
    subject.capability_registry = SimpleNamespace(
        definition_by_identity=lambda _: SimpleNamespace(capability="github.delete-exact-created-ref/v1")
    )
    subject.capsule_registry = SimpleNamespace(
        capsule_for_definition=lambda _: SimpleNamespace(capsule_digest=D1)
    )
    subject.handler_registry = SimpleNamespace(resolve=lambda _: SimpleNamespace())
    subject.runtime_profile = SimpleNamespace(
        provider="github-actions",
        provider_instance_id="gha:a09:rollback:1",
        rootfs_digest=D1,
        resource_limit_profile_digest=D2,
        network_policy_digest=D3,
        identity_revision="identity/a09-r1",
        condition_revision="condition/a09-r1",
        requirement_revision="requirement/a09-r1",
        boundary_revision="boundary/a09-r1",
        max_credential_ttl_seconds=60,
        credential_policy_revision="policy/a09-r1",
        credential_decision_revision="decision/a09-r1",
        credential_delivery_revision="delivery/a09-r1",
        activation_revision="activation/a09-r1",
        request_revision="request/a09-r1",
        preflight_revision="preflight/a09-r1",
    )
    witness = SimpleNamespace(observed_at="2026-08-20T02:00:01.000+00:00", witness_digest=D4)
    subject.trusted_clock = SimpleNamespace(witness=lambda **_: witness)
    subject.current_fence = SimpleNamespace(
        assert_current=lambda **_: events.append("current-fence")
    )
    subject.handler_contract = SimpleNamespace(
        prepare_request=lambda **_: events.append("request") or SimpleNamespace()
    )

    def fake_create(name: str, result: object):
        return lambda **_: events.append(name) or result

    monkeypatch.setattr(rollback_module.GitHubDeleteRefConditionContract, "create", fake_create("condition", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.RollbackWriteRequirement, "create", fake_create("requirement", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.RunnerIdentity, "create", fake_create("identity", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.RunnerBoundaryV3, "create", fake_create("boundary", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.CredentialBrokerPolicyV3, "create", fake_create("policy", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.CredentialAccessDecisionV3, "create", fake_create("decision", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.EphemeralRollbackCredentialDelivery, "create", fake_create("delivery", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.RollbackWriteRuntimeActivation, "create", fake_create("activation", SimpleNamespace()))
    monkeypatch.setattr(rollback_module.RollbackWriteEffectPreflight, "create", fake_create("preflight", SimpleNamespace(preflight_digest=D6)))

    output = subject.prepare(
        prepared=prepared(capability="github.delete-exact-created-ref/v1"),
        observed_ref_sha="a" * 40,
        predelete_observation_digest=D7,
    )

    assert events[-2:] == ["current-fence", "preflight"]
    assert "request" in events
    assert output.preflight.preflight_digest == D6
