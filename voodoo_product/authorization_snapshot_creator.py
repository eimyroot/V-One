from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, NoReturn, Protocol, runtime_checkable

from . import statements as sql
from .approval_certificate import ApprovalCertificate
from .approval_evidence_resolver import load_approval_evidence_on_connection
from .audit import AuditLedger
from .authority_witness import AuthorityWitnessSet
from .authorization_snapshot import PAYLOAD_DIGEST_SCHEME, AuthorizationSnapshot
from .authorization_snapshot_store import AuthorizationSnapshotStore
from .capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from .evidence_primitives import canonical_json, new_id
from .execution_contract import ApprovalEvidenceSet, REQUIRED_EXECUTION_PERMISSION
from .operational_safety import OperationalSafetyService
from .permission_authority import PermissionAuthority, PermissionDecision, PermissionQuery
from .persistence import DatabaseConnection, DatabaseRow, ProductDatabaseAdapter
from .policy_authority import ImmutablePolicyAuthority, PolicyRevision
from .target_binding import TargetBinderRegistry, TargetBinding
from .trusted_clock import ClockWitness, TrustedClockAuthority

CAPABILITY_SELECTION_TYPE: Final = "capability-selection/v1"
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
    """Content-addressed bridge from reviewed adapter identity to canonical capability."""

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
    """Explicit server-owned adapter-to-capability authority.

    The reviewed request stores an adapter name. That mutable integration label is not itself
    execution authority. This immutable bridge maps it to one canonical versioned capability.
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
    """Live monotonic revocation observation used by snapshot creation."""

    def current_epoch(
        self,
        connection: DatabaseConnection,
        *,
        workspace_id: str,
        environment: str,
        capability_definition_identity: str,
    ) -> int: ...


class SnapshotAuthorizationDenied(PermissionError):
    """Stable fail-closed denial without leaking authority-source internals."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = _require_text(reason_code, field="reason_code")
        super().__init__(self.reason_code)


class AuthoritativeSnapshotCreator:
    """Compose accepted authority facts and persist one immutable snapshot atomically.

    This object is deliberately not wired into ProductService or ExecutionService. It creates
    authorization evidence only; it never issues a grant or causes an external effect.
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
        operational_safety_service: OperationalSafetyService,
        production_effects_enabled: bool,
        authorization_source_revision: str,
        id_factory: IdFactory = new_id,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("snapshot creator audit ledger must use its database")
        if snapshot_store.db is not database:
            raise ValueError("snapshot creator store must use its database")
        if snapshot_store.audit_ledger is not audit_ledger:
            raise ValueError("snapshot creator store must use its audit ledger")
        if operational_safety_service.db is not database:
            raise ValueError("snapshot creator safety service must use its database")
        if operational_safety_service.audit_ledger is not audit_ledger:
            raise ValueError("snapshot creator safety service must use its audit ledger")
        if not isinstance(permission_authority, PermissionAuthority):
            raise ValueError("permission_authority is invalid")
        if not isinstance(policy_authority, ImmutablePolicyAuthority):
            raise ValueError("policy_authority is invalid")
        if not isinstance(capability_registry, ImmutableCapabilityRegistry):
            raise ValueError("capability_registry is invalid")
        if not isinstance(capability_selection_authority, CapabilitySelectionAuthority):
            raise ValueError("capability_selection_authority is invalid")
        if not isinstance(target_binders, TargetBinderRegistry):
            raise ValueError("target_binders is invalid")
        if not isinstance(trusted_clock, TrustedClockAuthority):
            raise ValueError("trusted_clock is invalid")
        if not isinstance(revocation_authority, RevocationEpochAuthority):
            raise ValueError("revocation_authority is invalid")
        if type(production_effects_enabled) is not bool:
            raise ValueError("production_effects_enabled must be boolean")
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
        self.operational_safety_service = operational_safety_service
        self.production_effects_enabled = production_effects_enabled
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

        # Any exception escapes this context and therefore rolls back snapshot and audit writes.
        with self.db.transaction() as connection:
            return self._create_in_transaction(
                connection,
                actor_id=actor_id,
                request_id=request_id,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

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
            sql.SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT,
            (request_id,),
        ).fetchone()
        request, payload = self._validated_request(request)

        environment = str(request["environment"])
        workspace_id = str(request["workspace_id"])

        if environment == "production" and not self.production_effects_enabled:
            self._deny("PRODUCTION_EFFECTS_DISABLED")
        if self.operational_safety_service.is_active(connection):
            self._deny("EMERGENCY_STOP_ACTIVE")

        selection = self._select_capability(str(request["adapter"]))
        capability_definition, capability_activation = self._resolve_capability(
            capability=selection.capability,
            environment=environment,
        )
        target_binding = self._bind_target(
            capability_definition=capability_definition,
            payload=payload,
        )
        policy_revision = self._resolve_policy()
        clock_witness = self._resolve_clock(environment=environment)
        approval_evidence = self._resolve_approval_evidence(
            connection,
            request_id=request_id,
            capability=capability_definition.capability,
            target_binding=target_binding,
            policy_revision=policy_revision,
            clock_witness=clock_witness,
        )
        approval_certificate = ApprovalCertificate.create(
            review_content_sha256=str(request["review_content_sha256"]),
            policy_revision=policy_revision,
            approval_evidence=approval_evidence,
        )
        permission_decision = self._resolve_permission(
            actor_id=actor_id,
            workspace_id=workspace_id,
            environment=environment,
        )
        revocation_epoch = self._resolve_revocation_epoch(
            connection,
            workspace_id=workspace_id,
            environment=environment,
            capability_definition_identity=capability_definition.definition_identity,
        )
        witness_set = self._build_witness_set(
            permission_decision=permission_decision,
            policy_revision=policy_revision,
            capability_definition=capability_definition,
            capability_activation=capability_activation,
            target_binding=target_binding,
            approval_certificate=approval_certificate,
            clock_witness=clock_witness,
            revocation_epoch=revocation_epoch,
        )

        snapshot = AuthorizationSnapshot.create(
            snapshot_id=self._id_factory("authz"),
            execution_id=self._id_factory("exec"),
            request_id=request_id,
            review_content_sha256=str(request["review_content_sha256"]),
            actor_id=actor_id,
            workspace_id=workspace_id,
            environment=environment,
            capability=capability_definition.capability,
            capability_definition_identity=capability_definition.definition_identity,
            payload_digest=approval_evidence.payload_digest,
            payload_digest_scheme=PAYLOAD_DIGEST_SCHEME,
            execution_target_identity=target_binding.target.target_digest,
            policy_version=policy_revision.policy_version,
            policy_identity=policy_revision.policy_identity,
            approval_evidence_identity=approval_evidence.approval_set_digest,
            issuance_timestamp_source_identity=clock_witness.source_identity,
            authorized_at=clock_witness.observed_at,
            authorization_source_revision=self.authorization_source_revision,
            execution_target=target_binding.target,
            approval_evidence=approval_evidence,
        )

        existing = connection.execute(
            sql.SELECT_AUTHORIZATION_SNAPSHOT_BY_IDEMPOTENCY_KEY,
            (idempotency_key,),
        ).fetchone()
        persisted = self.snapshot_store.persist_prevalidated_on_connection(
            connection,
            snapshot=snapshot,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        if existing is None:
            self._append_authority_witness_audit(
                connection,
                snapshot=persisted,
                correlation_id=correlation_id,
                selection=selection,
                witness_set=witness_set,
            )
        return persisted

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

        raw_payload = str(request["payload_json"])
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            self._deny("REQUEST_PAYLOAD_INVALID")
        if not isinstance(payload, dict):
            self._deny("REQUEST_PAYLOAD_INVALID")
        if canonical_json(payload) != raw_payload:
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

    def _select_capability(self, adapter: str) -> CapabilitySelection:
        try:
            selection = self.capability_selection_authority.select(adapter=adapter)
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("CAPABILITY_SELECTION_NOT_FOUND")
        if selection.adapter != adapter:
            self._deny("CAPABILITY_SELECTION_MISMATCH")
        return selection

    def _resolve_capability(
        self,
        *,
        capability: str,
        environment: str,
    ) -> tuple[CapabilityDefinition, CapabilityActivation]:
        try:
            return self.capability_registry.resolve_for_execution(
                capability=capability,
                environment=environment,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("CAPABILITY_INELIGIBLE")

    def _bind_target(
        self,
        *,
        capability_definition: CapabilityDefinition,
        payload: dict[str, object],
    ) -> TargetBinding:
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

    def _resolve_clock(self, *, environment: str) -> ClockWitness:
        try:
            witness = self.trusted_clock.witness(environment=environment)
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("TRUSTED_CLOCK_DENIED")
        if witness.source_identity != self.trusted_clock.source_identity:
            self._deny("TRUSTED_CLOCK_BINDING_MISMATCH")
        return witness

    def _resolve_approval_evidence(
        self,
        connection: DatabaseConnection,
        *,
        request_id: str,
        capability: str,
        target_binding: TargetBinding,
        policy_revision: PolicyRevision,
        clock_witness: ClockWitness,
    ) -> ApprovalEvidenceSet:
        try:
            return load_approval_evidence_on_connection(
                connection,
                request_id=request_id,
                capability=capability,
                execution_target=target_binding.target,
                policy_revision=policy_revision,
                clock_witness=clock_witness,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("APPROVAL_EVIDENCE_DENIED")

    def _resolve_permission(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        environment: str,
    ) -> PermissionDecision:
        query = PermissionQuery(
            actor_id=actor_id,
            workspace_id=workspace_id,
            environment=environment,
            permission=REQUIRED_EXECUTION_PERMISSION,
        )
        try:
            decision = self.permission_authority.decide(query)
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("EXECUTION_PERMISSION_DENIED")
        if not isinstance(decision, PermissionDecision):
            self._deny("PERMISSION_DECISION_INVALID")
        expected = (
            actor_id,
            workspace_id,
            environment,
            REQUIRED_EXECUTION_PERMISSION,
        )
        actual = (
            decision.actor_id,
            decision.workspace_id,
            decision.environment,
            decision.permission,
        )
        if actual != expected:
            self._deny("PERMISSION_DECISION_BINDING_MISMATCH")
        if not decision.granted:
            self._deny("EXECUTION_PERMISSION_DENIED")
        return decision

    def _resolve_revocation_epoch(
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
        except (LookupError, PermissionError, RuntimeError, ValueError):
            self._deny("REVOCATION_DENIED")
        if type(epoch) is not int or epoch < 0:
            self._deny("REVOCATION_EPOCH_INVALID")
        return epoch

    def _build_witness_set(
        self,
        *,
        permission_decision: PermissionDecision,
        policy_revision: PolicyRevision,
        capability_definition: CapabilityDefinition,
        capability_activation: CapabilityActivation,
        target_binding: TargetBinding,
        approval_certificate: ApprovalCertificate,
        clock_witness: ClockWitness,
        revocation_epoch: int,
    ) -> AuthorityWitnessSet:
        try:
            return AuthorityWitnessSet.create(
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
                "capability_definition_identity": witness_set.capability_definition_identity,
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
