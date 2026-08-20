# Current Capabilities

| Field | Value |
|---|---|
| Document status | Current-state inventory |
| Inventory audit date | `2026-08-20` |
| Reconciliation base Git baseline | `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| Exact live Git identity | Query live Git directly; never self-embed a commit as "current" |
| Reconciliation candidate | PR #128 / `feat/reconciliation-p0-p1-r1` |
| Latest runtime-attested committed baseline | `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` |
| Product version | `0.9.0-rc2-dev` |
| SQLite schema | version 14 |
| Production effects | disabled |
| Release classification | development / governed pilot, not unrestricted production |

## Reading this document

Capability status is evidence-scoped. A component can be `IMPLEMENTED` while its default provider
runtime remains disabled. `VERIFIED` means the named evidence scope was actually demonstrated; it does
not imply current provider execution, release, deployment or production authority.

Ask separately:

```text
Does the contract/component exist?
Is it tested?
Is it ProductComposition-capable?
Is the default provider runtime active?
Is there real provider/runtime evidence?
Is it surfaced truthfully in API/UI?
Is it released/deployed?
```

## Capability matrix

| Capability | Status | Current evidence | Current limitation |
|---|---|---|---|
| FastAPI `/api/v1` product surface | VERIFIED | system/product-composition tests | canonical VOP operation endpoint not yet public |
| Static command-center console | IMPLEMENTED | product HTTP/static surface | final exact-head reconciliation gate pending |
| Local bootstrap, login and sessions | VERIFIED | authentication/bootstrap/session tests | no released OIDC/MFA enterprise identity path |
| RBAC and approval separation | VERIFIED | governance/service tests | not full organization/tenant policy |
| Approval policy decision model | VERIFIED | deterministic policy-decision tests | default-off runtime compatibility path only; Solo, Team, Regulated enforcement is not implemented |
| Policy Decision Graph | PROPOSED | ADR-0003 design only | organization-scoped policy activation is not runtime authority |
| DatabasePermissionAuthority | IMPLEMENTED | PR #128 adversarial/system tests | requires current role, active state, workspace/environment and membership |
| Current-role/current-active permission reevaluation | IMPLEMENTED | role/state mutation tests | applies to canonical runtime authority path |
| Workspace membership scope | IMPLEMENTED | schema 0014 + membership/revocation tests | legacy schema-13 workspaces are not backfilled; explicit admin membership required |
| Workspace environment invariants | VERIFIED | service + DB-trigger tests | SQLite pilot backend |
| Change-request lifecycle | VERIFIED | change-request/product tests | legacy API compatibility surface remains |
| VOP canonical vocabulary R2 | IMPLEMENTED | machine registry + terminology tests | final exact-head reconciliation gate pending |
| Capability→terminal profile registry | IMPLEMENTED | terminal-profile tests | immutable current registry; not caller selectable |
| Terminal-strength escalation prevention | IMPLEMENTED | pipeline/profile negative tests | no claim about future unregistered capabilities |
| Provider semantic translation/equivalence | VERIFIED | deterministic translation tests | translation does not create authority |
| AuthorizationSnapshot contract | VERIFIED | contract/source tests | component proof does not imply provider effect |
| AuthoritativeSnapshotCreator | IMPLEMENTED | source/focused tests | canonical runtime factory dependency |
| ExecutionGrant/v2 | VERIFIED | deterministic authority tests | no independent provider effect claim |
| Durable grant persistence | IMPLEMENTED | schema 0010 + service tests | SQLite-only released backend |
| GrantConsumptionWitness/v1 | IMPLEMENTED | source/tests + Phase-C chain | control-plane only; Runner must not re-consume |
| Transactional DispatchOutboxEntry/v1 | IMPLEMENTED | schema 0011 + service tests | bounded to canonical pipeline |
| DispatchEnvelope/v1 | IMPLEMENTED | source/tests | transport identity is not authorization |
| DispatchInboxAdmission/v1 dedup | IMPLEMENTED | schema 0012 + tests | bounded to coordinator scope |
| ExecutionEpoch + ExecutionLease/v1 | IMPLEMENTED | schema 0013 + fencing tests | lease is not provider effect |
| DurableCoordinator / current fence | IMPLEMENTED | source/tests | required again at effect/preflight boundaries |
| CanonicalOperationPipeline | IMPLEMENTED | PR #128 system tests | intentionally stops before Runner/provider effect |
| ProductComposition canonical runtime seam | IMPLEMENTED | PR #128 composition tests | explicit runtime factory required; default remains fail-closed |
| CanonicalOperationRuntime router | IMPLEMENTED | PR #128 routing tests | routes only registered profile/capability paths |
| ExecutionCapsule/v1 | IMPLEMENTED | contract/tests | exact capability definition binding required |
| RunnerIdentity / RunnerBoundary | IMPLEMENTED | source/tests + pilot evidence | bounded execution only, never grant authority |
| CredentialAccessDecision | IMPLEMENTED | source/tests | metadata/authorization scope, not credential bytes |
| Isolated READ runtime activation | IMPLEMENTED | source/tests + D4b | bounded GitHub runtime profile |
| GitHub READ observation | VERIFIED | D4b live governed read | bounded GitHub pilot scope |
| CanonicalGitHubReadTerminal | IMPLEMENTED | PR #128 terminal tests | final exact-head candidate gate pending |
| Independent Verifier identity/boundary | VERIFIED | E3 live independent verifier | bounded GitHub pilot scope |
| Separate verifier credential decision | IMPLEMENTED | E3/E4b contracts/tests | must remain distinct from Runner credential path |
| VerificationResult/v1 | VERIFIED | E4b + historical F6b | READ terminal current stopping point |
| ExecutionReceipt/v2 | VERIFIED | contract/tests + historical F6b | execution claim only; not independent verification |
| GitHub CREATE_REF bounded write contract/runtime | VERIFIED | historical F4b effect evidence | historical execution is not new current effect authority |
| A09 reusable CREATE_REF preparation | IMPLEMENTED | PR #128 tests | ends at `WriteEffectPreflight/v1`; no transport/effect |
| GitHub DELETE_REF rollback contract/runtime | VERIFIED | historical F6b effect evidence | historical execution is not reusable current authorization |
| A09 reusable rollback preparation | IMPLEMENTED | PR #128 tests | ends at `RollbackWriteEffectPreflight/v2`; no DELETE call |
| A09 historical PR120/SHA independence | IMPLEMENTED | source-negative tests | only A09 seam; historical pilot files remain historical |
| OperationProof/v1 | IMPLEMENTED | historical deterministic proof contract | historical lineage; not reinterpreted as v2 |
| OperationProof/v2 | VERIFIED | current contract/tests + historical F6b digest | mutation-only post-verification lineage |
| OperationCell/v1 | VERIFIED | current contract/tests + historical F6b digest | mutation-only stable operation atom |
| Unified authority→profile runtime composition | IMPLEMENTED | ProductComposition + canonical runtime tests | default provider pack off; canonical public API later |
| Receipt/audit hash-chain integrity | VERIFIED | ledger verification tests | chain integrity != independent provider verification |
| SQLite migrations | VERIFIED | migrations 0001–0014 + integrity tests | single-node released backend |
| PostgreSQL backend | BLOCKED | fail-closed startup contract | adapter/concurrency/operations gates not released |
| OIDC identity provider | BLOCKED | fail-closed configuration tests | no released external identity runtime |
| Security Intelligence R-SI1.1 | IMPLEMENTED | metadata + tests | intelligence-only; no execution/proof authority |
| CyberCore integration | BLOCKED | reconciliation gate | waits for final exact-head R3 + reconciliation audit |
| Main GitHub governance policy | IMPLEMENTED | repository policy | live modern ruleset enforcement not verified |
| Main required latest-head enforcement | UNKNOWN | connector/settings evidence insufficient | explicit release blocker |
| Release-candidate build | VERIFIED | fail-closed workflow + historical image/SBOM checks | build candidate != deployment |
| Unrestricted production release | BLOCKED | production effects default disabled | separate security/legal/ops/release authorization required |
| Public commercial distribution | BLOCKED | no distribution authorization | licensing/EULA/privacy/support and production gates remain separate |

## Verified command surfaces

The current HTTP surface still exposes the established product endpoints. It does **not** yet claim a
new public endpoint for the full canonical VOP runtime. ProductComposition wiring and public product
surfacing are separate truth dimensions.

## Canonical ProductComposition shape

```text
ProductService database
        ↓
DatabasePermissionAuthority
        ↓
current user + role + active state + workspace membership
        ↓
CanonicalOperationPipeline
        ↓
immutable capability→terminal profile
        ↓
CanonicalOperationRuntime
        ├── READ_ONLY_VERIFIED
        │    → CanonicalGitHubReadTerminal
        │    → VerificationResult/v1
        │
        └── BOUNDED_MUTATION_VERIFIED
             ├── CREATE_REF → A09CreateRefPreparer → WriteEffectPreflight/v1 → STOP
             └── DELETE_REF → A09RollbackPreparer → RollbackWriteEffectPreflight/v2 → STOP
```

The runtime factory must share the exact ProductService database and permission-authority instance.
Without an explicit provider/runtime pack the default composition remains fail-closed. Workspace
membership is a scope check, not activation of the separately PROPOSED Solo/Team/Regulated policy.

## Verified historical complete operation atom

Historical F6b run `32213563750` proves one bounded staging operation through effect, independent
readback and portable proof/cell composition:

```text
DELETE_REF
→ ExecutionReceipt/v2 (mutation count 1, automatic retry false)
→ Runner ABSENT observation
→ independent Verifier ABSENT observation
→ VerificationResult/v1 = VERIFIED / OBSERVED_STATE_MATCH
→ OperationProof/v2
→ OperationCell/v1
```

Retained identities:

```text
OperationProof/v2 = 40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718
OperationCell/v1  = 2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
```

This is historical evidence for one real atom. It does not execute or verify the new A09 candidate.

## Release boundary

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
NEW_A09_PROVIDER_MUTATION=NO
RELEASE_VERIFIED=NO
DEPLOYMENT_VERIFIED=NO
```

No merge, CI pass, preflight, historical pilot, proof or cell changes those values by inference.

## Current closure gate

Before PR #128 can be considered reconciliation-complete, one exact final candidate head requires:

```text
CI = SUCCESS
D4b = SUCCESS
E3 = SUCCESS
E4b = SUCCESS
R3 adversarial review = complete
final reconciliation audit = complete
unresolved review findings = 0 or explicitly retained blocker
```

## Update rule

Update this inventory whenever a contract, composition path, live evidence scope, public truth
surface, governance boundary or release state materially changes. Preserve historical evidence rather
than silently promoting it into current capability claims.
