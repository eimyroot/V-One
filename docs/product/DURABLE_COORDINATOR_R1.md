# DurableCoordinator R1

Status: Phase C / C5 implementation contract.

## Purpose

`DurableCoordinator` is the engine-independent seam over the released C3 durable inbox and C4 execution-epoch lease contracts.

It exists so V-One can replace the current native coordination implementation later without changing trust-kernel semantics or allowing an orchestration engine to mint authority.

## Canonical transition surface

```text
DispatchEnvelope/v1
        |
        v
C3 durable admit / dedup
        |
        v
DispatchInboxAdmission/v1   <-- durable commit
        |
        v
C4 acquire ExecutionLease/v1
        |
        v
ExecutionEpoch N            <-- durable commit
        |
        v
future Phase D worker boundary
        |
        v
C4 fenced completion        <-- durable commit
```

C5 exposes exactly three transitions:

- `admit(envelope)` delegates to the released C3 durable inbox contract;
- `acquire(admission_id)` delegates to the released C4 durable epoch/lease authority;
- `complete(lease_id, completion_digest)` delegates to the released C4 completion fence.

## Non-authority rule

The coordinator is not an authority source. It must not:

- issue or widen an `ExecutionGrant`;
- modify an `AuthorizationSnapshot`;
- invent a `RunnerIdentity` or credential;
- bypass durable C3 admission;
- bypass the current C4 epoch fence;
- execute a handler or contact a provider;
- claim exactly-once provider effects.

Authority continues to narrow through the existing durable lineage.

## Recovery semantics

The commit boundaries intentionally remain separate.

| Failure point | Durable truth | Safe recovery |
| --- | --- | --- |
| before C3 commit | no admission | redeliver the same `DispatchEnvelope/v1` |
| after C3 commit, before C4 lease | immutable admission exists | call `acquire(admission_id)` |
| after C4 lease commit, before future worker completion | current epoch/lease exists | wait for completion or lease expiry |
| after lease expiry | expired epoch remains history | reacquire exactly epoch `N+1` |
| stale worker returns after reacquire | newer current epoch exists | C4 completion fence denies stale epoch |
| same completion repeated | completion digest already stored | exact duplicate is idempotent |
| conflicting completion repeated | different digest already stored | fail closed |

This means C5 does not require one giant transaction across transport admission, scheduling and completion. Each released commit is independently recoverable.

## Current native implementation

`NativeDurableCoordinator` composes the current C3 and C4 services over one shared durable database boundary. It contains no Temporal, Restate, DBOS or provider-runtime dependency.

The interface is intentionally small enough that a future durable engine adapter can implement `DurableCoordinator` without becoming part of V-One's authority model.

## Phase C gate

C5 closes the orchestration seam only. Provider execution remains forbidden in Phase C.

The Phase C invariants are:

```text
NO PROVIDER EFFECT BEFORE DURABLE COMMIT
NO STALE ATTEMPT MAY COMPLETE
```

Phase D may introduce a read-only isolated worker only if it preserves the current execution epoch at the worker/effect boundary.

## Next phase

After C5 merge and exact-head verification, Phase C is complete and the next bounded scope is **Phase D — READ-ONLY SandCloud**.
