from __future__ import annotations

from types import MappingProxyType

from .persistence import DatabaseStatement


def _read(name: str, sql: str) -> DatabaseStatement:
    return DatabaseStatement(name=name, mode="read", sqlite_sql=sql)


def _write(name: str, sql: str) -> DatabaseStatement:
    return DatabaseStatement(name=name, mode="write", sqlite_sql=sql)


SELECT_GOVERNANCE_USER = _read(
    "external_identity.select_governance_user",
    "SELECT id, username, role, active FROM users WHERE id = ?",
)

INSERT_BINDING = _write(
    "external_identity.insert_binding",
    """
    INSERT INTO external_identity_bindings(
        id, provider, issuer, subject, user_id, active, created_at, disabled_at
    ) VALUES (?, ?, ?, ?, ?, 1, ?, NULL)
    """,
)

SELECT_BINDING = _read(
    "external_identity.select_binding",
    """
    SELECT id, provider, issuer, subject, user_id, active, created_at, disabled_at
    FROM external_identity_bindings
    WHERE id = ?
    """,
)

DISABLE_BINDING = _write(
    "external_identity.disable_binding",
    """
    UPDATE external_identity_bindings
    SET active = 0, disabled_at = ?
    WHERE id = ? AND active = 1 AND disabled_at IS NULL
    RETURNING id
    """,
)

RESOLVE_ACTIVE_BINDING = _read(
    "external_identity.resolve_active_binding",
    """
    SELECT e.id AS binding_id, e.user_id, u.username, u.role
    FROM external_identity_bindings e
    JOIN users u ON u.id = e.user_id
    WHERE e.provider = ? AND e.issuer = ? AND e.subject = ?
      AND e.active = 1 AND e.disabled_at IS NULL AND u.active = 1
    """,
)

ALL_EXTERNAL_IDENTITY_STATEMENTS = (
    SELECT_GOVERNANCE_USER,
    INSERT_BINDING,
    SELECT_BINDING,
    DISABLE_BINDING,
    RESOLVE_ACTIVE_BINDING,
)

EXTERNAL_IDENTITY_STATEMENTS_BY_NAME = MappingProxyType(
    {statement.name: statement for statement in ALL_EXTERNAL_IDENTITY_STATEMENTS}
)
