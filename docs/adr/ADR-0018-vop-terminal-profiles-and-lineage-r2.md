# ADR-0018 — VOP terminal profiles and schema lineage reconciliation R2

Status: `PROPOSED_FOR_RECONCILIATION_ACCEPTANCE`
Risk class: `R3`
Date: `2026-08-20`
Input audit: `VONE_RECONCILIATION_AUDIT_20260819T2209Z`
Candidate: PR #128 / `feat/reconciliation-p0-p1-r1`

## Context

ADR-0014 froze the canonical VOP vocabulary before the current write/rollback evidence contracts were
fully reconciled into the product truth layer. Later contracts added `execution-receipt/v2`,
`operation-proof/v2` and `operation-cell/v1`.

A first reconciliation pass incorrectly represented `execution-receipt/v2` and `operation-proof/v2`
as universal semantic supersessions of their v1 families and visually implied one mandatory lifecycle
ending at `OperationCell/v1` for every capability.

The accepted source contracts prove that this is too strong:

- `ExecutionReceipt/v2` requires exactly one bounded provider mutation, no automatic mutation retry,
  and keeps verification `NOT_EVALUATED`;
- `OperationProof/v2` requires exactly one bounded provider mutation plus canonical independent
  provider readback;
- `OperationCell/v1` requires canonically revalidated `OperationProof/v2`;
- current READ-only verification can be independently `VERIFIED` through
  `VerificationResult/v1` without satisfying the mutation-only receipt/proof/cell contracts.

Presenting the specialized v2 contracts as universal replacements would violate the canonical rule:

> Stejný VOP termín musí mít napříč kódem, docs, receipts, API a UI jeden význam. Změna významu
> vyžaduje nový termín nebo novou verzi.

## Decision

Advance the semantic revision to:

```text
vop-terminology-freeze-r2
```

Keep `vop-canonical-vocabulary/v1` and `vop-schema-registry/v1` as container/schema identities; the
semantic revision carried inside them changes to R2.

### 1. Operation stages are an ordered superset

`OPERATION_STAGES` is not a claim that every operation traverses every stage. It is the ordered
superset of canonical lifecycle concepts. A concrete lineage uses only the stages required by its
registered terminal profile.

### 2. Register terminal profiles

```text
READ_ONLY_VERIFIED
  independent_verification
  → verification_result

BOUNDED_MUTATION_VERIFIED
  execution_receipt
  → independent_verification
  → verification_result
  → operation_proof
  → operation_cell
```

The shared authority/dispatch/execution prefix remains common. Terminal evidence is capability/profile
specific.

### 3. Restrict true supersession to true semantic replacement

Keep:

```text
execution-grant/v1
SUPERSEDED_BY
execution-grant/v2
```

Remove universal supersession claims for:

```text
execution-receipt/v1 → execution-receipt/v2
operation-proof/v1   → operation-proof/v2
```

Instead record explicit compatibility classifications:

- v1 receipt = legacy generic v1 receipt lineage;
- v2 receipt = current bounded-mutation effect receipt, not universal replacement;
- v1 proof = legacy generic v1 proof lineage;
- v2 proof = current bounded-mutation proof, not universal replacement;
- `VerificationResult/v1` = current verified READ-only terminal;
- `OperationCell/v1` = current bounded-mutation stable atom requiring `OperationProof/v2`.

## Invariants

1. Receipt existence or receipt-chain integrity never implies independent `VERIFIED`.
2. Runner never issues or consumes ExecutionGrant.
3. READ-only verification does not require mutation-only receipt/proof/cell contracts.
4. `ExecutionReceipt/v2` must not be widened to allow zero-mutation READ just to make one universal
   diagram work.
5. `OperationProof/v2` must not be widened to generic READ without a separate reviewed contract
   decision.
6. `OperationCell/v1` must not accept a proof lineage it cannot canonically revalidate.
7. Historical v1 evidence remains parseable/auditable according to its own contract.
8. Registry `SUPERSEDES` means real semantic replacement, not merely “newer file exists”.

## Why this is safer than generalizing v2

Generalizing `ExecutionReceipt/v2` or `OperationProof/v2` would erase safety properties that are
currently explicit and tested: exact one-mutation accounting, no automatic mutation retry, and
bounded-write evidence semantics. R2 instead models the real type distinction and lets future proof
profiles be introduced explicitly if needed.

## Product composition consequence

The canonical product orchestration must compose one shared authority/execution prefix and then choose
an explicitly registered evidence terminal profile. It must not implement a hard-coded universal
`VerificationResult → OperationProof/v2 → OperationCell/v1` tail.

## Scope

Included:

- VOP machine vocabulary revision R2;
- schema registry compatibility/terminal metadata;
- terminology and architecture projection;
- CI regression coverage;
- downstream source-of-truth reconciliation.

Not included:

- provider mutation;
- release/deploy;
- changing the accepted binary fields/invariants of Receipt/v2, Proof/v2 or Cell/v1;
- CyberCore integration;
- merge authorization.

## Acceptance gates

- exact-head lint/compile/tests PASS;
- VOP registry and terminology gates PASS;
- Product readiness gate understands R2 terminal profiles;
- top-level product docs stop claiming a universal proof/cell tail;
- no source contract is weakened merely to fit the diagram;
- R3 review and separate merge authorization remain required.
