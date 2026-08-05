# VOODOO One Architecture

| Field | Value |
|---|---|
| Document status | Accepted descriptive architecture — acceptance is declared here and must be traceable to repository or owner evidence |
| Documented implementation baseline | See `CURRENT_PRODUCT_STATE.md` and `docs/product/CURRENT_CAPABILITIES.md` |
| Current implementation at documented baseline | Modular monolith |
| Target evolution | Governed control plane plus isolated execution plane |
| Normative authority | Subordinate to the currently effective governance hierarchy and accepted ADRs |
| Live-state boundary | Not authoritative for a later HEAD, worktree, CI, runtime, release or deployment |
| Adoption and authority record | `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md` |

## Authority and freshness boundary

This document combines a documented current architecture with a clearly marked target architecture.
Statements under **documented current** sections are `DOCUMENTED_CURRENT` at the baseline referenced by
`CURRENT_PRODUCT_STATE.md`; they become `LIVE_VERIFIED` only after direct repository, test, CI or
runtime verification.

`PROJECT_CONSTITUTION.md` is a `Normative Draft` in the supplied document set. Until it is formally
adopted, this architecture is governed by the effective hierarchy recorded in
`docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`, not by the draft's self-declared authority.

## Architectural purpose

VOODOO One owns identity, policy enforcement, approvals, execution lifecycle, operational safety,
audit, receipts, and checkpoint evidence verification.

It deliberately does not own broad infrastructure discovery, vendor-specific intelligence, or an
unrestricted execution runtime.

## Documented current system context

```text
Authenticated operator / reviewer / auditor
                    |
                    v
            FastAPI HTTP boundary
                    |
                    v
        VOODOO One modular monolith
  identity | workspaces | requests | approvals
  execution | safety | audit | receipts | status
                    |
          +---------+---------+
          |                   |
          v                   v
     SQLite state        local bounded adapters
                              |
                              v
                       governed sandbox

Local operator
     |
     v
voodoo evidence verify
     |
     v
read-only checkpoint verifier -> deterministic ProofGraph JSON

Caller-supplied immutable snapshot
     |
     v
read-only PDG v1 library -> deterministic policy-decision graph + digest
     X
     +-- not wired into runtime authorization or execution
```

## Documented current components

### HTTP and console boundary

- FastAPI application with versioned `/api/v1` routes;
- trusted-host and browser security controls;
- static command-center console;
- health and evidence verification exposed as separate concerns.

### Identity and authorization

- local bootstrap and credential authentication;
- context-bound bearer tokens;
- database-backed active-session allowlist;
- role and permission enforcement;
- administrator-controlled session revocation;
- unreleased OIDC configuration fails closed.

### Governance services

- workspaces with authoritative environments;
- change requests and immutable submission semantics;
- independent approval rules;
- execution eligibility checks;
- emergency stop and recovery controls.

### Read-only policy decision projection

- accepted `policy-decision-graph/v1` pure library;
- immutable caller-supplied current-fact and `execution.run` permission observations;
- deterministic canonical nodes, edges, reason codes, limitations, and graph digest;
- deny-by-default informational projection for missing or failed current gates;
- no database, persistence, API, CLI, service composition, authorization lookup, execution gate, or
  adapter invocation;
- an `ALLOW` projection is not an execution grant and has no runtime authorization authority.

PDG v1 is owner-accepted and locally source/test VERIFIED for this read-only projection scope. The
latest runtime checkpoint attests the repository and development product image at
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`. It includes the PDG v1 source and tests but does
not upgrade the read-only projection into runtime authorization authority or integration.

### Pure execution-contract value objects

- accepted `execution-target/v1`, `approval-evidence-set/v1`, `execution-grant/v1`, and
  `execution-receipt/v1` deterministic value contracts from ADR-0007;
- canonical serialization, digest calculation, strict parsing, and cross-contract binding checks;
- no I/O, no persistence, no API wiring, no service composition, no signing, and no Runner runtime;
- representation only, not authorization authority.

ADR-0007 closes the deterministic contract shape between V-One authorization and a future isolated
Runner. It does not implement issuance, authenticity envelopes, durable one-time consumption, or
runtime execution.

### Persistence

- SQLite with ordered checksum-verified migrations;
- immutable classified SQL statement catalog;
- receipt and audit ledgers;
- execution leases, fencing, and recovery state;
- unreleased PostgreSQL support fails closed.

### Execution boundary

At the documented baseline, adapters are intentionally narrow:

- inert echo;
- bounded sandbox file output;
- allowlisted validation presets.

Production effects are disabled by default. Execution still shares the control-plane host identity;
that is an explicit limitation, not the target architecture.

### Evidence

- audit ledger;
- receipt ledger;
- independent integrity checks;
- local checkpoint verifier;
- deterministic ProofGraph v1 projection covering checkpoint, Git commit, source tree, and container
  image identity.

## Documented current data flow

```text
bootstrap or login
  -> authenticated principal
  -> workspace
  -> draft change request
  -> submitted request
  -> approval decision
  -> execution eligibility
  -> adapter execution
  -> receipt and audit event
  -> evidence verification
```

## Architectural invariants

1. Request environment must match the authoritative workspace environment.
2. A requester cannot approve their own request.
3. Production requests require independent approval and remain blocked while production effects are
   disabled.
4. Unreleased persistence and identity backends fail closed.
5. Application SQL comes from the reviewed statement catalog.
6. Execution idempotency keys bind to one request.
7. Expired executions recover only under emergency stop and late completion is fenced.
8. Liveness does not imply evidence integrity.
9. Checkpoint verification never executes checkpoint-provided code.
10. Documentation may describe target architecture only when marked PROPOSED.

## Trust boundaries

The detailed trust-boundary inventory is maintained in
[`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md).

The most important documented current boundary is:

```text
trusted governance state
        |
        | approved capability request
        v
control-plane process and local adapter
```

The principal target change is to replace that shared-process boundary with:

```text
VOODOO One
  -> durable queue or outbox
  -> short-lived execution-grant envelope (authenticity mechanism OPEN)
  -> isolated rootless runner
  -> structured receipt envelope (authenticity mechanism OPEN)
```

The reviewed ADR-0008 boundary and its threat model describe that target architecture only. They are
not implemented in the current runtime.

## Target architecture

```text
Users, AI proposal sources, CyberCore
                 |
                 v
        VOODOO One API and policy
 identity -> decision graph -> approvals
                 |
       execution-grant envelope
                 |
                 v
      Durable execution transport
                 |
                 v
         Isolated Runner Capsule
 capability allowlist | read-only root
 resource limits | network deny by default
 heartbeat | lease | fence | postconditions
                 |
           receipt envelope
                 |
       +---------+---------+
       |                   |
       v                   v
 VOODOO ledgers        CyberCore outcome
 and ProofGraph        observation/reference
```

## CyberCore boundary

CyberCore may provide observations, knowledge references, risk context, and immutable proposal
artifacts. VOODOO One remains authoritative for human identity, policy, approvals, grants, execution
lifecycle, and compliance evidence.

Initial integration must be:

- read-only;
- versioned;
- feature-flagged;
- audit-recorded;
- without shared persistence;
- without importing package-provided shell execution.

## Evolution rules

- preserve the modular monolith until a demonstrated operational boundary requires separation;
- separate execution before replacing SQLite for scale;
- add policy explanation before enabling more production capabilities;
- introduce signed grants and receipts before external mutation;
- extend ProofGraph through ADRs rather than parallel verifiers;
- avoid provider-specific behavior in the governance core.

## Related documents

- [`VISION.md`](VISION.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`foundation/FOUNDATIONS.md`](foundation/FOUNDATIONS.md)
- [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)
- [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md)
- [`GOVERNANCE.md`](GOVERNANCE.md)
- [`docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`](docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md)
- [`docs/governance/DOCUMENTATION_POLICY.md`](docs/governance/DOCUMENTATION_POLICY.md)
- [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md)
- [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md)
- [`docs/governance/ADR0008_R3_EVIDENCE_INDEX.md`](docs/governance/ADR0008_R3_EVIDENCE_INDEX.md)
- [`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md)
- [`docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md`](docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md)
- [`docs/adr/ADR-0007-execution-grant-receipt-contract-v1.md`](docs/adr/ADR-0007-execution-grant-receipt-contract-v1.md)
- [`docs/adr/ADR-0008-isolated-runner-boundary-v1.md`](docs/adr/ADR-0008-isolated-runner-boundary-v1.md)
- [`docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md`](docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md)
- [`docs/adr/`](docs/adr/)
