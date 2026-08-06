# Target Capabilities

| Field | Value |
|---|---|
| Document status | Target-state capability map |
| Capability status | PROPOSED unless explicitly stated otherwise |
| Planning source | `ROADMAP.md` |
| Current-state source | `CURRENT_CAPABILITIES.md` |

## Target capability template

Every target capability must define:

- user problem;
- product value;
- authoritative owner;
- inputs and outputs;
- trust boundary;
- failure behavior;
- evidence requirements;
- dependencies;
- acceptance criteria;
- rollback or disable strategy;
- current status.

## Verified foundation

ADR-0007 accepts the pure deterministic value-contract slice:

- `execution-target/v1`;
- `approval-evidence-set/v1`;
- `execution-grant/v1`;
- `execution-receipt/v1`.

This foundation is representation only. Authoritative issuance, signed envelopes, durable one-time
consumption, and isolated Runner runtime remain PROPOSED.

## T1 — Policy Decision Graph

**Status:** VERIFIED read-only projection foundation; authoritative policy, approval binding,
persistence, and runtime enforcement remain PROPOSED.

### Problem

Current approval rules are secure for the present scope but do not yet express a complete,
explainable matrix over risk, capability, blast radius, reversibility, target, and policy version.

### Verified foundation

Accepted ADR-0006 provides `policy-decision-graph/v1` as a pure deterministic projection over
caller-supplied current facts. It emits sorted nodes, edges, reason codes, limitations, and a
canonical digest; it denies informational eligibility when represented current gates fail.

This foundation is not wired into runtime authorization or execution, performs no permission
lookup, persists nothing, and issues no grant. Its snapshots are caller-supplied and unsigned.

### Target behavior

```text
normalized request context
  -> deterministic policy evaluation
  -> decision
  -> matched rules
  -> missing conditions
  -> required approval roles
  -> expiry and invalidation conditions
```

### Acceptance criteria

- same canonical inputs and policy version produce the same decision;
- approval binds to artifact digest, target, environment, policy version, and expiry;
- relevant drift invalidates approval;
- decision explanation is stored without sensitive payloads;
- negative and replay tests pass.

The first criterion is VERIFIED for the read-only v1 projection. Approval payload/policy-version/
expiry binding, stored authoritative decisions, drift invalidation, replay enforcement, and runtime
policy enforcement remain PROPOSED.

## T2 — Signed execution grants

**Status:** PROPOSED

The grant envelope and issuer/runtime path build on the accepted deterministic grant value contract,
but they are not implemented yet.

A grant must bind:

```text
grant_id
execution_id
artifact_digest
workspace_ref
target_ref
environment
policy_version
required_capabilities
pre_state_digest
issued_at
expires_at
nonce
fence
issuer_key_id
signature
```

Acceptance requires one-time use, replay rejection, expiry, rotation support, and deterministic
verification.

## T3 — Isolated Runner Capsules

**Status:** PROPOSED

The runner must provide:

- separate operating-system identity;
- rootless execution;
- read-only base filesystem;
- capability-scoped workspace;
- CPU, memory, PID, and timeout limits;
- network deny by default;
- explicit destination allowlist where required;
- heartbeat and lease renewal;
- cancellation and fencing;
- precondition and postcondition verification;
- structured result and signed receipt.

## T4 — Structured execution receipts

**Status:** PROPOSED

The runtime receipt envelope and ingest path build on the accepted deterministic receipt value
contract, but they are not implemented yet.

Target receipt fields include:

```text
execution_id
grant_id
artifact_digest
runner_id
runner_version
started_at
completed_at
status
pre_state_digest
post_state_digest
action_results
output_digest
log_artifact_digest
rollback_attempted
rollback_status
verification_status
runner_key_id
runner_signature
```

Raw credentials and uncontrolled provider responses must never be embedded.

## T5 — Expanded ProofGraph

**Status:** PROPOSED

Target nodes:

- source commit and tree;
- build;
- SBOM;
- vulnerability policy;
- artifact;
- publisher signature;
- policy decision;
- approval;
- execution grant;
- runner identity;
- execution;
- receipt;
- post-state observation;
- checkpoint;
- external anchor.

Target verification modes:

- local immutable package;
- remote byte verification;
- signature and trust-policy validation;
- registry digest verification;
- transparency or object-lock anchor verification.

## T6 — CyberCore read-only knowledge boundary

**Status:** PROPOSED

Initial contract may contain:

```text
source
knowledge_reference
artifact_id
artifact_digest
publisher
risk
target_reference
environment
evidence_references
confidence
expected_effect
verification_plan
observed_at
```

Required properties:

- versioned schema;
- feature flag off by default;
- no shared database;
- no package code execution;
- no secrets;
- idempotent import;
- audit event for every accepted or rejected intake.

## T7 — AI Change Copilot

**Status:** PROPOSED

The copilot may:

- translate human intent into a draft request;
- summarize evidence and uncertainty;
- identify missing preconditions;
- propose risk, tests, rollback, and verification;
- explain policy decisions;
- review execution evidence.

It must not:

- approve its own work;
- issue grants;
- alter policy;
- activate production effects;
- suppress uncertainty;
- execute external mutation directly.

## T8 — Enterprise identity and tenancy

**Status:** PROPOSED

Target capabilities:

- released OIDC;
- step-up authentication;
- workspace membership;
- role assignment per workspace;
- tenant and platform administrator separation;
- key rotation and `kid`;
- server-side logout and revocation across all supported identity paths.

## T9 — Released PostgreSQL and HA operations

**Status:** PROPOSED

Prerequisites:

- isolated runner boundary;
- transactional outbox;
- explicit locking for ledger heads and execution claims;
- connection pooling;
- backup, restore, and PITR;
- migration rehearsal;
- multi-node recovery tests;
- SLOs and operator runbooks.

## T10 — Signed multi-platform supply chain

**Status:** PROPOSED

Target:

```text
immutable source
  -> deterministic build
  -> linux/amd64 + linux/arm64
  -> SBOM
  -> vulnerability report
  -> provenance
  -> signature
  -> governed registry promotion
  -> deployment verification
```

## T11 — Outcome learning loop

**Status:** PROPOSED

Execution outcome should create a normalized observation for an intelligence layer such as CyberCore:

```text
planned state
  -> approved execution
  -> observed post-state
  -> drift and outcome comparison
  -> knowledge update
```

VOODOO One retains authorization and evidence ownership; the intelligence layer retains knowledge and
recommendation ownership.
