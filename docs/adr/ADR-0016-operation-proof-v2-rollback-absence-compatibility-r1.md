# ADR-0016 — OperationProof/v2 rollback-absence compatibility R1

Status: `PROPOSED`
Risk class: `R3`
Decision owner authorization: explicit `GO` in the governed F6b compatibility gate on 2026-08-19
Canonical base for this candidate: `main@0f0860c556cd38c21eb5b221384f0a38058fb258`

## Context

ADR-0015 introduced `OperationProof/v2` and hardened its presence/read-ref composer so that a
`VERIFIED` proof can only be created after canonical recomputation of the retained
`GitHubRefObservation/v1 + VerifierGitHubRefObservation/v1 +
IndependentVerificationBoundary/v1` chain through `verify_github_ref_readback()`.

After PR #124 was merged, the governed attempt to compose the historical F6b rollback proof found a
real compatibility gap. F6b did not use that presence/read-ref family. Its retained and already
verified evidence uses the rollback-absence family:

```text
ExecutionReceipt/v2
+ GitHubRefAbsenceObservation/v1
+ VerifierGitHubRefAbsenceObservation/v1
+ IndependentVerificationBoundary/v2
+ ObservedPostState/v1
+ VerificationStrength/v1
+ VerificationResult/v1
→ verify_github_ref_absence()
```

The F6b evidence is valid; the accepted proof composer was simply not compatible with this legitimate
lineage. Fabricating presence observations from 404/ABSENT evidence would defeat the provenance
hardening and is forbidden.

## Decision

Add a separate additive composer:

```text
create_operation_proof_v2_from_absence(...)
```

in `voodoo_product/operation_proof_v2_absence.py`.

The accepted `OperationProofV2.create()` implementation and the serialized `operation-proof/v2`
schema remain unchanged.

The absence composer must:

1. require `ExecutionReceipt/v2`,
2. require `GitHubRefAbsenceObservation/v1`,
3. require `VerifierGitHubRefAbsenceObservation/v1`,
4. require `IndependentVerificationBoundary/v2`,
5. call canonical `verify_github_ref_absence()` using the revisions retained in the supplied
   `ObservedPostState/v1`, `VerificationStrength/v1`, and `VerificationResult/v1`,
6. require exact equality between all three supplied verification artifacts and their canonical
   recomputation,
7. preserve receipt/verifier separation (`verification_status=NOT_EVALUATED`),
8. require exact execution and target binding,
9. require receipt environment to equal the rollback verification boundary environment,
10. require receipt provider operation `DELETE_REF`,
11. require `rollback_performed=true`,
12. require `VERIFIED / OBSERVED_STATE_MATCH / INDEPENDENT_PROVIDER_READBACK`,
13. require verification time not to precede receipt recording,
14. emit the existing compact `OperationProof/v2` payload through `OperationProofV2.from_dict()`,
15. perform no provider I/O or authority issuance.

## Why a separate composer

R1 deliberately does not widen `OperationProofV2.create()` to a union of unrelated runtime evidence
families.

A separate composer keeps the accepted presence path byte-for-byte unchanged and makes lineage choice
explicit at the API boundary. Cross-lineage substitution therefore fails before proof construction.

The compact proof remains schema-compatible. Its retained observation, boundary, state, strength, and
result digests identify the exact typed evidence roots used to compose it.

## Fail-closed invariants

Creation is denied unless:

- the runner observation is the rollback absence type,
- the verifier observation is the rollback absence type,
- the boundary is `IndependentVerificationBoundary/v2`,
- canonical absence recomputation succeeds,
- supplied state/strength/result exactly equal recomputed values,
- receipt and verification execution IDs match,
- receipt and verification target digests match,
- receipt environment equals the rollback verification boundary environment,
- receipt provider operation is exactly `DELETE_REF`,
- receipt records `rollback_performed=true`,
- receipt verification status remains `NOT_EVALUATED`,
- final verification is `VERIFIED`,
- reason is `OBSERVED_STATE_MATCH`,
- strength is `INDEPENDENT_PROVIDER_READBACK`,
- verification timestamp is not earlier than receipt recording,
- the resulting `OperationProof/v2` passes the existing strict schema/digest/invariant checks.

A structurally valid forged `VerificationResult/v1` is insufficient.

A `GitHubRefObservation/v1` from the presence lineage is not accepted as a rollback absence
observation.

A self/adversarial review of the first compatibility candidate also found that absence post-state
alone did not bind the semantic meaning of the receipt strongly enough. Without explicit checks, a
same-execution/same-target receipt could claim a different provider operation or environment. R1
therefore fails closed unless the receipt says `DELETE_REF`, records `rollback_performed=true`, and
matches the verification boundary environment.

## Trust boundary

This compatibility layer is evidence-only:

- no network I/O,
- no filesystem I/O,
- no provider mutation,
- no provider credential,
- no provider read,
- no authorization issuance,
- no retry of historical effects,
- no `OperationCell/v1`.

It recomputes already-retained evidence only.

## Scope

Included:

- `voodoo_product/operation_proof_v2_absence.py`,
- focused absence-lineage and cross-lineage regression tests,
- this ADR.

Not included:

- modification of the accepted presence composer,
- modification of `operation-proof/v2` serialized fields,
- historical F6b proof composition,
- `OperationCell/v1`,
- provider effects,
- deployment,
- release,
- merge.

## 7×ANO gate

```text
JEDNODUCHÁ: ANO — one companion composer; existing accepted path stays unchanged.
ÚČELNÁ: ANO — closes the observed F6b lineage compatibility blocker.
AUTOMATIZOVANÁ: ANO — deterministic canonical recomputation and proof construction.
BEZPEČNÁ: ANO — typed lineage plus delete/rollback/environment binding; no I/O or authority.
MĚŘITELNÁ: ANO — exact artifact equality, deterministic digest, focused negative tests.
VRATNÁ: ANO — three-file additive slice; rollback is revert/removal before acceptance.
DŮKAZNĚ OVĚŘITELNÁ: ANO — exact-head CI plus retained F6b evidence roots and review gate.
```

## Verification plan

Focused:

```bash
python -m ruff check \
  voodoo_product/operation_proof_v2_absence.py \
  tests/system/test_operation_proof_v2_absence.py \
  tests/system/test_operation_proof_v2.py
python -m compileall -q \
  voodoo_product/operation_proof_v2_absence.py \
  tests/system/test_operation_proof_v2_absence.py
python -m pytest -q \
  tests/system/test_operation_proof_v2_absence.py \
  tests/system/test_operation_proof_v2.py
```

Then require the repository's normal exact-head CI. Existing presence-lineage tests must remain green.

## Acceptance / merge gate

This candidate remains `PROPOSED` and unmerged until:

- exact-head CI is green,
- existing presence-lineage tests remain green,
- absence-lineage focused tests are green,
- cross-lineage substitution is proven fail-closed,
- non-delete, non-rollback, and cross-environment receipt substitution are proven fail-closed,
- review threads are zero,
- R3 review requirement is satisfied or the owner explicitly accepts remaining review-independence
  risk,
- fresh main/head preflight passes,
- a separate explicit merge authorization is received.

## Follow-up, explicitly separate

Only after this compatibility candidate is accepted may a later governed step compose the historical
F6b `OperationProof/v2` from retained evidence.

That later proof composition is not authorized by this ADR or by the `GO` that authorized this
candidate.
