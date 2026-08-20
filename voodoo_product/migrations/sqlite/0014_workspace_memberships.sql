CREATE TABLE IF NOT EXISTS workspace_memberships (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    membership_role TEXT NOT NULL CHECK(membership_role IN ('owner', 'member')),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY(workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user
ON workspace_memberships(user_id, workspace_id);

CREATE TRIGGER IF NOT EXISTS trg_workspace_memberships_role_insert
BEFORE INSERT ON workspace_memberships
FOR EACH ROW
WHEN NEW.membership_role NOT IN ('owner', 'member')
BEGIN
    SELECT RAISE(ABORT, 'invalid workspace membership role');
END;

CREATE TRIGGER IF NOT EXISTS trg_workspace_memberships_role_update
BEFORE UPDATE OF membership_role ON workspace_memberships
FOR EACH ROW
WHEN NEW.membership_role NOT IN ('owner', 'member')
BEGIN
    SELECT RAISE(ABORT, 'invalid workspace membership role');
END;
