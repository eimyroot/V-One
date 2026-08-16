from __future__ import annotations

from types import MappingProxyType

from .persistence import DatabaseStatement


def _read(name: str, sql: str) -> DatabaseStatement:
    return DatabaseStatement(name=name, mode="read", sqlite_sql=sql)


SELECT_APPROVAL_EVIDENCE = _read(
    "approval_evidence.select_approvals",
    """
    SELECT id, approver_id, decision, review_content_sha256, created_at
    FROM approvals
    WHERE request_id = ?
    ORDER BY id, approver_id, created_at
    """,
)

ALL_APPROVAL_EVIDENCE_STATEMENTS = (SELECT_APPROVAL_EVIDENCE,)

APPROVAL_EVIDENCE_STATEMENTS_BY_NAME = MappingProxyType(
    {statement.name: statement for statement in ALL_APPROVAL_EVIDENCE_STATEMENTS}
)
