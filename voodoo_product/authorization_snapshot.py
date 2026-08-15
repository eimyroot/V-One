from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json
from .execution_contract import (
    REQUIRED_EXECUTION_PERMISSION,
    ApprovalEvidenceSet,
    ExecutionTarget,
)

SCHEMA_VERSION = 1
AUTHORIZATION_SNAPSHOT_TYPE = "authorization-snapshot/v1"
PAYLOAD_DIGEST_SCHEME = "request-payload/v1"

_DIRECT_FIELDS = frozenset(
    {
        "schema_version",
        "snapshot_type",
        "snapshot_id",
        "execution_id",
        "request_id",
        "review_content_sha256",
        "actor_id",
        "workspace_id",
        "environment",
        "capability",
        "capability_definition_identity",
        "payload_digest",
        "payload_digest_scheme",
        "target_kind",
        "target_digest",
        "execution_target_identity",
        "policy_version",
        "policy_identity",
        "approval_set_digest",
        "approval_evidence_identity",
        "approval_valid_until",
        "required_permission",
        "issuance_timestamp_source_identity",
        "authorized_at",
        "authorization_source_revision",
        "snapshot_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
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


def _require_string(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_timestamp(value: object, *, field: str) -> tuple[str, datetime]:
    text = _require_string(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return text, parsed


@dataclass(frozen=True, slots=True)
class AuthorizationSnapshot:
    """Immutable snapshot contract.

    This value object validates deterministic structure and cross-contract bindings only. It does
    not prove that capability, policy, permission, approval, or target-authority gates succeeded.
    Those facts must be established by an authoritative V-One snapshot creator before persistence.
    """

    snapshot_id: str
    execution_id: str
    request_id: str
    review_content_sha256: str
    actor_id: str
    workspace_id: str
    environment: str
    capability: str
    capability_definition_identity: str
    payload_digest: str
    payload_digest_scheme: str
    execution_target_identity: str
    policy_version: str
    policy_identity: str
    approval_evidence_identity: str
    issuance_timestamp_source_identity: str
    authorized_at: str
    authorization_source_revision: str
    execution_target: ExecutionTarget
    approval_evidence: ApprovalEvidenceSet
    snapshot_digest: str

    def __post_init__(self) -> None:
        for field in (
            "snapshot_id",
            "execution_id",
            "request_id",
            "actor_id",
            "workspace_id",
            "capability_definition_identity",
            "execution_target_identity",
            "policy_identity",
            "approval_evidence_identity",
            "issuance_timestamp_source_identity",
            "authorization_source_revision",
        ):
            _require_string(getattr(self, field), field=field)
        _require_digest(self.review_content_sha256, field="review_content_sha256")
        _require_digest(self.payload_digest, field="payload_digest")
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        if self.payload_digest_scheme != PAYLOAD_DIGEST_SCHEME:
            raise ValueError("payload_digest_scheme is unsupported")
        if not isinstance(self.execution_target, ExecutionTarget):
            raise ValueError("execution_target is invalid")
        if not isinstance(self.approval_evidence, ApprovalEvidenceSet):
            raise ValueError("approval_evidence is invalid")

        authorized_at, authorized_at_value = _require_timestamp(
            self.authorized_at,
            field="authorized_at",
        )
        _, approval_valid_until = _require_timestamp(
            self.approval_evidence.approval_valid_until,
            field="approval_valid_until",
        )
        if authorized_at_value > approval_valid_until:
            raise ValueError("authorization occurs after approval validity")
        for approval in self.approval_evidence.approvals:
            _, approved_at = _require_timestamp(approval.approved_at, field="approved_at")
            if approved_at > authorized_at_value:
                raise ValueError("approval occurs after authorization")

        bindings = {
            "request_id": (self.approval_evidence.request_id, self.request_id),
            "payload_digest": (self.approval_evidence.payload_digest, self.payload_digest),
            "target_digest": (
                self.approval_evidence.target_digest,
                self.execution_target.target_digest,
            ),
            "capability": (self.approval_evidence.capability, self.capability),
            "policy_version": (self.approval_evidence.policy_version, self.policy_version),
        }
        mismatches = [
            field for field, (actual, expected) in bindings.items() if actual != expected
        ]
        if mismatches:
            raise ValueError(
                f"authorization snapshot cross-contract bindings mismatch: {sorted(mismatches)}"
            )

        _require_digest(self.snapshot_digest, field="snapshot_digest")
        if self.snapshot_digest != _digest(self._claims_without_digest()):
            raise ValueError("snapshot_digest does not match snapshot content")
        if authorized_at != self.authorized_at:
            raise ValueError("authorized_at is not canonical")

    @property
    def target_kind(self) -> str:
        return self.execution_target.target_kind

    @property
    def target_digest(self) -> str:
        return self.execution_target.target_digest

    @property
    def approval_set_digest(self) -> str:
        return self.approval_evidence.approval_set_digest

    @property
    def approval_valid_until(self) -> str:
        return self.approval_evidence.approval_valid_until

    @property
    def execution_target_json(self) -> str:
        return canonical_json(self.execution_target.to_dict())

    @property
    def approval_evidence_json(self) -> str:
        return canonical_json(self.approval_evidence.to_dict())

    @property
    def idempotency_binding_digest(self) -> str:
        claims = self._claims_without_digest().copy()
        for field in ("snapshot_id", "execution_id", "authorized_at"):
            claims.pop(field)
        return _digest(claims)

    @classmethod
    def create(
        cls,
        *,
        snapshot_id: str,
        execution_id: str,
        request_id: str,
        review_content_sha256: str,
        actor_id: str,
        workspace_id: str,
        environment: str,
        capability: str,
        capability_definition_identity: str,
        payload_digest: str,
        payload_digest_scheme: str,
        execution_target_identity: str,
        policy_version: str,
        policy_identity: str,
        approval_evidence_identity: str,
        issuance_timestamp_source_identity: str,
        authorized_at: str,
        authorization_source_revision: str,
        execution_target: ExecutionTarget,
        approval_evidence: ApprovalEvidenceSet,
    ) -> Self:
        if not isinstance(execution_target, ExecutionTarget):
            raise ValueError("execution_target is invalid")
        if not isinstance(approval_evidence, ApprovalEvidenceSet):
            raise ValueError("approval_evidence is invalid")
        values = {
            "snapshot_id": snapshot_id,
            "execution_id": execution_id,
            "request_id": request_id,
            "review_content_sha256": review_content_sha256,
            "actor_id": actor_id,
            "workspace_id": workspace_id,
            "environment": environment,
            "capability": capability,
            "capability_definition_identity": capability_definition_identity,
            "payload_digest": payload_digest,
            "payload_digest_scheme": payload_digest_scheme,
            "execution_target_identity": execution_target_identity,
            "policy_version": policy_version,
            "policy_identity": policy_identity,
            "approval_evidence_identity": approval_evidence_identity,
            "issuance_timestamp_source_identity": issuance_timestamp_source_identity,
            "authorized_at": authorized_at,
            "authorization_source_revision": authorization_source_revision,
            "execution_target": execution_target,
            "approval_evidence": approval_evidence,
        }
        claims = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_type": AUTHORIZATION_SNAPSHOT_TYPE,
            "snapshot_id": snapshot_id,
            "execution_id": execution_id,
            "request_id": request_id,
            "review_content_sha256": review_content_sha256,
            "actor_id": actor_id,
            "workspace_id": workspace_id,
            "environment": environment,
            "capability": capability,
            "capability_definition_identity": capability_definition_identity,
            "payload_digest": payload_digest,
            "payload_digest_scheme": payload_digest_scheme,
            "target_kind": execution_target.target_kind,
            "target_digest": execution_target.target_digest,
            "execution_target_identity": execution_target_identity,
            "policy_version": policy_version,
            "policy_identity": policy_identity,
            "approval_set_digest": approval_evidence.approval_set_digest,
            "approval_evidence_identity": approval_evidence_identity,
            "approval_valid_until": approval_evidence.approval_valid_until,
            "required_permission": REQUIRED_EXECUTION_PERMISSION,
            "issuance_timestamp_source_identity": issuance_timestamp_source_identity,
            "authorized_at": authorized_at,
            "authorization_source_revision": authorization_source_revision,
        }
        return cls(**values, snapshot_digest=_digest(claims))

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        execution_target: ExecutionTarget,
        approval_evidence: ApprovalEvidenceSet,
    ) -> Self:
        if not isinstance(value, Mapping):
            raise ValueError("authorization-snapshot/v1 must be an object")
        actual = frozenset(value)
        if actual != _DIRECT_FIELDS:
            missing = sorted(_DIRECT_FIELDS - actual)
            unknown = sorted(actual - _DIRECT_FIELDS)
            raise ValueError(
                "authorization-snapshot/v1 fields are invalid; "
                f"missing={missing}, unknown={unknown}"
            )
        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError("schema_version is unsupported")
        if value["snapshot_type"] != AUTHORIZATION_SNAPSHOT_TYPE:
            raise ValueError("snapshot_type is unsupported")
        if value["required_permission"] != REQUIRED_EXECUTION_PERMISSION:
            raise ValueError("required_permission must be execution.run")

        created = cls.create(
            snapshot_id=value["snapshot_id"],
            execution_id=value["execution_id"],
            request_id=value["request_id"],
            review_content_sha256=value["review_content_sha256"],
            actor_id=value["actor_id"],
            workspace_id=value["workspace_id"],
            environment=value["environment"],
            capability=value["capability"],
            capability_definition_identity=value["capability_definition_identity"],
            payload_digest=value["payload_digest"],
            payload_digest_scheme=value["payload_digest_scheme"],
            execution_target_identity=value["execution_target_identity"],
            policy_version=value["policy_version"],
            policy_identity=value["policy_identity"],
            approval_evidence_identity=value["approval_evidence_identity"],
            issuance_timestamp_source_identity=value["issuance_timestamp_source_identity"],
            authorized_at=value["authorized_at"],
            authorization_source_revision=value["authorization_source_revision"],
            execution_target=execution_target,
            approval_evidence=approval_evidence,
        )
        expected = created.to_dict()
        for field, supplied in value.items():
            if expected[field] != supplied:
                raise ValueError(f"{field} does not match authorization snapshot content")
        return created

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "snapshot_type": AUTHORIZATION_SNAPSHOT_TYPE,
            "snapshot_id": self.snapshot_id,
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "review_content_sha256": self.review_content_sha256,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "capability": self.capability,
            "capability_definition_identity": self.capability_definition_identity,
            "payload_digest": self.payload_digest,
            "payload_digest_scheme": self.payload_digest_scheme,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "execution_target_identity": self.execution_target_identity,
            "policy_version": self.policy_version,
            "policy_identity": self.policy_identity,
            "approval_set_digest": self.approval_set_digest,
            "approval_evidence_identity": self.approval_evidence_identity,
            "approval_valid_until": self.approval_valid_until,
            "required_permission": REQUIRED_EXECUTION_PERMISSION,
            "issuance_timestamp_source_identity": self.issuance_timestamp_source_identity,
            "authorized_at": self.authorized_at,
            "authorization_source_revision": self.authorization_source_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "snapshot_digest": self.snapshot_digest}
