# Phase F / F6 — Governed Rollback R1

Status: implementation candidate; **no live rollback has been authorized or executed by this PR**.

## Scope

F6 defines the governed rollback path for the exact F4b canary ref. The rollback is a separate governed mutation, not an implicit inverse of the original CREATE_REF authority.

Canonical target class:

- capability: `github.delete-exact-created-ref/v1`
- environment: `staging`
- namespace: `refs/heads/vone-canary/`
- effect ceiling: `mutation.reversible`
- maximum provider mutations: `1`
- provider host: fixed `api.github.com`
- automatic retry after ambiguous provider outcome: forbidden

## Temporal truth

GitHub delete-ref does not provide an expected-SHA compare-and-delete condition. F6 therefore does **not** claim `ATOMIC_PROVIDER_CONDITION`.

The R1 temporal model is:

`READ exact ref -> compare exact expected SHA -> one DELETE -> independent absence readback`

and is canonically labelled:

`READ_THEN_DELETE_NON_ATOMIC`

The pre-delete observation narrows authority but cannot eliminate the race window between the final READ and provider DELETE. A stale or substituted SHA must fail before the provider mutation.

## Versioning

Existing CREATE_REF-specific contracts remain semantically unchanged. F6 uses new versions or new terms where rollback semantics differ:

- `runner-boundary/v3`
- `credential-broker-policy/v3`
- `credential-access-decision/v3`
- `ephemeral-rollback-credential-delivery/v1`
- `write-runtime-activation/v2`
- `write-effect-preflight/v2`
- `github-ref-absence-observation/v1`
- `verifier-github-ref-absence-observation/v1`
- `independent-verification-boundary/v2`
- `verifier-credential-decision/v2`

`ExecutionCapsule/v1` and `HandlerConformanceEvidence/v1` are reused with their already-defined `READ_THEN_COMPARE` semantics. They must not claim an atomic provider condition for this rollback.

## Verification

A provider `404` for the exact deleted ref is represented as explicit absence evidence rather than silently discarded as an error. Runner absence observation and Verifier absence observation are separate artifacts.

The independent verifier path remains READ-only and must preserve identity, provider-instance and credential-class separation from the rollback Runner.

Only after independent absence readback may the existing generic artifacts be composed:

`ObservedPostState/v1 -> VerificationStrength/v1 -> VerificationResult/v1`

with `VerificationResult.verdict = VERIFIED` for exact independently observed absence.

`Observation != VerificationResult` and `ExecutionReceipt != VerificationResult` remain invariant.

## Dry-slice ceiling

This PR may contain mutation-capable transport code, but it contains no live workflow, no token, no credential value, no provider invocation and no provider effect. A future live rollback requires a separate explicit gate after exact-head CI, review-thread and base-drift acceptance.

## Exit gate for Phase F

Phase F is not complete until a separately authorized live rollback proves all of the following:

1. exact pre-delete ref SHA equals the F4b-created SHA;
2. exactly one governed DELETE is attempted;
3. ambiguous provider outcomes are not retried automatically;
4. Runner readback observes exact target absence;
5. an independent Verifier separately observes the same absence;
6. `VerificationResult/v1` is `VERIFIED` for the rollback post-state;
7. the rollback effect is recorded in `ExecutionReceipt/v2` without conflating receipt and verification;
8. live workflow replay is sealed/fail-closed;
9. canonical evidence is retained before declaring Phase F complete.

`OperationProof/v2` and `OperationCell/v1` remain downstream and are not introduced by this dry F6 slice.
