from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Self

from .approval_certificate import ApprovalCertificate
from .capability_registry import CapabilityActivation, CapabilityDefinition
from .evidence_primitives import canonical_json
from .permission_authority import PermissionDecision
from .policy_authority import PolicyRevision
from .target_binding import TargetBinding
from .trusted_clock import ClockWitness

AUTHORITY_WITNESS_SET_TYPE: Final = "authority-witness-set/v1"


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
class AuthorityWitnessSet:
    permission_decision_digest: str
    policy_identity: str
    capability_definition_identity: str
    capability_activation_digest: str
    target_binding_digest: str
    approval_certificate_digest: str
    clock_witness_digest: str
    revocation_epoch: int
    witness_set_digest: str

    def __post_init__(self) -> None:
        for field in (
            "permission_decision_digest",
            "policy_identity",
            "capability_definition_identity",
            "capability_activation_digest",
            "target_binding_digest",
            "approval_certificate_digest",
            "clock_witness_digest",
            "witness_set_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if type(self.revocation_epoch) is not int or self.revocation_epoch < 0:
            raise ValueError("revocation_epoch must be non-negative")
        if self.witness_set_digest != _digest(self._claims_without_digest()):
            raise ValueError("witness_set_digest does not match authority witnesses")

    @classmethod
    def create(
        cls,
        *,
        permission_decision: PermissionDecision,
        policy_revision: PolicyRevision,
        capability_definition: CapabilityDefinition,
        capability_activation: CapabilityActivation,
        target_binding: TargetBinding,
        approval_certificate: ApprovalCertificate,
        clock_witness: ClockWitness,
        revocation_epoch: int,
    ) -> Self:
        if not isinstance(permission_decision, PermissionDecision):
            raise ValueError("permission_decision is invalid")
        if not permission_decision.granted:
            raise PermissionError("permission decision is denied")
        if not isinstance(policy_revision, PolicyRevision):
            raise ValueError("policy_revision is invalid")
        if not isinstance(capability_definition, CapabilityDefinition):
            raise ValueError("capability_definition is invalid")
        if not isinstance(capability_activation, CapabilityActivation):
            raise ValueError("capability_activation is invalid")
        if capability_activation.revoked:
            raise PermissionError("capability activation is revoked")
        if (
            capability_activation.capability_definition_identity
            != capability_definition.definition_identity
        ):
            raise ValueError("capability activation definition binding mismatch")
        if not isinstance(target_binding, TargetBinding):
            raise ValueError("target_binding is invalid")
        if (
            target_binding.capability_definition_identity
            != capability_definition.definition_identity
        ):
            raise ValueError("target binding capability definition mismatch")
        if not isinstance(approval_certificate, ApprovalCertificate):
            raise ValueError("approval_certificate is invalid")
        if approval_certificate.policy_identity != policy_revision.policy_identity:
            raise ValueError("approval certificate policy identity mismatch")
        if approval_certificate.policy_version != policy_revision.policy_version:
            raise ValueError("approval certificate policy version mismatch")
        if not isinstance(clock_witness, ClockWitness):
            raise ValueError("clock_witness is invalid")
        if permission_decision.environment != clock_witness.environment:
            raise ValueError("permission and clock environment mismatch")
        if permission_decision.environment not in capability_activation.enabled_environments:
            raise PermissionError("capability is not active for permission environment")
        if type(revocation_epoch) is not int or revocation_epoch < 0:
            raise ValueError("revocation_epoch must be non-negative")

        claims = {
            "witness_set_type": AUTHORITY_WITNESS_SET_TYPE,
            "permission_decision_digest": permission_decision.decision_digest,
            "policy_identity": policy_revision.policy_identity,
            "capability_definition_identity": capability_definition.definition_identity,
            "capability_activation_digest": capability_activation.activation_digest,
            "target_binding_digest": target_binding.binding_digest,
            "approval_certificate_digest": approval_certificate.certificate_digest,
            "clock_witness_digest": clock_witness.witness_digest,
            "revocation_epoch": revocation_epoch,
        }
        return cls(
            permission_decision_digest=permission_decision.decision_digest,
            policy_identity=policy_revision.policy_identity,
            capability_definition_identity=capability_definition.definition_identity,
            capability_activation_digest=capability_activation.activation_digest,
            target_binding_digest=target_binding.binding_digest,
            approval_certificate_digest=approval_certificate.certificate_digest,
            clock_witness_digest=clock_witness.witness_digest,
            revocation_epoch=revocation_epoch,
            witness_set_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "witness_set_type": AUTHORITY_WITNESS_SET_TYPE,
            "permission_decision_digest": self.permission_decision_digest,
            "policy_identity": self.policy_identity,
            "capability_definition_identity": self.capability_definition_identity,
            "capability_activation_digest": self.capability_activation_digest,
            "target_binding_digest": self.target_binding_digest,
            "approval_certificate_digest": self.approval_certificate_digest,
            "clock_witness_digest": self.clock_witness_digest,
            "revocation_epoch": self.revocation_epoch,
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["witness_set_digest"] = self.witness_set_digest
        return value
