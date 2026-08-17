# DispatchInboxAdmission/v1 — C3 Contract R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@f198782489b30aff97736915fc62ff5383ee15b7`  
Phase: C3 — Durable Dispatch / Inbox + Dedup  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

C3 closes the next boundary after C2 `DispatchEnvelope/v1`:

```text
durable DispatchOutboxEntry/v1
        ↓
DispatchEnvelope/v1
        ↓
DispatchInboxAdmission/v1      this contract slice
        ↓
durable inbox persistence      next C3 persistence slice
        ↓
Lease + ExecutionEpoch/Fence   C4
```

This slice freezes the semantic admission artifact and duplicate/conflict rules before persistence is
added. It deliberately does not claim that an admission has been durably stored.

The final C3 gate remains durable Inbox + Dedup. This contract is an internal bounded sub-slice of C3,
not a new product phase.

## 2. Authority boundary

Inbox admission creates no new execution authority.

The chain remains:

```text
S_inbox <= S_envelope <= S_outbox <= S_consumed_grant <= S_snapshot
```

The admission may only bind already-authorized identifiers and execution constraints from one exact
C2 envelope and one exact C1b outbox entry.

It does not select:

- another target;
- another payload;
- another capability;
- another execution capsule;
- another runner class;
- a concrete RunnerIdentity;
- credentials;
- a lease;
- an execution epoch;
- a provider endpoint.

## 3. Required authoritative input

`DispatchInboxAdmission.create(...)` accepts only:

- one strict `DispatchEnvelope/v1`;
- one exact `DispatchOutboxEntry/v1`;
- one admission contract revision.

Before admission construction, the envelope must pass `DispatchEnvelope.assert_bound_to(...)` against
the supplied outbox entry.

A structurally valid or self-hashed envelope is therefore not sufficient authority evidence. The
future durable C3 service must first resolve the authoritative `dispatch_outbox_v1` row and reconstruct
its exact immutable `DispatchOutboxEntry/v1` before admission.

## 4. Logical dedup key

C3 preserves C2's deterministic logical identity:

```text
dispatch_id = H(dispatch-id/v1 + outbox_id + outbox_entry_digest)
```

The caller cannot choose the dispatch id.

The inbox admission id is also deterministic and caller-independent:

```text
admission_id = H(
    dispatch-inbox-admission-id/v1
    + dispatch_id
    + envelope_digest
    + outbox_entry_digest
)
```

This identity is evidence of exact accepted content, not an exactly-once execution claim.

## 5. Duplicate and conflict semantics

The canonical C3 rule is:

```text
first valid dispatch_id
    -> ADMIT exactly one content binding

same dispatch_id + same accepted envelope/outbox content
    -> DUPLICATE

same dispatch_id + different accepted content
    -> DENY / DISPATCH_CONTENT_CONFLICT
```

A protocol revision cannot silently replace previously admitted content. C2 deliberately keeps the
logical `dispatch_id` stable across envelope serialization revisions; therefore a different envelope
revision for an already-admitted dispatch id is conflicting content unless the persisted admission is
explicitly versioned by a future governed contract.

A different `dispatch_id` is a different logical dispatch and is not classified as redelivery of the
existing admission.

## 6. DispatchInboxAdmission/v1 fields

The immutable contract binds:

```text
admission_id
dispatch_id
envelope_digest
outbox_id
outbox_entry_digest
execution_id
workspace_id
environment
execution_capsule_digest
runner_class
admission_revision
admission_digest
```

The admission intentionally does not contain mutable delivery state such as:

```text
PENDING
RUNNING
ACKED
FAILED
RETRYING
```

C4 lease/attempt state must be represented by separate durable artifacts rather than rewriting the
admission.

## 7. Structural parsing is not authority

`DispatchInboxAdmission.from_dict(...)` performs strict structural validation and digest consistency.
It does not prove that:

- the referenced outbox exists durably;
- the envelope was derived from that outbox;
- this admission won an atomic first-writer race;
- another admission for the same dispatch id does not already exist.

The future persistence service must prove those properties transactionally.

## 8. Persistence contract required to complete C3

The next bounded C3 persistence slice must provide an immutable durable table and service with at least:

```text
BEGIN IMMEDIATE
  resolve dispatch_outbox_v1 by exact outbox_id
  reconstruct + validate exact DispatchOutboxEntry/v1
  validate DispatchEnvelope/v1 against exact outbox
  lookup dispatch_id in durable inbox

  if missing:
      append exact DispatchInboxAdmission/v1
      outcome = ADMITTED

  if existing + exact same content:
      outcome = DUPLICATE

  if existing + conflicting content:
      DENY / DISPATCH_CONTENT_CONFLICT
COMMIT
```

Two concurrent deliveries of the same logical dispatch must serialize so that exactly one durable
admission exists.

The persistence layer must be append-only. UPDATE and DELETE of an admitted logical dispatch must fail
closed.

## 9. Explicit non-goals

This contract slice does not add:

- database migration;
- durable inbox rows;
- network dispatcher;
- transport acknowledgements;
- retry counters;
- lease;
- ExecutionEpoch/fencing;
- concrete RunnerIdentity;
- credential brokerage;
- handler execution;
- provider mutation;
- Receipt/v2;
- independent verification;
- OperationProof;
- ProductService/ExecutionService runtime wiring;
- release or deployment.

## 10. Acceptance evidence

This contract is review-ready only after exact-head repository CI succeeds.

System tests cover at minimum:

- exact envelope/outbox projection;
- deterministic admission identity;
- caller cannot supply admission identity;
- exact redelivery -> `DUPLICATE`;
- same dispatch id + conflicting envelope content -> fail closed;
- different logical dispatch is not redelivery;
- self-consistent structural tamper does not prove authoritative binding;
- digest/identity/unknown-field rejection;
- no current runtime wiring.

## 11. C3 completion gate

After this contract is merged, C3 is **not complete**.

The next slice is the durable persistence half of the same phase:

```text
C3a contract semantics     -> this slice
C3b durable Inbox + Dedup  -> next
                              ↓
C3 GATE
                              ↓
C4 Lease + ExecutionEpoch/Fencing
```

Only after C3b proves one durable admission per logical dispatch, exact duplicate classification,
content-conflict denial and concurrent first-writer safety may Phase C advance to C4.
