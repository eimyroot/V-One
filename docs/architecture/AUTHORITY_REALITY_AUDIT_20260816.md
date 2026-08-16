# Authority Reality Audit — 2026-08-16

Status: EVIDENCE-BOUND CURRENT-STATE AUDIT
Scope: authority prerequisites for `AuthorityWitnessSet` and `AuthoritativeSnapshotCreator`
Audit base: `main@0d623c10aca11b5aabd26e34e253341d9708cbdf`
Runtime/release effect: NONE

## 1. Purpose

Determine which authority inputs required by the adopted Verifiable Operations Trust Plane already exist as authoritative runtime mechanisms, which exist only as contracts/current-behavior compatibility mechanisms, and which are missing.

This audit does not implement or activate authority. It is the reality gate before implementation.

## 2. Required target chain

```text
ReviewedOperation / immutable request facts
→ execution.run permission authority
→ capability definition + activation authority
→ deterministic target binding
→ immutable/versioned policy authority
→ approval evidence authority
→ trusted clock authority
→ AuthorityWitnessSet
→ AuthorizationSnapshot
→ atomic persistence + audit
```

## 3. Verified current foundations

### AuthorizationSnapshot contract — PRESENT

`voodoo_product/authorization_snapshot.py` provides a deterministic immutable contract with digest binding for request/review, actor, workspace, environment, capability identity, target, policy identity, approval evidence identity, timestamp-source identity and source revision.

The contract explicitly states that it does **not** prove the authority gates succeeded.

### AuthorizationSnapshot persistence — PRESENT, persistence-only

`voodoo_product/authorization_snapshot_store.py` persists prevalidated snapshots, validates immutable request bindings and writes audit evidence in a database transaction.

The store explicitly does not evaluate approval policy, capability eligibility, target binding or execution permission, and `persist_prevalidated(...)` opens its own transaction.

### ExecutionGrant contract — PRESENT as representation

`voodoo_product/execution_contract.py` already contains `execution-grant/v1` representation alongside `ExecutionTarget`, `ApprovalEvidenceSet` and `ExecutionReceipt` contracts.

This does not constitute an authoritative grant issuer.

## 4. Authority gate matrix

| Gate | Criterion | Current evidence | GateStatus |
|---|---|---|---|
| P0 | GitHub `main` enforces PR-only + required `verify` + no force/delete | repository baseline requires it; live GitHub metadata reports protection disabled and required checks off | FAIL |
| P1 | Immutable/versioned policy authority can be resolved as exact authority input | `approval_policy.py` exposes code-defined current compatibility policy; no persisted immutable `PolicyRevision` authority used for snapshot construction | FAIL |
| P2 | Server-side `execution.run` authority is reusable and revalidated inside authorization transaction | `security.py` maps roles to `execution.run`; `api.py` enforces it at HTTP dependency boundary only | FAIL |
| P3 | CapabilityDefinition + explicit activation authority exists | current change-request path uses static `VALID_ADAPTERS`; adapter implementation branches by name; no versioned capability definition/activation authority is composed | FAIL |
| P4 | Deterministic authoritative target binder runs before authorization | `ExecutionTarget` contract exists, but current adapters resolve effect-specific paths/presets during execution rather than through an authority binder before snapshot creation | FAIL |
| P5 | Approval evidence authority assembles exact reviewed approvals bound to capability, target, policy and validity | DB-backed approval lifecycle and immutable review digest exist; `ApprovalEvidenceSet` is a pure contract; no authoritative assembler/resolver for snapshot creation is composed | FAIL |
| P6 | Trusted clock authority supplies both time and immutable source identity | `utc_now()` supplies canonical UTC time; `issuance_timestamp_source_identity` is supplied to snapshot construction by the caller | FAIL |
| P7 | Snapshot persistence can participate in one outer authorization transaction | current `persist_prevalidated(...)` opens its own transaction | FAIL |
| P8 | AuthoritativeSnapshotCreator composes all authority reads + construction + persistence + audit atomically | no runtime creator is present | FAIL |

## 5. Detailed findings

### P1 — policy authority

FACT: `evaluate_current_approval_policy(...)` deterministically reproduces current approval behavior and has a version string.

FACT: the policy is defined by current source constants/logic and is primarily a compatibility evaluator.

FINDING: this is useful current behavior but is not yet an immutable persisted/versioned policy authority suitable as a transactionally resolved snapshot witness.

Required implementation direction:

```text
PolicyRevision
PolicyAssignment / effective-policy resolver
immutable identity/digest
resolve_effective_policy_on_connection(...)
```

### P2 — execution.run permission authority

FACT: `ROLE_PERMISSIONS` grants `execution.run` to `operator`; administrator wildcard also permits it.

FACT: the API endpoint `/change-requests/{request_id}/execute` uses `require_permission("execution.run")`.

FINDING: current execution permission is authoritative for the HTTP endpoint request, but it is not an independently versioned authority decision and is not re-resolved within the future Snapshot Creator database transaction.

Required implementation direction:

```text
PermissionDecision
permission authority identity/revision
check_execution_permission_on_connection(...)
```

The new authority path must not trust a client-supplied permission result.

### P3 — capability definition and activation

FACT: current change requests accept only `echo`, `write_artifact`, and `run_validation` through `VALID_ADAPTERS`.

FACT: `execute_adapter(...)` implements these names directly.

FINDING: static adapter allowlisting is not equivalent to `CapabilityDefinition` plus explicit `CapabilityActivation` authority. It lacks canonical capability identity/version, environment eligibility, permission requirements, target binder identity, verifier contract and activation identity.

Required implementation direction:

```text
CapabilityDefinition
CapabilityActivation
resolve_effective_capability_on_connection(...)
```

No module may self-activate.

### P4 — deterministic target binder

FACT: `ExecutionTarget` is deterministic and digest-bound as a value contract.

FACT: current target/effect details are interpreted inside adapters, for example sandbox artifact path handling occurs at execution time.

FINDING: target representation exists, but target authority does not. A Snapshot Creator must bind the authoritative target before authorization and before execution.

Required implementation direction:

```text
bind_execution_target_on_connection(...)
→ ExecutionTarget
→ authoritative target identity
```

### P5 — approval evidence authority

FACT: change-request approval is database-bound, forbids requester self-approval, verifies immutable review-content binding and counts required approvals in the same approval transaction.

FACT: `ApprovalEvidenceSet` binds request, payload digest, target digest, capability, policy version, approvals and validity.

FINDING: the runtime approval lifecycle does not yet expose an authoritative resolver that constructs that exact evidence object from persisted reviewed state plus exact policy/capability/target context.

Required implementation direction:

```text
load_approval_evidence_on_connection(...)
→ ApprovalEvidenceSet
→ approval evidence identity
```

### P6 — trusted clock authority

FACT: `utc_now()` returns canonical timezone-aware UTC milliseconds.

FINDING: canonical time generation exists, but trusted timestamp authority identity is not composed; the current snapshot contract accepts `issuance_timestamp_source_identity` as constructor input.

Required implementation direction:

```text
TrustedClock
now()
source_identity
```

The Snapshot Creator must source both values from the same trusted authority.

### P7 — atomic persistence boundary

FACT: `AuthorizationSnapshotStore.persist_prevalidated(...)` validates request bindings and persists snapshot + audit evidence.

FINDING: it opens its own transaction, therefore it cannot yet guarantee that authority reads, snapshot construction, persistence and audit all observe one coherent transaction state.

Required implementation direction:

```text
persist_prevalidated_on_connection(connection, ...)
```

Keep the existing convenience method as a wrapper if useful, but the authoritative creator must use the connection-aware path.

## 6. AuthorityWitnessSet contract requirements

`AuthorityWitnessSet` should be a deterministic, immutable, digest-bearing contract. It should contain identities/digests of the exact authority facts consumed by Snapshot Creator rather than duplicate mutable authority state.

Minimum target fields:

```text
schema_version
authority_witness_type
permission_decision_identity
capability_definition_identity
capability_activation_identity
execution_target_identity
policy_identity
approval_evidence_identity
issuance_timestamp_source_identity
revocation_epoch_identity or explicit NOT_APPLICABLE profile
witness_digest
```

Rules:

1. every identity is non-empty and canonical;
2. digest-bearing identities use lowercase SHA-256 where the source contract is content-addressed;
3. witness digest is deterministic canonical JSON;
4. no field can be silently omitted;
5. witness set is evidence of exact authority inputs, not execution permission;
6. downstream contracts may narrow authority but never widen it.

## 7. AuthoritativeSnapshotCreator acceptance contract

The creator is not ready to implement until P1–P7 have authoritative APIs.

Required transaction shape:

```text
BEGIN
  load immutable reviewed request facts
  revalidate review-content digest
  resolve actor/workspace/environment
  check execution.run permission
  resolve active capability definition + activation
  bind authoritative target
  resolve immutable policy revision
  load approval evidence and validate quorum/bindings/validity
  read trusted clock + source identity
  construct AuthorityWitnessSet
  construct AuthorizationSnapshot
  persist snapshot on same connection
  append audit on same connection
COMMIT
```

Any failed authority read or binding must roll back the entire operation.

## 8. Implementation order derived from audit

Do not implement the Snapshot Creator as one large patch.

Recommended bounded sequence:

```text
A0  Authority Reality Audit              ← this document
A1  AuthorityWitnessSet pure contract + tests
A2  transaction-aware SnapshotStore API + tests
A3  immutable PolicyRevision authority + tests
A4  server-side PermissionDecision authority + tests
A5  CapabilityDefinition + Activation authority + tests
A6  deterministic TargetBinder authority + tests
A7  ApprovalEvidence resolver + TrustedClock authority + tests
A8  AuthoritativeSnapshotCreator + rollback/negative tests
```

Each slice must preserve existing current execution behavior until an explicit migration/adoption step replaces it.

## 9. Current blocker

Repository-side P0 governance contract requires:

```text
pull_request_required = true
required_status_checks = ["verify"]
require_latest_head_checks = true
allow_force_pushes = false
allow_deletions = false
require_conversation_resolution = true
ordinary_admin_bypass = false
```

Live GitHub metadata at audit time still reports `main` branch protection disabled and required checks enforcement off.

Therefore:

```text
P0 GITHUB GOVERNANCE = FAIL
HIGHER-IMPACT AUTHORITY IMPLEMENTATION = BLOCKED BY REPO GOVERNANCE
```

This audit itself is documentation/evidence only and has no runtime/release/production effect.

## 10. Decision

The architecture direction is implementable without a big-bang rewrite, but `AuthoritativeSnapshotCreator` is not the next code file to write.

The next code slice after P0 enforcement is:

```text
AuthorityWitnessSet pure contract
+
focused deterministic/negative tests
```

Then implement the missing authoritative resolvers in the order above, preserving one language and one authority model throughout.