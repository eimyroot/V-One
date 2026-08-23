# Target Capabilities

| Field | Value |
|---|---|
| Document status | Target-state capability map |
| Capability status | PROPOSED unless explicitly stated otherwise |
| Planning source | `ROADMAP.md` |
| Current-state source | `CURRENT_CAPABILITIES.md` |
| Reconciled | `2026-08-24` after canonical G7 PR #140 |

## Target capability template

Every target capability must define user problem, product value, authoritative owner, inputs/outputs,
trust boundary, failure behavior, evidence requirements, dependencies, acceptance criteria, rollback or
disable strategy, and current status.

## Verified/implemented foundation

The historical ADR-0007 pure deterministic v1 contracts remain historical foundation. The current
system has progressed beyond representation-only status in named scopes:

```text
AuthorizationSnapshot                = IMPLEMENTED / VERIFIED contracts + canonical authority path
ExecutionGrant/v2                     = IMPLEMENTED / VERIFIED
durable one-time Grant consumption    = IMPLEMENTED
Dispatch Outbox/Envelope/Inbox        = IMPLEMENTED
ExecutionEpoch/Lease/Fence            = IMPLEMENTED
ExecutionCapsule / RunnerBoundary     = IMPLEMENTED
bounded isolated READ Runner          = VERIFIED pilot scope
independent Verifier                  = VERIFIED bounded scope
VerificationResult/v1                 = VERIFIED bounded scope
canonical public READ API             = IMPLEMENTED / MERGED
restart-safe durable resume           = IMPLEMENTED / MERGED
```

The default G8 provider runtime is still OFF, real default-runtime HTTP READ E2E is NOT VERIFIED, and
provider WRITE/release/deployment remain BLOCKED. Historical implementation does not silently rewrite
the exact design scope of older ADRs.

## T1 — Policy Decision Graph

**Status:** VERIFIED read-only projection foundation; organization-scoped authoritative policy/runtime
enforcement remains PROPOSED.

Accepted ADR-0006 provides `policy-decision-graph/v1` as a pure deterministic projection over supplied
facts. It does not itself become authorization authority. Target maturation still includes stored
organization-scoped policy decisions, drift invalidation, approval binding and explainable enforcement
without creating a second permission path.

## T2 — Authenticated execution-grant authority

**Status:** IMPLEMENTED for current `ExecutionGrant/v2` authority/persistence/one-time-consumption scope;
future signer/key-distribution and broader portable cryptographic attestation remain PROPOSED.

Current Grant authority binds the canonical snapshot, execution, capability, target, payload, policy,
approval/precondition evidence, runner class, revocation epoch, TTL and one-time semantics. Durable
consumption is control-plane state before Dispatch.

Future target work must preserve replay rejection, expiry/revocation handling, deterministic
verification and key rotation without weakening current exact-content authority.

## T3 — Isolated Runner Capsules

**Status:** VERIFIED bounded READ pilot primitives + IMPLEMENTED canonical READ terminal; default G8
product runtime remains PROPOSED/BLOCKED until its own gate passes.

Current verified/implemented controls include bounded Runner identity/boundary, current lease/fence,
capability/capsule binding, READ-only provider handling and isolated pilot runtime evidence. Target
productization still requires explicit default runtime composition, secrets/config operations,
repeatable canonical HTTP E2E, restart verification and release-grade operational controls.

## T4 — Structured execution and verification evidence

**Status:** IMPLEMENTED/VERIFIED in profile-specific current contracts; broader signed portable
provenance remains PROPOSED.

Current semantics are profile-specific:

```text
READ_ONLY_VERIFIED
→ VerificationResult/v1

BOUNDED_MUTATION_VERIFIED
→ ExecutionReceipt/v2
→ independent VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

Raw credentials and uncontrolled provider responses must never become portable evidence.

## T5 — Expanded ProofGraph

**Status:** PROPOSED beyond the current checkpoint/proof foundations.

Target nodes may include source/tree, build, SBOM, vulnerability policy, artifact, publisher identity,
policy decision, approval, execution grant, Runner identity, execution, receipt, post-state observation,
checkpoint and external anchor.

Target verification includes remote byte verification, signature/trust-policy validation, registry
digest verification and transparency/object-lock anchoring.

## T6 — CyberCore read-only knowledge boundary

**Status:** PROPOSED / BLOCKED during current G8 and release hardening.

Initial contract may contain source, knowledge reference, artifact digest, publisher, risk, target,
environment, evidence references, confidence, expected effect, verification plan and observed time.

Required properties: versioned schema, off by default, no shared authority database, no package-code
execution, no secrets, idempotent intake and audit for accepted/rejected imports.

CyberCore remains intelligence only and cannot issue grants, become Runner/Verifier or bypass V-One.

## T7 — AI Change Copilot

**Status:** PROPOSED.

The copilot may translate intent into drafts, summarize evidence/uncertainty, identify missing
preconditions, propose risk/tests/rollback/verification and explain policy or execution evidence.

It must not approve itself, issue grants, alter policy, activate production effects, suppress
uncertainty or execute external mutation directly.

## T8 — Enterprise identity and tenancy

**Status:** PROPOSED beyond current local identity/workspace-membership scope.

Target capabilities include released OIDC, step-up authentication, workspace-scoped role assignment,
tenant/platform-admin separation, key rotation and server-side revocation across supported identity
paths.

## T9 — Released PostgreSQL and HA operations

**Status:** PROPOSED.

Prerequisites include a released adapter, transactional migration locking, concurrency/isolation tests,
connection pooling, backup/restore/PITR, migration rehearsal, multi-node recovery, SLOs and operator
runbooks. Current PostgreSQL selection remains fail-closed.

## T10 — Signed multi-platform supply chain

**Status:** PROPOSED beyond current build/SBOM/checksum gates.

```text
immutable source
→ deterministic build
→ linux/amd64 + linux/arm64
→ SBOM
→ vulnerability report
→ provenance
→ signature
→ governed registry promotion
→ deployment verification
```

## T11 — Outcome learning loop

**Status:** PROPOSED.

```text
planned state
→ approved execution
→ observed post-state
→ drift/outcome comparison
→ knowledge update
```

V-One retains authorization/evidence ownership; intelligence layers retain knowledge/recommendation
ownership.

## T12 — G8 default READ provider runtime

**Status:** PROPOSED / NEXT PRODUCTIZATION TARGET.

The first default provider pack must be READ-only and reuse the existing canonical composition rather
than introduce a parallel execution framework. Required properties include:

- exact ProductService DB and DatabasePermissionAuthority;
- exact terminal-profile registry, envelope revision and current fence;
- explicit Runner and Verifier provider configuration;
- separate identities/credential decisions;
- no ambient credential fallback;
- exact `github.read-ref/v1` capability only;
- no CREATE_REF, DELETE_REF, rollback, generic execute or mutation transport;
- missing/ambiguous configuration fails closed.

## T13 — Real canonical HTTP READ E2E + restart continuity

**Status:** PROPOSED / BLOCKED until G8 exists.

Target proof chain:

```text
authenticated HTTP READ
→ current DB authority/membership
→ Snapshot
→ Grant/v2
→ one-time consumption
→ Outbox/Envelope/Inbox
→ ACTIVE Epoch/current Lease/Capsule
→ process interruption/restart before Runner completion
→ resume the same ACTIVE execution
→ no new prepare/grant/consume/outbox/envelope/inbox/epoch/lease
→ current-fence + authority-continuity validation
→ resumed isolated READ Runner
→ durable completion
→ independent Verifier with separate identity/credential decision
→ VerificationResult/v1
```

The current resume target is explicitly an `ACTIVE` execution. Resuming an already `COMPLETED` execution
or performing completed-execution reverification is outside T13 and requires a separate future contract.

Repeated successful and failure-injected evidence is required before provider WRITE may become merely
eligible under the governed READ-before-WRITE decision.

## T14 — Provider WRITE productization

**Status:** BLOCKED.

Current A09 CREATE_REF/rollback orchestration is pre-effect only. Provider mutation activation is not a
near-term default target: it remains blocked until the READ-before-WRITE evidence gate passes and then
still requires a separate effect-specific authority, credential, verification, rollback, security,
release and deployment decision.
