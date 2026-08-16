# V-One Product & Architecture Thesis R2

| Field | Value |
|---|---|
| Document class | Product and architecture decision thesis |
| Status | PROPOSED / REVIEW REQUIRED |
| Baseline | `main@0b8fe16eba50a5addfda93efcf41f14490b205e6` |
| Date | 2026-08-17 |
| Adoption authority | Explicit owner adoption only; merge/CI do not imply adoption |
| Implementation authority | NONE implied by this document |
| Immediate implementation gate after adoption | A8 `AuthoritativeSnapshotCreator` |

## 0. Purpose and decision boundary

This document freezes the product and architecture thesis that future V-One work is expected to
conform to unless a later, explicit, evidence-bound decision supersedes it.

It is intentionally a decision document rather than a marketing vision. It distinguishes:

- current implemented facts;
- required architectural invariants;
- proposed target components;
- later expansion areas;
- commercial hypotheses that still require customer validation.

Merging this file does **not** by itself make the thesis owner-adopted. Adoption must be recorded as an
explicit exact-content-bound decision in the repository authority/adoption mechanism. It also does not
authorize implementation, release, deployment, provider mutation, production effects, or any merge of
subsequent implementation PRs.

## 1. Triple-validation result

The thesis was challenged through three independent validation passes before being written.

### V1 — Technical architecture validation: PASS

Primary-source comparison covered current agent/runtime/security and durable-execution designs from
AWS AgentCore, Google Cloud, Microsoft Foundry, Restate, DBOS, SPIFFE, in-toto, Sigstore, MCP, A2A,
and the OpenAI Agents SDK.

The external systems strongly support the following directions:

- authorization enforcement outside probabilistic agent code;
- workload-specific identity rather than broad shared service identity;
- isolated execution boundaries;
- short-lived/scoped credentials;
- durable idempotency, inbox/outbox, leases and epoch fencing;
- separation of execution from verification/assessment;
- standard authenticated attestations rather than bespoke cryptographic envelopes.

The comparison does **not** prove that V-One is unique merely because it has policy, identity,
isolation, tracing, or verification. Those capabilities already exist elsewhere.

### V2 — Competitive differentiation validation: PASS WITH NARROWING

The market already contains strong offerings around agent authorization, gateways, tool runtimes,
workload identity, durable execution, audit, and governance. Therefore V-One must not compete on
"agent gateway + IAM + sandbox + logs" or on the number of integrations.

The defensible thesis is the complete exact-content chain:

```text
WHAT EXACTLY WAS REVIEWED?
        +
WHAT EXACTLY AUTHORIZED THE EFFECT?
        +
WHAT EXACTLY WAS ALLOWED TO EXECUTE?
        +
WHAT EXACT RUNTIME/CODE WAS BOUND TO THE GRANT?
        +
WHAT ACTUALLY EXECUTED?
        +
WHAT REAL POST-STATE EXISTS?
        +
CAN A THIRD PARTY VERIFY THE WHOLE CHAIN?
```

Independent verification alone is not a moat. Portable attestations alone are not a moat. Runtime
isolation alone is not a moat. The differentiation is the **content-bound composition across the full
operation lifecycle**.

### V3 — Current-code feasibility validation: PASS

The current V-One codebase remains a reasonable incremental base:

- modular-monolith control plane;
- canonical VOP vocabulary/translation foundations;
- immutable authority primitives;
- transaction-aware `AuthorizationSnapshotStore`;
- DB-backed authoritative approval evidence resolver;
- explicit execution/persistence and audit boundaries.

A big-bang rewrite is neither required nor justified. Responsibilities should first stabilize inside
the current codebase and only later be extracted into packages/services where a demonstrated trust or
operational boundary requires it.

### Commercial validation status: UNPROVEN

Existing vendors demonstrate willingness to pay for agent authorization, workload identity, durable
execution, governance and enterprise controls. That supports market plausibility, **not V-One product-
market fit**. Pricing, buyer urgency, sales cycle, retention and willingness to pay must be validated
with design partners and real pilots. No document may claim PMF from competitor pricing alone.

## 2. Definitive product position

### Product name

**VOODOO ONE — Verifiable Operations Trust Plane**

Technical description:

> **Provider-neutral control plane for proof-carrying operations.**

V-One is not primarily an AI governance platform and not primarily an agent security platform.
Humans, AI agents, CI/CD systems, MCP clients, A2A peers, schedulers, webhooks and other automation are
all possible proposal/ingress sources. They do not define the internal trust model.

### Core promise

V-One should make consequential operations independently explainable and verifiable across four
questions:

1. What exact operation was reviewed and authorized?
2. What exact bounded authority was issued for execution?
3. What exact implementation/runtime actually attempted the effect?
4. What independently observed post-state proves or disproves the expected result?

## 3. Canonical semantic invariant

```text
ONE SYSTEM
=
ONE SEMANTIC LANGUAGE
```

The internal language is VOP. Provider-specific terminology stays behind module boundaries.

```text
External semantics
        ↓
Semantic mapping
        ↓
VOP canonical semantics
        ↓
Authority / execution / verification / proof
```

Canonical lifecycle nouns include:

```text
Actor
Intent
Operation
ReviewedOperation
Capability
Input
AuthoritativeTarget
ExpectedPostState
Permission
PolicyRevision
Approval
ApprovalCertificate
AuthorityWitnessSet
AuthorizationSnapshot
ExecutionGrant
ExecutionCapsule
Dispatch
Runner
Handler
ExecutionReceipt
VerificationResult
Evidence
OperationProof
Module
Candidate
Activation
```

Canonical verbs remain semantically distinct:

```text
PROPOSE != REVIEW
REVIEW  != APPROVE
APPROVE != AUTHORIZE
AUTHORIZE != ISSUE
ISSUE != EXECUTE
EXECUTE != VERIFY
VERIFY != RELEASE
RELEASE != DEPLOY
```

The schema/vocabulary layer must eventually be machine-enforced through versioned contracts,
canonical serialization, semantic invariants and conformance tests.

## 4. Primary trust invariant — Monotonic Authority

After authorization, downstream components may only:

```text
KEEP
NARROW
EXPIRE
REVOKE
DENY
```

They must never `WIDEN` authority.

Formally, for effective scopes `S`:

```text
S_grant      ⊆ S_snapshot
S_credential ⊆ S_grant
S_runner     ⊆ S_grant
S_handler    ⊆ S_grant
```

A child operation receives no implicit authority from its parent. It must be independently derived and
bound according to the applicable policy.

A semantic/LLM safety layer may deny or escalate a deterministic candidate allow, but it must never
turn a deterministic deny into allow.

## 5. The stable product atom — `OperationCell/v1`

The first real V-One MVP is not a dashboard, a large provider catalog, or CyberCore. It is one complete
proof-carrying operation cell:

```text
Intent
  ↓
VOP Normalize
  ↓
ReviewedOperation
  ↓
PermissionDecision
PolicyRevision
CapabilityDefinition + Activation
TargetBinding
ApprovalCertificate
TrustedClock / Revocation observations
  ↓
AuthorityWitnessSet
  ↓
AuthorizationSnapshot
  ↓
Monotonic Commit Guard
  ↓
ExecutionGrant
  ↓
ExecutionCapsule
  ↓
Transactional Outbox
  ↓
DispatchEnvelope
  ↓
Inbox / Dedup
  ↓
Lease + ExecutionEpoch
  ↓
RunnerIdentity
  ↓
Scoped ephemeral credential
  ↓
PreconditionWitness
  ↓
Exact Handler
  ↓
REAL EFFECT
  ↓
ExecutionReceipt
  ↓
VerifierIdentity
  ↓
Separate read-only verifier credential
  ↓
ObservedPostState
  ↓
VerificationResult
  ↓
OperationProof
```

`OperationCell/v1` becomes stable only when this chain has both positive and fail-closed system evidence.

## 6. Authority plane

The Authority Plane owns deterministic authorization facts, not execution.

Required composition:

```text
ReviewedOperation
→ execution.run permission authority
→ immutable PolicyRevision
→ CapabilityDefinition + Activation
→ deterministic TargetBinding
→ ApprovalEvidence / ApprovalCertificate
→ trusted clock
→ emergency/revocation observations
→ AuthorityWitnessSet
→ AuthorizationSnapshot
```

No snapshot may be built from placeholders, mutable "current" state, caller-supplied authority facts,
or callbacks whose authority is not explicit and independently bound.

### `AuthorityWitnessSet`

The witness set exists so an external verifier can identify the exact authority facts that produced a
snapshot without needing to understand V-One internal SQL tables.

It should bind at minimum:

- permission decision identity;
- policy identity;
- capability definition identity;
- activation generation/digest;
- target binding identity;
- approval certificate identity;
- trusted clock identity;
- revocation/live-deny epoch or equivalent observation.

## 7. PreconditionWitness and TOCTOU defense

Authorization is a point-in-time decision. Provider state can change before execution.

For consequential effects, execution must therefore validate authoritative preconditions immediately
before the effect when the capability contract requires them.

Example:

```text
Authorized:
  merge PR #85
  expected head = abc123

Before effect:
  observed head = def456

Result:
  DENY / REAUTHORIZE
```

`PreconditionWitness` is not a replacement for `AuthorizationSnapshot`. It proves that execution-time
preconditions required by the authorized capability still hold. A mismatch must narrow authority to
DENY, never silently adapt the operation.

## 8. ExecutionGrant

A grant is a narrow, time-bounded execution permission derived from a snapshot. It must bind, at
minimum:

```text
snapshot identity
execution identity
capability
payload digest
authoritative target
runner identity/class
execution capsule digest
TTL / expiry
one-time identifier (jti or equivalent)
revocation semantics
```

Grant issuance must not add capability, target, payload, credential or runtime scope that was absent
from the snapshot.

## 9. ExecutionCapsule

Handler identity alone is insufficient to describe what code actually runs.

`ExecutionCapsule` should content-bind the execution environment, including as applicable:

- handler digest;
- module manifest digest;
- container/rootfs/artifact digest;
- dependency-lock digest;
- SBOM identity;
- network-policy digest;
- resource-limit profile;
- credential requirement/class;
- runner class;
- verification contract identity.

The grant binds the capsule digest. A runner must reject a different capsule, even when the handler
name is unchanged.

## 10. Durable execution boundary

The Authority Kernel must remain independent from a specific workflow engine.

Near-term default:

```text
SQLite for local/test/portable use
PostgreSQL production target
explicit transactions
transactional outbox
inbox/dedup
leases
idempotency
execution epochs/fencing
```

A future abstraction may permit native DB coordination, DBOS, Restate, Temporal or another engine,
but the trust kernel must not depend on one orchestration vendor.

Required dispatch gates:

```text
NO PROVIDER EFFECT BEFORE AUTHORIZATION/OUTBOX COMMIT
NO STALE EXECUTION EPOCH MAY COMPLETE
NO DUPLICATE DISPATCH MAY CREATE A SECOND EFFECT WHEN THE CAPABILITY CLAIMS IDEMPOTENCY
```

Relational tables remain authoritative current operational state. Append-only audit/evidence structures
remain immutable history/proof. Full event-sourcing is not justified by the current requirements.

## 11. SandCloud execution and verification fabric

`SandCloud` is the target execution/verification fabric, not an alternate authority system.

Runner classes may evolve by risk:

```text
low-risk development      → local/container
untrusted standard work   → hardened sandbox/container
high-risk multi-tenant    → microVM
consequential production  → microVM + ephemeral identity + narrow network/credentials
```

Isolation technology is replaceable. Trust semantics are not.

Initial Runner rollout must be READ-ONLY and capability-bounded, for example inspection, tests,
static analysis and provider reads. Provider mutations come only after a complete verified
`OperationCell/v1` exists for lower-risk capabilities.

## 12. Runner / Verifier separation

Required invariant:

```text
RunnerIdentity != VerifierIdentity
RunnerCredential != VerifierCredential
```

The Runner credential is the minimum permission required to cause the authorized effect.
The Verifier credential is read-only and only sufficient to observe the authoritative post-state.

A compromised executor must not automatically control the evidence channel used to prove its own
success.

### Verification strength

Verification should not be reduced to a misleading boolean. The product should encode an explicit
strength class, for example:

```text
V0 NONE
V1 EXECUTOR_ASSERTION
V2 INDEPENDENT_CODE_PATH
V3 INDEPENDENT_IDENTITY + PROVIDER READ
V4 EXTERNAL / CRYPTOGRAPHIC ATTESTATION
```

A capability's production eligibility may require a minimum verification strength.

## 13. Receipt is not proof

The following statement is forbidden:

```text
ExecutionReceipt.SUCCESS == VERIFIED
```

Correct semantics:

```text
execution succeeded
verification pending
```

or:

```text
Receipt.SUCCESS
+
Verifier.FAIL
=
VERIFICATION_FAILED
```

The independent verifier compares `ExpectedPostState` to an authoritative `ObservedPostState` under a
separate identity/credential path.

## 14. OperationProof

V-One should not invent a custom signature envelope when established attestation standards fit.

Target composition:

```text
in-toto Statement
        ↓
V-One OperationProof predicate
        ↓
DSSE-compatible authenticated envelope
        ↓
optional Sigstore-style identity signing / transparency
```

The proof should be portable and independently verifiable. A target UX is:

```text
vone verify proof.json
```

Offline verification should be supported where the trust-root model allows it.

## 15. Ecosystem boundaries

These are **target responsibility boundaries**, not claims that every component is already deployed.

### V-One

Owns:

- VOP semantics;
- authority model;
- capability/policy bindings;
- snapshot/grant contracts;
- monotonic-authority invariants;
- proof contracts and conformance requirements.

### SandCloud

Owns:

- durable dispatch execution boundary;
- isolated Runner runtime;
- workload identity integration;
- scoped credential acquisition;
- separate verification execution path.

It does not authorize operations.

### CASTER-MINAL

Owns operator UX (CLI/TUI/terminal-like interaction) and translates human/agent intent into governed
operation requests.

It must not be an unrestricted production shell and must not manufacture authority.

### CASER-SOURCER

Owns Source-of-Truth reconciliation, drift detection, ADR/provenance relationships and evidence state
reconciliation across live systems.

It may detect truth drift but does not grant execution authority merely because a fact is current.

### CASER

Owns the project/evidence experience: project identity, retained evidence, operation passports, audit
navigation, exports, sharing and commercial team experience.

CASER is not a substitute for V-One authority or independent verification.

## 16. Core, support and later scope

### CORE — build before expansion

```text
VOP
Authority Kernel
AuthorizationSnapshot
ExecutionGrant
ExecutionCapsule
Durable dispatch
Isolated Runner
Independent Verification
OperationProof
```

### SUPPORT — build only as much as the core needs

```text
minimal SandCloud
minimal CASTER-MINAL
CASER evidence UX
CASER-SOURCER reconciliation
```

### LATER

```text
large provider/module catalog
distributed execution fabric at scale
marketplace
Operation Graph / complex DAGs
CyberCore self-improvement loop
broad adaptive architecture
```

Scope expansion before `OperationCell/v1` is proven is a product risk.

## 17. First commercial wedge

The recommended first wedge is:

**Verified Production Change Guard**

Primary initial users/buyers:

- Platform Engineering;
- DevSecOps;
- Security Engineering;
- later regulated engineering/CISO organizations.

Initial job-to-be-done:

> Let humans, AI agents and automation perform bounded engineering changes while proving exactly what
> was approved, what authority was issued, what ran, and whether the real resulting state matches the
> expected state.

First provider domain: Git/GitHub/CI because V-One can dogfood the complete lifecycle against its own
engineering workflow.

Capability rollout should begin with READ-ONLY inspection and validation, then a small reversible
mutation, and only later high-impact actions such as merge/deploy.

## 18. Commercial model hypothesis

Commercial architecture is provisional until customer validation.

Recommended model:

### Community / open core

- VOP contracts and schemas;
- local kernel/CLI;
- module SDK/conformance tooling;
- local proof generation/verification where safe.

Purpose: adoption, inspectability, ecosystem trust and standard-like distribution.

### Team / hosted CASER experience

- hosted evidence retention;
- approvals and policy administration;
- GitHub integration;
- operation passports;
- signed/retained proofs;
- team collaboration.

### Business / Enterprise

- SSO/SAML/OIDC integration;
- BYOC/on-prem/air-gap options;
- SIEM/export integrations;
- private modules/policy packs;
- long retention;
- compliance-support evidence exports;
- HSM/private signing roots where required;
- SLA/support.

Preferred usage metric: **governed/verified operations**, with execution compute, evidence retention and
premium verification as secondary drivers. Token count should not be the primary value metric.

Exact prices are explicitly non-normative until customer discovery validates willingness to pay.

## 19. Module contract

A provider/domain module must not be only an API wrapper.

Before production eligibility, a module/capability should supply the applicable set of:

```text
CapabilityDefinition
Semantic mapping
TargetBinder
Handler
Verifier
CredentialContract
EvidenceContract
ExecutionCapsule
ConformanceEvidence
```

Provider SDK imports should remain behind module boundaries, never in the immutable authority kernel.

MCP and A2A are ingress/egress interoperability protocols above/beside VOP, not V-One authority
primitives.

## 20. World-class engineering baseline

A release-eligible V-One change should progressively enforce:

```text
exact-head PR CI
format / lint / type checks
unit tests
VOP/schema conformance
property-based authority tests
SQLite + PostgreSQL migration tests
negative fail-closed tests
idempotency / replay / concurrency tests
epoch-fencing tests
security tests
module conformance
dependency and static analysis
container/image build
SBOM
artifact provenance / attestation
signature verification
smoke tests
```

Telemetry is observability, not proof. Tests passing are not deployment. A receipt is not independent
verification. Documentation never upgrades implementation status.

## 21. Forbidden architectures and kill criteria

The following are architecture-level denials unless explicitly superseded with evidence:

```text
Generic unrestricted shell as a core production capability        → DENY
Provider SDK imports in authority kernel                           → DENY
LLM/reasoning system turns deterministic DENY into ALLOW           → DENY
Runtime credential broader than Grant                              → DENY
Runner chooses an arbitrary Handler                                → DENY
Execution capsule differs from Grant binding                       → DENY
Required precondition changed after authorization                  → DENY / REAUTHORIZE
Stale execution epoch attempts completion                          → DENY
Handler has no required verification contract                      → NOT PRODUCTION ELIGIBLE
Capability cannot independently verify required post-state         → NOT PRODUCTION ELIGIBLE
Receipt SUCCESS is treated as VERIFIED                             → INVALID CLAIM
CyberCore auto-activates its own candidate                         → DENY
Parent operation authority automatically transfers to child        → DENY
Ambiguous semantic mapping is guessed                              → NEW CAPABILITY/VERSION OR DENY
No evidence is treated as PASS                                     → INVALID CLAIM
Microservices introduced only for architecture appearance          → REJECT
```

## 22. Gated roadmap

### Phase A — Authority Cell completeness

- A8 `AuthoritativeSnapshotCreator` in one outer transaction;
- authoritative revocation/live-deny observation;
- Monotonic Authority checker/contract;
- PreconditionWitness contract and capability requirement model.

Gate: no authority from callbacks/placeholders/mutable unbound state; rollback on every failed authority
read/binding.

### Phase B — Grant and ExecutionCapsule

- authoritative grant issuer;
- replay/one-time store;
- TTL/jti/revocation;
- capsule contract;
- Handler/Runner/Verifier registries.

Gate: no downstream scope widening.

### Phase C — Durable dispatch

- transactional outbox;
- dispatch envelope;
- inbox/dedup;
- lease;
- execution epoch/fencing;
- `DurableCoordinator` boundary.

Gate: no provider effect before commit; no stale attempt may complete.

### Phase D — READ-ONLY SandCloud

- RunnerIdentity;
- credential broker;
- isolated execution;
- network deny-by-default;
- bounded read/test/static-analysis capabilities.

Gate: no provider mutation.

### Phase E — Independent verification

- VerifierIdentity;
- separate read-only credentials;
- ExpectedPostState / ObservedPostState contracts;
- VerificationStrength.

Gate: executor success cannot override verifier failure.

### Phase F — First controlled mutation

One low-risk/reversible GitHub capability through the complete chain.

Gate: complete operation proof and rollback/negative evidence.

### Phase G — OperationProof

- content-addressed evidence graph;
- in-toto-compatible statement/predicate;
- DSSE-compatible envelope;
- optional Sigstore integration;
- portable/offline verification path.

### Phase H — Freeze `OperationCell/v1`

Declare the atomic lifecycle stable only after complete system evidence.

### Phase I — Operation Graph

Compose cells into a bounded DAG with no implicit parent→child authority inheritance.

### Phase J — Module ecosystem / CASER productization

Expand providers and evidence UX after the core is stable.

### Phase K — CyberCore

```text
observe
→ compare
→ propose candidate
→ sandbox
→ benchmark
→ semantic equivalence
→ conformance
→ human/policy adoption candidate
```

CyberCore cannot authorize or activate its own proposal.

## 23. Immediate consequence for A8

After this thesis is explicitly adopted, the next bounded implementation remains A8.

A8 must not absorb future Grant, Runner, dispatch, provider mutation, or proof responsibilities. Its
single purpose is to compose exact authoritative facts into an immutable `AuthorizationSnapshot` and
persist snapshot + audit inside one coherent database transaction.

Required A8 negative evidence includes at least:

```text
stale/expired approval
wrong workspace/environment
missing or denied execution.run
inactive/revoked capability
capability/environment mismatch
target binding mismatch
policy drift/mismatch
trusted-clock/validity failure
revocation/live-deny failure
persistence/audit failure
outer transaction rollback
```

PreconditionWitness is a required future execution-time guard, but it must not be confused with the
snapshot creator's point-in-time authorization responsibility.

## 24. Research basis — primary sources

The thesis intentionally relies on primary/official documentation where external facts matter.
Representative sources checked during the R2 validation:

- AWS AgentCore Runtime sessions and microVM routing: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html
- AWS AgentCore Policy/Cedar enforcement: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-getting-started.html
- AWS AgentCore runtime security: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html
- Google Cloud Agent Identity / IAM: https://cloud.google.com/blog/products/identity-security/whats-new-in-iam-security-governance-and-runtime-defense
- Google Cloud agent security principles: https://cloud.google.com/blog/products/identity-security/cloud-ciso-perspectives-how-google-secures-ai-agents/
- Microsoft Foundry hosted agents / per-session isolation and identity: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
- Restate architecture / log, idempotency and epoch fencing: https://docs.restate.dev/references/architecture
- DBOS durable execution: https://docs.dbos.dev/
- SPIFFE workload identity and SVIDs: https://spiffe.io/docs/latest/deploying/svids/
- in-toto Statement: https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
- in-toto Envelope / DSSE recommendation: https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md
- Sigstore keyless signing: https://docs.sigstore.dev/cosign/signing/overview/
- MCP authorization scope: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- A2A 1.0 specification: https://a2a-protocol.org/dev/specification/
- OpenAI Agents SDK primitives: https://openai.github.io/openai-agents-python/
- GitHub offline attestation verification: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline
- Arcade actions runtime: https://www.arcade.dev/product/
- Permit MCP Gateway pricing/product evidence: https://www.permit.io/mcp-gateway/pricing
- Aembit workload/agent IAM pricing/product evidence: https://aembit.io/pricing/
- DBOS pricing/product evidence: https://www.dbos.dev/dbos-pricing

## 25. Final thesis

```text
V-ONE
=
CANONICAL OPERATION LANGUAGE
+
SMALL IMMUTABLE TRUST KERNEL
+
MONOTONIC AUTHORITY
+
VERSIONED OPERATION SEMANTICS
+
CONTENT-BOUND EXECUTION CONTRACTS
+
CONFORMANCE-TESTED MODULE ECOSYSTEM
+
ISOLATED DURABLE EXECUTION
+
INDEPENDENT POST-STATE VERIFICATION
+
PORTABLE PROOF
```

Short form:

> **One language. One authority model. One proof model. Many providers.**

Operational invariant:

```text
INTELLIGENCE MAY PROPOSE.
AUTHORITY MAY AUTHORIZE.
EVERY DOWNSTREAM LAYER MAY ONLY NARROW THAT AUTHORITY.
RUNNER MAY EXECUTE.
ONLY INDEPENDENT EVIDENCE MAY PROVE THE RESULT.
```

The project should optimize for completing one excellent, independently verifiable
`OperationCell/v1` before maximizing integrations, autonomy, provider count or distributed scale.
