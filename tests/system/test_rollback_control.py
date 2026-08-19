from __future__ import annotations

import pytest

from voodoo_product.rollback_control import (
    DELETE_EXACT_TARGET_ONLY,
    GITHUB_DELETE_REF_CONDITION_TYPE,
    READ_THEN_DELETE_NON_ATOMIC,
    GitHubDeleteRefConditionContract,
    GitHubDeleteRefProviderResponse,
    GitHubDeleteRefTargetBinder,
)


def condition() -> GitHubDeleteRefConditionContract:
    return GitHubDeleteRefConditionContract.create(
        repository="nulleimy/V-One",
        ref="refs/heads/vone-canary/f4b-pr120-32185703943",
        expected_sha="a" * 40,
        original_create_response_digest="b" * 64,
        original_verification_result_digest="c" * 64,
        contract_revision="rollback-condition/f6-r1",
    )


def test_delete_condition_is_exact_and_explicitly_non_atomic() -> None:
    value = condition().to_dict()
    assert value["condition_type"] == GITHUB_DELETE_REF_CONDITION_TYPE
    assert value["temporal_model"] == READ_THEN_DELETE_NON_ATOMIC
    assert value["delete_semantics"] == DELETE_EXACT_TARGET_ONLY
    assert value["expected_sha"] == "a" * 40


def test_target_binder_rejects_non_canary_ref() -> None:
    binder = GitHubDeleteRefTargetBinder()
    payload = {
        "repository": "nulleimy/V-One",
        "ref": "refs/heads/main",
        "expected_sha": "a" * 40,
        "original_create_response_digest": "b" * 64,
        "original_verification_result_digest": "c" * 64,
    }
    with pytest.raises(ValueError, match="canary namespace"):
        binder.bind(approved_payload=payload)


def test_provider_success_response_is_only_http_204() -> None:
    response = GitHubDeleteRefProviderResponse.deleted(
        ref="refs/heads/vone-canary/f4b-pr120-32185703943",
        expected_sha="a" * 40,
        source_identity="github-rest/git-delete-ref/v1",
        response_revision="github-delete-ref-provider-response/f6-r1",
    )
    assert response.http_status == 204
    assert response.deleted_ref.startswith("refs/heads/vone-canary/")
