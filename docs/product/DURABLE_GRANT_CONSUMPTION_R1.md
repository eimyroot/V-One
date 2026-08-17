# VOODOO One — Durable Grant Consumption R1

## Status

B4 defines the durable persistence and atomic ONE_TIME consumption boundary for
`execution-grant/v2`.

It is an **execution-authority consumption** boundary. It is not a dispatcher, Runner,
credential issuer, provider mutator, receipt producer, or proof system.

Merging this slice does not authorize runtime adoption, release, deployment, or any external effect.

## Canonical chain

```text
AuthorizationSnapshot
  → AuthorityConstraint
  → AuthoritativeGrantIssuer
  → ExecutionGrant/v2
  → fresh B3 conformance
  → durable append-only grant row
  → atomic consume transaction
      → exact stored grant reconstruction
      → trusted clock
      → TTL
      → emergency stop
      → live revocation epoch
      → fresh B3 conformance
      → append-only GrantConsumptionWitness/v1
  → consumed exactly once
```

## No caller-supplied persistence

B4 deliberately does not expose a public `persist(grant)` entrypoint.

The durable path is:

```text
DurableGrantService.issue_and_store(snapshot, authority)
  → server-owned AuthoritativeGrantIssuer.issue(...)
  → B4 validates live authority + B3 conformance
  → B4 persists exactly that returned grant
```

This prevents the persistence API from treating a structurally valid, caller-constructed
`ExecutionGrantV2` as proof that authoritative issuance occurred.

The composition root remains security-sensitive: the B4 service requires the GrantIssuer, operational
safety service, revocation authority and trusted clock to be the same authority instances used by
issuance, and the B1 execution-binding authority must share the same immutable capsule registry used
by B3 conformance.

## One execution, one durable grant

Migration `0010_durable_execution_grants.sql` makes `execution_id` unique in
`execution_grants_v2`.

This is stricter than uniqueness on JTI alone.

Without the execution-level constraint, two valid grants with different JTI values could be issued
for one execution and each could satisfy ONE_TIME semantics independently. B4 fails closed instead.
A new authorization attempt that must create a new grant requires a new execution identity.

## Durable schema

### `execution_grants_v2`

Append-only storage for the exact authoritative grant returned by B1.

Important bindings include:

- JTI — primary identity,
- unique Grant ID,
- unique execution ID,
- request/workspace/environment,
- exact AuthorizationSnapshot digest,
- exact ExecutionCapsule digest,
- exact Grant digest and canonical Grant JSON,
- B3 conformance witness at durable storage,
- trusted clock witness at durable storage,
- issuance/expiry timestamps,
- revocation epoch,
- store timestamp and store revision.

The database verifies that the snapshot digest, execution, request, workspace and environment resolve
to one existing `authorization_snapshots` row.

UPDATE and DELETE are rejected by triggers.

### `grant_consumptions_v1`

Append-only one-time consumption record.

`jti`, `grant_digest` and `execution_id` are unique. The row binds:

- exact stored Grant,
- AuthorizationSnapshot,
- ExecutionCapsule,
- authorized runner class,
- fresh B3 conformance witness,
- trusted clock witness,
- live revocation epoch,
- consumption timestamp,
- serialization contract,
- B4 authority revision,
- content-addressed `GrantConsumptionWitness/v1`.

UPDATE and DELETE are rejected by triggers.

## Atomic ONE_TIME semantics

SQLite R1 relies on the released persistence contract:

```text
backend_name        = sqlite
write_serialization = global
transaction         = BEGIN IMMEDIATE
serialization       = sqlite-begin-immediate/v1
```

Consumption occurs inside one `BEGIN IMMEDIATE` transaction.

For two consumers racing on the same JTI:

1. one transaction obtains the SQLite write reservation,
2. it proves the grant is still consumable and inserts the unique consumption row,
3. it commits,
4. the second transaction proceeds,
5. it observes the existing consumption and fails with `GRANT_ALREADY_CONSUMED`.

The unique database constraints remain a second fail-closed defense.

B4 refuses to initialize against a backend that does not expose the released SQLite/global-write
serialization contract. PostgreSQL remains unreleased; B4 does not guess PostgreSQL locking semantics.

## Live consume checks

A stored grant is not automatically consumable.

Every consume performs fresh checks inside the serialized transaction:

1. JTI exists in the durable grant store.
2. No prior consumption exists.
3. Canonical Grant JSON parses as `ExecutionGrantV2`.
4. Security-relevant scalar columns exactly match the parsed artifact.
5. Trusted clock is authorized for the Grant environment.
6. Consumption time is not before issuance.
7. Consumption time is strictly before `expires_at`.
8. Emergency stop is inactive.
9. Live revocation epoch equals the epoch bound into the Grant.
10. B3 `ExecutionConformanceAuthority` is evaluated again against current immutable
    capability/capsule/handler registries.
11. The append-only consumption witness is inserted atomically.

Any failure rolls back the transaction and leaves the grant unconsumed.

## Fresh B3 conformance

B3's historical witness is evidence, not runtime permission.

B4 evaluates B3 twice in its lifecycle:

- immediately before durable grant storage,
- again at ONE_TIME consumption.

A capsule or activation that is no longer execution-eligible therefore prevents consumption even if
the Grant was conformant when stored.

## Precondition boundary

B4 does **not** claim that consumption is the final execution-time TOCTOU check.

For `ATOMIC_PROVIDER_CONDITION`, the exact handler/capsule contract must later enforce the provider
condition at the real effect.

For `READ_THEN_COMPARE`, later runtime work must ensure the provider pre-state is revalidated close
enough to the real effect. B4 consumes authority; it does not execute the effect.

## Failure reasons

Representative fail-closed reasons include:

- `GRANT_NOT_FOUND`
- `GRANT_ALREADY_CONSUMED`
- `GRANT_STORE_CONFLICT`
- `STORED_GRANT_CORRUPT`
- `STORED_GRANT_BINDING_MISMATCH`
- `CLOCK_PRECEDES_GRANT`
- `GRANT_EXPIRED`
- `EMERGENCY_STOP_ACTIVE`
- `REVOCATION_AUTHORITY_DENIED`
- `REVOCATION_EPOCH_INVALID`
- `REVOCATION_EPOCH_CHANGED`
- `EXECUTION_CONFORMANCE_DENIED`
- `EXECUTION_CONFORMANCE_INVALID`
- `EXECUTION_CONFORMANCE_GRANT_MISMATCH`

## Non-goals

B4 does not add:

- transactional outbox,
- DispatchEnvelope,
- inbox/dedup,
- lease acquisition,
- ExecutionEpoch/fencing for the new authority chain,
- concrete RunnerIdentity,
- credentials,
- provider effects,
- ExecutionReceipt/v2,
- independent post-state verification,
- OperationProof,
- ProductService/ExecutionService runtime wiring,
- PostgreSQL support.

## Milestone

After B4 is merged and its gates pass, the precise milestone is:

`EXECUTION_AUTHORITY_CONSUMPTION_READY`

It is **not** `BOUNDED_RUNTIME_READY`.

The next phase is Phase C durable dispatch:

```text
GrantConsumptionWitness
  → Transactional Outbox
  → DispatchEnvelope
  → Inbox / Dedup
  → Lease
  → ExecutionEpoch / fencing
```
