# Documentation Truth and Maintenance Policy

| Field | Value |
|---|---|
| Document status | Normative repository documentation policy |
| Applies to | All Markdown, diagrams, examples, release notes, and public claims |
| Owner | Repository owner with architecture and security review where applicable |
| Primary rule | Documentation must not claim more than current evidence proves |

## Purpose

VOODOO One documentation must explain:

- what the product is;
- what it currently does;
- what it is intended to do;
- what is explicitly blocked;
- why architecture decisions were made;
- how operators verify, recover, and roll back;
- which evidence supports every material capability claim.

## Document classes

### Foundation

Stable product identity, principles, and terminology.

Examples:

- `foundation/FOUNDATIONS.md`
- `foundation/TERMINOLOGY.md`

Foundation documents are descriptive and must not override the engineering constitution.

### Vision

Long-term product outcome and non-goals.

Example:

- `VISION.md`

Vision content is PROPOSED target state unless a capability is separately listed as VERIFIED.

### Architecture

Current components, boundaries, data flows, and accepted target evolution.

Examples:

- `ARCHITECTURE.md`
- `docs/architecture/*`

Material architecture and trust-boundary decisions require ADRs.

### Current capability inventory

Evidence-backed description of current behavior.

Example:

- `docs/product/CURRENT_CAPABILITIES.md`

This is the authoritative human-readable capability status document.

### Target capability map and roadmap

Ordered future work and acceptance criteria.

Examples:

- `docs/product/TARGET_CAPABILITIES.md`
- `ROADMAP.md`

Roadmap status does not prove implementation.

### Specifications

Normative contracts for behavior that implementation must satisfy.

Specifications must define version, inputs, outputs, failure behavior, security properties, tests, and
compatibility. Unimplemented specifications must be labeled PROPOSED.

### ADRs

Accepted material decisions with context, consequences, verification, and rollback.

### Runbooks

Executable operational procedures. Commands must be safe, copyable, scoped, and reality-aligned.

### Release documents

State tied to a precise version, commit, artifacts, tests, and known limitations.

## Required status taxonomy

Only these capability-state labels are permitted:

- VERIFIED
- IMPLEMENTED
- PROPOSED
- INFERRED
- UNKNOWN
- BLOCKED

`COMPLETE`, `production-ready`, `secure`, or equivalent broad claims require explicit evidence and
scope. They must not be inferred from a successful local run.

## Claim format

A material claim should include:

```text
Capability:
Status:
Evidence:
Verification scope:
Known limitations:
Owner:
Next review or milestone:
```

Tables may combine these fields when the meaning remains explicit.

## Evidence priority

When documentation conflicts with technical evidence, use:

1. current repository content;
2. Git state and history;
3. executed tests and terminal results;
4. runtime configuration and observed state;
5. CI and produced artifacts;
6. technical documentation;
7. roadmap, vision, and README.

Correct the documentation rather than rationalizing the conflict.

## Update requirements

Update relevant documentation when a change affects:

- public or operator behavior;
- architecture or module ownership;
- trust boundaries;
- identity or authorization;
- persistence;
- execution;
- evidence formats;
- deployment or recovery;
- released capability status;
- roadmap sequence;
- known limitations.

Every accepted capability change must consider:

- `README.md`;
- `CURRENT_CAPABILITIES.md`;
- `TARGET_CAPABILITIES.md`;
- `ROADMAP.md`;
- relevant architecture or runbook;
- changelog and release notes.

## Current versus target language

Use:

- “currently provides” only for IMPLEMENTED or VERIFIED capabilities;
- “is designed to” or “target” for PROPOSED capabilities;
- “remains blocked” for unavailable security-sensitive capability;
- “not verified” when evidence scope is missing.

Do not use future architecture diagrams without labeling the current and target boundaries.

## Evidence and runtime files

Source documentation belongs in Git.

Runtime logs, databases, secrets, generated evidence, and checkpoint payloads do not belong in the
working tree. They must be stored in a separate evidence root, frozen after execution, hashed, and
included in a governed checkpoint when long-term retention is required.

## Review cycles

- current capabilities: every accepted capability change and checkpoint;
- roadmap: every milestone transition;
- architecture: every material boundary change;
- security and runbooks: after incidents and before releases;
- vision and foundations: at major product-direction review;
- release documents: per release candidate.

## Automated enforcement

Repository tests and product readiness must verify at least:

- required documentation exists;
- the documentation index and root README link to core documents;
- current capability states use the allowed taxonomy;
- roadmap distinguishes current and future work;
- foundation documents do not claim superior authority over governance files.

Automated checks support review; they do not replace owner approval.
