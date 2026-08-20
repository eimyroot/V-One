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
6. Validate tables, columns, indexes, required triggers and `PRAGMA integrity_check`.
7. Commit once; any exception rolls back the complete startup attempt.

Concurrent instances serialize on the database lock. Operationally, upgrades still start one
instance first so a migration failure is isolated and observable.

## Legacy adoption

A database created by the pre-migration VOODOO release has no migration table and uses
`PRAGMA user_version=0`. The baseline migrations use idempotent DDL, preserve its rows, then record the
complete migration history. Post-migration structural validation rejects an incompatible or partial
legacy schema.

## Upgrade and rollback

Before upgrade, activate emergency stop and verify both evidence chains, then stop all writers and
back up the main database, `-wal` and `-shm` files as one set. Keep production effects disabled. Start
one new instance, require health schema version `14`, verify evidence integrity again, and only then
scale out.

Migration `0003_receipt_sequence.sql` replaces timestamp/random-ID receipt ordering with a database
sequence. It reconstructs existing order from the recorded `previous_hash → receipt_hash` links in
the same exclusive migration transaction. A missing root, disconnected history, or branch prevents
the guard row from satisfying its constraint and rolls back the complete migration.

Migration `0004_execution_leases.sql` adds the legacy execution fence, lease expiry and recovery
index used by the pre-Phase-C `ExecutionService`. Existing `RUNNING` rows receive their original
`started_at` as an already-expired lease so they can be reviewed and explicitly recovered after
emergency stop. Existing terminal rows retain a null lease and fence value `1`. These legacy fields
are not the proof-carrying C4 ExecutionEpoch authority introduced later by migration `0013`.

Migration `0005_workspace_environment_boundary.sql` makes the workspace environment authoritative.
Database triggers reject new or retargeted change requests whose environment differs from their
workspace, prevent environment reclassification after governance begins, and reject execution rows
for any historical mismatch. Existing historical rows are preserved rather than silently rewritten;
the service blocks their submit, review and execution paths.

Migration `0006_external_identity_bindings.sql` adds immutable, non-reactivatable external identity
bindings without enabling the unreleased OIDC runtime.

Migration `0007_active_sessions.sql` adds the persistent local-session allowlist. It stores only a
purpose-derived HMAC reference, user ID and bounded timestamps. Existing v2 tokens have no matching
row and therefore fail closed until the operator signs in again. Session rows are immutable and
explicit revocation deletes only the selected active row while the audit chain preserves evidence.

Migration `0008_immutable_review_binding.sql` binds submitted change-request review content and new
approval evidence to the same deterministic SHA-256 identity. It prevents review-relevant request
content from changing after submission, requires new approval rows to carry the submitted review
digest, and makes approval evidence immutable. Existing historical submitted or terminal rows are
preserved without inventing a retroactive review-content digest.

Migration `0009_authorization_snapshots.sql` adds append-only persistence for prevalidated immutable
authorization snapshots. Rows are bound to an `APPROVED` change request, its exact workspace,
environment and review-content digest. Unique execution, idempotency and snapshot identities prevent
ambiguous reuse; database triggers reject snapshot updates and deletes. This migration does not make
the snapshot store an authorization authority and does not compose it into execution or production
runtime paths.

Migration `0010_durable_execution_grants.sql` adds append-only persistence for authoritative
`ExecutionGrant/v2` artifacts and their ONE_TIME consumption witnesses. Grant rows bind one unique
JTI, Grant ID, execution ID, AuthorizationSnapshot digest and ExecutionCapsule digest plus canonical
Grant/conformance/clock evidence. A database trigger requires the Grant's snapshot, execution,
request, workspace and environment to match one persisted AuthorizationSnapshot. Consumption rows
bind one unique JTI/grant/execution to fresh conformance, trusted-clock and live-revocation evidence.
Both tables reject UPDATE and DELETE. The application consumes grants only inside the released
SQLite `BEGIN IMMEDIATE` global-write serialization boundary; PostgreSQL locking semantics remain
unreleased.

Migration `0011_dispatch_outbox.sql` adds immutable `dispatch_outbox_v1` intents for the Phase-C
transactional outbox. Each row is uniquely bound to one existing Grant consumption, JTI, Grant and
execution and retains the exact C1a dispatch projection and canonical entry artifact. A database
binding trigger verifies the durable Grant/consumption relations available as scalar columns; UPDATE
and DELETE fail closed. The Phase-C application path appends the Grant consumption and exact outbox
intent in the same SQLite `BEGIN IMMEDIATE` transaction. If the outbox append fails, the consumption
rolls back as part of the same transaction. The migration does not synthesize outbox records for
historical B4-only consumptions: such history is valid authority-consumption evidence but is not
retroactively dispatch eligible. Delivery state, attempts and acknowledgements remain separate future
records; migration `0011` does not add a dispatcher or provider effect.

Migration `0012_dispatch_inbox.sql` adds append-only `dispatch_inbox_v1` admissions for Phase-C C3b.
Each row binds one unique logical `dispatch_id` to one exact existing `dispatch_outbox_v1` row, its
entry digest, execution identity, workspace/environment, ExecutionCapsule digest and runner class.
The service resolves and reconstructs the canonical durable outbox before admission; a structurally
valid caller envelope is not treated as authority proof. SQLite `BEGIN IMMEDIATE` serialization makes
the first admission durable before a concurrent redelivery can classify itself. Exact redelivery
returns `DUPLICATE` without a second row; conflicting content for the already-admitted logical dispatch
fails closed. UPDATE and DELETE are forbidden.

Migration `0013_execution_epoch_leases.sql` adds the Phase-C C4b durable execution-attempt authority.
`execution_leases_v1` is immutable history keyed by deterministic `ExecutionLease/v1` identity and
binds every epoch to the exact durable C3 admission, execution/workspace/environment, capsule, runner
class and trusted-clock acquire/expiry evidence. `execution_epoch_state_v1` is the single mutable
current-head row for that admission. Database triggers require the first epoch to be `1`, allow only
`N → N+1` active reacquisition after the recorded prior expiry, and allow only the current epoch to
transition from `ACTIVE` to `COMPLETED` before its recorded expiry. Lease rows cannot be updated or
deleted and epoch-state rows cannot be deleted. The application additionally constructs fresh
`ClockWitness/v1` evidence inside the SQLite `BEGIN IMMEDIATE` serialization boundary, so concurrent
reacquisition cannot allocate two successors and a superseded lease cannot record durable completion.
This migration still does not introduce a concrete RunnerIdentity, credentials, handler invocation or
provider mutation; those remain later execution-fabric gates.

Migration `0014_workspace_memberships.sql` adds the current user↔workspace scope boundary used by the
canonical database-backed permission authority. Membership rows bind an existing user to an existing
workspace as either `owner` or `member`; the schema validates the role vocabulary and indexes user
lookup. Fresh bootstrap creates the first administrator and bootstrap workspace owner atomically, and
new workspaces atomically add their creator as owner. Existing schema-13 databases are deliberately
**not** backfilled: migration does not infer historical memberships from global roles or past activity.
After upgrade, a legacy workspace therefore remains fail-closed for canonical workspace-scoped
permission decisions until an administrator explicitly records membership. Global product role still
defines which permissions a principal may exercise; membership defines the workspace in which those
permissions may be considered. This migration does not activate the separately PROPOSED Solo/Team/
Regulated organization policy model.

There are no automated down migrations. If rollout must be reversed and the older binary is not
compatible with the forward schema, stop all processes and restore the complete pre-migration backup.
Never delete `schema_migrations`, rewrite checksums or decrement `PRAGMA user_version` to bypass the
gate.

## PostgreSQL release gate

PostgreSQL requires a dedicated adapter, dialect-neutral service boundaries, transactional migration
locking, connection-pool lifecycle management, retry classification, backup/restore procedures and
integration tests against the supported PostgreSQL version. Tenant isolation and high-availability
testing remain enterprise-release gates. Until those controls pass, PostgreSQL startup stays blocked.

The backend-independent connection and error contract is documented in
`docs/product/PERSISTENCE_BOUNDARY.md`. It isolates the current SQLite adapter but deliberately does
not claim released PostgreSQL support. Application SQL ownership and the per-dialect fail-closed gate
are documented in `docs/product/STATEMENT_CATALOG.md`.
