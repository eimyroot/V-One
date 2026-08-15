# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Reconciled | `2026-08-16` |
| Reconciliation input | `main@b4d4aab7393251ffc113a3f5bf654523bdb27865` |
| Source of current capability truth | `docs/product/CURRENT_CAPABILITIES.md` |
| Source of live current-state snapshot | `CURRENT_PRODUCT_STATE.md` |
| Production status | BLOCKED until an explicit governed release |
| Update rule | Update with every accepted milestone or material scope change |

## Status vocabulary

- **VERIFIED** — supported by current repository evidence and executed verification;
- **IMPLEMENTED** — exists in current source/documentation but has not met every stated verification scope;
- **PROPOSED** — target direction or not-yet-implemented capability;
- **INFERRED** — derived from evidence but not directly demonstrated;
- **UNKNOWN** — evidence unavailable, adoption missing, or dedicated audit not completed;
- **BLOCKED** — intentionally unavailable or unsafe to activate.

## Architectural invariant

```text
V-ONE
=
CANONICAL OPERATION LANGUAGE
+
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
ONE SYSTEM = ONE SEMANTIC LANGUAGE
FRACTAL OUTSIDE.
ATOMIC INSIDE.
```

The current source/test implementation of VOP canonical vocabulary and semantic translation does not
by itself create normative owner adoption or runtime execution authority.

## Current verified milestones

### Authorization Snapshot persistence — PR #71

PR #71 merged the Authorization Snapshot persistence foundation as
`d8d375c61264ddad39eb53240dce9ff0c8e59818`.

Evidence:

- PR-head CI #282: `SUCCESS`;
- post-merge CI #283: `SUCCESS`;
- SQLite schema version 9;
- immutable append-only Authorization Snapshot persistence;
- idempotency/request/review bindings;
- contract, store and migration regression coverage.

### Canonical VOP semantics — PR #74

PR #74 merged as `a9a57df270b85907ee5012895c1523ade461f06f` and added:

- canonical VOP vocabulary and deterministic vocabulary digest;
- reserved/versioned schema registry identities;
- shared operation-stage ownership;
- immutable provider semantic mapping;
- deterministic semantic-equivalence profile/assessment;
- conformance/translation tests.

Evidence:

- PR-head CI #292: `SUCCESS` at `1be3721db70433a4dc4a45c353a5d748dd4bf113`;
- immediate post-merge CI #297 was cancelled by subsequent `main` activity, not by a failing gate;
- current `main` CI #298: `SUCCESS` at `b4d4aab7393251ffc113a3f5bf654523bdb27865`, including PR #74 source tree.

Status boundary:

```text
VOP SOURCE/TEST IMPLEMENTATION = VERIFIED
VOP OWNER ADOPTION = UNKNOWN
```

No explicit VOP owner-adoption record is currently present in
`docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`; merge is not treated as adoption.

### P0 repository governance contract — PR #75

PR #75 merged repository-side governance contract and hardened PR metadata requirements.

Evidence:

- PR-head CI #291: `SUCCESS` at `329cde854a34a713ccd10ad272fbd9554d88a602`;
- merge/current-main commit: `b4d4aab7393251ffc113a3f5bf654523bdb27865`;
- current-main CI #298: `SUCCESS`.

But live GitHub metadata still reports:

```text
main.protected = false
protection.enabled = false
required_status_checks.enforcement_level = off
```

Therefore repository contract completion is not GitHub enforcement completion.

## MVP delivery map

The detailed product-delivery map remains in
[`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md).

| Phase | Status | Summary |
|---|---|---|
| MVP-0 | VERIFIED | Control-plane foundation with identity, approvals, execution lifecycle, evidence, production effects disabled |
| MVP-1 | PARTIALLY VERIFIED | Deterministic execution contracts, adopted Runner/grant/snapshot design boundaries, verified Snapshot persistence and VOP source/test semantics |
| MVP-2 | PROPOSED | Complete authoritative authorization path through Snapshot Creator and Grant Issuer |
| MVP-3 | PROPOSED | Isolated READ-ONLY Runner vertical slice |
| MVP-4 | BLOCKED | Governed non-production mutation pilot until authority/Runner/verification gates pass |
| MVP-5 | PROPOSED | Productized multi-provider pilot and portable proof layer |

## STEP 0R — Post-VOP/P0 Source-of-Truth reconciliation

**Status:** IN_PROGRESS until this bounded reconciliation PR passes exact-head CI and is merged through a governed path.

Required:

- PR #74 VOP implementation and CI evidence represented accurately;
- VOP implementation distinguished from normative owner adoption;
- PR #75 repository governance contract represented accurately;
- live branch-protection failure kept visible;
- `CURRENT_PRODUCT_STATE.md`, `CURRENT_CAPABILITIES.md` and this roadmap aligned;
- historical evidence superseded, not deleted;
- no runtime, release or production claim introduced.

Exit gate:

```text
CURRENT STATE TRUSTWORTHY
```

## P0 — GitHub Main Governance Enforcement

**Status:** BLOCKED.

Repository-side contract exists, but live GitHub enforcement is not configured.

Required live state on `main`:

```text
pull_request_required = true
required_status_check = ci / verify
latest_head_required = true
force_push = false
branch_delete = false
conversation_resolution = true
ordinary_admin_bypass = false
```

Exit gate requires independent live GitHub Settings/API evidence. Documentation, PR merge or CI success
is insufficient.

```text
P0_GITHUB_GOVERNANCE = PASS
```

Higher-impact authority/Runner implementation must not rely on GitHub as a trusted enforcement
boundary before this gate passes.

## Architecture adoption candidate

PR #76 (`docs: adopt verifiable operations architecture target`) is an architecture/adoption candidate,
not current authority merely because it exists. Its adoption semantics must be reconciled with the
non-self-referential owner-adoption protocol and the current VOP source implementation before merge.
It must not be used to bypass P0 or infer runtime authority.

## STEP 1 — Authority Reality Audit

**Status:** PROPOSED next bounded engineering step after STEP 0R, with P0 enforcement completed before
higher-impact implementation relies on GitHub governance.

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

## STEP 3 — AuthoritativeSnapshotCreator

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

Bind exact grant/replay identity, issuer, runner audience/class, snapshot id/digest, execution id,
capability, target digest, payload digest, handler identity and validity window. Grant must be narrow,
short-lived, replay-safe and immutable.

## STEP 4B — Authoritative Grant Issuer

**Status:** PROPOSED.

Issuer loads committed immutable Snapshot evidence, checks required live issuance gates, binds exact
handler/Runner audience and persists grant state. It must not rebuild authorization from mutable UI or
request defaults.

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

**Status:** PROPOSED implementation. ADR-0008 design/safety boundary is owner-adopted; runtime remains
not implemented and production effects remain BLOCKED.

First allowed classes: bounded READ/COMPUTE operations such as repository inspection, diff, tests,
builds, static analysis and provider reads.

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

Before DAG/CyberCore complexity, prove one complete atomic operation cell end-to-end, including
positive path, permission deny, approval drift, target substitution, expired/replayed grant, wrong
runner/handler, transaction rollback, receipt-success/verification-fail and evidence completeness.

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

The VOP semantic mapping/equivalence source introduced by PR #74 is a foundation for this later module
boundary, not a module activation authority.

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

**Status:** PARTIAL FOUNDATION VERIFIED.

PR #74 provides deterministic semantic-equivalence profile/assessment contracts at source/test level.
Runtime candidate discovery, conformance, security review, owner adoption and activation remain future
work.

```text
SEMANTICALLY_EQUIVALENT != ADOPTED != ACTIVATED
```

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

## Explicit no-go items

- generic shell execution from user input;
- AI/CyberCore self-approval or grant issuance;
- shared VOODOO/CyberCore authority database;
- provider-specific policy logic in the trust kernel;
- production effects enabled by documentation/environment drift;
- silent fallback to unreleased identity/persistence backends;
- full microservice rewrite without measured pressure;
- treating merge/CI as normative owner adoption;
- treating repository governance documentation as live GitHub enforcement;
- public distribution before licensing is resolved.

## Immediate priority order

1. finish and verify this post-VOP/P0 Source-of-Truth reconciliation;
2. configure and independently verify GitHub `main` enforcement required by P0;
3. reconcile/decide architecture adoption candidate PR #76 without inferring authority from merge;
4. run the Authority Reality Audit against exact current protected `main`;
5. implement only proven missing authority prerequisites;
6. build `AuthoritativeSnapshotCreator` as one atomic authorization transaction;
7. only then proceed to Grant Issuer, outbox, READ-ONLY Runner, receipt, independent verification and OperationProof.
