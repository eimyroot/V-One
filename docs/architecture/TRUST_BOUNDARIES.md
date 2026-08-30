# Trust Boundaries

| Field | Value |
|---|---|
| Document status | Current trust-boundary inventory |
| Reconciled | `2026-08-24` after canonical G7 PR #140 |
| Security posture | deny by default / fail closed |
| GitHub governance | G0 VERIFIED / PASS from retained live verifier evidence |
| Default provider runtime | OFF / fail-closed until G8 |
| Production effects | BLOCKED until separately released |
| Update trigger | any material identity, authority, execution, persistence, evidence or integration change |

## Canonical authority and execution topology

The system has one shared authority/dispatch prefix and profile-specific terminals:

```text
Untrusted client / agent intent
        ↓
HTTP security + authenticated principal
        ↓
current active user + global role + exact workspace membership
        ↓
ReviewedOperation + Approval evidence
        ↓
AuthorizationSnapshot
        ↓
ExecutionGrant/v2
        ↓
CONTROL PLANE durable ONE_TIME grant consumption
        ↓
GrantConsumptionWitness/v1 + transactional DispatchOutboxEntry/v1
        ↓
DispatchEnvelope/v1
        ↓
DispatchInboxAdmission/v1
        ↓
ExecutionEpoch + ExecutionLease/v1 + CurrentExecutionFence
        ↓
ExecutionCapsule/v1
        ↓
immutable capability→terminal profile binding
        ↓
profile-specific runtime terminal
```

### READ_ONLY_VERIFIED

```text
RunnerIdentity + READ RunnerBoundary
→ READ CredentialAccessDecision + RuntimeActivation
→ Runner provider observation
→ durable completion
→ SEPARATE independent Verifier identity/credential/readback
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
→ STOP
```

### BOUNDED_MUTATION_VERIFIED

```text
write Runner/boundary/credential/runtime
→ exact separately-authorized provider effect
→ ExecutionReceipt/v2
→ SEPARATE independent Verifier readback
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

Current reusable A09 CREATE_REF/DELETE_REF paths stop at pre-effect artifacts; G7 did not activate a provider mutation transport.

## Non-negotiable authority boundary

```text
Control plane consumes ExecutionGrant before Dispatch.
Runner does NOT issue ExecutionGrant.
Runner does NOT consume ExecutionGrant.
Runner does NOT allocate a parallel authority epoch.
Dispatch does NOT create authority.
Terminal profile strength is NOT caller-selected.
Stale in-memory Principal state is NOT canonical permission authority.
Global role does NOT imply membership in arbitrary workspaces.
Historical workspace activity does NOT fabricate current membership.
Resume does NOT create a second authority/execution lineage.
Preflight does NOT equal provider effect.
ExecutionReceipt does NOT create VerificationResult.
OperationProof does NOT create execution authority.
OperationCell does NOT widen authority.
```

## TB-01 — HTTP client to control plane

**Status: IMPLEMENTED / VERIFIED in current product test scope.**

Controls include trusted-host validation, browser security headers, input bounds, authenticated requests,
rate limiting, permission checks and environment classification.

PR #137 merged the canonical public READ surface:

```text
GET  /api/v1/operations/status
POST /api/v1/operations/{request_id}/read
```

Residual boundary: the default G8 provider runtime remains OFF and unrestricted production release is blocked.

## TB-02 — Credential/session material

**Status: VERIFIED for current local-auth scope.**

- runtime-supplied secrets;
- purpose-derived session keys/references;
- active-session allowlist and revocation;
- raw bearer/session material excluded from persistence;
- live account/role revalidation.

Residual boundary: no released OIDC/MFA/tenant-specific enterprise key system.

## TB-03 — Governance to persistence

**Status: VERIFIED for SQLite.**

SQLite migrations are checksum-governed through schema 14. Durable state includes AuthorizationSnapshot,
ExecutionGrant, grant consumption, Outbox, Inbox, ExecutionEpoch/Lease and explicit workspace membership.
Migration 0014 does not infer/backfill historical membership.

Residual boundary: PostgreSQL remains fail-closed until separate adapter/concurrency/operations gates.

## TB-04 — Product permission and workspace-scope authority

**Status: IMPLEMENTED / MERGED.**

`DatabasePermissionAuthority` shares the exact ProductService database and rereads current user,
active-state, global role permission, exact workspace/environment and exact user↔workspace membership
for every canonical decision.

Controls include stale-Principal rejection, role/deactivation/membership revocation handling, no
cross-workspace global-role escalation, and rejection of a parallel database or permission authority.

Membership role (`owner`/`member`) governs membership management only. It does not activate the
separately PROPOSED Solo/Team/Regulated organization-policy model.

## TB-05 — AuthorizationSnapshot / ExecutionGrant

**Status: IMPLEMENTED / canonical.**

Snapshot and Grant contracts are immutable/content-bound. ONE_TIME Grant consumption is a control-plane
transaction before Dispatch. Component/composition readiness does not authorize provider effects.

## TB-06 — Durable Dispatch / coordination

**Status: IMPLEMENTED / canonical.**

```text
GrantConsumptionWitness
+ DispatchOutboxEntry
→ DispatchEnvelope
→ DispatchInboxAdmission
→ ExecutionEpoch / ExecutionLease
→ CurrentExecutionFence
```

Controls include exact-content admission, deduplication, monotonic epochs, stale-attempt fencing and no
authority creation during dispatch.

## TB-07 — Capability terminal-profile authority

**Status: IMPLEMENTED / MERGED.**

An immutable registry binds exact `capability_definition_identity` + capability to one terminal profile.
The canonical public READ route is narrowed to exactly `READ_ONLY_VERIFIED + github.read-ref/v1`.
Absence/mismatch fails closed before Grant issuance/consumption.

## TB-08 — Isolated READ Runner

**Status: VERIFIED pilot primitives + IMPLEMENTED canonical terminal composition.**

Runner authority remains `bounded_execution_only`. Controls include exact lease/capsule/Runner binding,
current-fence checks, READ-only runtime profile, narrowed network/provider access and no grant issuance
or re-consumption.

The default G8 provider runtime is not yet active; pilot evidence is not relabelled as default-product runtime evidence.

## TB-09 — Independent Verifier

**Status: VERIFIED bounded GitHub readback + IMPLEMENTED canonical READ terminal.**

Verifier uses separate identity/provider-instance/credential-decision boundaries. Only the independent
verification path produces `VerificationResult/v1` and strength classification.

```text
Runner credential != Verifier credential
Runner observation != Verifier observation
Execution success != VerificationResult
```

READ terminates at `VerificationResult/v1`; Receipt/v2, Proof/v2 and Cell/v1 are not required.

## TB-10 — Restart-safe durable resume

**Status: IMPLEMENTED / MERGED via PR #140 / post-merge verified.**

Resume reconstructs only the same already-authorized execution. It revalidates current DB permission,
durable snapshot/grant/consumption/supporting-witness/dispatch/lease bindings, terminal profile, envelope
revision and current execution fence.

Resume must not:

```text
re-enter CanonicalOperationPipeline.prepare()
issue a second ExecutionGrant/v2
consume the grant again
append duplicate Outbox/Inbox admission
reacquire a lease
accept a parallel DB / permission authority / profile registry / fence
```

Post-merge evidence on `main@60bc9c26813ee23c73bac194a9adb27714e8a1e8`: CI #1015, D4 #202,
E3 #193 and E4B #189 all SUCCESS.

## TB-11 — Provider WRITE effect

**Status: historical bounded F4b/F6b evidence only; current provider WRITE = BLOCKED.**

Current CREATE_REF preparation ends at `WriteEffectPreflight/v1 → STOP`; current rollback preparation
ends at `RollbackWriteEffectPreflight/v2 → STOP`. No current provider mutation transport is authorized.

Historical F4b/F6b effects remain evidence only, not current effect authority.

## TB-12 — ExecutionReceipt / evidence ledger

**Status: VERIFIED contract and ledger-integrity scope.**

`ExecutionReceipt/v2` is bounded-mutation execution evidence. Receipt/hash-chain integrity may be PASS
while provider verification remains UNKNOWN or NOT_EVALUATED.

```text
ExecutionReceipt != VerificationResult
receipt chain integrity != independent verification
```

## TB-13 — OperationProof / OperationCell

**Status: VERIFIED contract + historical F6b instance scope.**

`OperationProof/v2` binds mutation Receipt/v2 + independent verification lineage. `OperationCell/v1`
is a stable atom over a canonically revalidated Proof/v2. Neither creates new authority.

## TB-14 — ProductComposition compatibility boundary

**Status: IMPLEMENTED / MERGED.**

`ProductComposition` owns the database-backed permission authority and may own an explicit
`CanonicalOperationRuntime` created by a factory sharing the exact ProductService DB/authority.
Without that factory, canonical runtime is absent/fail-closed. Legacy `ExecutionService` is an explicit
compatibility surface, not canonical fallback authority.

G8 must extend this seam as a READ-only composition factory; it must not create a parallel execution or
authority framework.

## TB-15 — GitHub repository governance

**Status: VERIFIED / G0 PASS.**

Retained live evidence:

```text
workflow = g0-governance-verify
run = 32553113424
source_sha = 76d74d2ed62b6e78f027728c456c22da0b4a95bd
artifact = g0-governance-evidence-32553113424-1
artifact_digest = sha256:6e63caee23a57613471df66ef0279c0261ed8d375e4c929accdf50eff7dc4f5f
verdict = VERIFIED
```

Verified controls include PR-only main, required latest-head `verify`, force-push/delete protection,
conversation resolution, no ordinary bypass, active rulesets and verifier-source binding. G0 does not
authorize provider runtime, release or deployment.

## TB-16 — Security Intelligence / CyberCore

**Status: Security Intelligence IMPLEMENTED context-only; CyberCore BLOCKED during G8/release hardening.**

```text
Security Intelligence = observations/classification/context/proposals
CyberCore = intelligence_only
neither = Authorization authority
neither = ExecutionGrant issuer
neither = Runner
neither = Verifier
```

Any future active effect must enter the same canonical capability-bound V-One path.

## TB-17 — READ-before-WRITE boundary

**Status: ADR-0019 PROPOSED; provider WRITE remains BLOCKED independently.**

Before WRITE may become merely `ELIGIBLE`, repeated real authenticated canonical HTTP READ E2E must
prove:

```text
READ_E2E             = VERIFIED
RESTART_RESUME       = VERIFIED
NO_DUPLICATE_EFFECT  = VERIFIED
AUTHORITY_CONTINUITY = VERIFIED
INDEPENDENT_VERIFY   = VERIFIED
FAIL_CLOSED          = VERIFIED
```

`ELIGIBLE` is not effect authorization.

## Production gate

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
G0_GITHUB_GOVERNANCE=PASS
G7_CANONICAL_READ_API=MERGED
G7_RESTART_SAFE_RESUME=MERGED
G8_DEFAULT_PROVIDER_RUNTIME=OFF
REAL_CANONICAL_HTTP_READ_E2E=NOT_VERIFIED
NEW_A09_CREATE_REF_EFFECT=NO
NEW_A09_DELETE_REF_EFFECT=NO
WRITE_RUNTIME_GATE=BLOCKED
RELEASE_VERIFIED=NO
DEPLOYMENT_VERIFIED=NO
UNRESTRICTED_PRODUCTION=BLOCKED
```

No CI pass, preflight, historical live pilot, proof, cell, Security Intelligence metadata or CyberCore
proposal may bypass that gate.
