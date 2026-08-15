# VOODOO One Terminology

| Field | Value |
|---|---|
| Document status | Accepted terminology |
| Scope | Product, architecture, evidence, and roadmap language |
| Rule | New public terms require documentation and compatibility review |

## Product terms

### Common language

The deterministic shared vocabulary that binds V-One member roles, operation stages, and external
technique boundaries. The source representation lives in `voodoo_product/operation_semantics.py`.
It is a semantic contract and evidence input, not runtime authorization by itself.

### Change request

A structured proposal describing intended change, target workspace, environment, risk, adapter
capability, and bounded payload.

### Workspace

The authoritative scope for a target environment and governed activity. A request cannot relabel the
workspace environment to bypass policy.

### Approval

An independent authorization decision by an eligible principal. Approval is not publisher identity,
artifact integrity, or execution success.

### Policy decision

A deterministic result explaining whether a request is allowed, denied, or awaiting conditions under
a specific policy version.

### Operation semantics

A canonical `v-one-operation-semantics/v1` value describing the operation ID, versioned capability,
required system members, ordered operation stages, verified technique roles, and deterministic
semantics digest. It prevents the product language from drifting into ambiguous agent, tool,
runner, verifier, or proof meanings.

### Operation proof

A canonical `operation-proof/v1` value binding operation semantics, authorization snapshot,
execution grant, execution receipt, and independent verification into one deterministic proof
digest. It is accepted only when exact cross-contract bindings hold and when the verifier is
independent from the actor and runner.

### Execution

One governed attempt to apply an approved capability. It has an identity, idempotency binding, lease,
fence, state, result, receipt, and audit trail.

### Production effects

External or materially consequential mutations classified as production-changing. They are disabled
until an explicit release authorizes specific capabilities.

### Emergency stop

A governed runtime state that blocks new execution and is required for explicit recovery of expired
running executions.

## Evidence terms

### Audit event

An append-only record of a material decision or action in the control plane.

### Receipt

A structured record of an execution result, chained for integrity.

### Independent verification

A separate verification claim for observed target state and postconditions. It is not produced by
the runner and is required before a successful receipt can become a verified operation proof.

### Evidence verification

A deliberate operation that checks evidence integrity. It is separate from liveness and readiness.

### Checkpoint

A preserved development-state package containing source, Git history, provenance, evidence, and
cryptographic manifests. A checkpoint is not automatically a release.

### ProofGraph

A deterministic graph of demonstrated evidence relationships. ProofGraph v1 currently represents:

- checkpoint;
- Git commit;
- source tree;
- container image identity.

### Claim

A normalized statement derived from verified evidence, with explicit scope and source.

### Warning

A visible non-fatal limitation that does not invalidate required outer evidence. A warning must never
mask missing or mismatched authoritative evidence.

### Attestation

A signed statement binding an identity to a claim. Signature support is a target capability and is not
part of ProofGraph v1.

## Execution-plane terms

### Capability

A typed, allowlisted operation with known inputs, effects, limits, verification, and rollback or
compensation properties.

### Execution grant

The pure deterministic `execution-grant/v1` value object accepted by ADR-0007. It binds one
execution to an exact artifact, target, policy, capability, expiry, nonce, and fence as a canonical
representation. Authoritative issuance, signatures, and one-time runtime consumption remain
PROPOSED.

### Authoritative grant issuance

The governed operation that emits a short-lived execution grant from approved evidence and policy.
It is separate from the pure deterministic grant representation and remains PROPOSED.

### Runner

An isolated process or service that validates a grant, executes only allowed capabilities, verifies
postconditions, and emits a structured receipt. The isolated Runner runtime is PROPOSED and is
described by ADR-0008 and the reviewed threat model, not by current runtime behavior.

### Fence

A monotonic token preventing an obsolete or late worker from committing a result after recovery or
replacement.

### Indeterminate

An outcome where execution may have produced effects but a trustworthy final result was not recorded.
It must not be silently retried.

## Integration terms

### CyberCore

A separate infrastructure context and intelligence platform. In the target model it may provide
observations, knowledge, provenance, and proposals. It does not replace VOODOO One authorization.

### V-One member

A participant in the governed operation system with exactly one explicit purpose and authority
boundary. Current common-language roles are owner, operator, AI agent, CyberCore, policy engine,
approval quorum, runner, verifier, and evidence fabric.

### Read-only intake

A versioned integration that imports metadata and evidence references without allowing mutation,
package code execution, or shared persistence.

### Provider

An adapter translating an external system into normalized observations or capabilities. Provider
behavior must not leak into the governance core without an approved contract.

### Verified technique map

The bounded mapping from external techniques to V-One technique roles. MCP is treated as tool/context
access, A2A as agent interoperability, AgentCore-style runtime telemetry as observability input,
SPIFFE-style identity as transport/workload identity, and Sigstore/in-toto/SLSA as attestation and
provenance primitives. None of these techniques alone grants V-One authorization.

## State taxonomy

### VERIFIED

Actually demonstrated within a stated scope by current evidence.

### IMPLEMENTED

Present in current source or documentation but not fully verified for every stated scope.

### PROPOSED

Approved direction or design without current implementation.

### INFERRED

Derived from available evidence but not directly demonstrated.

### UNKNOWN

Insufficient evidence is available.

### BLOCKED

Intentionally unavailable because requirements, safety controls, evidence, or authorization are
missing.

`COMPLETE` is not a VOODOO capability status.
