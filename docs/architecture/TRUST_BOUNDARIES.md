# Trust Boundaries

| Field | Value |
|---|---|
| Document status | Current trust-boundary inventory / reconciliation candidate |
| Reconciled | `2026-08-20` against `main@71a931b561faa93c8dd2e062b83559401143b1df` plus PR #128 |
| Security posture | deny by default / fail closed |
| Production effects | BLOCKED until separately released |
| Update trigger | any material identity, authority, execution, persistence, evidence or integration change |

## Canonical authority and execution topology

The system has one shared authority/dispatch prefix and **profile-specific terminals**. There is no
universal mandatory Receipt→Proof→Cell tail.

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

A completed authorized mutation may continue:

```text
write Runner/boundary/credential/runtime
→ exact provider effect
→ ExecutionReceipt/v2
→ SEPARATE independent Verifier readback
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

PR #128 does not execute a new bounded mutation. Its A09 runtime ends at effect preflight.

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
Preflight does NOT equal provider effect.
ExecutionReceipt does NOT create VerificationResult.
OperationProof does NOT create execution authority.
OperationCell does NOT widen authority.
```

## TB-01 — HTTP client to control plane

**Status: VERIFIED for current product test scope.**

Controls include trusted-host validation, browser security headers, input bounds, authenticated
requests, rate limiting, permission checks and environment classification.

Residual boundary: the public API does not yet expose a new canonical VOP operation endpoint and the
product is not an unrestricted production release.

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

SQLite migrations are checksum-governed through schema 14. Durable state includes
AuthorizationSnapshot, ExecutionGrant, grant consumption, Outbox, Inbox, ExecutionEpoch/Lease and the
explicit user↔workspace membership scope required by canonical permission decisions.

Migration 0014 does not infer/backfill historical memberships. A schema-13 workspace upgraded to 14
has no canonical membership authority until an administrator explicitly records it.

Residual boundary: PostgreSQL remains fail-closed until separate adapter/concurrency/operations gates.

## TB-04 — Product permission and workspace-scope authority

**Status: IMPLEMENTED CANDIDATE in PR #128.**

`DatabasePermissionAuthority` shares the exact ProductService database and rereads current user,
active-state, global role permission set, exact workspace/environment and exact user↔workspace
membership for every canonical permission decision.

Controls:

- stale `Principal` role does not preserve stronger permission after DB role change;
- inactive/deleted user state fails closed;
- workspace/environment bindings are checked against current database state;
- an otherwise privileged global role without workspace membership is denied;
- membership revocation is effective without rebuilding the authority/runtime;
- schema-14 migration does not fabricate legacy memberships;
- ProductComposition runtime factory cannot substitute another permission-authority instance.

Membership role (`owner`/`member`) governs membership management only. It does not activate the
separately PROPOSED Solo/Team/Regulated organization-policy model.

Residual boundary: this is candidate source/test evidence until final exact-head gates close.

## TB-05 — AuthorizationSnapshot / ExecutionGrant

**Status: IMPLEMENTED component + canonical composition seam.**

Snapshot and Grant contracts are immutable/content-bound. ONE_TIME Grant consumption is a
**control-plane transaction** before Dispatch.

Residual boundary: component/composition readiness does not authorize provider effects.

## TB-06 — Durable Dispatch / coordination

**Status: IMPLEMENTED component + canonical composition seam.**

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

## TB-07 — Capability terminal-profile authority

**Status: IMPLEMENTED CANDIDATE in PR #128.**

An immutable registry binds the exact `capability_definition_identity` and capability to one terminal
profile. `CanonicalOperationPipeline.prepare()` has no caller-supplied `terminal_profile` argument.

Residual boundary: future capabilities must be explicitly registered; absence/mismatch fails closed.

## TB-08 — Isolated READ Runner

**Status: VERIFIED pilot primitives + IMPLEMENTED canonical terminal composition.**

Runner authority remains `bounded_execution_only`.

Controls include exact lease/capsule/Runner binding, current-fence checks, READ-only runtime profile,
narrowed network/provider access and no grant issuance/re-consumption.

`CanonicalGitHubReadTerminal` composes these controls from `CanonicalPreparedExecution`.

## TB-09 — Independent Verifier

**Status: VERIFIED bounded GitHub readback + IMPLEMENTED canonical READ terminal.**

Verifier uses separate identity, provider-instance and credential boundaries. Only the independent
verification path produces `VerificationResult/v1` and strength classification.

```text
Runner credential != Verifier credential
Runner observation != Verifier observation
Execution success != VerificationResult
```

READ terminates at `VerificationResult/v1`; Receipt/v2, Proof/v2 and Cell/v1 are not required.

## TB-10 — Provider WRITE effect

**Status: VERIFIED only for historical bounded F4b/F6b staging effects. New A09 effect = NOT EXECUTED.**

PR #128 adds reusable CREATE_REF preparation:

```text
CanonicalPreparedExecution
→ exact write bindings
→ scoped credential decision metadata
→ exact provider request
→ WriteEffectPreflight/v1
→ STOP
```

Controls:

- no provider transport in A09 orchestration;
- no credential secret argument/serialization;
- no historical PR120/ref/SHA hard-bind;
- exact current lease/target/fence binding;
- future mutation requires separate authorization/effect step.

Historical F4b execution remains evidence only and is not current effect authority.

## TB-11 — Rollback effect

**Status: VERIFIED historical F6b effect; reusable A09 rollback preparation IMPLEMENTED / NOT EXECUTED.**

```text
CanonicalPreparedExecution
→ exact rollback provenance
→ current pre-delete observation
→ rollback Runner/boundary/credential metadata
→ current-fence recheck
→ RollbackWriteEffectPreflight/v2
→ STOP
```

There is no GitHub DELETE transport call inside A09. A prepared rollback does not authorize or prove
rollback execution.

## TB-12 — ExecutionReceipt / evidence ledger

**Status: VERIFIED contract and ledger-integrity scope.**

`ExecutionReceipt/v2` is bounded mutation execution evidence. Receipt/hash-chain integrity may be
`PASS` while provider verification is still `UNKNOWN` or `NOT_EVALUATED`.

```text
ExecutionReceipt != VerificationResult
receipt chain integrity != independent verification
```

## TB-13 — OperationProof / OperationCell

**Status: VERIFIED contract + historical F6b instance scope.**

`OperationProof/v2` binds mutation Receipt/v2 + independent verification lineage. `OperationCell/v1`
is a stable atom over a canonically revalidated Proof/v2.

```text
VerificationResult != OperationProof
OperationProof != OperationCell
OperationCell != new authority
```

Residual boundary: A09 preflight preparation cannot emit or claim a new Proof/Cell because no new
provider effect/Receipt/VerificationResult exists.

## TB-14 — ProductComposition compatibility boundary

**Status: IMPLEMENTED CANDIDATE with explicit compatibility surface.**

`ProductComposition` now owns the database-backed permission authority and may own an explicit
`CanonicalOperationRuntime` created by a runtime factory sharing the exact ProductService DB/authority.

Without that factory, canonical runtime is absent/fail-closed. Legacy `ExecutionService` remains an
explicit existing API compatibility surface; it is not silently treated as canonical VOP authority.

Residual boundary: a canonical public operation API is not yet claimed.

## TB-15 — GitHub repository governance

**Status: UNKNOWN / RELEASE BLOCKER as an enforcement boundary.**

Repository policy requires PR-only main, latest-head checks, no force push/delete and conversation
resolution. Current connector evidence does not independently prove the complete modern ruleset.

Successful Actions runs are not Settings/ruleset enforcement evidence.

## TB-16 — Security Intelligence / CyberCore

**Status: R-SI1.1 metadata IMPLEMENTED; CyberCore integration BLOCKED pending final reconciliation.**

```text
Security Intelligence = observations/classification/context/proposals
CyberCore = intelligence_only
neither = Authorization authority
neither = ExecutionGrant issuer
neither = Runner
neither = Verifier
```

Any future active effect must enter the same canonical capability-bound V-One authority/runtime path.

## Production gate

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
NEW_A09_CREATE_REF_EFFECT=NO
NEW_A09_DELETE_REF_EFFECT=NO
UNRESTRICTED_PRODUCTION=BLOCKED
```

No CI pass, preflight, historical live pilot, proof, cell, Security Intelligence metadata or future
CyberCore proposal may bypass that gate.
