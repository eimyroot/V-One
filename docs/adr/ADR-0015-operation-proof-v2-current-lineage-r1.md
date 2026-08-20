# ADR-0015 — OperationProof/v2 current-lineage contract R1

Implementation status: `ACCEPTED / MERGED`
Risk class: `R3`
Original decision authorization: explicit governed `GO` on 2026-08-19
Original candidate base: `main@2473a37f791c51a8a419a9eb88a78fdbd23a9bcd`
Accepted PR: `#124`
Accepted candidate head: `29c24623e18e8f94e63e7573ceda8e74b79ce288`
Merge commit: `0f0860c556cd38c21eb5b221384f0a38058fb258`
Release/deploy authority: `NOT IMPLIED`

## Context

The repository already contained `operation-proof/v1`, bound to an older
`ExecutionGrant/v1 + ExecutionReceipt/v1 + IndependentVerification/v1` lineage. The current F6 family
uses `ExecutionReceipt/v2 + VerificationResult/v1`; silently reinterpreting v1 would lose lineage and
break auditability.

`ExecutionReceipt/v2` deliberately remains an execution claim with
`verification_status=NOT_EVALUATED`. Independent verification is a separate authority/evidence path.

The first v2 candidate accepted a standalone structurally valid VerificationResult. R3 adversarial
review identified that as insufficient provenance because a deterministic constructor can create a
self-consistent `VERIFIED` object. The accepted contract therefore requires canonical recomputation
from retained Runner/Verifier evidence before proof creation.

## Decision

`operation-proof/v2` is an additive current-lineage proof contract. Historical
`operation-proof/v1` remains reserved and must not be silently reinterpreted.

Current canonical presence lineage:

```text
ExecutionReceipt/v2
+ GitHubRefObservation/v1
+ VerifierGitHubRefObservation/v1
+ IndependentVerificationBoundary/v1
+ ObservedPostState/v1
+ VerificationStrength/v1
+ VerificationResult/v1
→ verify_github_ref_readback()
→ exact equality with supplied verification artifacts
→ OperationProof/v2
```

Rollback-absence compatibility is implemented by the separately reviewed absence composer and does
not alter the serialized `OperationProof/v2` schema.

## Proof content

The compact proof binds the minimum portable roots required to identify authority, effect and
independent outcome evidence, including execution/request/environment/capability identity, target,
authorization snapshot, execution grant, receipt, provider-effect summary, Runner/Verifier roots,
observed post-state, verification boundary/strength/result and chronology.

The retained source evidence is input to proof creation but is not duplicated into the compact proof.

## Fail-closed invariants

Creation is denied unless, for the relevant lineage:

1. the supplied receipt is valid `ExecutionReceipt/v2`;
2. retained Runner/Verifier observations and independent boundary are valid;
3. canonical verification recomputation succeeds;
4. recomputed state/strength/result exactly equal supplied artifacts;
5. execution and target identities match exactly;
6. the receipt remains `NOT_EVALUATED`;
7. the independent result is `VERIFIED / OBSERVED_STATE_MATCH`;
8. strength is `INDEPENDENT_PROVIDER_READBACK` for the accepted R1 proof path;
9. verification does not precede receipt recording;
10. effect-specific composer invariants such as mutation count/no automatic retry are preserved;
11. deserialization recomputes and verifies `proof_digest`.

A forged self-consistent `VerificationResult` that is not equal to canonical recomputation must be
rejected.

## Trust boundary

`OperationProof/v2` is evidence-only:

- no network/filesystem I/O;
- no credential access;
- no provider mutation or retry;
- no authorization issuance;
- no release or deploy authority.

It binds/revalidates retained evidence; it does not create operational authority.

## Verification / acceptance reality

The accepted PR #124 passed its required exact-head CI and D4b/E3/E4b regression gates before merge.
The contract is now present on canonical main. A later historical F6b instance was separately composed
and strictly validated with digest:

`40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718`

That instance evidence is a separate runtime/evidence fact; it is not what made this ADR accepted.

## Version lineage

```text
operation-proof/v1
SUPERSEDED_BY
operation-proof/v2
```

Supersession means current semantic lineage, not deletion of historical v1 evidence.

## Governance truth boundary

Technical merge/post-state of PR #124 is verified. Historical PR #125, which later added rollback
absence compatibility, retains separate pre-merge merge-authorization provenance as **NOT VERIFIED**.
This ADR reconciliation does not rewrite that historical governance metadata.

Repository acceptance also does not imply organizationally independent review, production release,
deployment or provider-mutation authorization beyond the separately evidenced scopes.

## Current follow-up

`OperationCell/v1` has since been accepted as a separate contract and a historical F6b cell has been
composed. The remaining product task is reconciliation and canonical ProductComposition, not another
proof format.
