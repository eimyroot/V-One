CREATE TABLE external_identity_bindings (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL CHECK(provider = 'oidc'),
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL,
    disabled_at TEXT,
    CHECK(length(issuer) BETWEEN 1 AND 2048),
    CHECK(length(subject) BETWEEN 1 AND 512),
    CHECK(
        (active = 1 AND disabled_at IS NULL)
        OR (active = 0 AND disabled_at IS NOT NULL)
    ),
    UNIQUE(provider, issuer, subject),
    UNIQUE(provider, issuer, user_id)
);

CREATE INDEX idx_external_identity_bindings_user
ON external_identity_bindings(user_id, active);

CREATE TRIGGER trg_external_identity_binding_identity_immutable
BEFORE UPDATE OF provider, issuer, subject, user_id ON external_identity_bindings
BEGIN
    SELECT RAISE(ABORT, 'external identity binding is immutable');
END;

CREATE TRIGGER trg_external_identity_binding_no_reactivation
BEFORE UPDATE OF active ON external_identity_bindings
WHEN OLD.active = 0 AND NEW.active = 1
BEGIN
    SELECT RAISE(ABORT, 'external identity binding cannot be reactivated');
END;

CREATE TRIGGER trg_external_identity_binding_no_delete
BEFORE DELETE ON external_identity_bindings
BEGIN
    SELECT RAISE(ABORT, 'external identity binding cannot be deleted');
END;
