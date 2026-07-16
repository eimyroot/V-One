# VOODOO One — Database Migration Contract

## Released backend

SQLite is the only released database backend. `VOODOO_DATABASE_BACKEND=postgresql` is reserved for a
future implementation and deliberately fails startup. The present service uses SQLite placeholders,
row types, exception classes, transaction semantics and conflict syntax; replacing only the
connection driver would be unsafe.

## Ownership and ordering

Migration files live in `voodoo_product/migrations/sqlite` and use the immutable
`NNNN_description.sql` format. Versions start at `0001` and must remain contiguous. Application
startup takes an exclusive migration transaction, compares each applied filename and SHA-256 checksum
with `schema_migrations`, applies only the pending suffix, validates the resulting schema and commits
once.

An applied migration must never be edited, renamed, reordered or removed. A schema change is always a
new migration. Startup fails closed when history is missing or divergent, the database is newer than
the binary, a statement is incomplete, required schema objects are absent, or SQLite reports an
integrity failure.

## Control flow and failure modes

1. Load and checksum the complete migration set from the deployed artifact.
2. Acquire the SQLite exclusive migration transaction.
3. Reconcile `PRAGMA user_version` with the recorded migration history.
4. Validate the recorded history as an exact prefix of the deployed files.
5. Execute pending statements and record each version in the same transaction.
6. Validate tables, columns, indexes and `PRAGMA integrity_check`.
7. Commit once; any exception rolls back the complete startup attempt.

Concurrent instances serialize on the database lock. Operationally, upgrades still start one
instance first so a migration failure is isolated and observable.

## Legacy adoption

A database created by the pre-migration VOODOO release has no migration table and uses
`PRAGMA user_version=0`. The baseline migrations use idempotent DDL, preserve its rows, then record the
complete migration history. Post-migration structural validation rejects an incompatible or partial
legacy schema.

## Upgrade and rollback

Before upgrade, stop all writers and back up the main database, `-wal` and `-shm` files as one set.
Keep production effects disabled. Start one new instance, require health schema version `2`, verify
evidence integrity, and only then scale out.

There are no automated down migrations. If rollout must be reversed and the older binary is not
compatible with the forward schema, stop all processes and restore the complete pre-migration backup.
Never delete `schema_migrations`, rewrite checksums or decrement `PRAGMA user_version` to bypass the
gate.

## PostgreSQL release gate

PostgreSQL requires a dedicated adapter, dialect-neutral service boundaries, transactional migration
locking, connection-pool lifecycle management, retry classification, backup/restore procedures and
integration tests against the supported PostgreSQL version. Tenant isolation and high-availability
testing remain enterprise-release gates. Until those controls pass, PostgreSQL startup stays blocked.
