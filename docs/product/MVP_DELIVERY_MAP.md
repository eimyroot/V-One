# VOODOO One MVP Delivery Map

| Field | Value |
|---|---|
| Document status | PROPOSED product-delivery map |
| Exact live Git identity | Query live Git directly; do not self-embed a commit as current |
| Latest runtime-attested baseline | `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` |
| Latest verified delivery milestone | Authorization Snapshot persistence merged through PR #71; exact current merge/CI identity is read from live GitHub evidence |
| ADR-0007 | VERIFIED acceptance of pure deterministic contracts only |
| ADR-0008 | ADOPTED design/safety scope; implementation authorization not implied |
| ADR-0009 | ADOPTED grant issuance/authenticity design boundary; implementation authorization not implied |
| ADR-0010 | ADOPTED immutable authorization-snapshot facts boundary; authoritative Snapshot Creator remains unimplemented |
| Production effects | BLOCKED |
| Release status | DEVELOPMENT / CONTROLLED PILOT ONLY |

## MVP product promise

The MVP is not an autonomous agent that can do anything.

The MVP is one governed operational path:

```text
operator requests one concrete capability
  -> VOODOO shows the exact target, payload, risk, policy, and required approval
  -> authoritative server-side checks bind one immutable AuthorizationSnapshot
  -> one narrow ExecutionGrant is issued from exact authority evidence
  -> an isolated Runner executes one registered capability
  -> an independent verifier observes the post-state
  -> VOODOO records the actual outcome, receipt, evidence, and proof
```

The MVP succeeds only when the operator can clearly answer:

- what is being requested;
- what will be touched;
- who approved it;
- what policy, permission, capability, target, and evidence authorized it;
- what exact authority was granted;
- what actually ran;
- what changed;
- whether the expected effect was independently verified;
- whether the result is failed, cancelled, timed out, interrupted, or indeterminate;
- where the independently verifiable evidence is stored.

## Proposed first customer profile

**Primary pilot customer - PROPOSED**

A platform, DevOps, SRE, or security engineering team that:

- already uses scripts, CI/CD, cloud APIs, or infrastructure tools;
- needs independent approval for selected changes;
- wants one evidence trail across human- and AI-originated proposals;
- can begin with non-production or read-only operations;
- values control and auditability more than maximum automation speed.

The MVP is not yet positioned for unrestricted production mutation, generic shell execution, or
broad multi-tenant enterprise deployment.

## MVP boundaries

### Included target scope

- one operator-facing request flow;
- one independent approval flow;
- deterministic policy explanation;
- immutable reviewed-request binding;
- exact execution-target, approval-evidence, authorization-snapshot, grant, and receipt contracts;
- authoritative policy/permission/capability/target composition before grant issuance;
- explicit capability and handler registry;
- isolated read-only/non-production Runner pilot;
- one-time durable grant consumption;
- cancellation, lease, and fencing semantics;
- credential isolation for provider-backed capabilities;
- independent precondition and postcondition verification;
- bounded evidence and clear terminal outcomes;
- one to three narrowly scoped pilot capabilities;
- integration through versioned modules/adapters rather than provider logic in the trusted kernel.

### Excluded

- generic shell or arbitrary script execution;
- unrestricted production changes;
- AI self-approval;
- shared VOODOO/CyberCore database;
- broad provider administration;
- dynamic trusted plugin discovery;
- automatic rollback presented as guaranteed recovery;
- unbounded marketplace or connector catalog;
- full enterprise tenancy before the single-team pilot is proven.

## Delivery sequence

## MVP-0 VERIFIED control-plane foundation

**Status:** VERIFIED for the development and controlled-pilot scope.

Delivered:

- identity, sessions, RBAC, workspaces, requests, approvals, lifecycle, emergency stop;
- local bounded adapters;
- idempotency, lease, fence, audit, receipt, and recovery foundations;
- ProofGraph verification and repository-owned evidence workflow;
- production effects disabled by default;
- historical verified development checkpoint at
  `main@d57d37111b8bc9471a136b6c618aad8e920f1aff`.

Remaining limitation:

- existing bounded execution still shares the control-plane operating-system identity;
- this historical runtime checkpoint does not attest later source changes.

## MVP-1 PARTIALLY VERIFIED contract and authorization-evidence foundation

**Status:** PARTIALLY VERIFIED.

Delivered:

- ADR-0006 read-only Policy Decision Graph foundation;
- ADR-0007 accepted deterministic execution-target, approval-evidence-set, execution-grant, and
  execution-receipt value contracts;
- strict representation, canonical digest, and cross-contract binding tests;
- ADR-0008 isolated Runner boundary and threat model owner-adopted for exact design/safety bytes;
- ADR-0009 grant issuance/authenticity boundary owner-adopted for its exact design scope;
- ADR-0010 immutable Authorization Snapshot facts boundary owner-adopted for its exact design scope;
- immutable `AuthorizationSnapshot` contract;
- append-only Authorization Snapshot persistence foundation, schema v9, immutable database triggers,
  idempotency/request/review binding, and fresh PR/post-merge CI evidence through PR #71.

Still required:

- complete Authority Reality Audit;
- immutable/versioned policy authority sufficient for snapshot creation;
- authoritative server-side `execution.run` permission authority;
- authoritative capability definition/activation and deterministic target binding;
- transaction-aware authority reads and snapshot persistence;
- `AuthoritativeSnapshotCreator`;
- authoritative grant issuance/authenticity implementation;
- durable one-time claim store;
- isolated Runner runtime integration.

Owner-decision gate:

- VERIFIED for the exact adopted ADR-0008/0009/0010 design boundaries;
- adoption does not itself authorize runtime implementation, release, deployment, or production
  effects.

Remaining exit criteria:

- authority inputs have explicit authoritative owners;
- one coherent authorization transaction produces the snapshot from authoritative facts;
- implementation slices preserve adopted control-plane/Runner responsibility boundaries;
- no documentation claim treats design evidence as runtime implementation.

## MVP-2 PROPOSED authoritative authorization path

**Status:** PROPOSED.

Goal:

Complete the control-plane path from immutable reviewed request to authoritative snapshot and narrow
execution grant before any isolated execution is attempted.

Required product behavior:

1. operator chooses one registered capability;
2. UI/API shows exact target, environment, payload digest, expected effect, risk, policy identity,
   required permission, approval requirements, and verification plan;
3. immutable reviewed content is revalidated server-side;
4. policy, `execution.run`, capability activation, target binding, approval evidence, and trusted
   timestamp are resolved authoritatively;
5. one atomic authorization transaction creates and persists the exact AuthorizationSnapshot;
6. a later Grant Issuer binds exact snapshot digest, execution id, capability, target, payload,
   handler, audience, TTL, and replay identity;
7. drift, stale approval, missing authority, or live deny gate fails closed;
8. no free-form executable command becomes authority.

Acceptance criteria:

- no client-supplied authority fact is trusted;
- approval binds to immutable request data;
- policy and missing gates are human-readable;
- snapshot persistence is transaction-aware under one outer authorization transaction;
- negative tests cover stale approval, changed target, changed payload, missing permission, inactive
  capability, missing policy revision, expiry, and rollback;
- grant scope cannot exceed snapshot scope;
- production remains deny-by-default.

## MVP-3 PROPOSED isolated read-only Runner pilot

**Status:** PROPOSED.

Goal:

Prove the full control-plane-to-Runner boundary without external mutation.

Initial capability candidates must be read-only or compute-only and separately authorized. Examples:

- verify a repository or evidence package;
- inspect a target version or configuration digest;
- run a bounded validation preset;
- collect a governed post-state observation.

Required controls:

- separate Runner identity and isolation boundary;
- rootless/hardened capsule or equivalent reviewed isolation;
- read-only immutable base where applicable;
- bounded workspace and resources;
- network denied by default;
- exact capability + handler registry identity;
- exact runner audience/class binding;
- one-time durable grant consumption;
- short-lived least-privilege credentials only when required;
- stable Runner receipt identity;
- cancellation and lease/fence behavior;
- independent observation and receipt ingestion;
- no fallback to in-process execution.

Exit gate:

- concurrent replay test proves one durable consume and one attempt;
- crash injection covers claim, startup, execution, verification, and receipt delivery;
- receipt conflicts fail closed;
- no secret appears in grant, logs, evidence, or workspace;
- independent security review passes;
- pilot remains non-production.

## MVP-4 BLOCKED governed non-production mutation pilot

**Status:** BLOCKED until MVP-3 passes and a separate R3/R4 authorization is issued.

Goal:

Execute exactly one narrow, reversible, non-production mutation capability.

The first mutation capability must have:

- one typed target kind;
- one exact expected-state token;
- provider-supported conditional mutation or reviewed equivalent;
- non-bypassable governed target gateway;
- current fence enforcement at mutation time;
- independent precondition and postcondition verification;
- explicit timeout, cancellation, and indeterminate behavior;
- bounded rollback or compensation plan that is not represented as guaranteed;
- no generic shell, arbitrary URL, ambient credential, or provider-wide authority.

Pilot examples are selected only after a capability risk review. The roadmap must not prematurely
declare a provider or operation.

Exit gate:

- every successful receipt has an independently passed postcondition;
- stale target and stale fence mutations are rejected;
- cancellation races preserve truthful outcomes;
- failure and uncertainty never become success;
- external side effects remain non-production and narrowly allowlisted;
- evidence can be independently verified from a portable package.

## MVP-5 PROPOSED productized pilot and integration layer

**Status:** PROPOSED.

Goal:

Turn the proven Operation Cell into a usable product pilot without turning VOODOO into an integration
monolith.

Required product elements:

- capability catalog with clear status and risk class;
- native request, approval, authorization, execution, verification, and evidence views;
- module/adapter SDK with versioning and conformance tests;
- connector health and permission visibility;
- clear separation among systems of understanding, authorization, action, verification, and evidence;
- exportable audit/evidence/proof package;
- operator runbooks and recovery procedures;
- pilot onboarding and permission checklist;
- product telemetry without secret or payload leakage.

Exit gate:

- one external team completes an end-to-end pilot;
- operators can diagnose blocked, failed, cancelled, timed-out, interrupted, verification-failed, and
  indeterminate outcomes;
- no manual database repair is required for normal recovery;
- capability onboarding is repeatable and reviewable;
- support and incident boundaries are documented.

## MVP release gate

The MVP may be described as pilot-ready only when all of the following are VERIFIED:

```text
MVP-0=VERIFIED
MVP-1=VERIFIED
MVP-2=VERIFIED
MVP-3=VERIFIED
MVP-4=VERIFIED_FOR_ONE_NARROW_NON_PRODUCTION_CAPABILITY
MVP-5=VERIFIED_FOR_CONTROLLED_PILOT
PRODUCTION_EFFECTS=DISABLED
GENERIC_SHELL=ABSENT
EVIDENCE_EXPORT=VERIFIED
RECOVERY_RUNBOOK=VERIFIED
OWNER_RELEASE_DECISION=APPROVED
```

This does not authorize unrestricted production use.

## Post-MVP sequence

1. add a second independently reviewed capability;
2. strengthen signed/authenticated proof, key rotation, and portable attestations;
3. strengthen supply-chain provenance and external evidence anchoring;
4. introduce read-only CyberCore observation/intake;
5. evaluate workspace-scoped tenancy and released OIDC;
6. evaluate PostgreSQL/HA only when measured product demand requires it;
7. consider production mutation only through a separate governed release program.

## Immediate priority order

1. finish Source-of-Truth reconciliation without self-referential current-SHA claims;
2. run the Authority Reality Audit against exact live `main`;
3. implement only proven-missing policy/permission/capability/target/transaction prerequisites;
4. implement `AuthoritativeSnapshotCreator` as one coherent authorization transaction;
5. implement the authoritative Grant Issuer and exact handler/Runner registry;
6. add transactional outbox/dispatch and credential-broker boundary;
7. implement a read-only isolated Runner vertical slice only after the authority path is proven;
8. prove receipt + independent verification before any mutation pilot;
9. keep CyberCore mutation and unrestricted production out of scope.

## Metrics

The MVP should track:

- request-to-decision time;
- approval invalidations caused by drift;
- authorization snapshot creation failures by reason;
- grant replay attempts rejected;
- executions by terminal status;
- indeterminate outcome rate;
- cancellation acknowledgement and completion latency;
- postcondition verification success/failure;
- evidence/proof-package verification success;
- operator recovery time;
- capability-specific failure rate;
- zero unauthorized production effects.

Metrics are observability signals, not substitutes for authorization or acceptance evidence.
