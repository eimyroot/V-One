from __future__ import annotations

from copy import deepcopy

import pytest

from voodoo_product.execution_receipt_v2 import (
    EFFECT_RECORDED,
    EXECUTION_SUCCEEDED,
    NOT_EVALUATED,
    ExecutionReceiptV2,
    compose_write_execution_receipt_v2,
)
from voodoo_product.f4b_live_write_pilot import run_live_write_pilot
from voodoo_product.github_create_ref_provider import GitHubCreateRefProviderResponse
from voodoo_product.github_create_ref_runtime import GitHubApiCreateRefTransport

FIXED_RECORDED_AT = "2026-08-19T00:00:00.000+00:00"
FIXED_CLOCK_DIGEST = "c" * 64


def _result(monkeypatch):
    values = {
        "GITHUB_TOKEN": "receipt-test-secret-never-serialized",
        "VONE_TARGET_REPOSITORY": "nulleimy/V-One",
        "VONE_TARGET_REF": "refs/heads/vone-canary/f5-receipt-test",
        "VONE_TARGET_SHA": "a" * 40,
        "VONE_PROVIDER_INSTANCE_ID": "gha-f5-receipt-test",
        "VONE_RUNTIME_ROOTFS_DIGEST": "1" * 64,
        "VONE_RESOURCE_LIMIT_PROFILE_DIGEST": "2" * 64,
        "VONE_NETWORK_POLICY_DIGEST": "3" * 64,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    calls = []

    def create_ref(self, *, request):
        del self
        calls.append(request.request_digest)
        return GitHubCreateRefProviderResponse.created(
            ref=request.ref,
            object_sha=request.sha,
            source_identity="github-rest/git-create-ref/v1",
            response_revision="github-create-ref-provider-response/f5-test-r1",
        )

    monkeypatch.setattr(GitHubApiCreateRefTransport, "create_ref", create_ref)
    result = run_live_write_pilot()
    assert len(calls) == 1
    return result


def _compose(result):
    return compose_write_execution_receipt_v2(
        write_result=result,
        recording_clock_witness_digest=FIXED_CLOCK_DIGEST,
        recorded_at=FIXED_RECORDED_AT,
        receipt_revision="execution-receipt/f5-r1",
    )


def test_execution_receipt_v2_composes_exact_f4b_effect_lineage(monkeypatch) -> None:
    result = _result(monkeypatch)
    receipt = _compose(result)

    assert receipt.execution_status == EXECUTION_SUCCEEDED
    assert receipt.effect_status == EFFECT_RECORDED
    assert receipt.verification_status == NOT_EVALUATED
    assert receipt.execution_grant_digest == result["execution_grant"]["grant_digest"]
    assert receipt.grant_consumption_witness_digest == result["grant_consumption"]["witness_digest"]
    assert receipt.dispatch_envelope_digest == result["dispatch_envelope"]["envelope_digest"]
    assert receipt.dispatch_admission_digest == result["dispatch_admission"]["admission_digest"]
    assert receipt.execution_lease_digest == result["execution_lease"]["lease_digest"]
    assert receipt.runner_boundary_digest == result["runner_boundary"]["boundary_digest"]
    assert receipt.provider_response_digest == result["provider_response"]["response_digest"]
    assert receipt.durable_completion_digest == receipt.provider_response_digest
    assert receipt.provider_mutation_count == 1
    assert receipt.automatic_retry_performed is False
    assert receipt.rollback_performed is False
    assert "receipt-test-secret-never-serialized" not in str(receipt.to_dict())

    restored = ExecutionReceiptV2.from_dict(receipt.to_dict())
    assert restored == receipt
    assert _compose(result).receipt_digest == receipt.receipt_digest


def test_execution_receipt_v2_rejects_grant_substitution(monkeypatch) -> None:
    result = deepcopy(_result(monkeypatch))
    result["grant_consumption"]["grant_digest"] = "d" * 64
    with pytest.raises(PermissionError, match="RECEIPT_CONSUMPTION_GRANT_MISMATCH"):
        _compose(result)


def test_execution_receipt_v2_rejects_completion_substitution(monkeypatch) -> None:
    result = deepcopy(_result(monkeypatch))
    result["durable_completion"]["completion_digest"] = "d" * 64
    with pytest.raises(PermissionError, match="RECEIPT_COMPLETION_RESPONSE_MISMATCH"):
        _compose(result)


def test_execution_receipt_v2_cannot_claim_verified(monkeypatch) -> None:
    receipt = _compose(_result(monkeypatch))
    value = receipt.to_dict()
    value["verification_status"] = "VERIFIED"
    with pytest.raises(ValueError, match="must not manufacture"):
        ExecutionReceiptV2.from_dict(value)
