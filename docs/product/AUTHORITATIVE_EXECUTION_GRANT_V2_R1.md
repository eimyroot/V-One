# Authoritative ExecutionGrant/v2 R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@2970bd33ec0b7ee593473659f34efa88c2fb4248`  
Phase: B1 — Execution Authority  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

B1 introduces the first authoritative V-One execution grant contract without changing the
published semantics of `execution-grant/v1`.

The invariant is:

```text
AuthorizationSnapshot
        ↓
AuthorityScope
        ↓
AuthorityConstraint
        ↓
MonotonicAuthorityDecision
        ↓
live revocation + emergency-stop check
        ↓
server-owned execution binding
        ↓
fresh PreconditionWitness
        ↓
trusted issuance clock
        ↓
ExecutionGrant/v2
```

`ExecutionGrant/v2` is a bounded child of already-established authority. It is not a new
source of authority and cannot widen its parent.

## 2. Versioning decision

`execution-grant/v1` is frozen as the legacy structural contract. B1 does not edit it and
does not change `ExecutionReceipt/v1`.

The authoritative contract is a new semantic version:

```text
execution-grant/v2
```

This preserves historical meaning and prevents a silent security-semantic change to v1.

## 3. Caller-controlled versus authoritative inputs

The public issuance boundary accepts only:

- one `AuthorizationSnapshot`;
- one A9 `AuthorityConstraint`.

The caller does **not** supply:

- parent `AuthorityScope`;
- `MonotonicAuthorityDecision`;
- snapshot-time or live revocation epoch;
- `PreconditionWitness`;
- precondition observation;
- execution capsule digest;
- runner class;
- issuer identity;
- issuance time;
- expiry.

The issuer derives or resolves all of those through server-owned authorities.

## 4. Snapshot authority evidence bridge

A8 currently stores `revocation_epoch` in the
`authorization_snapshot.authority_witness` audit event, not inside
`AuthorizationSnapshot` itself.

B1 therefore resolves exactly one authority-witness event for the supplied snapshot and
checks:

- canonical payload encoding;
- exact expected fields;
- audit event self-hash;
- snapshot id and snapshot digest;
- actor binding;
- policy identity;
- capability-definition identity;
- authorization-source revision;
- authority-witness-set digest format;
- snapshot-time revocation epoch.

Missing or duplicate authority-witness evidence is fail-closed.

This bridge does not redefine A8. It consumes the authority evidence A8 already records.

## 5. Live deny and revocation semantics

Before performing the precondition read, the issuer checks:

- emergency stop is inactive;
- live revocation authority is readable;
- current revocation epoch equals the snapshot-time epoch.

Because the precondition read can involve an external provider, the issuer repeats the
emergency-stop and live-revocation checks after the precondition read and before returning
the grant.

This still does not make revocation consumption atomic with a future external effect.
B4 grant consumption MUST re-check live deny/revocation at one-time consumption.

## 6. Execution binding seam

B1 defines:

```text
ExecutionBindingAuthority
        ↓
ExecutionBinding/v1
        ├── capability_definition_identity
        ├── environment
        ├── target_kind
        ├── execution_capsule_digest
        ├── runner_class
        ├── authority_revision
        └── binding_digest
```

The caller cannot choose `execution_capsule_digest` or `runner_class`.

B1 does not implement `ExecutionCapsule/v1`. The execution-binding authority is the narrow
B2 seam. A B1 grant is therefore **not runtime-eligible** until B2 provides the real
capsule/conformance authority.

This lets the v2 grant schema bind the capsule from day one without inventing a fake
capsule implementation.

## 7. Fresh precondition requirement

The issuer does not accept a caller-provided `PreconditionWitness`.

It calls A10 `PreconditionGuard` itself using:

- the scope projected from the exact snapshot;
- the caller's A9 child constraint;
- a recomputed monotonic decision;
- the snapshot's exact execution target.

A10 then performs a fresh authoritative read and emits a witness only for an exact state
match.

The grant binds:

- requirement digest;
- expectation digest;
- observation digest;
- witness digest;
- enforcement class;
- check timestamp.

The maximum precondition-check-to-grant interval in R1 is 30 seconds.

## 8. TOCTOU boundary

A `READ_THEN_COMPARE` precondition witness proves only that the authoritative state matched
at observation time. It does not claim provider-side atomicity.

If the requirement is `ATOMIC_PROVIDER_CONDITION`, later B2/B3 Handler and
ExecutionCapsule conformance must prove that the exact provider condition
(CAS/ETag/version/head-SHA or equivalent) is carried into the effect.

The grant preserves `precondition_enforcement_class`; it does not downgrade it.

## 9. ExecutionGrant/v2 claims

The v2 contract content-binds:

### Identity

- `grant_id`
- `jti`
- `execution_id`
- `request_id`

### Parent authority

- `authorization_snapshot_digest`
- snapshot authority witness-set digest
- snapshot authority audit event hash
- `parent_scope_digest`
- `authority_constraint_digest`
- `monotonic_authority_decision_digest`

### Narrowed authority claims

- actor
- workspace
- environment
- capability
- capability-definition identity
- target kind and digest
- payload digest
- policy version and identity
- approval-set digest
- `execution.run`

### Precondition

- requirement digest
- expectation digest
- observation digest
- witness digest
- enforcement class
- checked-at timestamp

### Execution binding

- execution-binding digest
- execution-capsule digest
- runner class
- execution-binding authority revision

### Lifetime and issuance

- issued-at
- expires-at
- revocation epoch
- `ONE_TIME`
- issuer identity and revision
- grant digest

Maximum grant TTL remains 300 seconds and the configured TTL is additionally clamped to
the A9 child authority expiry.

## 10. Structural parsing is not authority proof

`ExecutionGrantV2.from_dict(...)` validates schema, canonical field constraints and
`grant_digest`. It is a structural parser only.

A caller being able to construct self-consistent JSON or SHA-256 does not create authority.

Before runtime adoption, B4 must provide durable issuance/consumption evidence so a
deserialized grant can be proven to have come from the authoritative issuer and to be
unconsumed.

## 11. JTI and ONE_TIME status

B1 emits:

- `jti`;
- `use_semantics = ONE_TIME`.

B1 does **not** yet persist or consume the JTI.

Replay prevention and atomic one-time consumption belong to B4. Until B4 is complete,
`ExecutionGrant/v2` is not runtime-eligible.

## 12. Legacy compatibility

B1 intentionally leaves unchanged:

- `voodoo_product/execution_contract.py`;
- `ExecutionGrant/v1`;
- `ExecutionReceipt/v1`;
- current `ProductService`;
- current `ExecutionService`;
- database schema.

The legacy v1 grant/receipt chain keeps its historical semantics.

## 13. Failure behavior

Issuance is fail-closed for at least:

- monotonic-authority widening;
- missing or duplicate snapshot authority evidence;
- malformed or mismatched authority evidence;
- invalid audit event self-hash;
- active emergency stop;
- unavailable or invalid revocation authority;
- revocation epoch drift before or during the precondition window;
- missing or mismatched execution binding;
- failed or changed precondition;
- invalid trusted issuance clock;
- stale precondition witness;
- authority not valid at issuance;
- non-positive resulting grant lifetime.

No denial can be converted into allow by an LLM, callback, provider adapter, runner or
handler.

## 14. B1 non-goals

B1 does not add:

- Grant persistence;
- JTI consumption;
- replay protection;
- ExecutionCapsule/v1 implementation;
- credentials;
- DispatchEnvelope;
- outbox/inbox;
- Runner;
- provider mutation;
- receipt v2;
- independent post-state verification;
- OperationProof;
- runtime wiring;
- release;
- deployment;
- production effect.

## 15. Next gates

After B1:

```text
B2  ExecutionCapsule/v1
    + real ExecutionBindingAuthority/conformance

B3  Grant ↔ Capsule ↔ runner-class conformance

B4  durable grant issuance + JTI/ONE_TIME consumption
    + replay prevention
    + live revocation/emergency-stop re-check at consumption

Phase C
    durable dispatch / outbox / inbox / leases / epochs
```

## 16. Acceptance evidence

B1 is review-ready only when exact-head CI passes the repository's full `verify` job.

System tests must demonstrate at minimum:

- successful grant issuance from the exact Phase-A chain;
- content-addressed round trip;
- revocation drift denial;
- revocation change during the precondition window denial;
- emergency-stop denial;
- emergency stop activated during the precondition window denial;
- A9 widening denial;
- changed precondition denial;
- execution-binding mismatch denial;
- bounded precondition-to-grant interval;
- grant expiry clamped to child authority;
- tamper/unknown-field rejection;
- `execution-grant/v1` unchanged;
- no B1 runtime wiring.

CI success does not authorize merge, runtime adoption, release, deployment or provider
effects.
