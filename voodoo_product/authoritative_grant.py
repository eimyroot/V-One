from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, NoReturn, Protocol, Self, runtime_checkable

from .authorization_snapshot import AuthorizationSnapshot
from .evidence_primitives import canonical_json, chained_hash, new_id
from .execution_contract import (
    MAX_GRANT_TTL_SECONDS,
    ONE_TIME_USE,
    REQUIRED_EXECUTION_PERMISSION,
)
from .grant_authority_statements import SELECT_SNAPSHOT_AUTHORITY_WITNESS
from .monotonic_authority import (
    AuthorityConstraint,
    AuthorityScope,
    MonotonicAuthorityChecker,
    MonotonicAuthorityDecision,
    MonotonicAuthorityViolation,
)
from .operational_safety import OperationalSafetyService
from .persistence import DatabaseConnection, ProductDatabaseAdapter
from .precondition_witness import (
    ATOMIC_PROVIDER_CONDITION,
    READ_THEN_COMPARE,
    PreconditionGuard,
    PreconditionWitness,
)
from .trusted_clock import TrustedClockAuthority

EXECUTION_GRANT_V2_TYPE: Final = "execution-grant/v2"
EXECUTION_BINDING_TYPE: Final = "execution-binding/v1"
SNAPSHOT_AUTHORITY_EVIDENCE_TYPE: Final = "snapshot-authority-evidence/v1"
MAX_PRECONDITION_TO_GRANT_SECONDS: Final = 30

IdFactory = Callable[[str], str]

_GRANT_FIELDS = frozenset(
    {
        "schema_version",
        "grant_type",
        "grant_id",
        "jti",
        "execution_id",
        "request_id",
        "authorization_snapshot_digest",
        "snapshot_authority_witness_set_digest",
        "snapshot_authority_event_hash",
        "parent_scope_digest",
        "authority_constraint_digest",
        "monotonic_authority_decision_digest",
        "actor_id",
        "workspace_id",
        "environment",
        "capability",
        "capability_definition_identity",
        "target_kind",
        "target_digest",
        "payload_digest",
        "policy_version",
        "policy_identity",
        "approval_set_digest",
        "required_permission",
        "precondition_requirement_digest",
        "precondition_expectation_digest",
        "precondition_observation_digest",
        "precondition_witness_digest",
        "precondition_enforcement_class",
        "precondition_checked_at",
        "execution_binding_digest",
        "execution_capsule_digest",
        "runner_class",
        "execution_binding_authority_revision",
        "issued_at",
        "expires_at",
        "revocation_epoch",
        "use_semantics",
        "issuer_identity",
        "issuer_revision",
        "grant_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _require_timestamp(value: object, *, field: str) -> tuple[str, datetime]:
    text = _require_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    canonical = parsed.astimezone(UTC).isoformat(timespec="milliseconds")
    if text != canonical:
        raise ValueError(f"{field} must use canonical UTC millisecond form")
    return text, parsed.astimezone(UTC)


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


class GrantIssuanceDenied(PermissionError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = _require_text(reason_code, field="reason_code")
        super().__init__(self.reason_code)


@dataclass(frozen=True, slots=True)
class SnapshotAuthorityEvidence:
    snapshot_id: str
    snapshot_digest: str
    authority_witness_set_digest: str
    revocation_epoch: int
    event_hash: str
    evidence_digest: str

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, field="snapshot_id")
        for field in (
            "snapshot_digest",
            "authority_witness_set_digest",
            "event_hash",
            "evidence_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if type(self.revocation_epoch) is not int or self.revocation_epoch < 0:
            raise ValueError("revocation_epoch must be non-negative")
        if self.evidence_digest != _digest(self._claims_without_digest()):
            raise ValueError("evidence_digest does not match snapshot authority evidence")

    @classmethod
    def create(
        cls,
        *,
        snapshot_id: str,
        snapshot_digest: str,
        authority_witness_set_digest: str,
        revocation_epoch: int,
        event_hash: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "evidence_type": SNAPSHOT_AUTHORITY_EVIDENCE_TYPE,
            "snapshot_id": snapshot_id,
            "snapshot_digest": snapshot_digest,
            "authority_witness_set_digest": authority_witness_set_digest,
            "revocation_epoch": revocation_epoch,
            "event_hash": event_hash,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "evidence_type"}
        }
        return cls(**values, evidence_digest=_digest(claims))

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "evidence_type": SNAPSHOT_AUTHORITY_EVIDENCE_TYPE,
            "snapshot_id": self.snapshot_id,
            "snapshot_digest": self.snapshot_digest,
            "authority_witness_set_digest": self.authority_witness_set_digest,
            "revocation_epoch": self.revocation_epoch,
            "event_hash": self.event_hash,
        }


_AUTHORITY_WITNESS_PAYLOAD_FIELDS = frozenset(
    {
        "correlation_id",
        "snapshot_digest",
        "authority_witness_set_digest",
        "permission_decision_digest",
        "capability_selection_digest",
        "capability_selection_authority_revision",
        "policy_identity",
        "capability_definition_identity",
        "capability_activation_digest",
        "target_binding_digest",
        "approval_certificate_digest",
        "clock_witness_digest",
        "revocation_epoch",
        "authorization_source_revision",
    }
)


def load_snapshot_authority_evidence_on_connection(
    connection: DatabaseConnection,
    *,
    snapshot: AuthorizationSnapshot,
) -> SnapshotAuthorityEvidence:
    if not isinstance(snapshot, AuthorizationSnapshot):
        raise ValueError("snapshot is invalid")
    rows = connection.execute(
        SELECT_SNAPSHOT_AUTHORITY_WITNESS,
        (snapshot.snapshot_id,),
    ).fetchall()
    if len(rows) != 1:
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_AMBIGUOUS")

    row = rows[0]
    try:
        payload = json.loads(str(row["payload_json"]))
    except (TypeError, json.JSONDecodeError) as exc:
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_INVALID") from exc
    if not isinstance(payload, dict):
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_INVALID")
    if canonical_json(payload) != str(row["payload_json"]):
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_NON_CANONICAL")
    if frozenset(payload) != _AUTHORITY_WITNESS_PAYLOAD_FIELDS:
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_FIELDS_INVALID")

    event = {
        "id": str(row["id"]),
        "actor_id": str(row["actor_id"]),
        "action": str(row["action"]),
        "target_type": str(row["target_type"]),
        "target_id": str(row["target_id"]),
        "payload": payload,
        "created_at": str(row["created_at"]),
    }
    try:
        for field in ("id", "actor_id", "action", "target_type", "target_id"):
            _require_text(event[field], field=field)
        _require_timestamp(event["created_at"], field="created_at")
        _require_text(payload["correlation_id"], field="correlation_id")
        _require_text(
            payload["capability_selection_authority_revision"],
            field="capability_selection_authority_revision",
        )
        _require_text(
            payload["authorization_source_revision"],
            field="authorization_source_revision",
        )
    except ValueError as exc:
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_INVALID") from exc
    if event["action"] != "authorization_snapshot.authority_witness":
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_INVALID")
    if event["target_type"] != "authorization_snapshot":
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_INVALID")

    previous_hash = str(row["previous_hash"])
    event_hash = str(row["event_hash"])
    try:
        if previous_hash != "GENESIS":
            _require_digest(previous_hash, field="previous_hash")
        _require_digest(event_hash, field="event_hash")
    except ValueError as exc:
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVENT_HASH_INVALID") from exc
    if chained_hash(previous_hash, event) != event_hash:
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVENT_HASH_INVALID")

    expected = {
        "actor_id": snapshot.actor_id,
        "target_id": snapshot.snapshot_id,
        "snapshot_digest": snapshot.snapshot_digest,
        "policy_identity": snapshot.policy_identity,
        "capability_definition_identity": snapshot.capability_definition_identity,
        "authorization_source_revision": snapshot.authorization_source_revision,
    }
    actual = {
        "actor_id": event["actor_id"],
        "target_id": event["target_id"],
        "snapshot_digest": payload["snapshot_digest"],
        "policy_identity": payload["policy_identity"],
        "capability_definition_identity": payload["capability_definition_identity"],
        "authorization_source_revision": payload["authorization_source_revision"],
    }
    if actual != expected:
        raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_BINDING_MISMATCH")

    for field in (
        "authority_witness_set_digest",
        "permission_decision_digest",
        "capability_selection_digest",
        "policy_identity",
        "capability_definition_identity",
        "capability_activation_digest",
        "target_binding_digest",
        "approval_certificate_digest",
        "clock_witness_digest",
    ):
        try:
            _require_digest(payload[field], field=field)
        except ValueError as exc:
            raise GrantIssuanceDenied("SNAPSHOT_AUTHORITY_EVIDENCE_INVALID") from exc

    revocation_epoch = payload["revocation_epoch"]
    if type(revocation_epoch) is not int or revocation_epoch < 0:
        raise GrantIssuanceDenied("SNAPSHOT_REVOCATION_EPOCH_INVALID")

    return SnapshotAuthorityEvidence.create(
        snapshot_id=snapshot.snapshot_id,
        snapshot_digest=snapshot.snapshot_digest,
        authority_witness_set_digest=str(payload["authority_witness_set_digest"]),
        revocation_epoch=revocation_epoch,
        event_hash=event_hash,
    )


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    capability_definition_identity: str
    environment: str
    target_kind: str
    execution_capsule_digest: str
    runner_class: str
    authority_revision: str
    binding_digest: str

    def __post_init__(self) -> None:
        _require_digest(
            self.capability_definition_identity,
            field="capability_definition_identity",
        )
        for field in ("environment", "target_kind", "runner_class", "authority_revision"):
            _require_text(getattr(self, field), field=field)
        _require_digest(
            self.execution_capsule_digest,
            field="execution_capsule_digest",
        )
        _require_digest(self.binding_digest, field="binding_digest")
        if self.binding_digest != _digest(self._claims_without_digest()):
            raise ValueError("binding_digest does not match execution binding")

    @classmethod
    def create(
        cls,
        *,
        capability_definition_identity: str,
        environment: str,
        target_kind: str,
        execution_capsule_digest: str,
        runner_class: str,
        authority_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "binding_type": EXECUTION_BINDING_TYPE,
            "capability_definition_identity": capability_definition_identity,
            "environment": environment,
            "target_kind": target_kind,
            "execution_capsule_digest": execution_capsule_digest,
            "runner_class": runner_class,
            "authority_revision": authority_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "binding_type"}
        }
        return cls(**values, binding_digest=_digest(claims))

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "binding_type": EXECUTION_BINDING_TYPE,
            "capability_definition_identity": self.capability_definition_identity,
            "environment": self.environment,
            "target_kind": self.target_kind,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
            "authority_revision": self.authority_revision,
        }


@runtime_checkable
class ExecutionBindingAuthority(Protocol):
    def resolve(
        self,
        *,
        capability_definition_identity: str,
        environment: str,
        target_kind: str,
    ) -> ExecutionBinding: ...


@runtime_checkable
class GrantRevocationEpochAuthority(Protocol):
    def current_epoch(
        self,
        connection: DatabaseConnection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class ExecutionGrantV2:
    grant_id: str
    jti: str
    execution_id: str
    request_id: str
    authorization_snapshot_digest: str
    snapshot_authority_witness_set_digest: str
    snapshot_authority_event_hash: str
    parent_scope_digest: str
    authority_constraint_digest: str
    monotonic_authority_decision_digest: str
    actor_id: str
    workspace_id: str
    environment: str
    capability: str
    capability_definition_identity: str
    target_kind: str
    target_digest: str
    payload_digest: str
    policy_version: str
    policy_identity: str
    approval_set_digest: str
    required_permission: str
    precondition_requirement_digest: str
    precondition_expectation_digest: str
    precondition_observation_digest: str
    precondition_witness_digest: str
    precondition_enforcement_class: str
    precondition_checked_at: str
    execution_binding_digest: str
    execution_capsule_digest: str
    runner_class: str
    execution_binding_authority_revision: str
    issued_at: str
    expires_at: str
    revocation_epoch: int
    use_semantics: str
    issuer_identity: str
    issuer_revision: str
    grant_digest: str

    def __post_init__(self) -> None:
        for field in (
            "grant_id",
            "jti",
            "execution_id",
            "request_id",
            "actor_id",
            "workspace_id",
            "environment",
            "capability",
            "target_kind",
            "policy_version",
            "runner_class",
            "execution_binding_authority_revision",
            "issuer_identity",
            "issuer_revision",
        ):
            _require_text(getattr(self, field), field=field)
        for field in (
            "authorization_snapshot_digest",
            "snapshot_authority_witness_set_digest",
            "snapshot_authority_event_hash",
            "parent_scope_digest",
            "authority_constraint_digest",
            "monotonic_authority_decision_digest",
            "capability_definition_identity",
            "target_digest",
            "payload_digest",
            "policy_identity",
            "approval_set_digest",
            "precondition_requirement_digest",
            "precondition_expectation_digest",
            "precondition_observation_digest",
            "precondition_witness_digest",
            "execution_binding_digest",
            "execution_capsule_digest",
            "grant_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        if self.required_permission != REQUIRED_EXECUTION_PERMISSION:
            raise ValueError("required_permission must be execution.run")
        if self.precondition_enforcement_class not in {
            READ_THEN_COMPARE,
            ATOMIC_PROVIDER_CONDITION,
        }:
            raise ValueError("precondition_enforcement_class is unsupported")
        if self.use_semantics != ONE_TIME_USE:
            raise ValueError("use_semantics must be ONE_TIME")
        if type(self.revocation_epoch) is not int or self.revocation_epoch < 0:
            raise ValueError("revocation_epoch must be non-negative")
        _, checked = _require_timestamp(
            self.precondition_checked_at,
            field="precondition_checked_at",
        )
        _, issued = _require_timestamp(self.issued_at, field="issued_at")
        _, expires = _require_timestamp(self.expires_at, field="expires_at")
        if issued < checked:
            raise ValueError("grant issuance precedes precondition witness")
        if expires <= issued:
            raise ValueError("grant TTL must be positive")
        if (expires - issued).total_seconds() > MAX_GRANT_TTL_SECONDS:
            raise ValueError("grant TTL exceeds 300 seconds")
        if (issued - checked).total_seconds() > MAX_PRECONDITION_TO_GRANT_SECONDS:
            raise ValueError("precondition witness is too old for grant issuance")
        if self.grant_digest != _digest(self._claims_without_digest()):
            raise ValueError("grant_digest does not match execution grant v2 claims")

    @classmethod
    def _issue(cls, **claims: Any) -> Self:
        values = {
            "schema_version": 2,
            "grant_type": EXECUTION_GRANT_V2_TYPE,
            **claims,
        }
        content = {
            key: item
            for key, item in values.items()
            if key not in {"schema_version", "grant_type"}
        }
        return cls(**content, grant_digest=_digest(values))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _GRANT_FIELDS, contract=EXECUTION_GRANT_V2_TYPE)
        if value["schema_version"] != 2 or value["grant_type"] != EXECUTION_GRANT_V2_TYPE:
            raise ValueError("execution-grant/v2 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _GRANT_FIELDS
                if key not in {"schema_version", "grant_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "grant_type": EXECUTION_GRANT_V2_TYPE,
            "grant_id": self.grant_id,
            "jti": self.jti,
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "authorization_snapshot_digest": self.authorization_snapshot_digest,
            "snapshot_authority_witness_set_digest": (
                self.snapshot_authority_witness_set_digest
            ),
            "snapshot_authority_event_hash": self.snapshot_authority_event_hash,
            "parent_scope_digest": self.parent_scope_digest,
            "authority_constraint_digest": self.authority_constraint_digest,
            "monotonic_authority_decision_digest": (
                self.monotonic_authority_decision_digest
            ),
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "capability": self.capability,
            "capability_definition_identity": self.capability_definition_identity,
            "target_kind": self.target_kind,
            "target_digest": self.target_digest,
            "payload_digest": self.payload_digest,
            "policy_version": self.policy_version,
            "policy_identity": self.policy_identity,
            "approval_set_digest": self.approval_set_digest,
            "required_permission": self.required_permission,
            "precondition_requirement_digest": self.precondition_requirement_digest,
            "precondition_expectation_digest": self.precondition_expectation_digest,
            "precondition_observation_digest": self.precondition_observation_digest,
            "precondition_witness_digest": self.precondition_witness_digest,
            "precondition_enforcement_class": self.precondition_enforcement_class,
            "precondition_checked_at": self.precondition_checked_at,
            "execution_binding_digest": self.execution_binding_digest,
            "execution_capsule_digest": self.execution_capsule_digest,
            "runner_class": self.runner_class,
            "execution_binding_authority_revision": (
                self.execution_binding_authority_revision
            ),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revocation_epoch": self.revocation_epoch,
            "use_semantics": self.use_semantics,
            "issuer_identity": self.issuer_identity,
            "issuer_revision": self.issuer_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "grant_digest": self.grant_digest}


class AuthoritativeGrantIssuer:
    """Issue execution-grant/v2 only from live, narrowed, revalidated authority."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        operational_safety_service: OperationalSafetyService,
        revocation_authority: GrantRevocationEpochAuthority,
        precondition_guard: PreconditionGuard,
        execution_binding_authority: ExecutionBindingAuthority,
        trusted_clock: TrustedClockAuthority,
        issuer_identity: str,
        issuer_revision: str,
        grant_ttl_seconds: int = 60,
        id_factory: IdFactory = new_id,
    ) -> None:
        if operational_safety_service.db is not database:
            raise ValueError("grant issuer safety service must use its database")
        if not isinstance(revocation_authority, GrantRevocationEpochAuthority):
            raise ValueError("revocation_authority is invalid")
        if not isinstance(precondition_guard, PreconditionGuard):
            raise ValueError("precondition_guard is invalid")
        if not isinstance(execution_binding_authority, ExecutionBindingAuthority):
            raise ValueError("execution_binding_authority is invalid")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock is invalid")
        if precondition_guard.trusted_clock is not trusted_clock:
            raise ValueError("grant issuer and precondition guard must share trusted clock")
        if type(grant_ttl_seconds) is not int or not (
            1 <= grant_ttl_seconds <= MAX_GRANT_TTL_SECONDS
        ):
            raise ValueError("grant_ttl_seconds is invalid")
        if not callable(id_factory):
            raise ValueError("id_factory is invalid")

        self.db = database
        self.operational_safety_service = operational_safety_service
        self.revocation_authority = revocation_authority
        self.precondition_guard = precondition_guard
        self.execution_binding_authority = execution_binding_authority
        self.trusted_clock = trusted_clock
        self.issuer_identity = _require_text(issuer_identity, field="issuer_identity")
        self.issuer_revision = _require_text(issuer_revision, field="issuer_revision")
        self.grant_ttl_seconds = grant_ttl_seconds
        self._id_factory = id_factory

    def issue(
        self,
        *,
        snapshot: AuthorizationSnapshot,
        authority: AuthorityConstraint,
    ) -> ExecutionGrantV2:
        if not isinstance(snapshot, AuthorizationSnapshot):
            raise ValueError("snapshot is invalid")
        if not isinstance(authority, AuthorityConstraint):
            raise ValueError("authority constraint is invalid")

        parent = AuthorityScope.from_snapshot(snapshot)
        try:
            decision = MonotonicAuthorityChecker.check(parent=parent, child=authority)
        except MonotonicAuthorityViolation as exc:
            self._deny("MONOTONIC_AUTHORITY_DENIED", cause=exc)

        with self.db.connect() as connection:
            evidence, live_epoch = self._assert_live_authority(
                connection,
                snapshot=snapshot,
                evidence=None,
            )

        binding = self._resolve_execution_binding(snapshot)
        witness = self._build_precondition_witness(
            parent=parent,
            authority=authority,
            decision=decision,
            snapshot=snapshot,
        )
        issued_at, expires_at = self._resolve_validity(
            environment=snapshot.environment,
            authority=authority,
            witness=witness,
        )

        # Re-read live deny state after the provider precondition read. B4 must repeat
        # the same checks atomically at one-time grant consumption.
        with self.db.connect() as connection:
            _, live_epoch = self._assert_live_authority(
                connection,
                snapshot=snapshot,
                evidence=evidence,
            )

        return ExecutionGrantV2._issue(
            grant_id=self._id_factory("grt"),
            jti=self._id_factory("jti"),
            execution_id=snapshot.execution_id,
            request_id=snapshot.request_id,
            authorization_snapshot_digest=snapshot.snapshot_digest,
            snapshot_authority_witness_set_digest=(
                evidence.authority_witness_set_digest
            ),
            snapshot_authority_event_hash=evidence.event_hash,
            parent_scope_digest=parent.scope_digest,
            authority_constraint_digest=authority.constraint_digest,
            monotonic_authority_decision_digest=decision.decision_digest,
            actor_id=authority.actor_id,
            workspace_id=authority.workspace_id,
            environment=authority.environment,
            capability=authority.capability,
            capability_definition_identity=authority.capability_definition_identity,
            target_kind=authority.target_kind,
            target_digest=authority.target_digest,
            payload_digest=authority.payload_digest,
            policy_version=authority.policy_version,
            policy_identity=authority.policy_identity,
            approval_set_digest=authority.approval_set_digest,
            required_permission=authority.required_permission,
            precondition_requirement_digest=witness.requirement_digest,
            precondition_expectation_digest=witness.expectation_digest,
            precondition_observation_digest=witness.observation_digest,
            precondition_witness_digest=witness.witness_digest,
            precondition_enforcement_class=witness.enforcement_class,
            precondition_checked_at=witness.checked_at,
            execution_binding_digest=binding.binding_digest,
            execution_capsule_digest=binding.execution_capsule_digest,
            runner_class=binding.runner_class,
            execution_binding_authority_revision=binding.authority_revision,
            issued_at=issued_at,
            expires_at=expires_at,
            revocation_epoch=live_epoch,
            use_semantics=ONE_TIME_USE,
            issuer_identity=self.issuer_identity,
            issuer_revision=self.issuer_revision,
        )

    def _assert_live_authority(
        self,
        connection: DatabaseConnection,
        *,
        snapshot: AuthorizationSnapshot,
        evidence: SnapshotAuthorityEvidence | None,
    ) -> tuple[SnapshotAuthorityEvidence, int]:
        if self.operational_safety_service.is_active(connection):
            self._deny("EMERGENCY_STOP_ACTIVE")
        resolved_evidence = evidence
        if resolved_evidence is None:
            resolved_evidence = load_snapshot_authority_evidence_on_connection(
                connection,
                snapshot=snapshot,
            )
        live_epoch = self._live_revocation_epoch(
            connection,
            workspace_id=snapshot.workspace_id,
            environment=snapshot.environment,
            capability_definition_identity=snapshot.capability_definition_identity,
        )
        if live_epoch != resolved_evidence.revocation_epoch:
            self._deny("REVOCATION_EPOCH_CHANGED")
        return resolved_evidence, live_epoch

    def _live_revocation_epoch(
        self,
        connection: DatabaseConnection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int:
        try:
            epoch = self.revocation_authority.current_epoch(
                connection,
                workspace_id=workspace_id,
                environment=environment,
                capability_definition_identity=capability_definition_identity,
            )
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            self._deny("REVOCATION_AUTHORITY_DENIED", cause=exc)
        if type(epoch) is not int or epoch < 0:
            self._deny("REVOCATION_EPOCH_INVALID")
        return epoch

    def _resolve_execution_binding(
        self,
        snapshot: AuthorizationSnapshot,
    ) -> ExecutionBinding:
        try:
            binding = self.execution_binding_authority.resolve(
                capability_definition_identity=snapshot.capability_definition_identity,
                environment=snapshot.environment,
                target_kind=snapshot.target_kind,
            )
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            self._deny("EXECUTION_BINDING_DENIED", cause=exc)
        if not isinstance(binding, ExecutionBinding):
            self._deny("EXECUTION_BINDING_INVALID")
        expected = (
            snapshot.capability_definition_identity,
            snapshot.environment,
            snapshot.target_kind,
        )
        actual = (
            binding.capability_definition_identity,
            binding.environment,
            binding.target_kind,
        )
        if actual != expected:
            self._deny("EXECUTION_BINDING_MISMATCH")
        return binding

    def _build_precondition_witness(
        self,
        *,
        parent: AuthorityScope,
        authority: AuthorityConstraint,
        decision: MonotonicAuthorityDecision,
        snapshot: AuthorizationSnapshot,
    ) -> PreconditionWitness:
        try:
            return self.precondition_guard.witness(
                parent=parent,
                authority=authority,
                monotonic_decision=decision,
                target=snapshot.execution_target,
            )
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            self._deny("PRECONDITION_DENIED", cause=exc)

    def _resolve_validity(
        self,
        *,
        environment: str,
        authority: AuthorityConstraint,
        witness: PreconditionWitness,
    ) -> tuple[str, str]:
        try:
            clock_witness = self.trusted_clock.witness(environment=environment)
        except (LookupError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
            self._deny("TRUSTED_CLOCK_DENIED", cause=exc)
        if clock_witness.source_identity != self.trusted_clock.source_identity:
            self._deny("TRUSTED_CLOCK_BINDING_MISMATCH")

        issued_text, issued = _require_timestamp(
            clock_witness.observed_at,
            field="issued_at",
        )
        _, checked_at = _require_timestamp(
            witness.checked_at,
            field="precondition_checked_at",
        )
        _, authority_start = _require_timestamp(
            authority.valid_from,
            field="authority.valid_from",
        )
        _, authority_end = _require_timestamp(
            authority.valid_until,
            field="authority.valid_until",
        )
        if issued < checked_at:
            self._deny("ISSUANCE_PRECEDES_PRECONDITION")
        if (issued - checked_at).total_seconds() > MAX_PRECONDITION_TO_GRANT_SECONDS:
            self._deny("PRECONDITION_WITNESS_STALE")
        if issued < authority_start or issued >= authority_end:
            self._deny("AUTHORITY_NOT_VALID_AT_ISSUANCE")

        expiry = min(
            issued + timedelta(seconds=self.grant_ttl_seconds),
            authority_end,
        )
        if expiry <= issued:
            self._deny("AUTHORITY_EXPIRES_BEFORE_GRANT")
        return issued_text, expiry.astimezone(UTC).isoformat(timespec="milliseconds")

    @staticmethod
    def _deny(
        reason_code: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        error = GrantIssuanceDenied(reason_code)
        if cause is None:
            raise error
        raise error from cause
