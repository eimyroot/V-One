CREATE TABLE external_identity_bindings (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL CHECK(provider = 'oidc'),
    issuer TEXT NOT NULL CHECK(length(issuer) BETWEEN 1 AND 2048),
    subject TEXT NOT NULL CHECK(length(subject) BETWEEN 1 AND 512),
    user_id TEXT NOT NULL REFERENCES users(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(provider, issuer, subject),
    UNIQUE(provider, issuer, user_id)
);

CREATE TABLE external_role_mappings (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL CHECK(provider = 'oidc'),
    issuer TEXT NOT NULL CHECK(length(issuer) BETWEEN 1 AND 2048),
    external_group TEXT NOT NULL CHECK(length(external_group) BETWEEN 1 AND 256),
    internal_role TEXT NOT NULL CHECK(
        internal_role IN (
            'viewer',
            'developer',
            'operator',
            'security_reviewer',
            'auditor',
            'administrator'
        )
    ),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(provider, issuer, external_group)
);

CREATE INDEX idx_external_identity_user
ON external_identity_bindings(user_id, provider, issuer);

CREATE INDEX idx_external_role_mapping_role
ON external_role_mappings(internal_role, provider, issuer);

CREATE TRIGGER trg_external_identity_binding_active_user
BEFORE INSERT ON external_identity_bindings
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM users WHERE id = NEW.user_id AND active = 1
)
BEGIN
    SELECT RAISE(ABORT, 'external identity requires an active user');
END;

CREATE TRIGGER trg_external_identity_binding_immutable_update
BEFORE UPDATE ON external_identity_bindings
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'external identity binding is immutable');
END;

CREATE TRIGGER trg_external_identity_binding_immutable_delete
BEFORE DELETE ON external_identity_bindings
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'external identity binding is immutable');
END;

CREATE TRIGGER trg_external_role_mapping_immutable_update
BEFORE UPDATE ON external_role_mappings
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'external role mapping is immutable');
END;

CREATE TRIGGER trg_external_role_mapping_immutable_delete
BEFORE DELETE ON external_role_mappings
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'external role mapping is immutable');
END;
