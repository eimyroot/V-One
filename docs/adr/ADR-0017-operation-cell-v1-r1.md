# ADR-0017 — OperationCell/v1 stable operation atom R1

Implementation status: `ACCEPTED / MERGED`
Risk class: `R3`
Original decision authorization: explicit `GO OperationCell/v1` on 2026-08-19
Original candidate base: `main@67601a0a7bbac967433d668043851a4fe3ff2ccc`
Accepted PR: `#127`
Final reconciled candidate head: `c0bef4652cf8464c3f06c7d160c28ee7f6347ca5`
Merge commit: `71a931b561faa93c8dd2e062b83559401143b1df`
Owner review-independence risk acceptance: `YES`
Organizationally independent R3 review: `NO`
Release/deploy/provider-effect authority: `NOT IMPLIED`

## Decision

`OperationCell/v1` is the minimal stable content-addressed product atom over one canonically
revalidated `OperationProof/v2`. It is not a second proof format, does not widen authority and does
not duplicate nested evidence.

The serialized contract contains exactly 14 fields:

```text
schema_version
cell_type
execution_id
execution_epoch
request_id
environment
capability
target_digest
proof_type
operation_proof_digest
final_verdict
verification_strength_class
cell_revision
cell_digest
```

Required constants for R1:

```text
schema_version = 1
cell_type = operation-cell/v1
proof_type = operation-proof/v2
final_verdict = VERIFIED
verification_strength_class = INDEPENDENT_PROVIDER_READBACK
```

The schema is provider- and verification-lineage-neutral. It does not copy AuthorizationSnapshot,
Grant, Receipt, observation, provider or VerificationResult fields; those remain transitively
content-bound below `operation_proof_digest`.

## Trusted creation rule

The first trusted composer is rollback-absence specific:

```text
create_operation_cell_v1_from_absence(...)
```

It must:

1. receive an `OperationProofV2` plus retained rollback-absence proof inputs;
2. rerun the accepted `create_operation_proof_v2_from_absence(...)` path;
3. require exact equality between supplied proof and canonical recomputation;
4. copy only immutable indexing/proof identity claims into the cell;
5. compute `cell_digest` from canonical JSON of the 13 non-digest claims;
6. perform no I/O, provider call, credential access, authority issuance, mutation, deploy or release.

Additional lineage composers may be additive only if they preserve this exact serialized contract and
perform equally strict canonical proof provenance validation.

## Parsing versus provenance

`OperationCellV1.from_dict(...)` validates strict schema and self-integrity. Parsing a self-consistent
cell is **not** proof of provenance. Trusted composition requires a canonical lineage-specific
composer and exact proof recomputation.

## Required invariants

- exact 14-field schema;
- `cell_type == operation-cell/v1`;
- supplied proof is exact accepted `OperationProof/v2`;
- proof is canonically revalidated for its lineage;
- execution ID/epoch/request/environment/capability/target equal proof claims;
- proof verdict is `VERIFIED`;
- proof strength is `INDEPENDENT_PROVIDER_READBACK` for R1;
- nested `ExecutionReceipt/v2` remains separate from independent verification;
- `cell_digest` recomputes exactly;
- no new authority, provider I/O or effect.

## Why the cell stays small

`OperationProof/v2` already binds authorization, grant, receipt and independent verification roots.
`ExecutionReceipt/v2` transitively binds the lower execution/capsule/dispatch/lease/Runner/provider
chain. Duplicating those facts inside the cell would create a second representation capable of drift.

Therefore:

```text
VerificationResult != OperationProof
OperationProof != OperationCell
OperationCell != new authority
```

## Verification / acceptance reality

The accepted candidate passed focused conformance/adversarial tests and exact-head CI plus D4b/E3/E4b
regressions on reconciled head `c0bef4652cf8464c3f06c7d160c28ee7f6347ca5` before merge.

PR #127 was merged with expected-head protection into:

`71a931b561faa93c8dd2e062b83559401143b1df`

The owner explicitly accepted the remaining organizational review-independence risk. The prior
self/adversarial review remains correctly classified as **not organizationally independent**.

## Historical F6b instance

After contract acceptance, a separately authorized step composed the historical F6b
`OperationCell/v1` instance:

```text
cell_revision = operation-cell/f6b-live-r1
cell_digest = 2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
operation_proof_digest = 40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718
final_verdict = VERIFIED
verification_strength_class = INDEPENDENT_PROVIDER_READBACK
```

That composition performed no new provider mutation, historical replay, merge, deploy or release.

## Governance truth boundary

Historical PR #125 separate pre-merge merge-authorization provenance remains **NOT VERIFIED**. Neither
OperationProof nor OperationCell repairs or rewrites development-process governance history.

Acceptance of this ADR/contract does not authorize production effects, deploy, release or future
provider mutations.

## Current follow-up

The contract and first historical cell now exist. The current work is repository reconciliation:
canonical language, truthful UI/source-of-truth, CI/readiness coverage and one canonical
ProductComposition lifecycle before CyberCore integration.
