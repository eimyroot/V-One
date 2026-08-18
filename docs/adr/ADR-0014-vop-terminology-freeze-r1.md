# ADR-0014: VOP Terminology Freeze R1

| Field | Value |
|---|---|
| Status | ACCEPTED |
| Date | 2026-08-18 |
| Scope | Canonical V-One operation language across code, docs, receipts, API and UI |
| Initial branch base | `main@354928ddb5b2b15eacf204c9d2a2f233b5bf7a88` |
| Acceptance base | `main@b9468d91f39ff04090e6d19d314b5e820e029913` after PR #109 / E2 merge |
| Owner decision | Explicitly authorized before Phase E3 |
| Supersedes | ADR-0013 only where it names SandCloud as the isolated execution boundary |
| Runtime authority change | NONE |
| Provider mutation | NONE |

## Decision

V-One already has a canonical VOP language owner in:

1. `voodoo_product/vop_vocabulary.py` — machine-readable semantic authority;
2. `docs/architecture/VOP_CANONICAL_VOCABULARY.md` — normative human-readable projection;
3. `schemas/vop/registry.v1.json` — reserved contract identities and version lineage;
4. `foundation/TERMINOLOGY.md` — broader product-language projection that MUST NOT redefine VOP in parallel.

This ADR freezes the ownership model and reconciles Phase B-E2 additions into it. It does **not** create a second glossary.

The canonical invariant is:

> **Stejný VOP termín musí mít napříč kódem, docs, receipts, API a UI jeden význam. Změna významu vyžaduje nový termín nebo novou verzi.**

Equivalent normative form:

```text
SAME VOP TERM
= SAME SEMANTIC MEANING
ACROSS
CODE + DOCS + RECEIPTS + API + UI

MEANING CHANGE
=> NEW TERM OR NEW VERSION
```

## Semantic ownership

One semantic meaning MUST have:

```text
one canonical term
+ one authoritative definition
+ one contract identity/version lineage
```

A provider-specific label MAY exist behind a Module boundary, but any V-One-facing semantic surface MUST translate it into the canonical VOP term or an explicitly versioned subtype.

A UI-friendly label MAY be localized or shortened only when it maps unambiguously to the same canonical semantic identity. It MUST NOT silently merge Approval with Authorization, Execution with Verification, Observation with VerificationResult, Release with Deploy, or any other distinct VOP concepts.

## Versioning rule

Adding a new term without changing existing meanings MAY extend `vop-canonical-vocabulary/v1` under a new content revision and digest.

Changing an existing term's semantic meaning MUST NOT mutate that meaning in place. The change requires either:

- a new canonical term; or
- a new versioned contract identity.

Historical identities remain reserved for auditability and MUST NOT be silently reinterpreted.

### ExecutionGrant lineage

`execution-grant/v1` remains a historical deterministic value-contract identity.

The current authoritative runtime execution authority is:

```text
execution-grant/v2
```

Any active documentation that describes the current authoritative Grant as `execution-grant/v1` is terminology drift.

## Phase-C authority correction

Grant consumption is owned by the released control-plane lineage before dispatch:

```text
AuthorizationSnapshot
  -> ExecutionGrant/v2
  -> GrantConsumptionWitness/v1
  -> DispatchOutboxEntry/v1
  -> DispatchEnvelope/v1
  -> DispatchInboxAdmission/v1
  -> ExecutionEpoch + ExecutionLease/v1
  -> Runner
```

Therefore:

```text
Runner != Grant issuer
Runner != Grant consumer
Runner != Authorization authority
```

The Runner executes an already-authorized capability under the durable current dispatch/lease lineage. It MUST NOT re-consume a Grant or create another authority lineage.

## SandCloud correction

The historical ADR-0013 phrase that treated `SandCloud` as the provider-neutral name for the isolated execution boundary is superseded by this ADR.

Canonical meanings are now:

### SandCloud

Governed **non-canonical staging, review, validation and evidence layer**. SandCloud is not the execution boundary and does not create authorization.

### CASTER-MINAL

Governed execution control surface that hands an already-authorized operation plan to an eligible isolated Runner. CASTER-MINAL does not create authorization.

### Runner

The isolated execution principal governed by V-One runtime contracts.

Thus:

```text
SandCloud != Runner
SandCloud != CASTER-MINAL
CASTER-MINAL != Authorization authority
Runner != Verifier
```

## Phase C-E2 reconciliation

The VOP schema registry MUST reserve the current public contract identities introduced by released Phase C-D and the canonical E1/E2 track, including:

```text
execution-grant/v2
grant-consumption-witness/v1
dispatch-outbox-entry/v1
dispatch-inbox-admission/v1
execution-lease/v1
runner-identity/v1
runner-boundary/v1
credential-access-decision/v1
isolated-runtime-bootstrap/v1
read-only-runtime-activation/v1
github-ref-observation/v1
verifier-identity/v1
independent-verification-boundary/v1
verifier-credential-policy/v1
verifier-credential-decision/v1
verification-result/v1
```

Registry presence reserves semantic identity only. It does not claim implementation, successful execution, independent verification, release, deployment or production authority.

## Non-conflation rules

The following distinctions remain mandatory:

```text
APPROVE != AUTHORIZE
AUTHORIZE != ISSUE
ISSUE != DISPATCH
DISPATCH != EXECUTE
EXECUTE != VERIFY
VERIFY != ATTEST
RELEASE != DEPLOY

AuthorizationSnapshot != ExecutionGrant
ExecutionGrant != ExecutionCapsule
ExecutionReceipt != VerificationResult
Observation != VerificationResult
VerificationResult != OperationProof
RunnerIdentity != VerifierIdentity
Runner != Verifier
```

## Drift gate

CI MUST expose a named **VOP terminology drift gate**.

The gate MUST fail closed when the machine vocabulary, schema registry, canonical documentation or known released contract identities disagree on canonical semantic identity/version lineage.

Static automation cannot infer every possible human-language semantic error. Therefore semantic compatibility review remains REQUIRED for public VOP changes, especially UI/API wording. The automated gate is a minimum enforcement layer, not a substitute for architecture review.

## Consequences

Positive:

- Phase E continues on the same language established by the trust-plane design;
- released Phase C-E2 contracts cannot silently drift away from the vocabulary registry;
- future provider modules, API surfaces, receipts and UI labels have one semantic owner;
- historical contract versions remain auditable instead of being rewritten;
- OperationProof can later depend on stable semantic identities.

Cost:

- new public VOP terms require registry and compatibility work;
- semantic changes require explicit versioning rather than convenient in-place renaming.

## Phase-E gate

E2 is canonical at `main@b9468d91f39ff04090e6d19d314b5e820e029913`.

E3 MUST NOT be treated as accepted until this terminology reconciliation is canonical on `main` and has passed the required READY-state exact-head CI gate against the E2 baseline.
