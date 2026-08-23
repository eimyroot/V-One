# VOODOO One MVP Delivery Map

| Field | Value |
|---|---|
| Document status | PROPOSED product-delivery map; current implementation truth comes from `CURRENT_PRODUCT_STATE.md` / `CURRENT_CAPABILITIES.md` |
| Exact live Git identity | Query live Git directly; do not self-embed a commit as current |
| Latest runtime-attested baseline | `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` |
| Current post-G7 source milestone | PR #140 merged; canonical READ API from PR #137 merged; exact current SHA is queried live |
| G0 GitHub governance | VERIFIED / PASS from retained live verifier evidence |
| G7 durable resume/runtime wiring | IMPLEMENTED / MERGED |
| Default provider runtime pack | DISABLED / FAIL-CLOSED pending G8 |
| Real canonical HTTP READ E2E | NOT VERIFIED pending G8 |
| Provider WRITE | BLOCKED |
| Production effects | BLOCKED / disabled by default |
| Release status | DEVELOPMENT / CONTROLLED PILOT ONLY; release/deployment not performed |

The historical runtime-attested baseline above is intentionally retained because later source merges do
not retroactively create a new runtime attestation.

## MVP product promise

The MVP is not an autonomous agent that can do anything.

The MVP is one governed operational path:

```text
operator requests one concrete capability
  -> VOODOO shows exact target, payload, risk, policy, and required approval
  -> authoritative server-side checks bind one immutable AuthorizationSnapshot
  -> one narrow ExecutionGrant/v2 is issued from exact authority evidence
  -> control plane consumes that grant exactly once before dispatch
  -> durable dispatch / epoch / lease / fence bind one execution attempt
  -> an isolated bounded Runner executes one registered capability
  -> an independent Verifier observes provider state
  -> VOODOO records a truthful VerificationResult/v1 and profile-correct evidence
```

For `READ_ONLY_VERIFIED`, the terminal is `VerificationResult/v1`; Receipt/v2, Proof/v2 and Cell/v1 are
not universal READ requirements.

The MVP succeeds only when the operator can clearly answer:

- what is being requested;
- what will be touched;
- who approved it;
- what policy, permission, capability, target, and evidence authorized it;
- what exact authority was granted and consumed;
- what actually ran;
- whether the execution was current or fenced stale;
- whether the expected state was independently verified;
- whether the result is failed, cancelled, timed out, interrupted, verification-failed, or indeterminate;
- where independently verifiable evidence is stored.

## Proposed first customer profile

**Primary pilot customer - PROPOSED**

A platform, DevOps, SRE, or security engineering team that:

- already uses scripts, CI/CD, cloud APIs, or infrastructure tools;
- needs independent approval for selected changes;
- wants one evidence trail across human- and AI-originated proposals;
- can begin with non-production or read-only operations;
- values control and auditability more than maximum automation speed.

The MVP is not positioned for unrestricted production mutation, generic shell execution, or broad
multi-tenant enterprise deployment.

## MVP boundaries

### Included target scope

- authenticated operator-facing request flow;
- independent approval flow;
- deterministic policy explanation;
- immutable reviewed-request binding;
- authoritative Snapshot / Grant / grant-consumption path;
- explicit capability→terminal profile binding;
- durable outbox/envelope/inbox and epoch/lease/fence coordination;
- bounded READ Runner path;
- independent verifier and `VerificationResult/v1`;
- canonical READ HTTP API;
- restart-safe reconstruction of an ACTIVE canonical execution;
- one to three narrowly scoped provider capabilities;
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
- production WRITE before the READ-before-WRITE gate is satisfied.

## Delivery sequence

The historical MVP labels below are retained so the delivery-map/test vocabulary stays stable. Their
text is reconciled to current post-G7 reality; a `PROPOSED` milestone may therefore contain already
implemented prerequisites while its remaining product-level acceptance is still unverified.

## MVP-0 VERIFIED control-plane foundation

**Status:** VERIFIED for the development and controlled-pilot scope.

Delivered includes identity/session/RBAC/workspace/request/approval foundations, emergency stop,
SQLite persistence, audit/receipt integrity foundations, product composition, production-effects
default deny, and the retained historical runtime checkpoint at
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`.

The historical checkpoint does not attest later G7 source changes.

## MVP-1 PARTIALLY VERIFIED contract and authorization-evidence foundation

**Status:** PARTIALLY VERIFIED as a historical milestone bucket; major authority prerequisites are now
implemented/merged, while the bucket remains partial because product-level runtime acceptance is not
complete.

Delivered/current prerequisites include:

- immutable reviewed-request and approval evidence;
- `AuthoritativeSnapshotCreator` and durable snapshot persistence;
- database-backed permission/workspace-membership authority;
- `ExecutionGrant/v2` authoritative issuance and durable ONE_TIME consumption;
- transactional dispatch outbox plus envelope/inbox admission;
- execution epoch/lease/current-fence binding;
- immutable capability→terminal profile authority;
- bounded READ Runner and independent verifier components.

Still required at product level is G8 real canonical HTTP READ E2E through the default READ-only
provider runtime pack, including restart/resume while ACTIVE, independent verification and retained
fail-closed evidence.

## MVP-2 PROPOSED authoritative-path product acceptance

**Status:** PROPOSED as a product acceptance milestone, not as a claim that the underlying authority
components are absent.

Current code already implements the core authoritative Snapshot→Grant→Consumption→Dispatch path.
MVP-2 now exits only when the canonical product/API experience repeatedly proves those authorities
against current database state and exposes truthful blocked/failed/intermediate states without
falling back to legacy execution authority.

Acceptance remains deny-by-default and no client-supplied authority fact becomes authoritative.

## MVP-3 PROPOSED productized isolated read-only Runner pilot

**Status:** PROPOSED for the default product runtime pack and real canonical HTTP E2E.

Bounded GitHub READ Runner/Verifier pilots and canonical READ terminal/runtime components exist, and G7
adds restart-safe ACTIVE-execution reconstruction. G8 must compose them into the explicit default
READ-only provider runtime pack and prove one real authenticated canonical path:

```text
HTTP admission
→ authority + durable preparation
→ ACTIVE epoch / current lease / capsule
→ process restart before completion
→ durable resume without duplicate authority/dispatch/lease
→ resumed READ Runner
→ durable completion
→ independent Verifier
→ VerificationResult/v1
```

Exit gate includes fail-closed corruption/revocation tests, distinct Runner/Verifier credential
decisions, no ambient credential fallback, and independent review.

## MVP-4 BLOCKED governed non-production mutation pilot

**Status:** BLOCKED until MVP-3/G8 passes and a separate WRITE authorization/effect gate is issued.

Historical F4b/F6b bounded staging effects are evidence, not reusable current mutation authority.
Current A09 CREATE_REF/rollback orchestration remains pre-effect only. Any future mutation must be one
narrow reversible non-production capability with exact target/precondition/current-fence checks,
least-privilege credential scope, independent post-state verification and truthful uncertainty.

No generic shell, arbitrary URL, ambient credential, automatic mutation retry or provider-wide
authority is allowed.

## MVP-5 PROPOSED productized pilot and integration layer

**Status:** PROPOSED.

Required product elements include capability/status visibility, native request→approval→authorization→
execution→verification views, exportable evidence, connector health/permission visibility, repeatable
onboarding, recovery runbooks and operator-visible blocked/failed/indeterminate outcomes.

Exit requires at least one external controlled pilot and no manual database repair for normal recovery.

## MVP release gate

The MVP may be described as pilot-ready only when all of the following are independently evidenced:

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

## Immediate priority order

1. merge post-G7 product-truth convergence only after exact-head CI and independent review;
2. implement G8 as a READ-only composition/runtime pack using existing canonical components;
3. prove authenticated canonical HTTP READ E2E;
4. inject restart while execution is ACTIVE and prove durable resume without duplicate prepare/grant/consume/dispatch/epoch/lease;
5. prove independent `VerificationResult/v1` and fail-closed corruption/revocation paths;
6. repeat/retain READ E2E evidence required by ADR-0019;
7. only then evaluate a separately authorized bounded WRITE activation;
8. keep production release, deployment and unrestricted mutation separate gates;
9. keep CyberCore intelligence-only and outside authority issuance/execution.

## Metrics

The MVP should track request-to-decision time, approval invalidation, authorization failures by reason,
grant replay rejection, execution terminal states, resume/fencing outcomes, verification failures,
indeterminate outcomes, evidence verification, operator recovery time and zero unauthorized production
effects.

Metrics are observability signals, not substitutes for authorization or acceptance evidence.
