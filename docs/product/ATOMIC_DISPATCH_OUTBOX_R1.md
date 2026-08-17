# Atomic Dispatch Outbox R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@3eb102c6156595f853df50c9d4ccdbbca27aa181`  
Phase: C1b — Transactional Outbox Persistence  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

C1b closes the crash window between authoritative ONE_TIME Grant consumption and durable dispatch intent persistence.

The required invariant is:

```text
BEGIN IMMEDIATE
    prove ExecutionGrant/v2 is still consumable
    create GrantConsumptionWitness/v1
    create exact DispatchOutboxEntry/v1
    append grant consumption
    append dispatch outbox intent
COMMIT
```

The forbidden state is:

```text
Grant consumed
+
Dispatch outbox intent missing
```

If the outbox append fails, the entire transaction rolls back and the Grant remains unconsumed for a valid retry.

## 2. Canonical chain

```text
ExecutionGrant/v2
        ↓
B4 live consume checks
        ↓
GrantConsumptionWitness/v1
        +
C1a DispatchOutboxEntry/v1
        ↓
ONE SQLite BEGIN IMMEDIATE transaction
        ├── append grant_consumptions_v1
        └── append dispatch_outbox_v1
        ↓
TRANSACTIONAL_OUTBOX_READY
```

C1b does not dispatch the entry. It makes one immutable dispatch intent durably inseparable from one authoritative Grant consumption.

## 3. Authority composition

`DurableDispatchOutboxService` wraps one existing `DurableGrantService` instance.

It does not accept independent clock, revocation, operational-safety or conformance authorities. The wrapped B4 service remains the sole authority for:

- exact stored Grant decoding;
- trusted time;
- TTL enforcement;
- emergency-stop enforcement;
- live revocation epoch;
- fresh B3 execution conformance;
- GrantConsumptionWitness construction semantics.

This prevents C1b from accidentally composing a different authority stack from B4.

## 4. Atomic consume-and-enqueue path

The Phase-C entrypoint is:

```text
consume_and_enqueue(jti)
```

Inside one released SQLite global-write transaction it:

1. rejects an already-consumed JTI;
2. loads and reconstructs the exact durable `ExecutionGrant/v2`;
3. obtains a trusted-clock witness;
4. rechecks TTL, emergency stop and live revocation;
5. performs fresh B3 conformance;
6. creates `GrantConsumptionWitness/v1`;
7. derives the exact C1a `DispatchOutboxEntry/v1` from that Grant + witness;
8. appends the consumption row;
9. appends the outbox row;
10. commits once.

No provider effect, network dispatch or Runner execution occurs inside or after this method.

## 5. Immutable outbox intent

Migration `0011_dispatch_outbox.sql` adds `dispatch_outbox_v1`.

The row is an immutable intent artifact, not mutable queue state. It has no `PENDING`, `SENT`, `RETRYING` or `DONE` status column.

It binds the exact C1a fields, including:

- outbox identity;
- consumption identity and witness digest;
- JTI and Grant identity/digest;
- execution/request/actor/workspace/environment;
- capability and capability-definition identity;
- AuthorizationSnapshot digest;
- target kind/digest and payload digest;
- `execution.run`;
- execution-binding and ExecutionCapsule digests;
- runner class;
- precondition enforcement class;
- `ONE_TIME` semantics;
- creation/consumption timestamp;
- outbox revision;
- content-addressed entry digest and canonical JSON.

Database uniqueness requires one outbox intent per consumption/JTI/Grant/execution. UPDATE and DELETE fail closed.

Later dispatch claims, attempts, acknowledgements, inbox/dedup and lease records must be separate durable artifacts so operational history is never rewritten in place.

## 6. Database binding

The insertion trigger requires the outbox row to resolve to the exact existing `grant_consumptions_v1` and `execution_grants_v2` records for all security-relevant scalar bindings available in those durable tables.

C1b application code additionally derives and serializes the complete C1a entry from the canonical stored Grant. Fields that are carried only inside the canonical Grant artifact are therefore not caller-selected.

A future consumer of the outbox must parse and revalidate `entry_json`; structural database presence alone is not dispatch permission.

## 7. Historical B4 consumption boundary

B4 predates transactional outbox persistence and exposes `DurableGrantService.consume()` as an authority-consumption operation.

A historical B4-only consumption is valid evidence that authority was consumed, but it is **not** evidence that transactional dispatch intent was created.

C1b therefore refuses to initialize when it observes:

```text
grant_consumptions_v1 row
+
no matching dispatch_outbox_v1 row
```

C1b does not backfill or synthesize an outbox entry for such history. Doing so would fabricate a transactional fact that never occurred.

Future Phase-C composition must use `consume_and_enqueue()` for dispatch-eligible work.

## 8. Concurrency

SQLite R1 continues to use:

```text
backend_name        = sqlite
write_serialization = global
transaction         = BEGIN IMMEDIATE
```

Two concurrent callers using the same JTI serialize. Exactly one can append the unique consumption + outbox pair. The loser observes the committed consumption and fails `GRANT_ALREADY_CONSUMED`.

The unique database constraints are an additional fail-closed defense.

## 9. Failure semantics

Representative failures are:

- `GRANT_NOT_FOUND`;
- `GRANT_ALREADY_CONSUMED`;
- all existing B4 TTL / emergency-stop / revocation / conformance denials;
- `OUTBOX_PERSISTENCE_CONFLICT`;
- C1b schema/index/trigger validation failure;
- historical orphan-consumption startup denial.

An outbox persistence failure after the in-transaction consumption insert propagates out of the transaction. SQLite rollback removes the consumption insert as well as any partial outbox work.

## 10. Schema version

C1b advances the released SQLite schema from version 10 to version 11 through immutable migration:

```text
0011_dispatch_outbox.sql
```

The release health/smoke and migration regression baselines must therefore require schema version 11.

PostgreSQL remains unreleased. C1b does not infer PostgreSQL transactional-outbox locking semantics from the SQLite implementation.

## 11. Non-goals

C1b does not add:

- a dispatcher;
- `DispatchEnvelope/v1`;
- delivery claims or retries;
- inbox/dedup;
- leases;
- ExecutionEpoch/fencing for the new authority chain;
- concrete RunnerIdentity;
- credentials;
- Handler execution;
- provider effects;
- ExecutionReceipt/v2;
- independent post-state verification;
- OperationProof;
- ProductService/ExecutionService runtime wiring;
- PostgreSQL support;
- release;
- deployment;
- production effects.

## 12. Milestone and next gate

After merge and complete exact-head verification, the precise milestone is:

```text
TRANSACTIONAL_OUTBOX_READY
```

It is not `BOUNDED_RUNTIME_READY`.

The next bounded slice is:

```text
C2 DispatchEnvelope/v1
```

C2 must derive its envelope only from an exact durable `DispatchOutboxEntry/v1` and must not widen target, payload, capsule, runner class or authority.

## 13. Acceptance evidence

C1b is review-ready only after the repository's complete exact-head `verify` job succeeds.

Tests must demonstrate at minimum:

- successful atomic consumption + outbox append;
- persisted outbox canonical round trip;
- exact consumption/outbox digest binding;
- forced outbox insert failure rolls back the consumption;
- valid retry after that rollback succeeds;
- two concurrent consumers produce exactly one consumption and one outbox intent;
- outbox UPDATE and DELETE fail closed;
- historical B4-only consumption is not retroactively dispatch eligible;
- unknown JTI fails closed;
- schema 11 fresh/legacy/concurrent/rollback migration behavior;
- no dispatcher, Runner or provider effect is wired.

CI success does not authorize merge, runtime adoption, release, deployment or external effects.
