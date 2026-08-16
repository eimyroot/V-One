# Authority Primitives R1

| Field | Value |
|---|---|
| Document class | Bounded implementation evidence / design note |
| Scope | Phase 1 Authority Kernel primitives only |
| Runtime wiring | NONE |
| Snapshot Creator | NOT IMPLEMENTED |
| Grant Issuer | NOT IMPLEMENTED |
| Runner | NOT IMPLEMENTED |
| Production effects | NOT AUTHORIZED |

## Objective

Implement the first bounded code slice required by the Verifiable Operations Trust Plane before any
Authoritative Snapshot Creator is allowed to exist.

This slice introduces immutable, digest-bearing authority primitives and read-only registries for:

- exact `PolicyRevision` identities;
- current server-side `execution.run` permission decisions with an explicit current-scope marker;
- versioned `CapabilityDefinition` identities;
- exact `CapabilityActivation` generations;
- deterministic `TargetBinder` registration and target-binding evidence;
- `ApprovalCertificate` binding exact reviewed content, policy identity, and approval evidence;
- `TrustedClockAuthority` and digest-bearing `ClockWitness`;
- `AuthorityWitnessSet` composition over the exact authority evidence used for a future authorization.

## Boundary

The implementation is deliberately not connected to `ExecutionService` and does not alter the
existing `/change-requests/{request_id}/execute` path.

It does not:

- create `AuthorizationSnapshot`;
- issue `ExecutionGrant`;
- sign or dispatch anything;
- consume grants;
- invoke a Runner;
- mutate provider state;
- enable production effects;
- infer owner adoption for ADR-0012.

The current role permission adapter records `scope_model=current-global-role/v1`. That makes the
present server-side role model explicit and prevents a future consumer from silently treating it as
workspace-scoped tenancy authority.

## Fail-closed properties

The slice rejects or denies:

- unknown policy revision;
- duplicate policy or capability identities;
- missing, revoked, or environment-ineligible capability activation;
- production execution for a non-production-eligible capability;
- missing target binder;
- binder/target-kind mismatch;
- permission actor mismatch;
- policy mismatch in approval evidence;
- naive or unauthorized clock sources;
- denied permission in an `AuthorityWitnessSet`;
- cross-authority identity mismatches.

## Next gate

The next implementation slice may build `AuthoritativeSnapshotCreator` only after these primitives
pass repository CI and are reviewed as the authoritative input boundary.

The creator must then perform, in one database transaction:

```text
authoritative reads
-> permission decision
-> policy revision
-> capability definition + activation
-> deterministic target binding
-> approval certificate
-> trusted clock witness
-> revocation/live deny observations
-> AuthorityWitnessSet
-> AuthorizationSnapshot
-> persistence
-> audit
-> COMMIT
```

Any missing or conflicting authority must roll back and deny.
