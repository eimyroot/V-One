from __future__ import annotations

from dataclasses import replace

import pytest

from voodoo_product.vop_translation import (
    NEW_CAPABILITY,
    SEMANTICALLY_EQUIVALENT,
    ProviderSemanticMapping,
    SemanticEquivalenceAssessment,
    SemanticEquivalenceProfile,
)


def profile(
    *,
    implementation_identity: str,
    capability: str = "github.pull-request.merge/v1",
    side_effect: str = "pull_request_merged",
) -> SemanticEquivalenceProfile:
    return SemanticEquivalenceProfile.create(
        capability=capability,
        implementation_identity=implementation_identity,
        semantic_input="reviewed merge request",
        authoritative_target="github://nulleimy/V-One/pull/71",
        side_effect=side_effect,
        permission="pull_request.merge",
        approval="approval-policy/v1",
        idempotency="provider-key-idempotent",
        receipt="github-merge-receipt/v1",
        verification="github-merge-verifier/v1",
        evidence="full-operation-evidence/v1",
    )


def test_provider_mapping_keeps_transport_separate_from_vop_semantics() -> None:
    mapping = ProviderSemanticMapping.create(
        provider="github",
        external_operation="PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge",
        transport="REST",
        capability="github.pull-request.merge/v1",
        requested_target={"repository": "nulleimy/V-One", "pull_request": 71},
        expected_post_state={"state": "merged", "merge_commit_sha": "expected"},
    )

    assert mapping.capability == "github.pull-request.merge/v1"
    assert mapping.transport == "REST"
    assert mapping.to_dict()["mapping_digest"] == mapping.mapping_digest


def test_provider_mapping_does_not_retain_caller_owned_mutable_payloads() -> None:
    requested_target = {"repository": "nulleimy/V-One", "pull_request": 71}
    expected_post_state = {"state": "merged"}
    mapping = ProviderSemanticMapping.create(
        provider="github",
        external_operation="merge",
        transport="REST",
        capability="github.pull-request.merge/v1",
        requested_target=requested_target,
        expected_post_state=expected_post_state,
    )
    digest = mapping.mapping_digest

    requested_target["pull_request"] = 999
    expected_post_state["state"] = "closed"
    returned_target = mapping.requested_target
    returned_target["pull_request"] = 555

    assert mapping.requested_target == {"repository": "nulleimy/V-One", "pull_request": 71}
    assert mapping.expected_post_state == {"state": "merged"}
    assert mapping.mapping_digest == digest


def test_transport_implementation_change_can_be_semantically_equivalent() -> None:
    current = profile(implementation_identity="github-rest-handler@sha256:aaa")
    candidate = profile(implementation_identity="github-graphql-handler@sha256:bbb")

    assessment = SemanticEquivalenceAssessment.compare(current, candidate)

    assert assessment.result == SEMANTICALLY_EQUIVALENT
    assert assessment.mismatched_dimensions == ()


def test_semantic_change_requires_new_capability() -> None:
    current = profile(implementation_identity="github-rest-handler@sha256:aaa")
    candidate = profile(
        implementation_identity="github-graphql-handler@sha256:bbb",
        side_effect="pull_request_closed_without_merge",
    )

    assessment = SemanticEquivalenceAssessment.compare(current, candidate)

    assert assessment.result == NEW_CAPABILITY
    assert assessment.mismatched_dimensions == ("side_effect",)


def test_capability_identity_change_is_never_equivalent() -> None:
    current = profile(implementation_identity="impl-a")
    candidate = profile(
        implementation_identity="impl-b",
        capability="github.pull-request.close/v1",
    )

    assessment = SemanticEquivalenceAssessment.compare(current, candidate)

    assert assessment.result == NEW_CAPABILITY
    assert "capability" in assessment.mismatched_dimensions


def test_tampered_profile_digest_is_rejected() -> None:
    valid = profile(implementation_identity="impl-a")

    with pytest.raises(ValueError, match="profile_digest"):
        replace(valid, profile_digest="0" * 64)
