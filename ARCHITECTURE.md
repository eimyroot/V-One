# VOODOO One Architecture

| Field | Value |
|---|---|
| Document status | Accepted descriptive architecture |
| Current implementation | Modular monolith |
| Target evolution | Governed control plane plus isolated execution plane |
| Normative authority | Subordinate to the engineering constitution and accepted ADRs |

## Architectural purpose

VOODOO One owns identity, policy enforcement, approvals, execution lifecycle, operational safety,
audit, receipts, and checkpoint evidence verification.

It deliberately does not own broad infrastructure discovery, vendor-specific intelligence, or an
unrestricted execution runtime.

## Current system context

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

## Current components

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
latest runtime checkpoint attests exactly
`main@8a5f36b218c3aa6dce2e4cf771512875f136d839`; it does not attest PDG v1 or
subsequent source changes.

### Persistence

- SQLite with ordered checksum-verified migrations;
- immutable classified SQL statement catalog;
- receipt and audit ledgers;
- execution leases, fencing, and recovery state;
- unreleased PostgreSQL support fails closed.

### Execution boundary

Current adapters are intentionally narrow:

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

## Current data flow

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

The most important current boundary is:

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
  -> signed short-lived execution grant
  -> isolated rootless runner
  -> structured signed receipt
```

## Target architecture

```text
Users, AI proposal sources, CyberCore
                 |
                 v
        VOODOO One API and policy
 identity -> decision graph -> approvals
                 |
          signed execution grant
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
          structured signed receipt
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
- [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md)
- [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md)
- [`docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md`](docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md)
- [`docs/adr/`](docs/adr/)
