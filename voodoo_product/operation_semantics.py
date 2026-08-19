from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Self

from .evidence_primitives import canonical_json
from .vop_vocabulary import OPERATION_STAGES

SCHEMA_VERSION = 1
COMMON_LANGUAGE_TYPE = "v-one-common-language/v1"
OPERATION_SEMANTICS_TYPE = "v-one-operation-semantics/v1"

MEMBER_ROLES = (
    "owner",
    "operator",
    "ai_agent",
    "cybercore",
    "policy_engine",
    "approval_quorum",
    "runner",
    "verifier",
    "evidence_fabric",
)

TECHNIQUE_ROLES = (
    "tool_access",
    "agent_interop",
    "runtime_observability",
    "transport_identity",
    "attestation",
    "provenance",
)

_MEMBER_PURPOSES = {
    "owner": "Sets constitutional authority, release boundaries, and exception ownership.",
    "operator": "Accepts accountable human responsibility for consequential operation decisions.",
    "ai_agent": (
        "Creates proposals, explanations, tests, and review inputs without creating privilege."
    ),
    "cybercore": (
        "Supplies observations, context, learning signals, and proposals without authorization."
    ),
    "policy_engine": (
        "Evaluates deterministic allow, deny, and fail-closed rules for a requested operation."
    ),
    "approval_quorum": (
        "Binds independent human or organizational approvals to exact operation evidence."
    ),
    "runner": (
        "Executes an already-authorized dispatch under current lease and fence state, performs the "
        "bounded effect, and emits a structured receipt without issuing or consuming grants."
    ),
    "verifier": (
        "Checks real provider state independently from the actor, planner, and runner claim."
    ),
    "evidence_fabric": "Stores audit, receipt, manifest, checkpoint, and proof relationships.",
}

_MEMBER_AUTHORITY = {
    "owner": "governance_authority",
    "operator": "human_execution_accountability",
    "ai_agent": "proposal_only",
    "cybercore": "intelligence_only",
    "policy_engine": "decision_projection_or_gate",
    "approval_quorum": "approval_evidence",
    "runner": "bounded_execution_only",
    "verifier": "verification_evidence",
    "evidence_fabric": "evidence_integrity",
}

_TECHNIQUE_MAP = {
    "mcp": {
        "technique_role": "tool_access",
        "source_authority": "Model Context Protocol specification",
        "v_one_boundary": "Exposes tools and context below V-One authorization semantics.",
    },
    "a2a": {
        "technique_role": "agent_interop",
        "source_authority": "Agent2Agent Protocol specification",
        "v_one_boundary": (
            "Moves agent-to-agent tasks without deciding consequential-operation authority."
        ),
    },
    "aws_agentcore": {
        "technique_role": "runtime_observability",
        "source_authority": "Amazon Bedrock AgentCore documentation",
        "v_one_boundary": (
            "Provides runtime identity and observability inputs, not V-One proof by itself."
        ),
    },
    "spiffe": {
        "technique_role": "transport_identity",
        "source_authority": (
            "SPIFFE identity model as referenced by agent-platform identity designs"
        ),
        "v_one_boundary": (
            "Identifies workloads or agents; authorization still remains V-One governed."
        ),
    },
    "sigstore": {
        "technique_role": "attestation",
        "source_authority": "Sigstore documentation",
        "v_one_boundary": (
            "Signs and verifies artifacts or attestations without defining operation semantics."
        ),
    },
    "in_toto": {
        "technique_role": "attestation",
        "source_authority": "in-toto attestation specification",
        "v_one_boundary": (
            "Carries signed statements whose payload must be interpreted by V-One contracts."
        ),
    },
    "slsa": {
        "technique_role": "provenance",
        "source_authority": "SLSA provenance specification",
        "v_one_boundary": (
            "Describes artifact production provenance, not runtime authorization alone."
        ),
    },
}


def common_language() -> dict[str, Any]:
    """Return the deterministic V-One vocabulary shared by all members."""

    members = [
        {
            "role": role,
            "purpose": _MEMBER_PURPOSES[role],
            "authority": _MEMBER_AUTHORITY[role],
        }
        for role in MEMBER_ROLES
    ]
    techniques = [
        {
            "name": name,
            "technique_role": claims["technique_role"],
            "source_authority": claims["source_authority"],
            "v_one_boundary": claims["v_one_boundary"],
        }
        for name, claims in sorted(_TECHNIQUE_MAP.items())
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "language_type": COMMON_LANGUAGE_TYPE,
        "members": members,
        "operation_stages": list(OPERATION_STAGES),
        "techniques": techniques,
    }
    payload["language_digest"] = _digest(payload, "language_digest")
    return payload


@dataclass(frozen=True, slots=True)
class OperationMember:
    role: str
    member_id: str

    def __post_init__(self) -> None:
        if self.role not in MEMBER_ROLES:
            raise ValueError("member role is not part of the V-One common language")
        _require_identifier(self.member_id, field="member_id")

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "member_id": self.member_id,
            "purpose": _MEMBER_PURPOSES[self.role],
            "authority": _MEMBER_AUTHORITY[self.role],
        }


@dataclass(frozen=True, slots=True)
class TechniqueEvidence:
    name: str
    technique_role: str
    source_authority: str
    v_one_boundary: str

    def __post_init__(self) -> None:
        expected = _TECHNIQUE_MAP.get(self.name)
        if expected is None:
            raise ValueError("technique is not in the verified V-One technique map")
        for field in ("technique_role", "source_authority", "v_one_boundary"):
            if getattr(self, field) != expected[field]:
                raise ValueError(f"{field} does not match the verified technique map")

    @classmethod
    def from_name(cls, name: str) -> Self:
        _require_identifier(name, field="name")
        claims = _TECHNIQUE_MAP.get(name)
        if claims is None:
            raise ValueError("technique is not in the verified V-One technique map")
        return cls(
            name=name,
            technique_role=claims["technique_role"],
            source_authority=claims["source_authority"],
            v_one_boundary=claims["v_one_boundary"],
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "technique_role": self.technique_role,
            "source_authority": self.source_authority,
            "v_one_boundary": self.v_one_boundary,
        }


@dataclass(frozen=True, slots=True)
class OperationSemantics:
    operation_id: str
    capability: str
    members: tuple[OperationMember, ...]
    stages: tuple[str, ...]
    techniques: tuple[TechniqueEvidence, ...]
    semantics_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.operation_id, field="operation_id")
        _require_capability(self.capability)
        if not self.members or not all(isinstance(item, OperationMember) for item in self.members):
            raise ValueError("operation members are invalid")
        if not self.techniques or not all(
            isinstance(item, TechniqueEvidence) for item in self.techniques
        ):
            raise ValueError("operation techniques are invalid")
        if self.stages != OPERATION_STAGES:
            raise ValueError("operation stages must match the V-One common language")
        roles = [member.role for member in self.members]
        missing_roles = sorted(set(MEMBER_ROLES) - set(roles))
        if missing_roles:
            raise ValueError(f"operation members are missing required roles: {missing_roles}")
        if len(roles) != len(set(roles)):
            raise ValueError("operation member roles must be unique")
        if len([member.member_id for member in self.members]) != len(
            {member.member_id for member in self.members}
        ):
            raise ValueError("operation member identities must be unique")
        technique_roles = {technique.technique_role for technique in self.techniques}
        missing_technique_roles = sorted(set(TECHNIQUE_ROLES) - technique_roles)
        if missing_technique_roles:
            raise ValueError(
                f"operation techniques are missing required roles: {missing_technique_roles}"
            )
        if self.semantics_digest != _digest(self._claims_without_digest(), "semantics_digest"):
            raise ValueError("semantics_digest does not match operation semantics")

    @classmethod
    def create(
        cls,
        *,
        operation_id: str,
        capability: str,
        members: tuple[OperationMember, ...],
        techniques: tuple[TechniqueEvidence, ...],
    ) -> Self:
        ordered_members = tuple(sorted(members, key=lambda item: item.role))
        ordered_techniques = tuple(sorted(techniques, key=lambda item: item.name))
        claims = {
            "schema_version": SCHEMA_VERSION,
            "semantics_type": OPERATION_SEMANTICS_TYPE,
            "operation_id": operation_id,
            "capability": capability,
            "members": [member.to_dict() for member in ordered_members],
            "stages": list(OPERATION_STAGES),
            "techniques": [technique.to_dict() for technique in ordered_techniques],
        }
        return cls(
            operation_id=operation_id,
            capability=capability,
            members=ordered_members,
            stages=OPERATION_STAGES,
            techniques=ordered_techniques,
            semantics_digest=_digest(claims, "semantics_digest"),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        expected = {
            "schema_version",
            "semantics_type",
            "operation_id",
            "capability",
            "members",
            "stages",
            "techniques",
            "semantics_digest",
        }
        if set(value) != expected:
            raise ValueError("operation semantics fields are invalid")
        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError("schema_version is unsupported")
        if value["semantics_type"] != OPERATION_SEMANTICS_TYPE:
            raise ValueError("semantics_type is unsupported")
        raw_members = value["members"]
        raw_techniques = value["techniques"]
        if not isinstance(raw_members, list):
            raise ValueError("members must be an array")
        if not isinstance(raw_techniques, list):
            raise ValueError("techniques must be an array")
        semantics = cls.create(
            operation_id=value["operation_id"],
            capability=value["capability"],
            members=tuple(_member_from_dict(item) for item in raw_members),
            techniques=tuple(_technique_from_dict(item) for item in raw_techniques),
        )
        supplied_digest = _require_digest(value["semantics_digest"], field="semantics_digest")
        if supplied_digest != semantics.semantics_digest:
            raise ValueError("semantics_digest does not match operation semantics")
        if value["stages"] != list(OPERATION_STAGES):
            raise ValueError("operation stages must match the V-One common language")
        return semantics

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "semantics_type": OPERATION_SEMANTICS_TYPE,
            "operation_id": self.operation_id,
            "capability": self.capability,
            "members": [member.to_dict() for member in self.members],
            "stages": list(self.stages),
            "techniques": [technique.to_dict() for technique in self.techniques],
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["semantics_digest"] = self.semantics_digest
        return payload


def _member_from_dict(value: object) -> OperationMember:
    if not isinstance(value, dict) or set(value) != {
        "role",
        "member_id",
        "purpose",
        "authority",
    }:
        raise ValueError("member fields are invalid")
    member = OperationMember(role=value["role"], member_id=value["member_id"])
    if value["purpose"] != _MEMBER_PURPOSES[member.role]:
        raise ValueError("member purpose does not match the V-One common language")
    if value["authority"] != _MEMBER_AUTHORITY[member.role]:
        raise ValueError("member authority does not match the V-One common language")
    return member


def _technique_from_dict(value: object) -> TechniqueEvidence:
    if not isinstance(value, dict) or set(value) != {
        "name",
        "technique_role",
        "source_authority",
        "v_one_boundary",
    }:
        raise ValueError("technique fields are invalid")
    return TechniqueEvidence(
        name=value["name"],
        technique_role=value["technique_role"],
        source_authority=value["source_authority"],
        v_one_boundary=value["v_one_boundary"],
    )


def _digest(value: dict[str, Any], digest_field: str) -> str:
    return hashlib.sha256(
        canonical_json({key: item for key, item in value.items() if key != digest_field}).encode(
            "utf-8"
        )
    ).hexdigest()


def _require_identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_capability(value: object) -> str:
    text = _require_identifier(value, field="capability")
    if "/v" not in text:
        raise ValueError("capability must include an explicit version")
    return text