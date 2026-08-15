# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Reconciled | `2026-08-16` |
| Source of current capability truth | `docs/product/CURRENT_CAPABILITIES.md` |
| Source of live current-state snapshot | `CURRENT_PRODUCT_STATE.md` |
| Production status | BLOCKED until an explicit governed release |
| Update rule | Update with every accepted milestone or material scope change |

## Status vocabulary

- **VERIFIED** — supported by current repository evidence and executed verification;
- **IMPLEMENTED** — exists in current source/documentation but has not met every stated verification scope;
- **PROPOSED** — target direction or not-yet-implemented capability;
- **INFERRED** — derived from evidence but not directly demonstrated;
- **UNKNOWN** — evidence unavailable or dedicated audit not yet completed;
- **BLOCKED** — intentionally unavailable or unsafe to activate.

## Architectural invariant

```text
V-ONE
=
SMALL IMMUTABLE TRUST KERNEL
+
VERSIONED OPERATION SEMANTICS
+
MASSIVELY SCALABLE CAPABILITY CATALOG
+
CONFORMANCE-TESTED MODULE ECOSYSTEM
+
DISTRIBUTED EXECUTION FABRIC
+
INDEPENDENT VERIFICATION
+
PORTABLE PROOF
```

Scaling rule: provider/capability count may grow massively; trusted core must not grow proportionally.

```text
FRACTAL OUTSIDE.
ATOMIC INSIDE.
```

## Current verified milestone

PR #71 merged the Authorization Snapshot persistence foundation as
`d8d375c61264ddad39eb53240dce9ff0c8e59818`.

Evidence:

- PR-head CI #282: `SUCCESS`;
- post-merge CI #283: `SUCCESS`;
- SQLite schema version 9;
- immutable append-only Authorization Snapshot persistence;
- idempotency/request/review bindings;
- contract, store and migration regression coverage.

This milestone does **not** implement the authoritative Snapshot Creator, Grant Issuer, dispatch,
Runner, release, deployment, or production effects.

## MVP delivery map

The detailed product-delivery map remains in
[`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md).

| Phase | Status | Summary |
|---|---|---|
| MVP-0 | VERIFIED | Control-plane foundation with identity, approvals, execution lifecycle, evidence, production effects disabled |
| MVP-1 | PARTIALLY VERIFIED | Deterministic execution contracts, adopted Runner/grant/snapshot design boundaries, and verified Authorization Snapshot persistence foundation |
| MVP-2 | PROPOSED | Complete authoritative authorization path through Snapshot Creator and Grant Issuer |
| MVP-3 | PROPOSED | Isolated READ-ONLY Runner vertical slice |
| MVP-4 | BLOCKED | Governed non-production mutation pilot until authority/Runner/verification gates pass |
| MVP-5 | PROPOSED | Productized multi-provider pilot and portable proof layer |

## STEP 0 — Source-of-Truth reconciliation

**Status:** IN_PROGRESS until this reconciliation PR merges and CI passes.

Required:

- live `main` identity and CI evidence reconciled;
- `CURRENT_PRODUCT_STATE.md` current;
- `docs/product/CURRENT_CAPABILITIES.md` current;
- roadmap aligned to adopted ADR-0008/0009/0010 effective status;
- historical evidence superseded, not deleted;
- CASER evidence refreshed;
- branch-protection gap kept visible.

Exit gate:

```text
CURRENT STATE TRUSTWORTHY
```

## STEP 1 — Authority Reality Audit

**Status:** PROPOSED next execution step.

Audit exact current implementation of:

1. immutable/versioned policy authority;
2. server-side `execution.run` permission authority;
3. capability definition authority;
4. capability activation authority;
5. deterministic target binder;
6. approval evidence authority;
7. trusted clock/timestamp-source authority;
8. transaction-aware persistence/read APIs.

For each item classify:

```text
EXISTS / PARTIAL / MISSING / UNKNOWN
```

No implementation by assumption.

The broader organization/approval target remains described by
[`ADR-0003`](docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md).

## STEP 2 — Implement only missing authority prerequisites

**Status:** PROPOSED.

Expected candidate slices, only if Step 1 proves them missing:

- P1 immutable policy authority;
- P2 authoritative `execution.run` permission authority;
- P3 capability definition/activation authority;
- deterministic target binder;
- connection-aware read APIs;
- connection-aware `AuthorizationSnapshotStore.persist_prevalidated_on_connection(...)`;
- negative-path and transaction rollback tests.

Rule: no unrelated refactor, no whole-framework implementation.

## STEP 3 — 6B AuthoritativeSnapshotCreator

**Status:** PROPOSED.

One coherent authorization transaction:

```text
BEGIN
load reviewed request
revalidate reviewed-content digest
resolve actor/workspace/environment
check execution.run
resolve active capability definition
bind authoritative ExecutionTarget
resolve immutable PolicyRevision
load and validate ApprovalEvidence
read TrustedClock
construct AuthorizationSnapshot
persist exact snapshot + child bytes
append audit
COMMIT
```

Invariant:

```text
AUTHORITY READS
+
SNAPSHOT CREATION
+
SNAPSHOT PERSISTENCE
+
AUDIT
=
ONE COHERENT TRANSACTION
```

## STEP 4A — ExecutionGrant contract hardening

**Status:** PROPOSED.

Bind exact:

- `grant_id` / replay identity;
- issuer;
- runner audience/class;
- snapshot id/digest;
- execution id;
- capability;
- target digest;
- payload digest;
- handler identity;
- `issued_at`, `not_before`, `expires_at`.

Grant must be narrow, short-lived, replay-safe and immutable.

## STEP 4B — Authoritative Grant Issuer

**Status:** PROPOSED.

Issuer loads the committed immutable snapshot, checks live issuance gates required by adopted
ADR-0009/0010, binds exact handler/runner audience and persists grant state.

A later issuer must not rebuild authorization from mutable UI/request defaults.

## STEP 4C — Runner / Handler authority registry

**Status:** PROPOSED.

Explicit registries:

- Module Registry;
- Handler Registry;
- Runner Registry;
- Verifier Registry;
- Key Registry when authenticity implementation begins.

Dispatcher and Runner do not guess executable implementation identity.

## STEP 5 — Transactional Outbox / Dispatch

**Status:** PROPOSED.

```text
snapshot/grant/outbox state
        ↓
      COMMIT
        ↓
     DISPATCH
```

Dispatch delivers authority already issued; it does not create authority.

## STEP 5.5 — Credential Broker boundary

**Status:** PROPOSED.

```text
ExecutionGrant
+ RunnerIdentity
+ capability credential requirement
→ short-lived least-privilege provider credential
```

No long-lived broad provider token in operation payload or evidence.

## STEP 6 — READ-ONLY Isolated Runner

**Status:** PROPOSED implementation. The exact design/safety boundary in
[`ADR-0008`](docs/adr/ADR-0008-isolated-runner-boundary-v1.md) is owner-adopted; runtime remains not
implemented and production effects remain BLOCKED.

First allowed classes should be bounded READ/COMPUTE operations such as repository inspection,
diff, tests, builds, static analysis and provider reads.

Default deny:

```text
workspace write
remote write
deploy
production mutation
generic shell fallback
arbitrary network
long-lived secrets
```

## STEP 7 — ExecutionReceipt

**Status:** PROPOSED runtime composition; pure deterministic receipt contract already exists.

Receipt is an execution-subsystem claim, not independent proof of provider post-state.

```text
ExecutionReceipt.SUCCESS != VerificationResult.PASS
```

## STEP 8 — Independent Verification

**Status:** PROPOSED.

Verifier reads actual provider/post-state independently and compares expected vs observed state:

```text
PASS / FAIL / INDETERMINATE
```

Required negative demonstration:

```text
Runner reports success
Verification fails
Operation does not become VERIFIED
```

## STEP 9 — OperationProof

**Status:** PROPOSED runtime composition; deterministic operation-proof value contract is already
IMPLEMENTED at source/test layer.

Target chain:

```text
Intent
→ ReviewedOperation
→ ApprovalEvidence
→ AuthorizationSnapshot
→ ExecutionGrant
→ Dispatch
→ RunnerIdentity
→ ExecutionReceipt
→ VerificationResult
→ OperationProof
```

Proof target: content-addressed, schema-versioned, tamper-evident and portable.

## STEP 10 — Operation Cell hardening

**Status:** PROPOSED.

Before DAG/CyberCore complexity, prove one complete atomic operation cell end-to-end, including:

- positive path;
- permission deny;
- approval drift;
- target substitution;
- expired/replayed grant;
- wrong runner/handler;
- transaction rollback;
- receipt-success/verification-fail;
- evidence completeness.

## STEP 11 — Bounded Operation Graph

**Status:** PROPOSED.

Complex intent becomes a bounded DAG of proven Operation Cells.

```text
PARENT AUTHORITY != CHILD AUTHORITY
```

Every consequential child obtains its own bounded authority.

## STEP 12 — Module SDK + conformance

**Status:** PROPOSED.

Provider modules own translation semantics; kernel remains provider-neutral.

```text
ADAPTERS TRANSLATE.
ADAPTERS DO NOT AUTHORIZE.
```

Conformance target covers identity, deterministic binding, permissions, handler identity, credential
isolation, idempotency, receipts, independent verification, replay, production deny, secret
redaction, evidence completeness and module/kernel isolation.

## STEP 13 — Multi-provider execution

**Status:** PROPOSED.

Scale through versioned capabilities/modules, not provider logic inside the kernel.

## STEP 14 — CyberCore observation plane

**Status:** PROPOSED.

CyberCore may observe, benchmark, discover and propose optimizations. It does not authorize, issue
grants, activate modules, or grant itself production authority.

```text
LEARNING != SELF-AUTHORIZATION
```

## STEP 15 — Semantic Equivalence

**Status:** PROPOSED.

Optimization candidates may be adopted only if input/target/effect/authorization/idempotency/receipt/
post-state/security/evidence semantics are equivalent or stronger.

## STEP 16 — Integration Compiler / Developer SDK

**Status:** PROPOSED.

Generated capability/handler/verifier candidates remain untrusted until conformance, security review,
adoption and explicit activation.

```text
GENERATE CANDIDATE != ADOPT != ACTIVATE
```

## STEP 17 — Portable attestation / Operation Passport

**Status:** PROPOSED.

Expose portable, independently verifiable proof of reviewed, authorized, executed and verified
operations without conflating those lifecycle states.

## STEP 18 — Graduated mutation path

**Status:** BLOCKED beyond read/compute until prior gates pass.

```text
READ
→ COMPUTE
→ WORKSPACE WRITE
→ PATCH
→ LOCAL COMMIT
→ REMOTE PUSH
→ PR CREATE
→ CONTROLLED STAGING MUTATION
→ STAGING DEPLOY
→ separately governed production-capable path
```

Production remains deny-by-default.

## Governance gap — branch protection

Live GitHub reconciliation on 2026-08-16 observed `main` with branch protection disabled and no
required status checks. This does not invalidate successful CI evidence, but it is a governance gap
that should be closed before higher-impact authority/Runner work depends on GitHub enforcement.

## Explicit no-go items

- generic shell execution from user input;
- AI/CyberCore self-approval or grant issuance;
- shared VOODOO/CyberCore authority database;
- provider-specific policy logic in the trust kernel;
- production effects enabled by documentation/environment drift;
- silent fallback to unreleased identity/persistence backends;
- full microservice rewrite without measured pressure;
- public distribution before licensing is resolved.

## Immediate priority order

1. merge and verify the Source-of-Truth reconciliation slice;
2. run the Authority Reality Audit against exact current `main`;
3. implement only proven missing P1/P2/P3/transaction prerequisites;
4. build `AuthoritativeSnapshotCreator` as one atomic authorization transaction;
5. only then proceed to Grant Issuer, outbox, READ-ONLY Runner, receipt, independent verification and
   OperationProof.
