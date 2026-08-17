# ExecutionLease/v1 + ExecutionEpoch fencing — C4a R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@6fccd02b68672b1dd3394df9a96f1802605a7b81`  
Phase: C4a — Lease + ExecutionEpoch/Fencing contract  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

C3 now gives V-One one durable admitted logical dispatch and durable deduplication. C4 must prevent a
worker attempt that was delayed, expired or superseded from later completing an effect as though it
were still current.

The bounded C4 chain is:

```text
durable DispatchInboxAdmission/v1
        ↓
current durable ExecutionEpoch
        ↓
ExecutionLease/v1
        ↓
completion/effect fence
        ↓
current + unexpired only
```

This PR freezes the value contract and fail-closed decision semantics first. It deliberately does not
claim durable epoch allocation. C4b must add that persistence boundary under the released serialized
database transaction.

## 2. Core invariant

```text
NO STALE ATTEMPT MAY COMPLETE
```

A structurally valid lease is not enough. At every future completion/effect boundary the system must
resolve the **current durable execution epoch** and require exact equality with the lease epoch.

```text
lease.execution_epoch == current durable epoch
AND trusted time < lease.expires_at
AND exact C3 admission binding
→ fence may be CURRENT

otherwise
→ DENY
```

## 3. Monotonic epoch semantics

C4a freezes one sequence only:

```text
first epoch      = 1
next epoch       = previous + 1
reuse            = DENY
regression       = DENY
skip             = DENY
```

`assert_next_execution_epoch(...)` defines this transition rule but is not an allocator. C4b must
allocate the epoch in durable state while holding the released SQLite `BEGIN IMMEDIATE` serialization
boundary.

The epoch is a fencing token, not authority to widen target, payload, capability, capsule or runner
scope.

## 4. ExecutionLease/v1

The immutable lease binds:

```text
lease_id
dispatch_id
admission_id
admission_digest
execution_id
workspace_id
environment
execution_capsule_digest
runner_class
execution_epoch
acquired_at
expires_at
clock_witness_digest
lease_revision
lease_digest
```

The logical `lease_id` is deterministic from:

```text
execution-lease-id/v1
+
admission_id
+
execution_epoch
```

Changing serialization revision or lease body cannot manufacture a second logical lease for the same
admission/epoch pair. C4b must enforce exactly one durable accepted lease body for that identity.

## 5. Trusted time and bounded duration

Lease acquisition requires an existing `ClockWitness/v1` whose environment equals the admitted
operation environment. The lease is bounded to at most 3600 seconds in this R1 contract. The
completion fence denies:

- a clock witness from another environment;
- observation before lease acquisition;
- observation at or after expiry.

Expiry at the exact `expires_at` instant is fail-closed.

## 6. Fence outcomes

The contract has one positive outcome:

```text
FENCE_CURRENT
```

Negative decisions are exceptions with explicit reasons:

```text
STALE_EXECUTION_EPOCH
EXECUTION_EPOCH_REGRESSION
LEASE_EXPIRED
CLOCK_BEFORE_LEASE
CLOCK_ENVIRONMENT_MISMATCH
LEASE_ADMISSION_BINDING_MISMATCH
EXECUTION_EPOCH_TRANSITION_INVALID
```

No stale/expired case is represented as a warning that a caller may ignore.

## 7. Authority boundary

C4a preserves the existing monotonic chain:

```text
S_lease <= S_inbox <= S_envelope <= S_outbox <= S_consumed_grant <= S_snapshot
```

The lease copies only already-bound admission claims plus the fencing epoch and bounded trusted-time
window. It cannot select a different target, payload, capability, capsule or runner class.

There is deliberately **no concrete RunnerIdentity** in C4a. Runner identity belongs to Phase D after
C4 closes durable stale-attempt fencing. A transport worker name, endpoint or credential must not be
smuggled into this contract as authority.

## 8. Important non-authority statement

`ExecutionLease.create_candidate(...)` accepts a candidate integer epoch because this slice has no
durable allocator yet. Therefore:

```text
candidate lease JSON != current epoch authority
```

Likewise, `assert_completion_fence(current_execution_epoch=...)` defines the decision semantics but
does not make the supplied integer authoritative. C4b must remove that trust boundary from runtime use
by resolving the current epoch itself from durable state in the same safety boundary used to authorize
completion/effect.

## 9. Verification coverage

System tests cover:

- exact C3 admission projection;
- strict serialization round trip;
- deterministic lease identity;
- stable logical lease identity across contract revision;
- first/successor epoch transition semantics;
- epoch reuse, regression and skip denial;
- bounded lease duration;
- clock-environment binding;
- current unexpired epoch → `FENCE_CURRENT`;
- superseded epoch → `STALE_EXECUTION_EPOCH`;
- durable-epoch regression signal → fail closed;
- expiry at exact deadline → fail closed;
- pre-acquisition clock → fail closed;
- admission/digest/identity/unknown-field tamper rejection;
- no ProductService or legacy ExecutionService runtime wiring.

## 10. Explicit non-goals

This PR does **not** add:

- migration or durable epoch state;
- durable lease allocation;
- lease renewal/reacquisition persistence;
- concrete RunnerIdentity;
- credentials;
- dispatcher/network transport;
- handler execution;
- provider mutation;
- provider-side atomic precondition enforcement;
- Receipt/v2;
- independent verification;
- OperationProof;
- ProductService/ExecutionService runtime wiring;
- PostgreSQL support;
- release or deployment.

The legacy `executions.fence` / `lease_expires_at` fields remain a separate older execution lifecycle.
C4 must not silently treat that table as the new proof-carrying dispatch epoch authority.

## 11. C4b gate

The next bounded slice is **C4b Durable ExecutionEpoch + Lease Persistence**.

C4b must prove at minimum:

```text
first durable admitted dispatch
    → epoch 1 + one durable lease

expired/current lease reacquisition
    → epoch increments exactly once

concurrent claimers
    → one current epoch/lease winner

old lease after epoch increment
    → STALE / cannot pass completion fence

current epoch + expired lease
    → cannot pass completion fence
```

The durable current-epoch read and completion-fence decision must not be separable by an unsafe race.
No provider effect is enabled by C4b itself.

After C4b is green and merged, C4 may be considered complete for the released SQLite R1 persistence
boundary and the next phase is C5 DurableCoordinator.
