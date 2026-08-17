# Precondition Witness R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Base: `main@283e264c45be017eb4650b48e5c913570f6f96cc`  
Parent product thesis: adopted `VONE_PRODUCT_ARCHITECTURE_THESIS_R2`  
Depends on: A8 `AuthoritativeSnapshotCreator`, A9 `Monotonic Authority R1`

## Purpose

A10 adds the execution-time precondition contract required to detect stale real-world state between
authorization and a future provider effect.

It answers one narrow question:

> Does the authoritative pre-state observed immediately before execution still equal the exact
> pre-state encoded by the already-authorized target?

A successful `PreconditionWitness` is evidence of a matching precondition observation. It is not an
`ExecutionGrant`, provider mutation, credential, receipt, verification result, release authorization,
deployment authorization, or proof that the subsequent provider effect was atomic.

## Why this exists

Point-in-time authorization can be correct at `T0` and stale by `T1`.

Example:

```text
authorized target:
  pull request = 89
  expected head = abc123

provider state changes:
  head = def456

execution attempt:
  must DENY / REAUTHORIZE
```

A9 prevents downstream authority from widening. A10 prevents execution from silently using that
bounded authority against a materially different authoritative pre-state.

## R1 chain

```text
AuthorizationSnapshot
        ↓
AuthorityScope
        ↓
AuthorityConstraint
        ↓
MonotonicAuthorityDecision
        ↓
PreconditionRequirement
        ↓
registry-selected ExpectationBinder
        ↓
PreconditionExpectation
        ↓
registry-selected authoritative Observer
        ↓
TrustedClock witness
        ↓
PreconditionObservation
        ↓
exact state-digest comparison
        ↓
PreconditionWitness(MATCH)
```

The witness binds both the parent scope and the already-monotonic child constraint so a future
`ExecutionGrant` can remain linked to the same narrowed authority.

## Contracts

### `precondition-requirement/v1`

A content-addressed capability requirement bound to one exact
`capability_definition_identity`.

It fixes:

- target kind;
- expectation binder identity;
- authoritative observer identity;
- state schema;
- comparison mode;
- required enforcement class;
- requirement revision.

R1 supports only:

```text
comparison_mode = EXACT_STATE_DIGEST
```

No wildcard, fuzzy, semantic, LLM, similarity, or heuristic comparison is accepted.

The enforcement requirement is one of:

```text
READ_THEN_COMPARE
ATOMIC_PROVIDER_CONDITION
```

`ATOMIC_PROVIDER_CONDITION` is a requirement on the eventual effect path. A10 does not claim that
simply producing a witness made the later mutation atomic.

### `precondition-expectation/v1`

The expected state is derived by a registry-selected deterministic binder from the exact
`ExecutionTarget` already bound by authority.

The public `PreconditionGuard` does not accept arbitrary expected state from its caller.

The expectation binds:

- parent `AuthorityScope`;
- exact `AuthorityConstraint`;
- requirement digest;
- target kind and digest;
- state schema;
- canonical expected-state bytes and SHA-256 digest.

### `precondition-observation/v1`

The observation is created from:

- the registry-selected observer;
- its explicit source identity;
- the exact authorized target;
- the required state schema;
- a trusted-clock witness taken after the provider read;
- canonical observed-state bytes and SHA-256 digest.

Provider/module adapters may implement the observer, but provider-specific SDK behavior remains
outside the authority kernel.

### `precondition-witness/v1`

A witness is emitted only when:

```text
expected_state_digest == observed_state_digest
```

and all scope, monotonic-decision, requirement, target, observer, schema, clock and validity bindings
match.

A successful witness includes:

- parent scope digest;
- child authority-constraint digest;
- monotonic-authority decision digest;
- requirement digest;
- expectation digest;
- observation digest;
- exact target digest;
- expected and observed state digests;
- observer/source identity;
- trusted-clock witness digest;
- check timestamp;
- required enforcement class;
- relation `MATCH`.

A changed precondition raises fail-closed `PreconditionViolation` with
`PRECONDITION_CHANGED`; no `MATCH` witness is created.

## Time invariant

The observation timestamp must satisfy the already-narrowed authority interval:

```text
authority.valid_from <= checked_at < authority.valid_until
```

Checking before the child authority begins or at/after its expiry is denied.

## Fail-closed source selection

The guard resolves its requirement, expectation binder and observer from immutable/read-only
registries.

Missing or mismatched sources deny execution.

Representative bounded reason codes include:

```text
PRECONDITION_REQUIREMENT_NOT_FOUND
EXPECTATION_BINDER_NOT_FOUND
PRECONDITION_OBSERVER_NOT_FOUND
EXPECTATION_BINDER_TARGET_KIND_MISMATCH
EXPECTATION_BINDER_STATE_SCHEMA_MISMATCH
OBSERVER_TARGET_KIND_MISMATCH
OBSERVER_STATE_SCHEMA_MISMATCH
EXPECTATION_BINDER_DENIED
PRECONDITION_OBSERVER_DENIED
TRUSTED_CLOCK_DENIED
TRUSTED_CLOCK_BINDING_MISMATCH
PRECONDITION_OBSERVATION_INVALID
MONOTONIC_AUTHORITY_INVALID
MONOTONIC_AUTHORITY_DECISION_MISMATCH
TARGET_KIND_SCOPE_MISMATCH
TARGET_DIGEST_SCOPE_MISMATCH
PRECONDITION_CHECK_BEFORE_AUTHORITY
PRECONDITION_CHECK_AFTER_AUTHORITY_EXPIRY
PRECONDITION_CHANGED
```

Internal provider/read exceptions are not promoted into authority.

## Important limitation: read-check is not atomic effect enforcement

A normal sequence:

```text
READ
COMPARE
MATCH
EFFECT
```

still contains a small race window between `MATCH` and `EFFECT`.

Therefore A10 deliberately distinguishes requirement classes.

For a consequential capability, production conformance should prefer a provider-side conditional
effect where available, for example CAS/version/ETag/head-SHA style enforcement:

```text
READ authoritative state
        ↓
MATCH
        ↓
provider mutation conditioned on the same version/token
```

A future Handler/ExecutionCapsule contract must prove that an
`ATOMIC_PROVIDER_CONDITION` requirement is actually consumed by the effect path. A10 alone does not
make that claim.

Where a provider offers no atomic conditional primitive, the capability's effect/risk class must
define whether `READ_THEN_COMPARE` is acceptable. High-risk production eligibility must not be
silently inferred.

## Boundary with A8 and A9

A8:

```text
Was this exact operation authorized at authorization time?
```

A9:

```text
Did downstream authority remain equal or narrower?
```

A10:

```text
Does the authoritative pre-state still match before effect?
```

None of these questions substitutes for the others.

## Explicit non-goals

A10 does not add:

- `ExecutionGrant` issuance;
- grant persistence/replay/JTI;
- provider credentials;
- `ExecutionCapsule`;
- outbox/dispatch;
- Runner wiring;
- provider mutations;
- independent post-state verification;
- `OperationProof`;
- runtime adoption;
- release or deployment.

The existing `ExecutionService` remains unchanged.

## Verification requirements

The A10 system slice covers at minimum:

1. exact matching state emits a deterministic content-addressed witness;
2. changed authoritative state fails closed;
3. monotonic decision must bind the same child authority;
4. target drift is denied before provider observation;
5. missing requirement fails closed;
6. binder/schema mismatch fails closed;
7. provider read failure becomes a bounded denial;
8. checks outside the child-authority validity interval fail closed;
9. enforcement requirement is preserved without falsely claiming atomic effect;
10. expectation/observation contracts canonicalize and round-trip;
11. tampered contract digests fail;
12. strict parsers reject unknown fields;
13. A10 remains absent from current `ProductService` and `ExecutionService`.

## Immediate consequence

After A10 is merged and exact-head verification is green, Phase A of the adopted Thesis R2 has the
required primitives:

```text
AuthoritativeSnapshotCreator
+ live deny/revocation observation
+ Monotonic Authority
+ PreconditionWitness contract
```

The next bounded phase is B1 authoritative `GrantIssuer`.

B1 must bind a future grant to the same monotonic authority relation and precondition requirement.
A10 does not authorize B1 implementation, merge, runtime wiring, release, deploy, or provider effect.
