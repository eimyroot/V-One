# ADR-0012: Verifiable Operations Trust Plane

Status: Proposed for adoption
Date: 2026-08-16
Scope: V-One architecture and implementation roadmap

## Context

V-One has already merged the immutable Authorization Snapshot persistence foundation. The next work must avoid two failure modes:

1. building runtime execution before authority inputs are real and transactionally coherent;
2. letting external agent, tool, protocol, or provider terminology leak into the security kernel.

Competitive research across agent governance platforms, durable workflow engines, workload identity systems, credential brokers, policy systems, and supply-chain attestation systems confirms that identity, policy, gateway, runtime isolation, and observability are necessary but not sufficient differentiators.

V-One's useful position is provider-neutral proof-carrying operations.

## Decision

Adopt the following target architecture direction:

```text
V-ONE
=
CANONICAL OPERATION LANGUAGE
+
SMALL IMMUTABLE TRUST KERNEL
+
VERSIONED OPERATION SEMANTICS
+
MASSIVELY SCALABLE CAPABILITY CATALOG
+
CONFORMANCE-TESTED MODULE ECOSYSTEM
+
DISTRIBUTED EXECUTION FABRIC
+
INDEPENDENT VERIFICATION
+
PORTABLE PROOF
```

Adopt these architectural primitives as target contracts:

- Canonical VOP vocabulary;
- Monotonic Authority;
- AuthorityWitnessSet;
- ExecutionCapsule;
- Dispatch Inbox / Dedup / Epoch Fence;
- RunnerIdentity separate from VerifierIdentity;
- VerificationStrength;
- CredentialBroker boundary;
- OperationProof based on standard attestation direction;
- CyberCore as adaptive proposal plane, not authority plane.

## Key invariants

```text
AI may propose.
AI may not manufacture authority.
```

```text
AuthorizationSnapshot = immutable authorization evidence.
ExecutionGrant = narrow execution permission.
ExecutionReceipt = execution subsystem claim.
VerificationResult = independent post-state finding.
```

```text
APPROVE != AUTHORIZE
AUTHORIZE != ISSUE
ISSUE != EXECUTE
EXECUTE != VERIFY
VERIFY != RELEASE
RELEASE != DEPLOY
```

```text
Every downstream layer may only narrow, expire, revoke, deny, or preserve authority.
No downstream layer may widen authority.
```

## Implementation strategy

Do not perform a big-bang rewrite.

Implement as reversible, evidence-backed slices:

1. Truth and repository governance;
2. Authority kernel completeness;
3. AuthoritativeSnapshotCreator;
4. Grant / execution contract;
5. Durable dispatch with inbox and epoch fencing;
6. READ-ONLY isolated Runner;
7. Independent verification;
8. OperationProof;
9. OperationCell/v1 freeze;
10. Bounded Operation Graph;
11. Module ecosystem;
12. CyberCore observation and semantic equivalence.

## Consequences

Positive:

- improves proof portability;
- prevents provider and agent frameworks from becoming implicit authority;
- creates a stable semantic language for UI, API, audit, evidence, proof, and AI planning;
- keeps current modular monolith path while preserving future extraction options;
- makes Runner/Verifier separation explicit before real provider mutations exist.

Costs:

- more contracts before first real execution;
- strict vocabulary discipline;
- additional negative tests;
- more explicit registries and identity bindings.

Rejected alternatives:

- immediate Temporal/Restate rewrite;
- generic shell as core capability;
- provider SDK imports in the kernel;
- LLM-based ALLOW;
- receipt treated as verification;
- auto-activation of CyberCore-generated candidates;
- microservices-first architecture.

## Non-goals

This ADR does not implement:

- Snapshot Creator;
- Grant Issuer;
- Runner;
- provider mutation;
- production execution;
- deploy/release flow.

Those require separate scoped implementation PRs and evidence gates.
