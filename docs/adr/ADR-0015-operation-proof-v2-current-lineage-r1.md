# ADR-0015 — OperationProof/v2 current-lineage contract R1

Status: `PROPOSED`
Risk class: `R3`
Decision owner authorization: explicit `GO` in the governed F6b follow-up gate on 2026-08-19
Canonical base for this candidate: `main@2473a37f791c51a8a419a9eb88a78fdbd23a9bcd`

## Context

The repository already contains `operation-proof/v1`, but that contract binds the older
`ExecutionGrant/v1 + ExecutionReceipt/v1 + IndependentVerification/v1` lineage. The verified F6b
rollback uses the current `ExecutionReceipt/v2 + VerificationResult/v1` evidence chain. Reusing v1
would therefore either lose current lineage or falsely imply compatibility that does not exist.

`ExecutionReceipt/v2` deliberately records the bounded provider effect with
`verification_status=NOT_EVALUATED`; it must not manufacture a verification verdict. The verdict is
owned by the separately composed independent `VerificationResult/v1`.

## Decision

Add `operation-proof/v2` as a new deterministic evidence contract beside v1. Do not modify or
reinterpret v1.

R1 accepts exactly:

```text
ExecutionReceipt/v2
+ VerificationResult/v1
→ OperationProof/v2
```

The proof binds the minimum portable roots needed to identify authority, effect and independent
outcome evidence:

- execution/request/environment/capability identity,
- exact target digest,
- authorization snapshot digest,
- execution grant digest,
- execution receipt digest,
- provider operation/response summary,
- one-mutation/no-auto-retry facts,
- Runner and independent Verifier observation digests,
- observed post-state and verification-boundary digests,
- verifier identity digest,
- verification-strength digest/class,
- verification-result digest,
- receipt and verification timestamps,
- a canonical SHA-256 `proof_digest`.

## Fail-closed invariants

Creation is denied unless all are true:

1. receipt is a valid `ExecutionReceipt/v2`,
2. verification is a valid `VerificationResult/v1`,
3. execution IDs match exactly,
4. target digests match exactly,
5. the receipt still says `NOT_EVALUATED`, preserving receipt/verifier separation,
6. verification verdict is `VERIFIED`,
7. verification reason is `OBSERVED_STATE_MATCH`,
8. verification strength is `INDEPENDENT_PROVIDER_READBACK`,
9. verification does not precede receipt recording,
10. the proof records exactly one provider mutation and no automatic mutation retry,
11. deserialization recomputes and verifies the proof digest.

## Trust boundary

`OperationProof/v2` is evidence-only:

- no network I/O,
- no filesystem I/O,
- no provider credential,
- no provider mutation,
- no authorization issuance,
- no re-verification of provider state,
- no raw provider request/response bodies.

A proof is a content-addressed composition of already validated evidence. It does not create new
authority and does not substitute for the underlying receipt or verification evidence.

## Scope

Included:

- `voodoo_product/operation_proof_v2.py`,
- focused contract/regression tests,
- this ADR.

Not included:

- runtime automatic proof emission,
- reconstruction of the historical F6b proof from Actions logs,
- `OperationCell/v1`,
- release/deploy/production changes,
- provider effects,
- modification or removal of `operation-proof/v1`.

## 7×ANO gate

```text
JEDNODUCHÁ: ANO — one new pure evidence contract.
ÚČELNÁ: ANO — closes the type gap between Receipt/v2 and VerificationResult/v1.
AUTOMATIZOVANÁ: ANO — deterministic create/from_dict/to_dict plus CI tests.
BEZPEČNÁ: ANO — fail-closed, no I/O, no credentials, no authority expansion.
MĚŘITELNÁ: ANO — deterministic digest and explicit negative tests.
VRATNÁ: ANO — isolated additive module/test/ADR; rollback is branch/commit revert.
DŮKAZNĚ OVĚŘITELNÁ: ANO — exact digest bindings and CI evidence; independent R3 review remains required before merge.
```

## Verification plan

Focused:

```bash
python -m ruff check voodoo_product/operation_proof_v2.py tests/system/test_operation_proof_v2.py
python -m compileall -q voodoo_product/operation_proof_v2.py tests/system/test_operation_proof_v2.py
python -m pytest -q tests/system/test_operation_proof_v2.py
```

Then the repository's normal full CI gate must pass on the exact PR head.

## Merge gate

This ADR remains `PROPOSED` and the candidate remains unmerged until:

- exact-head CI is green,
- review threads are zero,
- independent R3 review evidence exists or the owner explicitly accepts the remaining review risk,
- no `main` drift invalidates the candidate baseline without reconciliation.

## Follow-up, explicitly separate

After this contract is accepted, a later governed slice may compose an actual `OperationProof/v2`
from retained F6b evidence. `OperationCell/v1` remains a separate proposed capability and must not be
silently created by this slice.
