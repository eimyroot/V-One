# VOODOO One — Persistence Boundary

## Current release contract

`ProductService` depends on the protocols and normalized exceptions in
`voodoo_product/persistence.py`. It does not import `sqlite3`, depend on SQLite row classes or catch
backend-specific integrity errors. The configured adapter owns connection creation, transaction
boundaries, error normalization, schema initialization and schema-version reporting.

SQLite remains the only released adapter. The application queries still use SQLite parameter markers
and SQLite-compatible conflict syntax. This boundary is therefore backend-isolated but not yet
dialect-neutral, and it must not be represented as PostgreSQL support.

## Connection ownership

`connect()` returns a context-managed connection for bounded reads and explicitly managed writes.
Leaving the context commits any successful work and always closes the connection. An exception rolls
back pending work and then closes the connection. Reusing a closed connection fails with a normalized
`DatabaseOperationError`.

`transaction()` acquires the adapter's write transaction, commits once after successful completion,
and rolls back on every exception. The SQLite adapter retains `BEGIN IMMEDIATE`, WAL mode, full
synchronous writes, foreign-key enforcement and a bounded busy timeout. Initial WAL activation uses a
bounded retry for the SQLite-specific concurrent-start lock condition.

## Error contract

Adapters translate backend exceptions into:

- `DatabaseIntegrityError` for constraint violations,
- `DatabaseOperationError` for other connection or statement failures,
- `DatabaseMigrationError` for migration and schema failures,
- `DatabaseBackendError` for unsupported or unsafe backend selection.

Messages crossing the adapter boundary are generic and do not include SQL text, table names,
credentials, connection strings or driver diagnostics. The original exception remains chained for
controlled internal debugging; it must not be returned by the public API or emitted to normal logs.

## PostgreSQL gate

A PostgreSQL release requires a PostgreSQL implementation of this contract, a separate migration set,
dialect-neutral statements or repositories, bounded pooling, TLS and credential configuration,
classified retry behavior, and integration tests against the supported server version. Until every
gate passes, selecting PostgreSQL continues to abort startup.
