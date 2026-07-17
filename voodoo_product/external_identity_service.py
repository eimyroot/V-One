from __future__ import annotations

import hashlib
from typing import Any

from . import external_identity_statements as identity_sql
from .audit import AuditLedgerWriter
from .external_identity import ExternalIdentityKey
from .persistence import (
    DatabaseConnection,
    DatabaseIntegrityError,
    DatabaseRow,
    ProductDatabaseAdapter,
)
from .security import ROLE_PERMISSIONS
from .service import new_id, utc_now


class GovernedExternalIdentityService:
    """Internal-only lifecycle service for immutable external identity bindings."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedgerWriter,
    ) -> None:
        self.db = database
        self.audit_ledger = audit_ledger

    def create_binding(
        self,
        *,
        actor_id: str,
        user_id: str,
        provider: str,
        issuer: str,
        subject: str,
        reason: str,
    ) -> dict[str, Any]:
        key = ExternalIdentityKey(provider=provider, issuer=issuer, subject=subject)
        normalized_reason = self._validate_reason(reason)
        binding_id = new_id("xid")
        created_at = utc_now()

        with self.db.transaction() as connection:
            self._require_active_administrator(connection, actor_id)
            target = self._require_active_target(connection, user_id)
            if actor_id == user_id:
                raise PermissionError("administrators cannot bind their own external identity")
            try:
                connection.execute(
                    identity_sql.INSERT_BINDING,
                    (
                        binding_id,
                        key.provider,
                        key.issuer,
                        key.subject,
                        user_id,
                        created_at,
                    ),
                )
            except DatabaseIntegrityError as exc:
                raise RuntimeError(
                    "external identity or internal user is already bound for this issuer"
                ) from exc
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="external_identity_binding.create",
                target_type="external_identity_binding",
                target_id=binding_id,
                payload={
                    "provider": key.provider,
                    "issuer": key.issuer,
                    "subject_digest": self._subject_digest(key.subject),
                    "user_id": user_id,
                    "user_role": str(target["role"]),
                    "reason": normalized_reason,
                },
            )

        return {
            "id": binding_id,
            "provider": key.provider,
            "issuer": key.issuer,
            "subject_digest": self._subject_digest(key.subject),
            "user_id": user_id,
            "active": True,
            "created_at": created_at,
        }

    def disable_binding(
        self,
        *,
        actor_id: str,
        binding_id: str,
        reason: str,
    ) -> dict[str, Any]:
        normalized_reason = self._validate_reason(reason)
        disabled_at = utc_now()

        with self.db.transaction() as connection:
            self._require_active_administrator(connection, actor_id)
            binding = connection.execute(
                identity_sql.SELECT_BINDING,
                (binding_id,),
            ).fetchone()
            if binding is None:
                raise LookupError("external identity binding not found")
            if not int(binding["active"]) or binding["disabled_at"] is not None:
                raise RuntimeError("external identity binding is already disabled")
            if actor_id == str(binding["user_id"]):
                raise PermissionError("administrators cannot disable their own external identity")

            disabled = connection.execute(
                identity_sql.DISABLE_BINDING,
                (disabled_at, binding_id),
            ).fetchone()
            if disabled is None:
                raise RuntimeError("external identity binding changed during disablement")
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="external_identity_binding.disable",
                target_type="external_identity_binding",
                target_id=binding_id,
                payload={
                    "provider": str(binding["provider"]),
                    "issuer": str(binding["issuer"]),
                    "subject_digest": self._subject_digest(str(binding["subject"])),
                    "user_id": str(binding["user_id"]),
                    "reason": normalized_reason,
                },
            )

        return {
            "id": binding_id,
            "user_id": str(binding["user_id"]),
            "active": False,
            "disabled_at": disabled_at,
        }

    def resolve_active_binding(
        self,
        *,
        provider: str,
        issuer: str,
        subject: str,
    ) -> dict[str, str]:
        key = ExternalIdentityKey(provider=provider, issuer=issuer, subject=subject)
        with self.db.connect() as connection:
            row = connection.execute(
                identity_sql.RESOLVE_ACTIVE_BINDING,
                (key.provider, key.issuer, key.subject),
            ).fetchone()
        if row is None:
            raise PermissionError("external identity is not actively bound")
        role = str(row["role"])
        if role not in ROLE_PERMISSIONS:
            raise PermissionError("bound account role is invalid")
        return {
            "binding_id": str(row["binding_id"]),
            "user_id": str(row["user_id"]),
            "username": str(row["username"]),
            "role": role,
        }

    @staticmethod
    def _validate_reason(reason: str) -> str:
        normalized = reason.strip()
        if not 3 <= len(normalized) <= 2_000:
            raise ValueError("external identity governance reason must contain 3 to 2000 characters")
        return normalized

    @staticmethod
    def _subject_digest(subject: str) -> str:
        return hashlib.sha256(subject.encode("utf-8")).hexdigest()

    @staticmethod
    def _require_active_administrator(
        connection: DatabaseConnection,
        actor_id: str,
    ) -> DatabaseRow:
        actor = connection.execute(
            identity_sql.SELECT_GOVERNANCE_USER,
            (actor_id,),
        ).fetchone()
        if actor is None or not int(actor["active"]):
            raise PermissionError("external identity governance requires an active administrator")
        if str(actor["role"]) != "administrator":
            raise PermissionError("external identity governance requires administrator role")
        return actor

    @staticmethod
    def _require_active_target(
        connection: DatabaseConnection,
        user_id: str,
    ) -> DatabaseRow:
        target = connection.execute(
            identity_sql.SELECT_GOVERNANCE_USER,
            (user_id,),
        ).fetchone()
        if target is None:
            raise LookupError("external identity target user not found")
        if not int(target["active"]):
            raise PermissionError("external identity target user is inactive")
        if str(target["role"]) not in ROLE_PERMISSIONS:
            raise PermissionError("external identity target role is invalid")
        return target
