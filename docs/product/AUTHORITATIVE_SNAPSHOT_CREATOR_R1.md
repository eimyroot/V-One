# Authoritative Snapshot Creator R1

Status: BOUNDED PHASE 2 IMPLEMENTATION CANDIDATE
Runtime wiring: NONE
Base: `main@593f70dc855c430dd90bd30333a7df81c2e89480`

## Purpose

`AuthoritativeSnapshotCreator` is the first server-side composition boundary that is allowed to
construct an `AuthorizationSnapshot` from accepted authority sources.

It is intentionally not an execution path. A successful snapshot is immutable authorization
evidence. It is not an `ExecutionGrant`, dispatch instruction, Runner credential, verification
result, release authorization, or production mutation permission.

## Transaction invariant

One creator call uses one datastore transaction:

```text
BEGIN
load immutable approved request
-> revalidate exact review-content digest
-> explicit server-owned CapabilitySelection
-> CapabilityDefinition + CapabilityActivation
-> deterministic TargetBinding
-> immutable PolicyRevision
-> exact persisted approvals
-> policy-derived approval validity
-> PermissionDecision(execution.run)
-> Trusted Clock witness
-> emergency-stop observation
-> live RevocationEpochAuthority
-> AuthorityWitnessSet
-> AuthorizationSnapshot
-> immutable snapshot persistence
-> bounded audit evidence
COMMIT
```

Any missing, stale, conflicting, inactive, revoked, unauthorized, or malformed authority denies.
Unexpected persistence/audit failure rolls the entire success path back.

## No adapter authority

The reviewed change request currently stores an `adapter` name. R1 does not promote that name into
execution authority.

`ImmutableCapabilitySelectionAuthority` is an explicit server-owned mapping from a reviewed adapter
identity to a canonical capability identity. The selected capability must still resolve through the
immutable capability registry and an exact activation generation.

```text
adapter
  -> explicit CapabilitySelectionAuthority
  -> canonical CapabilityDefinition
  -> exact CapabilityActivation
```

A missing mapping denies. No caller-supplied capability argument exists on the creator API.

## Approval validity

R1 never invents a fresh approval TTL at authorization time.

For each exact persisted approval:

```text
expiry = approved_at + PolicyRevision.approval_validity_seconds
```

The evidence set uses the earliest expiry. The trusted authorization timestamp must be no later than
that value, and every approval timestamp must be no later than authorization.

The number of persisted approved records must equal the exact immutable policy requirement for the
request environment. Ambiguous extra or missing approval evidence denies.

## Live deny observations

Snapshot creation observes:

- current server-side `execution.run` permission;
- current emergency-stop state in the same database transaction;
- current capability activation/revocation state;
- an explicit injected `RevocationEpochAuthority`;
- an authorized `TrustedClockAuthority`.

There is deliberately no synthetic revocation epoch. If no revocation authority can answer, snapshot
creation denies.

A future `GrantIssuer` must independently re-check live deny gates before granting execution.

## AuthorityWitnessSet evidence

The current `AuthorizationSnapshot` contract predates `AuthorityWitnessSet` and does not contain a
dedicated witness-set field. R1 does not silently mutate that stable contract.

Instead, the creator appends a bounded
`authorization_snapshot.authority_witness` audit event in the same transaction as snapshot
persistence. It binds:

- snapshot digest;
- authority witness-set digest;
- permission decision digest;
- capability-selection digest and authority revision;
- policy identity;
- capability definition identity;
- capability activation digest;
- target binding digest;
- approval certificate digest;
- clock witness digest;
- revocation epoch;
- creator source revision.

The event contains no raw request payload or target claims.

## Idempotency

The transaction-aware snapshot store preserves the existing snapshot idempotency binding.

- same idempotency key + same snapshot authorization inputs -> existing snapshot;
- same key + different binding -> conflict;
- an idempotent retry does not append a second authority-witness event.

`persist_prevalidated()` remains backward compatible. R1 additionally provides
`persist_prevalidated_in_transaction()` so the authoritative creator owns the outer transaction.

## Rejection evidence

Expected fail-closed authorization denials append only:

```json
{
  "correlation_id": "...",
  "reason_code": "..."
}
```

No raw payload, credential, target claims, or provider data is logged.

Stable R1 denial classes include:

- `CHANGE_REQUEST_NOT_FOUND`
- `CHANGE_REQUEST_NOT_APPROVED`
- `WORKSPACE_ENVIRONMENT_MISMATCH`
- `REVIEW_CONTENT_BINDING_MISSING`
- `REVIEW_CONTENT_DRIFT`
- `CAPABILITY_SELECTION_NOT_FOUND`
- `CAPABILITY_INELIGIBLE`
- `TARGET_BINDING_DENIED`
- `POLICY_REVISION_NOT_FOUND`
- `APPROVAL_COUNT_MISMATCH`
- `EXECUTION_PERMISSION_DENIED`
- `TRUSTED_CLOCK_DENIED`
- `APPROVAL_EXPIRED`
- `EMERGENCY_STOP_ACTIVE`
- `REVOCATION_DENIED`
- `AUTHORITY_WITNESS_INVALID`

## Explicit non-goals

This slice does **not**:

- compose the creator into `ProductService`, HTTP API, or `ExecutionService`;
- issue or sign an `ExecutionGrant`;
- implement grant replay protection;
- implement transactional dispatch/outbox;
- invoke an adapter, handler, or Runner;
- implement credential brokerage;
- implement verifier runtime;
- mutate provider state;
- enable production effects;
- release or deploy anything.

## Next gate

After this slice is independently reviewed, exact-head CI verified, accepted, and reconciled into
canonical `main`, the next separately scoped authority boundary is the authoritative `GrantIssuer`.

Snapshot creation alone must never be represented as execution readiness.
