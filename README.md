# V-One / VOODOO One

> **Governed Change Authorization, Execution & Evidence Trust Plane**

V-One keeps consequential human- and AI-initiated operations explicit, bounded and independently
verifiable. It owns authority semantics; provider/runtime details remain behind governed boundaries.

## Canonical model

All current operations share the authority/execution prefix:

```text
ReviewedOperation
→ Approval
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ control-plane GrantConsumptionWitness/v1
→ durable Dispatch
→ ExecutionEpoch / Lease / Fence
→ isolated bounded Runner
→ provider effect / observation
```

The evidence tail is **profile-specific**, not universal:

```text
READ_ONLY_VERIFIED
→ independent Verifier
→ VerificationResult/v1

BOUNDED_MUTATION_VERIFIED
→ ExecutionReceipt/v2                 [effect claim, NOT verification]
→ independent Verifier
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

`ExecutionReceipt/v2` and `OperationProof/v2` are bounded-mutation contracts. READ-only verification
currently terminates at `VerificationResult/v1`.

```text
ExecutionReceipt != VerificationResult
execution succeeded != VERIFIED
VerificationResult != OperationProof
OperationProof != OperationCell
```

## Current state

| Area | Status |
|---|---|
| Root engineering/governance standard | ADOPTED exact-content standard |
| Exact live Git identity | Query live Git directly; never self-embed a commit as "current" |
| Current source/runtime evidence | See current-state/capabilities plus live Git/CI/CASER evidence |
| Local identity, approval and legacy product lifecycle | VERIFIED current test scope |
| AuthoritativeSnapshotCreator | IMPLEMENTED / tested |
| ExecutionGrant/v2 + durable grant service | IMPLEMENTED / tested |
| Control-plane grant consumption + Outbox | IMPLEMENTED / tested |
| Inbox/dedup + Epoch/Lease/Coordinator | IMPLEMENTED / tested |
| Isolated bounded READ Runner | LIVE VERIFIED D4b scope |
| Independent Verifier + VerificationResult/v1 | LIVE VERIFIED E3/E4b/F6b scope |
| Bounded GitHub CREATE_REF / DELETE_REF | HISTORICALLY VERIFIED staging scopes |
| ExecutionReceipt/v2 | IMPLEMENTED bounded-mutation contract; F6b evidence |
| OperationProof/v2 | IMPLEMENTED bounded-mutation proof; F6b VERIFIED |
| OperationCell/v1 | IMPLEMENTED bounded-mutation atom; F6b VERIFIED |
| Security Intelligence R-SI1.1 | IMPLEMENTED intelligence-only metadata/test layer |
| VOP semantic revision R2 | CURRENT / MERGED via PR #128 |
| Canonical FastAPI ProductComposition runtime seam | IMPLEMENTED / MERGED; explicit runtime factory required, default provider pack disabled |
| Canonical public READ operation API | IMPLEMENTED / MERGED via PR #137; reconciled with resume/runtime via PR #140 |
| Restart-safe durable READ resume | IMPLEMENTED / MERGED via PR #140 |
| GitHub main governance enforcement | VERIFIED / G0 PASS from retained live verifier evidence |
| Default provider runtime pack | BLOCKED / disabled until G8 |
| Real canonical HTTP READ E2E through default G8 pack | BLOCKED / not yet verified |
| Provider WRITE activation | BLOCKED pending repeated READ E2E + restart-safe verification gate |
| Production effects | BLOCKED / disabled by default |
| Unrestricted production release | BLOCKED |
| Public commercial distribution | BLOCKED |
| CyberCore integration | BLOCKED pending product/release-governance hardening |

Product version remains `0.9.0-rc2-dev`; G7 reconciliation is not release/deploy.

### Historical runtime checkpoint

Latest retained full local runtime-attested development checkpoint:

```text
main@d57d37111b8bc9471a136b6c618aad8e920f1aff
archive SHA-256: 80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2
image ID: sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
```

It does not attest later source changes.

Current product truth:
[`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) and
[`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md).

## One canonical language

Machine authority:

- `voodoo_product/vop_vocabulary.py`;
- `schemas/vop/registry.v1.json`.

Human projection:
[`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md).

Current semantic revision is `vop-terminology-freeze-r2` (ADR-0018). R2 makes the lifecycle
stage list an ordered superset and registers explicit terminal profiles/compatibility. It deliberately
does **not** call Receipt/v2 or Proof/v2 universal supersessions of the older v1 families.

Important boundaries:

```text
Approval != Authorization
AuthorizationSnapshot != ExecutionGrant
ExecutionGrant != ExecutionCapsule
Runner != Verifier
ExecutionReceipt != VerificationResult
Observation != VerificationResult
VerificationResult != OperationProof
OperationProof != OperationCell
Evidence-chain integrity != independent verification
Release != Deploy
```

Grant consumption belongs to the control plane **before Dispatch**. Runner authority is
`bounded_execution_only`.

## ProductComposition reality

The repository contains the accepted authority, durable dispatch, coordination, Runner, verifier and
bounded-mutation proof/cell components. Merged PR #128 established the canonical trust-plane runtime
as a `ProductComposition` seam: an explicit runtime factory must share the exact ProductService database
and `DatabasePermissionAuthority`, and the default application intentionally leaves the provider
runtime pack absent/fail-closed.

PR #137 merged the canonical READ HTTP surface. PR #140 reconciled that surface with restart-safe
durable resume and runtime resume wiring, without adding a provider WRITE route or default provider
runtime pack.

```text
COMPONENT COVERAGE = STRONG
HISTORICAL BOUNDED-MUTATION ATOM = VERIFIED
CANONICAL PRODUCT RUNTIME SEAM = IMPLEMENTED / MERGED
CANONICAL PUBLIC READ API = IMPLEMENTED / MERGED
RESTART-SAFE DURABLE RESUME = IMPLEMENTED / MERGED
DEFAULT PROVIDER RUNTIME PACK = DISABLED / FAIL-CLOSED
REAL DEFAULT-RUNTIME HTTP READ E2E = NOT VERIFIED
PROVIDER WRITE = BLOCKED
```

Legacy `ExecutionService` remains an explicit compatibility surface and is not canonical fallback
authority. Public READ API availability does not imply provider runtime activation, provider mutation,
deployment, or release.

## G0 governance evidence

The former GitHub-governance blocker is closed by retained live verifier evidence, not by documentation
or ordinary CI inference:

```text
workflow = g0-governance-verify
run = 32553113424
source_sha = 76d74d2ed62b6e78f027728c456c22da0b4a95bd
artifact = g0-governance-evidence-32553113424-1
artifact_digest = sha256:6e63caee23a57613471df66ef0279c0261ed8d375e4c929accdf50eff7dc4f5f
verdict = VERIFIED
```

This evidence established the G0 PASS controls in the current-state documents. G0 PASS remains separate
from provider runtime, release, and deployment authorization.

## READ before WRITE

The next governed direction is a READ-only G8 runtime pack followed by repeated real canonical HTTP
READ E2E and restart/resume verification. Provider WRITE remains blocked unless the adopted safety gate
is satisfied with evidence for READ E2E, restart continuity, no duplicate authority/effect, independent
verification, and fail-closed behavior. Even then, `ELIGIBLE` would not itself authorize a WRITE effect.

Execution success remains distinct from independent verification:

```text
execution.status      = SUCCEEDED
verification.verdict  = NOT_VERIFIED
```

is truthful and must not be promoted to `VERIFIED` by execution success, receipts, or hash integrity.

## Historical verified bounded-mutation atom

F6b run `32213563750` proved one staging rollback operation:

- `DELETE_REF` exactly once;
- mutation count `1`;
- automatic retry `false`;
- rollback `true`;
- Runner and independent Verifier observed `ABSENT`;
- `VerificationResult/v1 = VERIFIED / OBSERVED_STATE_MATCH`;
- `OperationProof/v2 = 40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718`;
- `OperationCell/v1 = 2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5`.

This is real bounded-mutation evidence, not evidence that every READ produces Proof/v2/Cell/v1 or that
a new provider mutation is authorized.

## Security posture

- production effects default disabled;
- one-time grant consumption in control plane;
- exact current user/global-role/workspace/environment/membership permission revalidation before durable grant store/consume;
- exact target/capsule/dispatch/epoch/fence bindings in current contracts;
- SQLite migrations through schema 14;
- bounded isolated pilot runtimes;
- separate independent verifier path;
- receipt/verification semantics separate;
- canonical public READ API and restart-safe resume are merged;
- default G8 provider runtime and real product HTTP READ E2E remain blocked/unverified;
- provider WRITE remains blocked behind READ-before-WRITE evidence and separate effect authorization;
- no release/deployment inferred from CI, merge, Proof or Cell;
- GitHub main governance enforcement has retained live G0 VERIFIED evidence.

## Documentation

| Document | Purpose |
|---|---|
| [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md) | Current evidence-scoped product snapshot |
| [`CHANGELOG.md`](CHANGELOG.md) | Product/history changes |
| [`VISION.md`](VISION.md) | Product purpose and direction |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Current architecture and composition target |
| [`ROADMAP.md`](ROADMAP.md) | Ordered delivery/gate plan |
| [`SECURITY.md`](SECURITY.md) | Security policy/supported-state boundary |
| [`foundation/FOUNDATIONS.md`](foundation/FOUNDATIONS.md) | Stable engineering foundations |
| [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md) | Shared terminology/status language |
| [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md) | Current capability inventory |
| [`docs/product/POST_G7_CANONICAL_STATE.md`](docs/product/POST_G7_CANONICAL_STATE.md) | Commit-bound post-G7 truth snapshot |
| [`docs/product/G8_READ_RUNTIME_GATE.md`](docs/product/G8_READ_RUNTIME_GATE.md) | G8 READ-only runtime acceptance boundary |
| [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md) | Target capability contracts |
| [`docs/product/SECURITY_OVERVIEW.md`](docs/product/SECURITY_OVERVIEW.md) | Security-control summary |
| [`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md) | MVP/product delivery map |
| [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md) | Trust-boundary topology |
| [`docs/governance/DOCUMENTATION_POLICY.md`](docs/governance/DOCUMENTATION_POLICY.md) | Documentation truth rules |
| [`docs/governance/ADR0008_R3_EVIDENCE_INDEX.md`](docs/governance/ADR0008_R3_EVIDENCE_INDEX.md) | Historical R3 evidence index |
| [`docs/README.md`](docs/README.md) | Documentation index |

Normative governance remains in
[`WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`](WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md),
[`PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md), and effective adopted records/ADRs. ADR-0019
remains `PROPOSED` until its governed adoption gate closes.

## Local verification

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

## Local checkpoint verification

```bash
export PATH="$PWD/scripts:$PATH"
voodoo evidence verify /absolute/path/to/checkpoint
```

Equivalent:

```bash
python -m voodoo_product evidence verify /absolute/path/to/checkpoint
```

Checkpoint verification does not independently attest provider state, publish artifacts, authorize a
release or enable production effects. See
[`ADR-0002`](docs/adr/ADR-0002-local-checkpoint-proofgraph-verification.md).

## Local start

Create `.env.product.local` from `.env.product.example`, replace secret placeholders, configure exact
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
- production effects remain separately authorized/released;
- authentication/authority/persistence/evidence/write/release changes use governed review;
- automation cannot create stronger authority by inference.

See [`SECURITY.md`](SECURITY.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and
[`COMMERCIAL_READINESS.md`](docs/product/COMMERCIAL_READINESS.md).
