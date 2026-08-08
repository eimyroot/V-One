# Trust Boundaries

| Field | Value |
|---|---|
| Document status | Current and target trust-boundary inventory |
| Security posture | Deny by default and fail closed |
| Production effects | BLOCKED until separately released |
| Update trigger | Any material identity, execution, persistence, evidence, or integration change |

## Boundary map

```text
[Untrusted client input]
        |
        v
[HTTP security and authentication]
        |
        v
[Authenticated principal]
        |
        v
[Authorization and governance services]
        |
        +------------------+
        |                  |
        v                  v
[SQLite state]      [Execution adapter boundary]
                           |
                           v
                    [Sandbox / validation target]

[Untrusted checkpoint]
        |
        v
[Read-only local verifier]
        |
        v
[Deterministic JSON claims and ProofGraph]

ADR-0007 accepted contract layer:

[execution-target / approval-evidence-set / execution-grant / execution-receipt]
        |
        v
[Pure deterministic representation only; no runtime authority]

OWNER-ADOPTED ADR-0008 target boundary (runtime not implemented):

[V-One authorization and lifecycle]
        |
        v
[Durable dispatch / immutable grant reference]
        |
        v
[Runner admission + atomic one-time consumption]
        |
        v
[Digest-bound retrieval + capability registry]
        |
        v
[Rootless capsule / separate OS identity / network denied]
        |
        v
[Independent postcondition verifier]
        |
        v
[Bounded receipt and evidence -> V-One ingestion]
```

## TB-01 — HTTP client to application

**Current status:** VERIFIED for the current test scope.

Controls:

- exact trusted-host enforcement;
- browser security headers and no-store behavior;
- structured input validation;
- bearer authentication;
- rate limiting;
- permission checks.

Residual risks:

- current deployment is not an unrestricted internet-facing release;
- external identity integration is not released.

## TB-02 — Credential and session material

**Current status:** VERIFIED for local authentication.

Controls:

- runtime-supplied secrets;
- purpose-derived signing and reference keys;
- context-bound token format;
- active-session allowlist;
- audited logout and administrative revocation;
- raw session nonces excluded from persistence.

Residual risks:

- no released OIDC, MFA, or enterprise key-rotation boundary;
- local instance roles are not workspace-scoped tenancy.

## TB-03 — Governance services to persistence

**Current status:** VERIFIED for SQLite.

Controls:

- checksum-verified ordered migrations;
- central statement catalog;
- transactionally enforced invariants;
- bounded connections;
- integrity verification;
- unsupported backend fails closed.

Residual risks:

- SQLite is a single-node pilot backend;
- database administrators can rewrite complete hash chains unless evidence is externally anchored.

## TB-04 — Governance to execution adapter

**Current status:** IMPLEMENTED and VERIFIED for narrow local capabilities; target isolation is
PROPOSED.

Current controls:

- allowlisted adapter names;
- typed payload validation;
- bounded output;
- execution timeout;
- idempotency, lease, and fence;
- emergency-stop recovery;
- production effects disabled.

Residual risks:

- adapter process shares the control-plane operating-system identity;
- repository validation tools may execute repository-controlled behavior;
- no resource or network sandbox;
- emergency stop does not yet provide distributed runner cancellation;
- provider-side idempotency is not generalized.

Target:

```text
control plane
  -> durable outbox
  -> signed one-time grant
  -> isolated runner
  -> signed receipt
```

## TB-05 — Sandbox filesystem

**Current status:** VERIFIED for current tests.

Controls:

- relative path contract;
- segment-by-segment symlink rejection;
- opened-directory identity verification;
- no-follow file handling;
- atomic replacement;
- size limits.

Residual risks:

- local process identity still owns both control plane and sandbox;
- hostile same-user processes remain outside the current threat isolation.

## TB-06 — Audit and receipt evidence

**Current status:** VERIFIED for chain integrity.

Controls:

- canonical evidence serialization;
- monotonic receipt ordering;
- independent audit and receipt verification;
- explicit evidence endpoint.

Residual risks:

- hash chains are not external non-repudiation;
- no signing key identity or external anchor.

## TB-07 — Local checkpoint verification

**Current status:** VERIFIED.

The checkpoint is untrusted input.

Controls:

- symlink and special-file rejection;
- strict complete manifest coverage;
- SHA-256 recomputation;
- Git bundle verification with isolated Git configuration;
- source archive inspection without extraction;
- temporary bare repository;
- no network, Docker, registry, or checkpoint-provided code execution;
- deterministic output.

Residual risks:

- same-user race against mutable local files;
- remote Drive bytes are not independently verified;
- signatures are not implemented;
- nested evidence producers may have post-manifest log mutations, reported as warnings.

## TB-08 — CI and supply chain

**Current status:** VERIFIED for current repository CI configuration; signed provenance is PROPOSED.

Current controls:

- hash-locked dependencies;
- pinned workflow actions;
- read-only CI permissions;
- tests, readiness, dependency audit, Docker build, and smoke;
- manually gated release-candidate workflow.

Residual risks:

- no signed provenance or registry promotion policy;
- base image tag is not committed by digest;
- multi-platform verification is not established.

## TB-09 — CyberCore or external intelligence input

**Current status:** PROPOSED.

Initial boundary must allow only normalized read-only metadata and immutable references.

Forbidden in the first slice:

- direct apply;
- package-provided shell execution;
- shared database access;
- provider credentials;
- unbounded payload storage;
- implicit trust based on transport.

## TB-10 — AI proposal source

**Current status:** PROPOSED.

AI output is untrusted proposal content until validated.

AI may draft and explain. AI may not:

- authenticate as an approver without a real principal;
- change its own risk or policy result;
- issue a grant;
- enable production effects;
- suppress missing evidence.

## TB-11 — V-One to isolated Runner v1

**Design status:** ADOPTED by explicit owner decision on 2026-08-08. **Runtime status:** PROPOSED /
not implemented. ADR-0007 accepted the deterministic contract layer above, but that representation
does not authorize execution by itself.

Authoritative boundary:

- V-One owns identity, policy, approvals, grant issuance, cancellation intent, execution lifecycle,
  receipt ingestion, audit, and production-effect gating;
- the Runner owns durable one-time consumption, capsule lifecycle, resource enforcement, attempt
  observations, independent postcondition execution, and Runner receipt claims;
- the Runner never authorizes itself, and AI or CyberCore input remains proposal-only.

Target controls:

- one grant authorizes one attempt; atomic durable consumption occurs before any side effect;
- canonical versioned capability registry; arbitrary shell is not a capability and unknown
  capabilities fail closed;
- payload and target retrieval uses immutable digest-bound references and rehashes bytes inside the
  Runner boundary;
- separate Runner OS identity, fresh rootless capsule, read-only base, bounded writable workspace,
  resource limits, and network deny by default;
- cancellation, bounded leases, monotonic fencing, heartbeat, duplicate-delivery safety, and
  fail-closed recovery;
- postcondition verification is independent from the handler; uncertain post-state is
  `INDETERMINATE`;
- grants, receipts, dispatch records, logs, and general evidence contain no secrets;
- production effects remain blocked.

Rollout blockers and residual risks:

- current persisted approvals cannot authoritatively issue ADR-0007 grants with all required
  bindings;
- grant/receipt authenticity, transport, trust store, key lifecycle, durable dispatch and consume
  stores, capsule technology, target-side fencing, secret delivery, and receipt reconciliation are
  not implemented; ADR-0007 value contracts do not replace those runtime controls;
- a separate OS identity and rootless capsule do not eliminate kernel, runtime, provider, or
  supply-chain compromise;
- exactly-once external effect is unavailable without provider idempotency or target-side fencing;
- mutating rollout requires the verification gates in
  `docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md` and independent R3 review;
- production effects require a separate R4 owner decision and release evidence.

## Security review priorities

1. ADR-0008 child R3 decisions for durable consumption, isolation technology, and postcondition runtime enforcement;
2. grant and receipt authenticity, trust policy, and key lifecycle;
3. external evidence anchoring and signing;
4. output redaction and raw-log authorization;
5. workspace-scoped identity;
6. CyberCore read-only intake schema;
7. multi-platform supply-chain verification.
