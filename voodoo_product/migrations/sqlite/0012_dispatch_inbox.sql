CREATE TABLE dispatch_inbox_v1 (
    admission_id TEXT PRIMARY KEY
        CHECK(
            length(admission_id) = 64
            AND admission_id NOT GLOB '*[^0-9a-f]*'
        ),
    dispatch_id TEXT NOT NULL UNIQUE
        CHECK(
            length(dispatch_id) = 64
            AND dispatch_id NOT GLOB '*[^0-9a-f]*'
        ),
    envelope_digest TEXT NOT NULL
        CHECK(
            length(envelope_digest) = 64
            AND envelope_digest NOT GLOB '*[^0-9a-f]*'
        ),
    outbox_id TEXT NOT NULL UNIQUE
        REFERENCES dispatch_outbox_v1(outbox_id),
    outbox_entry_digest TEXT NOT NULL UNIQUE
        REFERENCES dispatch_outbox_v1(entry_digest),
    execution_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    environment TEXT NOT NULL
        CHECK(environment IN ('local', 'development', 'staging', 'production')),
    execution_capsule_digest TEXT NOT NULL
        CHECK(
            length(execution_capsule_digest) = 64
            AND execution_capsule_digest NOT GLOB '*[^0-9a-f]*'
        ),
    runner_class TEXT NOT NULL CHECK(length(runner_class) > 0),
    admission_revision TEXT NOT NULL CHECK(length(admission_revision) > 0),
    admission_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(admission_digest) = 64
            AND admission_digest NOT GLOB '*[^0-9a-f]*'
        ),
    admission_json TEXT NOT NULL CHECK(length(admission_json) > 2)
);

CREATE INDEX idx_dispatch_inbox_v1_workspace_environment
ON dispatch_inbox_v1(workspace_id, environment);

CREATE INDEX idx_dispatch_inbox_v1_execution
ON dispatch_inbox_v1(execution_id);

CREATE TRIGGER trg_dispatch_inbox_v1_outbox_binding_insert
BEFORE INSERT ON dispatch_inbox_v1
WHEN NOT EXISTS (
    SELECT 1
    FROM dispatch_outbox_v1 AS outbox
    WHERE outbox.outbox_id = NEW.outbox_id
      AND outbox.entry_digest = NEW.outbox_entry_digest
      AND outbox.execution_id = NEW.execution_id
      AND outbox.workspace_id = NEW.workspace_id
      AND outbox.environment = NEW.environment
      AND outbox.execution_capsule_digest = NEW.execution_capsule_digest
      AND outbox.runner_class = NEW.runner_class
)
BEGIN
    SELECT RAISE(ABORT, 'dispatch inbox outbox binding is invalid');
END;

CREATE TRIGGER trg_dispatch_inbox_v1_immutable_update
BEFORE UPDATE ON dispatch_inbox_v1
BEGIN
    SELECT RAISE(ABORT, 'dispatch inbox admission is immutable');
END;

CREATE TRIGGER trg_dispatch_inbox_v1_immutable_delete
BEFORE DELETE ON dispatch_inbox_v1
BEGIN
    SELECT RAISE(ABORT, 'dispatch inbox admission is immutable');
END;
