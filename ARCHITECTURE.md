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

## Proposed canonical VOP language invariant

The proposed VOP canonical-vocabulary contract is maintained in
[`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md).

It introduces the proposed architectural invariant:

```text
ONE SYSTEM
=
ONE SEMANTIC LANGUAGE
```

Provider-specific terminology remains behind Module boundaries. Where V-One concepts mean the same
thing across UI, API, persistence, audit, CLI, AI tooling and proof, they should converge on one
canonical VOP term and one versioned contract rather than parallel synonyms.

This section is **PROPOSED**, not an assertion that all listed VOP schemas, runtime composition or
package boundaries are already implemented or adopted. The machine-readable vocabulary registry and
its CI conformance gate are preparatory architecture controls only.

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
11. Proposed canonical-language semantics must not be treated as runtime authority merely because the
    vocabulary registry exists.

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
- avoid provider-specific behavior in the governance core;
- evolve VOP schemas incrementally from the canonical registry rather than performing a broad package rewrite.

## Related documents

- [`VISION.md`](VISION.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`foundation/FOUNDATIONS.md`](foundation/FOUNDATIONS.md)
- [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)
- [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md)
- [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md)
- [`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md)
- [`docs/governance/ADR0008_R3_EVIDENCE_INDEX.md`](docs/governance/ADR0008_R3_EVIDENCE_INDEX.md)
- [`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md)
- [`docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md`](docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md)
- [`docs/adr/ADR-0007-execution-grant-receipt-contract-v1.md`](docs/adr/ADR-0007-execution-grant-receipt-contract-v1.md)
- [`docs/adr/ADR-0008-isolated-runner-boundary-v1.md`](docs/adr/ADR-0008-isolated-runner-boundary-v1.md)
- [`docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md`](docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md)
- [`docs/adr/`](docs/adr/)
