# VOODOO One — Database Statement Catalog

## Purpose and ownership

`voodoo_product/statements.py` is the sole owner of SQL executed by `ProductService`. Every
application operation references a named, immutable `DatabaseStatement`; the service owns parameters
and business flow, while the catalog owns dialect text and read/write classification. Migration,
schema-validation and adapter-internal SQL remain owned by `voodoo_product/db.py` and migration files.

The catalog is explicit rather than generated. Names are stable lowercase identifiers, startup
rejects duplicate names, and tests lock the current inventory at 46 statements and all 51 service
execution sites. Dynamic SQL construction in the service is prohibited. Optional query behavior must
select between complete catalog entries, as the pending/all approval views do.

## Backend selection and safety

`DatabaseStatement.for_backend()` returns SQL only for an explicitly defined dialect. The current
release defines SQLite SQL and deliberately leaves every PostgreSQL definition absent. An unavailable
or unknown backend raises `DatabaseStatementError`; it never falls back to another dialect, rewrites
placeholder syntax or logs statement text.

Raw SQL remains accepted by the low-level connection protocol only for adapter internals, migrations,
controlled administration and isolated tests. New application SQL belongs in the catalog and must be
referenced from the service by its constant.

## Change procedure

For each new or changed application operation:

1. Add or update one immutable catalog entry with an unambiguous read/write mode.
2. Preserve parameter ordering and result-column semantics for every supported dialect.
3. Reference the entry from the service without concatenation or interpolation.
4. Add behavior coverage and update the catalog inventory test.
5. Run lint, compile, all tests, readiness and dependency-audit gates.

Changing a statement name or result shape is an internal compatibility change and requires analysis
of all callers. Changing schema still requires an append-only migration; editing a catalog entry does
not replace migration governance.

## PostgreSQL release gate

PostgreSQL stays unavailable until every catalog entry has reviewed PostgreSQL SQL and matching
integration coverage against the pinned server version. The adapter must also implement the migration,
pooling, TLS, error-normalization and retry contracts in `PERSISTENCE_BOUNDARY.md`.

The initial PostgreSQL adapter must preserve globally serialized writes—for example with a fixed,
transaction-scoped advisory lock—because audit and receipt chain heads are read then appended inside
the same transaction. Approval transitions, idempotency and rate-limit counters rely on the same
serialization today. Any narrower locking model requires separate race tests, invariants and rollback
evidence before release.

Execution completion and recovery are separate classified writes. Completion uses the durable fence
as a compare-and-set predicate. Recovery selects the execution context and increments that fence in
the same globally serialized transaction that marks the request failed and appends evidence. A
backend dialect must preserve this affected-row/`RETURNING` contract; silently accepting a stale
completion is prohibited.

Receipt list, verification and head statements order exclusively by the database-assigned monotonic
`sequence`. Timestamp and random identifier ordering is prohibited because multiple receipts can
legitimately share a millisecond.
