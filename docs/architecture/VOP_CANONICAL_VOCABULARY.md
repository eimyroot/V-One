# VOP Canonical Vocabulary

| Field | Value |
|---|---|
| Status | CANONICAL / FROZEN R1 |
| Machine authority | `voodoo_product/vop_vocabulary.py` |
| Schema identity authority | `schemas/vop/registry.v1.json` |
| Decision | ADR-0014 |
| Revision | `vop-terminology-freeze-r1` |

> **Jeden význam → jeden termín → jeden kontrakt → jedna autoritativní definice.**

Normative cross-surface invariant:

> **Stejný VOP termín musí mít napříč kódem, docs, receipts, API a UI jeden význam. Změna významu vyžaduje nový termín nebo novou verzi.**

This document is the human-readable projection of the machine vocabulary. It MUST NOT fork into a
second semantic dictionary. Where historical documents disagree, explicit ADR supersession and
version lineage decide the current meaning.

---

# 1. One operation language

External systems may use different transport language:

```text
GitHub       merge pull request
AWS          update service
Kubernetes   patch deployment
Jira         transition issue
Docker       build image
MCP          call tool
A2A          create task
AI           use tool
REST         POST
GraphQL      mutation
gRPC         RPC
```

V-One translates provider-specific semantics behind the Module boundary into one operation model:

```text
ACTOR
↓
INTENT
↓
OPERATION
↓
CAPABILITY
↓
TARGET
↓
INPUT
↓
EXPECTED POST-STATE
↓
POLICY
↓
APPROVAL
↓
AUTHORIZATION
↓
GRANT
↓
DISPATCH
↓
EXECUTION
↓
RECEIPT / OBSERVATION
↓
INDEPENDENT VERIFICATION
↓
EVIDENCE
↓
PROOF
```

Provider language stays behind the Module boundary:

```text
AWS / GitHub / MCP / A2A terminology
                 ↓
               MODULE
                 ↓
        CANONICAL VOP LANGUAGE
```

Transport vocabulary MUST NOT leak into authority semantics.

---

# 2. Canonical nouns

The machine-readable set lives in `voodoo_product/vop_vocabulary.py`. The current semantic meanings
are:

| Term | Canonical meaning |
|---|---|
| **Actor** | principal participating in or initiating a governed operation |
| **Intent** | requested outcome before exact operational normalization |
| **Operation** | governed unit of work |
| **ReviewedOperation** | exact operation content presented to governance |
| **Capability** | semantic action the system can perform |
| **Input** | operation input data |
| **Target** | authoritatively identified object of intended effect |
| **ExpectedPostState** | state expected after successful execution |
| **ObservedPostState** | state independently observed by verification |
| **Permission** | whether an Actor may request a Capability in context |
| **PolicyRevision** | immutable policy version used for a decision |
| **Approval** | approval of exact reviewed content |
| **ApprovalCertificate** | evidence that approval requirements were satisfied |
| **AuthorityWitnessSet** | exact authority facts used by Authorization |
| **AuthorizationSnapshot** | immutable evidence of an authorization decision |
| **ExecutionGrant** | narrow execution permission; current authoritative runtime contract is `execution-grant/v2` |
| **ExecutionCapsule** | exact identity of executable implementation/runtime inputs |
| **GrantConsumptionWitness** | durable evidence of ONE_TIME Grant consumption by the control plane |
| **Dispatch** | durable handoff of already-authorized execution intent |
| **DispatchOutboxEntry** | immutable durable outbound dispatch intent |
| **DispatchInboxAdmission** | durable admission/dedup result for a delivery |
| **ExecutionEpoch** | monotonic coordination generation for fencing obsolete attempts |
| **ExecutionLease** | time-bounded coordination lease for one current ExecutionEpoch |
| **Runner** | isolated execution principal; does not issue or consume Grants |
| **RunnerIdentity** | descriptive identity evidence for one concrete Runner instance |
| **RunnerBoundary** | fail-closed safety ceiling binding Runner to exact lease/capsule/capability |
| **Handler** | exact implementation of a Capability |
| **CredentialAccessDecision** | serializable narrowing decision for out-of-band credential delivery; not a credential |
| **VerifierCredentialDecision** | verifier-specific READ-only credential decision metadata; not a credential |
| **RuntimeActivation** | evidence that an eligible isolated runtime was activated |
| **Observation** | bounded provider/target-state observation; not VerificationResult |
| **ExecutionReceipt** | execution subsystem claim about what it performed |
| **VerifierIdentity** | independent verifier identity evidence |
| **IndependentVerificationBoundary** | fail-closed Runner/Verifier separation and binding contract |
| **VerificationStrength** | strength classification of an independent VerificationResult |
| **VerificationResult** | independent determination of actual observed post-state |
| **Evidence** | auditable evidence artifact |
| **OperationProof** | portable proof binding the governed operation chain |
| **Module** | provider/domain translation and implementation package |
| **Candidate** | proposed but non-active definition or implementation |
| **Activation** | explicit adoption of a concrete definition/implementation |

Every public subtype may be more specific, but MUST NOT weaken or redefine its parent semantic noun.

---

# 3. Canonical verbs

```text
PROPOSE
NORMALIZE
VALIDATE
REVIEW
APPROVE
AUTHORIZE
ISSUE
DISPATCH
EXECUTE
VERIFY
ATTEST
ADOPT
ACTIVATE
RELEASE
DEPLOY
REVOKE
SUPERSEDE
```

These verbs are not synonyms.

```text
APPROVE
!= AUTHORIZE

AUTHORIZE
!= ISSUE

ISSUE
!= DISPATCH

DISPATCH
!= EXECUTE

EXECUTE
!= VERIFY

VERIFY
!= ATTEST

RELEASE
!= DEPLOY
```

A stronger downstream verb MUST NOT be inferred from evidence of an earlier verb.

---

# 4. Mandatory non-conflation

```text
Approval
!= Authorization

AuthorizationSnapshot
!= ExecutionGrant

ExecutionGrant
!= ExecutionCapsule

ExecutionGrant
!= ExecutionLease

ExecutionEpoch
!= Authority

RunnerIdentity
!= Authorization

Runner
!= Verifier

ExecutionReceipt
!= VerificationResult

Observation
!= VerificationResult

VerificationResult
!= OperationProof

Release
!= Deploy
```

The canonical execution/verification language is intentionally asymmetric:

```text
execution succeeded
verification pending
```

is valid when Runner evidence exists but independent verification does not.

`successful operation` MUST NOT be used to imply full verified success from an ExecutionReceipt
alone.

---

# 5. Current authority-to-verification lineage

The released control-plane/runtime architecture uses:

```text
AuthorizationSnapshot
  ↓
ExecutionGrant/v2
  ↓
GrantConsumptionWitness/v1
  ↓
DispatchOutboxEntry/v1
  ↓
DispatchEnvelope/v1
  ↓
DispatchInboxAdmission/v1
  ↓
ExecutionEpoch + ExecutionLease/v1
  ↓
RunnerIdentity/v1 + RunnerBoundary/v1
  ↓
CredentialAccessDecision/v1
  ↓
RuntimeActivation
  ↓
Observation
  ↓
VerifierIdentity/v1 + IndependentVerificationBoundary/v1
  ↓
VerifierCredentialDecision
  ↓
ObservedPostState/v1
  ↓
VerificationResult/v1 + VerificationStrength/v1
  ↓
OperationProof
```

Not every future contract in this chain is implemented merely because its semantic identity is
reserved. Registry presence is not implementation evidence.

Grant consumption occurs in the control plane **before Dispatch**. The Runner MUST NOT re-consume a
Grant, issue authority, allocate its own authority epoch or create a second authorization lineage.

---

# 6. ExecutionGrant version lineage

`ExecutionGrant` remains one semantic noun, but contract versions are not interchangeable.

```text
execution-grant/v1
= historical deterministic value-contract identity

execution-grant/v2
= current authoritative runtime execution-authority contract
```

Therefore:

```text
execution-grant/v1
SUPERSEDED_BY
execution-grant/v2
```

Historical `v1` remains reserved for auditability. It MUST NOT be silently reinterpreted as `v2`.

---

# 7. SandCloud / CASTER-MINAL / Runner boundary

ADR-0014 supersedes the historical ADR-0013 naming that used SandCloud as a provider-neutral runtime
name.

Canonical meanings:

```text
SandCloud
= governed non-canonical staging / review / validation / evidence layer

CASTER-MINAL
= governed execution control surface

Runner
= isolated execution principal

V-One
= authority and governance semantics
```

Therefore:

```text
SandCloud != Runner
SandCloud != CASTER-MINAL
CASTER-MINAL != Authorization authority
Runner != Verifier
```

A hosting vendor, container, microVM or sandbox implementation is a provider implementation behind
the Runner boundary, not a replacement VOP term.

---

# 8. Canonical relation language

```text
REQUESTED_BY
PARENT_OF
CHILD_OF
DEPENDS_ON
DERIVED_FROM
BOUND_TO
AUTHORIZED_BY
ISSUED_FROM
DISPATCHED_TO
EXECUTED_BY
VERIFIED_BY
PRODUCED
PROVES
SUPERSEDES
ACTIVATES
CAUSES
CORRELATES_WITH
```

Example:

```text
op_123 AUTHORIZED_BY snapshot_55
grant_77 ISSUED_FROM snapshot_55
exec_88 EXECUTED_BY runner_2
verification_91 VERIFIED_BY verifier_4
proof_100 PROVES op_123
```

---

# 9. Identity grammar

Canonical identity fields:

```text
logical_identity
content_identity
instance_id
schema_version
producer
created_at
causation_id
correlation_id
```

Semantics:

```text
logical_identity = what semantic thing this is
content_identity = exact content/version identity
instance_id      = concrete occurrence/instance
```

Contract-specific field names may be narrower (`runner_id`, `identity_digest`, etc.), but MUST
preserve these identity roles rather than redefine them.

---

# 10. Shared CORE status language

Do not create a parallel VOP status taxonomy.

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

Historical descriptive labels may remain historical evidence; they MUST NOT be silently mapped into
a stronger canonical CORE state.

---

# 11. VOP Schema Registry

The vocabulary is machine-enforced through `schemas/vop/registry.v1.json` and
`voodoo_product/vop_vocabulary.py`.

The registry currently reserves, among others:

```text
operation-request/v1
reviewed-operation/v1
capability-definition/v1
execution-target/v1
policy-revision/v1
approval-certificate/v1
authority-witness-set/v1
authorization-snapshot/v1
execution-grant/v1
execution-grant/v2
execution-capsule/v1
grant-consumption-witness/v1
dispatch-outbox-entry/v1
dispatch-envelope/v1
dispatch-inbox-admission/v1
execution-lease/v1
runner-identity/v1
runner-boundary/v1
credential-access-decision/v1
isolated-runtime-bootstrap/v1
read-only-runtime-activation/v1
github-ref-observation/v1
verifier-github-ref-observation/v1
execution-receipt/v1
verifier-identity/v1
independent-verification-boundary/v1
verifier-credential-policy/v1
verifier-credential-decision/v1
observed-post-state/v1
verification-strength/v1
verification-result/v1
operation-proof/v1
```

A registry entry means **reserved semantic identity**, not automatic implementation, release,
verification or production authority.

Each implemented public contract should converge on:

```text
schema/version identity
+ semantic invariants
+ canonical serialization
+ conformance tests
+ explicit supersession lineage when meaning changes
```

---

# 12. Semantic Translation Layer

Provider modules translate external semantics into VOP semantics:

```text
EXTERNAL SEMANTICS
        ↓
SEMANTIC MAPPING
        ↓
VOP CANONICAL SEMANTICS
```

Example:

```text
PUT /pulls/71/merge
```

is not itself a V-One Capability. It is a transport implementation of a semantic operation such as:

```text
Capability:
github.pull-request.merge/v1

Target:
github://nulleimy/V-One/pull/71

ExpectedPostState:
state = merged
merge_commit_sha = expected
```

REST, GraphQL or a future provider API may change while the semantic operation remains stable. If
semantic input, authoritative target, side effect, permission, approval, idempotency, receipt or
verification meaning changes, it is not the same semantic Capability merely because the provider
calls look similar.

---

# 13. One dictionary for human, API, UI, audit and AI

The semantic identity exposed by:

```text
code
docs
receipts
API
UI
database concepts
audit events
CLI
AI tools
OperationProof
```

must resolve to the same VOP meaning.

Do not create this drift:

```text
UI: Action
API: Task
DB: Job
Runner: Command
Audit: Event
AI: Tool call
```

when all of them mean canonical `Operation`.

Localized or UX-friendly labels are allowed only as explicit presentation mappings. They cannot
change semantic identity.

---

# 14. Compatibility and terminology drift gate

A public VOP change requires compatibility review.

Allowed without changing an existing semantic version:

- add a genuinely new canonical term;
- reserve a new subtype/schema identity;
- clarify wording without changing semantic meaning.

Requires a new term or new version:

- broaden or narrow the meaning of an existing term;
- move authority ownership between components;
- make an evidence object imply a stronger state than before;
- merge previously distinct concepts;
- split one semantic contract into incompatible meanings.

CI exposes a named **VOP terminology drift gate**. It checks vocabulary determinism, registry parity,
released contract identity coverage, version supersession and known cross-document boundary drift.

The gate is intentionally fail-closed but cannot infer every possible semantic mistake in arbitrary
human prose. Architecture/compatibility review therefore remains part of the contract.

---

# 15. System invariant

```text
ONE SYSTEM
=
ONE SEMANTIC LANGUAGE
```

And the V-One architecture remains:

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

> **One language. One authority model. One proof model. Many providers.**
