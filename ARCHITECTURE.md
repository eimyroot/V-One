# VOODOO One Architecture

| Field | Value |
|---|---|
| Document status | Accepted descriptive architecture / reconciled current-state view |
| Reconciled | `2026-08-20` against `main@71a931b561faa93c8dd2e062b83559401143b1df` |
| Current product packaging | Modular monolith plus separately exercised isolated pilot runtimes |
| Current composition state | Trust-plane components exist; one canonical FastAPI lifecycle is still partial |
| Normative authority | Subordinate to engineering governance and effective adopted ADRs |
| Production effects | BLOCKED / disabled by default |

## Architectural purpose

V-One owns governance and authority semantics for consequential operations:

- identity and reviewed intent;
- policy/approval evidence;
- immutable authorization snapshot;
- narrow execution grant;
- durable one-time grant consumption in the control plane;
- dispatch/coordination/fencing;
- bounded execution;
- execution receipt;
- independent post-state verification;
- portable proof and stable operation cell.

It does not turn intelligence, transport or evidence integrity into authority by inference.

## Current system context

```text
Operator / AI proposal / CyberCore intelligence
                    |
                    v
             FastAPI product boundary
                    |
        +-----------+-----------+
        |                       |
        v                       v
legacy composed product    current VOP trust-plane
request/approval/           contracts + durable services
ExecutionService                    |
        |                           v
        |                  AuthorizationSnapshot
        |                  → ExecutionGrant/v2
        |                  → control-plane consumption
        |                  → Outbox / Envelope / Inbox
        |                  → Epoch / Lease / Fence
        |                  → Capsule / RunnerBoundary
        |                           |
        |                    isolated bounded Runner
        |                           |
        |                    ExecutionReceipt/v2
        |                           |
        |                    independent Verifier
        |                           |
        |                    VerificationResult/v1
        |                           |
        |                    OperationProof/v2
        |                           |
        |                    OperationCell/v1
        |
        +---- current product-composition convergence still required ----+

SQLite persistence: migrations 0001–0013
```

The repository therefore has deep trust-plane implementation without yet having one exclusive product
runtime path through every layer.

## Current components

### HTTP / product surface

- FastAPI `/api/v1` application;
- local authentication/session/RBAC/workspaces/change requests/approvals;
- static console;
- emergency stop, evidence and health surfaces;
- current composition preserves legacy `ExecutionService` behavior.

The Evidence UI must distinguish ledger integrity from independent provider verification. Receipt
existence or hash-chain validity is not operation `VERIFIED` evidence.

### Canonical VOP language

Machine authority:

- `voodoo_product/vop_vocabulary.py`;
- `schemas/vop/registry.v1.json`.

Current lifecycle vocabulary includes `OperationProof/v2` and `OperationCell/v1` while preserving
historical schema identities. Provider vocabulary stays behind module/transport boundaries.

### Authority layer

Implemented/tested component contracts include:

```text
ReviewedOperation / approval evidence
→ AuthorizationSnapshot
→ AuthoritativeSnapshotCreator
→ ExecutionGrant/v2
→ durable Grant persistence
→ GrantConsumptionWitness/v1
```

One-time Grant consumption belongs to the **control plane before Dispatch**. Runner admission does not
consume the Grant again and does not create another authorization lineage.

### Durable dispatch and coordination

Implemented/tested component chain:

```text
GrantConsumptionWitness
+ DispatchOutboxEntry/v1
→ DispatchEnvelope/v1
→ DispatchInboxAdmission/v1
→ ExecutionEpoch + ExecutionLease/v1
→ DurableCoordinator / CurrentExecutionFence
```

Migrations 0010–0013 persist the current grant/dispatch/coordination state on the released SQLite
backend.

### Runner boundary

Current source contains RunnerIdentity, RunnerBoundary, credential-decision, runtime-activation,
read-provider and write-boundary components. Bounded isolated GitHub READ execution has real D4b pilot
evidence, and E3/E4b repeat the Runner side as part of independent-verification pilots.

Canonical Runner authority:

```text
bounded_execution_only
```

The Runner:

- executes an already-authorized dispatch;
- is bound to exact capsule/capability/target/epoch/lease/fence inputs as required by the active path;
- does not issue authorization;
- does not issue or consume ExecutionGrants;
- does not become the independent Verifier.

The legacy in-process `ExecutionService` adapter path still exists in ProductComposition. That
compatibility/product boundary must not be confused with the isolated pilot execution plane.

### Provider effect / receipt

Historical F4b/F6b staging pilots exercised bounded GitHub write/rollback paths. Historical F6b
records exactly one `DELETE_REF` mutation, no automatic retry and rollback true.

`ExecutionReceipt/v2` is the execution subsystem claim. It is not independent verification and keeps
verification semantics separate.

### Independent verification

Current components/pilots provide:

```text
Runner observation
+ separate VerifierIdentity
+ IndependentVerificationBoundary
+ read-only verifier credential decision
+ verifier observation
→ ObservedPostState/v1
→ VerificationStrength/v1
→ VerificationResult/v1
```

D4b/E3/E4b provide bounded live GitHub READ/verification evidence. The Verifier is separate from the
Runner and cannot mutate provider state in the accepted readback path.

### Proof and stable operation atom

`OperationProof/v2` canonically revalidates current receipt + independent-verification lineage before
creating a portable proof.

`OperationCell/v1` freezes a minimal provider/lineage-neutral identity over a canonically revalidated
proof:

```text
VerificationResult != OperationProof
OperationProof != OperationCell
OperationCell != authority
```

Historical F6b retained evidence produced:

```text
OperationProof/v2 digest
40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718

OperationCell/v1 digest
2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5
```

### Security Intelligence

R-SI1.1 is an implemented descriptive metadata/test layer. It may classify and carry intelligence,
but does not create VOP authority or a parallel capability model.

### Persistence

Released backend: SQLite.

- checksum-verified immutable migration history;
- central statement catalog;
- audit/receipt ledgers;
- AuthorizationSnapshot persistence;
- durable ExecutionGrant/consumption;
- dispatch Outbox/Inbox;
- ExecutionEpoch/Lease state;
- schema version 13.

PostgreSQL remains unreleased/fail closed.

### Historical runtime checkpoint

The latest retained full local development runtime checkpoint remains
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff` with archive SHA-256
`80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2` and image ID
`sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc`.

It is historical evidence only and does not attest later source trees.

## Current data-flow classes

There are presently two distinct realities that must converge rather than be conflated.

### Existing product-composed compatibility path

```text
authenticated principal
→ workspace/change request
→ approval
→ legacy execution eligibility
→ ExecutionService adapter
→ legacy receipt/audit surface
```

### Current VOP component/pilot path

```text
ReviewedOperation
→ Approval
→ AuthorizationSnapshot
→ ExecutionGrant/v2
→ CONTROL-PLANE GrantConsumptionWitness
→ durable Dispatch
→ Epoch / Lease / Fence
→ Capsule / RunnerBoundary
→ bounded Runner effect/observation
→ ExecutionReceipt/v2
→ independent Verifier
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

The next major engineering objective is one canonical ProductComposition/API lifecycle that reuses the
second chain without silently breaking the currently supported product surface.

## Architectural invariants

1. Exact reviewed content is bound before downstream authority is created.
2. Approval is not Authorization.
3. AuthorizationSnapshot is not ExecutionGrant.
4. Grant consumption occurs durably in the control plane before Dispatch.
5. Dispatch, ExecutionEpoch and ExecutionLease coordinate work but do not create new authority.
6. Runner does not issue/consume Grants and cannot self-authorize.
7. Current fence/lease state prevents stale attempts from completing as current.
8. ExecutionReceipt is not independent VerificationResult.
9. Runner and Verifier remain identity/credential/instance separated as required by the active path.
10. Proof creation requires canonical verification provenance, not a self-consistent `VERIFIED` object.
11. OperationCell does not widen authority or duplicate lower evidence.
12. Evidence-chain integrity is not independent provider verification.
13. Unreleased persistence/identity/provider paths fail closed.
14. Production effects remain disabled until a separate release/effect gate.
15. Documentation never upgrades implementation, verification, release or deployment state by wording.

## Trust boundaries

Detailed current boundaries are maintained in
[`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md).

The principal current architectural gap is not missing low-level contracts. It is the boundary between
legacy ProductComposition and the already-implemented VOP lifecycle components.

## Canonical ProductComposition target

```text
FastAPI / governed operation entry
        ↓
review + approval
        ↓
AuthorizationSnapshot
        ↓
ExecutionGrant/v2
        ↓
control-plane consume + durable dispatch
        ↓
current epoch/lease/fence
        ↓
isolated bounded Runner
        ↓
ExecutionReceipt/v2
        ↓
independent Verifier
        ↓
VerificationResult/v1
        ↓
OperationProof/v2
        ↓
OperationCell/v1
```

Migration rules:

- reuse accepted components instead of creating a parallel v3 authority path;
- introduce composition behind explicit interfaces and tests;
- preserve supported legacy API behavior until replacement evidence exists;
- do not automatically turn historical PR-specific write workflows into product runtime;
- provider effect activation remains a separate authorization boundary.

## GitHub governance boundary

Repository policy requires PR-only main, latest-head `ci / verify`, no force push/delete and
conversation resolution. Available connector evidence does not expose/prove the complete modern
ruleset. Classic required-status enforcement is observed off, so GitHub enforcement remains
`UNKNOWN / BLOCKED` rather than inferred from repository documents or successful CI.

## CyberCore boundary

CyberCore may provide observations, context, learning signals and proposals.

```text
CyberCore = intelligence_only
CyberCore != Authorization
CyberCore != ExecutionGrant issuer
CyberCore != Runner
CyberCore != Verifier
```

Initial integration remains blocked until reconciliation and the canonical ProductComposition
lifecycle are complete. No shared persistence or package-provided arbitrary shell execution is
implicitly accepted.

## Evolution rules

- converge semantic epochs before adding another intelligence subsystem;
- preserve one authority lineage;
- keep provider language behind Modules;
- keep Receipt and independent Verification distinct;
- keep production effects blocked by default;
- preserve historical evidence/contracts instead of rewriting their meaning;
- add new provider/capability paths by translating into VOP, not by cloning governance logic;
- scale persistence only after authority/runtime semantics are stable.

## Related documents

- [`VISION.md`](VISION.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`CURRENT_PRODUCT_STATE.md`](CURRENT_PRODUCT_STATE.md)
- [`foundation/FOUNDATIONS.md`](foundation/FOUNDATIONS.md)
- [`foundation/TERMINOLOGY.md`](foundation/TERMINOLOGY.md)
- [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)
- [`docs/product/TARGET_CAPABILITIES.md`](docs/product/TARGET_CAPABILITIES.md)
- [`docs/architecture/TRUST_BOUNDARIES.md`](docs/architecture/TRUST_BOUNDARIES.md)
- [`docs/architecture/VOP_CANONICAL_VOCABULARY.md`](docs/architecture/VOP_CANONICAL_VOCABULARY.md)
- [`docs/governance/ADR0008_R3_EVIDENCE_INDEX.md`](docs/governance/ADR0008_R3_EVIDENCE_INDEX.md)
- [`docs/product/MVP_DELIVERY_MAP.md`](docs/product/MVP_DELIVERY_MAP.md)
- [`docs/adr/ADR-0015-operation-proof-v2-current-lineage-r1.md`](docs/adr/ADR-0015-operation-proof-v2-current-lineage-r1.md)
- [`docs/adr/ADR-0017-operation-cell-v1-r1.md`](docs/adr/ADR-0017-operation-cell-v1-r1.md)
- [`docs/adr/`](docs/adr/)
