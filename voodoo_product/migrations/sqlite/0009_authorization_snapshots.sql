CREATE TABLE authorization_snapshots (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL REFERENCES change_requests(id),
    actor_id TEXT NOT NULL REFERENCES users(id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    environment TEXT NOT NULL
        CHECK(environment IN ('local', 'development', 'staging', 'production')),
    review_content_sha256 TEXT NOT NULL
        CHECK(
            length(review_content_sha256) = 64
            AND review_content_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
    idempotency_key TEXT NOT NULL UNIQUE,
    idempotency_binding_digest TEXT NOT NULL
        CHECK(
            length(idempotency_binding_digest) = 64
            AND idempotency_binding_digest NOT GLOB '*[^0-9a-f]*'
        ),
    snapshot_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(snapshot_digest) = 64
            AND snapshot_digest NOT GLOB '*[^0-9a-f]*'
        ),
    snapshot_json TEXT NOT NULL,
    execution_target_json TEXT NOT NULL,
    approval_evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_authorization_snapshots_request
ON authorization_snapshots(request_id);

CREATE INDEX idx_authorization_snapshots_workspace_environment
ON authorization_snapshots(workspace_id, environment);

CREATE TRIGGER trg_authorization_snapshots_request_binding_insert
BEFORE INSERT ON authorization_snapshots
WHEN NOT EXISTS (
    SELECT 1
    FROM change_requests cr
    JOIN workspaces w ON w.id = cr.workspace_id
    WHERE cr.id = NEW.request_id
      AND cr.status = 'APPROVED'
      AND cr.workspace_id = NEW.workspace_id
      AND cr.environment = NEW.environment
      AND w.environment = NEW.environment
      AND cr.review_content_sha256 = NEW.review_content_sha256
      AND cr.review_content_sha256 IS NOT NULL
)
BEGIN
    SELECT RAISE(ABORT, 'authorization snapshot request binding is invalid');
END;

CREATE TRIGGER trg_authorization_snapshots_immutable_update
BEFORE UPDATE ON authorization_snapshots
BEGIN
    SELECT RAISE(ABORT, 'authorization snapshot is immutable');
END;

CREATE TRIGGER trg_authorization_snapshots_immutable_delete
BEFORE DELETE ON authorization_snapshots
BEGIN
    SELECT RAISE(ABORT, 'authorization snapshot is immutable');
END;
