# V-One / VOODOO One

> **Governed Change Authorization & Evidence Control Plane**

VOODOO One governs the flow:

```text
change request
  -> independent approval
  -> controlled execution
  -> evidence
```

It is designed for human- and AI-initiated change where identity, policy, approval, execution
lifecycle, recovery, and verifiable evidence must remain explicit.

## Current state

| Area | Status |
|---|---|
| Root agent governance | IMPLEMENTED in repository source |
| Current source/runtime identity | See `CURRENT_PRODUCT_STATE.md` and live Git state |
| Current verified Git baseline | VERIFIED at `main@57c7bf2277616c4445039865ac7cf81c5fada858` |
| Local identity, approvals, execution lifecycle, audit, and receipts | VERIFIED |
| ADR-0007 pure execution-contract value objects | VERIFIED source/test scope; deterministic representation only |
| Local checkpoint ProofGraph verifier | VERIFIED |
| Repository-owned checkpoint finalizer | VERIFIED |
| Latest runtime-attested committed baseline | VERIFIED for `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` post-merge development checkpoint |
| ADR-0008 lifecycle-semantics review | MERGED through PR #54 at `main@57c7bf2277616c4445039865ac7cf81c5fada858`; design remains PROPOSED |
| Read-only Policy Decision Graph v1 | VERIFIED deterministic projection/test scope; no runtime authority or integration |
| Isolated execution runner | PROPOSED |
| Production effects | BLOCKED and disabled by default |
| Unrestricted production release | BLOCKED |
| Public commercial distribution | BLOCKED pending licensing |

The current product version is `0.9.0-rc2-dev`. Exact repository identity is obtained from live Git,
not from this README. The latest verified Git baseline is
`main@57c7bf2277616c4445039865ac7cf81c5fada858`; the latest runtime-attested baseline remains
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`. That runtime checkpoint is classified
`IMPLEMENTED_VERIFIED_LOCAL_POST_MERGE_CHECKPOINT`: 433 tests passed, product readiness passed,
the dependency audit reported no known vulnerabilities, the product image built and passed its
recorded smoke gate, and production effects remained disabled. The checkpoint archive SHA-256 is
`80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2`; the recorded image ID is
`sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc`.
That checkpoint does not attest the later review commit `0fa69411...`, its PR #54 merge commit
`57c7bf22...`, this documentation/MVP patch, a release, deployment, or production operation. The implementation is suitable for local
integration, verification, and controlled pilot hardening. It is not an unrestricted production
release.

The latest exact evidence snapshot, including what works, current limitations, and the next safe step,
is maintained in [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md).

## Product model

```text
CyberCore or another intelligence source
  observations -> knowledge -> proposal
                         |
                         v
VOODOO One
  identity -> policy -> approvals -> execution lifecycle -> evidence
                         |
                         v
ADR-0007 pure execution contracts
  deterministic target / approval-evidence / grant / receipt values
                         |
                         v
Isolated Runner (target)
  bounded action -> postcondition verification -> bounded receipt and evidence
```

VOODOO One is the authorization system. CyberCore may become a separate system of understanding.
Execution is intended to move into an isolated runner. The pure deterministic execution-contract
layer is already accepted as source/test-verified representation in ADR-0007; the isolated Runner
runtime remains proposed. ProofGraph connects the resulting evidence.

## Documentation

| Document | Purpose |
|---|---|
| [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) | Exact current evidence snapshot and next safe step |
| [`CHANGELOG.md`](CHANGELOG.md) | Human-readable record of documentation and product-history changes |
| [`VISION.md`](VISION.md) | Product purpose, long-term direction, and non-goals |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Current architecture and target evolution |
| [`ROADMAP.md`](ROADMAP.md) | Ordered delivery plan and milestone states |
| [`SECURITY.md`](SECURITY.md) | Security policy and supported-state boundaries |
| [`foundation/FOUNDATIONS.md`](foundation/FOUNDATIONS.md) | Stable product and engineering foundations |
| [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md) | Shared vocabulary and status taxonomy |
| [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) | Evidence-backed current capability inventory |
| [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md) | Target capability contracts and acceptance criteria |
| [`docs/product/SECURITY_OVERVIEW.md`](docs/product/SECURITY_OVERVIEW.md) | Product security control summary and proposed Runner boundary |
| [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md) | Current and target trust boundaries |
| [`docs/governance/ADR0008_R3_EVIDENCE_INDEX.md`](docs/governance/ADR0008_R3_EVIDENCE_INDEX.md) | Immutable R3 evidence index and digest map |
| [`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md) | Product-delivery map and MVP phase status |
| [`docs/governance/DOCUMENTATION_POLICY.md`](docs/governance/DOCUMENTATION_POLICY.md) | Rules preventing documentation from outrunning reality |
| [`docs/README.md`](docs/README.md) | Documentation index |

Normative governance remains in
[`WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`](WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md),
[`PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md), and accepted ADRs.

## Current verified capabilities

The current implementation includes:

- FastAPI `/api/v1` control plane and static command-center console;
- local bootstrap, login, session allowlist, logout, and administrative revocation;
- RBAC, workspaces, change requests, independent approvals, and execution lifecycle;
- emergency stop, execution idempotency, leases, fencing, and indeterminate recovery;
- checksum-verified SQLite migrations and reviewed SQL statement catalog;
- audit and receipt ledgers with independent integrity verification;
- bounded local adapters with governed sandbox filesystem effects;
- local checkpoint verification, deterministic ProofGraph v1 JSON, and repository-owned checkpoint finalization;
- ADR-0007 pure execution-contract value objects with deterministic digests and cross-contract binding tests;
- read-only deterministic Policy Decision Graph v1 projection with no authorization or execution authority;
- hash-locked dependencies, CI, Docker build, smoke, and readiness gates.

See the scoped evidence and limitations in
[`CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md).

## Local verification

Working directory: repository root.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m ruff check .
python -m compileall -q voodoo_product scripts tests
python -m pytest -q
python scripts/product_readiness_gate.py
```

## Local checkpoint evidence verification

```bash
export PATH="$PWD/scripts:$PATH"
voodoo evidence verify /absolute/path/to/checkpoint
```

Equivalent module command:

```bash
python -m voodoo_product evidence verify /absolute/path/to/checkpoint
```

The verifier emits JSON and exits non-zero when required checkpoint evidence is inconsistent. It does
not verify remote Drive bytes, contact Docker, publish artifacts, authorize a release, or enable
production effects.

See [`ADR-0002`](docs/adr/ADR-0002-local-checkpoint-proofgraph-verification.md).

## Local start

Create `.env.product.local` from `.env.product.example`, replace both secret placeholders with
cryptographically random values, set `VOODOO_TRUSTED_HOSTS` to the exact accepted hostnames, and keep
`VOODOO_ALLOW_PRODUCTION_EFFECTS=false`.

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/uvicorn voodoo_product.main:app   --host 127.0.0.1   --port 8000   --no-access-log   --no-server-header
```

Console: `http://127.0.0.1:8000/console`

## Change governance

- changes use focused, reviewable commits;
- production effects remain disabled;
- behavior changes include tests;
- CI is read-only;
- authentication, authorization, persistence, evidence, release, and production changes require
  explicit owner review;
- automation may propose and verify but may not self-approve R2-R4 changes.

See [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and
[`COMMERCIAL_READINESS.md`](docs/product/COMMERCIAL_READINESS.md).
