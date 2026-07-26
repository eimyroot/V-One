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
| Development control-plane baseline | VERIFIED |
| Local identity, approvals, execution lifecycle, audit, and receipts | VERIFIED |
| Local checkpoint ProofGraph verifier | VERIFIED |
| Production effects | BLOCKED and disabled by default |
| Isolated execution runner | PROPOSED |
| Unrestricted production release | BLOCKED |
| Public commercial distribution | BLOCKED pending licensing |

The current product version is `0.9.0-rc2-dev`. The repository is suitable for local integration,
verification, and controlled pilot hardening. It is not an unrestricted production release.

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
Isolated Runner (target)
  bounded action -> postcondition verification -> signed receipt
```

VOODOO One is the authorization system. CyberCore may become a separate system of understanding.
Execution is intended to move into an isolated runner. ProofGraph connects the resulting evidence.

## Documentation

| Document | Purpose |
|---|---|
| [`VISION.md`](VISION.md) | Product purpose, long-term direction, and non-goals |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Current architecture and target evolution |
| [`ROADMAP.md`](ROADMAP.md) | Ordered delivery plan and milestone states |
| [`foundation/FOUNDATIONS.md`](foundation/FOUNDATIONS.md) | Stable product and engineering foundations |
| [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md) | Shared vocabulary and status taxonomy |
| [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) | Evidence-backed current capability inventory |
| [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md) | Target capability contracts and acceptance criteria |
| [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md) | Current and target trust boundaries |
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
- local checkpoint verification and deterministic ProofGraph v1 JSON;
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
