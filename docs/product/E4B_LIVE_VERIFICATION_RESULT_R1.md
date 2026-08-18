# E4b — Live VerificationResult R1

Status: PROPOSED / READ_ONLY pilot slice

## Purpose

E4b is the first live exercise of the canonical E4 contracts over real provider observations.
It proves that V-One can take:

1. a real governed Runner observation,
2. a real independent Verifier observation produced under a separate runtime identity, provider instance and credential class,
3. the exact IndependentVerificationBoundary binding those observations,

and deterministically derive:

- `ObservedPostState/v1`,
- `VerificationStrength/v1`,
- `VerificationResult/v1`.

E4b does not add a new provider capability or a new authority primitive.

## Critical semantic boundary

```text
Runner execution / observation
!=
Verifier observation
!=
VerificationResult
```

The provider READs happen before E4b evaluation. The E4b evaluator itself performs no provider call and receives no provider credential.

## Live flow

```text
GitHub Actions job A
  ↓
hardened isolated Runner
  ↓
D4b governed READ of exact Git ref
  ↓
GitHubRefObservation

GitHub Actions job B
  ↓
separate hardened isolated Verifier
  ↓
separate READ-only verifier credential path
  ↓
independent Git ref READ
  ↓
VerifierGitHubRefObservation
  ↓
E4b evaluator (no provider credential)
  ↓
ObservedPostState/v1
  +
VerificationStrength/v1
  +
VerificationResult/v1
```

## Positive live gate

The workflow acceptance marker is:

```text
E4B_LIVE_VERIFICATION_RESULT=VERIFIED
```

A positive result requires all canonical E4 binding checks to pass and the independently observed Git object ID to match the Runner observation.

The expected strength is:

```text
INDEPENDENT_PROVIDER_READBACK
SEQUENTIAL_READBACK_NON_ATOMIC
```

The readback is deliberately described as non-atomic because the target is a mutable Git ref and Runner and Verifier observe it sequentially.

## NOT_VERIFIED semantics

If the independent Verifier sees a different Git object ID for the same exact ref, E4 creates:

```text
verdict = NOT_VERIFIED
reason  = OBSERVED_STATE_MISMATCH
```

That does not by itself prove Runner fault. The ref may have legitimately changed between the two sequential reads.

For the E4b positive acceptance gate, a `NOT_VERIFIED` result causes the workflow to fail rather than silently relabel the operation as verified.

## Runtime isolation

Both provider-reading jobs preserve the established D3/D4/E3 runtime constraints:

- GitHub-hosted Ubuntu execution host;
- hardened Docker cell;
- read-only root filesystem;
- bounded tmpfs;
- memory / CPU / PID ceilings;
- all Linux capabilities dropped;
- `no-new-privileges`;
- network default DENY;
- explicit TCP/443 allow only to the resolved `api.github.com` address;
- negative arbitrary-egress proof;
- `contents: read` workflow permission;
- checkout credentials are not persisted.

The E4b evaluator is invoked in the Verifier cell without passing `GITHUB_TOKEN` or any other provider credential.

## Non-scope

E4b does not implement:

- provider mutation;
- ExecutionGrant issuance or consumption;
- new dispatch semantics;
- ExecutionReceipt replacement;
- atomic provider readback;
- attestation;
- `OperationProof`;
- DSSE or Sigstore;
- release;
- deploy;
- production activation.

Phase E remains READ_ONLY.

## Acceptance evidence

A candidate E4b head is acceptable only when the exact same head has:

- standard CI = SUCCESS;
- existing D4b live governed READ regression = SUCCESS;
- existing E3 independent verifier observation regression = SUCCESS;
- E4b live VerificationResult workflow = SUCCESS;
- zero unresolved review threads.

Workflow success is evidence that one live E4b run produced `VerificationResult.verdict = VERIFIED`; it is not yet an `OperationProof`.
