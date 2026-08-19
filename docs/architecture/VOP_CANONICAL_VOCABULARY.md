# VOP Canonical Vocabulary

| Field | Value |
|---|---|
| Status | CANONICAL / FROZEN R1 with additive reconciled identities |
| Machine authority | `voodoo_product/vop_vocabulary.py` |
| Schema identity authority | `schemas/vop/registry.v1.json` |
| Decision | ADR-0014 |
| Revision | `vop-terminology-freeze-r1` |
| Reconciled | `2026-08-20` |

> **Jeden význam → jeden termín → jeden kontrakt → jedna autoritativní definice.**

Normative cross-surface invariant:

> **Stejný VOP termín musí mít napříč kódem, docs, receipts, API a UI jeden význam. Změna významu vyžaduje nový termín nebo novou verzi.**

This document is the human projection of the machine vocabulary. It is not a second semantic
dictionary. Additive new identities may be registered without reinterpreting historical identities.

## 1. One operation language

External transports remain provider-specific, but authority/evidence semantics are VOP-specific:

```text
GitHub / AWS / Kubernetes / MCP / A2A / REST / GraphQL / gRPC
                         ↓
                       MODULE
                         ↓
                CANONICAL VOP LANGUAGE
```

Transport vocabulary MUST NOT leak into authority semantics.

## 2. Canonical lifecycle language

```text
ACTOR
↓
INTENT
↓
REVIEWED OPERATION
↓
CAPABILITY + TARGET + EXPECTED POST-STATE
↓
POLICY + APPROVAL
↓
AUTHORIZATION SNAPSHOT
↓
EXECUTION GRANT
↓
CONTROL-PLANE GRANT CONSUMPTION
↓
DISPATCH
↓
EXECUTION EPOCH / LEASE
↓
RUNNER EXECUTION
↓
EXECUTION RECEIPT
↓
INDEPENDENT VERIFICATION
↓
VERIFICATION RESULT
↓
OPERATION PROOF
↓
OPERATION CELL
```

The compact `OPERATION_STAGES` machine sequence remains a semantic lifecycle projection; lower-level
durable dispatch/lease contracts remain explicitly registered nouns/schema identities and must not be
collapsed into Runner authority.

## 3. Canonical nouns

The machine-readable definitions live in `voodoo_product/vop_vocabulary.py`. Important current nouns:

| Term | Canonical meaning |
|---|---|
| Actor | principal participating in or initiating a governed operation |
| Intent | requested outcome before exact normalization |
| Operation | governed unit of work |
| ReviewedOperation | exact content presented to governance |
| Capability | semantic action the system can perform |
| Target | authoritatively identified object of intended effect |
| ExpectedPostState | expected state after successful execution |
| ObservedPostState | state independently observed by verification |
| Approval | approval of exact reviewed content |
| AuthorizationSnapshot | immutable evidence of an authorization decision |
| ExecutionGrant | narrow execution permission; current authority contract is `execution-grant/v2` |
| ExecutionCapsule | exact executable/runtime input identity |
| GrantConsumptionWitness | durable evidence of ONE_TIME Grant consumption by the control plane |
| DispatchOutboxEntry | immutable durable outbound dispatch intent |
| DispatchInboxAdmission | durable delivery admission/dedup result |
| ExecutionEpoch | monotonic coordination generation for fencing obsolete attempts |
| ExecutionLease | time-bounded lease for one current ExecutionEpoch |
| Runner | isolated execution principal; does not issue or consume Grants |
| RunnerIdentity | descriptive content-addressed identity of one Runner instance |
| RunnerBoundary | fail-closed ceiling binding Runner to lease/capsule/capability |
| CredentialAccessDecision | narrowed credential-delivery decision metadata; not a credential |
| RuntimeActivation | evidence that an eligible isolated runtime was activated |
| Observation | bounded provider/target observation; not VerificationResult |
| ExecutionReceipt | execution subsystem claim about what it performed |
| VerifierIdentity | identity evidence for the independent verifier |
| IndependentVerificationBoundary | required Runner/Verifier separation/binding |
| VerificationStrength | strength classification for VerificationResult |
| VerificationResult | independent determination of actual observed post-state |
| Evidence | auditable evidence artifact |
| OperationProof | portable proof binding the governed operation chain |
| OperationCell | stable content-addressed product atom over canonically revalidated `OperationProof/v2` |
| Module | provider/domain translation and implementation package |
| Candidate | proposed but non-active definition/implementation |
| Activation | explicit adoption of a concrete definition/implementation |

`OperationCell` is not a second proof format and does not copy/widen nested authority. Its first
accepted contract is `operation-cell/v1`.

## 4. Canonical verbs

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

These verbs are not synonyms:

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

A stronger downstream verb MUST NOT be inferred from an earlier verb.

## 5. Mandatory non-conflation

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

OperationProof
!= OperationCell

Evidence-chain integrity
!= Independent verification

Release
!= Deploy
```

The execution/verification language is intentionally asymmetric:

```text
execution succeeded
verification pending
```

is valid. `successful operation` MUST NOT imply fully verified success from an ExecutionReceipt alone.

## 6. Current authority-to-cell lineage

```text
AuthorizationSnapshot
  ↓
ExecutionGrant/v2
  ↓
GrantConsumptionWitness/v1          [CONTROL PLANE]
  ↓
DispatchOutboxEntry/v1
  ↓
DispatchEnvelope/v1
  ↓
DispatchInboxAdmission/v1
  ↓
ExecutionEpoch + ExecutionLease/v1
  ↓
ExecutionCapsule/v1
  ↓
RunnerIdentity + RunnerBoundary
  ↓
CredentialAccessDecision
  ↓
RuntimeActivation
  ↓
Provider effect / Observation
  ↓
ExecutionReceipt/v2                 [verification_status remains separate]
  ↓
VerifierIdentity + IndependentVerificationBoundary
  ↓
VerifierCredentialDecision
  ↓
ObservedPostState/v1
  ↓
VerificationStrength/v1 + VerificationResult/v1
  ↓
OperationProof/v2
  ↓
OperationCell/v1
```

Grant consumption occurs in the **control plane before Dispatch**. The Runner MUST NOT re-consume a
Grant, issue authority, allocate its own authority epoch or create a second authorization lineage.

## 7. Version lineage

Historical schema IDs remain reserved for auditability and must not be silently reinterpreted.

```text
execution-grant/v1
SUPERSEDED_BY
execution-grant/v2

execution-receipt/v1
SUPERSEDED_BY
execution-receipt/v2

operation-proof/v1
SUPERSEDED_BY
operation-proof/v2
```

`operation-proof/v1` remains valid historical lineage. `operation-proof/v2` is the current proof
contract over `ExecutionReceipt/v2` and independent `VerificationResult/v1` evidence.

`operation-cell/v1` is additive and has no historical predecessor.

## 8. SandCloud / CASTER-MINAL / Runner boundary

```text
SandCloud
= governed non-canonical staging / review / validation / evidence layer

CASTER-MINAL
= governed execution control surface

Runner
= isolated bounded execution principal

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

## 9. Canonical relation language

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

## 10. Identity grammar

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

`logical_identity` says what semantic thing this is; `content_identity` binds exact content/version;
`instance_id` identifies a concrete occurrence.

## 11. Shared CORE status language

Do not create parallel status taxonomies.

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

Hash-chain integrity should use a gate/integrity result such as `PASS/FAIL`; it must not manufacture
an operation-level `VERIFIED` state.

## 12. VOP Schema Registry

The registry currently includes, among the broader set:

```text
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
runner-boundary/v2
runner-boundary/v3
credential-access-decision/v1
credential-access-decision/v2
credential-access-decision/v3
execution-receipt/v1
execution-receipt/v2
verifier-identity/v1
independent-verification-boundary/v1
independent-verification-boundary/v2
observed-post-state/v1
verification-strength/v1
verification-result/v1
operation-proof/v1
operation-proof/v2
operation-cell/v1
```

Registry presence reserves semantic identity. It never by itself creates implementation,
verification, release, deployment or runtime authority.

## 13. One dictionary for human, API, UI, audit and AI

The semantic identity exposed by code, docs, receipts, API, UI, database concepts, audit events, CLI,
AI tools, OperationProof and OperationCell must resolve to the same meaning.

Localized UX labels are allowed only as presentation mappings. They cannot change semantic identity.

## 14. Compatibility and terminology drift gate

A public VOP change requires compatibility review.

Allowed additively:

- genuinely new canonical term;
- new schema identity;
- wording clarification without changing existing meaning.

Requires new term/version or explicit supersession:

- moving authority ownership between components;
- making an evidence object imply a stronger state;
- broadening/narrowing an existing semantic meaning;
- merging previously distinct concepts.

CI must check machine vocabulary/registry parity **and** current implemented contract coverage plus the
cross-surface truth invariants that prevent Receipt⇒VERIFIED and Runner⇒Grant-consumer drift.

```text
ONE SYSTEM
=
ONE SEMANTIC LANGUAGE
```

**One language. One authority model. One proof model. Many providers.**
