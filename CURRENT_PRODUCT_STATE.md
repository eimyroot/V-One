# VOODOO One — CURRENT PRODUCT STATE

> Living evidence-scoped snapshot. Live Git/GitHub, executed tests and runtime evidence outrank this
> document. Historical claims stay historical and are never upgraded by later success.

## Snapshot identity

```text
AS_OF: 2026-08-23
EXACT_LIVE_GIT_IDENTITY: QUERY_LIVE_GIT_DIRECTLY
RECONCILIATION_INPUT_HEAD: 71a931b561faa93c8dd2e062b83559401143b1df
RECONCILIATION_BASE_MAIN: 71a931b561faa93c8dd2e062b83559401143b1df
RECONCILIATION_MERGE: PR #128 / d9e27ff17b76f29daba4a3421b11cc396826fe12
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@d57d37111b8bc9471a136b6c618aad8e920f1aff
VOP_SEMANTIC_REVISION: vop-terminology-freeze-r2
PRODUCT_VERSION: 0.9.0-rc2-dev
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

The exact live `main` identity must be queried directly. Retained SHAs in this file are historical or
merge provenance and are never self-updating claims about future repository state.

## Historical checkpoint boundary

The latest retained full runtime-attested checkpoint remains historical evidence for exactly
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`:

```text
POST_MERGE_CHECKPOINT_ZIP_SHA256=80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2
POST_MERGE_CHECKPOINT_IMAGE_ID=sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
```

Historical documentation-review merge `57c7bf2277616c4445039865ac7cf81c5fada858` remains ADR-0008
evidence-index provenance only; it is not the current Git baseline.

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
| Canonical ProductComposition trust-plane seam | **IMPLEMENTED / MERGED via PR #128** |
| Default provider runtime pack | **DISABLED / FAIL-CLOSED** |
| Canonical public operation API | **IMPLEMENTED CANDIDATE / PR #137 / READ-only; exact-head closure pending** |
| Capability→terminal profile authority | **IMPLEMENTED / MERGED; caller cannot strengthen profile** |
| Runtime/database-backed permission authority | **IMPLEMENTED / MERGED; current role + active state + workspace membership** |
| Workspace membership scope | **IMPLEMENTED / MERGED; schema 14, no legacy inference/backfill** |
| READ Runner→independent Verifier terminal | **IMPLEMENTED / MERGED; live pilot primitives already VERIFIED** |
| Reusable CREATE_REF WRITE orchestration | **IMPLEMENTED PRE-EFFECT ONLY; NOT EXECUTED** |
| Reusable DELETE_REF rollback orchestration | **IMPLEMENTED PRE-EFFECT ONLY; NOT EXECUTED** |
| Canonical VOP language | **R2 CURRENT / MERGED** |
| UI receipt/verification truth | **FIXED / MERGED; exact-head closure passed** |
| SQLite persistence | **IMPLEMENTED through schema 14** |
| OperationProof/v2 | **IMPLEMENTED bounded-mutation proof; historical F6b instance VERIFIED** |
| OperationCell/v1 | **IMPLEMENTED bounded-mutation atom; historical F6b instance VERIFIED** |
| Security Intelligence R-SI1.1 | **IMPLEMENTED intelligence-only layer** |
| Security Intelligence R-SI1.2 normalization | **IMPLEMENTED / MERGED via PR #135; descriptive/context-only** |
| GitHub G0 automation | **IMPLEMENTED / MERGED via PR #134; live enforcement still requires VERIFIED evidence** |
| GitHub main ruleset enforcement | **UNKNOWN/BLOCKED until fresh G0 verifier result is VERIFIED** |
| Production release/effects | **BLOCKED** |
| CyberCore | **BLOCKED pending product/release-governance hardening** |

## Canonical shared authority/execution prefix

Merged PR #128 established a reusable canonical prefix:

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

G7 additionally allows an internal route constraint (`required_terminal_profile` +
`required_capability`). This does not create/select authority: the snapshot and immutable capability
allowlist still derive the actual values. A mismatch only narrows the accepted route and now fails
before Grant issuance/consumption.

## Capability-bound terminal selection

Terminal strength is not a caller-selected argument. An immutable registry binds the exact
`capability_definition_identity` and capability name to one allowed terminal profile.

```text
capability_definition_identity
→ immutable allowlist binding
→ terminal profile
```

A caller cannot request `BOUNDED_MUTATION_VERIFIED` for a READ capability or otherwise strengthen the
profile. The G7 HTTP body uses `extra=forbid`, so a caller-supplied `terminal_profile` is rejected before
the canonical runtime is invoked.

## Runtime permission authority

`DatabasePermissionAuthority` is the current permission source for canonical product composition.
Every permission decision re-reads the same ProductService database and requires the current active
user, current global role permissions, exact workspace/environment and an exact current user↔workspace
membership. A stale in-memory `Principal`, a later role downgrade, deactivation or membership
revocation therefore cannot preserve stronger canonical authority.

Global role still answers **what** a principal may do; current membership answers **where** that
permission may be considered. Membership role (`owner`/`member`) controls membership management and
does not activate the separately PROPOSED Solo/Team/Regulated organization-policy semantics.
Migration `0014_workspace_memberships.sql` deliberately does not infer memberships for historical
schema-13 workspaces; upgraded legacy workspaces remain fail-closed until an administrator records
membership explicitly.

`ProductComposition` owns this database-backed authority. A canonical runtime factory is rejected if
it attempts to use another database or another permission-authority instance.

## ProductComposition reality

Merged PR #128 wires the trust-plane seam into `ProductComposition` rather than leaving it as a
detached pre-effect helper:

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

Legacy `ExecutionService` remains an explicit existing API compatibility surface. G7 exposes the
canonical READ operation surface separately; the legacy execute route is not treated as canonical
fallback authority.

## G7 canonical public Operation API candidate

PR #137 adds the candidate public surface:

```text
GET  /api/v1/operations/status
POST /api/v1/operations/{request_id}/read
```

The candidate has these boundaries:

- same configured product `IdentityProvider` at the HTTP boundary;
- `execution.run` is required before entering the READ route;
- authoritative current role/active/workspace/membership permission is still revalidated inside the
  canonical trust-plane runtime;
- `Idempotency-Key` is mandatory and correlation id is bounded;
- unknown body fields are forbidden, including any attempted terminal-profile injection;
- READ internally requires `READ_ONLY_VERIFIED + github.read-ref/v1` before Grant issuance;
- missing READ terminal fails before snapshot/grant preparation;
- successful execution and independent verification are separate response objects;
- `execution.status=SUCCEEDED` may truthfully coexist with `verification.verdict=NOT_VERIFIED`;
- no canonical CREATE_REF, DELETE_REF or rollback HTTP route exists;
- no provider WRITE transport/effect is added by G7.

The API being surfaced does not mean a provider runtime is active. Without the separately governed G8
runtime pack, status reports unconfigured/fail-closed state and READ execution is unavailable rather
than using ambient credentials or the legacy path.

## Canonical terminal profiles — R2

### READ-only verified

```text
READ_ONLY_VERIFIED
Runner Observation
→ independent Verifier Observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

`CanonicalGitHubReadTerminal` composes the accepted D4b Runner and E3/E4b independent-verifier
contracts. READ terminates at `VerificationResult/v1`. A real result may be `VERIFIED` or
`NOT_VERIFIED`; execution success alone never sets that verdict.

```text
ExecutionReceipt/v2 = NOT_APPLICABLE
OperationProof/v2   = NOT_APPLICABLE
OperationCell/v1    = NOT_APPLICABLE
```

### Bounded mutation verified

The semantic completed terminal remains:

```text
BOUNDED_MUTATION_VERIFIED
bounded provider mutation
→ ExecutionReceipt/v2                  [verification_status=NOT_EVALUATED]
→ independent readback
→ VerificationResult/v1 = VERIFIED
→ OperationProof/v2
→ OperationCell/v1
```

Merged PR #128 did **not** execute this terminal. It established reusable A09 preparation that ends
immediately before a separately authorized provider effect.

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
Public API != active provider runtime
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
| Workspace membership scope | IMPLEMENTED | DatabasePermissionAuthority | schema-14/membership tests; no live provider claim |
| Capsule / Runner identity/boundary | IMPLEMENTED | profile terminals | pilot/tests |
| READ runtime activation | IMPLEMENTED | CanonicalGitHubReadTerminal | D4b |
| Independent verifier / VerificationResult | IMPLEMENTED | CanonicalGitHubReadTerminal | E3/E4b/F6b |
| Canonical public READ API | IMPLEMENTED CANDIDATE | ProductComposition router / PR #137 | candidate tests; G8 runtime inactive |
| Bounded CREATE_REF | IMPLEMENTED | A09 pre-effect preparer | historical F4b; no new execution |
| Bounded DELETE_REF rollback | IMPLEMENTED | A09 pre-effect preparer | historical F6b; no new execution |
| ExecutionReceipt/v2 | IMPLEMENTED | post-effect mutation lineage only | historical F6b |
| OperationProof/v2 | IMPLEMENTED | post-verification mutation lineage only | historical F6b |
| OperationCell/v1 | IMPLEMENTED | post-proof mutation lineage only | historical F6b |
| Canonical operation runtime router | IMPLEMENTED | ProductComposition optional runtime pack | tests + PR #128 exact-head closure |

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

Merged PR #128 was gated on exact head `fcdd43578860bf8bf01f85b3f088bb5c6d21526c` with:

```text
CI #839 = SUCCESS
D4b #157 = SUCCESS
E3 #148 = SUCCESS
E4b #144 = SUCCESS
R3 self/adversarial review = PASS WITH OWNER-ACCEPTED INDEPENDENCE RISK
unresolved review threads = 0
```

Those exact-head results are historical merge evidence; later repository state must still be queried and
re-tested for later changes.

The current product-readiness inventory requires the canonical runtime, terminal allowlist, DB
permission authority, workspace membership boundary, A09 modules/tests, merged G0 governance verifier
artifacts and the G7 canonical HTTP surface/adversarial tests. PR #137 still requires its own fresh
exact-head closure before any merge claim.

## UI truth

Merged PR #128 changes evidence UI so hash-chain integrity is `PASS/FAIL` and a receipt's independent
verification is `UNKNOWN` unless an actual VerificationResult binding is exposed. Receipt existence
must never render `VERIFIED` by itself. G7 applies the same rule at the HTTP boundary by keeping
execution and verification in separate response objects.

## GitHub governance

Merged PR #134 provides the fail-closed G0 live verifier and evidence workflow. That is automation,
not proof that GitHub Settings currently satisfy the baseline.

```text
GITHUB_SETTINGS_ENFORCED = UNKNOWN/BLOCKED UNTIL FRESH VERIFIER RESULT = VERIFIED
RELEASE_BLOCKER = YES
```

Successful CI, branch metadata or repository documents are not a substitute for fresh live G0
evidence.

## Governance history

- Engineering operating standard remains hash-bound to
  `36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed`.
- Historical PR #125 technical merge/post-state is VERIFIED; separate pre-merge merge-authorization
  provenance remains **NOT VERIFIED** and is not rewritten.
- ADR-0018 records the R2 terminal-profile correction instead of silently rewriting older history.
- PR #128 reconciliation merge is recorded in CASER; organizationally independent R3 was absent and
  the remaining independence risk was explicitly accepted for that merge.

## CyberCore boundary

CyberCore remains intelligence/context/proposal only and is still blocked from implementation during
product/release-governance hardening. It cannot issue ExecutionGrant, consume grants, become
Runner/Verifier, execute provider effects or become proof evidence by inference.

Security Intelligence R-SI1.2 from merged PR #135 remains a descriptive normalization/context layer.
Open PR #136 is not part of the G7 critical path and is not treated as authority or runtime evidence.

## Release boundary

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
NEW_G7_PROVIDER_WRITE=NO
RELEASED=NO
DEPLOYED=NO
UNRESTRICTED_PRODUCTION=BLOCKED
```

## Next governed sequence

```text
fresh G0 live-enforcement evidence/fix
→ close G7 exact-head CI + adversarial review + separate merge gate
→ G8 explicit READ-first provider runtime pack, fail-closed
→ release-candidate/security/operations gates
→ deployment authorization only after release readiness
→ CyberCore integration only after V-One product baseline is stable
```
