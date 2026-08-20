# VOP Canonical Vocabulary

| Field | Value |
|---|---|
| Status | CANONICAL / RECONCILED R2 |
| Machine authority | `voodoo_product/vop_vocabulary.py` |
| Schema identity authority | `schemas/vop/registry.v1.json` |
| Original freeze | ADR-0014 |
| R2 reconciliation | ADR-0018 |
| Revision | `vop-terminology-freeze-r2` |
| Reconciled | `2026-08-20` |

> **Jeden význam → jeden termín → jeden kontrakt → jedna autoritativní definice.**

Normative cross-surface invariant:

> **Stejný VOP termín musí mít napříč kódem, docs, receipts, API a UI jeden význam. Změna významu vyžaduje nový termín nebo novou verzi.**

This document is the human projection of the machine vocabulary. It is not a second semantic
dictionary. Historical identities remain reserved; current specialized contracts must not be
presented as universal replacements when their source invariants are narrower.

## 1. One operation language

```text
GitHub / AWS / Kubernetes / MCP / A2A / REST / GraphQL / gRPC
                         ↓
                       MODULE
                         ↓
                CANONICAL VOP LANGUAGE
```

Provider vocabulary may implement a Capability, but it does not redefine V-One authority or evidence
semantics.

## 2. Canonical lifecycle is a stage superset

The machine `OPERATION_STAGES` sequence is an **ordered semantic superset**, not a requirement that
every capability visits every tail stage:

```text
INTENT
↓
REVIEWED OPERATION
↓
POLICY DECISION
↓
APPROVAL QUORUM CERTIFICATE
↓
AUTHORIZATION SNAPSHOT
↓
EXECUTION GRANT
↓
CONTROL-PLANE GRANT CONSUMPTION
↓
DISPATCH
↓
EXECUTION LEASE / EPOCH
↓
RUNNER EXECUTION
↓
[EXECUTION-SIDE EVIDENCE AS REQUIRED BY THE PROFILE]
↓
INDEPENDENT VERIFICATION
↓
VERIFICATION RESULT
↓
[PROFILE-SPECIFIC TERMINAL TAIL]
```

A concrete operation traverses only the stages required by its registered terminal profile.

## 3. Registered terminal profiles

### `READ_ONLY_VERIFIED`

Current independently verified READ operations terminate at the independent verification result:

```text
Runner Observation
↓
Independent Verifier Observation
↓
ObservedPostState/v1
↓
VerificationStrength/v1
↓
VerificationResult/v1 = VERIFIED
```

For this profile:

```text
ExecutionReceipt/v2 = NOT_APPLICABLE
OperationProof/v2   = NOT_APPLICABLE
OperationCell/v1    = NOT_APPLICABLE
```

This does **not** mean a future read-proof contract is forbidden. It means no current contract may be
silently stretched beyond its accepted invariants.

### `BOUNDED_MUTATION_VERIFIED`

The accepted current write/rollback lineage is:

```text
bounded provider mutation
↓
ExecutionReceipt/v2                 [effect claim; verification_status=NOT_EVALUATED]
↓
independent readback
↓
VerificationResult/v1 = VERIFIED
↓
OperationProof/v2
↓
OperationCell/v1
```

`OperationProof/v2` and `OperationCell/v1` are current bounded-mutation evidence contracts. They are
**NOT a universal replacement** for every historical v1 proof/receipt lineage and are not mandatory
for READ-only verification.

## 4. Canonical nouns

Machine-readable definitions live in `voodoo_product/vop_vocabulary.py`.

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
| AuthorizationSnapshot | immutable evidence of authorization |
| ExecutionGrant | narrow execution permission; current runtime authority is `execution-grant/v2` |
| GrantConsumptionWitness | durable evidence of ONE_TIME consumption by the control plane |
| Dispatch | durable handoff of already-authorized intent |
| ExecutionEpoch | monotonic coordination generation, not authority |
| ExecutionLease | time-bounded current-execution coordination lease |
| ExecutionCapsule | exact executable/runtime input identity |
| Runner | bounded execution principal; never Grant issuer/consumer |
| ExecutionReceipt | execution-side claim; version-specific semantics are mandatory |
| VerificationResult | independent determination of actual observed post-state |
| OperationProof | portable proof for a registered lineage, not a universal wrapper |
| OperationCell | stable content-addressed atom for the accepted `OperationProof/v2` lineage |
| Module | provider/domain translation implementation package |

## 5. Canonical verbs

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

They are not synonyms:

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

## 6. Mandatory non-conflation

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

Therefore this state is valid:

```text
execution succeeded
verification pending
```

and this inference is forbidden:

```text
Receipt exists
⇒ VERIFIED
```

## 7. Authority/execution prefix

The current component-level authority and execution prefix is:

```text
ReviewedOperation
↓
Approval / ApprovalCertificate
↓
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
```

Grant consumption occurs in the **control plane before Dispatch**. The Runner MUST NOT re-consume a
Grant, issue authority, allocate an authority epoch or create a parallel authorization lineage.

## 8. Version and compatibility lineage

Historical schema IDs remain reserved for auditability.

### True supersession

```text
execution-grant/v1
SUPERSEDED_BY
execution-grant/v2
```

`execution-grant/v2` is the current authoritative runtime authority contract.

### Parallel/specialized lineage — not universal supersession

```text
execution-receipt/v1
= legacy generic v1 receipt lineage

execution-receipt/v2
= current bounded-mutation effect receipt
  provider_mutation_count == 1
  automatic_retry_performed == false
  verification_status == NOT_EVALUATED
```

Therefore:

```text
execution-receipt/v2
!= universal supersession of execution-receipt/v1
```

Likewise:

```text
operation-proof/v1
= legacy generic v1 proof lineage

operation-proof/v2
= current bounded-mutation proof over ExecutionReceipt/v2
  + canonical independent VerificationResult/v1 evidence
```

Therefore:

```text
operation-proof/v2
!= universal supersession of operation-proof/v1
```

`operation-cell/v1` is additive and currently requires canonically revalidated
`operation-proof/v2`; it has no historical predecessor.

## 9. SandCloud / CASTER-MINAL / Runner boundary

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

So:

```text
SandCloud != Runner
SandCloud != CASTER-MINAL
CASTER-MINAL != Authorization authority
Runner != Verifier
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

## 11. Shared CORE status language

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

Hash-chain integrity uses a gate/integrity state such as `PASS/FAIL`; it never creates independent
`VERIFIED` operation state.

## 12. Registry rule

Registry presence reserves semantic identity. It does not by itself create implementation,
verification, release, deployment or authority.

The registry machine projection includes:

- `schema_supersessions` only for true semantic replacement;
- `schema_compatibility` for historical/specialized lineage relationships;
- `operation_terminal_profiles` for valid terminal tails;
- `operation_stage_rule` explaining that the stage sequence is a superset.

## 13. Cross-surface rule

Code, docs, receipts, API, UI, database concepts, audit events, CLI and AI tooling must resolve each
VOP term to the same meaning. Localized UX labels may change presentation, never semantic identity.

A public semantic change requires a new term/version/revision and compatibility review.

```text
ONE SYSTEM
=
ONE SEMANTIC LANGUAGE
```

**One language. One authority model. One proof model. Many providers.**
