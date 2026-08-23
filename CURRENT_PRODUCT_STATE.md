# VOODOO One — CURRENT PRODUCT STATE

> Living evidence-scoped snapshot. Live Git/GitHub, executed tests and runtime evidence outrank this document. Historical claims stay historical and are never upgraded by later success.

## Snapshot identity

```text
AS_OF: 2026-08-24
EXACT_LIVE_GIT_IDENTITY: QUERY_LIVE_GIT_DIRECTLY
RECONCILIATION_INPUT_HEAD: 3106ba95125a13adb8e0ee867fbf341d2d2e776e
RECONCILIATION_BASE_MAIN: 3106ba95125a13adb8e0ee867fbf341d2d2e776e
RECONCILIATION_MERGE: PR #140 / 60bc9c26813ee23c73bac194a9adb27714e8a1e8
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@d57d37111b8bc9471a136b6c618aad8e920f1aff
VOP_SEMANTIC_REVISION: vop-terminology-freeze-r2
PRODUCT_VERSION: 0.9.0-rc2-dev
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

The exact live `main` identity must be queried directly. The G7 merge SHA above is snapshot provenance, not a self-updating current-main claim.

## Historical checkpoint boundary

The latest retained full runtime-attested checkpoint remains historical evidence for exactly
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`:

```text
POST_MERGE_CHECKPOINT_ZIP_SHA256=80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2
POST_MERGE_CHECKPOINT_IMAGE_ID=sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
```

Historical documentation-review merge `57c7bf2277616c4445039865ac7cf81c5fada858` remains ADR-0008 evidence-index provenance only; it is not the current Git baseline.

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
| Canonical ProductComposition trust-plane seam | **IMPLEMENTED / MERGED** |
| Canonical public READ operation API | **IMPLEMENTED / MERGED via PR #137** |
| Restart-safe durable resume | **IMPLEMENTED / MERGED via PR #140** |
| Runtime resume wiring | **IMPLEMENTED / MERGED via PR #140** |
| G7 post-merge verification | **VERIFIED on `main@60bc9c268...` by CI #1015, D4 #202, E3 #193, E4B #189** |
| GitHub G0 governance | **VERIFIED / PASS** |
| Default provider runtime pack | **DISABLED / FAIL-CLOSED** |
| Real canonical HTTP READ E2E using default G8 pack | **BLOCKED / NOT YET VERIFIED** |
| Provider WRITE activation | **BLOCKED** |
| Reusable CREATE_REF orchestration | **IMPLEMENTED PRE-EFFECT ONLY; NOT CURRENTLY EXECUTED** |
| Reusable DELETE_REF rollback orchestration | **IMPLEMENTED PRE-EFFECT ONLY; NOT CURRENTLY EXECUTED** |
| Production release/effects | **BLOCKED / DISABLED** |
| Release | **NOT PERFORMED** |
| Deployment | **NOT PERFORMED** |
| CyberCore | **BLOCKED pending product/release-governance hardening** |

## G0 live GitHub governance

G0 is no longer an unresolved blocker. The exit gate is tied to identifiable live evidence:

```text
workflow = g0-governance-verify
run = 32553113424
event = workflow_dispatch
branch = main
source_sha = 76d74d2ed62b6e78f027728c456c22da0b4a95bd
artifact = g0-governance-evidence-32553113424-1
artifact_id = 9470619984
artifact_digest = sha256:6e63caee23a57613471df66ef0279c0261ed8d375e4c929accdf50eff7dc4f5f
evidence_json_checksum = 11a99765485b63b70186037011d31c105dea8dd75b689e0036a8766d05e8137d
verdict = VERIFIED
```

The retained evidence verifies PR-only main, required `verify` from workflow `ci`, latest-head strict checks, force-push disabled, branch deletion disabled, conversation resolution, no ordinary admin/ruleset bypass, active rulesets, and verifier source binding.

```text
REPO_ENFORCEMENT_CONTRACT       = VERIFIED
GITHUB_SETTINGS_ENFORCED        = VERIFIED
MAIN_PR_ONLY                    = VERIFIED
REQUIRED_CI                     = VERIFIED
FORCE_PUSH_DISABLED             = VERIFIED
BRANCH_DELETE_DISABLED          = VERIFIED
CONVERSATION_RESOLUTION         = VERIFIED
ORDINARY_ADMIN_BYPASS_DISABLED  = VERIFIED
P0_GITHUB_GOVERNANCE            = PASS
G0                              = PASS
```

G0 PASS does not authorize release or deployment.

## Canonical shared authority/execution prefix

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

`CanonicalOperationPipeline.prepare()` stops before Runner/provider effect and retains exact bound runtime objects for the terminal router. Grant consumption remains control-plane-before-Dispatch; Runner never issues or consumes ExecutionGrant.

## Capability-bound terminal selection

Terminal strength is not caller-selected. The immutable capability definition determines the terminal profile. G7 additionally narrows the public READ path to exactly:

```text
terminal_profile = READ_ONLY_VERIFIED
capability       = github.read-ref/v1
```

A caller-supplied `terminal_profile` is rejected. Route/profile/capability mismatch fails before Grant issuance/consumption.

## Runtime permission authority

`DatabasePermissionAuthority` remains the current permission source for canonical product composition. Every permission decision re-reads the ProductService database and requires the current active user, global role permission, exact workspace/environment, and current user↔workspace membership. A stale Principal, role downgrade, deactivation, or membership revocation cannot preserve stronger canonical authority.

## Canonical G7 public Operation API — merged

PR #137 is merged. PR #140 reconciles that API with durable resume and runtime resume wiring.

```text
GET  /api/v1/operations/status
POST /api/v1/operations/{request_id}/read
```

The response keeps execution and independent verification separate. This remains a valid truthful state:

```text
execution.status      = SUCCEEDED
verification.verdict  = NOT_VERIFIED
```

Execution success, receipt existence, digest integrity, or evidence-chain integrity must never manufacture `VERIFIED`.

No canonical CREATE_REF, DELETE_REF, or rollback HTTP route exists.

## Restart-safe durable resume — merged

Canonical resume reconstructs the same already-authorized execution from durable evidence. It requires the original actor and current DB permission, validates durable snapshot/grant/consumption/outbox/envelope/inbox/lease evidence, resolves the terminal profile server-side, and rechecks the current execution fence.

Resume must not:

```text
re-enter CanonicalOperationPipeline.prepare()
issue a second ExecutionGrant/v2
consume the grant a second time
append a second outbox/inbox admission
reacquire a lease
accept a parallel DB / permission authority / profile registry / fence
```

PR #140 fixed reviewed nested-ownership cases so runtime/composition revalidates the canonical DB ownership of snapshot store, permission authority, and current fence.

## G7 closure evidence

Accepted reconciliation head:

```text
cda7d957cbba8412aa8cd8720e5eb95ed781e58d
```

Pre-merge:

```text
CI #1013 = SUCCESS
D4 #201 = SUCCESS
E3 #192 = SUCCESS
E4B #188 = SUCCESS
fresh Codex R3 = no major issues
```

Post-merge on `main@60bc9c26813ee23c73bac194a9adb27714e8a1e8`:

```text
CI #1015 = SUCCESS
D4 #202 = SUCCESS
E3 #193 = SUCCESS
E4B #189 = SUCCESS
full pytest = SUCCESS
product readiness = SUCCESS
dependency vulnerability audit = SUCCESS
product image build + smoke = SUCCESS
```

Historical stacked PRs #138 and #139 were closed without merge after PR #140 became canonical.

## Canonical terminal profiles

### READ_ONLY_VERIFIED

```text
isolated READ Runner
→ Runner observation
→ durable completion
→ independent Verifier
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

For READ:

```text
ExecutionReceipt/v2 = NOT_APPLICABLE
OperationProof/v2   = NOT_APPLICABLE
OperationCell/v1    = NOT_APPLICABLE
```

### BOUNDED_MUTATION_VERIFIED

```text
bounded provider mutation
→ ExecutionReceipt/v2
→ independent verifier
→ VerificationResult/v1 = VERIFIED
→ OperationProof/v2
→ OperationCell/v1
```

Current reusable CREATE_REF and DELETE_REF/rollback orchestration stop at pre-effect artifacts. No current provider mutation is authorized by G7.

## Hard READ-before-WRITE boundary

Provider WRITE remains blocked until the same canonical product path repeatedly proves a real authenticated HTTP READ through independent `VerificationResult/v1`, including process restart and durable resume of the same execution.

Required gate:

```text
READ_E2E             = VERIFIED
RESTART_RESUME       = VERIFIED
NO_DUPLICATE_EFFECT  = VERIFIED
AUTHORITY_CONTINUITY = VERIFIED
INDEPENDENT_VERIFY   = VERIFIED
FAIL_CLOSED          = VERIFIED

WRITE_RUNTIME_GATE   = ELIGIBLE
```

`ELIGIBLE` still does not authorize provider WRITE; WRITE requires a later explicit effect-specific gate and authorization.

## G8 current boundary

G8 is the next implementation gate. The first default provider runtime pack is READ-only and must reuse existing canonical components rather than create a parallel provider or authority framework. It must use explicit configuration, separate Runner and Verifier credential decisions/identities, the exact ProductComposition DB/permission authority/profile registry/current fence, and no ambient credential fallback.

Until G8 is implemented and real HTTP READ E2E is verified:

```text
DEFAULT_PROVIDER_RUNTIME = OFF
REAL_CANONICAL_READ_E2E = NOT_VERIFIED
WRITE_RUNTIME_GATE = BLOCKED
PRODUCTION_EFFECTS = DISABLED
```

## Historical bounded mutation evidence

Historical F6b run `32213563750` remains one complete bounded staging operation:

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

This historical evidence does not authorize or prove any new provider mutation.

## Governance history

- Engineering operating standard remains hash-bound to `36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed`.
- Historical PR #125 technical merge/post-state is VERIFIED; separate pre-merge merge-authorization provenance remains **NOT VERIFIED** and is not rewritten.
- ADR-0018 records the R2 terminal-profile correction instead of silently rewriting older history.
- PR #128 reconciliation remains historical provenance; later G7 evidence does not rewrite it.

## Current release truth

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
G0_GITHUB_GOVERNANCE=PASS
G7_CANONICAL_READ_API=MERGED
G7_RESTART_SAFE_RESUME=MERGED
G8_DEFAULT_READ_RUNTIME=OFF
REAL_CANONICAL_READ_E2E=NOT_VERIFIED
WRITE_RUNTIME_GATE=BLOCKED
RELEASE=NOT_PERFORMED
DEPLOYMENT=NOT_PERFORMED
```
