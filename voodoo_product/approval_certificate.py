from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Self

from .evidence_primitives import canonical_json
from .execution_contract import ApprovalEvidenceSet
from .policy_authority import PolicyRevision

APPROVAL_CERTIFICATE_TYPE: Final = "approval-certificate/v1"


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class ApprovalCertificate:
    request_id: str
    review_content_sha256: str
    policy_version: str
    policy_identity: str
    approval_evidence: ApprovalEvidenceSet
    certificate_digest: str

    def __post_init__(self) -> None:
        _require_digest(self.review_content_sha256, field="review_content_sha256")
        if not isinstance(self.approval_evidence, ApprovalEvidenceSet):
            raise ValueError("approval_evidence is invalid")
        if self.request_id != self.approval_evidence.request_id:
            raise ValueError("approval certificate request binding mismatch")
        if self.policy_version != self.approval_evidence.policy_version:
            raise ValueError("approval certificate policy version mismatch")
        _require_digest(self.policy_identity, field="policy_identity")
        _require_digest(self.certificate_digest, field="certificate_digest")
        if self.certificate_digest != _digest(self._claims_without_digest()):
            raise ValueError("certificate_digest does not match approval certificate")

    @classmethod
    def create(
        cls,
        *,
        review_content_sha256: str,
        policy_revision: PolicyRevision,
        approval_evidence: ApprovalEvidenceSet,
    ) -> Self:
        if not isinstance(policy_revision, PolicyRevision):
            raise ValueError("policy_revision is invalid")
        if not isinstance(approval_evidence, ApprovalEvidenceSet):
            raise ValueError("approval_evidence is invalid")
        if approval_evidence.policy_version != policy_revision.policy_version:
            raise ValueError("approval evidence does not use supplied policy revision")
        claims = {
            "certificate_type": APPROVAL_CERTIFICATE_TYPE,
            "request_id": approval_evidence.request_id,
            "review_content_sha256": review_content_sha256,
            "policy_version": policy_revision.policy_version,
            "policy_identity": policy_revision.policy_identity,
            "approval_evidence": approval_evidence.to_dict(),
        }
        return cls(
            request_id=approval_evidence.request_id,
            review_content_sha256=review_content_sha256,
            policy_version=policy_revision.policy_version,
            policy_identity=policy_revision.policy_identity,
            approval_evidence=approval_evidence,
            certificate_digest=_digest(claims),
        )

    @property
    def approval_valid_until(self) -> str:
        return self.approval_evidence.approval_valid_until

    @property
    def approval_set_digest(self) -> str:
        return self.approval_evidence.approval_set_digest

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "certificate_type": APPROVAL_CERTIFICATE_TYPE,
            "request_id": self.request_id,
            "review_content_sha256": self.review_content_sha256,
            "policy_version": self.policy_version,
            "policy_identity": self.policy_identity,
            "approval_evidence": self.approval_evidence.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["certificate_digest"] = self.certificate_digest
        return value
