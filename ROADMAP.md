# VOODOO One Roadmap

| Field | Value |
|---|---|
| Document status | Living delivery plan |
| Source of current capability truth | `docs/product/CURRENT_CAPABILITIES.md` |
| Production status | BLOCKED until an explicit governed release |
| Update rule | Update with every accepted milestone or material scope change |

## Status vocabulary

- **VERIFIED** — supported by current repository evidence and executed verification;
- **IMPLEMENTED** — exists in the current code or documentation but has not met every stated
  verification scope;
- **PROPOSED** — accepted direction without implementation;
- **INFERRED** — derived from evidence but not directly demonstrated;
- **UNKNOWN** — evidence is unavailable;
- **BLOCKED** — intentionally unavailable or unsafe to activate.

## Program sequence

### EPIC-000 — Governed control-plane foundation

**Status:** VERIFIED for the development and controlled-pilot scope.

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

**Status:** VERIFIED for the current local adapter scope.

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

**Status:** VERIFIED.

Delivered:

- `voodoo evidence verify`;
- outer manifest and provenance verification;
- Git bundle and source-tree verification;
- source archive comparison without extraction;
- runtime identity consistency checks;
- nested post-manifest mutation warnings;
- deterministic ProofGraph v1 JSON;
- regression coverage and ADR-0002.

Next:

- fix evidence producers so logs are frozen before nested manifests;
- add signed checkpoint attestations;
- add remote byte verification and external anchoring;
- add SBOM and vulnerability-policy nodes.

### EPIC-003 — Product documentation foundation

**Status:** IMPLEMENTED by the documentation-foundation change; verification is repository-local.

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

**Status:** PROPOSED.

Design reference: [`ADR-0003`](docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md).

Implemented foundation: a pure compatibility evaluator reproduces current environment-based approval requirements and emits deterministic explanations. A default-off runtime compatibility path now consumes that policy owner, preserves current outcomes, and fails closed on evaluator drift; Solo, Team, and Regulated enforcement remain unimplemented.

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

### EPIC-006 — CyberCore read-only knowledge boundary

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

1. preserve a fresh runtime-verified checkpoint for the current committed HEAD;
2. complete the documentation foundation and keep it evidence-aligned;
3. remove the evidence-producer post-manifest log mutation;
4. specify Policy Decision Graph v1;
5. specify isolated runner grant and receipt contracts;
6. implement the read-only CyberCore boundary only after those contracts are reviewed.

## Explicit no-go items

- generic shell execution from user input;
- direct CyberCore apply integration;
- shared VOODOO/CyberCore database;
- production effects enabled by documentation or environment drift;
- silent fallback to unreleased OIDC or PostgreSQL;
- full microservice rewrite without measured need;
- public distribution before licensing is resolved.
