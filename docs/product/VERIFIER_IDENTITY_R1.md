# VerifierIdentity + Independent Verification Boundary R1

## Status

Phase E / E1 contract. This slice begins only after Phase D live governed READ is merged.

E1 defines the identity and minimum independence boundary for a future verifier. It does not yet
perform an independent provider read and it does not produce a final VerificationResult or an
OperationProof.

## Purpose

The execution path may report success, but execution evidence is not sufficient proof of the
provider state. Phase E introduces a verifier that is structurally independent from the Runner and
must observe provider state through a separate READ-only path.

Canonical separation:

```text
RunnerIdentity
  != VerifierIdentity

Runner provider instance
  != Verifier provider instance

Runner credential class
  != Verifier credential class
```

The verifier may use the same underlying provider family or the same immutable runtime image. Those
facts alone neither prove nor disprove independence. Later VerificationStrength policy may classify
stronger or weaker verifier arrangements. E1 freezes only the minimum fail-closed separation needed
before any live verifier credential or provider observation can be introduced.

## `verifier-identity/v1`

`VerifierIdentity` is content-addressed descriptive evidence for one concrete verifier runtime.

It binds:

- verifier class;
- provider and concrete provider instance;
- environment;
- verifier credential class;
- rootfs digest;
- resource-limit profile digest;
- network-policy digest;
- identity revision.

It contains no token, secret, execution grant, execution lease, provider permission or operation
authority.

The logical identity uses a verifier-specific namespace (`verifier-logical-identity/v1`). It is not
reusing the Runner logical identity namespace.

## `independent-verification-boundary/v1`

`IndependentVerificationBoundary` binds one `VerifierIdentity` to one exact already-produced Runner
observation and its exact Runner boundary.

The constructor fails closed unless all of the following are true:

1. the Runner identity, Runner boundary and Runner observation bind to each other exactly;
2. verifier environment equals the execution environment;
3. verifier identity differs from Runner identity;
4. verifier provider instance differs from Runner provider instance;
5. verifier credential class differs from Runner credential class;
6. verifier effect ceiling remains `READ_ONLY`;
7. network egress default remains `DENY_ALL`;
8. provider mutation remains disabled.

The boundary records the exact Runner observation digest, execution ID, execution epoch and target
digest. A later verifier observation therefore cannot silently attach itself to unrelated execution
evidence.

## Relationship to the existing `IndependentVerification`

`voodoo_product.operation_proof.IndependentVerification` predates the live Phase-D execution path.
It is currently a proof-composition data contract that carries a `verifier_id` string and observed
digests. It is not, by itself, evidence that an authenticated independent verifier runtime existed or
that a separate credential performed a provider observation.

E1 does not delete or silently reinterpret that historical contract. A later Phase-E integration
slice must bind the final verification result to `VerifierIdentity`, the independent verification
boundary and the verifier's own observation evidence before OperationProof is allowed to treat the
verification as live independent evidence.

## Non-goals

E1 does not add:

- verifier credentials or secret delivery;
- provider calls;
- a second GitHub Actions workflow;
- ExpectedPostState or ObservedPostState;
- VerificationStrength scoring;
- final VerificationResult;
- Receipt/v2;
- OperationProof/v2;
- provider WRITE;
- release or deploy behavior.

## Phase-E continuation

The intended bounded continuation is:

```text
E1  VerifierIdentity + independence boundary
 ↓
E2  separate READ-only verifier credential path
 ↓
E3  independent provider observation
 ↓
E4  ExpectedPostState + ObservedPostState + VerificationResult/Strength
 ↓
E gate
```

The Phase-E gate remains:

```text
Runner evidence may say SUCCESS
            +
Verifier may independently say FAIL
            =
NOT VERIFIED
```

No execution-side success may manufacture a verified result.
