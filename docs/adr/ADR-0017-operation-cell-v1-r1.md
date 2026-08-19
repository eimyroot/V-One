# ADR-0017 — OperationCell/v1 rollback-absence trust envelope R1

Status: `PROPOSED`
Risk class: `R3`
Decision owner authorization: explicit `GO OperationCell/v1` on 2026-08-19
Canonical base for this candidate: `main@67601a0a7bbac967433d668043851a4fe3ff2ccc`

## Decision card

```text
NÁZEV: OperationCell/v1 rollback-absence trust envelope R1
UŽIVATEL: V-One evidence/audit consumers and downstream governed composition
PROBLÉM: OperationProof/v2 is canonical evidence, but there is no compact typed cell that binds
         the operation's authorization, execution, verification and proof roots for downstream use.
OČEKÁVANÝ OUTCOME: one deterministic OperationCell/v1 can be created for historical F6b only
                   after its OperationProof/v2 provenance is freshly recomputed from retained
                   rollback-absence evidence.
RISK CLASS: R3
NEJMENŠÍ BEZPEČNÝ SLICE: one evidence-only schema/composer for rollback-absence OperationProof/v2
ZDROJ PRAVDY: current main contracts + retained canonical proof/evidence lineage
DOTČENÁ DATA A OPRÁVNĚNÍ: evidence digests only; no credentials; no new authority
DŮKAZ ÚSPĚCHU: deterministic digest, canonical proof recomputation, negative forged-proof and
                rehashed-cell substitution tests, exact-head CI
ROLLBACK: revert/remove this additive three-file slice before acceptance
MIMO ROZSAH: presence-lineage composer, provider I/O, execution, merge, deploy, release
OWNER DECISION: authorized to create candidate/PR; merge remains separately gated
```

## Context

Historical F6b now has a strictly validated `OperationProof/v2` rooted in:

```text
AuthorizationSnapshot
→ ExecutionGrant
→ ExecutionReceipt/v2
→ rollback-absence runner observation
→ independent rollback-absence verifier observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
→ OperationProof/v2
```

`OperationProof/v2` is the canonical proof of one verified operation. Downstream audit, evidence graph,
handoff and future composition need a smaller typed root that can identify the operation and its
major lifecycle evidence without carrying raw authority objects, raw provider responses, credentials,
or the entire proof payload.

A naive cell that merely accepts a standalone `OperationProofV2` object is insufficient. The current
`OperationProofV2.from_dict()` validates schema, digest and local invariants, but provenance of a
`VERIFIED` proof is established by the canonical composer and its retained verification evidence.
`OperationCell/v1` therefore must not upgrade a standalone self-consistent proof into a trusted cell.

## Decision

Add `voodoo_product/operation_cell_v1.py` with a compact `OperationCellV1` contract.

R1 supports one explicit creation path:

```text
OperationCellV1.create_from_absence(...)
```

The composer requires:

- the supplied `OperationProof/v2`,
- `ExecutionReceipt/v2`,
- `GitHubRefAbsenceObservation/v1`,
- `VerifierGitHubRefAbsenceObservation/v1`,
- `IndependentVerificationBoundary/v2`,
- `ObservedPostState/v1`,
- `VerificationStrength/v1`,
- `VerificationResult/v1`.

Before creating a cell it calls the accepted
`create_operation_proof_v2_from_absence(...)` composer using the supplied proof revision and requires
the recomputed proof to equal the supplied proof exactly.

The cell then derives all exposed operation fields from that canonically recomputed proof.

## Serialized contract

`operation-cell/v1` contains only compact, derived evidence:

```text
schema_version
cell_type
verification_lineage
operation_proof_type
operation_proof_digest
execution_id
execution_epoch
request_id
environment
capability
target_digest
authorization_snapshot_digest
execution_grant_digest
execution_receipt_digest
verification_result_digest
provider_operation
provider_mutation_count
rollback_performed
verification_strength_class
final_verdict
proof_revision
cell_revision
cell_digest
```

R1 sets:

```text
verification_lineage = rollback-absence/v1
operation_proof_type = operation-proof/v2
final_verdict = VERIFIED
```

The cell contains digests, identifiers and bounded effect metadata only. It contains no raw
authorization snapshot, grant, receipt, observation, verification result, provider request/response,
credential, token or secret.

## Provenance-safe deserialization

`OperationCellV1.from_dict(...)` does not accept serialized bytes in isolation as trusted evidence.

To deserialize a cell it requires the same canonical rollback-absence source artifacts and the
corresponding `OperationProof/v2`. It:

1. validates the exact field set, schema and self-digest,
2. recomputes the canonical absence proof from retained evidence,
3. requires exact equality with the supplied proof,
4. recomputes the expected cell from that proof,
5. requires exact equality with the serialized cell.

A rehashed cell with substituted metadata therefore remains invalid.

## Why the cell exists

The cell is not a second proof and does not add trust.

Its purpose is to provide one stable, addressable and indexable operation unit for:

- evidence graphs,
- audit navigation,
- downstream governed composition,
- compact lifecycle handoff,
- later aggregation without copying raw evidence.

The authoritative evidence remains the upstream proof and its canonical roots.

## Why rollback-absence only in R1

Historical F6b is the concrete accepted use case and its canonical lineage is rollback-absence.

R1 deliberately does not introduce a union-based generic composer or silently accept presence
evidence. A future presence/read-ref composer can be added as a separate additive path after a real
use case and its own review.

This keeps the current trust boundary explicit and prevents accidental cross-lineage substitution.

## Fail-closed invariants

Creation is denied unless:

- the supplied proof is `OperationProofV2`,
- canonical `create_operation_proof_v2_from_absence(...)` recomputation succeeds,
- the supplied proof exactly equals that recomputation,
- the proof represents exactly one bounded provider mutation,
- automatic mutation retry is already forbidden by `OperationProof/v2`,
- rollback is true,
- verification strength is `INDEPENDENT_PROVIDER_READBACK`,
- final verdict is `VERIFIED`,
- all exposed lifecycle roots are derived from the recomputed proof,
- the cell digest matches canonical JSON of all cell claims.

Deserialization additionally fails unless the serialized cell exactly equals a fresh cell recomputed
from the supplied canonical evidence.

## Trust boundary

`OperationCell/v1` is evidence-only:

- no network I/O,
- no filesystem I/O,
- no provider read,
- no provider write,
- no retry,
- no credential access,
- no authorization issuance,
- no approval semantics,
- no execution,
- no deployment,
- no release.

It cannot make an unverified operation verified and cannot authorize a new effect.

## Scope

Included:

- `voodoo_product/operation_cell_v1.py`,
- `tests/system/test_operation_cell_v1.py`,
- this ADR.

Not included:

- changing `OperationProof/v2`,
- changing the accepted absence composer,
- presence/read-ref OperationCell composer,
- historical provider re-execution,
- provider mutation,
- runtime API/UI integration,
- persistence changes,
- merge,
- deploy,
- release.

## 7×ANO gate

```text
JEDNODUCHÁ: ANO — one additive contract/composer for one proven use case.
ÚČELNÁ: ANO — creates the missing compact trust unit above an existing verified proof.
AUTOMATIZOVANÁ: ANO — deterministic proof and cell recomputation.
BEZPEČNÁ: ANO — standalone/rehashed proof or cell substitution fails closed; no I/O or authority.
MĚŘITELNÁ: ANO — exact object equality, exact digests and focused negative regression tests.
VRATNÁ: ANO — additive three-file slice; rollback is a focused revert/removal.
DŮKAZNĚ OVĚŘITELNÁ: ANO — exact-head tests/CI plus retained proof and evidence roots.
```

## Verification plan

Focused:

```bash
python -m ruff check \
  voodoo_product/operation_cell_v1.py \
  tests/system/test_operation_cell_v1.py \
  voodoo_product/operation_proof_v2.py \
  voodoo_product/operation_proof_v2_absence.py

python -m compileall -q \
  voodoo_product/operation_cell_v1.py \
  tests/system/test_operation_cell_v1.py

python -m pytest -q \
  tests/system/test_operation_cell_v1.py \
  tests/system/test_operation_proof_v2_absence.py \
  tests/system/test_operation_proof_v2.py
```

Then require the repository's normal exact-head CI and relevant D4b/E3/E4b regression workflows.

## Required adversarial cases

The candidate must prove at least:

1. deterministic creation and provenance-aware round trip,
2. exact binding of lifecycle trust roots to `OperationProof/v2`,
3. a standalone forged/rehashed `VERIFIED` proof is rejected when it does not match canonical
   rollback-absence recomputation,
4. a rehashed serialized cell with substituted metadata is rejected,
5. unknown serialized fields are rejected,
6. the cell contains no raw authority or secret material.

## Acceptance / merge gate

This candidate remains `PROPOSED` and unmerged until:

- focused tests are green,
- exact-head CI is green,
- relevant existing proof/verification workflows remain green,
- complete scoped diff is reviewed,
- review threads are zero,
- R3 independent review requirement is satisfied or the owner explicitly accepts the remaining
  review-independence risk,
- fresh head/main preflight passes,
- a separate explicit merge authorization is received.

## Governance truth boundary

The historical PR #125 merge-authorization provenance remains separate governance metadata and is
not repaired, rewritten or hidden by `OperationCell/v1`.

The cell represents operation evidence only. It does not make claims about historical development
process authorization that are not already verified.

## Follow-up, explicitly separate

If this candidate is later accepted on `main`, a separate governed step may compose and archive the
historical F6b `OperationCell/v1` instance from the retained F6b evidence and the existing
`OperationProof/v2`.

That historical cell instance is not created by this candidate and requires its own authorization.
