# VOODOO One Documentation

This directory is the entry point for product, architecture, governance, specification, operational,
and release documentation.

## Start here

| Question | Document |
|---|---|
| What is the exact current evidence snapshot? | [`../CURRENT_PRODUCT_STATE.md`](../CURRENT_PRODUCT_STATE.md) |
| What is VOODOO One? | [`../VISION.md`](../VISION.md) |
| How is it built today? | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| What works now? | [`product/CURRENT_CAPABILITIES.md`](product/CURRENT_CAPABILITIES.md) |
| What should it support later? | [`product/TARGET_CAPABILITIES.md`](product/TARGET_CAPABILITIES.md) |
| What is the security overview? | [`product/SECURITY_OVERVIEW.md`](product/SECURITY_OVERVIEW.md) |
| What is the MVP delivery map? | [`product/MVP_DELIVERY_MAP.md`](product/MVP_DELIVERY_MAP.md) |
| What is the delivery order? | [`../ROADMAP.md`](../ROADMAP.md) |
| Which terms are authoritative? | [`../foundation/TERMINOLOGY.md`](../foundation/TERMINOLOGY.md) |
| What are the main trust boundaries? | [`architecture/TRUST_BOUNDARIES.md`](architecture/TRUST_BOUNDARIES.md) |
| What is the ADR-0008 evidence index? | [`governance/ADR0008_R3_EVIDENCE_INDEX.md`](governance/ADR0008_R3_EVIDENCE_INDEX.md) |
| How must documentation stay truthful? | [`governance/DOCUMENTATION_POLICY.md`](governance/DOCUMENTATION_POLICY.md) |
| How will organization roles and approval profiles work? | [`adr/ADR-0003-organization-roles-and-configurable-approval-policy.md`](adr/ADR-0003-organization-roles-and-configurable-approval-policy.md) |
| What is the accepted read-only Policy Decision Graph v1 boundary? | [`adr/ADR-0006-read-only-policy-decision-graph-v1.md`](adr/ADR-0006-read-only-policy-decision-graph-v1.md) — ACCEPTED, projection-only, no runtime integration |
| What is the accepted pure execution-contract boundary? | [`adr/ADR-0007-execution-grant-receipt-contract-v1.md`](adr/ADR-0007-execution-grant-receipt-contract-v1.md) — ACCEPTED, deterministic value contracts only |
| What is the proposed isolated Runner boundary? | [`adr/ADR-0008-isolated-runner-boundary-v1.md`](adr/ADR-0008-isolated-runner-boundary-v1.md) — PROPOSED, owner decision REQUIRED |
| What is the proposed Runner threat model? | [`security/ISOLATED_RUNNER_THREAT_MODEL_V1.md`](security/ISOLATED_RUNNER_THREAT_MODEL_V1.md) |
| How are local checkpoint candidates finalized? | [`adr/ADR-0004-repository-owned-checkpoint-finalization.md`](adr/ADR-0004-repository-owned-checkpoint-finalization.md) |

## Structure

```text
docs/
├── README.md
├── adr/            Architecture decision records and proposals
├── architecture/   Current and target component and trust-boundary models
├── governance/     Documentation and engineering governance
└── product/        Current product contracts, readiness, runbooks, and capability maps
```

The current repository also contains product composition-boundary documents in `docs/product/`.
They remain authoritative for their specific service boundaries.

## Status rule

Documentation uses only:

```text
VERIFIED
IMPLEMENTED
PROPOSED
INFERRED
UNKNOWN
BLOCKED
```

A roadmap or vision statement is not implementation evidence.
