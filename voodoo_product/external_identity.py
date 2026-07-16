from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from . import statements as sql
from .identity import (
    ExternalIdentityClaims,
    validate_external_group,
    validate_external_identity_reference,
)
from .persistence import (
    DatabaseConnection,
    DatabaseIntegrityError,
    ProductDatabaseAdapter,
)
from .security import ROLE_PERMISSIONS


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class ExternalIdentityRegistry:
    def __init__(self, database: ProductDatabaseAdapter):
        self._database = database

    @staticmethod
    def _require_administrator(connection: DatabaseConnection, actor_id: str) -> None:
        actor = connection.execute(sql.SELECT_ACTIVE_USER, (actor_id,)).fetchone()
        if (
            actor is None
            or not int(actor["active"])
            or str(actor["role"]) != "administrator"
        ):
            raise PermissionError("external identity administration requires an administrator")

    def create_binding(
        self,
        *,
        actor_id: str,
        provider: str,
        issuer: str,
        subject: str,
        user_id: str,
    ) -> dict[str, Any]:
        validate_external_identity_reference(
            provider=provider,
            issuer=issuer,
            subject=subject,
        )
        binding_id = _new_id("xid")
        created_at = _utc_now()
        with self._database.transaction() as connection:
            self._require_administrator(connection, actor_id)
            user = connection.execute(sql.SELECT_ACTIVE_USER, (user_id,)).fetchone()
            if (
                user is None
                or not int(user["active"])
                or str(user["role"]) not in ROLE_PERMISSIONS
            ):
                raise ValueError("external identity requires an active user with a valid role")
            try:
                connection.execute(
                    sql.INSERT_EXTERNAL_IDENTITY_BINDING,
                    (
                        binding_id,
                        provider,
                        issuer,
                        subject,
                        user_id,
                        actor_id,
                        created_at,
                    ),
                )
            except DatabaseIntegrityError as exc:
                raise ValueError("external identity binding conflicts with existing identity") from exc
        return {
            "id": binding_id,
            "provider": provider,
            "issuer": issuer,
            "subject": subject,
            "user_id": user_id,
            "created_by": actor_id,
            "created_at": created_at,
        }

    def create_role_mapping(
        self,
        *,
        actor_id: str,
        provider: str,
        issuer: str,
        external_group: str,
        internal_role: str,
    ) -> dict[str, Any]:
        validate_external_identity_reference(
            provider=provider,
            issuer=issuer,
            subject="mapping-contract",
        )
        validate_external_group(external_group)
        if internal_role not in ROLE_PERMISSIONS:
            raise ValueError("external role mapping targets an unknown role")
        mapping_id = _new_id("xrm")
        created_at = _utc_now()
        with self._database.transaction() as connection:
            self._require_administrator(connection, actor_id)
            try:
                connection.execute(
                    sql.INSERT_EXTERNAL_ROLE_MAPPING,
                    (
                        mapping_id,
                        provider,
                        issuer,
                        external_group,
                        internal_role,
                        actor_id,
                        created_at,
                    ),
                )
            except DatabaseIntegrityError as exc:
                raise ValueError("external group already has an immutable role mapping") from exc
        return {
            "id": mapping_id,
            "provider": provider,
            "issuer": issuer,
            "external_group": external_group,
            "internal_role": internal_role,
            "created_by": actor_id,
            "created_at": created_at,
        }

    def resolve(self, claims: ExternalIdentityClaims) -> dict[str, str]:
        with self._database.connect() as connection:
            identity = connection.execute(
                sql.SELECT_EXTERNAL_IDENTITY,
                (claims.provider, claims.issuer, claims.subject),
            ).fetchone()
            if identity is None or not int(identity["active"]):
                raise PermissionError("external identity is not authorized")
            user_role = str(identity["role"])
            if user_role not in ROLE_PERMISSIONS:
                raise PermissionError("external identity is not authorized")

            mapped_roles: set[str] = set()
            for group in claims.groups:
                mapping = connection.execute(
                    sql.SELECT_EXTERNAL_ROLE_MAPPING,
                    (claims.provider, claims.issuer, group),
                ).fetchone()
                if mapping is not None:
                    mapped_role = str(mapping["internal_role"])
                    if mapped_role not in ROLE_PERMISSIONS:
                        raise PermissionError("external identity role mapping is invalid")
                    mapped_roles.add(mapped_role)

        if mapped_roles != {user_role}:
            raise PermissionError("external identity role authorization failed")
        return {
            "id": str(identity["user_id"]),
            "username": str(identity["username"]),
            "role": user_role,
        }
