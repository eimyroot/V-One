# E3 — Independent Live Verifier Observation R1

Status: `IMPLEMENTED_CANDIDATE`

## Purpose

E3 proves that V-One can perform a second live provider READ through a Verifier path that is
independent from the Runner path already proven in D4b.

E3 produces an **Observation**. It does not yet produce `ObservedPostState`,
`VerificationResult`, attestation or `OperationProof`.

## Canonical VOP position

```text
Runner
  -> github-ref-observation/v1
  -> VerifierIdentity/v1
  -> IndependentVerificationBoundary/v1
  -> VerifierCredentialDecision/v1
  -> verifier-github-ref-observation/v1

E3 STOPS HERE.
```

The next Phase-E slice may compare governed expected/observed state and produce a
`VerificationResult`. E3 itself MUST NOT use a successful second READ as shorthand for
`VERIFIED`.

## Independence invariants

The live boundary requires:

```text
RunnerIdentity != VerifierIdentity
Runner provider instance != Verifier provider instance
Runner credential class != Verifier credential class
Runner observation != Verifier observation
```

The current live GitHub pilot uses two separate GitHub Actions jobs and two separate hardened
Docker runtime instances. Both jobs receive only READ repository permissions. The Verifier uses
canonical credential class:

```text
github.actions-token.verifier-read/v1
```

No V-One evidence object contains token bytes, a secret handle or an environment-variable name.

## Provider effect ceiling

E3 remains:

```text
READ_ONLY
provider_mutation_allowed = false
network_egress_default = DENY_ALL
```

Each Docker cell is read-only, capability-dropped, no-new-privileges, resource-bounded and
network-denied by default. The only explicit egress allowance is HTTPS to the resolved
`api.github.com` address, and each job contains a negative arbitrary-egress test.

## Exact binding

`verifier-github-ref-observation/v1` binds:

- exact `Target` digest;
- exact `VerifierIdentity`;
- exact `IndependentVerificationBoundary`;
- exact `VerifierCredentialDecision`;
- exact prior Runner observation digest;
- exact execution id and execution epoch;
- Verifier provider instance;
- provider source identity;
- trusted-clock evidence immediately before credential use;
- trusted-clock evidence for the resulting observation.

A target substitution, identity substitution, boundary substitution, decision substitution,
expired verifier credential, environment mismatch or mutation allowance fails closed before the
provider READ.

## Runner evidence handoff

The Runner job emits only the sanitized D4b result JSON already produced by
`d4b-live-governed-read/v1`. E3 transfers that evidence to the Verifier job as base64-encoded job
output. The encoding is transport only and adds no authority.

The Verifier rehydrates and validates the exact Runner identity and boundary from the D4b runtime,
lease, credential-decision and observation evidence before constructing the independent boundary.

## Non-goals

E3 does not:

- compare Runner and Verifier observations into a verification verdict;
- construct `ExpectedPostState` or `ObservedPostState`;
- produce `VerificationResult` or `VerificationStrength`;
- produce an attestation or `OperationProof`;
- mutate GitHub or any provider;
- release, deploy or modify production.

## Acceptance gate

E3 is accepted only when the same exact PR head has:

1. repository `verify` = SUCCESS;
2. D4b live READ regression = SUCCESS;
3. E3 live independent verifier observation = SUCCESS;
4. zero unresolved review threads;
5. no provider mutation evidence.

Passing E3 authorizes no Phase-F WRITE capability.
