# VOODOO One — Persistence Boundary

## Current release contract

`ProductService` depends on the protocols and normalized exceptions in
`voodoo_product/persistence.py`. It does not import `sqlite3`, depend on SQLite row classes or catch
backend-specific integrity errors. The configured adapter owns connection creation, transaction
boundaries, error normalization, schema initialization and schema-version reporting.

Application database calls use the immutable, backend-owned statement catalog in
`voodoo_product/statements.py`. SQLite remains the only released dialect in that catalog. PostgreSQL
SQL is intentionally absent, so attempting to resolve any application statement for PostgreSQL fails
closed instead of executing SQLite syntax against a different driver. This boundary must not be
represented as PostgreSQL support.

## Connection ownership

`connect()` returns a context-managed connection for bounded reads and explicitly managed writes.
Leaving the context commits any successful work and always closes the connection. An exception rolls
back pending work and then closes the connection. Reusing a closed connection fails with a normalized
`DatabaseOperationError`.

`transaction()` acquires the adapter's write transaction, commits once after successful completion,
and rolls back on every exception. The SQLite adapter retains `BEGIN IMMEDIATE`, WAL mode, full
synchronous writes, foreign-key enforcement and a bounded busy timeout. Initial WAL activation uses a
bounded retry for the SQLite-specific concurrent-start lock condition.

Execution idempotency lookup and creation run inside that same serialized write transaction. The
idempotency binding is evaluated before request-state and emergency-stop checks, so a retry returns
the already-bound execution even when the original request has moved from `APPROVED` to `RUNNING` or
`COMPLETED`. A key bound to another request still fails closed. This ordering is part of the adapter
contract and is covered by a deterministic concurrent regression test.

Receipt order is owned by the database `sequence`, never by wall-clock timestamps or random IDs.
Sequence assignment, receipt insertion and chain-head selection remain inside the globally serialized
transaction. Verification requires contiguous sequence values as well as matching previous and
computed hashes. Migration v3 reconstructs earlier ordering from the stored hash links and fails the
whole migration when the history is disconnected or branched.

Each adapter declares its write-serialization contract. SQLite currently declares `global`: every
write transaction is serialized across the database. A future adapter must preserve this behavior
until separate concurrency proofs exist for audit-chain heads, receipt-chain heads, approval state,
execution idempotency and authentication rate limits. PostgreSQL can satisfy the initial contract with
a transaction-scoped global advisory lock; weakening it is a separate reviewed change.

## Error contract

Adapters translate backend exceptions into:

- `DatabaseIntegrityError` for constraint violations,
- `DatabaseOperationError` for other connection or statement failures,
- `DatabaseStatementError` when a named statement is invalid or unavailable for a backend,
- `DatabaseMigrationError` for migration and schema failures,
- `DatabaseBackendError` for unsupported or unsafe backend selection.

Messages crossing the adapter boundary are generic and do not include SQL text, table names,
credentials, connection strings or driver diagnostics. The original exception remains chained for
controlled internal debugging; it must not be returned by the public API or emitted to normal logs.

## PostgreSQL gate

A PostgreSQL release requires a PostgreSQL implementation of this contract, a complete reviewed SQL
definition for every catalog statement, a separate migration set, globally serialized writes,
bounded pooling, TLS and credential configuration, classified retry behavior, and integration tests
against the supported server version. Until every gate passes, selecting PostgreSQL continues to
abort startup.
