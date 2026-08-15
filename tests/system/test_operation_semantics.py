from __future__ import annotations

import hashlib

import pytest

from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.operation_semantics import (
    MEMBER_ROLES,
    OPERATION_STAGES,
    TECHNIQUE_ROLES,
    OperationMember,
    OperationSemantics,
    TechniqueEvidence,
    common_language,
)


def members() -> tuple[OperationMember, ...]:
    return tuple(
        OperationMember(role=role, member_id=f"id_{role}")
        for role in reversed(MEMBER_ROLES)
    )


def techniques() -> tuple[TechniqueEvidence, ...]:
    return tuple(
        TechniqueEvidence.from_name(name)
        for name in ("slsa", "mcp", "sigstore", "a2a", "aws_agentcore", "spiffe")
    )


def digest_without(payload: dict[str, object], digest_field: str) -> str:
    without_digest = {
        key: value for key, value in payload.items() if key != digest_field
    }
    return hashlib.sha256(
        canonical_json(without_digest).encode("utf-8")
    ).hexdigest()


def test_common_language_is_deterministic_and_complete() -> None:
    first = common_language()
    second = common_language()

    assert first == second
    assert first["language_digest"] == digest_without(first, "language_digest")
    assert [member["role"] for member in first["members"]] == list(MEMBER_ROLES)
    assert first["operation_stages"] == list(OPERATION_STAGES)
    assert {item["technique_role"] for item in first["techniques"]} == set(TECHNIQUE_ROLES)


def test_operation_semantics_digest_is_stable_and_bound_to_common_language() -> None:
    first = OperationSemantics.create(
        operation_id="op_semantics",
        capability="github.pull-request.merge/v1",
        members=members(),
        techniques=techniques(),
    )
    second = OperationSemantics.create(
        operation_id="op_semantics",
        capability="github.pull-request.merge/v1",
        members=tuple(reversed(members())),
        techniques=tuple(reversed(techniques())),
    )

    assert first.to_dict() == second.to_dict()
    assert first.semantics_digest == digest_without(first.to_dict(), "semantics_digest")
    assert OperationSemantics.from_dict(first.to_dict()) == first


def test_operation_semantics_requires_every_system_member_role() -> None:
    incomplete_members = tuple(member for member in members() if member.role != "verifier")

    with pytest.raises(ValueError, match="missing required roles"):
        OperationSemantics.create(
            operation_id="op_semantics",
            capability="github.pull-request.merge/v1",
            members=incomplete_members,
            techniques=techniques(),
        )


def test_operation_semantics_rejects_duplicate_member_identity() -> None:
    duplicate_identity = tuple(
        OperationMember(role=role, member_id="same_identity")
        for role in MEMBER_ROLES
    )

    with pytest.raises(ValueError, match="member identities must be unique"):
        OperationSemantics.create(
            operation_id="op_semantics",
            capability="github.pull-request.merge/v1",
            members=duplicate_identity,
            techniques=techniques(),
        )


def test_operation_semantics_rejects_tampered_member_purpose() -> None:
    payload = OperationSemantics.create(
        operation_id="op_semantics",
        capability="github.pull-request.merge/v1",
        members=members(),
        techniques=techniques(),
    ).to_dict()
    payload["members"][0]["purpose"] = "Creates privilege from an AI plan."
    payload["semantics_digest"] = digest_without(payload, "semantics_digest")

    with pytest.raises(ValueError, match="member purpose"):
        OperationSemantics.from_dict(payload)


def test_operation_semantics_rejects_unverified_technique() -> None:
    with pytest.raises(ValueError, match="verified V-One technique map"):
        TechniqueEvidence.from_name("unverified_magic_bus")


def test_operation_semantics_requires_all_technique_roles() -> None:
    incomplete_techniques = tuple(
        technique for technique in techniques() if technique.technique_role != "provenance"
    )

    with pytest.raises(ValueError, match="missing required roles"):
        OperationSemantics.create(
            operation_id="op_semantics",
            capability="github.pull-request.merge/v1",
            members=members(),
            techniques=incomplete_techniques,
        )
