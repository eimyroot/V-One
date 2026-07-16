ALTER TABLE executions
ADD COLUMN fence INTEGER NOT NULL DEFAULT 1 CHECK(fence >= 1);

ALTER TABLE executions
ADD COLUMN lease_expires_at TEXT;

UPDATE executions
SET lease_expires_at = started_at
WHERE status = 'RUNNING';

CREATE INDEX idx_executions_recovery
ON executions(status, lease_expires_at);
