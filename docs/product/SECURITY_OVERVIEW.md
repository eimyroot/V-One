# VOODOO One 0.9.0-rc2-dev — Security Overview

> Current security posture is evidence-scoped. This development version is not an unrestricted
> production release and production effects remain disabled by default.

## Product/control-plane controls

Current released/local product controls include:

- no hardcoded authentication secret;
- `scrypt` password hashing with per-user salt;
- context-bound v2 sessions with purpose-derived signing keys;
- database-backed active-session allowlisting and revocation;
- raw bearer/session nonce exclusion from persistence;
- persistent HMAC-keyed login/bootstrap throttling;
- exact trusted-host validation, CSP, no-store/no-sniff/anti-frame headers and production-only HSTS;
- live account/role revalidation and permission-based RBAC;
- requester/approver separation and workspace-authoritative environment classification;
- production effects disabled by default;
- emergency stop and explicit recovery boundaries;
- checksum-governed SQLite migrations and reviewed statement catalog;
- hash-chained receipt and audit ledgers with separate integrity verification;
- bounded legacy local adapters, filesystem path hardening and subprocess-without-shell controls.

These controls describe the currently composed product surface. They do not by themselves attest the
newer isolated execution/verification path for every FastAPI execution.

## Current VOP authority controls

Implemented/tested trust-plane components now include:

```text
AuthorizationSnapshot
→ ExecutionGrant/v2
→ durable one-time Grant consumption in CONTROL PLANE
→ DispatchOutboxEntry/v1
→ DispatchEnvelope/v1
→ DispatchInboxAdmission/v1
→ ExecutionEpoch + ExecutionLease/v1
→ CurrentExecutionFence
→ ExecutionCapsule / RunnerBoundary
```

Key authority invariant:

```text
Runner does not issue or consume ExecutionGrants.
Grant consumption occurs before Dispatch in the control plane.
Dispatch/lease/fence coordinate execution but do not create new authority.
```

SQLite persistence is current through schema 13. `VOODOO_DATABASE_BACKEND=sqlite` remains the only
released database mode; selecting unreleased PostgreSQL support fails closed.

## Isolated bounded Runner evidence

The repository contains RunnerIdentity, RunnerBoundary, credential-decision, runtime-activation and
provider-boundary contracts/tests. Bounded isolated GitHub READ behavior has real D4b/E3/E4b pilot
evidence, with controls including exact runtime identity/binding, read-only filesystem/rootfs choices
for the pilot, dropped Linux capabilities, bounded resources and default-deny egress with explicit
provider allowlisting.

This does **not** mean the legacy FastAPI `ExecutionService` path has been replaced by that isolated
execution plane. ProductComposition convergence is a separate gate.

Historical F4b/F6b staging workflows additionally demonstrated narrowly scoped GitHub mutation and
rollback paths. Those historical workflows are evidence artifacts, not generic current production
mutation entrypoints.

## Execution receipt versus verification

`ExecutionReceipt/v2` records the execution subsystem claim and must not manufacture independent
verification state.

```text
ExecutionReceipt != VerificationResult
receipt-chain integrity != independent provider verification
execution succeeded != VERIFIED
```

The UI/API must therefore expose weaker intermediate state when independent verification is absent.

## Independent verification controls

The accepted verifier path separates:

- Runner identity/instance;
- Verifier identity/instance;
- credential class;
- provider readback;
- observed post-state;
- verification-strength classification;
- final `VerificationResult/v1`.

D4b/E3/E4b and historical F6b provide bounded GitHub readback evidence. The verifier path is READ-only
for the accepted verification scope and must not inherit provider-mutation authority.

## Proof and operation-cell controls

`OperationProof/v2` accepts current execution evidence only after canonical independent-verification
recomputation for its lineage. A merely self-consistent forged `VERIFIED` result is insufficient.

`OperationCell/v1` is a minimal stable atom over a canonically revalidated `OperationProof/v2`; it
contains no credential/provider authority and does not widen execution authority.

```text
VerificationResult != OperationProof
OperationProof != OperationCell
OperationCell != authority
```

Historical F6b evidence has a strictly validated proof and cell, but that historical success does not
release production or automatically compose the current FastAPI product path.

## Legacy local execution safety boundary

The currently composed legacy `ExecutionService` still uses narrow local adapters. Existing safety
controls include:

- adapter allowlisting;
- typed/bounded payloads and output;
- descriptor-relative sandbox writes with symlink/path checks;
- subprocess invocation without a shell;
- execution idempotency;
- legacy lease/fence recovery;
- emergency stop;
- production-effects gate.

This compatibility path shares the product/control-plane process identity and must not be described as
equivalent to the separately exercised isolated Runner pilot boundary.

## Identity and HTTP boundary

OIDC configuration remains unreleased and fail closed. The released `local` identity provider owns
session issuance/verification and uses separate credential-authentication, active-user lookup and
session-lifecycle ports. External groups must not become internal roles without a separately governed
mapping/integration gate.

The application does not trust arbitrary client forwarding headers. Any production reverse proxy must
be explicitly trusted/configured at the ASGI boundary.

Supported start commands suppress raw Uvicorn access logging; structured middleware logs only
allowlisted metadata and avoid request bodies, headers, query strings, raw account identifiers and
unexpected exception internals.

## Persistence / migration boundary

SQLite migration history is immutable/checksum verified and current through `0013`. Grant, dispatch
and coordination tables use fail-closed binding/immutability rules appropriate to their contracts.
There are no automated down migrations; rollback of an incompatible schema requires restoring a full
pre-upgrade database/WAL/SHM backup.

PostgreSQL remains a future release gate requiring an adapter, dialect-neutral service boundaries,
transactional migration locking, concurrency tests, backup/restore operations and tenant-isolation
proofs.

## Supply-chain / release boundary

The manual release-candidate workflow:

- validates source version;
- reruns verification;
- builds and smoke-tests the product image;
- produces source/SBOM checksums.

Checksums provide integrity, not signer identity. Signed provenance/attestation remains separately
gated. CI, a merge, a historical provider pilot, OperationProof or OperationCell is not deployment or
release evidence.

## GitHub governance boundary

Repository policy requires PR-only `main`, latest-head `ci / verify`, no force push/delete and
conversation resolution. Available connector evidence does not prove the complete modern GitHub
ruleset; classic required-status enforcement is observed off. Therefore live repository enforcement
remains `UNKNOWN / BLOCKED` until settings/ruleset evidence proves the full baseline.

## Security Intelligence / CyberCore

Security Intelligence R-SI1.1 is descriptive metadata/test logic only. CyberCore is an intelligence
participant only. Neither may:

- issue AuthorizationSnapshot or ExecutionGrant;
- consume a Grant;
- become Runner or Verifier by inference;
- bypass human/policy gates;
- cause provider mutation outside the canonical V-One lifecycle.

CyberCore integration remains blocked until reconciliation and canonical ProductComposition gates
pass.

## Required gates before enterprise/unrestricted release

- canonical authority→OperationCell ProductComposition path;
- current reusable governed WRITE/rollback orchestration with separately authorized provider effects;
- verified live GitHub main enforcement;
- external penetration test;
- dependency/container scanning and release evidence;
- released enterprise identity/role mapping;
- tenant-specific key management;
- PostgreSQL tenant/isolation/concurrency gates if PostgreSQL is released;
- signed SBOM/artifact provenance strategy;
- incident/vulnerability disclosure contacts;
- licensing, privacy, support and deployment runbooks.

Until those gates pass:

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
UNRESTRICTED_PRODUCTION=BLOCKED
```
