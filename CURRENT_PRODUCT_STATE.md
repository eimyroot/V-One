# VOODOO One — CURRENT PRODUCT STATE

> Living evidence-scoped snapshot. Live Git/GitHub, executed tests and runtime evidence outrank this
> document. Historical claims stay in Git/CASER and are never upgraded by later success.

## Snapshot identity

```text
AS_OF: 2026-08-20
EXACT_LIVE_GIT_IDENTITY: QUERY_LIVE_GIT_DIRECTLY
RECONCILIATION_INPUT_HEAD: 71a931b561faa93c8dd2e062b83559401143b1df
RECONCILIATION_BASE_MAIN: 71a931b561faa93c8dd2e062b83559401143b1df
RECONCILIATION_BASE_TREE: 423e234757686f720de20decd762270c43e0a8bb
AUDIT: VONE_RECONCILIATION_AUDIT_20260819T2209Z
RECONCILIATION_CANDIDATE: PR #128 / feat/reconciliation-p0-p1-r1
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@d57d37111b8bc9471a136b6c618aad8e920f1aff
VOP_SEMANTIC_REVISION_CANDIDATE: vop-terminology-freeze-r2
PRODUCT_VERSION: 0.9.0-rc2-dev
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

The exact live Git identity must be queried directly; none of these retained SHAs is a self-updating
claim about future `main`.

## Historical checkpoint boundary

The latest retained full local runtime-attested checkpoint remains historical development evidence for
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`:

```text
EVIDENCE_ARCHIVE: POST_MERGE_CHECKPOINT_20260802T152505Z_d57d37111b8b.zip
PRODUCT_IMAGE_ID: sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
```

It does not attest later source changes. Historical documentation-review merge
`57c7bf2277616c4445039865ac7cf81c5fada858` remains only ADR-0008 evidence-index provenance; it is not
the current Git baseline.

## Truth dimensions

Do not collapse these dimensions:

```text
CONTRACT / COMPONENT      = source implementation exists
PRODUCT_COMPOSED          = canonical ProductComposition/API uses it
LIVE_VERIFIED             = real runtime/provider evidence exists for the named scope
PRODUCT_SURFACED          = API/UI exposes the same semantics truthfully
RELEASED / DEPLOYED       = separately governed states
```

## Overall state

| Dimension | Current state |
|---|---|
| Technical trust-plane components | **STRONG / IMPLEMENTED** |
| Historical bounded-mutation operation atom | **VERIFIED** in F6b staging scope |
| Unified canonical ProductComposition/API | **PARTIAL / NOT YET COMPOSED** |
| Canonical VOP language | **R2 RECONCILIATION CANDIDATE** in PR #128 |
| UI receipt/verification truth | **FIXED IN PR #128; exact-head verification pending** |
| SQLite persistence | **IMPLEMENTED through schema 13** |
| READ-only isolated Runner + verifier | **LIVE VERIFIED pilot scope** |
| Governed write/rollback | **HISTORICALLY VERIFIED pilot; not reusable current entrypoint** |
| OperationProof/v2 | **IMPLEMENTED bounded-mutation proof; F6b instance VERIFIED** |
| OperationCell/v1 | **IMPLEMENTED bounded-mutation atom; F6b instance VERIFIED** |
| Security Intelligence R-SI1.1 | **IMPLEMENTED intelligence-only layer** |
| GitHub main ruleset enforcement | **UNKNOWN / BLOCKED until live evidence** |
| Production release/effects | **BLOCKED** |
| CyberCore | **BLOCKED until reconciliation closure** |

## Canonical shared authority/execution prefix

The current accepted component model shares this prefix:

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
→ RunnerIdentity + RunnerBoundary
→ CredentialAccessDecision
→ RuntimeActivation
→ Provider effect / Observation
```

Grant consumption belongs to the control plane before Dispatch. Runner authority is
`bounded_execution_only`; Runner never issues or consumes ExecutionGrant.

## Canonical terminal profiles — R2

The lifecycle is **not** one mandatory universal tail.

### READ-only verified

```text
READ_ONLY_VERIFIED
Runner Observation
→ independent Verifier Observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1 = VERIFIED
```

Current READ-only verified operations terminate at `VerificationResult/v1`.

```text
ExecutionReceipt/v2 = NOT_APPLICABLE
OperationProof/v2   = NOT_APPLICABLE
OperationCell/v1    = NOT_APPLICABLE
```

### Bounded mutation verified

```text
BOUNDED_MUTATION_VERIFIED
bounded provider mutation
→ ExecutionReceipt/v2                  [verification_status=NOT_EVALUATED]
→ independent readback
→ VerificationResult/v1 = VERIFIED
→ OperationProof/v2
→ OperationCell/v1
```

`ExecutionReceipt/v2` and `OperationProof/v2` both require exactly one bounded provider mutation and
forbid automatic mutation retry. They are current specialized mutation-lineage contracts, **not**
universal replacements for every v1 receipt/proof lineage.

Mandatory non-conflation:

```text
Approval != Authorization
ExecutionGrant != ExecutionCapsule
ExecutionReceipt != VerificationResult
execution succeeded != VERIFIED
VerificationResult != OperationProof
OperationProof != OperationCell
Evidence-chain integrity != independent verification
Release != Deploy
```

## Component inventory

| Layer | Component | Product composed | Live evidence |
|---|---|---|---|
| Review/approval | IMPLEMENTED | legacy product path | local/system |
| AuthoritativeSnapshotCreator | IMPLEMENTED | NO | component tests |
| ExecutionGrant/v2 + durable store | IMPLEMENTED | NO | component tests |
| Grant consumption + transactional outbox | IMPLEMENTED | NO | component/pilot |
| Dispatch envelope + durable inbox/dedup | IMPLEMENTED | NO | component/pilot |
| ExecutionEpoch/Lease + DurableCoordinator | IMPLEMENTED | NO | component/pilot |
| Capsule / Runner identity/boundary | IMPLEMENTED | NO | pilot |
| READ runtime activation | IMPLEMENTED | NO | D4b |
| Independent verifier / VerificationResult | IMPLEMENTED | NO | E3/E4b/F6b |
| Bounded CREATE_REF | IMPLEMENTED | NO | historical F4b |
| Bounded DELETE_REF rollback | IMPLEMENTED | NO | historical F6b |
| ExecutionReceipt/v2 | IMPLEMENTED | NO | historical F6b |
| OperationProof/v2 | IMPLEMENTED | NO | historical F6b |
| OperationCell/v1 | IMPLEMENTED | NO | historical F6b |
| Unified current lifecycle orchestration | NOT IMPLEMENTED | N/A | NO |

The remaining core task is composition of accepted components, not reimplementation of their
contracts.

## Historical F6b mutation evidence

Historical F6b run `32213563750` records:

```text
provider operation = DELETE_REF
provider mutation count = 1
automatic retry = false
rollback = true
Runner readback = ABSENT
independent verifier readback = ABSENT
VerificationResult = VERIFIED / OBSERVED_STATE_MATCH
verification strength = INDEPENDENT_PROVIDER_READBACK
OperationProof/v2 = 40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718
OperationCell/v1  = 2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
```

This proves one complete bounded-mutation atom. It does not prove that every READ requires or produces
a Proof/v2/Cell/v1, and it does not make historical PR-specific workflows reusable product runtime.

## ProductComposition reality

Current FastAPI composition still centers on legacy `ExecutionService`. The accepted A/B/C/D/E/F/H
components are not yet wired through one canonical runtime/API orchestration.

```text
COMPONENT COVERAGE = STRONG
ONE CANONICAL PRODUCT ORCHESTRATION = NO
```

The new ProductComposition must:

1. reuse the authoritative Snapshot/Grant/consumption/dispatch/lease contracts;
2. create no second authority path;
3. select the terminal profile explicitly;
4. terminate READ at VerificationResult/v1;
5. allow Proof/v2→Cell/v1 only for the accepted bounded-mutation profile;
6. preserve weaker states truthfully at API/UI surfaces.

## UI truth

PR #128 changes evidence UI so hash-chain integrity is `PASS/FAIL` and a receipt's independent
verification is `UNKNOWN` unless an actual VerificationResult binding is exposed. Receipt existence
must never render `VERIFIED` by itself.

## GitHub governance

Repository policy requires PR-only `main`, required `ci / verify`, current-head checks, no force push,
no branch deletion and conversation resolution. Available connector evidence does not prove the full
modern ruleset; classic required-status enforcement was observed off.

```text
GITHUB_SETTINGS_ENFORCED = UNKNOWN
P0_GITHUB_GOVERNANCE = BLOCKED
```

Successful CI is not Settings enforcement evidence.

## Governance history

- Engineering operating standard remains hash-bound to
  `36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed`.
- Historical PR #125 technical merge/post-state is VERIFIED; separate pre-merge merge-authorization
  provenance remains **NOT VERIFIED** and is not rewritten.
- ADR-0018 records the R2 terminal-profile correction instead of silently rewriting ADR-0014 history.

## CyberCore boundary

R-SI1.1 and future CyberCore inputs remain intelligence/context/proposal only. They cannot issue
ExecutionGrant, consume grants, become Runner/Verifier, execute provider effects or automatically
become proof evidence.

CyberCore remains blocked until:

1. P0/P1 reconciliation exact-head gates pass;
2. canonical ProductComposition is functional;
3. reusable governed WRITE/rollback orchestration exists without auto-activation;
4. final reconciliation audit passes;
5. GitHub governance is VERIFIED or retained as an explicit release blocker.

## Release boundary

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
RELEASED=NO
DEPLOYED=NO
UNRESTRICTED_PRODUCTION=BLOCKED
```

## Next governed sequence

```text
VOP R2 truth convergence
→ canonical ProductComposition
→ reusable WRITE/rollback orchestration
→ exact-head CI + R3 review
→ final reconciliation audit
→ CyberCore only after PASS
```
