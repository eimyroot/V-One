# Dispatch Outbox Contract R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@20d36f8fd86857cd095b3aa05ddc22b25086ec02`  
Phase: C1a — Durable Dispatch Contract  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

C1a defines the content-bound handoff artifact between Phase B execution-authority
consumption and the later Phase C transactional outbox.

The contract is:

```text
ExecutionGrant/v2
        +
GrantConsumptionWitness/v1
        ↓
DispatchOutboxEntry/v1
```

C1a does not persist an outbox row and does not dispatch anything. Its purpose is to freeze
exactly what C1b may atomically persist so the persistence slice cannot invent broader runtime
scope.

## 2. Why the contract comes before persistence

B4 proves that one authoritative `ExecutionGrant/v2` was consumed exactly once under fresh
TTL, emergency-stop, live-revocation and B3 conformance checks.

A later dispatcher still needs a durable handoff identity. If that handoff were assembled from
caller-supplied routing values, a downstream component could silently substitute a different target,
payload, capsule or runner class even though the Grant itself was narrower.

C1a prevents that class of widening by making the outbox artifact a deterministic projection of the
exact consumed Grant.

## 3. Caller boundary

`DispatchOutboxEntry.create(...)` accepts only:

- an outbox id;
- one exact `ExecutionGrantV2`;
- one exact `GrantConsumptionWitness`;
- an outbox contract revision.

The caller does not supply:

- execution id;
- request id;
- actor/workspace/environment;
- capability;
- target kind or target digest;
- payload digest;
- authorization snapshot digest;
- execution binding digest;
- execution capsule digest;
- runner class;
- precondition enforcement class;
- permission;
- use semantics;
- creation time.

Those values are copied from the exact Grant or consumption witness.

## 4. Exact consumption binding

Before creating an outbox artifact, C1a requires exact equality between the supplied Grant and
consumption witness for:

```text
jti
grant_id
grant_digest
execution_id
authorization_snapshot_digest
execution_capsule_digest
runner_class
```

A valid consumption witness for another Grant cannot be combined with the supplied Grant.

## 5. DispatchOutboxEntry/v1

The content-addressed entry binds:

```text
outbox_id
consumption_id
consumption_witness_digest
jti
grant_id
grant_digest
execution_id
request_id
actor_id
workspace_id
environment
capability
capability_definition_identity
authorization_snapshot_digest
target_kind
target_digest
payload_digest
required_permission
execution_binding_digest
execution_capsule_digest
runner_class
precondition_enforcement_class
use_semantics
created_at
outbox_revision
entry_digest
```

`required_permission` remains exactly `execution.run` and `use_semantics` remains exactly
`ONE_TIME`.

## 6. Monotonic dispatch invariant

C1a preserves the adopted Thesis R2 invariant:

```text
S_outbox <= S_consumed_grant <= S_snapshot
```

The outbox entry cannot select a different target, payload, capsule or runner class. A change in any
bound dispatch claim produces a different entry digest.

The entry is a dispatch intent artifact, not new authority.

## 7. Structural parsing is not runtime permission

`DispatchOutboxEntry.from_dict(...)` is a strict structural parser. A caller being able to construct
self-consistent JSON and SHA-256 does not prove:

- authoritative Grant issuance;
- successful ONE_TIME consumption;
- durable outbox persistence;
- current dispatch eligibility;
- a lease;
- a valid execution epoch;
- a concrete Runner identity;
- credential authority;
- provider effect;
- post-state verification.

C1b must persist the entry only while atomically creating the exact B4 consumption record.

## 8. C1b transactional requirement

The next bounded slice must satisfy:

```text
BEGIN serialized transaction
    prove Grant still consumable
    append GrantConsumptionWitness/v1
    append exact DispatchOutboxEntry/v1
COMMIT
```

Forbidden state:

```text
consumption committed
+
outbox missing
```

If outbox insertion fails, consumption must roll back and the Grant must remain unconsumed.

The first released C1b implementation should use the same SQLite `BEGIN IMMEDIATE` serialization
contract already proven by B4. PostgreSQL semantics remain a later explicit contract.

## 9. Outbox persistence shape

C1b should use an immutable outbox intent row rather than a mutable `PENDING → SENT` status row.
Later dispatch claims, attempts, acknowledgements, inbox/dedup and leases should be separate durable
records so operational history is not rewritten in place.

At minimum the database must uniquely bind one outbox entry to one Grant consumption and reject
UPDATE/DELETE of the intent row.

## 10. Non-goals

C1a does not add:

- database migration;
- outbox persistence;
- mutable queue state;
- dispatcher;
- `DispatchEnvelope`;
- inbox/dedup;
- lease;
- execution epoch/fencing;
- concrete RunnerIdentity;
- credential brokerage;
- handler execution;
- provider mutation;
- ExecutionReceipt/v2;
- independent post-state verification;
- OperationProof;
- ProductService/ExecutionService runtime wiring;
- release;
- deployment;
- production effect.

## 11. Next gate

```text
C1a DispatchOutboxEntry/v1 contract
        ↓
C1b migration + atomic consumption/outbox append
        ↓
C2 DispatchEnvelope/v1
```

C1 is not complete until C1b proves the atomic persistence invariant.

## 12. Acceptance evidence

C1a is review-ready only after exact-head CI passes the repository's complete `verify` job.

System tests must demonstrate at minimum:

- exact consumed-Grant projection;
- strict Grant ↔ consumption binding;
- deterministic serialization round trip;
- target/payload/capsule/runner claims copied from the Grant;
- changed authorized target changes the entry digest;
- mismatched consumption witness denial;
- tamper rejection;
- unknown-field rejection;
- reusable authority rejection;
- no persistence, dispatch or provider effect introduced by this slice.

CI success does not authorize merge, runtime adoption, release, deployment or provider effects.
