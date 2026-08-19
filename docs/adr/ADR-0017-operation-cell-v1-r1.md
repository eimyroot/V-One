# ADR-0017 — OperationCell/v1 stable operation atom R1

Status: `PROPOSED`
Risk class: `R3`
Decision owner authorization: explicit `GO OperationCell/v1` on 2026-08-19
Canonical base for this candidate: `main@67601a0a7bbac967433d668043851a4fe3ff2ccc`

## Decision card

```text
NÁZEV: OperationCell/v1 stable operation atom R1
UŽIVATEL: V-One evidence/audit consumers and downstream governed composition
PROBLÉM: one fully verified operation has no compact, stable, content-addressed product atom
OČEKÁVANÝ OUTCOME: OperationCell/v1 freezes immutable indexing identity over a canonically
                   revalidated OperationProof/v2 without duplicating nested evidence
RISK CLASS: R3
NEJMENŠÍ BEZPEČNÝ SLICE: minimal provider-neutral schema + explicit rollback-absence composer
ZDROJ PRAVDY: current main contracts + retained canonical F6b proof/evidence lineage + prior CASER design
DOTČENÁ DATA A OPRÁVNĚNÍ: immutable evidence identifiers/digests only; no credentials; no authority
DŮKAZ ÚSPĚCHU: exact canonical proof recomputation, 14-field schema, deterministic digest,
                negative substitution/conformance tests, exact-head CI
ROLLBACK: focused revert/removal of the additive three-file candidate
MIMO ROZSAH: provider effects, historical cell instance, merge, deploy, release, API/UI integration
OWNER DECISION: candidate/PR authorized; merge remains separately gated
```

## Context

Historical F6b has a strictly validated `OperationProof/v2`. That proof already content-binds the
important lifecycle evidence. `ExecutionReceipt/v2` transitively binds the lower execution chain.

The architectural target prepared before this implementation defines `OperationCell/v1` as the
stable product atom over that content-addressed closure:

```text
OperationCell/v1
        ↓ exact content-addressed root
OperationProof/v2
        ↓
ExecutionReceipt/v2 + independent verification roots
        ↓
authority / capsule / dispatch / lease / runner / provider evidence
```

The cell is not a second proof format. It must not widen authority and must not independently restate
mutable facts already content-bound below it.

An initial draft of this candidate copied additional proof roots and encoded rollback lineage in the
serialized cell. R3 self/adversarial review rejected that shape because it duplicated evidence and
would make `OperationCell/v1` unnecessarily lineage-specific. This ADR records the hardened minimal
contract instead.

## Decision

Add:

- `voodoo_product/operation_cell_v1.py`
- `tests/system/test_operation_cell_v1.py`
- this ADR

The serialized `operation-cell/v1` schema is provider- and verification-lineage-neutral.

The first trusted composer is explicitly lineage-specific:

```text
create_operation_cell_v1_from_absence(...)
```

It receives the retained F6b proof inputs, reruns the accepted
`create_operation_proof_v2_from_absence(...)` path, requires the supplied `OperationProof/v2` to equal
that canonical recomputation exactly, and only then freezes immutable indexing claims into the cell.

Additional lineage composers require separate review, but may remain additive as long as they preserve
this exact serialized `OperationCell/v1` contract and semantics.

## Exact serialized contract

`OperationCell/v1` contains exactly 14 fields:

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

No authorization snapshot, grant, receipt, observations, provider metadata or verification result is
copied into the cell. Those remain transitively content-bound by `operation_proof_digest`.

## Creation rule

`create_operation_cell_v1_from_absence(...)` must:

1. require an `OperationProofV2` and the retained rollback-absence proof inputs;
2. rerun `create_operation_proof_v2_from_absence(...)` using the supplied proof revision;
3. require exact equality between the supplied proof and canonical recomputation;
4. copy only `execution_id`, `execution_epoch`, `request_id`, `environment`, `capability`,
   `target_digest`, proof identity/verdict/strength and cell revision;
5. compute `cell_digest` from canonical JSON of all cell claims except `cell_digest`;
6. perform no I/O, provider call, credential access, authority issuance, mutation, deploy or release.

A merely self-consistent forged proof JSON therefore cannot be promoted to a trusted cell through the
canonical composer.

## Parsing versus provenance verification

`OperationCellV1.from_dict(...)` is a strict parser for the serialized atom. It validates:

- exact field set,
- schema/type constants,
- text/digest forms,
- execution epoch,
- VERIFIED verdict,
- independent-provider-readback strength,
- exact cell self-digest.

Parsing alone is not a provenance claim. Trusted creation or lineage verification requires a canonical
lineage-specific composer. This mirrors the core rule that content self-consistency is not equivalent
to proof provenance.

## Required invariants

- `schema_version == 1`
- `cell_type == operation-cell/v1`
- supplied proof must be exact `OperationProof/v2`
- proof must be canonically recomputed for its verification lineage
- supplied proof must exactly equal that recomputation
- cell execution ID/epoch/request/environment/capability/target exactly equal proof claims
- `proof_type == operation-proof/v2`
- `operation_proof_digest == proof.proof_digest`
- proof final verdict is `VERIFIED`
- proof strength is `INDEPENDENT_PROVIDER_READBACK` for R1
- nested `ExecutionReceipt/v2` remains `NOT_EVALUATED` and valid through canonical proof recomputation
- `cell_digest` equals SHA-256 of canonical JSON for the 13 non-digest claims
- no I/O, credentials, provider mutation or new authority

## Why the schema stays small

`OperationProof/v2` already binds:

- authorization snapshot,
- execution grant,
- execution receipt,
- Runner observation,
- Verifier observation,
- observed post-state,
- verification boundary,
- verification strength,
- verification result.

`ExecutionReceipt/v2` transitively binds:

- execution capsule,
- grant consumption,
- dispatch envelope/admission,
- execution lease,
- Runner identity/boundary,
- credential decision,
- runtime activation,
- write preflight,
- provider request/response roots.

Duplicating those claims in `OperationCell/v1` would create a second representation that can drift.
The cell therefore freezes the content-addressed closure rather than copying it.

## Required conformance / adversarial coverage

The candidate must cover:

- deterministic output and exact round trip;
- exact 14-field schema;
- proof digest binding;
- proof substitution from another execution ID;
- another execution epoch;
- another request ID;
- another environment;
- another capability;
- another target;
- self-consistent forged `VERIFIED` proof rejected by canonical recomputation;
- receipt/proof execution mismatch;
- receipt/proof target mismatch;
- chronology mismatch;
- unknown and missing cell fields;
- tampered cell digest;
- non-VERIFIED and weaker-strength serialized claims rejected;
- no duplicated nested/raw authority, verification or provider evidence.

The existing `ExecutionReceipt/v2` and `OperationProof/v2` contracts retain their own fail-closed
coverage, including `verification_status=NOT_EVALUATED`, exact mutation count and no automatic retry.

## Trust boundary

`OperationCell/v1`:

- creates no authority,
- performs no network or filesystem I/O,
- performs no provider read/write,
- accesses no credentials,
- cannot retry an effect,
- cannot execute an operation,
- cannot deploy or release,
- does not repair or rewrite development-process governance history.

It only freezes an already-proven operation into a stable content-addressed product atom.

## 7×ANO gate

```text
JEDNODUCHÁ: ANO — exact 14-field atom + one explicit first composer.
ÚČELNÁ: ANO — closes the missing Phase-H product atom over an already verified operation.
AUTOMATIZOVANÁ: ANO — deterministic proof recomputation and cell hashing.
BEZPEČNÁ: ANO — no authority/I/O; canonical proof equality blocks forged proof promotion.
MĚŘITELNÁ: ANO — exact schema, exact digests and explicit negative conformance cases.
VRATNÁ: ANO — additive three-file slice; focused revert before acceptance.
DŮKAZNĚ OVĚŘITELNÁ: ANO — canonical roots + exact-head tests/CI + R3 review gate.
```

## Verification plan

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

Then require the repository's exact-head CI plus relevant D4b/E3/E4b regression workflows.

## Scope

Included:

- minimal `OperationCell/v1` contract,
- rollback-absence trusted composer,
- focused positive/negative tests,
- ADR and candidate verification.

Not included:

- modification of `OperationProof/v2`,
- modification of the accepted absence proof composer,
- historical F6b `OperationCell/v1` instance composition,
- provider mutation or historical effect replay,
- persistence/runtime API/UI integration,
- merge,
- deploy,
- release.

## Acceptance / merge gate

This candidate remains `PROPOSED` and unmerged until:

- focused and relevant regression tests are green;
- exact-head CI is green;
- D4b/E3/E4b regressions are green;
- complete scoped diff receives R3 review;
- unresolved review threads are zero;
- a genuine independent review exists or the owner explicitly accepts remaining review-independence risk;
- fresh exact-head/main preflight passes;
- a separate explicit merge authorization is received.

## Governance truth boundary

Historical PR #125's separate pre-merge merge-authorization provenance remains `NOT VERIFIED`. This
candidate does not repair, hide or reinterpret that governance fact.

The OperationCell contract represents operation evidence. It does not manufacture development-process
authorization evidence.

## Follow-up, explicitly separate

Only after this contract candidate is accepted on canonical `main` may a separately authorized step
compose and archive the historical F6b `OperationCell/v1` instance.

The current `GO OperationCell/v1` does not authorize merge or historical cell-instance composition.
