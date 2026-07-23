# VOODOO One Vision

| Field | Value |
|---|---|
| Document status | Accepted product direction |
| Capability status | PROPOSED target state with VERIFIED current foundations |
| Owner | VOODOO product and architecture owner |
| Review cycle | At every material product or trust-boundary change |

## Purpose

VOODOO One exists to make consequential operational change understandable, authorized, controlled,
and provable.

Its product identity is:

> **Governed Change Authorization & Evidence Control Plane**

VOODOO One accepts change intent from people or automated systems, evaluates policy, requires the
right independent approvals, authorizes a precisely bounded execution, and preserves evidence about
what was requested, allowed, attempted, and observed.

## Problem

Infrastructure and software changes become dangerous when any of these questions cannot be answered:

- Who requested the change?
- What exact target and environment were affected?
- What evidence justified the change?
- Which policy version governed the decision?
- Who approved the exact payload?
- What actually ran?
- What result and post-state were observed?
- Can the evidence be independently verified?
- Can a failed or indeterminate operation be recovered safely?

VOODOO One is designed to answer those questions without making automation itself the authority.

## Product promise

The product should provide one governed path:

```text
intent
  -> structured change request
  -> policy evaluation
  -> independent approval
  -> bounded execution grant
  -> controlled execution
  -> postcondition verification
  -> audit, receipt, and ProofGraph evidence
```

## Long-term system model

```text
CyberCore or another intelligence source
  observations -> evidence -> knowledge -> proposal
                         |
                         | versioned references
                         v
VOODOO One
  identity -> policy -> approvals -> execution grant -> evidence
                         |
                         | short-lived capability grant
                         v
Isolated Runner
  preflight -> apply -> postflight -> signed receipt
                         |
                         v
ProofGraph
  source -> decision -> build -> execution -> receipt -> checkpoint
```

The intended division of responsibility is:

- **CyberCore or another intelligence source:** system of understanding;
- **VOODOO One:** system of authorization and governed lifecycle;
- **isolated runner:** system of action;
- **ProofGraph:** system of evidence.

## Principles

1. Humans remain authoritative at material mutation boundaries.
2. AI may propose, explain, correlate, draft, and review; it may not silently approve itself.
3. Approval must bind to exact content, target, environment, policy, and validity period.
4. Execution must use capabilities, not arbitrary user-provided shell commands.
5. Production effects remain disabled until separately released with evidence.
6. Evidence must distinguish integrity, provenance, authorization, execution, and observed outcome.
7. Failure, uncertainty, and indeterminate outcomes must remain visible.
8. Current capability claims must never be inferred from roadmap or vision documents.
9. Small, reversible vertical slices are preferred over broad rewrites.
10. CyberCore integration, if adopted, begins read-only and without a shared database.

## Intended users

- administrators;
- operators;
- security reviewers;
- auditors;
- developers proposing governed changes;
- AI-assisted systems that submit proposals but do not own authorization.

## Success outcomes

VOODOO One is successful when:

- materially risky changes cannot bypass policy and independent approval;
- approval becomes invalid when its governed inputs drift;
- execution is isolated from the control-plane identity;
- every execution has a structured, bounded, and verifiable result;
- evidence can be independently checked without trusting the running application;
- operators can understand why an action is allowed, blocked, failed, or indeterminate;
- recovery and rollback procedures are explicit before mutation;
- production activation is a governed release decision, not a configuration accident.

## Non-goals

VOODOO One is not intended to become:

- a generic autonomous shell agent;
- a duplicate infrastructure inventory or knowledge platform;
- a second implementation of CyberCore;
- an unbounded provider-specific automation monolith;
- a replacement for Terraform, Ansible, monitoring, or provider APIs;
- a system that treats AI confidence as authorization;
- an unrestricted production platform before runner isolation, signed evidence, and release gates exist.

## Current reality

The current repository provides a tested development control-plane baseline, local adapters with
production effects disabled, and a local checkpoint ProofGraph verifier. It is not an unrestricted
production release.

The authoritative current-state inventory is
[`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md). The delivery sequence
is maintained in [`ROADMAP.md`](ROADMAP.md).
