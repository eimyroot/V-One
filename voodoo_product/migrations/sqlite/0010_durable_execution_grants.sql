CREATE TABLE execution_grants_v2 (
    jti TEXT PRIMARY KEY,
    grant_id TEXT NOT NULL UNIQUE,
    execution_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL REFERENCES change_requests(id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    environment TEXT NOT NULL
        CHECK(environment IN ('local', 'development', 'staging', 'production')),
    authorization_snapshot_digest TEXT NOT NULL UNIQUE
        REFERENCES authorization_snapshots(snapshot_digest),
    execution_capsule_digest TEXT NOT NULL
        CHECK(
            length(execution_capsule_digest) = 64
            AND execution_capsule_digest NOT GLOB '*[^0-9a-f]*'
        ),
    grant_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(grant_digest) = 64
            AND grant_digest NOT GLOB '*[^0-9a-f]*'
        ),
    grant_json TEXT NOT NULL CHECK(length(grant_json) > 2),
    issuance_conformance_witness_digest TEXT NOT NULL
        CHECK(
            length(issuance_conformance_witness_digest) = 64
            AND issuance_conformance_witness_digest NOT GLOB '*[^0-9a-f]*'
        ),
    issuance_conformance_witness_json TEXT NOT NULL
        CHECK(length(issuance_conformance_witness_json) > 2),
    store_clock_witness_digest TEXT NOT NULL
        CHECK(
            length(store_clock_witness_digest) = 64
            AND store_clock_witness_digest NOT GLOB '*[^0-9a-f]*'
        ),
    store_clock_witness_json TEXT NOT NULL
        CHECK(length(store_clock_witness_json) > 2),
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revocation_epoch INTEGER NOT NULL CHECK(revocation_epoch >= 0),
    stored_at TEXT NOT NULL,
    store_revision TEXT NOT NULL CHECK(length(store_revision) > 0)
);

CREATE INDEX idx_execution_grants_v2_request
ON execution_grants_v2(request_id);

CREATE INDEX idx_execution_grants_v2_workspace_environment
ON execution_grants_v2(workspace_id, environment);

CREATE TRIGGER trg_execution_grants_v2_snapshot_binding_insert
BEFORE INSERT ON execution_grants_v2
WHEN NOT EXISTS (
    SELECT 1
    FROM authorization_snapshots snapshot
    WHERE snapshot.snapshot_digest = NEW.authorization_snapshot_digest
      AND snapshot.execution_id = NEW.execution_id
      AND snapshot.request_id = NEW.request_id
      AND snapshot.workspace_id = NEW.workspace_id
      AND snapshot.environment = NEW.environment
)
BEGIN
    SELECT RAISE(ABORT, 'execution grant snapshot binding is invalid');
END;

CREATE TRIGGER trg_execution_grants_v2_immutable_update
BEFORE UPDATE ON execution_grants_v2
BEGIN
    SELECT RAISE(ABORT, 'execution grant is immutable');
END;

CREATE TRIGGER trg_execution_grants_v2_immutable_delete
BEFORE DELETE ON execution_grants_v2
BEGIN
    SELECT RAISE(ABORT, 'execution grant is immutable');
END;

CREATE TABLE grant_consumptions_v1 (
    consumption_id TEXT PRIMARY KEY,
    jti TEXT NOT NULL UNIQUE REFERENCES execution_grants_v2(jti),
    grant_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(grant_digest) = 64
            AND grant_digest NOT GLOB '*[^0-9a-f]*'
        ),
    execution_id TEXT NOT NULL UNIQUE,
    authorization_snapshot_digest TEXT NOT NULL
        CHECK(
            length(authorization_snapshot_digest) = 64
            AND authorization_snapshot_digest NOT GLOB '*[^0-9a-f]*'
        ),
    execution_capsule_digest TEXT NOT NULL
        CHECK(
            length(execution_capsule_digest) = 64
            AND execution_capsule_digest NOT GLOB '*[^0-9a-f]*'
        ),
    runner_class TEXT NOT NULL CHECK(length(runner_class) > 0),
    conformance_witness_digest TEXT NOT NULL
        CHECK(
            length(conformance_witness_digest) = 64
            AND conformance_witness_digest NOT GLOB '*[^0-9a-f]*'
        ),
    conformance_witness_json TEXT NOT NULL
        CHECK(length(conformance_witness_json) > 2),
    clock_witness_digest TEXT NOT NULL
        CHECK(
            length(clock_witness_digest) = 64
            AND clock_witness_digest NOT GLOB '*[^0-9a-f]*'
        ),
    clock_witness_json TEXT NOT NULL CHECK(length(clock_witness_json) > 2),
    live_revocation_epoch INTEGER NOT NULL CHECK(live_revocation_epoch >= 0),
    consumed_at TEXT NOT NULL,
    serialization_contract TEXT NOT NULL
        CHECK(serialization_contract = 'sqlite-begin-immediate/v1'),
    authority_revision TEXT NOT NULL CHECK(length(authority_revision) > 0),
    consumption_digest TEXT NOT NULL UNIQUE
        CHECK(
            length(consumption_digest) = 64
            AND consumption_digest NOT GLOB '*[^0-9a-f]*'
        ),
    consumption_json TEXT NOT NULL CHECK(length(consumption_json) > 2)
);

CREATE INDEX idx_grant_consumptions_v1_execution
ON grant_consumptions_v1(execution_id);

CREATE TRIGGER trg_grant_consumptions_v1_grant_binding_insert
BEFORE INSERT ON grant_consumptions_v1
WHEN NOT EXISTS (
    SELECT 1
    FROM execution_grants_v2 grant_row
    WHERE grant_row.jti = NEW.jti
      AND grant_row.grant_digest = NEW.grant_digest
      AND grant_row.execution_id = NEW.execution_id
      AND grant_row.authorization_snapshot_digest = NEW.authorization_snapshot_digest
      AND grant_row.execution_capsule_digest = NEW.execution_capsule_digest
)
BEGIN
    SELECT RAISE(ABORT, 'grant consumption binding is invalid');
END;

CREATE TRIGGER trg_grant_consumptions_v1_immutable_update
BEFORE UPDATE ON grant_consumptions_v1
BEGIN
    SELECT RAISE(ABORT, 'grant consumption is immutable');
END;

CREATE TRIGGER trg_grant_consumptions_v1_immutable_delete
BEFORE DELETE ON grant_consumptions_v1
BEGIN
    SELECT RAISE(ABORT, 'grant consumption is immutable');
END;
