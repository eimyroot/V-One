# VOODOO One Architecture

| Field | Value |
|---|---|
| Document status | Accepted descriptive architecture / reconciliation candidate |
| Reconciled | `2026-08-20` against `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| VOP semantic candidate | `vop-terminology-freeze-r2` / ADR-0018 |
| Current packaging | Modular monolith + separately exercised isolated pilot runtimes |
| Current composition | Deep trust-plane components exist; one canonical FastAPI orchestration is still partial |
| Production effects | BLOCKED / disabled by default |

## Purpose

V-One owns governance and trust semantics for consequential operations:

- exact reviewed intent;
- policy/approval evidence;
- immutable AuthorizationSnapshot;
- narrow one-time ExecutionGrant;
- durable control-plane grant consumption;
- dispatch/coordination/fencing;
- bounded Runner execution;
- independent post-state verification;
- profile-correct portable evidence.

It does not turn intelligence, transport, execution success or evidence integrity into stronger
authority/verification by inference.

## Current system context

```text
Operator / AI proposal / CyberCore intelligence
                    |
                    v
             FastAPI product boundary
                    |
        +-----------+-----------+
        |                       |
        v                       v
legacy composed product    current VOP trust-plane
ExecutionService           contracts + durable services
        |                       |
        |                       v
        |             authority / dispatch / lease
        |                       |
        |                       v
        |                bounded Runner
        |                       |
        |                       v
        |             profile-specific evidence tail
        |                       |
        +---- composition convergence still required ----+

SQLite persistence: migrations 0001–0013
```

The technical gap is composition, not absence of the core contracts.

## Canonical shared authority/execution prefix

```text
ReviewedOperation
→ Approval / ApprovalCertificate
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ GrantConsumptionWitness/v1          [CONTROL PLANE]
→ DispatchOutboxEntry/v1
→ DispatchEnvelope/v1
→ DispatchInboxAdmission/v1
→ ExecutionEpoch + ExecutionLease/v1
→ ExecutionCapsule/v1
→ RunnerIdentity + RunnerBoundary
→ CredentialAccessDecision
→ RuntimeActivation
→ Provider effect / Observation
```

One-time grant consumption occurs **before Dispatch in the control plane**. Runner authority is
`bounded_execution_only`; Runner never issues or consumes grants.

## Terminal profiles

The shared prefix has typed evidence terminals. `OPERATION_STAGES` is a semantic superset, not one
mandatory path.

### READ-only verified

```text
READ_ONLY_VERIFIED
Runner Observation
→ independent Verifier Observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

This profile currently terminates at `VerificationResult/v1`.

### Bounded mutation verified

```text
BOUNDED_MUTATION_VERIFIED
bounded provider mutation
→ ExecutionReceipt/v2                 [verification_status=NOT_EVALUATED]
→ independent Verifier readback
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

`ExecutionReceipt/v2` and `OperationProof/v2` require exactly one bounded provider mutation and no
automatic mutation retry. They are specialized current mutation-lineage contracts, not universal
replacement contracts for READ or every historical v1 lineage.

## Current components

### Product surface

- FastAPI `/api/v1`;
- local authentication/session/RBAC/workspaces/change requests/approvals;
- static console;
- emergency stop/evidence/health;
- legacy `ExecutionService` remains product-composed.

PR #128 corrects the Evidence UI so ledger integrity uses `PASS/FAIL` and raw receipt verification
fails closed to `UNKNOWN` unless an actual independent VerificationResult is exposed.

### VOP machine language

Authorities:

- `voodoo_product/vop_vocabulary.py`;
- `schemas/vop/registry.v1.json`;
- human projection `docs/architecture/VOP_CANONICAL_VOCABULARY.md`.

R2 adds explicit `operation_terminal_profiles` and `schema_compatibility`. Only true semantic
replacement belongs in `schema_supersessions`.

### Authority

Implemented/tested:

```text
AuthoritativeSnapshotCreator
→ AuthorizationSnapshot
→ AuthoritativeGrantIssuer / DurableGrantService
→ ExecutionGrant/v2
→ DurableDispatchOutboxService.consume_and_enqueue()
```

The atomic outbox service is the intended composition seam for ONE_TIME grant consumption and durable
handoff; ProductComposition must not call Runner-side consumption.

### Dispatch / coordination

```text
DispatchOutboxEntry/v1
→ DispatchEnvelope/v1
→ DurableDispatchInboxService
→ DispatchInboxAdmission/v1
→ DurableExecutionLeaseService
→ ExecutionEpoch + ExecutionLease/v1
→ NativeDurableCoordinator / CurrentExecutionFence
```

Migrations 0010–0013 persist the released SQLite grant/dispatch/coordination model.

### Runner

Source includes Capsule/RunnerIdentity/RunnerBoundary, credential decisions, runtime activation and
READ/write runtime boundaries. D4b provides real bounded GitHub READ evidence. E3/E4b exercise
separate verification identity/readback.

The current D3 `IsolatedRunnerAdapter` is READ-only. Historical write runtime has separate explicit
write-boundary/credential/effect-preflight contracts; those must not be collapsed into D3 READ by
configuration trickery.

### Receipt / verification / proof

```text
ExecutionReceipt != VerificationResult
VerificationResult != OperationProof
OperationProof != OperationCell
```

Receipt/v2 is bounded-write execution evidence only. `VerificationResult/v1` is independent provider
truth. Proof/v2 can only be created after canonical verification provenance recomputation. Cell/v1 can
only be trusted after canonical Proof/v2 recomputation through an accepted lineage composer.

Historical F6b produced:

```text
OperationProof/v2
40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718

OperationCell/v1
2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
```

That proves one bounded-mutation atom, not a universal READ terminal.

### Security Intelligence

R-SI1.1 is descriptive intelligence metadata only. It creates no VOP authority, execution or proof.

### Persistence

Released backend: SQLite schema 13 with immutable/checksum-verified migrations, central statements,
audit/receipt ledgers, snapshots, grants, outbox/inbox and execution epoch/lease state. PostgreSQL
remains fail-closed/unreleased.

## Historical runtime checkpoint

Latest retained full local runtime checkpoint:

```text
main@d57d37111b8bc9471a136b6c618aad8e920f1aff
archive SHA-256: 80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2
image ID: sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
```

It is historical evidence and does not attest later source trees.

## ProductComposition target

The next functional architecture is one shared composition with explicit terminal selection:

```text
FastAPI / governed operation entry
        ↓
review + approval
        ↓
AuthoritativeSnapshotCreator
        ↓
ExecutionGrant/v2
        ↓
atomic consume + outbox
        ↓
envelope + inbox admission
        ↓
epoch / lease / current fence
        ↓
bounded Runner
        ↓
terminal profile selector
        ├── READ_ONLY_VERIFIED → VerificationResult/v1
        └── BOUNDED_MUTATION_VERIFIED
             → ExecutionReceipt/v2
             → VerificationResult/v1
             → OperationProof/v2
             → OperationCell/v1
```

Composition rules:

1. reuse accepted authority contracts; no parallel v3 authority path;
2. no test/pilot fixture seeding in product runtime;
3. all durable transitions use released persistence services;
4. profile selection is explicit/fail-closed;
5. READ must not be coerced into mutation-only schemas;
6. provider effect activation remains separately authorized;
7. legacy ExecutionService remains explicit compatibility surface until replacement behavior is proven.

## Architectural invariants

1. Approval != Authorization.
2. AuthorizationSnapshot != ExecutionGrant.
3. Grant consumption is durable control-plane state before Dispatch.
4. Dispatch/Epoch/Lease coordinate but never widen authority.
5. Runner never issues/consumes grants or self-authorizes.
6. Current fence prevents stale completion/effect authority.
7. ExecutionReceipt != VerificationResult.
8. Runner and Verifier remain separated as required by the profile.
9. READ_ONLY_VERIFIED terminates at VerificationResult/v1 today.
10. Receipt/v2 and Proof/v2 remain bounded-mutation-specific.
11. Cell/v1 requires canonical Proof/v2 provenance.
12. Evidence-chain integrity != provider verification.
13. Unreleased backends fail closed.
14. Production effects remain disabled until separate authorization/release.
15. Documentation cannot upgrade capability state.

## GitHub governance boundary

Policy requires PR-only main, latest-head `ci / verify`, no force push/delete and conversation
resolution. Available connector evidence cannot prove the complete modern ruleset. Classic required
status enforcement was observed off, therefore enforcement remains `UNKNOWN / BLOCKED` rather than
inferred from CI success.

## CyberCore boundary

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

CyberCore remains blocked until the canonical composition, reusable governed write orchestration,
exact-head gates and final reconciliation audit pass.

## Related documents

- [`VISION.md`](VISION.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md)
- [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md)
- [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)
- [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md)
- [`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md)
- [`docs/adr/ADR-0018-vop-terminal-profiles-and-lineage-r2.md`](docs/adr/ADR-0018-vop-terminal-profiles-and-lineage-r2.md)
