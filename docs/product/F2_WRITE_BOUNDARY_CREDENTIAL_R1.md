# F2 Write Boundary + Credential Decision R1

Status: IMPLEMENTATION CANDIDATE / NO PROVIDER WRITE

Baseline: `main@68b253f9213b29308b84de435caade593608714b`

Phase: F2 — write-specific RunnerBoundary + CredentialAccessDecision

## Purpose

F2 converts the F1 controlled-write eligibility contract into a strictly bounded candidate Runner and credential-delivery boundary without performing a provider mutation.

F2 preserves every released Phase-D READ-only contract unchanged. It therefore introduces new semantic versions instead of widening the meaning of the existing v1 contracts:

```text
runner-boundary/v1                 = READ_ONLY / provider mutation false
runner-boundary/v2                 = exact F1 reversible mutation candidate

credential-broker-policy/v1       = READ_ONLY policy
credential-broker-policy/v2       = exact bounded write-delivery policy

credential-access-decision/v1     = READ_ONLY delivery decision
credential-access-decision/v2     = exact bounded write-delivery decision
```

The same canonical nouns retain one meaning; the security semantics change only through explicit contract versions.

## Canonical F2 chain

```text
ControlledWriteRequirement/v1
        +
CapabilityDefinition
        +
ExecutionCapsule/v1
        +
HandlerConformanceEvidence/v1
        +
GitHubCreateRefConditionContract/v1
        +
current ExecutionLease/v1
        +
RunnerIdentity/v1
        ↓
RunnerBoundary/v2
        ↓
CredentialBrokerPolicy/v2
        ↓
CredentialAccessDecision/v2
        ↓
WRITE-CAPABLE CANDIDATE METADATA
```

This chain does not activate a runtime and does not deliver a credential.

## `runner-boundary/v2`

The v2 boundary is content-addressed evidence that one exact Runner candidate is eligible to host the first controlled mutation design.

It binds:

- exact Runner identity and runtime profile digests;
- current C4 lease and execution epoch;
- exact ExecutionCapsule;
- exact CapabilityDefinition;
- exact F1 `ControlledWriteRequirement`;
- exact create-ref atomic provider-condition contract;
- exact verification-contract identity;
- write-specific runner class;
- write-specific credential class;
- staging-only environment;
- `mutation.reversible` effect ceiling;
- `DENY_ALL` network default;
- `provider_mutation_allowed=true` only inside this bounded v2 contract;
- exactly one provider mutation maximum;
- rollback strategy `DELETE_EXACT_CREATED_REF`.

The boundary is not an `ExecutionGrant`, credential, runtime activation, provider call, receipt or verification result.

## Write-specific Runner class

F2 narrows the candidate runner class to:

```text
github-actions.docker-isolated-write/v1
```

`RunnerIdentity/v1` can remain the descriptive identity contract because it does not itself grant authority or impose READ-only semantics. The effect ceiling belongs to the versioned `RunnerBoundary`.

F2 does not start such a Runner.

## Credential class

F2 narrows the candidate credential class to:

```text
github.create-ref/scoped-v1
```

This is a V-One credential class identifier, not secret material and not a claim that the provider can natively issue a token limited to one REST route.

A later live slice must separately prove the concrete provider credential and its effective provider permissions. No secret bytes, token handles, environment-variable names or ambient credential source are carried by the F2 decision contracts.

## `credential-broker-policy/v2`

The policy is exact rather than list-oriented. It binds one:

- credential class;
- provider `github`;
- audience `api.github.com`;
- CapabilityDefinition identity;
- F1 controlled-write requirement digest;
- atomic provider-condition contract identity;
- staging environment;
- access mode `WRITE_BOUNDED`;
- provider operation `CREATE_REF`;
- mutation maximum of one;
- maximum credential-decision TTL.

R1 limits the policy TTL to at most 300 seconds.

The repository previously had `credential-broker-policy/v1` in code but not in the canonical schema registry. F2 reserves that historical ID while adding v2 so the version lineage remains explicit. This does not alter v1 semantics.

## `credential-access-decision/v2`

The decision is authorization metadata for out-of-band delivery of one candidate write credential. It is not the credential itself.

It binds:

```text
RunnerBoundary/v2
+ current ExecutionLease/v1
+ CredentialBrokerPolicy/v2
+ exact F1 requirement
+ exact atomic provider condition
+ exact capability/capsule lineage
+ CREATE_REF
+ WRITE_BOUNDED
+ max mutations = 1
+ bounded lifetime
```

Its validity begins at the lease acquisition time and expires at the earlier of:

```text
lease.expires_at
policy.max_ttl_seconds from lease acquisition
```

The decision cannot outlive the execution lease.

## Phase-D non-regression

F2 does not edit:

```text
runner_identity.RunnerBoundary
credential_broker.CredentialBrokerPolicy
credential_broker.CredentialAccessDecision
read-only-runtime-activation/v1
```

The released v1 contracts remain:

```text
RunnerBoundary/v1.effect_ceiling            = READ_ONLY
RunnerBoundary/v1.provider_mutation_allowed = false
CredentialBrokerPolicy/v1.access_mode       = READ_ONLY
CredentialAccessDecision/v1.access_mode     = READ_ONLY
CredentialAccessDecision/v1.provider_mutation_allowed = false
```

No v1 parser accepts v2 payloads and no v2 parser reinterprets v1 payloads.

## Authority boundary

F2 creates no new authority source.

A future actual provider mutation still requires the existing chain:

```text
ReviewedOperation
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ B3 conformance
→ durable ONE_TIME Grant consumption
→ transactional outbox
→ durable inbox admission
→ current ExecutionEpoch + ExecutionLease
→ write-specific boundary/credential path
→ exact F3 handler
→ provider-native create-only effect
```

`RunnerBoundary/v2` and `CredentialAccessDecision/v2` only narrow already-authorized lineage. They do not authorize an operation that was not already authorized upstream.

## Provider-condition boundary

The first write remains exactly:

```text
github.create-ref/v1
```

with F1 semantics:

```text
CREATE_ONLY
overwrite existing ref = false
force update = false
namespace = refs/heads/vone-canary/
ATOMIC_PROVIDER_CONDITION
max provider mutations = 1
```

F2 does not add a GitHub transport and cannot call create-ref, update-ref or delete-ref.

## Network boundary

`RunnerBoundary/v2` carries `DENY_ALL` as its required network-egress default and binds the Runner identity network-policy digest to the ExecutionCapsule network-policy digest.

This is contract evidence only. F2 does not claim a live firewall or runtime activation. A future live write pilot must prove the concrete network policy independently.

## Verification boundary

F2 does not create a new verification model. The F1 verification-contract identity remains bound through the v2 Runner boundary.

After a future write, the existing independent verifier path must perform a fresh provider READ and produce the canonical:

```text
ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

Provider/Runner success cannot manufacture `VERIFIED`.

## Phase F continuation

```text
F1  ControlledWriteRequirement + create-ref condition contract      COMPLETE
 ↓
F2  write-specific RunnerBoundary + credential decision             ← this slice
 ↓
F3  exact github.create-ref/v1 target binder + handler/transport
    contract tests and negative overwrite tests only
    NO LIVE MUTATION
 ↓
F4  explicit-authorized live canary create-ref through full A→B→C→F chain
    + ExecutionReceipt/v2
 ↓
F5  independent readback + live VerificationResult
 ↓
PHASE F COMPLETE
```

F3 may define the exact write-capable runtime activation contract if required by the handler/runtime boundary. It must not silently reuse `read-only-runtime-activation/v1`.

## Acceptance

F2 is acceptable only when:

- v2 boundary round-trips canonically and is content-addressed;
- the exact F1 requirement, capsule, handler evidence and provider-condition digests are bound;
- wrong Runner class fails closed;
- non-staging or production-capable definitions fail closed;
- `READ_THEN_COMPARE` cannot enter the v2 write boundary;
- policy and decision bind the exact boundary and current lease;
- decision TTL is bounded and cannot exceed the lease;
- policy substitution fails closed;
- no token/secret/provider transport is introduced;
- v1 READ-only semantics remain unchanged;
- v1/v2 registry identities are present in one canonical VOP registry;
- full repository CI and existing D4b/E3/E4b READ/verification regressions remain green on the exact candidate head.

## Non-goals

No provider call. No GitHub write. No ref creation or deletion. No write token. No secret delivery. No runtime activation. No handler transport. No Grant issuance or consumption. No dispatch behavior change. No ExecutionReceipt/v2. No OperationProof. No release. No deploy. No production effect.
