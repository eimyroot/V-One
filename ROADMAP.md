# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Reconciled | `2026-08-24` |
| Canonical G7 merge snapshot | PR #140 / `60bc9c26813ee23c73bac194a9adb27714e8a1e8` |
| Historical R1 reconciliation | PR #128 / `d9e27ff17b76f29daba4a3421b11cc396826fe12` |
| VOP semantic revision | `vop-terminology-freeze-r2` / ADR-0018 |
| Capability truth | [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) |
| Current-state truth | [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) |
| Post-G7 truth | [`docs/product/POST_G7_CANONICAL_STATE.md`](docs/product/POST_G7_CANONICAL_STATE.md) |
| G8 gate | [`docs/product/G8_READ_RUNTIME_GATE.md`](docs/product/G8_READ_RUNTIME_GATE.md) |
| Production status | BLOCKED until separately governed release |

## Status vocabulary

- **VERIFIED** — demonstrated by the named evidence scope;
- **IMPLEMENTED** — exists in source/configuration; not automatically live/released;
- **PROPOSED** — target direction or prepared design;
- **INFERRED** — reasoned from evidence but not directly demonstrated;
- **UNKNOWN** — required evidence unavailable;
- **BLOCKED** — intentionally unavailable until a named gate passes.

Roadmap status does not prove implementation. Implementation does not prove live provider effect,
independent verification, release, or deployment.

## Architectural invariant

```text
ONE SYSTEM
=
ONE CANONICAL OPERATION LANGUAGE
+
ONE AUTHORITY LINEAGE
+
ONE EXECUTION LINEAGE
+
CURRENT WORKSPACE SCOPE
+
CAPABILITY-BOUND TERMINAL PROFILE
+
INDEPENDENT VERIFICATION
+
RESTART-SAFE CONTINUITY
+
PROFILE-CORRECT PORTABLE EVIDENCE
```

READ-only verification terminates at `VerificationResult/v1`. Bounded mutation may additionally produce
`ExecutionReceipt/v2 → VerificationResult/v1 → OperationProof/v2 → OperationCell/v1` after a separately
authorized effect. No compatibility path may widen those contracts.

The organization-scoped approval/profile design remains separately **PROPOSED** in
[ADR-0003](docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md). Workspace
membership is a current scope boundary; it does not activate Solo, Team, or Regulated policy behavior.

## Completed technical milestones

| Track | Status | Evidence boundary |
|---|---|---|
| AuthorizationSnapshot + authoritative creator | VERIFIED | source/tests + schema 0009 |
| ExecutionGrant/v2 + durable grant service | VERIFIED | source/tests + schema 0010 |
| Grant consumption + transactional Outbox | VERIFIED | source/tests + schema 0011 |
| Dispatch Envelope + Inbox/dedup | VERIFIED | source/tests + schema 0012 |
| ExecutionEpoch/Lease + DurableCoordinator | VERIFIED | source/tests + schema 0013 |
| Workspace membership scope | IMPLEMENTED | schema 0014 + membership/revocation tests |
| Capability→terminal allowlist | IMPLEMENTED | canonical profile tests |
| Database-backed permission authority | IMPLEMENTED | canonical composition tests |
| ProductComposition canonical runtime seam | IMPLEMENTED | merged PR #128 + PR #140 |
| Canonical public READ API | IMPLEMENTED | merged PR #137 |
| Restart-safe durable resume | IMPLEMENTED | merged PR #140 |
| Runtime resume wiring | IMPLEMENTED | merged PR #140 |
| Isolated READ Runner | VERIFIED | D4 live governed read evidence |
| Independent verifier | VERIFIED | E3 evidence |
| VerificationResult/v1 | VERIFIED | E4B + historical F6b evidence |
| Reusable CREATE_REF A09 preflight orchestration | IMPLEMENTED | no current provider effect |
| Reusable rollback A09 preflight orchestration | IMPLEMENTED | no current provider effect |
| OperationProof/v2 | VERIFIED | bounded-mutation contract + historical F6b |
| OperationCell/v1 | VERIFIED | bounded-mutation contract + historical F6b |
| Security Intelligence R-SI1.1 | IMPLEMENTED | intelligence-only metadata/tests |
| Security Intelligence R-SI1.2 normalization | IMPLEMENTED | merged PR #135; descriptive/context-only |

These rows do not authorize a new provider mutation or release.

## Gate G0 — GitHub main enforcement

**Status: VERIFIED / PASS.**

Identifiable exit evidence:

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

Verified controls include PR-only main, required `verify` from workflow `ci`, latest-head strict checks,
force-push disabled, branch deletion disabled, conversation resolution, no ordinary bypass, active
rulesets, and verifier-source binding. G0 PASS is not release/deploy authorization.

## Gates G1–G6 — Canonical trust-plane foundation

**Status: IMPLEMENTED / VERIFIED in their named evidence scopes.**

Current canonical composition preserves one ProductService database, one DatabasePermissionAuthority,
current user/role/active/workspace/membership reevaluation, immutable capability→terminal binding,
canonical Grant/Dispatch/Lease lineage, profile-specific terminal semantics, and no hidden fallback to
legacy authority.

Historical PR #128 remains the major reconciliation provenance for this foundation. Its historical
review/evidence facts are preserved and are not upgraded by later success.

## Gate G7 — Canonical public READ API + restart-safe resume

**Status: IMPLEMENTED / MERGED / POST-MERGE VERIFIED.**

Public surface:

```text
GET  /api/v1/operations/status
POST /api/v1/operations/{request_id}/read
```

PR #137 merged the canonical READ HTTP surface. PR #140 reconciled it with restart-safe durable resume
and runtime resume wiring. The accepted reconciliation head was
`cda7d957cbba8412aa8cd8720e5eb95ed781e58d`.

Exact reconciliation evidence:

```text
CI #1013 = SUCCESS
D4 #201 = SUCCESS
E3 #192 = SUCCESS
E4B #188 = SUCCESS
fresh Codex R3 = no major issues
```

Post-merge evidence on `main@60bc9c26813ee23c73bac194a9adb27714e8a1e8`:

```text
CI #1015 = SUCCESS
D4 #202 = SUCCESS
E3 #193 = SUCCESS
E4B #189 = SUCCESS
full pytest = SUCCESS
product readiness = SUCCESS
dependency vulnerability audit = SUCCESS
product image build + smoke = SUCCESS
```

Resume is allowed only for the same durable execution. It must not re-run `prepare()`, issue or consume
a second grant, append duplicate dispatch admission, or reacquire a lease. Current DB permission,
durable evidence bindings, terminal profile, envelope revision, and current fence are revalidated.

G7 does not activate a default provider runtime pack and does not create a provider WRITE route.

## Hard gate — READ before WRITE

The safety decision is being governed in
[`ADR-0019`](docs/adr/ADR-0019-read-e2e-before-write.md). Until its adoption gate and the evidence below
are complete, WRITE remains BLOCKED.

Required evidence before WRITE can become merely `ELIGIBLE`:

```text
READ_E2E             = VERIFIED
RESTART_RESUME       = VERIFIED
NO_DUPLICATE_EFFECT  = VERIFIED
AUTHORITY_CONTINUITY = VERIFIED
INDEPENDENT_VERIFY   = VERIFIED
FAIL_CLOSED          = VERIFIED

WRITE_RUNTIME_GATE   = ELIGIBLE
```

`ELIGIBLE` is not WRITE authorization.

## Gate G8 — Explicit READ-only provider runtime pack

**Status: BLOCKED / NEXT IMPLEMENTATION GATE.**

The first default provider pack is READ-only. It must reuse the existing canonical stack rather than
create a parallel execution framework.

Required properties:

- exact ProductComposition database and DatabasePermissionAuthority;
- exact canonical terminal-profile registry, envelope revision, and current execution fence;
- explicit provider configuration;
- distinct Runner and independent Verifier identities and credential decisions;
- no credential bytes in V-One evidence;
- no ambient `GITHUB_TOKEN` fallback;
- exact capability `github.read-ref/v1` only;
- no CREATE_REF, DELETE_REF, rollback, generic execute, or arbitrary mutation transport;
- missing or ambiguous configuration fails closed.

Implementation should reuse the existing `GitHubReadTransport`, `GitHubApiRefReadTransport`,
`GitHubRefReadHandler`, `CanonicalGitHubReadTerminal`, canonical runtime, and durable resume contracts.

G8 exits only after fresh exact-head CI/security/review and a real canonical authenticated HTTP READ E2E
run has been demonstrated through independent `VerificationResult/v1`.

## Gate G8.1 — Real canonical READ E2E + restart

**Status: BLOCKED until G8 runtime exists.**

Required operational sequence:

```text
authenticated HTTP request
→ current DB permission + workspace membership
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ one-time GrantConsumptionWitness/v1
→ transactional Outbox
→ DispatchEnvelope
→ Inbox admission
→ ACTIVE ExecutionEpoch + current Lease
→ ExecutionCapsule
→ process interruption/restart before Runner completion
→ durable resume of the same ACTIVE execution
→ no new prepare/grant/consume/outbox/envelope/inbox/epoch/lease
→ current-fence + authority-continuity validation
→ resumed isolated READ Runner
→ durable completion
→ independent Verifier with separate identity/credential decision
→ VerificationResult/v1
```

The current resume contract does not claim resumption of an already `COMPLETED` execution. Completed-execution recovery or reverification is a separate future design boundary.

The sequence must be repeated and failure-injected before the WRITE eligibility gate can change.

## Gate G9 — Provider WRITE runtime/effect

**Status: BLOCKED.**

WRITE design/pre-effect tests may continue, but provider mutation activation cannot begin before the
READ-before-WRITE evidence gate is VERIFIED. A future WRITE slice requires its own effect-specific
credential scope, independent post-state verification, rollback semantics, security review, and
explicit authorization.

## Gate G10 — RC / release / deployment

**Status: BLOCKED.**

Before release/deploy:

- G8 READ runtime and real HTTP READ E2E;
- restart/resume continuity evidence;
- fresh security/adversarial review;
- dependency/SBOM/image/provenance gates;
- secrets/credential rotation and operational runbooks;
- observability/incident/rollback plan;
- commercial/legal/privacy/support requirements as applicable;
- explicit release authorization;
- explicit deployment authorization.

Production effects stay disabled until those gates are separately satisfied.

## CyberCore

**Status: BLOCKED during V-One product/release-governance hardening.**

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

CyberCore must not become a workaround for unfinished V-One product/release controls.

## Later productization

- organization/tenant policy maturation through ADR-0003 lineage;
- released enterprise identity / MFA / OIDC;
- PostgreSQL adapter/isolation gates;
- artifact provenance/signing eligibility;
- production deployment/release runbooks;
- commercial/legal/support readiness.

These remain PROPOSED or BLOCKED by their individual evidence gates.
