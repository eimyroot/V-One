# V-One / VOODOO One

> **Governed Change Authorization, Execution & Evidence Trust Plane**

V-One governs consequential human- and AI-initiated operations so authority, execution and evidence
remain explicit, bounded and independently verifiable.

Canonical lifecycle target/current component lineage:

```text
ReviewedOperation
→ Approval
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ control-plane GrantConsumptionWitness/v1
→ durable Dispatch
→ ExecutionEpoch / Lease / Fence
→ isolated bounded Runner
→ ExecutionReceipt/v2
→ independent Verifier
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

`ExecutionReceipt != VerificationResult`, and execution success alone never implies `VERIFIED`.

## Current state

| Area | Status |
|---|---|
| Root engineering/governance standard | ADOPTED exact-content standard; live technical state still verified directly |
| Exact live Git identity | Query live Git directly; never self-embed a commit as "current" |
| Current source/runtime evidence | See `CURRENT_PRODUCT_STATE.md`, `docs/product/CURRENT_CAPABILITIES.md`, live Git/CI and retained CASER evidence |
| Local identity, approval and legacy product lifecycle | VERIFIED for current test scope |
| AuthorizationSnapshot + AuthoritativeSnapshotCreator | IMPLEMENTED / tested component layer |
| ExecutionGrant/v2 + durable grant persistence | IMPLEMENTED / tested component layer |
| Control-plane one-time Grant consumption + durable Outbox | IMPLEMENTED / tested component layer |
| Dispatch Inbox/dedup + ExecutionEpoch/Lease | IMPLEMENTED / tested component layer |
| Isolated bounded READ Runner | LIVE VERIFIED in D4b pilot scope |
| Independent Verifier | LIVE VERIFIED in E3 pilot scope |
| VerificationResult/v1 | LIVE VERIFIED in E4b/F6b scopes |
| Bounded GitHub CREATE_REF / DELETE_REF | HISTORICALLY VERIFIED staging pilot scopes |
| ExecutionReceipt/v2 | IMPLEMENTED; historical F6b real receipt evidence |
| OperationProof/v2 | IMPLEMENTED; historical F6b proof VERIFIED |
| OperationCell/v1 | IMPLEMENTED; historical F6b cell VERIFIED |
| Security Intelligence R-SI1.1 | IMPLEMENTED descriptive metadata/test layer; intelligence-only |
| Unified authority→OperationCell FastAPI ProductComposition | PARTIAL / NOT YET COMPOSED |
| GitHub main required-check/ruleset enforcement | UNKNOWN / release-blocking until live settings prove the baseline |
| Production effects | BLOCKED and disabled by default |
| Unrestricted production release | BLOCKED |
| Public commercial distribution | BLOCKED |
| CyberCore integration | BLOCKED until reconciliation and canonical product-pipeline gates pass |

The current product version remains `0.9.0-rc2-dev`; this reconciliation is not a release.

### Historical runtime checkpoint

The latest retained full local runtime-attested development checkpoint remains
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`. Its archive SHA-256 is
`80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2` and recorded product image ID is
`sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc`.
It does **not** attest later source changes; later trees rely on their own commit-bound CI/pilot
evidence.

The current evidence snapshot is [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md), and the
capability-by-capability view is
[`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md).

## Product model

```text
CyberCore / AI agents / operators
        observations, context, proposals
                     |
                     v
               V-One authority
 ReviewedOperation → Approval → AuthorizationSnapshot
                     |
              ExecutionGrant/v2
                     |
      CONTROL PLANE one-time consumption
                     |
              durable Dispatch
                     |
         Epoch / Lease / current Fence
                     |
          isolated bounded Runner
                     |
          ExecutionReceipt/v2
                     |
                     +----------------------+
                                            v
                              independent Verifier READ
                                            |
                                  VerificationResult/v1
                                            |
                                  OperationProof/v2
                                            |
                                   OperationCell/v1
```

V-One owns authority semantics. CyberCore and Security Intelligence may supply context and proposals,
but cannot issue authorization, consume grants, become Runner authority or manufacture verification.

## One canonical language

The canonical machine vocabulary is in `voodoo_product/vop_vocabulary.py` with registry identity in
`schemas/vop/registry.v1.json`; the human projection is
[`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md).

Important boundaries:

```text
Approval != Authorization
AuthorizationSnapshot != ExecutionGrant
ExecutionGrant != ExecutionCapsule
Runner != Verifier
ExecutionReceipt != VerificationResult
VerificationResult != OperationProof
OperationProof != OperationCell
Evidence-chain integrity != independent verification
Release != Deploy
```

Grant consumption belongs to the control plane **before Dispatch**. The Runner executes only an
already-authorized dispatch under current lease/fence state.

## ProductComposition reality

The repository contains the individual authority, durable dispatch, coordination, Runner,
verification, proof and cell components. The current FastAPI `ProductComposition` still preserves the
legacy `ExecutionService` product surface and does not yet orchestrate the full chain as one canonical
runtime/API path.

Therefore:

```text
COMPONENT CHAIN = IMPLEMENTED DEEPLY
HISTORICAL COMPLETE OPERATION ATOM = VERIFIED
ONE CANONICAL PRODUCT RUNTIME PATH = NOT YET IMPLEMENTED
```

The next architecture track is composition/convergence, not reimplementation of the accepted
contracts.

## Historical verified operation atom

Historical F6b run `32213563750` records one bounded staging rollback operation with:

- exact `DELETE_REF` target;
- provider mutation count `1`;
- no automatic retry;
- rollback true;
- Runner and independent Verifier observed `ABSENT`;
- `VerificationResult/v1 = VERIFIED / OBSERVED_STATE_MATCH`;
- `OperationProof/v2 = 40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718`;
- `OperationCell/v1 = 2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5`.

This is real historical evidence, not a claim that every current API execution automatically produces
a cell.

## Common system members

`voodoo_product/operation_semantics.py` defines one common-language membership model:

- owner;
- operator;
- AI agent;
- CyberCore;
- policy engine;
- approval quorum;
- Runner;
- Verifier;
- evidence fabric.

The Runner authority is bounded execution only. CyberCore is intelligence only. The Verifier owns
independent verification evidence, not execution authority.

## Current security posture

- production effects default disabled;
- exact authority/target/capsule/dispatch/epoch/fence bindings in current trust-plane contracts;
- immutable/checksum-governed SQLite migrations through schema 13;
- one-time grant-consumption evidence in the control plane;
- bounded isolated pilot runtimes with default-deny network policy demonstrated in scoped workflows;
- separate independent verifier path;
- receipt and verification semantics separated;
- no release/deployment inferred from CI, merge, Proof or Cell;
- live GitHub main enforcement remains UNKNOWN until settings/ruleset evidence proves the repository
  baseline.

## Documentation

| Document | Purpose |
|---|---|
| [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) | Current evidence-scoped product snapshot |
| [`CHANGELOG.md`](CHANGELOG.md) | Human-readable product-history changes |
| [`VISION.md`](VISION.md) | Product purpose and long-term direction |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Current architecture and convergence target |
| [`ROADMAP.md`](ROADMAP.md) | Ordered delivery/gate plan |
| [`SECURITY.md`](SECURITY.md) | Security policy and supported-state boundaries |
| [`foundation/FOUNDATIONS.md`](foundation/FOUNDATIONS.md) | Stable product/engineering foundations |
| [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md) | Shared vocabulary and status taxonomy |
| [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) | Evidence-backed current capability inventory |
| [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md) | Target capability contracts |
| [`docs/product/SECURITY_OVERVIEW.md`](docs/product/SECURITY_OVERVIEW.md) | Current security-control summary |
| [`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md) | Historical/product MVP delivery map |
| [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md) | Current trust-boundary topology |
| [`docs/governance/DOCUMENTATION_POLICY.md`](docs/governance/DOCUMENTATION_POLICY.md) | Documentation truth rules |
| [`docs/governance/ADR0008_R3_EVIDENCE_INDEX.md`](docs/governance/ADR0008_R3_EVIDENCE_INDEX.md) | Immutable historical R3 evidence index |
| [`docs/README.md`](docs/README.md) | Documentation index |

Normative governance remains in
[`WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`](WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md),
[`PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md), and effective adopted governance records/ADRs.

## Local verification

From repository root:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m ruff check .
python -m compileall -q voodoo_product scripts tests
python -m pytest -q
python scripts/product_readiness_gate.py
```

No command above enables production effects.

## Local checkpoint evidence verification

```bash
export PATH="$PWD/scripts:$PATH"
voodoo evidence verify /absolute/path/to/checkpoint
```

Equivalent:

```bash
python -m voodoo_product evidence verify /absolute/path/to/checkpoint
```

Checkpoint verification does not independently attest provider state, publish artifacts, authorize a
release or enable production effects.

See [`ADR-0002`](docs/adr/ADR-0002-local-checkpoint-proofgraph-verification.md).

## Local start

Create `.env.product.local` from `.env.product.example`, replace secret placeholders, set exact
`VOODOO_TRUSTED_HOSTS`, and keep:

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
```

Then:

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/uvicorn voodoo_product.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-server-header
```

Console: `http://127.0.0.1:8000/console`

## Change governance

- focused reviewable commits;
- behavior changes include tests;
- CI is not release/deploy authority;
- production effects remain disabled unless separately authorized/released;
- authentication, authorization, persistence, evidence, write, release and production changes use
  governed review;
- automation may propose/verify but cannot create stronger authority by inference.

See [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and
[`COMMERCIAL_READINESS.md`](docs/product/COMMERCIAL_READINESS.md).
