# Durable Dispatch Inbox + Dedup R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@ffd418885883f017bb5e4ef26f9eb0c90ba03f6b`  
Phase: C3b — Durable Dispatch  

## 1. Purpose

C3b closes the durable first-admission and deduplication boundary after the C3a
`DispatchInboxAdmission/v1` contract.

```text
durable DispatchOutboxEntry/v1
        ↓
DispatchEnvelope/v1
        ↓
resolve exact durable outbox
        ↓
DispatchInboxAdmission/v1
        ↓
dispatch_inbox_v1
        ↓
ADMITTED | DUPLICATE | DENY
```

C3b still does not execute anything. It persists which exact transport content won the first durable
admission for one logical `dispatch_id` and prevents at-least-once redelivery from becoming a second
admission.

## 2. Authoritative outbox resolution

The caller supplies only one `DispatchEnvelope/v1`. The persistence service does not accept a caller-
supplied `DispatchOutboxEntry` as authority.

Inside the same serialized transaction it:

1. resolves `dispatch_outbox_v1` by the envelope's exact `outbox_id`;
2. reconstructs and hash-validates canonical `DispatchOutboxEntry/v1` from `entry_json`;
3. compares every persisted scalar projection with the reconstructed artifact;
4. requires `envelope.assert_bound_to(exact_durable_outbox)`;
5. only then performs inbox lookup/admission.

A self-consistent caller-produced envelope is therefore insufficient when it does not bind the exact
durable outbox row.

## 3. Durable dedup semantics

```text
first valid dispatch_id + exact content
    → ADMITTED + one immutable inbox row

same dispatch_id + same exact accepted content
    → DUPLICATE + existing row returned

same dispatch_id + different envelope content
    → DENY / DISPATCH_CONTENT_CONFLICT
```

`DUPLICATE` is not a second execution attempt and does not create a second durable admission.

## 4. Concurrency boundary

R1 is deliberately bound to the released SQLite persistence semantics:

```text
backend = sqlite
write_serialization = global
transaction = BEGIN IMMEDIATE
```

Two concurrent deliveries of the same logical dispatch serialize. The first transaction may append
the unique `dispatch_id`; the second observes the committed admission and classifies the exact
redelivery as `DUPLICATE`.

C3b does not claim PostgreSQL concurrency semantics. A future PostgreSQL adapter must provide an
explicit equivalent first-writer contract before this service may run on it.

## 5. Migration 0012

`0012_dispatch_inbox.sql` adds append-only `dispatch_inbox_v1` with unique logical dispatch identity,
exact outbox bindings, content-addressed admission identity and canonical admission JSON.

The database trigger requires the inbox scalar projection to match one exact `dispatch_outbox_v1`
row for:

- outbox identity and digest;
- execution identity;
- workspace and environment;
- ExecutionCapsule digest;
- runner class.

UPDATE and DELETE fail closed.

## 6. Authority boundary

C3b preserves:

```text
S_inbox <= S_envelope <= S_outbox <= S_consumed_grant <= S_snapshot
```

It does not create or select:

- a concrete RunnerIdentity;
- credentials;
- a lease;
- an ExecutionEpoch;
- a provider endpoint;
- a Handler execution;
- a provider mutation;
- a Receipt;
- a VerificationResult.

## 7. Failure semantics

Fail closed reasons include:

- `OUTBOX_NOT_FOUND`;
- `OUTBOX_ROW_INVALID`;
- `OUTBOX_BINDING_MISMATCH`;
- `INBOX_ROW_INVALID`;
- `INBOX_PERSISTENCE_CONFLICT`;
- `DISPATCH_CONTENT_CONFLICT`.

No failure is promoted to execution authority.

## 8. Verification coverage

System tests prove:

- first valid delivery creates exactly one durable admission;
- exact redelivery returns `DUPLICATE` without a second row;
- same logical dispatch with conflicting envelope content fails closed;
- two concurrent identical deliveries produce one admission and one duplicate;
- structurally valid but outbox-divergent content is denied;
- missing durable outbox is denied;
- inbox rows reject UPDATE and DELETE;
- no ProductService/ExecutionService runtime wiring exists.

## 9. Explicit non-goals

No dispatcher/network transport, delivery acknowledgement state, retry counter, lease,
ExecutionEpoch/fencing, concrete RunnerIdentity, credential brokerage, Handler execution, provider
mutation, Receipt/v2, independent verification, OperationProof, release or deployment.

## 10. C3 gate

After C3b is merged and exact-head verification is green, **Inbox + Dedup is complete** for the R1
SQLite persistence boundary.

The next bounded slice is:

```text
C4 Lease + ExecutionEpoch/Fencing
```

C4 must prove that only the currently fenced execution attempt may progress toward a future effect and
that a stale/late attempt cannot complete after lease loss or epoch supersession.
