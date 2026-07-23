# VOODOO One Documentation

This directory is the entry point for product, architecture, governance, specification, operational,
and release documentation.

## Start here

| Question | Document |
|---|---|
| What is VOODOO One? | [`../VISION.md`](../VISION.md) |
| How is it built today? | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| What works now? | [`product/CURRENT_CAPABILITIES.md`](product/CURRENT_CAPABILITIES.md) |
| What should it support later? | [`product/TARGET_CAPABILITIES.md`](product/TARGET_CAPABILITIES.md) |
| What is the delivery order? | [`../ROADMAP.md`](../ROADMAP.md) |
| Which terms are authoritative? | [`../foundation/TERMINOLOGY.md`](../foundation/TERMINOLOGY.md) |
| What are the main trust boundaries? | [`architecture/TRUST_BOUNDARIES.md`](architecture/TRUST_BOUNDARIES.md) |
| How must documentation stay truthful? | [`governance/DOCUMENTATION_POLICY.md`](governance/DOCUMENTATION_POLICY.md) |

## Structure

```text
docs/
├── README.md
├── adr/            Accepted architecture decisions
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
