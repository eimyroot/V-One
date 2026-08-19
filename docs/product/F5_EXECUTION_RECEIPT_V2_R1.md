# F5 — ExecutionReceipt/v2 R1

## Status

Candidate contract for the current VOP A→B→C→F execution/effect lineage.

## Purpose

`execution-receipt/v2` is the execution subsystem's content-addressed claim about one completed bounded provider effect. It supersedes the historical `execution-receipt/v1` identity for the current authoritative execution chain without rewriting v1 history.

It binds the exact lineage:

`AuthorizationSnapshot → ExecutionGrant/v2 → ExecutionCapsule → GrantConsumptionWitness → DispatchEnvelope → DispatchInboxAdmission → ExecutionLease → RunnerIdentity → RunnerBoundary → CredentialAccessDecision → RuntimeActivation → WriteEffectPreflight → provider request → provider response → durable completion`.

## Semantic boundary

```text
ExecutionReceipt != VerificationResult
ExecutionReceipt SUCCESS != VERIFIED
```

R1 therefore serializes `verification_status = NOT_EVALUATED`. A receipt cannot construct or carry a `VERIFIED` verdict. Independent provider readback remains the E3/E4 verifier responsibility.

## R1 invariants

For a successful bounded-write receipt:

- exactly one provider mutation is recorded;
- automatic mutation retry is false;
- provider response is content-addressed;
- durable completion is `COMPLETED` and binds the exact provider response digest;
- all authority/dispatch/runtime/effect identities are cross-checked before receipt creation;
- secret material is not part of the receipt;
- rollback state is an explicit boolean fact, not inferred;
- substituted Grant, Dispatch, Lease, Runner, target, request, response, or completion evidence fails closed.

## Versioning

- `execution-receipt/v1` remains a historical released identity used by the legacy proof model.
- `execution-receipt/v2` is a new contract for the current `ExecutionGrant/v2` / durable dispatch / governed Runner chain.
- V1 is not silently reinterpreted.

## Non-scope

F5 performs no provider mutation, no rollback, no verification provider call, no `VerificationResult`, no `OperationProof/v2`, no release, no deploy, and no production effect.

## Acceptance

- deterministic create/round-trip/digest tests;
- exact F4b mocked lineage composition;
- substitution-negative tests;
- explicit rejection of `VERIFIED` inside an ExecutionReceipt;
- VOP registry parity;
- exact-head standard CI plus existing D4b/E3/E4b regressions.
