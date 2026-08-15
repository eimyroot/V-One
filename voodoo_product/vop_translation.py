from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final, Self

from .evidence_primitives import canonical_json

SEMANTIC_MAPPING_TYPE: Final = "vop-semantic-mapping/v1"
SEMANTIC_PROFILE_TYPE: Final = "vop-semantic-equivalence-profile/v1"
SEMANTIC_ASSESSMENT_TYPE: Final = "vop-semantic-equivalence-assessment/v1"

SEMANTIC_DIMENSIONS: Final = (
    "semantic_input",
    "authoritative_target",
    "side_effect",
    "permission",
    "approval",
    "idempotency",
    "receipt",
    "verification",
    "evidence",
)

SEMANTICALLY_EQUIVALENT: Final = "SEMANTICALLY_EQUIVALENT"
NEW_CAPABILITY: Final = "NEW_CAPABILITY"


@dataclass(frozen=True, slots=True)
class ProviderSemanticMapping:
    provider: str
    external_operation: str
    transport: str
    capability: str
    requested_target: dict[str, Any]
    expected_post_state: dict[str, Any]
    mapping_digest: str

    def __post_init__(self) -> None:
        _require_text(self.provider, field="provider")
        _require_text(self.external_operation, field="external_operation")
        _require_text(self.transport, field="transport")
        _require_capability(self.capability)
        _require_mapping(self.requested_target, field="requested_target")
        _require_mapping(self.expected_post_state, field="expected_post_state")
        if self.mapping_digest != _digest(self._claims_without_digest()):
            raise ValueError("mapping_digest does not match semantic mapping")

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        external_operation: str,
        transport: str,
        capability: str,
        requested_target: dict[str, Any],
        expected_post_state: dict[str, Any],
    ) -> Self:
        claims = {
            "mapping_type": SEMANTIC_MAPPING_TYPE,
            "provider": provider,
            "external_operation": external_operation,
            "transport": transport,
            "capability": capability,
            "requested_target": requested_target,
            "expected_post_state": expected_post_state,
        }
        return cls(
            provider=provider,
            external_operation=external_operation,
            transport=transport,
            capability=capability,
            requested_target=requested_target,
            expected_post_state=expected_post_state,
            mapping_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "mapping_type": SEMANTIC_MAPPING_TYPE,
            "provider": self.provider,
            "external_operation": self.external_operation,
            "transport": self.transport,
            "capability": self.capability,
            "requested_target": self.requested_target,
            "expected_post_state": self.expected_post_state,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["mapping_digest"] = self.mapping_digest
        return payload


@dataclass(frozen=True, slots=True)
class SemanticEquivalenceProfile:
    capability: str
    implementation_identity: str
    semantic_input: str
    authoritative_target: str
    side_effect: str
    permission: str
    approval: str
    idempotency: str
    receipt: str
    verification: str
    evidence: str
    profile_digest: str

    def __post_init__(self) -> None:
        _require_capability(self.capability)
        _require_text(self.implementation_identity, field="implementation_identity")
        for field in SEMANTIC_DIMENSIONS:
            _require_text(getattr(self, field), field=field)
        if self.profile_digest != _digest(self._claims_without_digest()):
            raise ValueError("profile_digest does not match semantic profile")

    @classmethod
    def create(
        cls,
        *,
        capability: str,
        implementation_identity: str,
        semantic_input: str,
        authoritative_target: str,
        side_effect: str,
        permission: str,
        approval: str,
        idempotency: str,
        receipt: str,
        verification: str,
        evidence: str,
    ) -> Self:
        claims = {
            "profile_type": SEMANTIC_PROFILE_TYPE,
            "capability": capability,
            "implementation_identity": implementation_identity,
            "semantic_input": semantic_input,
            "authoritative_target": authoritative_target,
            "side_effect": side_effect,
            "permission": permission,
            "approval": approval,
            "idempotency": idempotency,
            "receipt": receipt,
            "verification": verification,
            "evidence": evidence,
        }
        return cls(
            capability=capability,
            implementation_identity=implementation_identity,
            semantic_input=semantic_input,
            authoritative_target=authoritative_target,
            side_effect=side_effect,
            permission=permission,
            approval=approval,
            idempotency=idempotency,
            receipt=receipt,
            verification=verification,
            evidence=evidence,
            profile_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "profile_type": SEMANTIC_PROFILE_TYPE,
            "capability": self.capability,
            "implementation_identity": self.implementation_identity,
            **{field: getattr(self, field) for field in SEMANTIC_DIMENSIONS},
        }

    def semantic_vector(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in SEMANTIC_DIMENSIONS}


@dataclass(frozen=True, slots=True)
class SemanticEquivalenceAssessment:
    current_profile_digest: str
    candidate_profile_digest: str
    result: str
    mismatched_dimensions: tuple[str, ...]
    assessment_digest: str

    def __post_init__(self) -> None:
        _require_sha256(self.current_profile_digest, field="current_profile_digest")
        _require_sha256(self.candidate_profile_digest, field="candidate_profile_digest")
        if self.result not in {SEMANTICALLY_EQUIVALENT, NEW_CAPABILITY}:
            raise ValueError("semantic equivalence result is unsupported")
        if any(item not in SEMANTIC_DIMENSIONS for item in self.mismatched_dimensions):
            raise ValueError("mismatched semantic dimension is unsupported")
        if self.result == SEMANTICALLY_EQUIVALENT and self.mismatched_dimensions:
            raise ValueError("equivalent assessment cannot contain mismatches")
        if self.result == NEW_CAPABILITY and not self.mismatched_dimensions:
            raise ValueError("new-capability assessment must explain semantic mismatches")
        if self.assessment_digest != _digest(self._claims_without_digest()):
            raise ValueError("assessment_digest does not match semantic assessment")

    @classmethod
    def compare(
        cls,
        current: SemanticEquivalenceProfile,
        candidate: SemanticEquivalenceProfile,
    ) -> Self:
        mismatches = tuple(
            field
            for field in SEMANTIC_DIMENSIONS
            if current.semantic_vector()[field] != candidate.semantic_vector()[field]
        )
        if current.capability != candidate.capability:
            # Capability identity itself is semantic. A different capability cannot be equivalent.
            mismatches = ("side_effect",) if not mismatches else mismatches
        result = SEMANTICALLY_EQUIVALENT if not mismatches else NEW_CAPABILITY
        claims = {
            "assessment_type": SEMANTIC_ASSESSMENT_TYPE,
            "current_profile_digest": current.profile_digest,
            "candidate_profile_digest": candidate.profile_digest,
            "result": result,
            "mismatched_dimensions": list(mismatches),
        }
        return cls(
            current_profile_digest=current.profile_digest,
            candidate_profile_digest=candidate.profile_digest,
            result=result,
            mismatched_dimensions=mismatches,
            assessment_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "assessment_type": SEMANTIC_ASSESSMENT_TYPE,
            "current_profile_digest": self.current_profile_digest,
            "candidate_profile_digest": self.candidate_profile_digest,
            "result": self.result,
            "mismatched_dimensions": list(self.mismatched_dimensions),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._claims_without_digest()
        payload["assessment_digest"] = self.assessment_digest
        return payload


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{field} is invalid")
    return value


def _require_capability(value: object) -> str:
    text = _require_text(value, field="capability")
    if "/v" not in text:
        raise ValueError("capability must include an explicit version")
    return text


def _require_mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    canonical_json(value)
    return value


def _require_sha256(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value
