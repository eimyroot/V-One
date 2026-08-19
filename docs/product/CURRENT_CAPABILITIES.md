# Current Capabilities

| Field | Value |
|---|---|
| Document status | Current-state inventory |
| Inventory audit date | `2026-08-20` |
| Reconciliation input Git baseline | `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| Reconciliation input tree | `423e234757686f720de20decd762270c43e0a8bb` |
| Exact live Git identity | Query live Git directly; never self-embed a commit as "current" |
| Reconciliation evidence | `VONE_RECONCILIATION_AUDIT_20260819T2209Z` |
| Reconciliation candidate | PR #128 / `feat/reconciliation-p0-p1-r1` |
| Latest runtime-attested committed baseline | `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` |
| Product version | `0.9.0-rc2-dev` |
| SQLite schema | version 13 |
| Production effects | disabled |
| Release classification | development / governed pilot, not unrestricted production |

## Reading this document

Capability status is evidence-scoped. A source component can be `IMPLEMENTED` while remaining absent
from the canonical ProductComposition/API runtime. `VERIFIED` means the evidence named in that row was
actually demonstrated; it does not imply release, deployment or production authority.

Use these separate questions for every capability:

```text
Does the contract/component exist?
Is it tested?
Is it composed into the canonical product runtime/API?
Is there real provider/runtime evidence?
Is it exposed truthfully in API/UI?
Is it released/deployed?
```

Do not collapse those questions into one stronger claim.

## Capability matrix

| Capability | Status | Current evidence | Current limitation |
|---|---|---|---|
| FastAPI `/api/v1` control plane | VERIFIED | system and product-composition tests | current composition still centers on legacy ExecutionService |
| Static command-center console | IMPLEMENTED | product HTTP/static surface | reconciliation PR #128 corrects receipt-to-VERIFIED overclaim |
| Local bootstrap, login and sessions | VERIFIED | authentication/bootstrap/session tests | no released OIDC/MFA enterprise identity path |
| RBAC and approval separation | VERIFIED | governance/service tests | current product roles are not full multi-tenant organization policy |
| Approval policy decision model | VERIFIED | deterministic policy-decision tests | default-off runtime compatibility path only; Solo, Team, Regulated enforcement is not implemented |
| Policy Decision Graph | PROPOSED | ADR-0003 design only | organization-scoped policy activation is not runtime authority |
| Workspace environment invariants | VERIFIED | service + database-trigger tests | SQLite pilot backend |
| Change-request lifecycle | VERIFIED | change-request/product tests | VOP end-to-end mapping into new trust-plane runtime is partial |
| VOP canonical vocabulary | IMPLEMENTED | machine vocabulary + registry + terminology tests | PR #128 reconciles proof/cell identities and Runner semantics |
| Provider semantic translation/equivalence | VERIFIED | deterministic translation tests | translation does not create authority |
| AuthorizationSnapshot contract | VERIFIED | contract/source tests | component status does not imply product composition |
| AuthoritativeSnapshotCreator | IMPLEMENTED | source + focused tests | not wired into canonical ProductComposition/API |
| ExecutionGrant/v2 | VERIFIED | deterministic contract and authority tests | not wired into canonical ProductComposition/API |
| Durable grant persistence | IMPLEMENTED | schema 0010 + service tests | SQLite-only released backend |
| GrantConsumptionWitness/v1 | IMPLEMENTED | source/tests and Phase-C chain | control plane owns consumption; Runner must not re-consume |
| Transactional DispatchOutboxEntry/v1 | IMPLEMENTED | schema 0011 + service tests | not product-composed |
| DispatchEnvelope/v1 | IMPLEMENTED | source/tests | delivery pilot/component scope |
| DispatchInboxAdmission/v1 dedup | IMPLEMENTED | schema 0012 + tests | not product-composed |
| ExecutionEpoch + ExecutionLease/v1 | IMPLEMENTED | schema 0013 + concurrency/fencing tests | not product-composed |
| DurableCoordinator / current fence | IMPLEMENTED | source/tests | component/pilot scope |
| ExecutionCapsule/v1 | IMPLEMENTED | contract/tests | not product-composed |
| RunnerIdentity / RunnerBoundary | IMPLEMENTED | source/tests and pilot binding | Runner is bounded execution only, not authorization/grant authority |
| CredentialAccessDecision | IMPLEMENTED | source/tests | decision metadata only; not a credential |
| Isolated runtime activation | IMPLEMENTED | source/tests + D4b/E3/E4b pilots | no general product-runtime orchestration |
| GitHub READ observation | VERIFIED | D4b live governed read | bounded GitHub pilot scope |
| Independent Verifier identity/boundary | VERIFIED | E3 live independent verifier | bounded GitHub pilot scope |
| VerificationResult/v1 | VERIFIED | E4b + historical F6b evidence | not product-composed/API-surfaced per operation |
| ExecutionReceipt/v2 | VERIFIED | contract/tests + historical F6b receipt | receipt remains execution claim, not verification |
| GitHub CREATE_REF bounded write | VERIFIED | historical F4b live canary pilot | workflow on main is hard-bound to historical PR120/main SHA |
| GitHub DELETE_REF rollback | VERIFIED | historical F6b live governed delete | historical workflow is not a current reusable main entrypoint |
| OperationProof/v1 | IMPLEMENTED | historical deterministic proof contract | historical lineage; must not be reinterpreted as v2 |
| OperationProof/v2 | VERIFIED | current contract/tests + F6b proof digest | not product-composed |
| OperationCell/v1 | VERIFIED | current contract/tests + F6b cell digest | not product-composed/API-surfaced |
| Unified authority→cell ProductComposition | PROPOSED | architecture target + implemented underlying components | one canonical runtime/API orchestration still missing |
| Receipt/audit hash-chain integrity | VERIFIED | ledger verification tests | chain integrity is not independent provider verification |
| SQLite migrations | VERIFIED | migrations 0001–0013 + integrity regression tests | single-node released backend |
| PostgreSQL backend | BLOCKED | fail-closed startup contract | adapter/concurrency/operations gates not released |
| OIDC identity provider | BLOCKED | fail-closed configuration tests | no released external identity runtime |
| Security Intelligence R-SI1.1 | IMPLEMENTED | PR #126 metadata + tests | intelligence-only; no execution authority or proof binding |
| CyberCore integration | BLOCKED | reconciliation audit | wait for P0/P1 convergence + canonical product pipeline |
| Main GitHub governance baseline | IMPLEMENTED | repository policy + machine baseline | live modern ruleset enforcement not verified |
| Main required `ci / verify` enforcement | UNKNOWN | classic required-status metadata observed off | must be proven/enforced via live GitHub settings/ruleset |
| Release-candidate build | VERIFIED | manual fail-closed workflow + image/SBOM checks | build/release candidate is not deployment |
| Unrestricted production release | BLOCKED | production effects default disabled | separate security/legal/ops/release authorization required |
| Public commercial distribution | BLOCKED | no release/distribution authorization | licensing/EULA/privacy/support and production gates remain separate |

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

This is real evidence for one historical operation atom. It is not evidence that the current FastAPI
ProductComposition automatically emits a cell for every operation.

## Verified command surfaces

```text
HTTP legacy/current product surface:
  /api/v1/health
  /api/v1/bootstrap/status
  /api/v1/auth/bootstrap
  /api/v1/auth/login
  /api/v1/auth/logout
  /api/v1/me
  /api/v1/users
  /api/v1/workspaces
  /api/v1/command-center
  /api/v1/change-requests
  /api/v1/approvals
  /api/v1/executions
  /api/v1/evidence/receipts
  /api/v1/evidence/verify
  /api/v1/audit
  /api/v1/system/emergency-stop

Local CLI:
  voodoo evidence verify <checkpoint>
  voodoo evidence capture-runtime <new-candidate>
  voodoo evidence finalize <candidate> <destination>
```

The HTTP surface above does not yet expose the complete authority→OperationCell lifecycle as one
canonical product API.

## Historical runtime checkpoint boundary

The latest retained full local runtime checkpoint remains historical development evidence for
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`. Later source trees are verified by their own GitHub
CI/pilot evidence; the older runtime archive must not be presented as attesting later commits.

## Current release boundary

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
RELEASE_VERIFIED=NO
DEPLOYMENT_VERIFIED=NO
```

No merge, CI pass, historical pilot, proof or cell changes those values by inference.

## Update rule

Update this inventory whenever a contract, composition path, live evidence scope, public truth
surface, governance boundary or release state materially changes. Preserve historical evidence in Git
and CASER instead of leaving stale current-state claims in this file.
