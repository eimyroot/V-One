CREATE TABLE dispatch_outbox_v1 (
    outbox_id TEXT PRIMARY KEY,
    consumption_id TEXT NOT NULL UNIQUE
        REFERENCES grant_consumptions_v1(consumption_id),
    consumption_witness_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(consumption_witness_digest) = 64
            AND consumption_witness_digest NOT GLOB '*[^0-9a-f]*'
        ),
    jti TEXT NOT NULL UNIQUE REFERENCES execution_grants_v2(jti),
    grant_id TEXT NOT NULL UNIQUE,
    grant_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(grant_digest) = 64
            AND grant_digest NOT GLOB '*[^0-9a-f]*'
        ),
    execution_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL REFERENCES change_requests(id),
    actor_id TEXT NOT NULL REFERENCES users(id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    environment TEXT NOT NULL
        CHECK(environment IN ('local', 'development', 'staging', 'production')),
    capability TEXT NOT NULL CHECK(length(capability) > 0),
    capability_definition_identity TEXT NOT NULL
        CHECK(
            length(capability_definition_identity) = 64
            AND capability_definition_identity NOT GLOB '*[^0-9a-f]*'
        ),
    authorization_snapshot_digest TEXT NOT NULL
        REFERENCES authorization_snapshots(snapshot_digest),
    target_kind TEXT NOT NULL CHECK(length(target_kind) > 0),
    target_digest TEXT NOT NULL
        CHECK(
            length(target_digest) = 64
            AND target_digest NOT GLOB '*[^0-9a-f]*'
        ),
    payload_digest TEXT NOT NULL
        CHECK(
            length(payload_digest) = 64
            AND payload_digest NOT GLOB '*[^0-9a-f]*'
        ),
    required_permission TEXT NOT NULL CHECK(required_permission = 'execution.run'),
    execution_binding_digest TEXT NOT NULL
        CHECK(
            length(execution_binding_digest) = 64
            AND execution_binding_digest NOT GLOB '*[^0-9a-f]*'
        ),
    execution_capsule_digest TEXT NOT NULL
        CHECK(
            length(execution_capsule_digest) = 64
            AND execution_capsule_digest NOT GLOB '*[^0-9a-f]*'
        ),
    runner_class TEXT NOT NULL CHECK(length(runner_class) > 0),
    precondition_enforcement_class TEXT NOT NULL
        CHECK(
            precondition_enforcement_class IN (
                'READ_THEN_COMPARE',
                'ATOMIC_PROVIDER_CONDITION'
            )
        ),
    use_semantics TEXT NOT NULL CHECK(use_semantics = 'ONE_TIME'),
    created_at TEXT NOT NULL,
    outbox_revision TEXT NOT NULL CHECK(length(outbox_revision) > 0),
    entry_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(entry_digest) = 64
            AND entry_digest NOT GLOB '*[^0-9a-f]*'
        ),
    entry_json TEXT NOT NULL CHECK(length(entry_json) > 2)
);

CREATE INDEX idx_dispatch_outbox_v1_workspace_environment
ON dispatch_outbox_v1(workspace_id, environment);

CREATE INDEX idx_dispatch_outbox_v1_created_at
ON dispatch_outbox_v1(created_at);

CREATE TRIGGER trg_dispatch_outbox_v1_binding_insert
BEFORE INSERT ON dispatch_outbox_v1
WHEN NOT EXISTS (
    SELECT 1
    FROM grant_consumptions_v1 AS consumption
    JOIN execution_grants_v2 AS grant_row
      ON grant_row.jti = consumption.jti
    WHERE consumption.consumption_id = NEW.consumption_id
      AND consumption.consumption_digest = NEW.consumption_witness_digest
      AND consumption.jti = NEW.jti
      AND consumption.grant_digest = NEW.grant_digest
      AND consumption.execution_id = NEW.execution_id
      AND consumption.authorization_snapshot_digest = NEW.authorization_snapshot_digest
      AND consumption.execution_capsule_digest = NEW.execution_capsule_digest
      AND consumption.runner_class = NEW.runner_class
      AND consumption.consumed_at = NEW.created_at
      AND grant_row.jti = NEW.jti
      AND grant_row.grant_id = NEW.grant_id
      AND grant_row.grant_digest = NEW.grant_digest
      AND grant_row.execution_id = NEW.execution_id
      AND grant_row.request_id = NEW.request_id
      AND grant_row.workspace_id = NEW.workspace_id
      AND grant_row.environment = NEW.environment
      AND grant_row.authorization_snapshot_digest = NEW.authorization_snapshot_digest
      AND grant_row.execution_capsule_digest = NEW.execution_capsule_digest
)
BEGIN
    SELECT RAISE(ABORT, 'dispatch outbox binding is invalid');
END;

CREATE TRIGGER trg_dispatch_outbox_v1_immutable_update
BEFORE UPDATE ON dispatch_outbox_v1
BEGIN
    SELECT RAISE(ABORT, 'dispatch outbox intent is immutable');
END;

CREATE TRIGGER trg_dispatch_outbox_v1_immutable_delete
BEFORE DELETE ON dispatch_outbox_v1
BEGIN
    SELECT RAISE(ABORT, 'dispatch outbox intent is immutable');
END;
