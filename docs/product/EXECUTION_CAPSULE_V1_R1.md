# ExecutionCapsule/v1 R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@5efe33fe69beeb71c120766c661d5910e2481bbe`  
Phase: B2 — Execution Authority  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

B2 introduces the exact content-addressed execution contract required by the adopted V-One Thesis R2.

An `ExecutionGrant/v2` may authorize only one exact execution capsule digest and one bounded runner class.
The capsule describes what may later run. It does not execute code, acquire a credential, dispatch work,
consume a grant, mutate a provider, or prove post-state.

The B2 chain is:

```text
CapabilityDefinition
        ↓
ExecutionCapsule/v1
        ↓
CapsuleActivation
        ↓
ImmutableExecutionCapsuleRegistry
        ↓
AuthoritativeExecutionBindingAuthority
        ↓
ExecutionBinding/v1
        ↓
B1 AuthoritativeGrantIssuer
```

## 2. Contract identity

The contract type is:

```text
execution-capsule/v1
```

Its digest binds every execution-relevant claim. Changing any bound handler, artifact, rootfs,
dependency lock, SBOM, network policy, resource profile, credential class, runner class,
precondition enforcement contract, verification contract, or capsule revision creates a different
capsule digest.

## 3. Exact capsule claims

`ExecutionCapsule/v1` binds:

- capability-definition identity;
- target kind;
- handler id and handler digest;
- module-manifest digest;
- artifact kind and digest;
- rootfs/image digest;
- dependency-lock digest;
- SBOM digest;
- network-policy digest;
- resource-limit-profile digest;
- credential class;
- runner class;
- precondition enforcement class;
- verification class;
- verification-contract identity;
- capsule revision;
- capsule digest.

The capsule contains no runtime secret and no provider credential.

## 4. Capability binding

The immutable registry refuses a capsule when:

- the capability definition does not exist;
- the capsule handler id differs from `CapabilityDefinition.handler_id`;
- the target kind differs from the capability definition;
- the verification class differs from the capability definition;
- more than one capsule is registered for the same capability-definition identity.

This means a caller cannot select an arbitrary handler for an already-authorized capability.

## 5. Capsule activation

`CapsuleActivation` is distinct from the immutable capsule content.

It binds:

- capsule digest;
- activation generation;
- enabled environments;
- revoked state;
- production eligibility;
- activation digest.

The activation may only narrow the capability definition. It cannot enable an unsupported environment
or claim production eligibility when the capability definition itself is not production eligible.

## 6. Authoritative registry resolution

`ImmutableExecutionCapsuleRegistry.resolve_for_binding(...)` checks both authority layers:

```text
CapabilityDefinition
+ CapabilityActivation
+ ExecutionCapsule
+ CapsuleActivation
```

Resolution fails closed when:

- the capability activation is revoked;
- the capability is inactive in the requested environment;
- the capability does not support the environment;
- production is not capability eligible;
- the capsule is missing;
- the capsule activation is missing or revoked;
- the capsule is inactive in the environment;
- production is not capsule eligible;
- target kind differs.

## 7. Real B1 ExecutionBindingAuthority

B1 intentionally introduced only the protocol seam:

```text
ExecutionBindingAuthority
        ↓
ExecutionBinding/v1
```

B2 now supplies the first repository-owned authoritative implementation:

```text
AuthoritativeExecutionBindingAuthority
```

It does not accept a capsule digest or runner class from the caller.

Its public resolution inputs remain exactly the B1 protocol inputs:

```text
capability_definition_identity
environment
target_kind
```

The authority resolves the active immutable capsule and returns:

```text
ExecutionBinding/v1
├── capability_definition_identity
├── environment
├── target_kind
├── execution_capsule_digest
├── runner_class
├── authority_revision
└── binding_digest
```

This plugs into `AuthoritativeGrantIssuer` without modifying `ExecutionGrant/v2`.

## 8. Monotonic execution contract

B2 preserves the Thesis R2 invariant:

```text
S_capsule <= S_grant <= S_snapshot
```

At B2, the exact capsule digest is selected by a server-owned immutable registry, not a caller.

Changing execution code or environment policy does not mutate an existing capsule. It creates a new
content digest and requires a new registry/activation decision before B1 can issue a grant bound to it.

## 9. Precondition enforcement

A capsule binds one of:

```text
READ_THEN_COMPARE
ATOMIC_PROVIDER_CONDITION
```

B2 does not yet claim that this value has been proven equal to the precondition semantics carried by a
particular `ExecutionGrant/v2`.

That exact cross-contract assertion is the B3 gate:

```text
Grant
↔ Capsule
↔ runner class
↔ precondition enforcement
```

For `ATOMIC_PROVIDER_CONDITION`, later Handler/Runner conformance must prove that the provider-side
condition is actually carried into the effect.

## 10. Verification contract

Every B2 capsule requires:

- the capability definition verification class;
- a content-bound verification-contract identity.

This does not mean independent post-state verification is implemented. It prevents the execution
contract from omitting the identity of the verification contract that later phases must satisfy.

Independent verifier identity, credentials, observed post-state, verification result and OperationProof
remain later phases.

## 11. Supply-chain meaning

The digest fields are contract identities, not claims that V-One already builds or verifies all of the
artifacts.

For example:

- `artifact_digest` identifies the executable artifact expected by the contract;
- `rootfs_digest` identifies the root filesystem/image identity;
- `dependency_lock_digest` binds dependency resolution;
- `sbom_digest` binds the expected SBOM artifact;
- `network_policy_digest` binds the network policy;
- `resource_limit_profile_digest` binds the resource profile.

B2 does not invent artifact attestation or image provenance. Later conformance gates must establish
that runtime artifacts actually match these identities.

## 12. Credential boundary

`credential_class` is a class requirement only.

B2 does not:

- mint a credential;
- store a credential;
- select a concrete secret;
- authorize broader provider scope.

A future credential broker must prove:

```text
actual credential scope <= capsule credential class <= grant authority
```

## 13. Runner boundary

`runner_class` is part of the capsule digest and is copied into B1 `ExecutionBinding/v1`.

B2 does not select a concrete Runner identity.

Later dispatch/runtime phases must prove:

```text
actual runner ∈ grant.runner_class
```

and may only narrow the class.

## 14. B2 non-goals

B2 does not add:

- Grant persistence;
- JTI consumption;
- replay prevention;
- Grant ↔ Capsule runtime conformance;
- concrete Runner identity;
- credential broker;
- DispatchEnvelope;
- transactional outbox/inbox;
- lease or execution epoch;
- Handler execution;
- provider mutation;
- ExecutionReceipt/v2;
- independent verification;
- OperationProof;
- ProductService or ExecutionService wiring;
- release;
- deployment;
- production effect.

## 15. Runtime eligibility

After B2, V-One has a real content-bound capsule and real authoritative binding authority.

That still does **not** make current execution runtime eligible.

Required next gates are:

```text
B3 Grant ↔ Capsule ↔ runner-class conformance
        ↓
B4 durable grant issuance/consumption
   + JTI / ONE_TIME
   + replay prevention
   + live revocation/emergency-stop at consumption
        ↓
Phase C durable dispatch
```

## 16. Acceptance evidence

B2 is review-ready only after exact-head CI passes the repository `verify` workflow.

System evidence must demonstrate at minimum:

- exact capsule serialization round trip;
- tamper and unknown-field rejection;
- handler binding to capability definition;
- target-kind binding;
- verification-class binding;
- capability production scope cannot be widened by capsule activation;
- exact active capsule → B1 ExecutionBinding;
- revoked capsule denial;
- revoked capability denial;
- environment mismatch denial;
- target mismatch denial;
- production eligibility denial;
- any execution-relevant content change produces a different capsule digest;
- no current ProductService/ExecutionService wiring.

CI success does not authorize merge, runtime adoption, release, deployment or provider effects.
