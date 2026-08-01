from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

from .evidence_primitives import canonical_json

SCHEMA_VERSION = 1
EXECUTION_TARGET_TYPE = "execution-target/v1"
APPROVAL_EVIDENCE_SET_TYPE = "approval-evidence-set/v1"
EXECUTION_GRANT_TYPE = "execution-grant/v1"
EXECUTION_RECEIPT_TYPE = "execution-receipt/v1"
REQUIRED_EXECUTION_PERMISSION = "execution.run"
ONE_TIME_USE = "ONE_TIME"
MAX_GRANT_TTL_SECONDS = 300

_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,255}")
_POLICY_VERSION_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,255}")
_CAPABILITY_PATTERN = re.compile(
    r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*/v[1-9][0-9]*"
)
_EXECUTION_STATUSES = frozenset(
    {"SUCCEEDED", "FAILED", "INTERRUPTED", "TIMED_OUT", "CANCELLED", "REJECTED"}
)
_EXECUTION_OUTCOMES = frozenset(
    {
        "EXPECTED_EFFECT_VERIFIED",
        "EXPECTED_EFFECT_NOT_VERIFIED",
        "INDETERMINATE",
    }
)
_POSTCONDITION_STATUSES = frozenset({"PASSED", "FAILED", "NOT_RUN", "INDETERMINATE"})
_ATTEMPTED_EXECUTION_STATUSES = _EXECUTION_STATUSES - {"REJECTED"}


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


def _require_string(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_identifier(value: object, *, field: str) -> str:
    text = _require_string(value, field=field)
    if _IDENTIFIER_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field} is invalid")
    return text


def _require_capability(value: object) -> str:
    capability = _require_string(value, field="capability")
    if _CAPABILITY_PATTERN.fullmatch(capability) is None:
        raise ValueError("capability is invalid")
    return capability


def _require_policy_version(value: object) -> str:
    policy_version = _require_string(value, field="policy_version")
    if _POLICY_VERSION_PATTERN.fullmatch(policy_version) is None:
        raise ValueError("policy_version is invalid")
    return policy_version


def _require_digest(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _DIGEST_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
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


def _require_json_value(value: object, *, field: str, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError(f"{field} exceeds the nesting limit")
    if value is None or type(value) in {bool, int, str}:
        return
    if isinstance(value, list):
        for item in value:
            _require_json_value(item, field=field, depth=depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field} keys must be strings")
            _require_json_value(item, field=field, depth=depth + 1)
        return
    raise ValueError(f"{field} contains an unsupported JSON value")


def _require_schema_and_type(
    *,
    schema_version: object,
    actual_type: object,
    expected_type: str,
    type_field: str,
) -> None:
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        raise ValueError("schema_version is unsupported")
    if actual_type != expected_type:
        raise ValueError(f"{type_field} is unsupported")


@dataclass(frozen=True, slots=True)
class ExecutionTarget:
    target_kind: str
    _target_claims_json: str
    target_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.target_kind, field="target_kind")
        try:
            claims = json.loads(self._target_claims_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("target_claims are invalid") from exc
        if not isinstance(claims, dict):
            raise ValueError("target_claims must be an object")
        _require_json_value(claims, field="target_claims")
        if self._target_claims_json != canonical_json(claims):
            raise ValueError("target_claims are not canonical")
        _require_digest(self.target_digest, field="target_digest")
        expected = _digest(
            {
                "schema_version": SCHEMA_VERSION,
                "target_type": EXECUTION_TARGET_TYPE,
                "target_kind": self.target_kind,
                "target_claims": claims,
            }
        )
        if self.target_digest != expected:
            raise ValueError("target_digest does not match target claims")

    @classmethod
    def create(cls, *, target_kind: str, target_claims: Mapping[str, Any]) -> Self:
        _require_identifier(target_kind, field="target_kind")
        if not isinstance(target_claims, Mapping):
            raise ValueError("target_claims must be an object")
        claims = dict(target_claims)
        _require_json_value(claims, field="target_claims")
        claims_json = canonical_json(claims)
        without_digest = {
            "schema_version": SCHEMA_VERSION,
            "target_type": EXECUTION_TARGET_TYPE,
            "target_kind": target_kind,
            "target_claims": json.loads(claims_json),
        }
        return cls(target_kind, claims_json, _digest(without_digest))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "target_type",
                "target_kind",
                "target_claims",
                "target_digest",
            }
        )
        _require_exact_fields(value, expected, contract=EXECUTION_TARGET_TYPE)
        _require_schema_and_type(
            schema_version=value["schema_version"],
            actual_type=value["target_type"],
            expected_type=EXECUTION_TARGET_TYPE,
            type_field="target_type",
        )
        target = cls.create(
            target_kind=_require_identifier(value["target_kind"], field="target_kind"),
            target_claims=value["target_claims"],
        )
        supplied_digest = _require_digest(value["target_digest"], field="target_digest")
        if supplied_digest != target.target_digest:
            raise ValueError("target_digest does not match target claims")
        return target

    @property
    def target_claims(self) -> dict[str, Any]:
        return json.loads(self._target_claims_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "target_type": EXECUTION_TARGET_TYPE,
            "target_kind": self.target_kind,
            "target_claims": self.target_claims,
            "target_digest": self.target_digest,
        }


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_id: str
    approver_id: str
    decision: str
    approved_at: str

    def __post_init__(self) -> None:
        _require_identifier(self.approval_id, field="approval_id")
        _require_identifier(self.approver_id, field="approver_id")
        if self.decision != "APPROVED":
            raise ValueError("approval record decision must be APPROVED")
        _require_timestamp(self.approved_at, field="approved_at")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset({"approval_id", "approver_id", "decision", "approved_at"})
        _require_exact_fields(value, expected, contract="approval-record/v1")
        return cls(
            approval_id=value["approval_id"],
            approver_id=value["approver_id"],
            decision=value["decision"],
            approved_at=value["approved_at"],
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "approval_id": self.approval_id,
            "approver_id": self.approver_id,
            "decision": self.decision,
            "approved_at": self.approved_at,
        }


@dataclass(frozen=True, slots=True)
class ApprovalEvidenceSet:
    request_id: str
    payload_digest: str
    target_digest: str
    capability: str
    policy_version: str
    approvals: tuple[ApprovalRecord, ...]
    approval_valid_until: str
    approval_set_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.request_id, field="request_id")
        _require_digest(self.payload_digest, field="payload_digest")
        _require_digest(self.target_digest, field="target_digest")
        _require_capability(self.capability)
        _require_policy_version(self.policy_version)
        _, valid_until = _require_timestamp(
            self.approval_valid_until,
            field="approval_valid_until",
        )
        if not self.approvals or not all(
            isinstance(item, ApprovalRecord) for item in self.approvals
        ):
            raise ValueError("approvals must contain approved records")
        expected_order = tuple(
            sorted(
                self.approvals,
                key=lambda item: (
                    item.approval_id,
                    item.approver_id,
                    item.approved_at,
                ),
            )
        )
        if self.approvals != expected_order:
            raise ValueError("approvals are not canonically ordered")
        approval_ids = [item.approval_id for item in self.approvals]
        approver_ids = [item.approver_id for item in self.approvals]
        if len(approval_ids) != len(set(approval_ids)):
            raise ValueError("approval IDs must be distinct")
        if len(approver_ids) != len(set(approver_ids)):
            raise ValueError("approver identities must be distinct")
        for approval in self.approvals:
            _, approved_at = _require_timestamp(approval.approved_at, field="approved_at")
            if approved_at > valid_until:
                raise ValueError("approval occurs after approval validity")
        _require_digest(self.approval_set_digest, field="approval_set_digest")
        expected = _digest(
            {
                "schema_version": SCHEMA_VERSION,
                "approval_set_type": APPROVAL_EVIDENCE_SET_TYPE,
                "request_id": self.request_id,
                "payload_digest": self.payload_digest,
                "target_digest": self.target_digest,
                "capability": self.capability,
                "policy_version": self.policy_version,
                "approvals": [item.to_dict() for item in self.approvals],
                "approval_valid_until": self.approval_valid_until,
            }
        )
        if self.approval_set_digest != expected:
            raise ValueError("approval_set_digest does not match approval evidence")

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        payload_digest: str,
        target_digest: str,
        capability: str,
        policy_version: str,
        approvals: Iterable[ApprovalRecord],
        approval_valid_until: str,
    ) -> Self:
        _require_identifier(request_id, field="request_id")
        _require_digest(payload_digest, field="payload_digest")
        _require_digest(target_digest, field="target_digest")
        _require_capability(capability)
        _require_policy_version(policy_version)
        valid_until, valid_until_value = _require_timestamp(
            approval_valid_until,
            field="approval_valid_until",
        )
        supplied_approvals = tuple(approvals)
        if not supplied_approvals or not all(
            isinstance(item, ApprovalRecord) for item in supplied_approvals
        ):
            raise ValueError("approvals must contain approved records")
        ordered = tuple(
            sorted(
                supplied_approvals,
                key=lambda item: (
                    item.approval_id,
                    item.approver_id,
                    item.approved_at,
                ),
            )
        )
        approval_ids = [item.approval_id for item in ordered]
        approver_ids = [item.approver_id for item in ordered]
        if len(approval_ids) != len(set(approval_ids)):
            raise ValueError("approval IDs must be distinct")
        if len(approver_ids) != len(set(approver_ids)):
            raise ValueError("approver identities must be distinct")
        for approval in ordered:
            _, approved_at = _require_timestamp(approval.approved_at, field="approved_at")
            if approved_at > valid_until_value:
                raise ValueError("approval occurs after approval validity")
        without_digest = {
            "schema_version": SCHEMA_VERSION,
            "approval_set_type": APPROVAL_EVIDENCE_SET_TYPE,
            "request_id": request_id,
            "payload_digest": payload_digest,
            "target_digest": target_digest,
            "capability": capability,
            "policy_version": policy_version,
            "approvals": [item.to_dict() for item in ordered],
            "approval_valid_until": valid_until,
        }
        return cls(
            request_id=request_id,
            payload_digest=payload_digest,
            target_digest=target_digest,
            capability=capability,
            policy_version=policy_version,
            approvals=ordered,
            approval_valid_until=valid_until,
            approval_set_digest=_digest(without_digest),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        expected = frozenset(
            {
                "schema_version",
                "approval_set_type",
                "request_id",
                "payload_digest",
                "target_digest",
                "capability",
                "policy_version",
                "approvals",
                "approval_valid_until",
                "approval_set_digest",
            }
        )
        _require_exact_fields(value, expected, contract=APPROVAL_EVIDENCE_SET_TYPE)
        _require_schema_and_type(
            schema_version=value["schema_version"],
            actual_type=value["approval_set_type"],
            expected_type=APPROVAL_EVIDENCE_SET_TYPE,
            type_field="approval_set_type",
        )
        raw_approvals = value["approvals"]
        if not isinstance(raw_approvals, list):
            raise ValueError("approvals must be an array")
        evidence = cls.create(
            request_id=value["request_id"],
            payload_digest=value["payload_digest"],
            target_digest=value["target_digest"],
            capability=value["capability"],
            policy_version=value["policy_version"],
            approvals=(ApprovalRecord.from_dict(item) for item in raw_approvals),
            approval_valid_until=value["approval_valid_until"],
        )
        supplied_digest = _require_digest(
            value["approval_set_digest"],
            field="approval_set_digest",
        )
        if supplied_digest != evidence.approval_set_digest:
            raise ValueError("approval_set_digest does not match approval evidence")
        return evidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "approval_set_type": APPROVAL_EVIDENCE_SET_TYPE,
            "request_id": self.request_id,
            "payload_digest": self.payload_digest,
            "target_digest": self.target_digest,
            "capability": self.capability,
            "policy_version": self.policy_version,
            "approvals": [item.to_dict() for item in self.approvals],
            "approval_valid_until": self.approval_valid_until,
            "approval_set_digest": self.approval_set_digest,
        }


@dataclass(frozen=True, slots=True)
class ExecutionGrant:
    grant_id: str
    execution_id: str
    request_id: str
    actor_id: str
    workspace_id: str
    environment: str
    capability: str
    target_kind: str
    target_digest: str
    payload_digest: str
    approval_set_digest: str
    policy_version: str
    required_permission: str
    issued_at: str
    expires_at: str
    use_semantics: str
    grant_digest: str

    def __post_init__(self) -> None:
        for field in (
            "grant_id",
            "execution_id",
            "request_id",
            "actor_id",
            "workspace_id",
            "environment",
            "target_kind",
        ):
            _require_identifier(getattr(self, field), field=field)
        _require_capability(self.capability)
        _require_digest(self.target_digest, field="target_digest")
        _require_digest(self.payload_digest, field="payload_digest")
        _require_digest(self.approval_set_digest, field="approval_set_digest")
        _require_policy_version(self.policy_version)
        if self.required_permission != REQUIRED_EXECUTION_PERMISSION:
            raise ValueError("required_permission must be execution.run")
        if self.use_semantics != ONE_TIME_USE:
            raise ValueError("use_semantics must be ONE_TIME")
        _, issued = _require_timestamp(self.issued_at, field="issued_at")
        _, expires = _require_timestamp(self.expires_at, field="expires_at")
        lifetime = (expires - issued).total_seconds()
        if lifetime <= 0:
            raise ValueError("grant TTL must be positive")
        if lifetime > MAX_GRANT_TTL_SECONDS:
            raise ValueError("grant TTL exceeds 300 seconds")
        _require_digest(self.grant_digest, field="grant_digest")
        without_digest = self.to_dict()
        without_digest.pop("grant_digest")
        if self.grant_digest != _digest(without_digest):
            raise ValueError("grant_digest does not match grant claims")

    @classmethod
    def create(
        cls,
        *,
        grant_id: str,
        execution_id: str,
        actor_id: str,
        workspace_id: str,
        environment: str,
        target: ExecutionTarget,
        approval_evidence: ApprovalEvidenceSet,
        issued_at: str,
        expires_at: str,
        required_permission: str = REQUIRED_EXECUTION_PERMISSION,
        use_semantics: str = ONE_TIME_USE,
    ) -> Self:
        for field, value in (
            ("grant_id", grant_id),
            ("execution_id", execution_id),
            ("actor_id", actor_id),
            ("workspace_id", workspace_id),
            ("environment", environment),
        ):
            _require_identifier(value, field=field)
        if not isinstance(target, ExecutionTarget):
            raise ValueError("target must be execution-target/v1")
        if not isinstance(approval_evidence, ApprovalEvidenceSet):
            raise ValueError("approval_evidence must be approval-evidence-set/v1")
        if required_permission != REQUIRED_EXECUTION_PERMISSION:
            raise ValueError("required_permission must be execution.run")
        if use_semantics != ONE_TIME_USE:
            raise ValueError("use_semantics must be ONE_TIME")
        issued_text, issued = _require_timestamp(issued_at, field="issued_at")
        expires_text, expires = _require_timestamp(expires_at, field="expires_at")
        lifetime = (expires - issued).total_seconds()
        if lifetime <= 0:
            raise ValueError("grant TTL must be positive")
        if lifetime > MAX_GRANT_TTL_SECONDS:
            raise ValueError("grant TTL exceeds 300 seconds")
        without_digest = {
            "schema_version": SCHEMA_VERSION,
            "grant_type": EXECUTION_GRANT_TYPE,
            "grant_id": grant_id,
            "execution_id": execution_id,
            "request_id": approval_evidence.request_id,
            "actor_id": actor_id,
            "workspace_id": workspace_id,
            "environment": environment,
            "capability": approval_evidence.capability,
            "target_kind": target.target_kind,
            "target_digest": target.target_digest,
            "payload_digest": approval_evidence.payload_digest,
            "approval_set_digest": approval_evidence.approval_set_digest,
            "policy_version": approval_evidence.policy_version,
            "required_permission": required_permission,
            "issued_at": issued_text,
            "expires_at": expires_text,
            "use_semantics": use_semantics,
        }
        claims = {
            key: item
            for key, item in without_digest.items()
            if key not in {"schema_version", "grant_type"}
        }
        grant = cls(**claims, grant_digest=_digest(without_digest))
        grant.validate_bindings(
            target=target,
            approval_evidence=approval_evidence,
        )
        return grant

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        """Parse structurally; authoritative use also requires validate_bindings."""

        expected = frozenset(
            {
                "schema_version",
                "grant_type",
                "grant_id",
                "execution_id",
                "request_id",
                "actor_id",
                "workspace_id",
                "environment",
                "capability",
                "target_kind",
                "target_digest",
                "payload_digest",
                "approval_set_digest",
                "policy_version",
                "required_permission",
                "issued_at",
                "expires_at",
                "use_semantics",
                "grant_digest",
            }
        )
        _require_exact_fields(value, expected, contract=EXECUTION_GRANT_TYPE)
        _require_schema_and_type(
            schema_version=value["schema_version"],
            actual_type=value["grant_type"],
            expected_type=EXECUTION_GRANT_TYPE,
            type_field="grant_type",
        )
        without_digest = {key: value[key] for key in expected if key != "grant_digest"}
        for field in (
            "grant_id",
            "execution_id",
            "request_id",
            "actor_id",
            "workspace_id",
            "environment",
            "target_kind",
        ):
            _require_identifier(value[field], field=field)
        _require_policy_version(value["policy_version"])
        _require_capability(value["capability"])
        for field in (
            "target_digest",
            "payload_digest",
            "approval_set_digest",
            "grant_digest",
        ):
            _require_digest(value[field], field=field)
        if value["required_permission"] != REQUIRED_EXECUTION_PERMISSION:
            raise ValueError("required_permission must be execution.run")
        if value["use_semantics"] != ONE_TIME_USE:
            raise ValueError("use_semantics must be ONE_TIME")
        _, issued = _require_timestamp(value["issued_at"], field="issued_at")
        _, expires = _require_timestamp(value["expires_at"], field="expires_at")
        lifetime = (expires - issued).total_seconds()
        if lifetime <= 0:
            raise ValueError("grant TTL must be positive")
        if lifetime > MAX_GRANT_TTL_SECONDS:
            raise ValueError("grant TTL exceeds 300 seconds")
        if value["grant_digest"] != _digest(without_digest):
            raise ValueError("grant_digest does not match grant claims")
        return cls(
            **{
                key: value[key]
                for key in expected
                if key not in {"schema_version", "grant_type"}
            }
        )

    def validate_bindings(
        self,
        *,
        target: ExecutionTarget,
        approval_evidence: ApprovalEvidenceSet,
    ) -> None:
        expected = {
            "request_id": approval_evidence.request_id,
            "capability": approval_evidence.capability,
            "target_kind": target.target_kind,
            "target_digest": target.target_digest,
            "payload_digest": approval_evidence.payload_digest,
            "approval_set_digest": approval_evidence.approval_set_digest,
            "policy_version": approval_evidence.policy_version,
        }
        mismatches = sorted(
            field
            for field, expected_value in expected.items()
            if getattr(self, field) != expected_value
        )
        if target.target_digest != approval_evidence.target_digest:
            mismatches.append("approval_evidence.target_digest")
        _, grant_issued = _require_timestamp(self.issued_at, field="issued_at")
        _, grant_expiry = _require_timestamp(self.expires_at, field="expires_at")
        _, approval_expiry = _require_timestamp(
            approval_evidence.approval_valid_until,
            field="approval_valid_until",
        )
        if grant_expiry > approval_expiry:
            mismatches.append("approval_valid_until")
        latest_approval = max(
            _require_timestamp(approval.approved_at, field="approved_at")[1]
            for approval in approval_evidence.approvals
        )
        if latest_approval > grant_issued:
            mismatches.append("approval_causality")
        if mismatches:
            raise ValueError(
                f"grant cross-contract bindings mismatch: {sorted(set(mismatches))}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "grant_type": EXECUTION_GRANT_TYPE,
            "grant_id": self.grant_id,
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "capability": self.capability,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "payload_digest": self.payload_digest,
            "approval_set_digest": self.approval_set_digest,
            "policy_version": self.policy_version,
            "required_permission": self.required_permission,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "use_semantics": self.use_semantics,
            "grant_digest": self.grant_digest,
        }


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    runner_receipt_id: str
    grant_id: str
    grant_digest: str
    execution_id: str
    runner_id: str
    status: str
    outcome: str
    started_at: str
    completed_at: str
    output_digest: str
    postcondition_status: str
    postcondition_digest: str
    receipt_digest: str

    def __post_init__(self) -> None:
        for field in ("runner_receipt_id", "grant_id", "execution_id", "runner_id"):
            _require_identifier(getattr(self, field), field=field)
        _require_digest(self.grant_digest, field="grant_digest")
        _require_receipt_result(self.status, self.outcome, self.postcondition_status)
        _, started = _require_timestamp(self.started_at, field="started_at")
        _, completed = _require_timestamp(self.completed_at, field="completed_at")
        if completed < started:
            raise ValueError("completed_at precedes started_at")
        _require_digest(self.output_digest, field="output_digest")
        _require_digest(self.postcondition_digest, field="postcondition_digest")
        _require_digest(self.receipt_digest, field="receipt_digest")
        without_digest = self.to_dict()
        without_digest.pop("receipt_digest")
        if self.receipt_digest != _digest(without_digest):
            raise ValueError("receipt_digest does not match receipt claims")

    @classmethod
    def create(
        cls,
        *,
        runner_receipt_id: str,
        grant: ExecutionGrant,
        runner_id: str,
        status: str,
        outcome: str,
        started_at: str,
        completed_at: str,
        output_digest: str,
        postcondition_status: str,
        postcondition_digest: str,
    ) -> Self:
        _require_identifier(runner_receipt_id, field="runner_receipt_id")
        _require_identifier(runner_id, field="runner_id")
        if not isinstance(grant, ExecutionGrant):
            raise ValueError("grant must be execution-grant/v1")
        _require_receipt_result(status, outcome, postcondition_status)
        _require_digest(output_digest, field="output_digest")
        _require_digest(postcondition_digest, field="postcondition_digest")
        started_text, started = _require_timestamp(started_at, field="started_at")
        completed_text, completed = _require_timestamp(completed_at, field="completed_at")
        if completed < started:
            raise ValueError("completed_at precedes started_at")
        without_digest = {
            "schema_version": SCHEMA_VERSION,
            "receipt_type": EXECUTION_RECEIPT_TYPE,
            "runner_receipt_id": runner_receipt_id,
            "grant_id": grant.grant_id,
            "grant_digest": grant.grant_digest,
            "execution_id": grant.execution_id,
            "runner_id": runner_id,
            "status": status,
            "outcome": outcome,
            "started_at": started_text,
            "completed_at": completed_text,
            "output_digest": output_digest,
            "postcondition_status": postcondition_status,
            "postcondition_digest": postcondition_digest,
        }
        claims = {
            key: item
            for key, item in without_digest.items()
            if key not in {"schema_version", "receipt_type"}
        }
        receipt = cls(**claims, receipt_digest=_digest(without_digest))
        receipt.validate_bindings(grant)
        return receipt

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        """Parse structurally; authoritative use also requires validate_bindings."""

        expected = frozenset(
            {
                "schema_version",
                "receipt_type",
                "runner_receipt_id",
                "grant_id",
                "grant_digest",
                "execution_id",
                "runner_id",
                "status",
                "outcome",
                "started_at",
                "completed_at",
                "output_digest",
                "postcondition_status",
                "postcondition_digest",
                "receipt_digest",
            }
        )
        _require_exact_fields(value, expected, contract=EXECUTION_RECEIPT_TYPE)
        _require_schema_and_type(
            schema_version=value["schema_version"],
            actual_type=value["receipt_type"],
            expected_type=EXECUTION_RECEIPT_TYPE,
            type_field="receipt_type",
        )
        for field in ("runner_receipt_id", "grant_id", "execution_id", "runner_id"):
            _require_identifier(value[field], field=field)
        for field in (
            "grant_digest",
            "output_digest",
            "postcondition_digest",
            "receipt_digest",
        ):
            _require_digest(value[field], field=field)
        _require_receipt_result(
            value["status"],
            value["outcome"],
            value["postcondition_status"],
        )
        _, started = _require_timestamp(value["started_at"], field="started_at")
        _, completed = _require_timestamp(value["completed_at"], field="completed_at")
        if completed < started:
            raise ValueError("completed_at precedes started_at")
        without_digest = {key: value[key] for key in expected if key != "receipt_digest"}
        if value["receipt_digest"] != _digest(without_digest):
            raise ValueError("receipt_digest does not match receipt claims")
        return cls(
            **{
                key: value[key]
                for key in expected
                if key not in {"schema_version", "receipt_type"}
            }
        )

    def validate_bindings(self, grant: ExecutionGrant) -> None:
        """Require exact grant identity and temporal authority for attempted execution."""

        _require_receipt_grant_bindings(
            grant=grant,
            grant_id=self.grant_id,
            grant_digest=self.grant_digest,
            execution_id=self.execution_id,
            status=self.status,
            started_at=self.started_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "receipt_type": EXECUTION_RECEIPT_TYPE,
            "runner_receipt_id": self.runner_receipt_id,
            "grant_id": self.grant_id,
            "grant_digest": self.grant_digest,
            "execution_id": self.execution_id,
            "runner_id": self.runner_id,
            "status": self.status,
            "outcome": self.outcome,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "output_digest": self.output_digest,
            "postcondition_status": self.postcondition_status,
            "postcondition_digest": self.postcondition_digest,
            "receipt_digest": self.receipt_digest,
        }


def _require_receipt_result(
    status: object,
    outcome: object,
    postcondition_status: object,
) -> None:
    if status not in _EXECUTION_STATUSES:
        raise ValueError("receipt status is invalid")
    if outcome not in _EXECUTION_OUTCOMES:
        raise ValueError("receipt outcome is invalid")
    if postcondition_status not in _POSTCONDITION_STATUSES:
        raise ValueError("postcondition_status is invalid")
    if outcome == "EXPECTED_EFFECT_VERIFIED" and status != "SUCCEEDED":
        raise ValueError("EXPECTED_EFFECT_VERIFIED requires status SUCCEEDED")
    if outcome == "EXPECTED_EFFECT_VERIFIED" and postcondition_status != "PASSED":
        raise ValueError("EXPECTED_EFFECT_VERIFIED requires postcondition_status PASSED")
    if postcondition_status == "PASSED" and outcome != "EXPECTED_EFFECT_VERIFIED":
        raise ValueError("postcondition_status PASSED requires EXPECTED_EFFECT_VERIFIED")
    if status == "REJECTED" and (
        outcome != "EXPECTED_EFFECT_NOT_VERIFIED" or postcondition_status != "NOT_RUN"
    ):
        raise ValueError(
            "REJECTED requires EXPECTED_EFFECT_NOT_VERIFIED and postcondition_status NOT_RUN"
        )
    if status != "REJECTED" and postcondition_status == "NOT_RUN":
        raise ValueError("postcondition_status NOT_RUN requires status REJECTED")
    if outcome == "INDETERMINATE" and postcondition_status != "INDETERMINATE":
        raise ValueError("INDETERMINATE outcome requires indeterminate postcondition")
    if postcondition_status == "INDETERMINATE" and outcome != "INDETERMINATE":
        raise ValueError("indeterminate postcondition requires INDETERMINATE outcome")


def _require_receipt_grant_bindings(
    *,
    grant: ExecutionGrant,
    grant_id: str,
    grant_digest: str,
    execution_id: str,
    status: str,
    started_at: str,
) -> None:
    if not isinstance(grant, ExecutionGrant):
        raise ValueError("grant must be execution-grant/v1")
    mismatches = [
        field
        for field, actual, expected in (
            ("grant_id", grant_id, grant.grant_id),
            ("grant_digest", grant_digest, grant.grant_digest),
            ("execution_id", execution_id, grant.execution_id),
        )
        if actual != expected
    ]
    if status in _ATTEMPTED_EXECUTION_STATUSES:
        _, issued = _require_timestamp(grant.issued_at, field="issued_at")
        _, expires = _require_timestamp(grant.expires_at, field="expires_at")
        _, started = _require_timestamp(started_at, field="started_at")
        if started < issued or started > expires:
            mismatches.append("execution_start_grant_validity")
    if mismatches:
        raise ValueError(
            f"receipt cross-contract bindings mismatch: {sorted(set(mismatches))}"
        )
