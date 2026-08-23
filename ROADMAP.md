# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Reconciled | `2026-08-23` |
| Reconciliation base | historical `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| Reconciliation merge | PR #128 / `d9e27ff17b76f29daba4a3421b11cc396826fe12` |
| VOP semantic revision | `vop-terminology-freeze-r2` / ADR-0018 |
| Capability truth | [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) |
| Current-state truth | [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) |
| Production status | BLOCKED until separately governed release |

## Status vocabulary

- **VERIFIED** — demonstrated by the named evidence scope;
- **IMPLEMENTED** — exists in source/configuration; not automatically live/released;
- **PROPOSED** — target direction or prepared design;
- **INFERRED** — reasoned from evidence but not directly demonstrated;
- **UNKNOWN** — required evidence unavailable;
- **BLOCKED** — intentionally unavailable until a named gate passes.

Roadmap status does not prove implementation. Implementation does not prove live provider effect,
independent verification, release or deployment.

## Architectural invariant

```text
ONE SYSTEM
=
ONE CANONICAL OPERATION LANGUAGE
+
ONE AUTHORITY LINEAGE
+
ONE EXECUTION LINEAGE
+
CURRENT WORKSPACE SCOPE
+
CAPABILITY-BOUND TERMINAL PROFILE
+
INDEPENDENT VERIFICATION
+
PROFILE-CORRECT PORTABLE EVIDENCE
```

The mutation profile supports portable `OperationProof/v2 → OperationCell/v1`; READ-only verification
terminates at `VerificationResult/v1`. No diagram or compatibility path may widen those contracts.

## Completed technical milestones

| Track | Status | Evidence boundary |
|---|---|---|
| AuthorizationSnapshot + authoritative creator | VERIFIED | source/tests + schema 0009 |
| ExecutionGrant/v2 + durable grant service | VERIFIED | source/tests + schema 0010 |
| Grant consumption + transactional Outbox | VERIFIED | source/tests + schema 0011 |
| Dispatch Envelope + Inbox/dedup | VERIFIED | source/tests + schema 0012 |
| ExecutionEpoch/Lease + DurableCoordinator | VERIFIED | source/tests + schema 0013 |
| Workspace membership scope | IMPLEMENTED | schema 0014 + membership/revocation tests |
| Runner identity/boundary + credential decisions | VERIFIED | source/tests/pilot scope |
| Isolated READ Runner | VERIFIED | D4b live governed read |
| Independent verifier | VERIFIED | E3 live verifier observation |
| VerificationResult/v1 | VERIFIED | E4b + F6b evidence |
| Bounded CREATE_REF | VERIFIED | historical F4b pilot |
| Bounded DELETE_REF rollback | VERIFIED | historical F6b pilot |
| ExecutionReceipt/v2 | VERIFIED | bounded-mutation contract + F6b |
| OperationProof/v2 | VERIFIED | bounded-mutation contract + F6b |
| OperationCell/v1 | VERIFIED | bounded-mutation contract + F6b |
| Capability→terminal allowlist | IMPLEMENTED | merged PR #128 tests |
| Database-backed product permission authority | IMPLEMENTED | merged PR #128 tests |
| Canonical authority/dispatch/lease pipeline | IMPLEMENTED | merged PR #128 tests |
| Canonical READ Runner→Verifier terminal | IMPLEMENTED | merged PR #128 composition tests + D4b/E3/E4b evidence |
| ProductComposition canonical runtime seam | IMPLEMENTED | merged PR #128 composition tests |
| Reusable CREATE_REF A09 preflight orchestration | IMPLEMENTED | merged PR #128 tests; no provider effect |
| Reusable rollback A09 preflight orchestration | IMPLEMENTED | merged PR #128 tests; no provider effect |
| Security Intelligence R-SI1.1 | IMPLEMENTED | intelligence-only metadata/tests |
| Security Intelligence R-SI1.2 normalization | IMPLEMENTED | merged PR #135; descriptive/context-only |

These rows do not authorize new provider mutation or release.

The organization-scoped approval/profile design remains separately **PROPOSED** in
[ADR-0003](docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md). Its presence does
not activate Solo, Team or Regulated behavior and does not weaken current human-authorization safety
requirements. Workspace membership introduced by schema 14 is only a current scope boundary; it is
not adoption of that organization-policy design.

## Gate R1 — Truth + semantic reconciliation

**Status: VERIFIED / MERGED via PR #128.**

Closed properties:

1. receipt/hash-chain UI never manufactures `VERIFIED`;
2. Runner never issues/consumes ExecutionGrant;
3. VOP R2 registry carries true supersession, compatibility and terminal profiles;
4. READ_ONLY does not require mutation-only Receipt/v2/Proof/v2/Cell/v1;
5. top-level docs, code, tests and registry express the same model;
6. readiness/CI fail on semantic drift;
7. historical governance uncertainty, including PR #125 provenance, stays visible;
8. global role authority cannot cross workspace boundaries without current membership;
9. schema-13 history does not fabricate schema-14 membership.

Final pre-merge head `fcdd43578860bf8bf01f85b3f088bb5c6d21526c` passed CI #839, D4b #157,
E3 #148 and E4b #144. The self/adversarial R3 passed with organizationally independent review absent;
the remaining independence risk was explicitly accepted for that merge. That risk acceptance is not a
standing bypass for future high-risk changes.

## Gate G0 — GitHub main enforcement

**Status: BLOCKED until fresh live verifier evidence returns `VERIFIED`.**

Required release baseline:

```text
PR-only main
required latest-head check = verify / workflow ci
force push disabled
branch deletion disabled
conversation resolution required
ordinary admin/ruleset bypass disabled
```

Merged PR #134 provides the fail-closed live verifier and evidence workflow. Repository automation is
not GitHub Settings enforcement: G0 becomes PASS only from a fresh live verifier result proving every
required control. Historical branch metadata or successful CI cannot substitute for that evidence.

**G0 remains a release-governance blocker until that live result is VERIFIED.**

## Gate G1 — Canonical ProductComposition

**Status: IMPLEMENTED / MERGED via PR #128.**

Current composition:

```text
ProductService database
→ current active user + global role + workspace/environment + membership
→ DatabasePermissionAuthority
→ AuthoritativeSnapshotCreator
→ ExecutionGrant/v2
→ atomic consume + DispatchOutbox
→ DispatchEnvelope + Inbox admission
→ ExecutionEpoch/Lease/current fence
→ immutable capability→terminal binding
→ CanonicalOperationRuntime
```

Properties enforced:

- one product database boundary;
- one database-backed permission authority;
- stale Principal role/state cannot preserve stronger permission;
- membership revocation is observed before durable grant store/one-time consume;
- global role does not imply membership in arbitrary workspaces;
- no legacy membership inference/backfill during schema-14 migration;
- no caller-selected stronger terminal profile;
- no second authority path;
- default app remains fail-closed unless an explicit canonical runtime factory/provider pack is supplied;
- legacy `ExecutionService` remains an explicit compatibility API surface, not hidden fallback authority.

The canonical public HTTP operation endpoint is implemented as the G7 candidate below; default provider
runtime activation remains a separate G8 gate.

## Gate G2 — Profile-specific terminal composition

**Status: IMPLEMENTED / MERGED via PR #128.**

### READ terminal

```text
READ_ONLY_VERIFIED
→ isolated READ Runner
→ Runner observation
→ durable completion
→ independent verifier boundary/credential
→ independent observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

The terminal reuses existing D4b/E3/E4b contracts; it does not create a parallel verifier model.

### Bounded mutation terminal

Completed mutation semantics remain:

```text
BOUNDED_MUTATION_VERIFIED
→ provider mutation
→ ExecutionReceipt/v2
→ independent Verifier
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

Merged PR #128 only prepared current WRITE/rollback effects through A09 and did not execute this tail.

## Gate G3 — Reusable governed WRITE / rollback orchestration

**Status: IMPLEMENTED PRE-EFFECT / MERGED / NOT EXECUTED.**

CREATE_REF path:

```text
CanonicalPreparedExecution
→ write safety bindings
→ exact request
→ WriteEffectPreflight/v1
→ STOP
```

Rollback path:

```text
CanonicalPreparedExecution
→ exact rollback provenance
→ current pre-delete observation
→ current fence recheck
→ RollbackWriteEffectPreflight/v2
→ STOP
```

Current properties:

- no PR120/old-main/ref/SHA hard binding in A09;
- explicit current capability/target lineage;
- no automatic provider mutation retry;
- scoped credential decision metadata without secret serialization;
- current fence immediately before preflight readiness;
- rollback remains separately authorized;
- no provider transport call inside A09;
- no new CREATE_REF or DELETE_REF execution in reconciliation work.

A preflight is not a provider effect and cannot be presented as `VERIFIED`.

## Gate G4 — Product readiness baseline

**Status: VERIFIED for merged PR #128 baseline; every later head requires fresh evidence.**

The PR #128 exact-head CI covered:

- canonical pipeline/runtime/router;
- capability terminal allowlist;
- database permission authority;
- workspace membership statement/migration boundary;
- READ terminal;
- A09 CREATE/rollback orchestration;
- current trust-plane contracts and profile semantics;
- canonical ProductComposition tests;
- UI/API truth tests;
- migrations through schema 14;
- supply-chain/dependency/image gates;
- production effects disabled.

Current readiness inventory also requires the merged G0 verifier/workflow/baseline and the G7 canonical
HTTP surface plus its adversarial tests. A historical PASS is never reused for a later candidate head.

## Gate G5 — R3 adversarial review baseline

**Status: COMPLETED for PR #128 with retained governance risk.**

The review attacked terminal-profile escalation, stale role/Principal authority, cross-workspace access,
membership revocation/backfill, parallel ProductComposition authority, Runner/Verifier collapse, A09
hidden provider transport, stale lease/fence, rollback provenance substitution and evidence-semantic
conflation.

Organizationally independent review was **not present**. The owner accepted that remaining risk for PR
#128 only. Future high-risk changes require their own review/risk decision.

## Gate G6 — Reconciliation audit

**Status: PASS / MERGED.**

The merged baseline established:

```text
one meaning per canonical term
code ↔ tests ↔ evidence ↔ docs aligned
one authority/execution composition
current role + active state + workspace membership scope
terminal profile derived from capability identity
profile-specific Runner + verifier terminal
A09 WRITE/rollback reusable but inert
UI/API no stronger than evidence
historical uncertainty preserved
GitHub enforcement retained as explicit release blocker
```

## Gate G7 — Canonical public operation API

**Status: IMPLEMENTED CANDIDATE / PR #137 / exact-head closure pending.**

Candidate public surface:

```text
GET  /api/v1/operations/status
POST /api/v1/operations/{request_id}/read
```

Properties implemented in the candidate:

- versioned FastAPI request/response schemas;
- same product IdentityProvider at the HTTP boundary;
- outer `execution.run` permission plus authoritative database-backed role/active/membership revalidation in the canonical runtime;
- mandatory `Idempotency-Key` and bounded correlation id;
- request body rejects unknown fields, including caller-supplied `terminal_profile`;
- READ route internally requires exactly `READ_ONLY_VERIFIED + github.read-ref/v1`;
- route/profile/capability mismatch fails before Grant issuance/consumption;
- missing READ terminal fails before canonical authority preparation;
- response separates `execution.status` from independent `verification.verdict`, including the truthful state `SUCCEEDED + NOT_VERIFIED`;
- OpenAPI exposes no canonical CREATE_REF, DELETE_REF or rollback route;
- legacy `ExecutionService` remains an explicit compatibility surface and is not canonical fallback authority.

This candidate does **not** activate a provider runtime pack. With no explicit G8 runtime factory,
`/operations/status` reports the fail-closed state and READ execution returns service unavailable rather
than falling back to ambient credentials or legacy execution.

G7 exits only after fresh exact-head CI/readiness plus final adversarial review. Merge remains a separate
owner gate.

## Gate G8 — Explicit provider runtime pack

**Status: BLOCKED / default remains fail-closed.**

First productized runtime pack should be READ-first and explicitly configured. It must:

- share the exact ProductComposition database/permission authority;
- use separate Runner and Verifier identities/credential decisions;
- preserve current fence/lease checks;
- fail closed if provider configuration or credentials are unavailable;
- expose no ambient provider authority;
- require fresh live verification before being called product-ready.

Mutation runtime remains a later, separately authorized gate.

## Gate G9 — Release / deployment readiness

**Status: BLOCKED.**

Before release/deploy:

- G0 GitHub enforcement live evidence;
- merged/verified G7 canonical public API;
- G8 READ runtime pack;
- fresh security/adversarial review;
- dependency/SBOM/image/provenance gates;
- secrets/credential rotation and operational runbooks;
- observability/incident/rollback plan;
- commercial/legal/privacy/support requirements as applicable;
- explicit release authorization;
- explicit deployment authorization.

Production effects stay disabled until those gates are separately satisfied.

## Gate G10 — CyberCore

**Status: BLOCKED during V-One product/release-governance hardening.**

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

Initial integration remains descriptive/read-only and must reuse the canonical VOP language. Any later
active effect enters the same V-One authority/execution pipeline and its capability-bound terminal.
CyberCore must not become a workaround for unfinished V-One product/release controls.

## Later productization

- organization/tenant policy maturation through ADR-0003 lineage;
- released enterprise identity / MFA / OIDC;
- PostgreSQL adapter/isolation gates;
- artifact provenance/signing eligibility;
- production deployment/release runbooks;
- commercial/legal/support readiness.

These remain PROPOSED or BLOCKED by their individual evidence gates.
