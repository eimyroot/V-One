# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Reconciled | `2026-08-20` |
| Reconciliation base | `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| Reconciliation candidate | PR #128 / `feat/reconciliation-p0-p1-r1` |
| VOP semantic candidate | `vop-terminology-freeze-r2` / ADR-0018 |
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
| Runner identity/boundary + credential decisions | VERIFIED | source/tests/pilot scope |
| Isolated READ Runner | VERIFIED | D4b live governed read |
| Independent verifier | VERIFIED | E3 live verifier observation |
| VerificationResult/v1 | VERIFIED | E4b + F6b evidence |
| Bounded CREATE_REF | VERIFIED | historical F4b pilot |
| Bounded DELETE_REF rollback | VERIFIED | historical F6b pilot |
| ExecutionReceipt/v2 | VERIFIED | bounded-mutation contract + F6b |
| OperationProof/v2 | VERIFIED | bounded-mutation contract + F6b |
| OperationCell/v1 | VERIFIED | bounded-mutation contract + F6b |
| Capability→terminal allowlist | IMPLEMENTED | PR #128 tests |
| Database-backed product permission authority | IMPLEMENTED | PR #128 tests |
| Canonical authority/dispatch/lease pipeline | IMPLEMENTED | PR #128 tests |
| Canonical READ Runner→Verifier terminal | IMPLEMENTED | PR #128 composition tests + existing D4b/E3/E4b evidence |
| ProductComposition canonical runtime seam | IMPLEMENTED | PR #128 composition tests |
| Reusable CREATE_REF A09 preflight orchestration | IMPLEMENTED | PR #128 tests; no provider effect |
| Reusable rollback A09 preflight orchestration | IMPLEMENTED | PR #128 tests; no provider effect |
| Security Intelligence R-SI1.1 | IMPLEMENTED | intelligence-only metadata/tests |

These rows do not authorize new provider mutation or release.

The organization-scoped approval/profile design remains separately **PROPOSED** in
[ADR-0003](docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md). Its presence does
not activate Solo, Team or Regulated behavior and does not weaken current human-authorization safety
requirements.

## Gate R1 — Truth + semantic reconciliation

**Status: IMPLEMENTED CANDIDATE / final exact-head closure pending in PR #128.**

Required closure:

1. receipt/hash-chain UI never manufactures `VERIFIED`;
2. Runner never issues/consumes ExecutionGrant;
3. VOP R2 registry carries true supersession, compatibility and terminal profiles;
4. READ_ONLY does not require mutation-only Receipt/v2/Proof/v2/Cell/v1;
5. top-level docs, code, tests and registry express the same model;
6. readiness/CI fail on semantic drift;
7. historical governance uncertainty, including PR #125 provenance, stays visible.

## Gate G0 — GitHub main enforcement

**Status: BLOCKED / live ruleset evidence UNKNOWN.**

Required release baseline:

```text
PR-only main
required latest-head ci / verify
force push disabled
branch deletion disabled
conversation resolution required
ordinary admin bypass disabled
```

Successful CI does not prove these Settings/ruleset controls.

## Gate G1 — Canonical ProductComposition

**Status: IMPLEMENTED CANDIDATE in PR #128.**

Current candidate composition:

```text
ProductService database
→ DatabasePermissionAuthority
→ AuthoritativeSnapshotCreator
→ ExecutionGrant/v2
→ atomic consume + DispatchOutbox
→ DispatchEnvelope + Inbox admission
→ ExecutionEpoch/Lease/current fence
→ immutable capability→terminal binding
→ CanonicalOperationRuntime
```

Properties now enforced:

- one product database boundary;
- one database-backed permission authority;
- stale Principal role/state cannot preserve stronger permission;
- no caller-selected stronger terminal profile;
- no second authority path;
- default app remains fail-closed unless an explicit canonical runtime factory/provider pack is supplied;
- legacy `ExecutionService` remains an explicit compatibility API surface, not hidden fallback authority.

The canonical public HTTP operation endpoint is a later product-surface task and is not inferred from
ProductComposition wiring.

## Gate G2 — Profile-specific terminal composition

**Status: IMPLEMENTED CANDIDATE in PR #128.**

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

PR #128 only prepares current WRITE/rollback effects through A09 and does not execute this tail.

## Gate G3 — Reusable governed WRITE / rollback orchestration

**Status: IMPLEMENTED PRE-EFFECT CANDIDATE / NOT EXECUTED.**

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

Required properties satisfied by the candidate design/tests:

- no PR120/old-main/ref/SHA hard binding in A09;
- explicit current capability/target lineage;
- no automatic provider mutation retry;
- scoped credential decision metadata without secret serialization;
- current fence immediately before preflight readiness;
- rollback remains separately authorized;
- no provider transport call inside A09;
- no new CREATE_REF or DELETE_REF execution in this reconciliation work.

A preflight is not a provider effect and cannot be presented as `VERIFIED`.

## Gate G4 — Product readiness

**Status: FINAL EXACT-HEAD GATE PENDING.**

Readiness now inventories:

- canonical pipeline/runtime/router;
- capability terminal allowlist;
- database permission authority;
- READ terminal;
- A09 CREATE/rollback orchestration;
- current trust-plane contracts and profile semantics;
- canonical ProductComposition tests;
- UI/API truth tests;
- migrations through schema 13;
- supply-chain/dependency/image gates;
- production effects disabled until separate release authorization.

Exit requires one exact candidate head with:

```text
CI = SUCCESS
D4b = SUCCESS
E3 = SUCCESS
E4b = SUCCESS
```

Intermediate runs do not attest later commits.

## Gate G5 — R3 adversarial review

**Status: PENDING FINAL HEAD.**

Review must attack at least:

- terminal-profile privilege escalation;
- stale Principal / role-change authority;
- parallel ProductComposition authority/database paths;
- Runner/Verifier identity or credential collapse;
- A09 hidden provider transport/effect;
- stale lease/fence bypass;
- rollback provenance substitution;
- receipt/verification/proof/cell semantic conflation;
- historical evidence upgraded into current provider execution claims.

Organizational independence must be reported truthfully; self-review is not independent review.

## Gate G6 — Final reconciliation audit

**Status: PENDING FINAL HEAD + R3.**

Require:

```text
one meaning per canonical term
code ↔ tests ↔ evidence ↔ docs aligned
one authority/execution composition
terminal profile derived from capability identity
current DB-backed permission authority
profile-specific Runner + verifier terminal
A09 WRITE/rollback reusable but inert
UI/API no stronger than evidence
historical uncertainty preserved
GitHub enforcement VERIFIED or explicit release blocker
```

## Gate G7 — CyberCore

**Status: BLOCKED until G6 passes.**

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

Initial integration remains descriptive/read-only and must reuse the canonical VOP language. Any later
active effect enters the same V-One authority/execution pipeline and its capability-bound terminal.

## Later productization

- canonical public operation API/UI surface;
- multi-provider semantic/runtime packs;
- organization/tenant policy maturation through ADR-0003 lineage;
- released enterprise identity;
- PostgreSQL adapter/isolation gates;
- artifact provenance/signing eligibility;
- production deployment/release runbooks;
- commercial/legal/support readiness.

These remain PROPOSED or BLOCKED by their individual evidence gates.
