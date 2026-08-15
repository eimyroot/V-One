# VOODOO One Terminology

| Field | Value |
|---|---|
| Document status | Accepted terminology |
| Scope | Product, architecture, evidence, and roadmap language |
| Rule | New public terms require documentation and compatibility review |
| VOP authority | `docs/architecture/VOP_CANONICAL_VOCABULARY.md` + `voodoo_product/vop_vocabulary.py` |

## Canonical-language boundary

The authoritative operation-language vocabulary is VOP Canonical Vocabulary. One semantic meaning
must have one canonical term, one contract identity, and one authoritative definition. This file may
explain broader product/foundation terms, but it must not redefine VOP nouns, verbs, relations,
identity grammar, or shared CORE status language in parallel.

Machine-readable VOP vocabulary lives in `voodoo_product/vop_vocabulary.py`. Reserved canonical
schema identities live in `schemas/vop/registry.v1.json`. Existing operation semantics consume the
shared VOP operation-stage sequence instead of defining another copy.

## Product terms

### Common language

The deterministic shared semantic vocabulary that binds V-One operation language, member roles,
operation stages, and external technique boundaries. Canonical operation-language ownership lives in
`voodoo_product/vop_vocabulary.py`; `voodoo_product/operation_semantics.py` consumes that vocabulary
for operation semantics. The vocabulary is a semantic contract and evidence input, not runtime
authorization by itself.

### Change request

A structured proposal describing intended change, target workspace, environment, risk, adapter
capability, and bounded payload.

### Workspace

The authoritative scope for a target environment and governed activity. A request cannot relabel the
workspace environment to bypass policy.

### Approval

Human or system approval of exact reviewed content under the applicable approval rules. Approval is
evidence used by authorization; it is not itself Authorization, an ExecutionGrant, publisher
identity, artifact integrity, execution success, or verification success.

### Policy decision

A deterministic result explaining whether a request is allowed, denied, or awaiting conditions under
a specific policy version. A policy decision is one authority input; it does not by itself create an
ExecutionGrant.

### Operation semantics

A canonical `v-one-operation-semantics/v1` value describing the operation ID, versioned capability,
required system members, the shared VOP operation stages, verified technique roles, and deterministic
semantics digest. It prevents the product language from drifting into ambiguous agent, tool, runner,
verifier, or proof meanings.

### Operation proof

A canonical `operation-proof/v1` value binding operation semantics, authorization snapshot,
execution grant, execution receipt, and independent verification into one deterministic proof
digest. It is accepted only when exact cross-contract bindings hold and when the verifier is
independent from the actor and runner.

### Skill orchestration plan

A canonical `v-one-skill-orchestration-plan/v1` value that classifies one engineering task, selects
only relevant specialist skills, assigns one primary coordinator, records exclusions, development
purpose, development system benefit, and acceptance gates, and emits a deterministic plan digest.
It is a workflow contract, not tool execution, approval, plugin trust, or runtime authorization.

### Control-plane decision

A canonical `v-one-control-plane-decision/v1` value that binds operation semantics, skill
orchestration, optional verified operation proof, explicit boundary, evidence references,
acceptance gates, purpose, system benefit, status, and deterministic decision digest into one system
decision record. It is the control-plane contract, not runtime dispatch or production authority by
itself.

### Usefulness gate

An explicit acceptance gate proving that a change or decision has stated purpose and system benefit.
Current canonical gate names are `change_has_purpose_and_system_benefit` for development work and
`decision_has_purpose_and_system_benefit` for control-plane decisions.

### Execution

One governed attempt to apply an authorized capability. It has an identity, idempotency binding,
lease, fence, state, result, receipt, and audit trail. Execution success is not Verification success.

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

A structured record of an execution result, chained for integrity. A receipt is an executor-side
claim and must not be treated as independent verification.

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

A typed, allowlisted semantic operation with known inputs, effects, limits, verification, and
rollback or compensation properties. Provider-native commands or endpoints are implementations of a
Capability, not replacements for its VOP semantic identity.

### Execution grant

The pure deterministic `execution-grant/v1` value object accepted by ADR-0007. It binds one
execution to an exact artifact, target, policy, capability, expiry, nonce, and fence as a canonical
representation. Authoritative issuance and one-time runtime consumption are separate concerns and
must not be inferred merely from the existence of this contract.

### Authoritative grant issuance

The governed operation that emits a short-lived ExecutionGrant from an immutable authorized state and
exact execution constraints. It is separate from Approval, AuthorizationSnapshot representation, and
Runner execution.

### Runner

An isolated process or service that validates and consumes a scoped grant, executes only the exact
allowed capability/handler under its execution boundary, and emits an ExecutionReceipt. The Runner
does not independently verify real provider post-state; that belongs to a separate verifier identity
and verification path. The isolated Runner runtime remains a separately governed implementation
boundary described by ADR-0008 and its threat model.

### Handler

The exact implementation selected to perform a Capability under an eligible Runner boundary. A
Handler translates VOP semantics into provider/runtime behavior; it does not create authority.

### Fence

A monotonic token preventing an obsolete or late worker from committing a result after recovery or
replacement.

### Indeterminate

An execution result where effects may have occurred but trustworthy final state is unavailable. It
must not be silently treated as verification success or blindly retried.

## Integration terms

### CyberCore

A separate infrastructure context and intelligence platform. In the target model it may provide
observations, knowledge, provenance, comparisons, and candidates. It does not replace VOODOO One
authorization and cannot activate its own Candidate by inference alone.

### V-One member

A participant in the governed operation system with exactly one explicit purpose and authority
boundary. Current common-language roles are owner, operator, AI agent, CyberCore, policy engine,
approval quorum, runner, verifier, and evidence fabric.

### Read-only intake

A versioned integration that imports metadata and evidence references without allowing mutation,
package code execution, or shared persistence.

### Provider

An external system reached through a Module/adapter boundary. Provider-specific language is
translated into VOP semantic capabilities and must not leak into governance authority definitions.

### Module

A provider/domain translation and implementation package. Modules translate canonical VOP semantics
to provider/runtime behavior and back into canonical evidence. Modules do not authorize, choose
policy, invent target identity, or gain arbitrary shell authority.

### Verified technique map

The bounded mapping from external techniques to V-One technique roles. MCP is treated as tool/context
access, A2A as agent interoperability, AgentCore-style runtime telemetry as observability input,
SPIFFE-style identity as transport/workload identity, and Sigstore/in-toto/SLSA as attestation and
provenance primitives. None of these techniques alone grants V-One authorization.

## Canonical CORE status language

Do not create a parallel workflow/status taxonomy for VOP operations.

### RunState

```text
RECEIVED
CLASSIFIED
PLANNED
IN_PROGRESS
WAITING_DEPENDENCY
WAITING_APPROVAL
REVIEW
COMPLETED
CANCELLED
```

### GateStatus

```text
PASS
FAIL
BLOCKED
UNKNOWN
NOT_APPLICABLE
```

### TaskOutcome

```text
COMPLETE
PARTIAL
FAILED
BLOCKED
CANCELLED
```

### Artifact / execution state

```text
PREPARED
APPLIED
VERIFIED
PUBLISHED
DEPLOYED
```

Historical documents may contain older descriptive labels such as `IMPLEMENTED`, `PROPOSED`, or
`INFERRED`. Those labels remain historical/source evidence where they occur; they are not a second
canonical VOP workflow taxonomy and must not be silently translated into a stronger CORE state.
