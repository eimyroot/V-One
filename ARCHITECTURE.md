# VOODOO One Architecture

| Field | Value |
|---|---|
| Document status | Accepted descriptive architecture / current post-G7 baseline |
| Reconciled | `2026-08-24` after merged PR #140 on canonical `main` |
| VOP semantic revision | `vop-terminology-freeze-r2` / ADR-0018 |
| Current packaging | Modular monolith + explicit profile-specific runtime packs |
| Current composition | Canonical READ API + restart-safe runtime are ProductComposition-integrated; default provider runtime remains fail-closed |
| GitHub governance | G0 VERIFIED / PASS from retained live verifier evidence |
| Production effects | BLOCKED / disabled by default |

## Purpose

V-One owns governance and trust semantics for consequential operations:

- exact reviewed intent;
- policy/approval evidence;
- immutable AuthorizationSnapshot;
- narrow one-time ExecutionGrant;
- durable control-plane grant consumption;
- dispatch/coordination/fencing;
- capability-bound terminal selection;
- bounded Runner execution;
- independent post-state verification;
- restart-safe continuity;
- profile-correct portable evidence.

It does not turn intelligence, transport, execution success, preflight readiness or evidence integrity
into stronger authority/verification by inference.

## Current system context

```text
Operator / AI proposal / CyberCore intelligence
                    |
                    v
             FastAPI product boundary
                    |
        +-----------+-------------------+
        |                               |
        v                               v
legacy API compatibility         ProductComposition
ExecutionService                        |
                                ProductService database
                                        |
                                current user/role/active
                                + workspace membership
                                        |
                                DatabasePermissionAuthority
                                        |
                                CanonicalOperationPipeline
                                        |
                                CapabilityTerminalProfileRegistry
                                        |
                                CanonicalOperationRuntime
                                  /                \
                                 v                  v
                       READ verified terminal    A09 WRITE/rollback
                                 |                pre-effect only
                                 v
                     durable restart/resume
```

The canonical READ HTTP surface is merged. The canonical trust-plane runtime is a ProductComposition
seam and G7 restart-safe resume is integrated. The default application still does not silently
instantiate a provider runtime pack; without explicit G8 runtime dependencies it remains fail-closed.

## Canonical authority/execution prefix

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
→ capability-bound terminal profile
```

One-time grant consumption occurs **before Dispatch in the control plane**. Runner authority is
`bounded_execution_only`; Runner never issues or consumes grants.

`CanonicalOperationPipeline.prepare()` stops before any provider effect and returns exact bound runtime
objects for the selected terminal.

## Terminal profile authority

Terminal strength is not caller-controlled. The pipeline resolves an immutable binding from the exact
`capability_definition_identity` plus capability name to one allowed profile.

```text
CapabilityDefinition identity
        ↓
immutable terminal allowlist
        ↓
READ_ONLY_VERIFIED | BOUNDED_MUTATION_VERIFIED
```

The public G7 READ route narrows the accepted route to exactly `READ_ONLY_VERIFIED + github.read-ref/v1`.
Caller-supplied terminal-profile authority is rejected.

## Product permission authority

Canonical product composition uses `DatabasePermissionAuthority`, sharing the exact ProductService
database. Every decision rereads the current active user, global role permission set, exact workspace,
workspace environment and exact current user↔workspace membership. Stale in-memory principals,
role downgrades, deactivation and membership revocation therefore cannot preserve stronger canonical
authority.

Global role defines **what** permission is available. Membership defines **where** that permission may
be considered. Membership role (`owner`/`member`) is only a workspace-scope management primitive and
does not activate the separately PROPOSED Solo/Team/Regulated organization-policy model.

Migration `0014_workspace_memberships.sql` deliberately does not infer membership for historical
schema-13 workspaces. Upgraded legacy workspaces remain fail-closed for canonical permission decisions
until membership is explicitly recorded by an authorized administrator/owner.

A canonical runtime factory is rejected if it uses another database or another permission-authority
instance. G7 reconciliation additionally revalidates resume-service ownership of the canonical DB,
snapshot store, permission authority, terminal-profile registry, envelope revision and current fence.
This prevents compatibility/runtime/resume authority forks.

## Canonical public READ API

Merged PR #137 exposes:

```text
GET  /api/v1/operations/status
POST /api/v1/operations/{request_id}/read
```

PR #140 reconciles that HTTP surface with durable resume/runtime wiring. The API keeps execution and
independent verification separate and exposes no canonical CREATE_REF, DELETE_REF or rollback route.

A successful execution may truthfully end with:

```text
execution.status      = SUCCEEDED
verification.verdict  = NOT_VERIFIED
```

and must not be promoted to VERIFIED by transport success, receipts, or digest integrity.

## READ-only terminal

```text
READ_ONLY_VERIFIED
CanonicalPreparedExecution
→ isolated READ Runner
→ Runner GitHub observation
→ durable completion
→ independent verification boundary
→ separate verifier credential decision
→ independent GitHub observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

`CanonicalGitHubReadTerminal` reuses accepted D4b/E3/E4b contracts. READ currently terminates at
`VerificationResult/v1`.

```text
ExecutionReceipt/v2 = NOT_APPLICABLE
OperationProof/v2   = NOT_APPLICABLE
OperationCell/v1    = NOT_APPLICABLE
```

## Restart-safe durable resume

Merged PR #140 reconstructs an already-authorized execution from durable evidence after process
restart. Resume must not re-enter `CanonicalOperationPipeline.prepare()`, issue a second grant, consume
the grant again, append duplicate outbox/inbox admission, or reacquire a lease.

The resume boundary revalidates current DB permission, persisted snapshot/grant/consumption/supporting
witnesses, dispatch lineage, terminal profile, envelope revision and current execution fence. Corrupt,
missing, stale, ambiguous, expired or mismatched durable state fails closed.

## Bounded mutation terminal

The semantic completed terminal remains:

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
automatic mutation retry. They are specialized mutation-lineage contracts, not universal READ
contracts.

Current A09 orchestration is pre-effect only. G7 did not activate provider WRITE.

## A09 CREATE_REF pre-effect orchestration

```text
CanonicalPreparedExecution
→ exact definition/capsule/handler evidence
→ ControlledWriteRequirement
→ write Runner identity/boundary
→ scoped credential decision metadata
→ runtime activation metadata
→ exact target binding/request
→ current-fence checked WriteEffectPreflight/v1
→ STOP
```

Properties:

- no provider mutation transport in A09;
- no credential secret input/serialization;
- no `create_ref()` call;
- no historical PR120/ref/SHA hard-bind;
- one exact current authority/lease/target chain;
- a future provider effect remains a separate authorization boundary.

## A09 rollback pre-effect orchestration

```text
CanonicalPreparedExecution
→ exact rollback definition/capsule/handler evidence
→ rollback provenance/condition
→ rollback Runner identity/boundary
→ scoped rollback credential decision metadata
→ current pre-delete observation
→ current-fence recheck
→ RollbackWriteEffectPreflight/v2
→ STOP
```

Rollback preparation contains no GitHub DELETE transport and performs no provider mutation. Rollback
execution remains separately authorized.

## ProductComposition

`ProductComposition` owns:

- ProductService and its shared evidence/persistence services;
- `DatabasePermissionAuthority`;
- optional `CanonicalOperationRuntime` produced by an explicit runtime factory.

The canonical runtime factory must use the exact ProductService database and permission authority.
Without a runtime factory, `canonical_operation_runtime=None` is intentional fail-closed behavior.
Legacy `ExecutionService` remains an explicit API compatibility surface; it is not canonical fallback
authority for the merged public READ API.

The next G8 target is deliberately a **READ-only composition factory** over the existing
`GitHubReadTransport`, `CanonicalGitHubReadTerminal`, canonical pipeline and resume contracts. It must
not introduce a parallel execution framework, ambient credential fallback, generic provider client, or
mutation transport.

## VOP machine language

Authorities:

- `voodoo_product/vop_vocabulary.py`;
- `schemas/vop/registry.v1.json`;
- `voodoo_product/terminal_profile.py` for exact capability→profile bindings;
- human projection `docs/architecture/VOP_CANONICAL_VOCABULARY.md`.

R2 carries explicit `operation_terminal_profiles` and narrow compatibility rules. Only true semantic
replacement belongs in `schema_supersessions`.

## Persistence

Current released backend remains SQLite schema 14 with immutable/checksum-verified migrations, central
statements, audit/receipt ledgers, snapshots, grants, outbox/inbox, execution epoch/lease state and
explicit workspace membership scope. PostgreSQL remains fail-closed/unreleased.

## Historical verified mutation atom

Historical F6b produced one complete bounded staging atom:

```text
OperationProof/v2
40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718

OperationCell/v1
2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
```

That historical evidence does not prove or authorize a new A09 provider effect.

## Architectural invariants

1. Approval != Authorization.
2. AuthorizationSnapshot != ExecutionGrant.
3. Grant consumption is durable control-plane state before Dispatch.
4. Dispatch/Epoch/Lease coordinate but never widen authority.
5. Runner never issues/consumes grants or self-authorizes.
6. Terminal profile strength is derived from immutable capability identity, not caller choice.
7. Current database role + active state + exact workspace membership, not stale Principal memory, are canonical permission authority inputs.
8. Global role permission never implies membership in an arbitrary workspace.
9. Historical workspace activity never fabricates schema-14 membership.
10. Current fence prevents stale completion/effect authority.
11. ExecutionReceipt != VerificationResult.
12. Runner and Verifier remain separated as required by the profile.
13. READ_ONLY_VERIFIED terminates at VerificationResult/v1 today.
14. Receipt/v2 and Proof/v2 remain bounded-mutation-specific.
15. Cell/v1 requires canonical Proof/v2 provenance.
16. Preflight != provider effect.
17. Prepared rollback != rollback execution.
18. Evidence-chain integrity != provider verification.
19. Restart/resume cannot mint new authority or duplicate dispatch/lease state.
20. Unreleased backends/provider packs fail closed.
21. Provider WRITE remains blocked until the governed READ-before-WRITE evidence gate and a later effect-specific authorization are satisfied.
22. Production effects remain disabled until separate authorization/release.
23. Documentation cannot upgrade capability state.

## GitHub governance boundary

G0 is bound to retained live verifier evidence:

```text
workflow = g0-governance-verify
run = 32553113424
source_sha = 76d74d2ed62b6e78f027728c456c22da0b4a95bd
artifact = g0-governance-evidence-32553113424-1
artifact_digest = sha256:6e63caee23a57613471df66ef0279c0261ed8d375e4c929accdf50eff7dc4f5f
verdict = VERIFIED
```

That evidence established PR-only main, required latest-head `verify` from workflow `ci`, force-push
and deletion protection, conversation resolution, no ordinary bypass, active rulesets and verifier
source binding. G0 is PASS. This is repository-governance evidence only; it does not authorize provider
runtime, release or deployment.

## READ-before-WRITE boundary

ADR-0019 is `PROPOSED` until its governed adoption gate closes. The proposed invariant requires repeated
real canonical authenticated HTTP READ E2E, independent `VerificationResult/v1`, restart-safe durable
resume, no duplicate authority/effect, authority continuity and fail-closed failure injection before
WRITE may become merely `ELIGIBLE`. `ELIGIBLE` is not effect authorization.

## CyberCore boundary

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

CyberCore remains blocked while product/release-governance hardening is incomplete. It cannot be used
to bypass G8, READ E2E, WRITE, release, or deployment gates.

## Related documents

- [`VISION.md`](VISION.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md)
- [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md)
- [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)
- [`docs/product/POST_G7_CANONICAL_STATE.md`](docs/product/POST_G7_CANONICAL_STATE.md)
- [`docs/product/G8_READ_RUNTIME_GATE.md`](docs/product/G8_READ_RUNTIME_GATE.md)
- [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md)
- [`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md)
- [`docs/adr/ADR-0018-vop-terminal-profiles-and-lineage-r2.md`](docs/adr/ADR-0018-vop-terminal-profiles-and-lineage-r2.md)
- [`docs/adr/ADR-0019-read-e2e-before-write.md`](docs/adr/ADR-0019-read-e2e-before-write.md)
