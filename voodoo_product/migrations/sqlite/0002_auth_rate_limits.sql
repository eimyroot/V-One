CREATE TABLE IF NOT EXISTS auth_rate_limits (
    scope TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    failure_count INTEGER NOT NULL CHECK(failure_count >= 0),
    window_started_at INTEGER NOT NULL,
    blocked_until INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY(scope, key_hash)
);

CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_updated
ON auth_rate_limits(updated_at);
