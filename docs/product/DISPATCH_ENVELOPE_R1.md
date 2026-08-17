# DispatchEnvelope/v1 — C2 R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@12513f8b6dbf1b910bff996e012d920205b8c120`  
Phase: C2 — Durable Dispatch  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

C2 defines the exact transport artifact that may represent one already-committed C1b transactional
outbox intent.

```text
ExecutionGrant/v2
        ↓
GrantConsumptionWitness/v1
        +
DispatchOutboxEntry/v1        durable / committed
        ↓
DispatchEnvelope/v1           C2
        ↓
Inbox / Dedup                  C3 — not implemented here
```

C2 does not dispatch work. It freezes the content that a later transport may redeliver without
allowing the transport layer to invent a new target, payload, capsule, runner class or authority.

## 2. Authority boundary

`DispatchEnvelope/v1` is not new authority. It is a content-bound transport representation of one
exact durable `DispatchOutboxEntry/v1`.

The monotonic relationship remains:

```text
S_envelope <= S_outbox <= S_consumed_grant <= S_snapshot
```

C2 may copy already-bound claims. It may not widen them.

The envelope does not prove:

- that an inbox admitted it;
- that a lease exists;
- that an execution epoch is current;
- that a concrete RunnerIdentity was selected;
- that credentials were issued;
- that execution-time preconditions still hold;
- that a provider effect happened;
- that post-state verification succeeded.

## 3. Caller boundary

`DispatchEnvelope.create(...)` accepts only:

- one exact `DispatchOutboxEntry`;
- one envelope contract revision.

The caller does **not** supply:

- `dispatch_id`;
- target or payload;
- capability;
- execution capsule;
- runner class;
- workspace/environment;
- grant/consumption identities;
- a Runner endpoint;
- a concrete Runner identity;
- transport destination;
- queue state;
- retry counter;
- lease or execution epoch.

All security-relevant operation claims are copied from the exact outbox entry.

## 4. Deterministic logical dispatch identity

C2 derives `dispatch_id` deterministically from:

```text
dispatch-id/v1
+
outbox_id
+
outbox_entry_digest
```

The caller cannot choose it.

This gives C3 a stable logical dedup identity for repeated delivery of the same durable outbox intent.
The `dispatch_id` deliberately does not depend on an ephemeral transport attempt or network endpoint.
It also remains stable if the envelope serialization revision changes, so changing protocol versions
cannot manufacture a second logical operation.

A later C3 rule should therefore be fail-closed:

```text
same dispatch_id + same accepted envelope content  -> duplicate/redelivery
same dispatch_id + conflicting content             -> DENY / CONTENT CONFLICT
```

C2 itself does not persist an inbox decision.

## 5. Delivery semantics

The only C2 delivery semantic is:

```text
AT_LEAST_ONCE_REDELIVERY_DEDUP_REQUIRED
```

This is intentionally not `EXACTLY_ONCE`.

A transport may redeliver an envelope after timeout, process restart or uncertain acknowledgement.
Exactly-once provider effect cannot be obtained merely by naming a queue mode. It requires the later
C3 inbox/dedup boundary, C4 lease/epoch fencing and capability-specific idempotency/precondition
semantics.

## 6. DispatchEnvelope/v1 fields

The content-addressed envelope binds:

```text
dispatch_id
outbox_id
outbox_entry_digest
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
outbox_created_at
outbox_revision
delivery_semantics
envelope_revision
envelope_digest
```

`required_permission` remains exactly `execution.run` and `use_semantics` remains exactly `ONE_TIME`.

There is no concrete Runner identity in C2. Thesis R2 orders that after inbox/dedup and lease/epoch.

## 7. Exact outbox binding

`DispatchEnvelope.assert_bound_to(...)` compares the complete copied projection against one supplied
`DispatchOutboxEntry` and fails closed on any mismatch.

This is required because `DispatchEnvelope.from_dict(...)` is only a strict **structural parser**.
A caller can calculate SHA-256 over invented JSON. Hash consistency is not authority and does not
prove durable outbox existence.

A future runtime path must therefore resolve the authoritative durable `dispatch_outbox_v1` row and
verify the envelope against that exact row before inbox admission.

## 8. No mutable dispatch state

C2 adds no fields such as:

```text
PENDING
SENT
DELIVERED
RETRYING
ACKED
FAILED
```

Those are operational events/state transitions, not properties of the immutable dispatch intent.
Later durable attempts and acknowledgements must not rewrite the original outbox or envelope identity.

## 9. Security properties

C2 fails closed when:

- the dispatch id is changed or caller-selected;
- the outbox identity/digest changes;
- target, payload, capsule or runner class is changed without changing envelope content identity;
- `execution.run` is replaced;
- `ONE_TIME` is replaced;
- delivery semantics claim exactly-once behavior;
- unknown fields are introduced;
- an envelope is checked against a different durable outbox entry.

The envelope contains no network address and no arbitrary route string. Transport routing must not
become a mechanism to replace the grant-bound runner class.

## 10. Non-goals

C2 does not add:

- database migration;
- outbox mutation;
- dispatcher process;
- broker/network transport;
- delivery attempts or acknowledgements;
- inbox persistence;
- dedup persistence;
- leases;
- ExecutionEpoch/fencing;
- concrete RunnerIdentity;
- scoped credentials;
- handler execution;
- provider effect;
- Receipt/v2;
- independent verification;
- OperationProof;
- ProductService/ExecutionService runtime wiring;
- PostgreSQL support;
- release or deployment.

## 11. C3 gate

The next bounded slice is **C3 Inbox + Dedup**.

C3 must prove at minimum:

```text
one logical dispatch_id
        ↓
first valid envelope       -> one durable inbox admission
same valid redelivery      -> duplicate, no second admission
same id + conflicting body -> DENY
```

C3 must resolve/bind the exact durable outbox identity before accepting an envelope. It must not treat
a structurally valid caller-produced envelope as proof of authority.

## 12. Acceptance evidence

C2 is review-ready only after exact-head repository `verify` succeeds.

System tests cover at minimum:

- exact projection from C1a outbox;
- strict serialization round-trip;
- deterministic dispatch identity;
- stable logical identity across redelivery;
- different outbox => different dispatch identity;
- caller cannot supply dispatch id;
- changed dispatch id denied;
- exactly-once delivery claim denied;
- self-consistent envelope tamper fails exact outbox binding;
- digest tamper and unknown fields denied;
- no current runtime wiring.

## 13. Milestone

After merge, C2 means:

```text
DISPATCH_ENVELOPE_CONTRACT_READY
```

It does **not** mean durable inbox, dispatcher, bounded runtime, execution or verification is ready.
