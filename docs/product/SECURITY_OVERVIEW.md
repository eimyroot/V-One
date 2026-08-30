# VOODOO One 0.9.0-rc2-dev — Security Overview

> Current security posture is evidence-scoped. This development version is not an unrestricted
> production release and production effects remain disabled by default.

## Product/control-plane controls

Current product controls include:

- no hardcoded authentication secret;
- `scrypt` password hashing with per-user salt;
- context-bound v2 sessions with purpose-derived signing keys;
- database-backed active-session allowlisting and revocation;
- raw bearer/session nonce exclusion from persistence;
- persistent HMAC-keyed login/bootstrap throttling;
- exact trusted-host validation, CSP, no-store/no-sniff/anti-frame headers and production-only HSTS;
- live account/role revalidation and permission-based RBAC;
- explicit current user↔workspace membership scope in addition to global role;
- requester/approver separation and workspace-authoritative environment classification;
- production effects disabled by default;
- emergency stop and explicit recovery boundaries;
- checksum-governed SQLite migrations and reviewed statement catalog;
- hash-chained receipt and audit ledgers with separate integrity verification;
- bounded legacy local adapters, filesystem path hardening and subprocess-without-shell controls.

These controls do not by themselves imply that the default G8 provider runtime is active, that every
FastAPI request uses a provider runtime, or that unrestricted production execution is released.

## Current VOP authority controls

Implemented/tested trust-plane components include:

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

Canonical product authority additionally requires current database-backed actor state: active user,
global role, exact workspace, workspace environment and exact user↔workspace membership. That decision
is evaluated at snapshot creation and revalidated inside the SQLite serialized boundary at durable
Grant store and one-time Grant consumption, so a membership removed before consumption fails closed.
This does not claim retroactive cancellation of an already-consumed/running execution attempt.

SQLite persistence is current through schema 14. `VOODOO_DATABASE_BACKEND=sqlite` remains the only
current released database mode; selecting unreleased PostgreSQL support fails closed.

## Canonical public READ API and resume

PR #137 merged the canonical READ HTTP surface:

```text
GET  /api/v1/operations/status
POST /api/v1/operations/{request_id}/read
```

PR #140 reconciled that surface with restart-safe durable resume and runtime resume wiring. The public
request cannot select a stronger terminal profile and is narrowed to exactly:

```text
READ_ONLY_VERIFIED + github.read-ref/v1
```

The merged resume path reconstructs only the same already-authorized durable execution. It must not
re-enter canonical `prepare()`, issue a second Grant, consume the Grant again, append duplicate
Outbox/Inbox admission, or reacquire a lease. It revalidates current database authority, persisted
lineage, terminal profile, envelope revision and current execution fence.

Post-merge evidence on `main@60bc9c26813ee23c73bac194a9adb27714e8a1e8` includes CI #1015,
D4 #202, E3 #193 and E4B #189, all SUCCESS. That is G7 evidence, not G8 default-runtime or release
evidence.

## Isolated bounded Runner evidence

The repository contains RunnerIdentity, RunnerBoundary, credential-decision, runtime-activation and
provider-boundary contracts/tests. Bounded isolated GitHub READ behavior has real D4b/E3/E4b pilot
evidence, with controls including exact runtime identity/binding, read-only filesystem/rootfs choices
for the pilot, dropped Linux capabilities, bounded resources and default-deny egress with explicit
provider allowlisting.

The canonical product runtime seam is merged and the public READ API is surfaced. The default G8
provider runtime pack nevertheless remains absent/fail-closed. Existing pilot evidence must not be
relabelled as proof that the default application has a live provider runtime.

Historical F4b/F6b staging workflows additionally demonstrated narrowly scoped GitHub mutation and
rollback paths. Those historical workflows are evidence artifacts, not generic current production
mutation entrypoints and do not authorize a new WRITE effect.

## Execution receipt versus verification

`ExecutionReceipt/v2` records the execution subsystem claim and must not manufacture independent
verification state.

```text
ExecutionReceipt != VerificationResult
receipt-chain integrity != independent provider verification
execution succeeded != VERIFIED
```

The UI/API must therefore expose weaker intermediate state when independent verification is absent.
A truthful result may be:

```text
execution.status      = SUCCEEDED
verification.verdict  = NOT_VERIFIED
```

## Independent verification controls

The accepted verifier path separates:

- Runner identity/instance;
- Verifier identity/instance;
- credential class/decision;
- provider readback;
- observed post-state;
- verification-strength classification;
- final `VerificationResult/v1`.

D4b/E3/E4b and historical F6b provide bounded GitHub readback evidence. The verifier path is READ-only
for the accepted verification scope and must not inherit provider-mutation authority.

The first G8 provider runtime must preserve this separation and may not use one ambient credential as
implicit authority for both Runner and Verifier.

## Proof and operation-cell controls

`OperationProof/v2` accepts current bounded-mutation execution evidence only after canonical
independent-verification recomputation for its lineage. A merely self-consistent forged `VERIFIED`
result is insufficient.

`OperationCell/v1` is a minimal stable atom over a canonically revalidated `OperationProof/v2`; it
contains no credential/provider authority and does not widen execution authority.

```text
VerificationResult != OperationProof
OperationProof != OperationCell
OperationCell != authority
```

Historical F6b evidence has a strictly validated proof and cell, but that historical success does not
release production or prove any new provider effect.

## Legacy local execution safety boundary

The composed legacy `ExecutionService` remains an explicit compatibility surface. Existing safety
controls include:

- adapter allowlisting;
- typed/bounded payloads and output;
- descriptor-relative sandbox writes with symlink/path checks;
- subprocess invocation without a shell;
- execution idempotency;
- legacy lease/fence recovery;
- emergency stop;
- production-effects gate.

This path must not become fallback canonical authority when the explicit provider runtime is absent.
The canonical READ API is surfaced separately and G8 must fail closed rather than route through legacy
execution or ambient provider credentials.

## Identity and HTTP boundary

OIDC configuration remains unreleased and fail closed. The current `local` identity provider owns
session issuance/verification and uses separate credential-authentication, active-user lookup and
session-lifecycle ports. External groups must not become internal roles without a separately governed
mapping/integration gate.

The application does not trust arbitrary client forwarding headers. Any production reverse proxy must
be explicitly trusted/configured at the ASGI boundary.

Supported start commands suppress raw Uvicorn access logging; structured middleware logs only
allowlisted metadata and avoid request bodies, headers, query strings, raw account identifiers and
unexpected exception internals.

## Persistence / migration boundary

SQLite migration history is immutable/checksum verified and current through `0014`. Schema 14 adds
explicit workspace membership state without fabricating memberships for historical schema-13
workspaces. Grant, dispatch and coordination tables use fail-closed binding/immutability rules
appropriate to their contracts. There are no automated down migrations; rollback of an incompatible
schema requires restoring a full pre-upgrade database/WAL/SHM backup.

PostgreSQL remains a future release gate requiring an adapter, dialect-neutral service boundaries,
transactional migration locking, concurrency tests, backup/restore operations and tenant-isolation
proofs.

## GitHub governance boundary

G0 is no longer `UNKNOWN`. It is tied to retained live verifier evidence:

```text
workflow = g0-governance-verify
run = 32553113424
event = workflow_dispatch
source_sha = 76d74d2ed62b6e78f027728c456c22da0b4a95bd
artifact = g0-governance-evidence-32553113424-1
artifact_id = 9470619984
artifact_digest = sha256:6e63caee23a57613471df66ef0279c0261ed8d375e4c929accdf50eff7dc4f5f
evidence_json_checksum = 11a99765485b63b70186037011d31c105dea8dd75b689e0036a8766d05e8137d
verdict = VERIFIED
```

That evidence verified PR-only main, required latest-head `verify` from workflow `ci`, force-push and
branch-deletion protection, conversation resolution, no ordinary bypass, active rulesets and verifier
source binding.

```text
G0 = PASS
```

G0 PASS is repository-governance evidence only. It does not authorize a provider runtime, production
effect, release or deployment.

## READ-before-WRITE boundary

ADR-0019 is currently `PROPOSED — governed adoption pending` and creates no authority before its gate
closes. The proposed rule keeps provider WRITE blocked until repeated real canonical authenticated HTTP
READ E2E proves all of:

```text
READ_E2E             = VERIFIED
RESTART_RESUME       = VERIFIED
NO_DUPLICATE_EFFECT  = VERIFIED
AUTHORITY_CONTINUITY = VERIFIED
INDEPENDENT_VERIFY   = VERIFIED
FAIL_CLOSED          = VERIFIED
```

Even after that evidence, WRITE would become only `ELIGIBLE`, not authorized. A provider mutation still
requires a separate effect-specific decision, credential scope, review, post-state verification,
rollback semantics, release and deployment gates.

## G8 security boundary

The next provider-runtime milestone is READ-only. G8 must reuse the canonical ProductComposition,
GitHub READ transport, READ terminal and resume contracts; it must not create a parallel execution or
authority framework.

Required fail-closed properties include:

- exact ProductService database and DatabasePermissionAuthority;
- exact canonical terminal-profile registry, envelope revision and current fence;
- explicit Runner and Verifier provider configuration;
- separate Runner and Verifier identities/credential decisions;
- no ambient `GITHUB_TOKEN` fallback;
- no CREATE_REF, DELETE_REF, rollback, generic execute or arbitrary mutation transport;
- missing or ambiguous configuration aborts activation.

Real canonical HTTP READ E2E through this default pack remains **NOT VERIFIED** until G8 is implemented
and exercised.

## Supply-chain / release boundary

The manual release-candidate workflow:

- validates source version;
- reruns verification;
- builds and smoke-tests the product image;
- produces source/SBOM checksums.

Checksums provide integrity, not signer identity. Signed provenance/attestation remains separately
gated. CI, a merge, a historical provider pilot, OperationProof or OperationCell is not deployment or
release evidence.

## Security Intelligence / CyberCore

Security Intelligence R-SI1.1/R-SI1.2 are descriptive/context-only layers. CyberCore is an intelligence
participant only. Neither may:

- issue AuthorizationSnapshot or ExecutionGrant;
- consume a Grant;
- become Runner or Verifier by inference;
- bypass human/policy gates;
- cause provider mutation outside the canonical V-One lifecycle.

CyberCore integration remains blocked by current G8/READ-E2E/product-release hardening and cannot be
used as a workaround.

## Required gates before enterprise/unrestricted release

Current remaining release gates include:

- G8 explicit READ-only default provider runtime;
- repeated real canonical authenticated HTTP READ E2E;
- restart/resume no-duplicate and fail-closed evidence;
- fresh security/adversarial review for the runtime candidate;
- provider WRITE only if/after the separately governed READ-before-WRITE and effect-specific gates;
- external penetration test as required for unrestricted/enterprise release;
- dependency/container scanning and release evidence;
- released enterprise identity/role mapping where required;
- tenant-specific key management;
- PostgreSQL tenant/isolation/concurrency gates if PostgreSQL is released;
- signed SBOM/artifact provenance strategy;
- incident/vulnerability disclosure contacts;
- licensing, privacy, support and deployment runbooks;
- explicit release authorization;
- explicit deployment authorization.

Until those gates pass:

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
G8_DEFAULT_PROVIDER_RUNTIME=OFF
REAL_CANONICAL_HTTP_READ_E2E=NOT_VERIFIED
WRITE_RUNTIME_GATE=BLOCKED
RELEASE_VERIFIED=NO
DEPLOYMENT_VERIFIED=NO
UNRESTRICTED_PRODUCTION=BLOCKED
```
