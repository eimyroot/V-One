# Verifier READ Credential Path R1

Status: **Phase E / E2 candidate**

## Purpose

E2 introduces a credential path for the independent verifier that is structurally separate from the Runner credential path established in Phase D.

The verifier credential path does **not** authorize execution and does **not** contain secret material. It produces only content-addressed metadata describing whether a separate READ-only verifier credential may be delivered out of band.

## Invariants

- `VerifierIdentity != RunnerIdentity` remains enforced by E1.
- `verifier_credential_class != runner_credential_class`.
- access mode is exactly `READ_ONLY`.
- `provider_mutation_allowed = false`.
- policy chooses provider/audience/environment and maximum TTL; the caller cannot widen them.
- decision binds the exact `IndependentVerificationBoundary`, runner observation, target, execution id and execution epoch.
- serializable policy/decision objects contain no token, secret, secret handle or ambient credential location.
- verifier credential validity is independent of the Runner execution lease. Verification may occur after Runner completion, but remains short-lived under verifier policy.

## Contracts

### `verifier-credential-policy/v1`

Immutable broker-side narrowing policy:

- verifier credential class
- provider
- audience
- enabled environments
- READ_ONLY access mode
- provider mutation disabled
- maximum credential TTL
- policy revision/digest

### `verifier-credential-decision/v1`

Content-addressed metadata binding:

- exact VerifierIdentity
- exact IndependentVerificationBoundary
- exact runner observation digest
- exact target digest
- exact execution/epoch
- exact credential class/provider/audience/environment
- short validity window
- exact policy digest/revision

The decision is not a credential.

## Explicit non-goals

E2 does not:

- obtain or expose a real GitHub token;
- perform a GitHub API call;
- create the independent verifier runtime;
- create an independent provider observation;
- compare ExpectedPostState and ObservedPostState;
- emit final VerificationResult or VerificationStrength;
- create OperationProof;
- permit provider mutation, release or deploy.

## Next

`E3 independent live provider observation` must use a separate verifier runtime instance and a separately delivered READ-only credential consistent with this decision. E4 will then bind ExpectedPostState, ObservedPostState, VerificationStrength and final VerificationResult.
