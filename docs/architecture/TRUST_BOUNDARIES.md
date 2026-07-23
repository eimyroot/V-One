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

## Security review priorities

1. isolated runner grant and receipt contracts;
2. external evidence anchoring and signing;
3. output redaction and raw-log authorization;
4. workspace-scoped identity;
5. CyberCore read-only intake schema;
6. multi-platform supply-chain verification.
