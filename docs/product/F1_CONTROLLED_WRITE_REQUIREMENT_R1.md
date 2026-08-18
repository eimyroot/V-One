# F1 Controlled Write Requirement R1

Status: IMPLEMENTATION CANDIDATE / NO PROVIDER WRITE

Baseline: `main@9cedd387e0c65709065eb5b7dec78199f7e11198`

Phase: F1 — Controlled Write Contract

## Purpose

F1 begins Phase F without performing a provider mutation.

It freezes the eligibility contract for the first bounded write path while preserving every released
Phase-D READ-only contract unchanged.

The first candidate capability is:

```text
github.create-ref/v1
```

The intended future effect is creation of one unique canary Git ref in the dedicated namespace:

```text
refs/heads/vone-canary/<exact operation-bound suffix>
```

F1 itself does not create a ref, obtain a write credential, activate a write-capable runtime, construct
an ExecutionReceipt, or claim VerificationResult for a write.

## Why create-ref is the first mutation candidate

The first write must be smaller than merge, deploy, release, file overwrite, branch force-update or
arbitrary API access.

A create-ref canary has useful properties for the first governed write:

- exact repository + fully-qualified ref + exact commit SHA can be authority-bound;
- creation is a distinct provider operation from update-ref;
- F1 forbids force update and overwrite semantics;
- the ref namespace is V-One-owned and non-production;
- the existing Git-ref READ observation and independent verifier path can later inspect its post-state;
- rollback can be represented as a separate governed deletion of the exact created ref.

The rollback is deliberately a separate operation. F1 does not treat cleanup authority as implicit
child authority of the original create operation.

## Canonical F1 chain

```text
CapabilityDefinition
        ↓
ExecutionCapsule/v1
        ↓
HandlerConformanceEvidence/v1
        ↓
GitHubCreateRefConditionContract/v1
        ↓
ControlledWriteRequirement/v1
        ↓
F1 ELIGIBLE CANDIDATE
```

This chain does not include a provider transport.

## `github-create-ref-condition/v1`

The provider-condition contract freezes the first mutation semantics:

```text
provider                      = github
operation                     = CREATE_REF
target_kind                   = git_ref
ref namespace                 = refs/heads/vone-canary/
create semantics              = CREATE_ONLY
overwrite existing ref        = false
force update                  = false
rollback strategy             = DELETE_EXACT_CREATED_REF
verification class            = provider-read/v1
```

Its content digest is the `atomic_provider_condition_contract_identity` carried by the existing B3
HandlerConformanceEvidence contract.

`CREATE_ONLY` means a later handler may call only the provider create-ref operation for this capability.
It may not silently substitute update-ref, force-update or a generic GitHub write client.

## `controlled-write-requirement/v1`

The requirement is content-addressed evidence that one immutable execution definition is eligible for
the first Phase-F write design.

It binds:

- exact CapabilityDefinition identity;
- exact ExecutionCapsule digest;
- exact HandlerConformanceEvidence digest;
- exact atomic provider-condition contract identity;
- exact verification-contract identity;
- effect class `mutation.reversible`;
- exactly one provider mutation maximum;
- rollback strategy `DELETE_EXACT_CREATED_REF`;
- explicit `provider_mutation_allowed=true` candidate semantics.

The requirement is not execution authority. `provider_mutation_allowed=true` describes the candidate
contract; it does not grant permission to mutate GitHub.

## First-write eligibility ceiling

F1 fails closed unless all of these are true:

1. capability is exactly `github.create-ref/v1`;
2. target kind is exactly `git_ref`;
3. handler is exactly `github-create-ref-handler/v1`;
4. effect class is exactly `mutation.reversible`;
5. verification class is exactly `provider-read/v1`;
6. capability is not production-eligible;
7. capability supports staging only;
8. capsule requires `ATOMIC_PROVIDER_CONDITION`;
9. handler evidence exactly matches the capsule;
10. handler evidence binds the exact create-ref condition digest;
11. maximum provider mutations is exactly one.

## Phase-D non-regression

F1 does not edit or broaden:

```text
runner-boundary/v1
read-only-runtime-activation/v1
credential-access-decision/v1
```

`RunnerBoundary/v1` remains:

```text
effect_ceiling             = READ_ONLY
provider_mutation_allowed  = false
```

A future write-capable runtime boundary must use a new versioned contract or a new canonical term. It
must not reinterpret the released Phase-D contract in place.

## Authority and credential boundary

F1 creates no new authority source.

The future write path must still originate from the existing chain:

```text
AuthorizationSnapshot
  → ExecutionGrant/v2
  → fresh B3 conformance
  → atomic ONE_TIME consumption
  → transactional outbox
  → durable inbox admission
  → current ExecutionEpoch + ExecutionLease
```

A future write credential must be separately authorized, short-lived, scoped to the exact provider
capability and narrower than the Grant/Capsule authority. F1 contains no token, secret, bearer value,
secret handle or ambient credential fallback.

## Provider-condition requirement

For Phase F, `READ_THEN_COMPARE` is not sufficient for the first mutation.

The first write requires:

```text
ATOMIC_PROVIDER_CONDITION
```

For create-ref, the concrete handler must prove that it used create-only provider semantics and did not
fall back to update-ref. A later live acceptance must include a negative case showing that attempting the
same create operation against an already-existing exact canary ref fails closed rather than overwriting
it.

## Verification requirement

The future write must not trust the create response as verification.

After the provider mutation, the existing independent verifier path must perform a fresh read of the
exact created ref and derive:

```text
ObservedPostState/v1
  → VerificationStrength/v1
  → VerificationResult/v1
```

Runner/provider success alone remains insufficient for VERIFIED.

## Rollback semantics

`DELETE_EXACT_CREATED_REF` is a rollback strategy, not implicit rollback authority.

Rollback must be a separately authorized operation with its own current target observation and authority
chain. Because the provider delete-ref operation does not itself supply F1's create-only condition, a
future rollback slice must define its own stale-state/fencing semantics before automatic cleanup is
allowed.

F1 therefore does not delete any ref.

## Phase F continuation

The bounded continuation is:

```text
F1  ControlledWriteRequirement + create-ref condition contract       ← this slice
 ↓
F2  write-specific RunnerBoundary / CredentialAccessDecision versions
 ↓
F3  exact github.create-ref/v1 target binder + handler/transport
    contract tests only; still no live mutation
 ↓
F4  explicit-authorized live canary create-ref through full A→B→C→F chain
    + ExecutionReceipt/v2
 ↓
F5  independent readback through existing verifier path
    + live VerificationResult
 ↓
PHASE F COMPLETE
```

The F4 provider write is a separate consequential gate and requires explicit authorization after exact
head CI, negative tests and write-credential review are complete.

## Acceptance for F1

F1 is acceptable only if:

- canonical round trips and content digests pass;
- unknown/tampered fields fail closed;
- READ-only capability is rejected;
- `READ_THEN_COMPARE` mutation is rejected;
- production eligibility is rejected;
- substituted atomic provider-condition identity is rejected;
- `runner-boundary/v1` remains frozen READ_ONLY;
- VOP schema registry includes both new contract IDs;
- no HTTP/provider transport or secret delivery is introduced;
- full repository CI is green on the exact candidate head.

## Non-goals

No provider call. No GitHub write. No ref creation. No ref deletion. No write credential. No write-capable
runtime activation. No Grant issuance or consumption. No new dispatch behavior. No ExecutionReceipt/v2.
No OperationProof. No release. No deploy. No production effect.
