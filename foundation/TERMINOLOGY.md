# VOODOO One Terminology

| Field | Value |
|---|---|
| Document status | Accepted terminology |
| Scope | Product, architecture, evidence, and roadmap language |
| Rule | New public terms require documentation and compatibility review |
| VOP authority | `docs/architecture/VOP_CANONICAL_VOCABULARY.md` + `voodoo_product/vop_vocabulary.py` |
| Original VOP freeze | ADR-0014 / `vop-terminology-freeze-r1` |
| Current VOP revision | ADR-0018 / `vop-terminology-freeze-r2` |
| Reconciled | `2026-08-20` |

## Canonical-language boundary

The authoritative operation-language vocabulary is VOP Canonical Vocabulary. One semantic meaning
must have one canonical term, one contract identity and one authoritative definition. This file
explains product/foundation language; it must not fork VOP nouns, verbs, relations or status semantics.

> **Stejný VOP termín musí mít napříč kódem, docs, receipts, API a UI jeden význam. Změna významu vyžaduje nový termín nebo novou verzi.**

Machine vocabulary lives in `voodoo_product/vop_vocabulary.py`; canonical schema identities,
compatibility classification and terminal profiles live in `schemas/vop/registry.v1.json`.

Historical schema identities remain reserved for auditability. `SUPERSEDES` is used only for a true
semantic replacement; a newer specialized contract must instead carry explicit compatibility/lineage
classification.

## Capability-status vocabulary

Documentation capability state uses:

```text
VERIFIED
IMPLEMENTED
PROPOSED
INFERRED
UNKNOWN
BLOCKED
```

These labels describe evidence-scoped capability truth. They are not a second VOP run-state taxonomy.

`COMPLETE` is not a VOODOO capability status.

## Core product terms

### ReviewedOperation

Exact normalized operation content presented to governance. Downstream approvals and authority bind to
that reviewed identity rather than mutable UI intent.

### Approval

Approval of exact reviewed content. Approval is evidence used by authorization; it is not itself
Authorization or ExecutionGrant.

### AuthorizationSnapshot

Immutable evidence of an authorization decision over exact reviewed operation, policy/permission,
approval and target facts.

### ExecutionGrant

`ExecutionGrant` is the canonical semantic noun. Version-specific behavior must state the schema.

`execution-grant/v1` is historical deterministic representation. The current authoritative runtime authority contract is:

```text
execution-grant/v2
```

It is narrow, exact-content bound and ONE_TIME. This is a true semantic supersession.

### Grant consumption witness

`grant-consumption-witness/v1` is durable evidence that one ONE_TIME `ExecutionGrant/v2` was consumed
by the **control plane before Dispatch**.

Grant consumption is not a Runner responsibility.

### Dispatch

Durable handoff of already-authorized execution intent. Current contracts include
`dispatch-outbox-entry/v1`, `dispatch-envelope/v1` and `dispatch-inbox-admission/v1`.

Dispatch transports authority already decided upstream; it does not create new authority.

### ExecutionEpoch / ExecutionLease

`ExecutionEpoch` is a monotonic coordination generation. `execution-lease/v1` is the bounded lease for
one current epoch. Epoch/lease/fence coordinate current execution attempts but do not widen authority.

### ExecutionCapsule

Exact identity of executable implementation/runtime inputs. It is distinct from ExecutionGrant.

### Runner

An isolated execution principal that performs only the already-authorized capability/handler under
current durable dispatch, lease and fence state.

The Runner **does not
issue or consume the Grant**, does not allocate its own authority epoch, does not authorize itself and
does not independently verify provider post-state.

Canonical common-language Runner authority is `bounded_execution_only`.

### RunnerIdentity / RunnerBoundary

`runner-identity/v1` is descriptive identity evidence for one concrete Runner instance. RunnerBoundary
is the fail-closed execution ceiling binding Runner to exact lease/capsule/capability constraints.
Neither creates authorization.

### CredentialAccessDecision

Serializable narrowing metadata for out-of-band credential delivery. It contains no usable secret and
is not authorization or provider-effect evidence.

### RuntimeActivation

Evidence that an eligible isolated runtime boundary was activated for use. Activation is not provider
post-state verification.

### ExecutionReceipt

Execution-side claim about what the execution subsystem attempted/performed. Version semantics are
mandatory:

```text
execution-receipt/v1
= legacy generic v1 receipt lineage

execution-receipt/v2
= current bounded-mutation effect receipt
  provider_mutation_count == 1
  automatic_retry_performed == false
  verification_status == NOT_EVALUATED
```

Therefore `execution-receipt/v2` is **not** a universal replacement for every v1 receipt lineage.

```text
ExecutionReceipt != VerificationResult
execution succeeded != VERIFIED
```

A receipt or valid receipt chain cannot manufacture independent verification.

## Verification terms

### Observation

Bounded provider/target-state observation. Observation is evidence input, not VerificationResult.

### VerifierIdentity

Content-addressed identity evidence for a verifier that must remain separate from RunnerIdentity.

### IndependentVerificationBoundary

Fail-closed binding proving required Runner/Verifier identity, instance and credential separation for
the active verification path.

### VerificationStrength

Classification of how strongly a VerificationResult is supported.

### VerificationResult

Independent determination of actual observed provider/target post-state. It is distinct from Runner
execution evidence, Observation, OperationProof and OperationCell.

For the current `READ_ONLY_VERIFIED` terminal profile, `VerificationResult/v1` is the verified terminal:

```text
READ_ONLY_VERIFIED
→ independent_verification
→ verification_result
```

No current READ-only contract is silently promoted into `ExecutionReceipt/v2`, `OperationProof/v2` or
`OperationCell/v1`.

### OperationProof

Portable content-addressed proof for a registered evidence lineage.

```text
operation-proof/v1
= legacy generic v1 proof lineage

operation-proof/v2
= current bounded-mutation proof lineage
  ExecutionReceipt/v2
  + canonical independent VerificationResult/v1 evidence
```

`operation-proof/v2` requires exactly one bounded provider mutation, forbids automatic mutation retry
and recomputes canonical verification provenance. It is **not a universal supersession** of
`operation-proof/v1`.

### OperationCell

`operation-cell/v1` is the stable minimal provider-neutral product atom for the current
`BOUNDED_MUTATION_VERIFIED` lineage over one canonically revalidated `OperationProof/v2`.

```text
BOUNDED_MUTATION_VERIFIED
→ execution_receipt
→ independent_verification
→ verification_result
→ operation_proof
→ operation_cell
```

```text
VerificationResult != OperationProof
OperationProof != OperationCell
OperationCell != authority
```

The cell does not duplicate nested authorization/provider evidence and cannot execute, verify, release
or deploy anything.

## Evidence terms

### Audit event

Append-only record of a material governance/control-plane action.

### Receipt-chain / audit-chain integrity

Integrity result over retained evidence structure. Use a gate result such as `PASS/FAIL`; do not
translate chain integrity into an operation-level `VERIFIED` state.

### Evidence verification

A deliberate check of evidence integrity/provenance in its stated scope. It is distinct from liveness,
readiness and provider-state verification.

### Checkpoint / ProofGraph

A checkpoint is a preserved development-state package. ProofGraph is a deterministic projection of
supported evidence relationships. Neither is automatically release or deployment evidence.

### Attestation

Signed statement binding identity to a claim. Signature/integrity support does not by itself define
V-One authority semantics.

## Integration terms

### SandCloud

Governed non-canonical staging/review/validation/evidence layer. SandCloud is not project truth,
authorization authority or the canonical execution principal.

### CASTER-MINAL

Governed execution control surface that hands an already-authorized plan to an eligible Runner. It
does not manufacture authorization.

### Module

Provider/domain translation and implementation package. Modules translate VOP semantics into
provider/runtime behavior; provider terminology must not redefine authority semantics.

### Security Intelligence

Descriptive security context/classification metadata. Current R-SI1.1 is intelligence-only and cannot
issue authority, consume Grants, become Runner/Verifier or automatically become proof evidence.

### CyberCore

Separate infrastructure/context/intelligence system. It may provide observations, learning signals,
knowledge and proposals.

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

No shared database, tool access or proposal automatically creates V-One authority.

## Canonical non-conflation

```text
Approval != Authorization
AuthorizationSnapshot != ExecutionGrant
ExecutionGrant != ExecutionCapsule
ExecutionGrant != ExecutionLease
ExecutionEpoch != Authority
Runner != Verifier
ExecutionReceipt != VerificationResult
Observation != VerificationResult
VerificationResult != OperationProof
OperationProof != OperationCell
Evidence-chain integrity != independent verification
Release != Deploy
```

## Canonical CORE status language

Do not create another VOP workflow/status taxonomy.

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

Historical descriptive labels remain historical evidence where they occur. They must not be silently
mapped into stronger current VOP states.