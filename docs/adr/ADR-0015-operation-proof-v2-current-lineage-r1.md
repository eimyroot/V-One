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
`verification_status=NOT_EVALUATED`; it must not manufacture a verification verdict.

An adversarial R3 review of the first candidate found a material trust-boundary gap:
`VerificationResult.create()` is a public deterministic constructor. Accepting a
`VerificationResult/v1` object by type and verdict alone therefore does not prove that the verdict
was derived through the independent Runner/Verifier readback pipeline.

## Decision

Add `operation-proof/v2` as a new deterministic evidence contract beside v1. Do not modify or
reinterpret v1.

R1 accepts the complete retained evidence chain:

```text
ExecutionReceipt/v2
+ GitHubRefObservation/v1
+ VerifierGitHubRefObservation/v1
+ IndependentVerificationBoundary/v1
+ ObservedPostState/v1
+ VerificationStrength/v1
+ VerificationResult/v1
→ deterministic verification-chain recomputation
→ OperationProof/v2
```

`OperationProofV2.create()` must call the canonical `verify_github_ref_readback()` function over the
retained Runner observation, Verifier observation, and independent boundary, using the revisions
carried by the retained state/strength/result artifacts. Creation is denied unless the recomputed
`ObservedPostState`, `VerificationStrength`, and `VerificationResult` exactly equal the supplied
artifacts.

This closes the first-candidate `VERIFIED-by-construction` gap without provider I/O and without
creating a second verification algorithm.

## Proof content

The compact proof binds the minimum portable roots needed to identify authority, effect and
independent outcome evidence:

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

The full retained evidence objects are inputs to proof creation but are not embedded in the compact
proof payload.

## Fail-closed invariants

Creation is denied unless all are true:

1. receipt is a valid `ExecutionReceipt/v2`,
2. Runner observation is a valid `GitHubRefObservation/v1`,
3. Verifier observation is a valid `VerifierGitHubRefObservation/v1`,
4. boundary is a valid `IndependentVerificationBoundary/v1`,
5. supplied `ObservedPostState/v1`, `VerificationStrength/v1`, and `VerificationResult/v1` exactly
   equal the canonical recomputation from that evidence chain,
6. execution IDs match exactly between receipt and recomputed verification,
7. target digests match exactly,
8. the receipt still says `NOT_EVALUATED`, preserving receipt/verifier separation,
9. recomputed verification verdict is `VERIFIED`,
10. recomputed verification reason is `OBSERVED_STATE_MATCH`,
11. verification strength is `INDEPENDENT_PROVIDER_READBACK`,
12. verification does not precede receipt recording,
13. the receipt records exactly one provider mutation and no automatic mutation retry,
14. deserialization recomputes and verifies the proof digest.

A forged `VerificationResult.create(... verdict="VERIFIED" ...)` that is not equal to the canonical
recomputation from retained read-only evidence must be rejected.

## Trust boundary

`OperationProof/v2` is evidence-only:

- no network I/O,
- no filesystem I/O,
- no provider credential,
- no provider mutation,
- no authorization issuance,
- no new provider read,
- no raw provider request/response bodies.

The proof recomputes the deterministic verification artifacts from already-retained read-only
observations. It does not call the provider and does not create new authority.

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
- modification or removal of `operation-proof/v1`,
- changing `VerificationResult/v1` itself.

## 7×ANO gate

```text
JEDNODUCHÁ: ANO — one additive pure evidence contract using the existing canonical verifier.
ÚČELNÁ: ANO — closes the type/provenance gap between Receipt/v2 and VerificationResult/v1.
AUTOMATIZOVANÁ: ANO — deterministic create/from_dict/to_dict and canonical chain recomputation.
BEZPEČNÁ: ANO — fail-closed, no I/O, no credentials, no authority expansion.
MĚŘITELNÁ: ANO — exact artifact equality, deterministic digest and negative forgery tests.
VRATNÁ: ANO — isolated additive module/test/ADR; rollback is branch/commit revert.
DŮKAZNĚ OVĚŘITELNÁ: ANO — exact digest bindings plus exact-head CI; organizationally independent
R3 review remains a separate requirement unless the owner explicitly accepts that remaining risk.
```

## Verification plan

Focused:

```bash
python -m ruff check voodoo_product/operation_proof_v2.py tests/system/test_operation_proof_v2.py
python -m compileall -q voodoo_product/operation_proof_v2.py tests/system/test_operation_proof_v2.py
python -m pytest -q tests/system/test_operation_proof_v2.py
```

Then the repository's normal full CI gate and current-head D4b/E3/E4b regression workflows must pass
again on the exact updated PR head.

## Review finding closure

First candidate head: `07b110eb90172fbe8325c5a48c6d65c5be16ee28`.

Finding:

```text
R3-BLOCKER:
OperationProofV2.create() accepted a standalone VerificationResult/v1.
VerificationResult.create() can construct a structurally valid VERIFIED result from supplied digests.
Therefore proof creation did not itself establish provenance through the canonical independent
readback pipeline.
```

Required closure:

```text
OperationProofV2.create()
→ require retained Runner/Verifier/boundary/state/strength/result evidence
→ recompute via verify_github_ref_readback()
→ require exact equality of recomputed state/strength/result
→ only then permit VERIFIED OperationProof/v2
```

## Merge gate

This ADR remains `PROPOSED` and the candidate remains unmerged until:

- the updated exact-head CI is green,
- updated D4b/E3/E4b regression workflows are green,
- review threads are zero,
- this R3 blocker is proven closed by tests,
- organizationally independent R3 review exists or the owner explicitly accepts the remaining
  independence risk,
- no `main` drift invalidates the candidate baseline without reconciliation,
- a separate explicit merge authorization is received.

## Follow-up, explicitly separate

After this contract is accepted, a later governed slice may compose an actual `OperationProof/v2`
from retained F6b evidence. `OperationCell/v1` remains a separate proposed capability and must not be
silently created by this slice.
