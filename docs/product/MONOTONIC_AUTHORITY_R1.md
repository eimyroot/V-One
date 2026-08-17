# Monotonic Authority R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Base: `main@ad1b7b7bc44ad3e5f0701ae88ce167db84cdffed`  
Parent product thesis: adopted `VONE_PRODUCT_ARCHITECTURE_THESIS_R2`  
Roadmap slice: A9 / Phase A authority-cell completeness

## Purpose

Monotonic Authority R1 turns the Thesis R2 invariant

```text
EVERY DOWNSTREAM LAYER MAY ONLY NARROW AUTHORITY.
```

into a machine-checkable contract.

This slice does **not** issue an `ExecutionGrant`, dispatch work, create a credential, invoke a Runner,
or cause a provider effect. It defines the content-addressed parent authority scope and the only
accepted shape of a child restriction.

The core relation is:

```text
child authority ⊆ parent authority
```

For the current singular V-One authority model, non-temporal security bindings must remain exact and
time may only narrow.

## Contracts

### `authority-scope/v1`

`AuthorityScope` is an immutable projection of one accepted `AuthorizationSnapshot`.

It binds:

- exact `authorization_snapshot_digest`;
- actor;
- workspace;
- environment;
- canonical capability;
- capability-definition identity;
- target kind + target digest;
- payload digest;
- policy version + immutable policy identity;
- approval-set digest;
- required `execution.run` permission;
- authorization start;
- approval-derived authority expiry.

The scope is content-addressed by `scope_digest`.

The parent scope never extends the snapshot. It only projects authority facts already present in the
snapshot into the vocabulary used by downstream narrowing checks.

### `authority-constraint/v1`

`AuthorityConstraint` is one proposed downstream restriction.

It carries an explicit `parent_scope_digest` and repeats all security-relevant scope bindings.
In R1:

- actor cannot change;
- workspace cannot change;
- environment cannot change;
- capability cannot change;
- capability-definition identity cannot change;
- target kind or target digest cannot change;
- payload digest cannot change;
- policy version or policy identity cannot change;
- approval-set digest cannot change;
- required permission cannot change;
- `valid_from` may move later;
- `valid_until` may move earlier;
- use semantics are exactly `ONE_TIME`.

The constraint is content-addressed by `constraint_digest`.

R1 deliberately does not invent wildcard, hierarchy, pattern, resource-prefix, or semantic-subset
rules. The current authority is singular and exact. A future capability that genuinely needs a richer
subset relation must introduce a versioned scope schema with explicit conformance tests instead of
guessing whether one string or JSON object is "narrower" than another.

### `monotonic-authority-decision/v1`

`MonotonicAuthorityChecker.check(...)` returns a content-addressed decision only when the child is
`NARROW_OR_EQUAL`.

Any widening raises `MonotonicAuthorityViolation` with stable bounded reason codes.

There is no boolean fallback that a caller can reinterpret as permission.

## Fail-closed checks

R1 rejects at least:

```text
wrong parent scope digest
different actor
different workspace
different environment
different capability
different capability-definition identity
different target kind
different target digest
different payload digest
different policy version
different policy identity
different approval set
different required permission
earlier child validity start
later child validity end
child starting after parent expiry
reusable child authority
```

A denial creates no authority decision and has no runtime side effect.

## Relationship to the existing `ExecutionGrant/v1`

The repository already contains a structural `ExecutionGrant` value object in
`voodoo_product/execution_contract.py`.

That contract validates important local properties such as:

- one-time semantics;
- maximum TTL;
- target/evidence bindings;
- approval validity;
- content-addressed grant digest.

However, it currently does **not** carry a direct immutable parent `AuthorizationSnapshot` or
`AuthorityScope` digest.

Therefore:

```text
structurally valid ExecutionGrant != authoritative child of a snapshot
```

A9 does not silently bless the historical structural contract.

The future B1 authoritative GrantIssuer must derive its child authority through this monotonic
contract and must preserve an explicit immutable parent binding in the authoritative grant path.
Whether that requires a versioned grant schema or an additional bound grant-authority object is a B1
decision; A9 does not pre-authorize either implementation.

## Relationship to A8

A8 answers:

```text
What exact authority was valid at authorization time?
```

A9 answers:

```text
Did a later layer keep or narrow that authority without widening it?
```

A9 does not repeat:

- approval reconstruction;
- permission evaluation;
- capability activation;
- target binding;
- policy resolution;
- trusted-clock authority;
- revocation observation.

Those are upstream authority facts already composed by A8.

## Relationship to A10 PreconditionWitness

Monotonic Authority is not a TOCTOU check.

A child may be perfectly narrower than its parent while the external world has changed since
authorization.

A10 remains separately required:

```text
snapshot authority valid
        +
downstream authority did not widen
        +
required provider pre-state still matches
        =
eligible to continue toward effect
```

Changed external preconditions still require `DENY / REAUTHORIZE`.

## B1 GrantIssuer gate

An authoritative GrantIssuer must not issue usable execution authority unless:

1. its parent snapshot is valid and immutable;
2. an exact `AuthorityScope` is projected from that snapshot;
3. the proposed child authority is explicitly parent-bound;
4. `MonotonicAuthorityChecker` returns `NARROW_OR_EQUAL`;
5. grant-time live deny/revocation checks pass;
6. the final grant cannot outlive the parent authority;
7. the final grant cannot weaken one-time semantics;
8. downstream credentials and execution capsules cannot broaden the grant.

A structural `ExecutionGrant.from_dict(...)` result is not sufficient evidence for any of those
claims.

## Explicit non-goals

A9 does not implement:

- `PreconditionWitness`;
- GrantIssuer;
- grant persistence or replay consumption;
- JTI;
- credential scope;
- ExecutionCapsule;
- Handler/Runner/Verifier registry;
- dispatch/outbox;
- Runner;
- provider mutation;
- verification;
- OperationProof;
- runtime adoption;
- release or deployment.

## Verification requirements

System tests in this slice verify:

1. deterministic snapshot -> `AuthorityScope` projection;
2. strict content-addressed serialization;
3. equal authority is accepted;
4. later start / earlier expiry is accepted;
5. every currently expressible security-binding change is denied;
6. wrong parent binding is denied;
7. earlier start is denied;
8. later expiry is denied;
9. stale child starting after parent expiry is denied;
10. reusable authority is structurally rejected;
11. a different permission is structurally rejected;
12. tampered contract digests are rejected;
13. unknown contract fields are rejected;
14. A9 is not wired into current `ProductService` or `ExecutionService`.

## Adoption/runtime status

Merging this implementation candidate, if separately authorized, would make the contracts available
in the codebase.

It would **not** mean:

```text
GrantIssuer active
runtime uses A9
Runner uses A9
credentials are narrowed
provider effects are governed by A9
Phase A complete
release approved
deployment approved
```

Phase A remains incomplete until the separately reviewed PreconditionWitness slice is merged and the
Phase A gate is re-evaluated against exact `main`.
