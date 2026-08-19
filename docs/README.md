# VOODOO One Documentation

This directory is the entry point for product, architecture, governance, specification, operational
and release documentation. Live Git/CI/runtime evidence outranks static current-state wording.

## Start here

| Question | Document |
|---|---|
| What is the exact current evidence snapshot? | [`../CURRENT_PRODUCT_STATE.md`](../CURRENT_PRODUCT_STATE.md) |
| What is VOODOO One? | [`../VISION.md`](../VISION.md) |
| How is it built today? | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| What works now? | [`product/CURRENT_CAPABILITIES.md`](product/CURRENT_CAPABILITIES.md) |
| What should it support later? | [`product/TARGET_CAPABILITIES.md`](product/TARGET_CAPABILITIES.md) |
| What is the security overview? | [`product/SECURITY_OVERVIEW.md`](product/SECURITY_OVERVIEW.md) |
| What is the Security Intelligence R-SI1.1 authority ceiling? | [`product/SECURITY_INTELLIGENCE_RSI1_BOUNDARY.md`](product/SECURITY_INTELLIGENCE_RSI1_BOUNDARY.md) |
| What is the MVP delivery map? | [`product/MVP_DELIVERY_MAP.md`](product/MVP_DELIVERY_MAP.md) |
| What is the delivery order? | [`../ROADMAP.md`](../ROADMAP.md) |
| Which foundation terms are used? | [`../foundation/TERMINOLOGY.md`](../foundation/TERMINOLOGY.md) |
| What is the canonical VOP vocabulary? | [`architecture/VOP_CANONICAL_VOCABULARY.md`](architecture/VOP_CANONICAL_VOCABULARY.md) |
| What are the current trust boundaries? | [`architecture/TRUST_BOUNDARIES.md`](architecture/TRUST_BOUNDARIES.md) |
| What is the ADR-0008 historical R3 evidence index? | [`governance/ADR0008_R3_EVIDENCE_INDEX.md`](governance/ADR0008_R3_EVIDENCE_INDEX.md) |
| How must documentation stay truthful? | [`governance/DOCUMENTATION_POLICY.md`](governance/DOCUMENTATION_POLICY.md) |
| How will organization roles and approval profiles work? | [`adr/ADR-0003-organization-roles-and-configurable-approval-policy.md`](adr/ADR-0003-organization-roles-and-configurable-approval-policy.md) — still PROPOSED |
| What is the read-only Policy Decision Graph v1 boundary? | [`adr/ADR-0006-read-only-policy-decision-graph-v1.md`](adr/ADR-0006-read-only-policy-decision-graph-v1.md) |
| What is the historical pure execution-contract v1 boundary? | [`adr/ADR-0007-execution-grant-receipt-contract-v1.md`](adr/ADR-0007-execution-grant-receipt-contract-v1.md) |
| What is the owner-adopted isolated Runner design boundary? | [`adr/ADR-0008-isolated-runner-boundary-v1.md`](adr/ADR-0008-isolated-runner-boundary-v1.md) — historical design authority retained; later bounded pilot implementation/evidence is tracked separately |
| What threat model is bound to ADR-0008? | [`security/ISOLATED_RUNNER_THREAT_MODEL_V1.md`](security/ISOLATED_RUNNER_THREAT_MODEL_V1.md) — exact reviewed artifact remains immutable; later implementation does not rewrite it |
| What is the current OperationProof/v2 decision? | [`adr/ADR-0015-operation-proof-v2-current-lineage-r1.md`](adr/ADR-0015-operation-proof-v2-current-lineage-r1.md) — ACCEPTED / MERGED |
| What is the current OperationCell/v1 decision? | [`adr/ADR-0017-operation-cell-v1-r1.md`](adr/ADR-0017-operation-cell-v1-r1.md) — ACCEPTED / MERGED |
| How are local checkpoint candidates finalized? | [`adr/ADR-0004-repository-owned-checkpoint-finalization.md`](adr/ADR-0004-repository-owned-checkpoint-finalization.md) |

## Current truth hierarchy

For runtime/technical state use, in order:

```text
current repository content
→ live Git identity
→ executed tests / GitHub CI
→ runtime/pilot evidence
→ current-state docs
→ roadmap/vision intent
```

Normative document authority is separate and follows governance/adoption records.

## Current architecture distinction

```text
TRUST-PLANE COMPONENT CHAIN = deeply implemented/tested
HISTORICAL COMPLETE F6b OPERATION ATOM = VERIFIED
ONE CANONICAL FastAPI ProductComposition THROUGH OperationCell = NOT YET IMPLEMENTED
```

Do not collapse component presence, product composition, live verification and release into one
status.

## Structure

```text
docs/
├── README.md
├── adr/            Architecture decisions, historical decisions and proposals
├── architecture/   Current semantic/component/trust-boundary models
├── governance/     Documentation, authority and engineering governance
├── product/        Current capabilities, boundaries, readiness and runbooks
└── security/       Security threat-model artifacts
```

## Status rule

Capability documentation uses only:

```text
VERIFIED
IMPLEMENTED
PROPOSED
INFERRED
UNKNOWN
BLOCKED
```

A roadmap, ADR presence, merge, CI pass or evidence hash must not be promoted into a stronger runtime,
release or deployment claim without the required independent evidence.
