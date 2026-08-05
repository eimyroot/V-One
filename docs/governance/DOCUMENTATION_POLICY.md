# Documentation Truth and Maintenance Policy

| Field | Value |
|---|---|
| Document status | Normative repository documentation policy |
| Applies to | All Markdown, diagrams, examples, release notes and public claims |
| Owner | Repository owner with architecture and security review where applicable |
| Adoption evidence | Must be recorded in `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`; file presence alone is not adoption |
| Primary rule | Documentation must not claim more than current evidence proves |
| Live-state boundary | This policy governs claims; it does not itself prove the current repository or runtime state |

## Purpose

VOODOO One documentation must explain:

- what the product is;
- what it currently does;
- what it is intended to do;
- what is explicitly blocked;
- why architecture decisions were made;
- how operators verify, recover, and roll back;
- which evidence supports every material capability claim.

## Authority, adoption and evidence are separate

Documentation must keep these dimensions separate:

| Dimension | Meaning |
|---|---|
| `DECLARED` | the document states a role, status or authority about itself or another artifact |
| `ADOPTED` | an explicit owner decision or accepted ADR records that the artifact is effective |
| `DOCUMENTED_CURRENT` | a dated document describes state at an identified baseline |
| `LIVE_VERIFIED` | state was checked directly against current Git, tests, CI, artifacts or runtime |
| `INFERRED` | a conclusion is derived from evidence but not explicitly demonstrated |
| `UNKNOWN` | available evidence does not establish the claim |

A document may be `DECLARED` as normative but still not be `ADOPTED`. A snapshot may be
`DOCUMENTED_CURRENT` but not `LIVE_VERIFIED`. Merge, review, upload to GPT knowledge, or presence in
the repository does not by itself prove adoption.

The canonical adoption and authority record is
`docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`.

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

Material architecture decisions and proposals with context, consequences, verification, and rollback. A proposed ADR must state `PROPOSED`, must not claim implementation, and becomes accepted only through explicit owner and required architecture or security review.

### Runbooks

Executable operational procedures. Commands must be safe, copyable, scoped, and reality-aligned.

### Release documents

State tied to a precise version, commit, artifacts, tests, and known limitations.

## Required status taxonomy

Only these capability-state labels are permitted:

- `VERIFIED` — all stated gates for the exact claim and scope are evidenced;
- `PARTIALLY_VERIFIED` — a precisely identified subset is verified and missing gates are listed;
- `IMPLEMENTED` — implementation exists but has not met every verification gate;
- `PROPOSED` — intended or under review; not necessarily adopted and not implemented;
- `INFERRED` — derived from evidence but not directly demonstrated;
- `UNKNOWN` — evidence is unavailable or conflicting;
- `BLOCKED` — intentionally unavailable or unsafe to proceed.

Do not use spelling variants such as `PARTIALLY VERIFIED` in machine-readable status fields.

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

## Normative authority versus evidence priority

Normative authority determines what rules **should govern**. Evidence priority determines what is
**actually present or observed**. Neither substitutes for the other.

When documentation conflicts with technical evidence about current implementation or runtime, use:

1. current repository content;
2. Git state and history;
3. executed tests and terminal results;
4. runtime configuration and observed state;
5. CI and produced artifacts;
6. technical documentation;
7. roadmap, vision, and README.

Correct the documentation rather than rationalizing the conflict. If the implementation violates an
adopted higher-authority rule, the result is not to declare the implementation authoritative; record
the non-compliance, block unsafe operation and reconcile through an approved change.

## Adoption record requirements

A document that claims normative, mandatory, constitutional or accepted status must have an entry in
`docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md` containing at least:

```text
DOCUMENT:
VERSION:
DECLARED_STATUS:
EFFECTIVE_STATUS:
OWNER:
ADOPTION_METHOD:
ADOPTION_DATE:
ADOPTION_COMMIT:
CONTENT_SHA256:
SUPERSEDES:
CONFLICTS_RESOLVED:
NEXT_REVIEW:
```

If the entry or required evidence is missing, the effective status is `UNKNOWN` or `PROPOSED`; do not
silently infer `ADOPTED`.

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
- current capability states use the allowed taxonomy and canonical spelling;
- roadmap distinguishes current, partially verified, proposed and blocked work;
- foundation and draft documents do not claim effective authority without an adoption record;
- every normative, mandatory, constitutional or accepted document has a complete authority-register
  entry;
- snapshot documents state their baseline and live-state limitation;
- links among governance, architecture, capability and evidence documents resolve.

Automated checks support review; they do not replace owner approval.
