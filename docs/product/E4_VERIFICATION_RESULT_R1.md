# E4 — ObservedPostState + VerificationStrength + VerificationResult R1

| Field | Value |
|---|---|
| Status | IMPLEMENTED CANDIDATE |
| Phase | E — Independent Verification |
| Effect ceiling | `READ_ONLY` |
| Provider mutation | `false` |
| Contracts | `observed-post-state/v1`, `verification-strength/v1`, `verification-result/v1` |
| Implementation | `voodoo_product/verification_result.py` |

## Purpose

E4 converts already-produced Runner and independent Verifier observations into the first canonical
VOP `VerificationResult`.

The sequence is:

```text
GitHubRefObservation
        +
IndependentVerificationBoundary
        +
VerifierGitHubRefObservation
        |
        v
ObservedPostState
        +
VerificationStrength
        |
        v
VerificationResult
```

E4 performs no provider call. The provider READ belongs to E3. E4 is a pure fail-closed
verification step over content-addressed evidence.

## Canonical non-conflation

```text
Observation != ObservedPostState
Observation != VerificationResult
ExecutionReceipt != VerificationResult
VerificationResult != OperationProof
```

A Runner observation alone is never `VERIFIED`. An E3 Verifier observation alone is also not a
`VerificationResult`.

## ObservedPostState/v1

`ObservedPostState` is the independent state projection derived from the Verifier observation.

For the E4 Git-ref profile:

```text
state_kind = git_ref
state_claims.repository
state_claims.ref
state_claims.commit_sha
```

The artifact also binds the exact execution, epoch, target, verifier identity, independent
verification boundary, verifier observation, provider instance, source identity, observation time
and content digest.

It contains no provider token, Grant, lease or authorization material.

## VerificationStrength/v1

E4 R1 emits exactly:

```text
strength_class = INDEPENDENT_PROVIDER_READBACK
independence_class = SEPARATE_IDENTITY_INSTANCE_CREDENTIAL
temporal_model = SEQUENTIAL_READBACK_NON_ATOMIC

target_binding_exact = true
identity_separation = true
provider_instance_separation = true
credential_separation = true
provider_readback = true
atomic_readback = false

effect_ceiling = READ_ONLY
provider_mutation_allowed = false
```

`atomic_readback = false` is normative. The Runner and Verifier READs are sequential, not one
provider-atomic snapshot.

## VerificationResult/v1

The R1 verdict set produced by the Git-ref verifier is:

```text
VERIFIED
NOT_VERIFIED
```

A result is `VERIFIED` only when all fail-closed evidence bindings pass and the independent Verifier
observes the same exact Git object ID for the same repository/ref target as the Runner observation.

```text
Runner commit == Verifier commit
=> VERIFIED / OBSERVED_STATE_MATCH
```

When all bindings are valid but the independently observed Git object ID differs:

```text
Runner commit != Verifier commit
=> NOT_VERIFIED / OBSERVED_STATE_MISMATCH
```

Because the readback is sequential and the target may be mutable, `NOT_VERIFIED` means **the Runner
observation was not independently corroborated at Verifier observation time**. It does not by
itself prove that the Runner lied or malfunctioned; the ref may have legitimately changed between
the two READs.

## Fail-closed conditions

No `VerificationResult` is manufactured when evidence is not eligible for comparison. E4 denies
before result construction when, among other things:

- the Runner observation does not match the independent verification boundary;
- the Verifier observation does not bind the exact Runner observation;
- execution ID, ExecutionEpoch or target digest differs;
- Verifier identity/provider instance does not match the independent boundary;
- repository/ref target claims differ;
- the Verifier observation predates the Runner observation.

Missing or substituted evidence is therefore not silently converted into `NOT_VERIFIED`.

## Time semantics

The E4 `checked_at` value is the independent Verifier observation time.

For `VERIFIED`, the precise meaning is:

> the exact Runner-observed Git ref value was independently corroborated by a separate Verifier
> path at the recorded Verifier observation time under the declared non-atomic readback strength.

This is deliberately narrower than an atomic provider transaction witness.

## Relationship to legacy proof code

`voodoo_product/operation_proof.py` contains a historical `independent-verification/v1` value
contract. E4 does not silently reinterpret that contract as `verification-result/v1`.

Any migration, supersession or OperationProof integration belongs to a later explicit proof-layer
slice.

## Non-scope

E4 R1 does not:

- call or mutate a provider;
- issue or consume an ExecutionGrant;
- create an ExecutionReceipt;
- attest or sign evidence;
- construct `OperationProof`;
- release, deploy or perform a production effect.

Phase E therefore remains `READ_ONLY`.
