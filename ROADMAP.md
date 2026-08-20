# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Reconciled | `2026-08-20` |
| Reconciliation input | `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| VOP semantic candidate | `vop-terminology-freeze-r2` / ADR-0018 |
| Capability truth | [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) |
| Current-state truth | [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) |
| Production status | BLOCKED until separately governed release |

## Status vocabulary

- **VERIFIED** — demonstrated by the named evidence scope;
- **IMPLEMENTED** — exists in source/configuration; not automatically composed/released;
- **PROPOSED** — target direction or prepared design;
- **INFERRED** — reasoned from evidence but not directly demonstrated;
- **UNKNOWN** — required evidence unavailable;
- **BLOCKED** — intentionally unavailable until a named gate passes.

Roadmap status does not prove implementation. Implementation does not prove product composition,
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
EXPLICIT TERMINAL PROFILE
+
INDEPENDENT VERIFICATION
+
PROFILE-CORRECT PORTABLE EVIDENCE
```

The mutation profile currently supports portable `OperationProof/v2 → OperationCell/v1`; READ-only
verification currently terminates at `VerificationResult/v1`. No diagram may widen those contracts.

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
| Security Intelligence R-SI1.1 | IMPLEMENTED | intelligence-only metadata/tests |

These are component/pilot/evidence milestones, not proof that FastAPI already composes one current
runtime path.

The organization-scoped approval/profile design remains separately **PROPOSED** in
[ADR-0003](docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md). Its presence does
not activate Solo, Team or Regulated behavior or weaken current human-authorization requirements.

## Current gate R1 — Truth + semantic reconciliation

**Status: IMPLEMENTED candidate / exact-head verification pending in PR #128.**

Required closure:

1. receipt/hash-chain UI never manufactures `VERIFIED`;
2. Runner never issues/consumes ExecutionGrant;
3. VOP R2 registry carries true supersession, compatibility and terminal profiles;
4. READ_ONLY does not require mutation-only Receipt/v2/Proof/v2/Cell/v1;
5. top-level docs, code, tests and registry express the same model;
6. readiness/CI fail on semantic drift;
7. historical governance uncertainty, including PR #125 provenance, stays visible.

Exit gate:

```text
P0_TRUTH = PASS
P0_RUNNER_AUTHORITY = PASS
VOP_R2_TERMINALS = PASS
VOP_R2_COMPATIBILITY = PASS
TOP_LEVEL_SOURCE_OF_TRUTH = PASS
TRUTH_DRIFT_CI = PASS
```

## Gate G0 — GitHub main enforcement

**Status: BLOCKED / live ruleset evidence UNKNOWN.**

Required baseline:

```text
PR-only main
required ci / verify on latest head
force push disabled
branch deletion disabled
conversation resolution required
ordinary admin bypass disabled
```

Classic required-status metadata was observed off. A modern ruleset may exist, but no PASS is claimed
without live settings evidence.

## Gate G1 — Canonical ProductComposition

**Status: PROPOSED next functional reconciliation slice.**

The task is to compose existing accepted components, not duplicate them.

### Shared authority/execution prefix

```text
ReviewedOperation
→ Approval
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ GrantConsumptionWitness/v1          [CONTROL PLANE]
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

### READ terminal

```text
READ_ONLY_VERIFIED
→ independent Verifier
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

### Bounded-mutation terminal

```text
BOUNDED_MUTATION_VERIFIED
→ ExecutionReceipt/v2             [effect only; NOT_EVALUATED]
→ independent Verifier
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

Required properties:

- one authority path; no compatibility authority fork;
- control-plane grant consumption only;
- exact target/capsule/epoch/fence bindings;
- explicit terminal-profile selection;
- no widening of Receipt/v2 or Proof/v2 to fit READ;
- receipt/verification separation;
- Cell only after canonical Proof/v2 recomputation;
- API/UI exposes weaker intermediate states truthfully;
- legacy ExecutionService becomes explicit compatibility boundary or is retired only after replacement
  behavior is proven.

## Gate G2 — Reusable governed WRITE / rollback orchestration

**Status: PROPOSED.**

Historical F4b/F6b workflows are evidence, not reusable product entrypoints. Current orchestration must:

- remove PR #120 / old-main hard binding;
- accept explicit capability/target/expected-state inputs;
- preserve one mutation and no automatic mutation retry;
- use ephemeral least-privilege WRITE credentials;
- require current fence immediately before effect;
- keep rollback separately authorized;
- run independent readback before `VERIFIED`;
- compose Receipt/v2→Proof/v2→Cell/v1 only for bounded mutation;
- remain inert until a separate provider-effect authorization exists.

Implementing/testing the orchestration does **not** authorize provider mutation.

## Gate G3 — Product readiness

**Status: RECONCILIATION IN PROGRESS.**

Readiness must cover:

- current trust-plane source set;
- VOP R2 registry/compatibility/terminal invariants;
- canonical ProductComposition tests;
- UI/API truth tests;
- migrations through schema 13;
- supply-chain/dependency/image gates;
- production effects disabled until separate release authorization.

## Gate G4 — Final reconciliation audit

**Status: PROPOSED.**

Require:

```text
one meaning per canonical term
code ↔ tests ↔ evidence ↔ docs aligned
one authority/execution composition
terminal profile chosen explicitly
UI/API no stronger than evidence
historical uncertainty preserved
GitHub enforcement VERIFIED or explicit release blocker
```

## Gate G5 — CyberCore

**Status: BLOCKED until G4 passes.**

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

Initial integration remains read-only/descriptive and reuses VOP canonical language. Any later active
effect must enter the same V-One authority/execution pipeline and the correct evidence terminal profile.

## Later productization

- multi-provider semantic modules;
- organization/tenant policy maturation through ADR-0003 lineage;
- released enterprise identity;
- PostgreSQL adapter/isolation gates;
- artifact provenance/signing eligibility;
- production deployment/release runbooks;
- commercial/legal/support readiness.

These remain PROPOSED or BLOCKED by their individual evidence gates.