# VOODOO One — CURRENT PRODUCT STATE

> Living evidence-scoped snapshot. Live Git/GitHub, executed tests and runtime evidence outrank this
> document. Historical claims stay historical and are never upgraded by later success.

## Snapshot identity

```text
AS_OF: 2026-08-20
EXACT_LIVE_GIT_IDENTITY: QUERY_LIVE_GIT_DIRECTLY
RECONCILIATION_BASE_MAIN: 71a931b561faa93c8dd2e062b83559401143b1df
RECONCILIATION_CANDIDATE: PR #128 / feat/reconciliation-p0-p1-r1
VOP_SEMANTIC_REVISION_CANDIDATE: vop-terminology-freeze-r2
PRODUCT_VERSION: 0.9.0-rc2-dev
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

The exact candidate and live `main` identities must be queried directly. A retained SHA in this file is
never a self-updating claim about future repository state.

## Truth dimensions

Do not collapse these dimensions:

```text
CONTRACT / COMPONENT      = source implementation exists
PRODUCT_COMPOSED          = ProductComposition can own/use the component through the canonical path
DEFAULT_RUNTIME_ACTIVE    = the default application actually instantiates a provider runtime pack
LIVE_VERIFIED             = real runtime/provider evidence exists for the named scope
PRODUCT_SURFACED          = API/UI exposes the same semantics truthfully
RELEASED / DEPLOYED       = separately governed states
```

## Overall state

| Dimension | Current state |
|---|---|
| Technical trust-plane components | **STRONG / IMPLEMENTED** |
| Historical bounded-mutation operation atom | **VERIFIED** in F6b staging scope |
| Canonical ProductComposition trust-plane seam | **IMPLEMENTED CANDIDATE in PR #128** |
| Default provider runtime pack | **DISABLED / FAIL-CLOSED** |
| Canonical public operation API | **NOT YET SURFACED** |
| Capability→terminal profile authority | **IMPLEMENTED CANDIDATE; caller cannot strengthen profile** |
| Runtime/database-backed permission authority | **IMPLEMENTED CANDIDATE** |
| READ Runner→independent Verifier terminal | **IMPLEMENTED CANDIDATE; live pilot primitives already VERIFIED** |
| Reusable CREATE_REF WRITE orchestration | **IMPLEMENTED PRE-EFFECT ONLY; NOT EXECUTED** |
| Reusable DELETE_REF rollback orchestration | **IMPLEMENTED PRE-EFFECT ONLY; NOT EXECUTED** |
| Canonical VOP language | **R2 RECONCILIATION CANDIDATE** |
| UI receipt/verification truth | **FIXED IN PR #128; final exact-head gate pending** |
| SQLite persistence | **IMPLEMENTED through schema 13** |
| OperationProof/v2 | **IMPLEMENTED bounded-mutation proof; historical F6b instance VERIFIED** |
| OperationCell/v1 | **IMPLEMENTED bounded-mutation atom; historical F6b instance VERIFIED** |
| Security Intelligence R-SI1.1 | **IMPLEMENTED intelligence-only layer** |
| GitHub main ruleset enforcement | **UNKNOWN / RELEASE BLOCKER** |
| Production release/effects | **BLOCKED** |
| CyberCore | **BLOCKED until final reconciliation closure** |

## Canonical shared authority/execution prefix

PR #128 now contains a reusable canonical prefix:

```text
ReviewedOperation
→ Approval / ApprovalCertificate
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ GrantConsumptionWitness/v1          [CONTROL PLANE ONLY]
→ DispatchOutboxEntry/v1
→ DispatchEnvelope/v1
→ DispatchInboxAdmission/v1
→ ExecutionEpoch + ExecutionLease/v1
→ ExecutionCapsule/v1
→ profile-specific terminal
```

`CanonicalOperationPipeline.prepare()` stops before Runner/provider effect and retains exact bound
runtime objects for the terminal router. Grant consumption remains control-plane-before-Dispatch;
Runner never issues or consumes ExecutionGrant.

## Capability-bound terminal selection

Terminal strength is no longer a caller-selected argument. An immutable registry binds the exact
`capability_definition_identity` and capability name to one allowed terminal profile.

```text
capability_definition_identity
→ immutable allowlist binding
→ terminal profile
```

A caller cannot request `BOUNDED_MUTATION_VERIFIED` for a READ capability or otherwise strengthen the
profile by supplying a stronger string to `CanonicalOperationPipeline.prepare()`.

## Runtime permission authority

`DatabasePermissionAuthority` is the current candidate permission source for canonical product
composition. It reads current user/workspace state from the same ProductService database for every
permission decision, including current role and active state. A stale in-memory `Principal` therefore
does not retain a stronger permission after the backing role/state changes.

`ProductComposition` owns this database-backed authority. A canonical runtime factory is rejected if
it attempts to use another database or another permission-authority instance.

## ProductComposition reality

PR #128 now wires the trust-plane seam into `ProductComposition` rather than leaving it as a detached
pre-effect helper:

```text
ProductService database
        ↓
DatabasePermissionAuthority
        ↓
CanonicalOperationPipeline
        ↓
CanonicalOperationRuntime
        ├── READ_ONLY_VERIFIED → CanonicalGitHubReadTerminal
        └── BOUNDED_MUTATION_VERIFIED
             ├── CREATE_REF → A09CreateRefPreparer
             └── DELETE_REF → A09RollbackPreparer
```

The canonical runtime is supplied through an explicit runtime factory and must share the exact
ProductService database and permission authority. Without that explicit provider/runtime pack,
`canonical_operation_runtime` remains `None`. This is intentional fail-closed behavior, not a hidden
fallback to legacy authority or ambient GitHub credentials.

Legacy `ExecutionService` remains an explicit existing API compatibility surface. The canonical VOP
runtime is now product-composable, but a new public HTTP operation endpoint has not been claimed.

## Canonical terminal profiles — R2

### READ-only verified

```text
READ_ONLY_VERIFIED
Runner Observation
→ independent Verifier Observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1 = VERIFIED
```

`CanonicalGitHubReadTerminal` composes the accepted D4b Runner and E3/E4b independent-verifier
contracts. READ terminates at `VerificationResult/v1`.

```text
ExecutionReceipt/v2 = NOT_APPLICABLE
OperationProof/v2   = NOT_APPLICABLE
OperationCell/v1    = NOT_APPLICABLE
```

### Bounded mutation verified

The semantic terminal remains:

```text
BOUNDED_MUTATION_VERIFIED
bounded provider mutation
→ ExecutionReceipt/v2                  [verification_status=NOT_EVALUATED]
→ independent readback
→ VerificationResult/v1 = VERIFIED
→ OperationProof/v2
→ OperationCell/v1
```

PR #128 does **not** execute this terminal. It adds reusable A09 preparation that ends immediately
before a separately authorized provider effect.

### A09 CREATE_REF preparation

```text
CanonicalPreparedExecution
→ exact capability/capsule/handler evidence
→ ControlledWriteRequirement
→ write Runner identity/boundary
→ scoped credential decision metadata
→ runtime activation metadata
→ exact target binding/request
→ WriteEffectPreflight/v1
→ STOP
```

There is no provider transport, credential secret, `create_ref()` invocation or historical PR120/SHA
hard-bind in the A09 orchestration.

### A09 rollback preparation

```text
CanonicalPreparedExecution
→ exact rollback capability/capsule/handler evidence
→ current target provenance
→ rollback condition/requirement
→ rollback Runner identity/boundary
→ scoped credential decision metadata
→ current pre-delete observation
→ current fence recheck
→ RollbackWriteEffectPreflight/v2
→ STOP
```

There is no `DELETE_REF` provider call. Rollback remains a separately authorized future effect.

Mandatory non-conflation:

```text
Approval != Authorization
ExecutionGrant != ExecutionCapsule
ExecutionReceipt != VerificationResult
execution succeeded != VERIFIED
VerificationResult != OperationProof
OperationProof != OperationCell
Evidence-chain integrity != independent verification
Preflight != provider effect
Prepared rollback != rollback execution
Release != Deploy
```

## Component inventory

| Layer | Component | Product composed | Live evidence |
|---|---|---|---|
| Review/approval | IMPLEMENTED | legacy product path | local/system |
| AuthoritativeSnapshotCreator | IMPLEMENTED | canonical runtime factory seam | component tests |
| ExecutionGrant/v2 + durable store | IMPLEMENTED | canonical runtime factory seam | component tests |
| Grant consumption + transactional outbox | IMPLEMENTED | canonical pipeline | component/pilot |
| Dispatch envelope + durable inbox/dedup | IMPLEMENTED | canonical pipeline | component/pilot |
| ExecutionEpoch/Lease + DurableCoordinator | IMPLEMENTED | canonical pipeline | component/pilot |
| Capability terminal allowlist | IMPLEMENTED | canonical pipeline | system tests |
| Database permission authority | IMPLEMENTED | ProductComposition | system tests |
| Capsule / Runner identity/boundary | IMPLEMENTED | profile terminals | pilot/tests |
| READ runtime activation | IMPLEMENTED | CanonicalGitHubReadTerminal | D4b |
| Independent verifier / VerificationResult | IMPLEMENTED | CanonicalGitHubReadTerminal | E3/E4b/F6b |
| Bounded CREATE_REF | IMPLEMENTED | A09 pre-effect preparer | historical F4b; no new execution |
| Bounded DELETE_REF rollback | IMPLEMENTED | A09 pre-effect preparer | historical F6b; no new execution |
| ExecutionReceipt/v2 | IMPLEMENTED | post-effect mutation lineage only | historical F6b |
| OperationProof/v2 | IMPLEMENTED | post-verification mutation lineage only | historical F6b |
| OperationCell/v1 | IMPLEMENTED | post-proof mutation lineage only | historical F6b |
| Canonical operation runtime router | IMPLEMENTED | ProductComposition optional runtime pack | tests; final exact-head gate pending |

## Historical F6b mutation evidence

Historical F6b run `32213563750` records one complete bounded staging operation:

```text
provider operation = DELETE_REF
provider mutation count = 1
automatic retry = false
rollback = true
Runner readback = ABSENT
independent verifier readback = ABSENT
VerificationResult = VERIFIED / OBSERVED_STATE_MATCH
OperationProof/v2 = 40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718
OperationCell/v1  = 2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
```

This historical evidence does not authorize or prove any new A09 provider mutation.

## CI / readiness state

The final reconciliation candidate is not considered closed until one exact head has all of:

```text
full CI = SUCCESS
D4b = SUCCESS
E3 = SUCCESS
E4b = SUCCESS
R3 adversarial review = completed
reconciliation audit = completed
```

Intermediate green runs are useful regression evidence but do not attest later candidate commits.
The product-readiness inventory now includes the canonical runtime, terminal allowlist, DB permission
authority and A09 modules/tests so those layers cannot silently fall outside future readiness checks.

## UI truth

PR #128 changes evidence UI so hash-chain integrity is `PASS/FAIL` and a receipt's independent
verification is `UNKNOWN` unless an actual VerificationResult binding is exposed. Receipt existence
must never render `VERIFIED` by itself.

## GitHub governance

Repository policy requires PR-only `main`, latest-head checks, no force push/delete and conversation
resolution. Available evidence does not prove complete modern ruleset enforcement; successful CI is
not Settings/ruleset evidence.

```text
GITHUB_SETTINGS_ENFORCED = UNKNOWN
RELEASE_BLOCKER = YES
```

## Governance history

- Engineering operating standard remains hash-bound to
  `36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed`.
- Historical PR #125 technical merge/post-state is VERIFIED; separate pre-merge merge-authorization
  provenance remains **NOT VERIFIED** and is not rewritten.
- ADR-0018 records the R2 terminal-profile correction instead of silently rewriting older history.

## CyberCore boundary

CyberCore remains intelligence/context/proposal only and is still blocked. It cannot issue
ExecutionGrant, consume grants, become Runner/Verifier, execute provider effects or become proof
evidence by inference.

CyberCore may proceed only after final exact-head gates and the new reconciliation audit are closed.

## Release boundary

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
RELEASED=NO
DEPLOYED=NO
UNRESTRICTED_PRODUCTION=BLOCKED
```

## Next governed sequence

```text
final source/docs/readiness convergence
→ one fresh exact-head CI + D4b/E3/E4b set
→ R3 adversarial review
→ complete reconciliation audit
→ separate merge authorization gate
→ CyberCore only after reconciliation PASS
```
