from __future__ import annotations

from .persistence import DatabaseStatement

INSERT_WORKSPACE_MEMBERSHIP = DatabaseStatement(
    name="workspace_memberships.insert",
    mode="write",
    sqlite_sql="""
        INSERT INTO workspace_memberships(
            workspace_id, user_id, membership_role, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?)
    """,
)
SELECT_WORKSPACE_MEMBERSHIP = DatabaseStatement(
    name="workspace_memberships.select",
    mode="read",
    sqlite_sql="""
        SELECT workspace_id, user_id, membership_role, created_by, created_at
        FROM workspace_memberships
        WHERE workspace_id = ? AND user_id = ?
    """,
)
LIST_WORKSPACE_MEMBERS = DatabaseStatement(
    name="workspace_memberships.list",
    mode="read",
    sqlite_sql="""
        SELECT wm.workspace_id, wm.user_id, wm.membership_role, wm.created_by, wm.created_at,
               u.username, u.role, u.active
        FROM workspace_memberships wm
        JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = ?
        ORDER BY u.username
    """,
)
DELETE_WORKSPACE_MEMBERSHIP = DatabaseStatement(
    name="workspace_memberships.delete",
    mode="write",
    sqlite_sql="""
        DELETE FROM workspace_memberships
        WHERE workspace_id = ? AND user_id = ?
        RETURNING user_id, membership_role
    """,
)
COUNT_WORKSPACE_OWNERS = DatabaseStatement(
    name="workspace_memberships.count_owners",
    mode="read",
    sqlite_sql="""
        SELECT COUNT(*) AS count
        FROM workspace_memberships
        WHERE workspace_id = ? AND membership_role = 'owner'
    """,
)
