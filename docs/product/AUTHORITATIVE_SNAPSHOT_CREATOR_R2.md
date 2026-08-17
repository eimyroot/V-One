# Authoritative Snapshot Creator R2

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Base: `main@d344aedaed48fccbd9bd27f24ba8c187d9215d0a`  
Parent product thesis: adopted `VONE_PRODUCT_ARCHITECTURE_THESIS_R2`  
Supersedes implementation candidate: historical divergent `feat/authoritative-snapshot-creator-r1`

## Purpose

`AuthoritativeSnapshotCreator` is the bounded server-side composition boundary allowed to construct
and persist one `authorization-snapshot/v1` from accepted authority sources.

A successful snapshot is immutable authorization evidence. It is not:

- an `ExecutionGrant`;
- a dispatch instruction;
- a Runner credential;
- a provider mutation;
- a verification result;
- release authorization;
- deployment authorization.

The creator is deliberately not composed into `ProductService`, HTTP API, or `ExecutionService`.

## R2 transaction invariant

One call owns one datastore transaction:

```text
BEGIN
  load exact approved reviewed request
  revalidate canonical payload + review-content digest
  check production-effects gate
  check emergency stop
  resolve server-owned adapter -> canonical capability selection
  resolve exact CapabilityDefinition + CapabilityActivation
  derive deterministic TargetBinding from approved payload
  resolve immutable PolicyRevision
  read TrustedClock witness
  A7: resolve exact persisted ApprovalEvidenceSet on SAME connection
  construct ApprovalCertificate
  resolve execution.run PermissionDecision
  verify exact actor/workspace/environment/permission decision bindings
  read live RevocationEpochAuthority
  construct AuthorityWitnessSet
  construct AuthorizationSnapshot
  A2: persist snapshot on SAME connection
  append bounded authority-witness audit evidence
COMMIT
```

Any denial, source error, conflict, persistence error, or witness-audit failure escapes the
transaction and rolls back all writes from the creator call.

R2 intentionally does **not** commit a separate rejection audit record from a denied creator
transaction. A denial produces no snapshot, no authority-witness event, and no partial creator
evidence. This follows the adopted Thesis R2 fail-closed transaction rule.

## Authoritative source rules

### Reviewed request

The creator accepts only a persisted request in exact `APPROVED` state whose:

- request environment equals workspace environment;
- payload is canonical JSON;
- persisted `review_content_sha256` exists;
- recomputed `change-request-review/v1` digest exactly matches the persisted digest.

### Capability selection

The request currently persists an `adapter` identity. R2 does not promote that value directly into
execution authority.

```text
reviewed adapter
  -> ImmutableCapabilitySelectionAuthority
  -> canonical versioned capability
  -> ImmutableCapabilityRegistry
  -> exact activation generation
```

A missing mapping, inactive capability, revoked activation, unsupported environment, or
production-ineligible capability fails closed.

### Target binding

`TargetBinderRegistry` derives the exact `ExecutionTarget` only from:

- the accepted immutable capability definition; and
- the exact canonical approved payload.

The caller cannot supply capability, target, target digest, or target claims.

### Policy

The creator receives one server-owned immutable `policy_version` selector and resolves that exact
revision through `ImmutablePolicyAuthority`.

The caller does not supply a policy revision to `create_snapshot()`.

### Approval evidence

R2 delegates approval reconstruction to the already-merged A7 resolver:

`load_approval_evidence_on_connection(...)`

A7 runs on the same caller-owned transaction connection and validates exact request binding,
approval review-content binding, canonical timestamps, requester independence, quorum, target,
capability, payload digest, policy version, trusted authorization time, and policy-derived expiry.

R2 does not reimplement or weaken A7.

### Permission decision

The permission authority must return a granted `execution.run` decision bound exactly to:

- requested actor;
- request workspace;
- request environment;
- `execution.run`.

A granted decision for another actor, workspace, environment, or permission is denied.

### Live deny observations

Before snapshot persistence R2 observes:

- production-effects gate;
- emergency-stop state on the same datastore connection;
- capability activation/revocation;
- trusted clock authority;
- live revocation epoch;
- current `execution.run` permission.

There is no synthetic revocation epoch. Missing or invalid revocation authority fails closed.

A future GrantIssuer must independently re-check all grant-time live deny gates. A historical
snapshot is evidence of an authorization decision, not an irrevocable bearer permission.

## Success evidence

The existing A2 `AuthorizationSnapshotStore.persist_prevalidated_on_connection(...)` persists:

- the immutable snapshot;
- exact child target/evidence bytes;
- the bounded `authorization_snapshot.create` audit event.

R2 then appends `authorization_snapshot.authority_witness` in the same transaction, binding:

- snapshot digest;
- authority witness-set digest;
- permission decision digest;
- capability-selection digest + authority revision;
- policy identity;
- capability definition identity;
- capability activation digest;
- target binding digest;
- approval certificate digest;
- clock witness digest;
- revocation epoch;
- authorization source revision.

The witness event contains no raw approved payload, raw target claims, credential, or provider data.

## Idempotency

A2 remains authoritative for snapshot idempotency.

- same idempotency key + same snapshot authorization binding -> existing snapshot;
- same key + different binding -> conflict;
- an idempotent retry does not append another authority-witness event.

Generated `snapshot_id`, `execution_id`, and `authorized_at` remain excluded from the existing A2
idempotency binding exactly as defined by `AuthorizationSnapshot`.

R2 does not change the snapshot contract or store semantics.

## Stable R2 denial classes

The public creator emits bounded reason codes including:

- `CHANGE_REQUEST_NOT_FOUND`
- `CHANGE_REQUEST_NOT_APPROVED`
- `WORKSPACE_ENVIRONMENT_MISMATCH`
- `REVIEW_CONTENT_BINDING_MISSING`
- `REQUEST_PAYLOAD_INVALID`
- `REQUEST_PAYLOAD_NON_CANONICAL`
- `REVIEW_CONTENT_DRIFT`
- `PRODUCTION_EFFECTS_DISABLED`
- `EMERGENCY_STOP_ACTIVE`
- `CAPABILITY_SELECTION_NOT_FOUND`
- `CAPABILITY_SELECTION_MISMATCH`
- `CAPABILITY_INELIGIBLE`
- `TARGET_BINDING_DENIED`
- `POLICY_REVISION_NOT_FOUND`
- `TRUSTED_CLOCK_DENIED`
- `TRUSTED_CLOCK_BINDING_MISMATCH`
- `APPROVAL_EVIDENCE_DENIED`
- `PERMISSION_DECISION_INVALID`
- `PERMISSION_DECISION_BINDING_MISMATCH`
- `EXECUTION_PERMISSION_DENIED`
- `REVOCATION_DENIED`
- `REVOCATION_EPOCH_INVALID`
- `AUTHORITY_WITNESS_INVALID`

The reason code is intentionally less detailed than internal authority-source exceptions.

## Verification requirements in this slice

System tests cover at minimum:

1. exact successful snapshot + persisted authority witness;
2. A2 idempotent retry without duplicate witness evidence;
3. denied `execution.run` leaves no creator write or rejection audit;
4. expired A7 approval evidence leaves no snapshot;
5. unknown adapter-to-capability selection fails closed;
6. a granted permission decision bound to the wrong workspace fails closed;
7. live emergency stop blocks creation;
8. unavailable/revoked revocation authority blocks creation;
9. production request is denied while production-effects gate is closed;
10. authority-witness audit failure rolls back snapshot + snapshot audit atomically;
11. creator remains absent from the current product runtime.

## Explicit non-goals

This slice does **not** implement or wire:

- `PreconditionWitness`;
- Monotonic Commit Guard;
- `ExecutionGrant` or GrantIssuer;
- signing/JWS/key management;
- grant replay/one-time consumption;
- transactional outbox or dispatch;
- Runner execution;
- CASTER-MINAL or SandCloud integration;
- credentials;
- independent post-state verifier;
- `OperationProof`;
- provider mutation;
- production effect;
- release;
- deploy.

These remain separately gated work under the adopted Thesis R2.

## Next gate

After exact-head CI, independent review, and reconciliation into canonical `main`, the next
authority slice is the GrantIssuer boundary plus the separately defined precondition/monotonic
authority gates.

Snapshot creation alone must never be represented as end-to-end execution readiness.
