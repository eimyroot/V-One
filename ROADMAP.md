# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Reconciled | `2026-08-20` |
| Reconciliation input | `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| Capability truth | [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) |
| Current-state truth | [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) |
| Production status | BLOCKED until a separately governed release |

## Status vocabulary

- **VERIFIED** — demonstrated by the named current evidence scope;
- **IMPLEMENTED** — exists in source/configuration but is not automatically verified/composed/released;
- **PROPOSED** — target direction or prepared design;
- **INFERRED** — reasoned from available evidence but not directly demonstrated;
- **UNKNOWN** — required evidence is unavailable;
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
INDEPENDENT VERIFICATION
+
PORTABLE PROOF
+
STABLE OPERATION CELL
```

Provider/capability count may grow; the trusted semantic core must not grow proportionally.

## Completed technical milestones

The old roadmap that still described Snapshot Creator, Grant Issuer, Dispatch, Runner, Verification
and OperationProof as future work is superseded. Current source/evidence has progressed through these
bounded milestones:

| Track | Status | Evidence boundary |
|---|---|---|
| AuthorizationSnapshot persistence + authoritative creation prerequisites | VERIFIED | source/tests + migrations |
| ExecutionGrant/v2 + durable grant service | VERIFIED | source/tests + schema 0010 |
| Grant consumption + transactional Outbox | VERIFIED | Phase C source/tests + schema 0011 |
| Dispatch Envelope + Inbox/dedup | VERIFIED | Phase C source/tests + schema 0012 |
| ExecutionEpoch/Lease + DurableCoordinator | VERIFIED | Phase C source/tests + schema 0013 |
| Runner identity/boundary + credential decisions | VERIFIED | source/tests/pilot scope |
| Isolated READ Runner | VERIFIED | D4b live governed read |
| Independent verifier | VERIFIED | E3 live verifier observation |
| VerificationResult/v1 | VERIFIED | E4b + F6b evidence |
| Bounded CREATE_REF | VERIFIED | historical F4b live canary |
| Bounded DELETE_REF rollback | VERIFIED | historical F6b live governed delete |
| ExecutionReceipt/v2 | VERIFIED | source/tests + F6b real receipt |
| OperationProof/v2 | VERIFIED | source/tests + historical F6b proof |
| OperationCell/v1 | VERIFIED | source/tests + historical F6b cell |
| Security Intelligence R-SI1.1 | IMPLEMENTED | metadata/test slice, intelligence-only |

These are component/pilot/evidence milestones. They do **not** mean the current FastAPI product has one
fully composed runtime path through every row.

## Current critical gate — Reconciliation R1

**Status: IMPLEMENTED candidate / verification in progress (PR #128).**

Purpose: converge product truth before any CyberCore integration.

Required closure:

1. receipt/hash-chain UI must never manufacture `VERIFIED`;
2. Runner must not issue or consume ExecutionGrants;
3. `OperationProof/v2` and `OperationCell/v1` must be in canonical vocabulary/registry;
4. current state, capability map, roadmap, trust boundaries, security overview and changelog must
   describe the same architecture;
5. CI/readiness must fail when current contracts escape canonical registry/truth coverage;
6. historical governance uncertainty, especially PR #125 merge-authorization provenance, remains
   visible rather than rewritten.

Exit gate:

```text
P0_TRUTH = PASS
P0_RUNNER_AUTHORITY = PASS
VOP_REGISTRY_CURRENT = PASS
TOP_LEVEL_SOURCE_OF_TRUTH = PASS
TRUTH_DRIFT_CI = PASS
```

## Gate G0 — GitHub main enforcement

**Status: BLOCKED / live ruleset evidence UNKNOWN.**

Repository baseline requires:

```text
PR-only main
required ci / verify on latest head
force push disabled
branch deletion disabled
conversation resolution required
ordinary admin bypass disabled
```

Classic required-status metadata is observed off. A modern ruleset may exist, but no PASS may be
claimed until live settings/ruleset evidence proves the complete baseline.

## Gate G1 — Canonical ProductComposition lifecycle

**Status: PROPOSED next implementation track after Reconciliation R1.**

Underlying components already exist. The task is to compose, not duplicate them.

Target runtime/API lineage:

```text
ReviewedOperation
→ Approval
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ GrantConsumptionWitness/v1     [CONTROL PLANE]
→ DispatchOutboxEntry/v1
→ DispatchEnvelope/v1
→ DispatchInboxAdmission/v1
→ ExecutionEpoch + ExecutionLease/v1
→ ExecutionCapsule/v1
→ RunnerIdentity + RunnerBoundary
→ CredentialAccessDecision
→ RuntimeActivation
→ Provider effect / Observation
→ ExecutionReceipt/v2            [NOT verification]
→ independent Verifier
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

Required properties:

- one authority path, no compatibility-path authority fork;
- no Runner-side grant consumption;
- exact target/capsule/epoch/fence bindings retained;
- receipt and verification remain separate;
- operation cell emitted only after canonical proof recomputation;
- public API/UI exposes weaker intermediate states truthfully;
- legacy ExecutionService path either becomes an explicit compatibility boundary or is retired only
  after replacement tests prove equivalent required product behavior.

## Gate G2 — Reusable governed WRITE / rollback orchestration

**Status: PROPOSED.**

Historical F4b/F6b pilots are evidence, not reusable product entrypoints. The current path must:

- remove hard binding to PR #120 / historical main SHA;
- preserve explicit capability/target/expected-state binding;
- preserve one mutation/no automatic retry semantics;
- make WRITE credential delivery ephemeral and least privilege;
- require current execution fence immediately before effect;
- keep rollback separately authorized;
- run independent readback before any `VERIFIED` outcome;
- never activate provider mutation merely because workflow code exists.

Design/implementation of this workflow is allowed as a separate R3 slice; **executing a provider
mutation remains a separate explicit effect authorization**.

## Gate G3 — Product readiness / release truth

**Status: BLOCKED.**

Readiness must cover the current trust-plane contract set, not only the legacy product surface.
Required before release consideration:

- current VOP components included in readiness inventory;
- canonical lifecycle composition tests;
- truth-surface tests;
- migrations through schema 13;
- supply-chain/dependency/image gates;
- external security/release prerequisites from security documentation;
- production effects remain disabled until separate release authorization.

## Gate G4 — Final reconciliation audit

**Status: PROPOSED.**

After G1–G3 candidate work, rerun the large reconciliation audit and require:

```text
canonical language = one meaning per term
code ↔ tests ↔ evidence ↔ docs = aligned
ProductComposition lifecycle = one canonical path
UI/API truth = no stronger claim than evidence
historical uncertainty = preserved
GitHub enforcement = VERIFIED or explicit release blocker
```

## Gate G5 — CyberCore integration

**Status: BLOCKED until G4 passes.**

CyberCore enters only as an intelligence/context/learning/proposal participant:

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

First integration slices must be read-only/descriptive and must reuse VOP canonical language. Any
future active effect still travels through the same V-One authority → execution → independent
verification → proof/cell chain.

## Later productization

After the above gates:

- multi-provider semantic modules;
- organization/tenant policy maturation;
- released enterprise identity;
- PostgreSQL adapter and isolation gates;
- artifact provenance/signing eligibility;
- production deployment/release runbooks;
- commercial/legal/support readiness.

These remain PROPOSED or BLOCKED according to their individual evidence gates; nothing in the
reconciliation work silently releases them.
