# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Authority scope | Delivery order and exit gates; does not prove implementation or adoption |
| Source of documented capability truth | `docs/product/CURRENT_CAPABILITIES.md` |
| Evidence baseline | `CURRENT_PRODUCT_STATE.md` |
| Live-state boundary | Phase statuses are documented at the cited baseline and require direct verification for a later HEAD, CI or runtime |
| Production status | BLOCKED until an explicit governed release |
| Update rule | Update with every accepted milestone or material scope change |
| Governance | `docs/governance/DOCUMENTATION_POLICY.md` and `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md` |

## Status vocabulary

- **VERIFIED** — all stated gates for the exact claim and scope are evidenced at the documented baseline;
- **PARTIALLY_VERIFIED** — an exact subset is verified and the missing gates are listed;
- **IMPLEMENTED** — exists in code or documentation but has not met every stated verification scope;
- **PROPOSED** — intended or under review; not necessarily adopted and not implemented;
- **INFERRED** — derived from evidence but not directly demonstrated;
- **UNKNOWN** — evidence is unavailable or conflicting;
- **BLOCKED** — intentionally unavailable or unsafe to activate.

Roadmap status is a planning classification. It becomes `LIVE_VERIFIED` only after the current
repository and required gates are checked directly. A roadmap edit, merge or milestone label cannot
create a capability, release or deployment.

## MVP delivery map

The detailed product-delivery map lives in
[`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md).

| Phase | Status | Summary |
|---|---|---|
| MVP-0 | VERIFIED | Control-plane foundation with identity, approvals, execution lifecycle, evidence, and production effects disabled |
| MVP-1 | PARTIALLY_VERIFIED | Deterministic contract and decision foundation, including ADR-0007 pure execution-contract value objects and reviewed ADR-0008 evidence |
| MVP-2 | PROPOSED | Operator and approver immutable-request workflow |
| MVP-3 | PROPOSED | Isolated read-only Runner pilot |
| MVP-4 | BLOCKED | Governed non-production mutation pilot |
| MVP-5 | PROPOSED | Productized pilot and integration layer |

The central product promise remains:

```text
operator requests one concrete capability
-> exact scope and approval are visible
-> one short-lived one-time grant is issued
-> one registered capability executes in an isolated Runner
-> independent post-state verification runs
-> VOODOO shows the actual outcome and evidence
```

## Program sequence

### EPIC-000 — Governed control-plane foundation

**Status at documented baseline:** VERIFIED for the development and controlled-pilot scope.

Delivered:

- versioned FastAPI API and static operator console;
- local identity, RBAC, bootstrap, login, logout, and session revocation;
- workspaces, change requests, approvals, execution lifecycle, and emergency stop;
- SQLite migrations, statement catalog, audit ledger, and receipt ledger;
- production effects disabled by default;
- hash-locked dependencies, CI, Docker build, smoke, and readiness gates.

Remaining limitations:

- no unrestricted production release;
- no workspace-scoped multi-tenant role model;
- no released OIDC or PostgreSQL backend.

### EPIC-001 — Execution safety and recovery

**Status at documented baseline:** VERIFIED for the local adapter scope.

Delivered:

- bounded adapter capabilities;
- portable symlink-safe sandbox path resolution;
- idempotency binding;
- execution leases and fencing;
- explicit indeterminate recovery under emergency stop;
- bounded execution output.

Next:

- isolate execution from the control-plane process;
- add heartbeat, cancellation, and postcondition verification;
- define capability-specific compensation contracts.

### EPIC-002 — ProofGraph local checkpoint verification

**Status at documented baseline:** VERIFIED.

Delivered:

- `voodoo evidence verify`;
- outer manifest and provenance verification;
- Git bundle and source-tree verification;
- source archive comparison without extraction;
- runtime identity consistency checks;
- nested post-manifest mutation warnings;
- deterministic ProofGraph v1 JSON;
- repository-owned frozen-snapshot finalization with fail-closed verification;
- repository-owned runtime candidate capture;
- historical capture→finalize→independent verify closure for
  `main@8a5f36b218c3aa6dce2e4cf771512875f136d839`;
- latest post-merge development checkpoint for
  `main@d57d37111b8bc9471a136b6c618aad8e920f1aff`, with 433 tests, readiness,
  dependency audit, product-image build and recorded smoke gate passed, and production effects
  disabled; checkpoint archive SHA-256
  `80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2`;
- regression coverage, ADR-0002, and ADR-0004.

Next:

- add signed checkpoint attestations;
- add remote byte verification and external anchoring;
- add SBOM and vulnerability-policy nodes.

### EPIC-003 — Product documentation foundation

**Status at documented baseline:** IMPLEMENTED by the documentation-foundation change; verification is repository-local.

Scope:

- project vision;
- current and target architecture;
- current capability inventory;
- target capability map;
- roadmap;
- terminology;
- trust boundaries;
- documentation truth policy;
- documentation index and automated structure checks.

Exit criteria:

- documents are linked from the root README;
- capability status uses the repository taxonomy;
- roadmap does not claim planned work as delivered;
- documentation checks run in CI and product readiness.

### EPIC-004 — Policy Decision Graph

**Status at documented baseline:** VERIFIED for the read-only PDG v1 projection foundation; broader authoritative policy
and runtime enforcement remain PROPOSED.

Accepted foundation: [`ADR-0006`](docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md).
Broader target: [`ADR-0003`](docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md).

Implemented foundation: a pure compatibility evaluator reproduces current environment-based approval requirements and emits deterministic explanations. A default-off runtime compatibility path now consumes that policy owner, preserves current outcomes, and fails closed on evaluator drift; Solo, Team, and Regulated enforcement remain unimplemented.

The accepted read-only PDG v1 slice deterministically projects caller-supplied current facts,
permission observations, approval-policy decisions, approvals, lifecycle/safety state, and optional
evidence references into a canonical graph and digest. It has no persistence, API, execution gate,
runtime authorization authority, or runtime integration. The latest post-merge runtime checkpoint
attests the source tree and development image at
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`; it includes PDG v1 source and tests but does not
prove any broader runtime authority or integration.

The pure deterministic execution-contract value objects accepted in ADR-0007 are a separate
representation layer. They are not the signed grant envelope, isolated runner runtime, or
production mutation boundary.

Goal:

Produce deterministic and explainable authorization decisions from:

```text
principal
+ workspace and target
+ environment
+ risk
+ capability
+ blast radius
+ reversibility
+ artifact digest
+ policy version
= decision and required approvals
```

Exit criteria:

- decision inputs are canonical and versioned;
- matched and missing policy conditions are explicit;
- approvals bind to exact governed inputs;
- drift invalidates prior approval;
- negative-path and replay tests pass.

### EPIC-005 — Isolated Runner Capsules

**Status:** PROPOSED.

Goal:

Move execution behind a durable boundary with:

- one-time signed grants;
- rootless isolated runtime;
- read-only base filesystem;
- capability-scoped workspace;
- CPU, memory, PID, and timeout limits;
- network denied by default;
- heartbeat, lease renewal, cancellation, and fencing;
- structured signed receipts;
- postcondition verification.

Production-changing adapters remain BLOCKED until this epic and its security review are complete.
See the detailed MVP delivery map for the phase-by-phase path from the accepted contract layer to
the proposed runner pilot.

### EPIC-006 — Core read-only knowledge boundary

**Status:** PROPOSED.

First safe slice:

- import normalized metadata and immutable references only;
- no shared database;
- no package-provided execution;
- feature flag off by default;
- audit every intake;
- retain VOODOO One as authorization source of truth.

Future mutation from CyberCore-originated artifacts requires signed publisher identity, exact artifact
binding, runner isolation, and a separate ADR.

### EPIC-007 — Signed supply chain and external evidence anchoring

**Status:** PROPOSED.

Target:

- digest-pinned base images;
- deterministic `linux/amd64` and `linux/arm64` builds;
- SBOM and vulnerability report;
- build provenance;
- image and checkpoint signatures;
- key identity and rotation;
- registry promotion policy;
- external ledger-head anchoring.

### EPIC-008 — AI Change Copilot

**Status:** PROPOSED.

Permitted responsibilities:

- draft structured change requests;
- summarize evidence;
- identify missing preconditions;
- suggest risk and rollback plans;
- explain policy decisions;
- review diffs and verification results.

Prohibited responsibilities:

- approving its own proposal;
- issuing execution grants;
- bypassing policy;
- directly enabling production effects;
- hiding uncertainty or missing evidence.

### EPIC-009 — Enterprise and unrestricted production readiness

**Status:** BLOCKED.

Prerequisites include:

- isolated runner and signed grants;
- signed receipts and evidence anchoring;
- workspace-scoped identity and step-up authentication;
- released PostgreSQL and backup/PITR strategy;
- secrets and tenant key separation;
- observability, SLOs, and incident runbooks;
- penetration testing;
- resolved product license, EULA, privacy, and support model;
- explicit release authorization.

## Immediate priority order

1. specify the execution grant and structured receipt contract;
2. design and implement the isolated runner boundary against the reviewed contracts;
3. implement the read-only CyberCore boundary only after execution contracts are reviewed;
4. keep CyberCore mutation out of scope until artifact binding, isolated execution, and
   postcondition evidence are separately authorized.

## Explicit no-go items

- generic shell execution from user input;
- direct CyberCore apply integration;
- shared VOODOO/CyberCore database;
- production effects enabled by documentation or environment drift;
- silent fallback to unreleased OIDC or PostgreSQL;
- full microservice rewrite without measured need;
- public distribution before licensing is resolved.
