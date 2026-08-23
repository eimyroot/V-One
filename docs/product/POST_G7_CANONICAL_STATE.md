# VOODOO One — Post-G7 Canonical State

> Evidence-scoped product truth after canonical G7 reconciliation. Live GitHub state and executed evidence outrank this document.

## Snapshot identity

```text
AS_OF: 2026-08-24
CANONICAL_MAIN_AT_SNAPSHOT: 60bc9c26813ee23c73bac194a9adb27714e8a1e8
G7_RECONCILIATION_PR: #140
G7_RECONCILIATION_HEAD: cda7d957cbba8412aa8cd8720e5eb95ed781e58d
PRODUCT_VERSION: 0.9.0-rc2-dev
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

The retained SHA above is snapshot provenance only. Query live `main` before any consequential operation.

## Authoritative truth convergence

This snapshot is supplemental. The same current-state claims are reconciled in the authoritative product surfaces in this change:

- `CURRENT_PRODUCT_STATE.md`;
- `docs/product/CURRENT_CAPABILITIES.md`;
- `ROADMAP.md`.

If later live repository/runtime evidence conflicts with any document, live evidence wins and the documents must be reconciled again rather than silently upgrading a historical claim.

## Canonical G7 status

G7 is no longer a candidate. PR #140 reconciled the merged canonical READ API with restart-safe durable resume and runtime resume wiring onto current main.

```text
canonical READ HTTP API                    = MERGED
restart-safe durable resume                = MERGED
runtime resume wiring                      = MERGED
second prepare/grant/consume on resume     = FORBIDDEN
caller-selected terminal authority         = FORBIDDEN
provider WRITE introduced by G7            = NO
```

The accepted reconciliation head `cda7d957cbba8412aa8cd8720e5eb95ed781e58d` passed fresh exact-head CI, D4, E3 and E4B and a fresh independent Codex review with no major findings before merge.

Post-merge evidence on `main@60bc9c26813ee23c73bac194a9adb27714e8a1e8`:

```text
ci / verify                         #1015 = SUCCESS
d4b-live-governed-read              #202  = SUCCESS
e3-live-independent-verifier        #193  = SUCCESS
e4b-live-verification-result        #189  = SUCCESS
full pytest                                = SUCCESS
product readiness                          = SUCCESS
dependency vulnerability audit             = SUCCESS
product image build + smoke                 = SUCCESS
```

Historical stacked PRs #138 and #139 are superseded by canonical PR #140 and must not be used as alternate merge paths.

## G0 governance — identifiable live evidence

G0 is bound to the retained live verifier evidence, not inferred from documentation or ordinary CI:

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

That evidence verified PR-only main, required `verify` from workflow `ci`, latest-head strict checks, force-push disabled, branch deletion disabled, conversation resolution, no ordinary admin/ruleset bypass, active rulesets, and verifier source binding.

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

G0 PASS does not itself authorize release or deployment.

## Current product boundary

```text
Canonical ProductComposition trust plane  = IMPLEMENTED / MERGED
Canonical public READ API                  = IMPLEMENTED / MERGED
Durable restart-safe READ resume           = IMPLEMENTED / MERGED
Independent READ VerificationResult        = IMPLEMENTED / VERIFIED in governed pilot evidence
Default provider runtime pack              = DISABLED / FAIL-CLOSED
Real canonical HTTP READ E2E via G8        = NOT VERIFIED
Canonical provider WRITE runtime           = DISABLED
WRITE runtime gate                         = BLOCKED
Production effects                         = DISABLED
Release                                    = NOT PERFORMED
Deployment                                 = NOT PERFORMED
```

Without the separately governed G8 runtime pack, the product must remain fail-closed rather than use ambient provider credentials or a legacy execution path.

## READ-before-WRITE proposal

ADR-0019 is under governed adoption in this change; it is not treated as accepted authority before its adoption gate closes. The proposed safety rule is stricter than the current state: provider WRITE remains blocked regardless.

No provider WRITE effect becomes eligible for activation until the same canonical path repeatedly proves a real READ end-to-end from authenticated HTTP request through independent `VerificationResult/v1`, including restart/resume behavior.

Required proof chain:

```text
authenticated HTTP request
→ current DB permission + workspace membership
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ one-time GrantConsumptionWitness/v1
→ transactional Outbox
→ DispatchEnvelope
→ Inbox admission
→ ExecutionEpoch + current Lease
→ ExecutionCapsule
→ isolated READ Runner
→ durable completion
→ independent Verifier
→ VerificationResult/v1
→ process restart
→ durable resume of the same execution
→ no new grant
→ no second grant consumption
→ no second outbox/inbox admission
→ no lease reacquisition
→ current-fence validation
→ same truthful verification semantics or fail-closed result
```

WRITE eligibility requires all of:

```text
READ_E2E             = VERIFIED
RESTART_RESUME       = VERIFIED
NO_DUPLICATE_EFFECT  = VERIFIED
AUTHORITY_CONTINUITY = VERIFIED
INDEPENDENT_VERIFY   = VERIFIED
FAIL_CLOSED          = VERIFIED

WRITE_RUNTIME_GATE   = ELIGIBLE
```

`ELIGIBLE` is still not effect authorization.

`execution.status = SUCCEEDED` is never sufficient. A valid truthful result may remain:

```text
execution.status      = SUCCEEDED
verification.verdict  = NOT_VERIFIED
```

and must never be promoted to `VERIFIED` by execution success, receipt existence, digest integrity, or evidence-chain integrity.

## Next governed sequence

```text
1. post-G7 product-truth convergence
2. G8 explicit READ-only provider runtime pack
3. repeated real canonical HTTP READ E2E + restart/resume verification
4. only then evaluate WRITE runtime/effect eligibility
5. RC gates
6. release authorization
7. deployment authorization
```

No step inherits authorization from the previous one.