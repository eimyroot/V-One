CREATE TABLE execution_leases_v1 (
    lease_id TEXT PRIMARY KEY
        CHECK(length(lease_id) = 64 AND lease_id NOT GLOB '*[^0-9a-f]*'),
    admission_id TEXT NOT NULL
        REFERENCES dispatch_inbox_v1(admission_id),
    dispatch_id TEXT NOT NULL
        CHECK(length(dispatch_id) = 64 AND dispatch_id NOT GLOB '*[^0-9a-f]*'),
    admission_digest TEXT NOT NULL
        CHECK(length(admission_digest) = 64 AND admission_digest NOT GLOB '*[^0-9a-f]*'),
    execution_id TEXT NOT NULL CHECK(length(execution_id) > 0),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    environment TEXT NOT NULL
        CHECK(environment IN ('local', 'development', 'staging', 'production')),
    execution_capsule_digest TEXT NOT NULL
        CHECK(
            length(execution_capsule_digest) = 64
            AND execution_capsule_digest NOT GLOB '*[^0-9a-f]*'
        ),
    runner_class TEXT NOT NULL CHECK(length(runner_class) > 0),
    execution_epoch INTEGER NOT NULL CHECK(execution_epoch >= 1),
    acquired_at TEXT NOT NULL CHECK(length(acquired_at) > 0),
    expires_at TEXT NOT NULL CHECK(length(expires_at) > 0),
    clock_witness_digest TEXT NOT NULL
        CHECK(
            length(clock_witness_digest) = 64
            AND clock_witness_digest NOT GLOB '*[^0-9a-f]*'
        ),
    clock_witness_json TEXT NOT NULL CHECK(length(clock_witness_json) > 2),
    lease_revision TEXT NOT NULL CHECK(length(lease_revision) > 0),
    lease_digest TEXT NOT NULL UNIQUE
        CHECK(length(lease_digest) = 64 AND lease_digest NOT GLOB '*[^0-9a-f]*'),
    lease_json TEXT NOT NULL CHECK(length(lease_json) > 2),
    UNIQUE(admission_id, execution_epoch)
);

CREATE INDEX idx_execution_leases_v1_admission_epoch
ON execution_leases_v1(admission_id, execution_epoch);

CREATE INDEX idx_execution_leases_v1_execution
ON execution_leases_v1(execution_id);

CREATE TABLE execution_epoch_state_v1 (
    admission_id TEXT PRIMARY KEY
        REFERENCES dispatch_inbox_v1(admission_id),
    admission_digest TEXT NOT NULL
        CHECK(length(admission_digest) = 64 AND admission_digest NOT GLOB '*[^0-9a-f]*'),
    execution_id TEXT NOT NULL CHECK(length(execution_id) > 0),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    environment TEXT NOT NULL
        CHECK(environment IN ('local', 'development', 'staging', 'production')),
    execution_capsule_digest TEXT NOT NULL
        CHECK(
            length(execution_capsule_digest) = 64
            AND execution_capsule_digest NOT GLOB '*[^0-9a-f]*'
        ),
    runner_class TEXT NOT NULL CHECK(length(runner_class) > 0),
    current_epoch INTEGER NOT NULL CHECK(current_epoch >= 1),
    current_lease_id TEXT NOT NULL UNIQUE
        REFERENCES execution_leases_v1(lease_id),
    current_lease_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(current_lease_digest) = 64
            AND current_lease_digest NOT GLOB '*[^0-9a-f]*'
        ),
    current_lease_acquired_at TEXT NOT NULL CHECK(length(current_lease_acquired_at) > 0),
    current_lease_expires_at TEXT NOT NULL CHECK(length(current_lease_expires_at) > 0),
    status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'COMPLETED')),
    completion_digest TEXT
        CHECK(
            completion_digest IS NULL
            OR (
                length(completion_digest) = 64
                AND completion_digest NOT GLOB '*[^0-9a-f]*'
            )
        ),
    completed_at TEXT,
    completion_clock_witness_digest TEXT
        CHECK(
            completion_clock_witness_digest IS NULL
            OR (
                length(completion_clock_witness_digest) = 64
                AND completion_clock_witness_digest NOT GLOB '*[^0-9a-f]*'
            )
        ),
    completion_clock_witness_json TEXT,
    authority_revision TEXT NOT NULL CHECK(length(authority_revision) > 0),
    updated_at TEXT NOT NULL CHECK(length(updated_at) > 0),
    CHECK(
        (status = 'ACTIVE'
            AND completion_digest IS NULL
            AND completed_at IS NULL
            AND completion_clock_witness_digest IS NULL
            AND completion_clock_witness_json IS NULL)
        OR
        (status = 'COMPLETED'
            AND completion_digest IS NOT NULL
            AND completed_at IS NOT NULL
            AND completion_clock_witness_digest IS NOT NULL
            AND completion_clock_witness_json IS NOT NULL)
    )
);

CREATE INDEX idx_execution_epoch_state_v1_execution
ON execution_epoch_state_v1(execution_id);

CREATE INDEX idx_execution_epoch_state_v1_status_expiry
ON execution_epoch_state_v1(status, current_lease_expires_at);

CREATE TRIGGER trg_execution_leases_v1_admission_binding_insert
BEFORE INSERT ON execution_leases_v1
WHEN NOT EXISTS (
    SELECT 1
    FROM dispatch_inbox_v1 AS inbox
    WHERE inbox.admission_id = NEW.admission_id
      AND inbox.dispatch_id = NEW.dispatch_id
      AND inbox.admission_digest = NEW.admission_digest
      AND inbox.execution_id = NEW.execution_id
      AND inbox.workspace_id = NEW.workspace_id
      AND inbox.environment = NEW.environment
      AND inbox.execution_capsule_digest = NEW.execution_capsule_digest
      AND inbox.runner_class = NEW.runner_class
)
BEGIN
    SELECT RAISE(ABORT, 'execution lease admission binding is invalid');
END;

CREATE TRIGGER trg_execution_leases_v1_immutable_update
BEFORE UPDATE ON execution_leases_v1
BEGIN
    SELECT RAISE(ABORT, 'execution lease is immutable');
END;

CREATE TRIGGER trg_execution_leases_v1_immutable_delete
BEFORE DELETE ON execution_leases_v1
BEGIN
    SELECT RAISE(ABORT, 'execution lease is immutable');
END;

CREATE TRIGGER trg_execution_epoch_state_v1_insert_guard
BEFORE INSERT ON execution_epoch_state_v1
WHEN NEW.current_epoch != 1
   OR NEW.status != 'ACTIVE'
   OR NOT EXISTS (
        SELECT 1
        FROM dispatch_inbox_v1 AS inbox
        WHERE inbox.admission_id = NEW.admission_id
          AND inbox.admission_digest = NEW.admission_digest
          AND inbox.execution_id = NEW.execution_id
          AND inbox.workspace_id = NEW.workspace_id
          AND inbox.environment = NEW.environment
          AND inbox.execution_capsule_digest = NEW.execution_capsule_digest
          AND inbox.runner_class = NEW.runner_class
   )
   OR NOT EXISTS (
        SELECT 1
        FROM execution_leases_v1 AS lease
        WHERE lease.lease_id = NEW.current_lease_id
          AND lease.lease_digest = NEW.current_lease_digest
          AND lease.admission_id = NEW.admission_id
          AND lease.execution_epoch = NEW.current_epoch
          AND lease.acquired_at = NEW.current_lease_acquired_at
          AND lease.expires_at = NEW.current_lease_expires_at
   )
BEGIN
    SELECT RAISE(ABORT, 'execution epoch initial state is invalid');
END;

CREATE TRIGGER trg_execution_epoch_state_v1_update_guard
BEFORE UPDATE ON execution_epoch_state_v1
WHEN OLD.status != 'ACTIVE'
   OR NEW.admission_id != OLD.admission_id
   OR NEW.admission_digest != OLD.admission_digest
   OR NEW.execution_id != OLD.execution_id
   OR NEW.workspace_id != OLD.workspace_id
   OR NEW.environment != OLD.environment
   OR NEW.execution_capsule_digest != OLD.execution_capsule_digest
   OR NEW.runner_class != OLD.runner_class
   OR NEW.authority_revision != OLD.authority_revision
   OR NOT (
        (
            NEW.status = 'ACTIVE'
            AND NEW.current_epoch = OLD.current_epoch + 1
            AND NEW.current_lease_id != OLD.current_lease_id
            AND NEW.current_lease_digest != OLD.current_lease_digest
            AND NEW.updated_at >= OLD.current_lease_expires_at
            AND NEW.completion_digest IS NULL
            AND NEW.completed_at IS NULL
            AND NEW.completion_clock_witness_digest IS NULL
            AND NEW.completion_clock_witness_json IS NULL
            AND EXISTS (
                SELECT 1
                FROM execution_leases_v1 AS lease
                WHERE lease.lease_id = NEW.current_lease_id
                  AND lease.lease_digest = NEW.current_lease_digest
                  AND lease.admission_id = NEW.admission_id
                  AND lease.execution_epoch = NEW.current_epoch
                  AND lease.acquired_at = NEW.current_lease_acquired_at
                  AND lease.expires_at = NEW.current_lease_expires_at
            )
        )
        OR
        (
            NEW.status = 'COMPLETED'
            AND NEW.current_epoch = OLD.current_epoch
            AND NEW.current_lease_id = OLD.current_lease_id
            AND NEW.current_lease_digest = OLD.current_lease_digest
            AND NEW.current_lease_acquired_at = OLD.current_lease_acquired_at
            AND NEW.current_lease_expires_at = OLD.current_lease_expires_at
            AND NEW.completion_digest IS NOT NULL
            AND NEW.completed_at IS NOT NULL
            AND NEW.completed_at >= OLD.current_lease_acquired_at
            AND NEW.completed_at < OLD.current_lease_expires_at
            AND NEW.completion_clock_witness_digest IS NOT NULL
            AND NEW.completion_clock_witness_json IS NOT NULL
        )
   )
BEGIN
    SELECT RAISE(ABORT, 'execution epoch state transition is invalid');
END;

CREATE TRIGGER trg_execution_epoch_state_v1_immutable_delete
BEFORE DELETE ON execution_epoch_state_v1
BEGIN
    SELECT RAISE(ABORT, 'execution epoch state cannot be deleted');
END;
