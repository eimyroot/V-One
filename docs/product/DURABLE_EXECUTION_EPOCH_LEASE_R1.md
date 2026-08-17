# Durable ExecutionEpoch + Lease Persistence R1

## Status

Phase C / **C4b** durable safety slice for the released SQLite backend.

This slice promotes the C4a `ExecutionLease/v1` contract into a durable epoch authority. It does not
introduce a Runner identity, credentials, network transport, handler execution or provider mutation.

## Invariant

```text
NO STALE ATTEMPT MAY COMPLETE
```

For each durable `DispatchInboxAdmission/v1`, exactly one `ExecutionEpoch` is current. Epochs start at
`1` and advance by exactly one. A successor epoch may be allocated only after the current lease has
expired according to a server-constructed `ClockWitness/v1`.

## Durable model

`execution_leases_v1` is immutable history. Every lease stores the exact C3 admission projection,
ExecutionEpoch, bounded acquire/expiry window, trusted-clock evidence and canonical
`ExecutionLease/v1` artifact.

`execution_epoch_state_v1` is the single mutable current-head row for one admission. It binds the
current epoch and exact current lease and has only two valid transition classes:

```text
ACTIVE(epoch N) --after expiry--> ACTIVE(epoch N+1)
ACTIVE(epoch N) --current+unexpired--> COMPLETED(epoch N)
```

A completed admission cannot be reacquired. A stale lease cannot write completion after a successor
epoch becomes current.

## Serialization

C4b is released only for SQLite with the existing global `BEGIN IMMEDIATE` write serialization.
Acquisition, reacquisition and durable completion all resolve current state and write the successor
inside that transaction boundary. Two concurrent reacquisition attempts therefore cannot both
allocate the same successor epoch.

## Completion semantics

Completion is content-addressed by a caller-supplied SHA-256 `completion_digest`. The current,
unexpired lease may atomically persist it once. Exact redelivery of the same completion returns
`DUPLICATE_COMPLETION`; a different digest after completion is a fail-closed
`COMPLETION_DIGEST_CONFLICT`.

This is a **durable coordinator completion fence**, not proof that an external provider effect was
performed. Phase D must either keep provider effects behind an equivalent epoch-aware fence or use an
effect target that rejects stale epoch tokens.

## Trusted time

The service constructs clock witnesses through `TrustedClockAuthority` inside the serialized
transaction. Caller timestamps are not accepted as lease or completion authority. C4b persists the
acquisition and completion clock witness JSON alongside their digests.

## Database enforcement

Migration `0013_execution_epoch_leases.sql` adds:

- immutable `execution_leases_v1` history;
- `execution_epoch_state_v1` current-head state;
- exact C3 admission-binding triggers;
- first-epoch `1` enforcement;
- successor `N+1` enforcement;
- active-to-completed enforcement;
- immutable lease history and non-deletable epoch state.

The application additionally reconstructs canonical C3 and C4 artifacts from durable JSON and rejects
scalar/JSON divergence before making an authority decision.

## Explicit non-goals

- no concrete `RunnerIdentity`;
- no credentials or secret delivery;
- no network dispatcher or worker protocol;
- no handler execution;
- no provider mutation;
- no Receipt/v2 or OperationProof;
- no PostgreSQL locking semantics;
- no runtime wiring into the legacy `ExecutionService`;
- no release or deployment.

## Next gate

After C4b merge and exact-head CI, Phase C continues to **C5 DurableCoordinator**. C5 composes durable
inbox admission, current epoch/lease state and later worker lifecycle without weakening the C4 fence.
