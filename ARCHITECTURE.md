# VOODOO One Architecture

| Field | Value |
|---|---|
| Document status | Accepted descriptive architecture / reconciliation candidate |
| Reconciled | `2026-08-20` against `main@71a931b561faa93c8dd2e062b83559401143b1df` plus PR #128 candidate |
| VOP semantic candidate | `vop-terminology-freeze-r2` / ADR-0018 |
| Current packaging | Modular monolith + explicit profile-specific runtime packs |
| Current composition | Canonical trust-plane runtime is ProductComposition-capable; default provider runtime remains fail-closed |
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
                                                pre-effect only
```

The canonical trust-plane runtime is now a ProductComposition seam. The default application does not
silently instantiate a provider runtime pack; without explicit runtime dependencies it remains
fail-closed.

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

The caller cannot pass a stronger `terminal_profile` argument to `prepare()`.

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
instance. This prevents a compatibility/runtime authority fork.

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

PR #128 does not execute a new mutation. It adds reusable A09 preparation seams.

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
Legacy `ExecutionService` remains an explicit API compatibility surface until canonical public
operation endpoints are separately introduced and proven.

## VOP machine language

Authorities:

- `voodoo_product/vop_vocabulary.py`;
- `schemas/vop/registry.v1.json`;
- `voodoo_product/terminal_profile.py` for exact capability→profile bindings;
- human projection `docs/architecture/VOP_CANONICAL_VOCABULARY.md`.

R2 carries explicit `operation_terminal_profiles` and narrow compatibility rules. Only true semantic
replacement belongs in `schema_supersessions`.

## Persistence

Released backend remains SQLite schema 14 with immutable/checksum-verified migrations, central
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
19. Unreleased backends/provider packs fail closed.
20. Production effects remain disabled until separate authorization/release.
21. Documentation cannot upgrade capability state.

## GitHub governance boundary

Policy requires PR-only main, latest-head checks, no force push/delete and conversation resolution.
Available connector evidence cannot prove the complete modern ruleset. Successful Actions runs are not
ruleset-enforcement evidence, therefore GitHub settings enforcement remains `UNKNOWN / RELEASE
BLOCKER`.

## CyberCore boundary

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

CyberCore remains blocked until final exact-head gates and the new reconciliation audit pass.

## Related documents

- [`VISION.md`](VISION.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md)
- [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md)
- [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)
- [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md)
- [`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md)
- [`docs/adr/ADR-0018-vop-terminal-profiles-and-lineage-r2.md`](docs/adr/ADR-0018-vop-terminal-profiles-and-lineage-r2.md)
