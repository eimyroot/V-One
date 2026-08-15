# Current Capabilities

| Field | Value |
|---|---|
| Document status | Current-state inventory |
| Inventory audit date | `2026-08-16` |
| Reconciliation input Git baseline | `main@b4d4aab7393251ffc113a3f5bf654523bdb27865` |
| Reconciliation input tree | `61021278068a7d64b66325190c94dde6f4593b16` |
| Exact live Git identity | Query live Git directly; never self-embed a commit as "current" |
| Current-main verification | CI #298 SUCCESS at reconciliation input head |
| PR #71 merge commit | `d8d375c61264ddad39eb53240dce9ff0c8e59818` |
| PR #71 verification | PR-head CI #282 SUCCESS; post-merge CI #283 SUCCESS |
| PR #74 VOP merge commit | `a9a57df270b85907ee5012895c1523ade461f06f` |
| PR #74 verification | PR-head CI #292 SUCCESS; current-main CI #298 SUCCESS includes merged VOP tree |
| PR #75 governance-contract merge | `b4d4aab7393251ffc113a3f5bf654523bdb27865` |
| PR #75 verification | PR-head CI #291 SUCCESS; current-main CI #298 SUCCESS |
| Latest runtime-attested committed baseline | `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` |
| Product version | `0.9.0-rc2-dev` |
| Release classification | Development baseline, not unrestricted production |
| Authorization Snapshot contract | IMPLEMENTED |
| Authorization Snapshot persistence | VERIFIED for merged PR #71 scope |
| SQLite schema | version 9 |
| VOP canonical vocabulary | VERIFIED source/test scope |
| VOP semantic translation/equivalence | VERIFIED source/test scope |
| VOP owner-adoption status | UNKNOWN; no explicit record in authority/adoption register |
| ADR-0008 effective status | ADOPTED via authority/adoption register; Runner runtime not implemented |
| ADR-0009 effective status | ADOPTED design boundary; grant issuer/authenticity implementation not implied |
| ADR-0010 effective status | ADOPTED facts boundary; Snapshot Creator not implemented |
| P0 repository governance contract | MERGED |
| Main branch protection live | DISABLED |
| Required checks live | OFF |
| P0 GitHub governance | BLOCKED |

## Reading this document

This is the authoritative human-readable capability status inventory. A capability may be VERIFIED in
one evidence scope while remaining unavailable for release, production or normative adoption. GitHub
CI success is not a runtime checkpoint, release, deployment or owner-adoption claim. Exact live Git
identity is deliberately not embedded as a static "current" commit because the commit containing this
document would immediately supersede that value.

## Capability matrix

| Capability | Status | Current evidence | Current limitation |
|---|---|---|---|
| FastAPI `/api/v1` control plane | VERIFIED | system tests and established product composition | development/control-plane scope only |
| Static command-center console | VERIFIED | product platform and HTTP tests | controlled-pilot UX |
| Local bootstrap and credential login | VERIFIED | authentication/bootstrap tests | no released external identity provider |
| Context-bound bearer sessions | VERIFIED | token, identity, session lifecycle tests | local session model |
| Active-session allowlist and revocation | VERIFIED | session/user-account tests | instance-scoped administration |
| RBAC and independent approval | VERIFIED | service/composition/product tests | roles not yet workspace-scoped multi-tenant assignments |
| Workspace environment invariants | VERIFIED | service and migration tests | SQLite pilot backend |
| Change-request lifecycle | VERIFIED | change-request tests | target policy matrix remains narrower than target architecture |
| Immutable reviewed-request binding | VERIFIED | MVP-2 immutable-review binding tests and schema | does not by itself prove all snapshot/grant issuance facts |
| Production dual-approval rule | VERIFIED | governance tests | production execution remains blocked |
| Approval policy decision model | VERIFIED | focused policy and change-request tests | default-off runtime compatibility path only; Solo, Team, Regulated enforcement is not complete |
| Read-only Policy Decision Graph v1 | VERIFIED | deterministic graph/digest tests | projection only; no runtime authorization authority |
| ADR-0007 execution contracts | VERIFIED | deterministic contract/binding tests | representation only; no authoritative issuer/Runner |
| VOP canonical vocabulary | VERIFIED | PR #74 source/tests; PR-head CI #292; current-main CI #298 | verified semantic contract is not by itself normative owner adoption |
| VOP machine-readable vocabulary/digest | VERIFIED | `voodoo_product/vop_vocabulary.py` + conformance tests | registry does not create authority |
| VOP schema registry identities | IMPLEMENTED | `schemas/vop/registry.v1.json` | IDs are `RESERVED_IDS`; concrete schemas require separate implementation/conformance |
| Provider semantic mapping | VERIFIED | `ProviderSemanticMapping` source/tests; CI #292/#298 | semantic translation only; module does not authorize |
| Semantic equivalence assessment | VERIFIED | deterministic profile/assessment source/tests; CI #292/#298 | candidate equivalence does not imply adoption or activation |
| VOP normative owner adoption | UNKNOWN | no explicit VOP record in `AUTHORITY_AND_ADOPTION_REGISTER.md` | merge/CI cannot be promoted to ADOPTED by inference |
| Operation semantics contract | VERIFIED | existing semantics now consume shared VOP operation stages; current-main CI #298 | semantic contract only; not authorization authority |
| Operation proof contract | IMPLEMENTED | deterministic source/tests | no composed runtime proof pipeline |
| Skill orchestration contract | IMPLEMENTED | deterministic source/tests | planning contract only; no dynamic trusted execution |
| System control-plane decision contract | IMPLEMENTED | deterministic source/tests | no authoritative runtime dispatcher |
| Authorization Snapshot contract | IMPLEMENTED | `voodoo_product/authorization_snapshot.py` plus contract tests | construction is not yet authoritative runtime issuance |
| Authorization Snapshot append-only persistence | VERIFIED | PR #71, schema v9, store/contract/migration tests, CI #282/#283 | store accepts prevalidated snapshots; no authoritative Snapshot Creator |
| Authorization Snapshot immutable DB enforcement | VERIFIED | migration 0009 indexes/triggers and regression tests | SQLite pilot scope |
| Authorization Snapshot idempotency binding | VERIFIED | store tests and unique bindings | does not provide grant replay protection |
| Authorization Snapshot request/review binding | VERIFIED | persistence store + migration trigger validation | does not evaluate permission/policy/capability authority |
| Transaction-aware Snapshot persistence API | PROPOSED | architecture requirement identified during reconciliation | current `persist_prevalidated` opens its own transaction |
| Immutable/versioned policy authority for Snapshot Creator | PROPOSED | ADR-0010 requirements + current evaluator audit | current evaluator is insufficient as full persisted immutable authority |
| Authoritative server-side `execution.run` authority | UNKNOWN | required by ADR-0009/0010; dedicated reality audit pending | no PASS claim without source audit |
| Capability definition/activation authority | UNKNOWN | required by authorization boundary; dedicated reality audit pending | no PASS claim without source audit |
| Deterministic authoritative target binder | UNKNOWN | required by authorization boundary; dedicated reality audit pending | no PASS claim without source audit |
| Authoritative Snapshot Creator | PROPOSED | adopted ADR-0010 target; persistence prerequisite merged | not implemented |
| Authoritative ExecutionGrantIssuer | PROPOSED | adopted ADR-0009 target | not implemented |
| Grant authenticity envelope | PROPOSED | adopted ADR-0009 design scope | no implementation/signing authority path |
| Transactional outbox/dispatch | PROPOSED | target roadmap | not implemented |
| Credential broker | PROPOSED | security target boundary | not implemented |
| Isolated read-only Runner | PROPOSED | ADR-0008 adopted design/safety boundary | runtime not implemented |
| Durable one-time Runner grant consumption | PROPOSED | adopted Runner/grant requirements | runtime not implemented |
| Independent provider post-state verification | PROPOSED | target architecture | not implemented end-to-end |
| ExecutionReceipt contract | VERIFIED | ADR-0007 pure deterministic value contract | does not prove provider post-state |
| Receipt ledger | VERIFIED | receipt/evidence tests | local ledger integrity is not independent provider verification |
| Audit ledger | VERIFIED | audit/composition tests | no external signed anchor |
| Execution idempotency | VERIFIED | idempotency tests | provider-level external idempotency is capability-specific |
| Execution leases and fencing | VERIFIED | execution/recovery tests | no separate distributed Runner heartbeat |
| Indeterminate recovery under emergency stop | VERIFIED | recovery/safety tests | requires operator investigation |
| Emergency stop | VERIFIED | operational-safety/API tests | no distributed Runner cancellation yet |
| Sandbox file capability | VERIFIED | sandbox security tests | runs under current control-plane host identity |
| Allowlisted validation presets | VERIFIED | adapter/execution tests | repository content still executes under control-plane identity |
| Health and evidence separation | VERIFIED | platform-status tests | health does not prove historical evidence integrity |
| SQLite migrations and integrity gates | VERIFIED | migration tests through schema v9 | single-node pilot backend |
| Statement catalog | VERIFIED | statement-catalog tests | PostgreSQL statements are not released |
| PostgreSQL backend | BLOCKED | fail-closed startup/migration tests | intentionally unreleased |
| OIDC identity provider | BLOCKED | fail-closed identity-provider tests | no released OIDC login path |
| Local checkpoint verifier | VERIFIED | checkpoint verification tests and historical evidence | local filesystem scope |
| ProofGraph v1 JSON | VERIFIED | deterministic module and launcher output | no persistent graph store |
| P0 repository governance contract | VERIFIED | PR #75 content + PR-head CI #291 + current-main CI #298 | repository-side contract does not enforce GitHub Settings |
| Main branch PR-only protection | BLOCKED | live GitHub metadata: `protected=false` | must be configured in GitHub Settings/ruleset |
| Main required `ci / verify` enforcement | BLOCKED | live enforcement level `off`; no required contexts | must be configured and independently re-read |
| Main force-push/delete protection | BLOCKED | P0 contract requires it; live branch protection is disabled | cannot claim enforcement while branch is unprotected |
| Unrestricted production release | BLOCKED | production fail-closed gate | release, legal, Runner, signing, operations prerequisites missing |
| Public commercial distribution | BLOCKED | `LICENSE_DECISION_REQUIRED.md` | license/EULA/privacy/support unresolved |

## Verified command surfaces

```text
HTTP:
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
  python -m voodoo_product evidence verify <checkpoint>
  python -m voodoo_product evidence capture-runtime <new-candidate>
  python -m voodoo_product evidence finalize <candidate> <destination>
```

## Current release boundary

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
RELEASE_VERIFIED=NO
```

Successful CI, documentation reconciliation, VOP vocabulary presence or a local checkpoint cannot
independently change that state.

## Evidence update rule

Update this document whenever a capability, evidence scope, trust boundary, reconciliation input or
known limitation materially changes. Historical evidence must be superseded, not silently rewritten.
Exact live Git identity is always queried from Git rather than embedded as self-referential current
state. Owner adoption is read from the external adoption register and is never inferred from merge.
