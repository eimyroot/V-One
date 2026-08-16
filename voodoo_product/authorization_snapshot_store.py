from __future__ import annotations

import json
from collections.abc import Callable

from . import statements as sql
from .audit import AuditLedger
from .authorization_snapshot import AuthorizationSnapshot
from .evidence_primitives import canonical_json, utc_now
from .execution_contract import ApprovalEvidenceSet, ExecutionTarget
from .persistence import (
    DatabaseConnection,
    DatabaseIntegrityError,
    DatabaseRow,
    ProductDatabaseAdapter,
)

Clock = Callable[[], str]


class AuthorizationSnapshotConflict(RuntimeError):
    """Raised when an idempotency or immutable snapshot identity conflicts."""


class AuthorizationSnapshotSourceError(RuntimeError):
    """Raised when current authoritative request facts do not match the snapshot."""


class AuthorizationSnapshotStore:
    """Persistence-only boundary for prevalidated authorization snapshots.

    This store does not evaluate approval policy, capability eligibility, target binding, or
    execution permission. It is intentionally not composed into the product runtime.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        clock: Clock = utc_now,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("authorization snapshot audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._clock = clock

    def persist_prevalidated(
        self,
        *,
        snapshot: AuthorizationSnapshot,
        idempotency_key: str,
        correlation_id: str,
    ) -> AuthorizationSnapshot:
        snapshot, idempotency_key, correlation_id = self._validated_persistence_inputs(
            snapshot=snapshot,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        with self.db.transaction() as connection:
            return self._persist_prevalidated_on_connection(
                connection,
                snapshot=snapshot,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

    def persist_prevalidated_on_connection(
        self,
        connection: DatabaseConnection,
        *,
        snapshot: AuthorizationSnapshot,
        idempotency_key: str,
        correlation_id: str,
    ) -> AuthorizationSnapshot:
        """Persist within the caller-owned transaction without commit or rollback."""

        snapshot, idempotency_key, correlation_id = self._validated_persistence_inputs(
            snapshot=snapshot,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        return self._persist_prevalidated_on_connection(
            connection,
            snapshot=snapshot,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )

    def _persist_prevalidated_on_connection(
        self,
        connection: DatabaseConnection,
        *,
        snapshot: AuthorizationSnapshot,
        idempotency_key: str,
        correlation_id: str,
    ) -> AuthorizationSnapshot:
        existing = connection.execute(
            sql.SELECT_AUTHORIZATION_SNAPSHOT_BY_IDEMPOTENCY_KEY,
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            if str(existing["idempotency_binding_digest"]) != snapshot.idempotency_binding_digest:
                raise AuthorizationSnapshotConflict(
                    "idempotency key is bound to different authorization inputs"
                )
            return self._decode(existing)

        request = connection.execute(
            sql.SELECT_AUTHORIZATION_SNAPSHOT_REQUEST_CONTEXT,
            (snapshot.request_id,),
        ).fetchone()
        self._require_request_binding(snapshot=snapshot, request=request)

        try:
            connection.execute(
                sql.INSERT_AUTHORIZATION_SNAPSHOT,
                (
                    snapshot.snapshot_id,
                    snapshot.execution_id,
                    snapshot.request_id,
                    snapshot.actor_id,
                    snapshot.workspace_id,
                    snapshot.environment,
                    snapshot.review_content_sha256,
                    idempotency_key,
                    snapshot.idempotency_binding_digest,
                    snapshot.snapshot_digest,
                    canonical_json(snapshot.to_dict()),
                    snapshot.execution_target_json,
                    snapshot.approval_evidence_json,
                    self._clock(),
                ),
            )
        except DatabaseIntegrityError as exc:
            raise AuthorizationSnapshotConflict(
                "authorization snapshot immutable identity conflicts"
            ) from exc

        self.audit_ledger.append(
            connection,
            actor_id=snapshot.actor_id,
            action="authorization_snapshot.create",
            target_type="authorization_snapshot",
            target_id=snapshot.snapshot_id,
            payload={
                "correlation_id": correlation_id,
                "snapshot_digest": snapshot.snapshot_digest,
                "execution_id": snapshot.execution_id,
                "request_id": snapshot.request_id,
                "review_content_sha256": snapshot.review_content_sha256,
                "workspace_id": snapshot.workspace_id,
                "environment": snapshot.environment,
                "payload_digest": snapshot.payload_digest,
                "payload_digest_scheme": snapshot.payload_digest_scheme,
                "target_kind": snapshot.target_kind,
                "target_digest": snapshot.target_digest,
                "capability": snapshot.capability,
                "capability_definition_identity": snapshot.capability_definition_identity,
                "policy_version": snapshot.policy_version,
                "policy_identity": snapshot.policy_identity,
                "approval_set_digest": snapshot.approval_set_digest,
                "approval_valid_until": snapshot.approval_valid_until,
                "issuance_timestamp_source_identity": (
                    snapshot.issuance_timestamp_source_identity
                ),
                "authorized_at": snapshot.authorized_at,
                "authorization_source_revision": snapshot.authorization_source_revision,
            },
        )
        return snapshot

    def get(self, snapshot_id: str) -> AuthorizationSnapshot:
        snapshot_id = self._require_token(snapshot_id, field="snapshot_id")
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_AUTHORIZATION_SNAPSHOT,
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise LookupError("authorization snapshot not found")
        return self._decode(row)

    def get_by_idempotency_key(self, idempotency_key: str) -> AuthorizationSnapshot | None:
        idempotency_key = self._require_token(idempotency_key, field="idempotency_key")
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_AUTHORIZATION_SNAPSHOT_BY_IDEMPOTENCY_KEY,
                (idempotency_key,),
            ).fetchone()
        return None if row is None else self._decode(row)

    @classmethod
    def _validated_persistence_inputs(
        cls,
        *,
        snapshot: AuthorizationSnapshot,
        idempotency_key: str,
        correlation_id: str,
    ) -> tuple[AuthorizationSnapshot, str, str]:
        if not isinstance(snapshot, AuthorizationSnapshot):
            raise ValueError("snapshot is invalid")
        return (
            snapshot,
            cls._require_token(idempotency_key, field="idempotency_key"),
            cls._require_token(correlation_id, field="correlation_id"),
        )

    @staticmethod
    def _require_request_binding(
        *,
        snapshot: AuthorizationSnapshot,
        request: DatabaseRow | None,
    ) -> None:
        if request is None:
            raise AuthorizationSnapshotSourceError("change request not found")
        if str(request["status"]) != "APPROVED":
            raise AuthorizationSnapshotSourceError(
                "change request is not in an approved immutable-review state"
            )
        expected = {
            "workspace_id": snapshot.workspace_id,
            "environment": snapshot.environment,
            "review_content_sha256": snapshot.review_content_sha256,
        }
        mismatches = [
            field for field, value in expected.items() if str(request[field]) != value
        ]
        if mismatches:
            raise AuthorizationSnapshotSourceError(
                f"change request snapshot bindings mismatch: {sorted(mismatches)}"
            )

    @staticmethod
    def _decode(row: DatabaseRow) -> AuthorizationSnapshot:
        try:
            snapshot_value = json.loads(str(row["snapshot_json"]))
            target_value = json.loads(str(row["execution_target_json"]))
            approval_value = json.loads(str(row["approval_evidence_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("authorization snapshot storage is not valid JSON") from exc
        if not isinstance(snapshot_value, dict):
            raise RuntimeError("authorization snapshot storage is invalid")
        if not isinstance(target_value, dict) or not isinstance(approval_value, dict):
            raise RuntimeError("authorization snapshot child storage is invalid")
        if canonical_json(target_value) != str(row["execution_target_json"]):
            raise RuntimeError("execution target bytes are not canonical")
        if canonical_json(approval_value) != str(row["approval_evidence_json"]):
            raise RuntimeError("approval evidence bytes are not canonical")
        if canonical_json(snapshot_value) != str(row["snapshot_json"]):
            raise RuntimeError("authorization snapshot bytes are not canonical")

        target = ExecutionTarget.from_dict(target_value)
        approval_evidence = ApprovalEvidenceSet.from_dict(approval_value)
        snapshot = AuthorizationSnapshot.from_dict(
            snapshot_value,
            execution_target=target,
            approval_evidence=approval_evidence,
        )
        row_bindings = {
            "id": snapshot.snapshot_id,
            "execution_id": snapshot.execution_id,
            "request_id": snapshot.request_id,
            "actor_id": snapshot.actor_id,
            "workspace_id": snapshot.workspace_id,
            "environment": snapshot.environment,
            "review_content_sha256": snapshot.review_content_sha256,
            "idempotency_binding_digest": snapshot.idempotency_binding_digest,
            "snapshot_digest": snapshot.snapshot_digest,
        }
        mismatches = [
            field
            for field, value in row_bindings.items()
            if str(row[field]) != value
        ]
        if mismatches:
            raise RuntimeError(
                f"authorization snapshot storage bindings mismatch: {sorted(mismatches)}"
            )
        return snapshot

    @staticmethod
    def _require_token(value: object, *, field: str) -> str:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or "\x00" in value
        ):
            raise ValueError(f"{field} is invalid")
        return value
