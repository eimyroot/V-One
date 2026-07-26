CREATE TABLE active_sessions (
    session_reference TEXT PRIMARY KEY CHECK(length(session_reference) = 64),
    user_id TEXT NOT NULL REFERENCES users(id),
    issued_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    CHECK(expires_at > issued_at)
);

CREATE INDEX idx_active_sessions_user_expiry
ON active_sessions(user_id, expires_at);

CREATE TRIGGER trg_active_sessions_immutable
BEFORE UPDATE ON active_sessions
BEGIN
    SELECT RAISE(ABORT, 'active session is immutable');
END;
