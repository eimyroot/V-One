# CredentialBroker READ Contract R1

Status: Phase D / D2 candidate

Base: `main@0f3a50bcc7a39c6c7e29ca5248a71d129946e0e7`

## Purpose

D2 freezes the credential-decision boundary between the released D1 `RunnerBoundary/v1` and a
future isolated SandCloud runtime adapter.

D2 does **not** deliver a credential. It only proves that one exact current Runner/lease context is
eligible for a later, out-of-band, short-lived READ-only credential delivery.

The authoritative lineage remains:

```text
AuthorizationSnapshot
  -> ExecutionGrant/v2
  -> GrantConsumptionWitness/v1
  -> DispatchOutboxEntry/v1
  -> DispatchEnvelope/v1
  -> DispatchInboxAdmission/v1
  -> durable ExecutionEpoch + ExecutionLease/v1
  -> DurableCoordinator
  -> RunnerIdentity/v1 + RunnerBoundary/v1
  -> CredentialBrokerPolicy/v1
  -> CredentialAccessDecision/v1
```

No object introduced by D2 can widen that lineage.

## Contracts

### `CredentialBrokerPolicy/v1`

An immutable broker policy keyed by the exact `credential_class` already bound into the
`ExecutionCapsule` and D1 `RunnerBoundary`.

The policy binds:

- credential class;
- credential provider;
- provider audience;
- exact allowed capability-definition identities;
- exact enabled environments;
- `access_mode = READ_ONLY`;
- `provider_mutation_allowed = false`;
- versioned policy revision and content digest.

The policy contains no secret bytes, token, credential handle, environment variable name or ambient
credential location.

### `CredentialAccessDecision/v1`

A deterministic content-addressed decision derived only from:

- exact D1 `RunnerBoundary/v1`;
- exact C4 `ExecutionLease/v1`;
- exact immutable `CredentialBrokerPolicy/v1`.

The decision binds:

- Runner identity and boundary digest;
- exact lease ID/digest;
- execution ID and current epoch;
- exact ExecutionCapsule and CapabilityDefinition identity;
- credential class;
- provider and audience;
- environment;
- `READ_ONLY` access mode;
- provider mutation disabled;
- validity window copied exactly from the C4 lease;
- exact policy digest/revision;
- deterministic decision ID and digest.

The decision is **not** a bearer credential and possession of it grants no provider access.

## Critical safety invariants

```text
S_credential_decision <= S_runner_boundary <= S_execution_lease <= S_dispatch
```

D2 additionally requires:

```text
credential.valid_from = execution_lease.acquired_at
credential.expires_at = execution_lease.expires_at
provider_mutation_allowed = false
access_mode = READ_ONLY
```

A successor C4 epoch cannot reuse an older `RunnerBoundary` to obtain a new credential decision.
The exact lease ID and lease digest must match.

A stale worker also cannot recover authority from a cached decision. D3 must re-check the durable
current C4 epoch immediately before secret exposure and before any provider call.

## Secret-handling boundary

D2 deliberately keeps all usable credential material outside canonical evidence.

Forbidden fields include, without limitation:

- token;
- secret;
- password;
- credential bytes;
- credential handle when possession of the handle would grant access;
- authorization header;
- ambient environment-variable fallback.

The later broker/runtime adapter must deliver a short-lived capability-scoped secret directly to
the isolated runtime through a non-evidence secret channel. Logs, Grant, Dispatch, RunnerIdentity,
RunnerBoundary, CredentialAccessDecision, Receipt and proof artifacts must never contain the secret.

## Broker semantics

`CredentialBroker.authorize(boundary, lease)` returns only a `CredentialAccessDecision/v1`.

The R1 `ImmutableCredentialBroker` resolves the broker policy from the exact boundary
`credential_class`; callers cannot choose a broader provider policy, capability set, environment or
access mode per request.

Fail-closed reasons include:

- unregistered credential class;
- boundary/lease mismatch;
- execution or epoch mismatch;
- unsupported credential class;
- capability definition outside the policy;
- environment outside the policy.

Repeated authorization for the same exact boundary, lease and policy is deterministic. It does not
mint a second secret or second execution authority.

## Runtime consequences

D2 introduces no network call, provider call, secret lookup, secret injection, sandbox creation,
handler execution, provider READ, provider mutation, release or deployment.

The existing D1 default remains:

```text
network_egress_default = DENY_ALL
provider_mutation_allowed = false
```

D3 may introduce a concrete isolated SandCloud runtime adapter only if it preserves these
constraints and revalidates current epoch before secret delivery.

## Verification requirements

D2 acceptance must prove:

- policy and decision strict canonical round-trip;
- READ-only and provider-mutation-disabled invariants;
- exact D1 boundary/C4 lease binding;
- successor epoch cannot reuse old boundary;
- credential class must be registered;
- capability and environment must be explicitly allowed by policy;
- repeated authorization is deterministic;
- unknown secret/token fields are rejected;
- full repository CI remains green.

## Non-goals

No actual credential bytes.
No secret broker backend.
No provider identity attestation.
No SandCloud session creation.
No network-policy allowlist activation.
No provider READ.
No provider mutation.
No production effect.
No independent verifier credential.
No Receipt/v2 or OperationProof.

## Next gate

After D2 merge and exact-main verification:

```text
D3 isolated SandCloud runtime adapter
  -> create/identify isolated runtime
  -> prove RunnerIdentity provider binding
  -> enforce exact runtime profile
  -> re-check current C4 epoch
  -> inject READ-only secret out of band
  -> keep provider mutation impossible
```

The first actual provider observation remains D4.
