from __future__ import annotations

import ast
from pathlib import Path

from voodoo_product.f4b_live_write_pilot import run_live_write_pilot
from voodoo_product.github_create_ref_provider import GitHubCreateRefProviderResponse
from voodoo_product.github_create_ref_runtime import GitHubApiCreateRefTransport


def _env(monkeypatch) -> None:
    values = {
        "GITHUB_TOKEN": "test-secret-never-serialized",
        "VONE_TARGET_REPOSITORY": "nulleimy/V-One",
        "VONE_TARGET_REF": "refs/heads/vone-canary/f4b-dry-test",
        "VONE_TARGET_SHA": "a" * 40,
        "VONE_PROVIDER_INSTANCE_ID": "gha-f4b-dry-test",
        "VONE_RUNTIME_ROOTFS_DIGEST": "1" * 64,
        "VONE_RESOURCE_LIMIT_PROFILE_DIGEST": "2" * 64,
        "VONE_NETWORK_POLICY_DIGEST": "3" * 64,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_full_f4b_chain_reaches_one_create_only_transport_call(monkeypatch) -> None:
    _env(monkeypatch)
    calls = []

    def create_ref(self, *, request):
        del self
        calls.append(request.to_dict())
        return GitHubCreateRefProviderResponse.created(
            ref=request.ref,
            object_sha=request.sha,
            source_identity="github-rest/git-create-ref/v1",
            response_revision="github-create-ref-provider-response/f4b-dry-test-r1",
        )

    monkeypatch.setattr(GitHubApiCreateRefTransport, "create_ref", create_ref)
    result = run_live_write_pilot()

    assert len(calls) == 1
    assert result["status"] == "EFFECT_RECORDED_NOT_VERIFIED"
    assert result["provider_mutation_performed"] is True
    assert result["provider_mutation_count"] == 1
    assert result["automatic_retry_performed"] is False
    assert result["rollback_performed"] is False
    assert result["credential_secret_material_serialized"] is False
    assert result["provider_response"]["status_code"] == 201
    assert result["create_ref_request"]["ref"] == "refs/heads/vone-canary/f4b-dry-test"
    assert result["create_ref_request"]["sha"] == "a" * 40
    assert result["execution_grant"]["use_semantics"] == "ONE_TIME"
    assert result["execution_grant"]["precondition_enforcement_class"] == "ATOMIC_PROVIDER_CONDITION"
    assert result["runner_boundary"]["max_provider_mutations"] == 1
    assert result["credential_decision"]["provider_operation"] == "CREATE_REF"
    assert result["write_effect_preflight"]["provider_operation"] == "CREATE_REF"
    assert result["durable_completion"]["completion_digest"] == result["provider_response"]["response_digest"]

    encoded = str(result)
    assert "test-secret-never-serialized" not in encoded
    assert "VERIFIED" not in encoded


def test_f4b_pilot_has_no_delete_or_force_update_provider_path() -> None:
    source = Path("voodoo_product/f4b_live_write_pilot.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    public_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "delete_ref" not in public_calls
    assert "update_ref" not in public_calls
    assert "force_update" not in public_calls
    assert "create_ref" in public_calls
