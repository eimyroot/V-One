# Trust Boundaries

| Field | Value |
|---|---|
| Document status | Current + target trust-boundary inventory |
| Reconciled | `2026-08-20` against `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| Security posture | deny by default / fail closed |
| Production effects | BLOCKED until separately released |
| Update trigger | any material identity, authority, execution, persistence, evidence or integration change |

## Canonical authority and execution topology

```text
Untrusted client / agent intent
        ↓
HTTP security + authenticated principal
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
RunnerIdentity + RunnerBoundary
        ↓
CredentialAccessDecision + RuntimeActivation
        ↓
bounded Handler / provider effect
        ↓
ExecutionReceipt/v2
        ↓
SEPARATE independent Verifier identity/credential/readback
        ↓
ObservedPostState + VerificationStrength + VerificationResult/v1
        ↓
OperationProof/v2
        ↓
OperationCell/v1
```

### Non-negotiable authority boundary

```text
Control plane consumes ExecutionGrant before Dispatch.
Runner does NOT issue ExecutionGrant.
Runner does NOT consume ExecutionGrant.
Runner does NOT allocate a parallel authority epoch.
Dispatch does NOT create authority.
ExecutionReceipt does NOT create VerificationResult.
OperationProof does NOT create new execution authority.
OperationCell does NOT widen authority.
```

Historical wording that placed one-time Grant consumption inside Runner admission is superseded by the
merged Phase-C durable authority chain.

## TB-01 — HTTP client to control plane

**Status: VERIFIED for current product test scope.**

Controls include trusted-host validation, browser security headers, input bounds, authenticated
requests, rate limiting, permission checks and environment classification.

Residual boundary: current deployment is not an unrestricted public production release and external
enterprise identity remains unreleased.

## TB-02 — Credential/session material

**Status: VERIFIED for released local-auth scope.**

- runtime-supplied secrets;
- purpose-derived session keys/references;
- active-session allowlist and revocation;
- raw bearer/session material excluded from persistence;
- live account/role revalidation.

Residual boundary: no released OIDC/MFA/tenant-specific enterprise key system.

## TB-03 — Governance to persistence

**Status: VERIFIED for SQLite.**

SQLite migrations are checksum-governed and current through schema 13. Durable authority/dispatch
state includes AuthorizationSnapshot, ExecutionGrant, grant consumption, Outbox, Inbox and
ExecutionEpoch/Lease persistence.

Residual boundary: SQLite is the released single-node backend. PostgreSQL remains fail closed until a
separate adapter/concurrency/operations release gate.

## TB-04 — AuthorizationSnapshot / ExecutionGrant

**Status: IMPLEMENTED component layer.**

Snapshot and Grant contracts are immutable/content-bound. Grant issuance cannot be reconstructed from
mutable UI state after the fact. ONE_TIME Grant consumption is a **control-plane transaction**, not a
Runner action.

Residual boundary: these components are not yet one canonical FastAPI ProductComposition lifecycle.

## TB-05 — Durable Dispatch / coordination

**Status: IMPLEMENTED component/pilot layer.**

```text
GrantConsumptionWitness
+ DispatchOutboxEntry
→ DispatchEnvelope
→ DispatchInboxAdmission
→ ExecutionEpoch / ExecutionLease
→ CurrentExecutionFence
```

Controls:

- durable exact-content admission;
- duplicate delivery classification;
- monotonic execution epochs;
- stale-attempt fencing;
- no authority creation during dispatch.

Residual boundary: current product API does not yet expose this as the sole execution path.

## TB-06 — Isolated Runner

**Status: VERIFIED for bounded D4b/E3/E4b pilot scopes; product composition remains partial.**

Runner authority is `bounded_execution_only`.

Controls demonstrated in bounded pilots include:

- exact RunnerIdentity/RunnerBoundary binding;
- current lease/fence checks;
- read-only filesystem/rootfs constraints where applicable;
- capability/target-specific provider transport;
- narrowed network policy;
- no generic authority issuance;
- no Grant re-consumption.

Residual boundary: current live pilot workflows are not the general product runtime and production
mutation remains separately blocked.

## TB-07 — Provider WRITE effect

**Status: VERIFIED only for historical bounded F4b/F6b staging pilots.**

Historical write/rollback controls include exact target binding, one mutation, no automatic mutation
retry, ephemeral credential delivery, current-fence preflight and separately governed rollback.

Residual boundary:

- F4b workflow on current main is hard-bound to historical PR #120/main identity;
- historical F6b rollback workflow is evidence, not a reusable current product entrypoint;
- no provider mutation is authorized by repository presence alone.

## TB-08 — ExecutionReceipt / evidence ledger

**Status: VERIFIED for contract and ledger integrity scopes.**

`ExecutionReceipt/v2` records what execution claims it performed. Receipt/hash-chain integrity can be
`PASS` while independent provider verification is still `UNKNOWN` or pending.

```text
ExecutionReceipt != VerificationResult
receipt chain integrity != independent verification
```

Residual boundary: local ledger integrity is not an external signed anchor and does not independently
prove provider state.

## TB-09 — Independent Verifier

**Status: VERIFIED for bounded GitHub readback scope.**

Verifier uses a separate identity/instance/credential boundary and READ-only provider observation.
Only the independent verification path may produce `VerificationResult/v1` and its strength class.

Residual boundary: current FastAPI ProductComposition does not yet bind every product execution to
this verifier path.

## TB-10 — OperationProof / OperationCell

**Status: VERIFIED contract + historical F6b instance scope.**

`OperationProof/v2` binds the current ExecutionReceipt/v2 + independent verification lineage.
`OperationCell/v1` is a minimal provider/lineage-neutral stable atom over a canonically revalidated
OperationProof/v2.

```text
VerificationResult != OperationProof
OperationProof != OperationCell
OperationCell != new authority
```

Residual boundary: proof/cell emission is not yet automatic for the legacy ProductComposition path.

## TB-11 — ProductComposition compatibility boundary

**Status: PARTIAL / reconciliation required.**

The current product still composes the legacy ExecutionService surface for existing API behavior while
the newer VOP authority/dispatch/Runner/verification/proof/cell components exist beside it.

The next architecture slice must converge to one canonical runtime path without silently deleting
legacy behavior before replacement tests prove the required product surface.

## TB-12 — GitHub repository governance

**Status: UNKNOWN / BLOCKED as an enforcement boundary.**

Repository policy requires PR-only main, required `ci / verify`, latest-head checks, no force push,
no branch deletion and conversation resolution. Classic required-status metadata is observed off; a
modern ruleset is not independently proven by current connector evidence.

Until live settings prove every control, GitHub must not be treated as a completed authority boundary.

## TB-13 — Security Intelligence / CyberCore

**Status: IMPLEMENTED metadata boundary for R-SI1.1; CyberCore integration BLOCKED pending reconciliation.**

```text
Security Intelligence = observations/classification/context/proposals
CyberCore = intelligence_only
neither = Authorization authority
neither = ExecutionGrant issuer
neither = Runner
neither = Verifier
```

Any later active effect still flows through the same canonical V-One authority and verification
lineage.

## Production gate

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
UNRESTRICTED_PRODUCTION=BLOCKED
```

No CI pass, historical live pilot, proof, cell, Security Intelligence metadata or future CyberCore
proposal may bypass that gate.
