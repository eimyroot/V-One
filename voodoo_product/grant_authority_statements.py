from __future__ import annotations

from types import MappingProxyType

from .persistence import DatabaseStatement


def _read(name: str, sql: str) -> DatabaseStatement:
    return DatabaseStatement(name=name, mode="read", sqlite_sql=sql)


SELECT_SNAPSHOT_AUTHORITY_WITNESS = _read(
    "grant_authority.select_snapshot_authority_witness",
    """
    SELECT id, actor_id, action, target_type, target_id,
           payload_json, previous_hash, event_hash, created_at
    FROM audit_events
    WHERE action = 'authorization_snapshot.authority_witness'
      AND target_type = 'authorization_snapshot'
      AND target_id = ?
    ORDER BY sequence DESC
    LIMIT 2
    """,
)

ALL_GRANT_AUTHORITY_STATEMENTS = (SELECT_SNAPSHOT_AUTHORITY_WITNESS,)

GRANT_AUTHORITY_STATEMENTS_BY_NAME = MappingProxyType(
    {statement.name: statement for statement in ALL_GRANT_AUTHORITY_STATEMENTS}
)
