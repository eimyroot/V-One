# VOODOO One MVP Delivery Map

| Field | Value |
|---|---|
| Document status | PROPOSED product-delivery map |
| Current verified Git baseline | `main@57c7bf2277616c4445039865ac7cf81c5fada858` |
| Latest runtime-attested baseline | `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` |
| ADR-0008 review commit | `0fa69411b246c4bd80b8a2eaa989e60fd8bca663`, merged via PR #54 |
| ADR-0007 | VERIFIED acceptance of pure deterministic contracts only |
| ADR-0008 | ADOPTED design/safety scope by explicit owner decision on 2026-08-08; implementation authorization not implied |
| Production effects | BLOCKED |
| Release status | DEVELOPMENT / CONTROLLED PILOT ONLY |

## MVP product promise

The MVP is not an autonomous agent that can do anything.

The MVP is one governed operational path:

```text
operator requests one concrete capability
  -> VOODOO shows the exact target, payload, risk, policy, and required approval
  -> an independent approver authorizes that exact request
  -> VOODOO issues one short-lived, one-time execution grant
  -> an isolated Runner executes one registered capability
  -> an independent verifier observes the post-state
  -> VOODOO records the actual outcome, receipt, and evidence
```

The MVP succeeds only when the operator can clearly answer:

- what is being requested;
- what will be touched;
- who approved it;
- what exact authority was granted;
- what actually ran;
- what changed;
- whether the expected effect was verified;
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

### Included

- one operator-facing request flow;
- one independent approval flow;
- deterministic policy explanation;
- exact execution-target, approval-evidence, grant, and receipt contracts;
- capability registry;
- isolated non-production Runner;
- one-time durable grant consumption;
- cancellation, lease, and fencing semantics;
- governed target mutation gateway;
- independent precondition and postcondition verification;
- bounded evidence and clear terminal outcomes;
- one to three narrowly scoped pilot capabilities;
- integration through versioned adapters rather than product-specific hard-coding.

### Excluded

- generic shell or arbitrary script execution;
- unrestricted production changes;
- AI self-approval;
- shared VOODOO/CyberCore database;
- broad provider administration;
- dynamic plugin discovery;
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
- verified development checkpoint at `main@d57d37111b8bc9471a136b6c618aad8e920f1aff`.

Remaining limitation:

- execution still runs inside the control-plane operating-system identity.

## MVP-1 PARTIALLY VERIFIED contract and decision foundation

**Status:** PARTIALLY VERIFIED.

Delivered:

- ADR-0006 read-only Policy Decision Graph foundation;
- ADR-0007 accepted deterministic execution-target, approval-evidence-set, execution-grant, and
  execution-receipt value contracts;
- strict representation, canonical digest, and cross-contract binding tests;
- ADR-0008 isolated Runner boundary and threat model reviewed as source evidence and subsequently
  owner-adopted for the exact design/safety bytes on 2026-08-08;
- R3-01 through R3-04 closed for exact patch
  `a39a8febd258b27e3b756e1df6b6fa2b795614642b5874dff66a5990d6c2ac02`.

Still required:

- authoritative grant issuance;
- authenticity/signature envelope and trust policy;
- durable one-time claim store;
- runtime integration.

Owner-decision gate:

- VERIFIED: ADR-0008 was adopted by an explicit owner decision without weakening its safety
  boundaries; production effects remain BLOCKED and implementation authorization is not implied.

Remaining exit criteria:

- implementation slices preserve the adopted contract/runtime responsibility matrix;
- no documentation claim treats design evidence as runtime implementation.

## MVP-2 PROPOSED operator and approver workflow

**Status:** PROPOSED.

Goal:

Make the governed request understandable before any isolated execution exists.

Required product behavior:

1. operator chooses one registered capability;
2. UI/API shows exact target, environment, payload digest, expected effect, risk, policy version,
   and verification plan;
3. policy explains why approval is required;
4. approver sees the exact immutable request and cannot approve a moving target;
5. drift invalidates the approval;
6. execution remains blocked until every required gate succeeds;
7. operator sees a stable execution timeline and terminal state.

Acceptance criteria:

- no free-form executable command field;
- approval binds to immutable request data;
- policy and missing gates are human-readable;
- cancellation before execution is unambiguous;
- negative-path tests cover stale approval, changed target, changed payload, expired approval, and
  emergency stop;
- accessibility and keyboard-first operation are verified for the critical path.

## MVP-3 PROPOSED isolated read-only Runner pilot

**Status:** PROPOSED.

Goal:

Prove the full control-plane-to-Runner boundary without external mutation.

Initial capability candidates must be read-only and separately approved. Examples:

- verify a repository or evidence package;
- inspect a target version or configuration digest;
- run a bounded validation preset;
- collect a governed post-state observation.

Required controls:

- separate Runner OS identity;
- rootless capsule;
- read-only immutable base;
- bounded workspace and resources;
- network denied by default;
- exact capability registry entry;
- one-time durable grant consumption;
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

Turn the proven vertical slice into a usable product pilot without turning VOODOO into an
integration monolith.

Required product elements:

- capability catalog with clear status and risk class;
- native request, approval, execution, and evidence views;
- adapter SDK/contract with versioning and conformance tests;
- connector health and permission visibility;
- clear separation among:
  - systems of understanding;
  - systems of authorization;
  - systems of action;
  - systems of evidence;
- exportable audit/evidence package;
- operator runbooks and recovery procedures;
- pilot onboarding and permission checklist;
- product telemetry without secret or payload leakage.

Exit gate:

- one external team completes an end-to-end pilot;
- operators can diagnose blocked, failed, cancelled, timed-out, interrupted, and indeterminate
  outcomes;
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
2. add signed/authenticated grant and receipt envelopes with key rotation;
3. strengthen supply-chain provenance and external evidence anchoring;
4. introduce read-only CyberCore intake;
5. evaluate workspace-scoped tenancy and released OIDC;
6. evaluate PostgreSQL/HA only when measured product demand requires it;
7. consider production mutation only through a separate governed release program.

## Immediate priority order

1. implement the operator/approver immutable-request slice;
2. prepare the separately reviewable child R3 decisions required before isolated Runner runtime;
3. implement a read-only isolated Runner vertical slice only after explicit implementation
   authorization;
4. prove one-time consumption, cancellation, fencing, stable receipt identity, and independent
   verification;
5. only then select one narrow non-production mutation capability;
6. keep CyberCore mutation and unrestricted production out of scope.

## Metrics

The MVP should track:

- request-to-decision time;
- approval invalidations caused by drift;
- replay attempts rejected;
- executions by terminal status;
- indeterminate outcome rate;
- cancellation acknowledgement and completion latency;
- postcondition verification success/failure;
- evidence-package verification success;
- operator recovery time;
- capability-specific failure rate;
- zero unauthorized production effects.

Metrics are observability signals, not substitutes for authorization or acceptance evidence.
