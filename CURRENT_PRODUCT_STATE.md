# VOODOO One — CURRENT PRODUCT STATE

> Living evidence-scoped snapshot. Live Git/GitHub, executed tests and runtime evidence outrank this
> document for technical state. Historical claims remain available in Git history and CASER; they are
> superseded here rather than rewritten retroactively.

## Snapshot identity

```text
AS_OF: 2026-08-20
EXACT_LIVE_GIT_IDENTITY: QUERY_LIVE_GIT_DIRECTLY
RECONCILIATION_INPUT_HEAD: 71a931b561faa93c8dd2e062b83559401143b1df
RECONCILIATION_BASE_MAIN: 71a931b561faa93c8dd2e062b83559401143b1df
RECONCILIATION_BASE_TREE: 423e234757686f720de20decd762270c43e0a8bb
AUDIT: VONE_RECONCILIATION_AUDIT_20260819T2209Z
AUDIT_STATUS: RECONCILIATION_REQUIRED_TECHNICAL_CORE_STRONG_PRODUCT_TRUTH_DRIFT_FOUND
RECONCILIATION_CANDIDATE: PR #128 / feat/reconciliation-p0-p1-r1
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@d57d37111b8bc9471a136b6c618aad8e920f1aff
PRODUCT_VERSION: 0.9.0-rc2-dev
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

Exact live Git identity must still be queried directly. The reconciliation SHA is an immutable input
baseline, not a self-updating claim about future `main`.

## Historical runtime checkpoint boundary

The latest retained full local runtime-attested checkpoint remains historical development evidence for
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`:

```text
EVIDENCE_ARCHIVE: POST_MERGE_CHECKPOINT_20260802T152505Z_d57d37111b8b.zip
PRODUCT_IMAGE_ID: sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
```

It does **not** attest the later reconciliation baseline or later source changes. Those later trees
require their own commit-bound CI/pilot evidence.

## How status is represented

A V-One capability has separate dimensions. They MUST NOT be collapsed into one overloaded status:

```text
CONTRACT / COMPONENT      = source implementation exists
PRODUCT_COMPOSED          = canonical ProductComposition/API uses it
LIVE_VERIFIED             = real provider/runtime evidence exists for the stated scope
PRODUCT_SURFACED          = API/UI exposes the same semantics truthfully
RELEASED / DEPLOYED       = separately governed release/deployment state
```

`IMPLEMENTED` therefore never means automatically `PRODUCT_COMPOSED`, `VERIFIED`, `RELEASED` or
`DEPLOYED`.

## Overall state

| Dimension | Current state |
|---|---|
| Technical trust-plane component depth | **STRONG / IMPLEMENTED** |
| Historical complete governed operation atom | **VERIFIED** in staging F6b scope |
| Unified canonical product/API lifecycle | **PARTIAL / NOT YET COMPOSED** |
| Canonical VOP language | **RECONCILIATION IN PROGRESS** in PR #128 |
| Product UI verification truth | **RECONCILIATION IN PROGRESS** in PR #128 |
| SQLite persistence | **IMPLEMENTED / TESTED through schema 13** |
| Read-only isolated Runner pilot | **LIVE VERIFIED for bounded GitHub READ scope** |
| Independent verifier pilot | **LIVE VERIFIED for bounded GitHub READ scope** |
| Governed write/rollback | **HISTORICALLY VERIFIED pilot scope; not reusable current product entrypoint** |
| OperationProof/v2 | **IMPLEMENTED; historical F6b instance VERIFIED** |
| OperationCell/v1 | **IMPLEMENTED; historical F6b instance VERIFIED** |
| Security Intelligence R-SI1.1 | **IMPLEMENTED metadata/test layer; intelligence-only, not runtime authority** |
| GitHub main enforcement | **UNKNOWN / BLOCKED until live ruleset evidence proves baseline** |
| Production release/effects | **BLOCKED** |
| CyberCore integration | **BLOCKED until reconciliation and canonical product composition gates pass** |

## Canonical lifecycle reality

Current component/evidence architecture is:

```text
ReviewedOperation
→ Approval
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ GrantConsumptionWitness/v1       [CONTROL PLANE ONLY]
→ DispatchOutboxEntry/v1
→ DispatchEnvelope/v1
→ DispatchInboxAdmission/v1
→ ExecutionEpoch + ExecutionLease/v1
→ ExecutionCapsule/v1
→ RunnerIdentity + RunnerBoundary
→ CredentialAccessDecision
→ RuntimeActivation
→ Provider Effect / Observation
→ ExecutionReceipt/v2              [EXECUTION CLAIM, NOT VERIFICATION]
→ independent Verifier
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

Mandatory semantic boundaries:

```text
Approval != Authorization
ExecutionGrant != ExecutionCapsule
ExecutionReceipt != VerificationResult
Execution succeeded != VERIFIED
VerificationResult != OperationProof
OperationProof != OperationCell
Evidence-chain integrity != independent verification
Release != Deploy
```

Grant consumption belongs to the control plane before Dispatch. The Runner does not issue or consume
ExecutionGrants and does not create a parallel authorization lineage.

## Component inventory

| Layer | Contract/component | Tests | Product composed | Live evidence |
|---|---|---|---|---|
| Review/approval | IMPLEMENTED | YES | legacy product path | YES, local/system |
| AuthorizationSnapshot + AuthoritativeSnapshotCreator | IMPLEMENTED | YES | NO | component evidence |
| ExecutionGrant/v2 + durable grant persistence | IMPLEMENTED | YES | NO | component evidence |
| GrantConsumptionWitness + transactional Outbox | IMPLEMENTED | YES | NO | component/pilot evidence |
| Dispatch Envelope + durable Inbox/dedup | IMPLEMENTED | YES | NO | component/pilot evidence |
| ExecutionEpoch/Lease + DurableCoordinator | IMPLEMENTED | YES | NO | component/pilot evidence |
| ExecutionCapsule / RunnerIdentity / RunnerBoundary | IMPLEMENTED | YES | NO | pilot evidence |
| Credential decision / RuntimeActivation | IMPLEMENTED | YES | NO | pilot evidence |
| GitHub READ observation | IMPLEMENTED | YES | NO | D4b LIVE |
| Independent Verifier | IMPLEMENTED | YES | NO | E3 LIVE |
| VerificationResult/v1 | IMPLEMENTED | YES | NO | E4b + F6b LIVE |
| GitHub CREATE_REF path | IMPLEMENTED | YES | NO | historical F4b LIVE |
| GitHub DELETE_REF rollback path | IMPLEMENTED | YES | NO | historical F6b LIVE |
| ExecutionReceipt/v2 | IMPLEMENTED | YES | NO | F6b real receipt |
| OperationProof/v2 | IMPLEMENTED | YES | NO | F6b VERIFIED proof |
| OperationCell/v1 | IMPLEMENTED | YES | NO | F6b VERIFIED cell |
| Security Intelligence R-SI1.1 | IMPLEMENTED | YES | NO | metadata/test only |
| Unified lifecycle ProductComposition/API | NOT IMPLEMENTED | PARTIAL | N/A | NO |

The central remaining architecture task is therefore composition, not reimplementation of the already
accepted component contracts.

## Persistence reality

SQLite is the only released backend. Ordered immutable migrations are implemented through schema 13:

```text
0009 authorization_snapshots
0010 durable_execution_grants
0011 dispatch_outbox
0012 dispatch_inbox
0013 execution_epoch_leases
```

PostgreSQL remains fail-closed/unreleased. Forward migration history must not be rewritten.

## Live evidence reality

### Reusable read/verification pilots on current main

- D4b — isolated governed READ;
- E3 — separate independent verifier observation;
- E4b — canonical VerificationResult.

These workflows are useful verification gates, not the ProductComposition runtime itself.

### Historical write/rollback proof

F4b and F6b proved a bounded staging lifecycle. Historical F6b run `32213563750` records:

```text
provider operation = DELETE_REF
provider mutation count = 1
automatic retry = false
rollback = true
Runner readback = ABSENT
independent verifier readback = ABSENT
VerificationResult = VERIFIED / OBSERVED_STATE_MATCH
verification strength = INDEPENDENT_PROVIDER_READBACK
```

The retained proof was composed into:

```text
OperationProof/v2 digest = 40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718
OperationCell/v1 digest  = 2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
```

This proves one complete historical operation atom. It does not make the old PR-specific WRITE
workflow a reusable product entrypoint.

## ProductComposition / API reality

The current FastAPI product composition still centers on the legacy `ExecutionService` surface. The
new authority → dispatch → Runner → verification → proof → cell components are not yet wired as one
canonical runtime/API transaction/lifecycle.

Therefore:

```text
FULL COMPONENT CHAIN EXISTS = YES
ONE CANONICAL PRODUCT RUNTIME PATH = NO
```

A later governed reconciliation slice must compose the chain without creating a second authority path
or promoting historical pilot orchestration into product runtime by copy/paste.

## UI truth boundary

Before reconciliation PR #128, the Evidence UI incorrectly rendered receipt rows as `VERIFIED`
without an independent VerificationResult. PR #128 changes that surface to fail closed: chain
integrity is `PASS/FAIL`, while independent verification for a receipt is `UNKNOWN` unless the product
actually exposes the independent verification binding.

No UI surface may derive `VERIFIED` from Receipt existence or hash-chain integrity alone.

## GitHub governance

Repository policy requires PR-only `main`, required `ci / verify`, latest-head checks, no force push,
no branch deletion and conversation resolution. Available live metadata does not prove the complete
modern ruleset configuration; classic required-status enforcement is observed `off`.

Until independent live Settings/API evidence proves every required control:

```text
GITHUB_SETTINGS_ENFORCED = UNKNOWN
P0_GITHUB_GOVERNANCE = BLOCKED
```

Repository documents and successful CI are not enforcement evidence.

## ADR / governance truth

- The adopted engineering operating standard remains bound to SHA-256
  `36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed`.
- OperationProof/v2 and OperationCell/v1 contracts are technically merged/implemented; their ADR
  metadata is reconciled separately from normative document-adoption semantics.
- Historical PR #125 technical merge/post-state is VERIFIED, while separate pre-merge
  merge-authorization provenance remains **NOT VERIFIED**. This metadata must not be rewritten.

## Security Intelligence / CyberCore boundary

R-SI1.1 is descriptive Security Intelligence metadata with tests. It does not issue authority, bypass
VOP policy, execute provider effects or automatically become OperationProof evidence.

CyberCore remains an intelligence/context/proposal participant only. Integration starts only after:

1. P0 product truth and Runner authority reconciliation;
2. canonical vocabulary/registry reconciliation;
3. top-level source-of-truth + CI/readiness reconciliation;
4. one canonical ProductComposition/API lifecycle design and implementation;
5. current governed WRITE/rollback orchestration design;
6. live GitHub enforcement is either VERIFIED or explicitly retained as a blocking boundary.

## Release boundary

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
RELEASED=NO
DEPLOYED=NO
UNRESTRICTED_PRODUCTION=BLOCKED
```

Successful CI, a merged contract, a verified historical pilot, OperationProof or OperationCell does
not independently change release/deployment state.

## Next governed sequence

```text
P0 truth + Runner authority
→ canonical vocabulary/registry
→ source-of-truth + CI/readiness convergence
→ canonical ProductComposition/API lifecycle
→ reusable governed WRITE/rollback orchestration
→ live GitHub governance verification/enforcement
→ final reconciliation audit
→ only then CyberCore integration
```
