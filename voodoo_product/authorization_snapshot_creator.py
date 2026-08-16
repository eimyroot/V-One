from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Final, NoReturn, Protocol, runtime_checkable

from . import statements as sql
from .approval_certificate import ApprovalCertificate
from .audit import AuditLedger
from .authority_witness import AuthorityWitnessSet
from .authorization_snapshot import (
    PAYLOAD_DIGEST_SCHEME,
    AuthorizationSnapshot,
)
from .authorization_snapshot_store import (
    AuthorizationSnapshotPersistenceResult,
    AuthorizationSnapshotStore,
)
from .capability_registry import ImmutableCapabilityRegistry
from .evidence_primitives import canonical_json, new_id
from .execution_contract import (
    REQUIRED_EXECUTION_PERMISSION,
    ApprovalEvidenceSet,
    ApprovalRecord,
)
from .permission_authority import PermissionAuthority, PermissionQuery
from .persistence import DatabaseConnection, DatabaseRow, ProductDatabaseAdapter
from .policy_authority import ImmutablePolicyAuthority, PolicyRevision
from .target_binding import TargetBinderRegistry
from .trusted_clock import TrustedClockAuthority

CAPABILITY_SELECTION_TYPE: Final = "capability-selection/v1"
CAPABILITY_SELECTION_AUTHORITY_TYPE: Final = "capability-selection-authority/v1"
AUTHORIZATION_SOURCE_TYPE: Final = "authoritative-snapshot-creator/v1"

IdFactory = Callable[[str], str]


def _digest(value: Mapping[str, object]) -> str:
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


@dataclass(frozen=True, slots=True)
class CapabilitySelection:
    adapter: str
    capability: str
    authority_revision: str
    selection_digest: str

    def __post_init__(self) -> None:
        _require_text(self.adapter, field="adapter")
        _require_text(self.capability, field="capability")
        _require_text(self.authority_revision, field="authority_revision")
        expected = _digest(
            {
                "selection_type": CAPABILITY_SELECTION_TYPE,
                "adapter": self.adapter,
                "capability": self.capability,
                "authority_revision": self.authority_revision,
            }
        )
        if self.selection_digest != expected:
            raise ValueError("selection_digest does not match capability selection")

    @classmethod
    def create(
        cls,
        *,
        adapter: str,
        capability: str,
        authority_revision: str,
    ) -> CapabilitySelection:
        claims = {
            "selection_type": CAPABILITY_SELECTION_TYPE,
            "adapter": _require_text(adapter, field="adapter"),
            "capability": _require_text(capability, field="capability"),
            "authority_revision": _require_text(
                authority_revision,
                field="authority_revision",
            ),
        }
        return cls(
            adapter=claims["adapter"],
            capability=claims["capability"],
            authority_revision=claims["authority_revision"],
            selection_digest=_digest(claims),
        )


@runtime_checkable
class CapabilitySelectionAuthority(Protocol):
    def select(self, *, adapter: str) -> CapabilitySelection: ...


class ImmutableCapabilitySelectionAuthority:
    """Explicit server-owned adapter-to-capability bridge.

    An adapter name is never itself treated as execution authority. This authority merely
    selects the canonical capability that must still pass the immutable capability registry.
    """

    def __init__(
        self,
        *,
        bindings: Mapping[str, str],
        authority_revision: str,
    ) -> None:
        revision = _require_text(authority_revision, field="authority_revision")
        normalized: dict[str, str] = {}
        for adapter, capability in bindings.items():
            adapter = _require_text(adapter, field="adapter")
            capability = _require_text(capability, field="capability")
            if adapter in normalized:
                raise ValueError("duplicate adapter capability selection")
            normalized[adapter] = capability
        if not normalized:
            raise ValueError("capability selection authority requires at least one binding")
        self._bindings = MappingProxyType(normalized)
        self._authority_revision = revision

    def select(self, *, adapter: str) -> CapabilitySelection:
        adapter = _require_text(adapter, field="adapter")
        try:
            capability = self._bindings[adapter]
        except KeyError as exc:
            raise LookupError("capability selection not found") from exc
        return CapabilitySelection.create(
            adapter=adapter,
            capability=capability,
            authority_revision=self._authority_revision,
        )


@runtime_checkable
class RevocationEpochAuthority(Protocol):
    """Server-side live revocation observer required by snapshot creation."""

    def current_epoch(
        self,
        connection: DatabaseConnection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int: ...


class SnapshotAuthorizationDenied(PermissionError):
    """Fail-closed authorization rejection with a bounded stable reason code."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = _require_text(reason_code, field="reason_code")


class AuthoritativeSnapshotCreator:
    """Construct and persist one authorization snapshot in one datastore transaction.

    The creator performs only authorization evidence construction. It does not issue grants,
    dispatch work, invoke a Runner, or mutate provider state.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        snapshot_store: AuthorizationSnapshotStore,
        permission_authority: PermissionAuthority,
        policy_authority: ImmutablePolicyAuthority,
        policy_version: str,
        capability_registry: ImmutableCapabilityRegistry,
        capability_selection_authority: CapabilitySelectionAuthority,
        target_binders: TargetBinderRegistry,
        trusted_clock: TrustedClockAuthority,
        revocation_authority: RevocationEpochAuthority,
        authorization_source_revision: str,
        id_factory: IdFactory = new_id,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("snapshot creator audit ledger must use its database")
        if snapshot_store.db is not database:
            raise ValueError("snapshot creator store must use its database")
        if not isinstance(permission_authority, PermissionAuthority):
            raise ValueError("permission_authority is invalid")
        if not isinstance(capability_selection_authority, CapabilitySelectionAuthority):
            raise ValueError("capability_selection_authority is invalid")
        if not isinstance(revocation_authority, RevocationEpochAuthority):
            raise ValueError("revocation_authority is invalid")
        if not isinstance(policy_authority, ImmutablePolicyAuthority):
            raise ValueError("policy_authority is invalid")
        if not isinstance(capability_registry, ImmutableCapabilityRegistry):
            raise ValueError("capability_registry is invalid")
        if not isinstance(target_binders, TargetBinderRegistry):
            raise ValueError("target_binders is invalid")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock is invalid")
        if not callable(id_factory):
            raise ValueError("id_factory is invalid")

        self.db = database
        self.audit_ledger = audit_ledger
        self.snapshot_store = snapshot_store
        self.permission_authority = permission_authority
        self.policy_authority = policy_authority
        self.policy_version = _require_text(policy_version, field="policy_version")
        self.capability_registry = capability_registry
        self.capability_selection_authority = capability_selection_authority
        self.target_binders = target_binders
        self.trusted_clock = trusted_clock
        self.revocation_authority = revocation_authority
        self.authorization_source_revision = _require_text(
            authorization_source_revision,
            field="authorization_source_revision",
        )
        self._id_factory = id_factory

    def create_snapshot(
        self,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> AuthorizationSnapshot:
        actor_id = _require_text(actor_id, field="actor_id")
        request_id = _require_text(request_id, field="request_id")
        idempotency_key = _require_text(idempotency_key, field="idempotency_key")
        correlation_id = _require_text(correlation_id, field="correlation_id")

        denied: SnapshotAuthorizationDenied | None = None
        result: AuthorizationSnapshot | None = None

        with self.db.transaction() as connection:
            try:
                result = self._create_in_transaction(
                    connection,
                    actor_id=actor_id,
                    request_id=request_id,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                )
            except SnapshotAuthorizationDenied as exc:
                self.audit_ledger.append(
                    connection,
                    actor_id=actor_id,
                    action="authorization_snapshot.reject",
                    target_type="change_request",
                    target_id=request_id,
                    payload={
                        "correlation_id": correlation_id,
                        "reason_code": exc.reason_code,
                    },
                )
                denied = exc

        if denied is not None:
            raise denied
        if result is None:
            raise RuntimeError("snapshot creator completed without a result")
        return result

    def _create_in_transaction(
        self,
        connection: DatabaseConnection,
        *,
        actor_id: str,
        request_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> AuthorizationSnapshot:
        request = connection.execute(
            sql.SELECT_CHANGE_REQUEST_FOR_EXECUTION,
            (request_id,),
        ).fetchone()
        request, payload = self._validated_request(request)

        selection = self._select_capability(str(request["adapter"]))
        capability_definition, capability_activation = self._resolve_capability(
            capability=selection.capability,
            environment=str(request["environment"]),
        )
        target_binding = self._bind_target(
            capability_definition=capability_definition,
            payload=payload,
        )
        policy_revision = self._resolve_policy()

        approvals = self._approval_records(
            connection,
            request=request,
            policy_revision=policy_revision,
        )
        payload_digest = _digest(
            {
                "schema_version": 1,
                "binding_type": PAYLOAD_DIGEST_SCHEME,
                "payload": payload,
            }
        )
        approval_valid_until = self._approval_valid_until(
            approvals=approvals,
            policy_revision=policy_revision,
        )
        approval_evidence = ApprovalEvidenceSet.create(
            request_id=str(request["id"]),
            payload_digest=payload_digest,
            target_digest=target_binding.target.target_digest,
            capability=capability_definition.capability,
            policy_version=policy_revision.policy_version,
            approvals=approvals,
            approval_valid_until=approval_valid_until,
        )
        approval_certificate = ApprovalCertificate.create(
            review_content_sha256=str(request["review_content_sha256"]),
            policy_revision=policy_revision,
            approval_evidence=approval_evidence,
        )

        permission_decision = self.permission_authority.decide(
            PermissionQuery(
                actor_id=actor_id,
                workspace_id=str(request["workspace_id"]),
                environment=str(request["environment"]),
                permission=REQUIRED_EXECUTION_PERMISSION,
            )
        )
        if not permission_decision.granted:
            self._deny("EXECUTION_PERMISSION_DENIED")

        try:
            clock_witness = self.trusted_clock.witness(
                environment=str(request["environment"])
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("TRUSTED_CLOCK_DENIED")

        authorized_at = clock_witness.observed_at
        authorized_at_value = datetime.fromisoformat(authorized_at)
        valid_until_value = datetime.fromisoformat(approval_valid_until)
        if authorized_at_value > valid_until_value:
            self._deny("APPROVAL_EXPIRED")
        for approval in approvals:
            if datetime.fromisoformat(approval.approved_at) > authorized_at_value:
                self._deny("APPROVAL_AFTER_AUTHORIZATION")

        emergency_stop = connection.execute(sql.SELECT_EMERGENCY_STOP).fetchone()
        if emergency_stop is not None and str(emergency_stop["value"]) == "1":
            self._deny("EMERGENCY_STOP_ACTIVE")

        try:
            revocation_epoch = self.revocation_authority.current_epoch(
                connection,
                workspace_id=str(request["workspace_id"]),
                environment=str(request["environment"]),
                capability_definition_identity=capability_definition.definition_identity,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("REVOCATION_DENIED")
        if type(revocation_epoch) is not int or revocation_epoch < 0:
            self._deny("REVOCATION_EPOCH_INVALID")

        try:
            witness_set = AuthorityWitnessSet.create(
                permission_decision=permission_decision,
                policy_revision=policy_revision,
                capability_definition=capability_definition,
                capability_activation=capability_activation,
                target_binding=target_binding,
                approval_certificate=approval_certificate,
                clock_witness=clock_witness,
                revocation_epoch=revocation_epoch,
            )
        except (PermissionError, ValueError):
            self._deny("AUTHORITY_WITNESS_INVALID")

        snapshot = AuthorizationSnapshot.create(
            snapshot_id=self._id_factory("authz"),
            execution_id=self._id_factory("exec"),
            request_id=str(request["id"]),
            review_content_sha256=str(request["review_content_sha256"]),
            actor_id=actor_id,
            workspace_id=str(request["workspace_id"]),
            environment=str(request["environment"]),
            capability=capability_definition.capability,
            capability_definition_identity=capability_definition.definition_identity,
            payload_digest=payload_digest,
            payload_digest_scheme=PAYLOAD_DIGEST_SCHEME,
            execution_target_identity=target_binding.target.target_digest,
            policy_version=policy_revision.policy_version,
            policy_identity=policy_revision.policy_identity,
            approval_evidence_identity=approval_evidence.approval_set_digest,
            issuance_timestamp_source_identity=clock_witness.source_identity,
            authorized_at=authorized_at,
            authorization_source_revision=self.authorization_source_revision,
            execution_target=target_binding.target,
            approval_evidence=approval_evidence,
        )
        persisted = self.snapshot_store.persist_prevalidated_in_transaction(
            connection,
            snapshot=snapshot,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        if persisted.created:
            self._append_authority_witness_audit(
                connection,
                snapshot=persisted.snapshot,
                correlation_id=correlation_id,
                selection=selection,
                witness_set=witness_set,
            )
        return persisted.snapshot

    def _validated_request(
        self,
        request: DatabaseRow | None,
    ) -> tuple[DatabaseRow, dict[str, object]]:
        if request is None:
            self._deny("CHANGE_REQUEST_NOT_FOUND")
        assert request is not None

        if str(request["status"]) != "APPROVED":
            self._deny("CHANGE_REQUEST_NOT_APPROVED")
        if str(request["environment"]) != str(request["workspace_environment"]):
            self._deny("WORKSPACE_ENVIRONMENT_MISMATCH")

        review_digest = request["review_content_sha256"]
        if not isinstance(review_digest, str) or not review_digest:
            self._deny("REVIEW_CONTENT_BINDING_MISSING")

        try:
            payload = json.loads(str(request["payload_json"]))
        except (TypeError, json.JSONDecodeError):
            self._deny("REQUEST_PAYLOAD_INVALID")
        if not isinstance(payload, dict):
            self._deny("REQUEST_PAYLOAD_INVALID")
        if canonical_json(payload) != str(request["payload_json"]):
            self._deny("REQUEST_PAYLOAD_NON_CANONICAL")

        expected_review = hashlib.sha256(
            canonical_json(
                {
                    "schema": "change-request-review/v1",
                    "workspace_id": str(request["workspace_id"]),
                    "title": str(request["title"]),
                    "description": str(request["description"]),
                    "risk": str(request["risk"]),
                    "environment": str(request["environment"]),
                    "adapter": str(request["adapter"]),
                    "payload": payload,
                    "requested_by": str(request["requested_by"]),
                }
            ).encode("utf-8")
        ).hexdigest()
        if review_digest != expected_review:
            self._deny("REVIEW_CONTENT_DRIFT")
        return request, payload

    def _approval_records(
        self,
        connection: DatabaseConnection,
        *,
        request: DatabaseRow,
        policy_revision: PolicyRevision,
    ) -> tuple[ApprovalRecord, ...]:
        rows = connection.execute(
            sql.SELECT_AUTHORIZATION_SNAPSHOT_CREATOR_APPROVALS,
            (str(request["id"]),),
        ).fetchall()
        required = policy_revision.required_approvals_for(str(request["environment"]))
        if len(rows) != required:
            self._deny("APPROVAL_COUNT_MISMATCH")

        records: list[ApprovalRecord] = []
        approvers: set[str] = set()
        for row in rows:
            if str(row["decision"]) != "APPROVED":
                self._deny("APPROVAL_DECISION_INVALID")
            if str(row["review_content_sha256"]) != str(request["review_content_sha256"]):
                self._deny("APPROVAL_REVIEW_BINDING_MISMATCH")
            approver_id = str(row["approver_id"])
            if approver_id == str(request["requested_by"]):
                self._deny("REQUESTER_SELF_APPROVAL")
            if approver_id in approvers:
                self._deny("APPROVER_IDENTITY_DUPLICATE")
            approvers.add(approver_id)
            try:
                record = ApprovalRecord(
                    approval_id=str(row["id"]),
                    approver_id=approver_id,
                    decision=str(row["decision"]),
                    approved_at=str(row["created_at"]),
                )
            except ValueError:
                self._deny("APPROVAL_RECORD_INVALID")
            records.append(record)
        return tuple(
            sorted(
                records,
                key=lambda item: (
                    item.approval_id,
                    item.approver_id,
                    item.approved_at,
                ),
            )
        )

    @staticmethod
    def _approval_valid_until(
        *,
        approvals: tuple[ApprovalRecord, ...],
        policy_revision: PolicyRevision,
    ) -> str:
        expiries = []
        for approval in approvals:
            approved_at = datetime.fromisoformat(approval.approved_at)
            expiries.append(
                approved_at + timedelta(seconds=policy_revision.approval_validity_seconds)
            )
        return min(expiries).astimezone(UTC).isoformat(timespec="milliseconds")

    def _select_capability(self, adapter: str) -> CapabilitySelection:
        try:
            selection = self.capability_selection_authority.select(adapter=adapter)
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("CAPABILITY_SELECTION_NOT_FOUND")
        if selection.adapter != adapter:
            self._deny("CAPABILITY_SELECTION_MISMATCH")
        return selection

    def _resolve_capability(self, *, capability: str, environment: str):
        try:
            return self.capability_registry.resolve_for_execution(
                capability=capability,
                environment=environment,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("CAPABILITY_INELIGIBLE")

    def _bind_target(self, *, capability_definition, payload: dict[str, object]):
        try:
            return self.target_binders.bind(
                definition=capability_definition,
                approved_payload=payload,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("TARGET_BINDING_DENIED")

    def _resolve_policy(self) -> PolicyRevision:
        try:
            return self.policy_authority.resolve(self.policy_version)
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("POLICY_REVISION_NOT_FOUND")

    def _append_authority_witness_audit(
        self,
        connection: DatabaseConnection,
        *,
        snapshot: AuthorizationSnapshot,
        correlation_id: str,
        selection: CapabilitySelection,
        witness_set: AuthorityWitnessSet,
    ) -> None:
        self.audit_ledger.append(
            connection,
            actor_id=snapshot.actor_id,
            action="authorization_snapshot.authority_witness",
            target_type="authorization_snapshot",
            target_id=snapshot.snapshot_id,
            payload={
                "correlation_id": correlation_id,
                "snapshot_digest": snapshot.snapshot_digest,
                "authority_witness_set_digest": witness_set.witness_set_digest,
                "permission_decision_digest": witness_set.permission_decision_digest,
                "capability_selection_digest": selection.selection_digest,
                "capability_selection_authority_revision": selection.authority_revision,
                "policy_identity": witness_set.policy_identity,
                "capability_definition_identity": (
                    witness_set.capability_definition_identity
                ),
                "capability_activation_digest": witness_set.capability_activation_digest,
                "target_binding_digest": witness_set.target_binding_digest,
                "approval_certificate_digest": witness_set.approval_certificate_digest,
                "clock_witness_digest": witness_set.clock_witness_digest,
                "revocation_epoch": witness_set.revocation_epoch,
                "authorization_source_revision": snapshot.authorization_source_revision,
            },
        )

    @staticmethod
    def _deny(reason_code: str) -> NoReturn:
        raise SnapshotAuthorizationDenied(reason_code)
