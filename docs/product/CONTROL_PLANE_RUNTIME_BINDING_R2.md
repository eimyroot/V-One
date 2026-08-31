# Control Plane Runtime Binding R2

Status: **CANDIDATE** until merged through the canonical protected `main` workflow.

## Purpose

R2 binds the R1 control-plane identity/event contracts to the existing canonical READ execution path
without changing any authority-bearing or content-addressed execution contract.

The runtime path remains authoritative:

```text
CorrelationContext/v1
        |
        | correlation_id only
        v
CanonicalOperationRuntime.run_read_only
        v
AuthorizationSnapshot
        v
ExecutionGrantV2
        v
DispatchOutboxEntry
        v
DispatchEnvelope
        v
Admission + ExecutionLease
        v
Runner observation
        v
Independent verifier readback
        v
VerificationResult/v1
        v
ControlPlaneEvent/v1 -> canonical AuditLedger
```

## New boundary

`ControlPlaneReadRuntime` owns a `CorrelationContext` and delegates execution to the existing canonical
READ runtime. It does not create authority and does not replace the canonical runtime.

After the canonical terminal returns, R2 independently verifies the returned lineage across:

- request and actor -> AuthorizationSnapshot;
- snapshot -> grant;
- grant -> outbox;
- outbox -> dispatch envelope;
- dispatch -> admission;
- admission -> execution lease and epoch;
- lease -> Runner observation;
- Runner observation -> independent verification evidence;
- verification evidence -> VerificationResult/v1.

A mismatch fails closed before R2 appends normalized control-plane events.

## Event model

R2 records two normalized events for a successful READ terminal invocation:

1. `runtime.read.prepared`
   - carries the original `run_id` and `correlation_id`;
   - references snapshot, grant, outbox, envelope, admission and lease evidence;
   - records only lineage that was already accepted by the canonical runtime.
2. `runtime.read.verified`
   - carries the same `run_id` and `correlation_id`;
   - sets `causation_event_id` to the prepared event;
   - references Runner observation, verifier observation, observed state, verification boundary,
     verifier identity, verification strength and verification result.

Both events are appended through the R1 `ControlPlaneEventLog`, which is backed by the existing
hash-chained `AuditLedger`. R2 does not introduce another ledger or event database.

## Authority invariant

```text
CONTROL-PLANE IDENTITY != EXECUTION AUTHORITY
```

`run_id` and `correlation_id` are observability/control-plane identities. They MUST NOT:

- select a capability;
- issue or widen an ExecutionGrant;
- alter AuthorizationSnapshot content;
- alter grant/outbox/envelope/admission/lease digests;
- authorize a provider mutation;
- bypass a policy, approval, permission, lease or verifier gate.

The existing immutable authority contracts remain unchanged.

## Transaction boundary

The canonical READ operation finishes before the R2 event append transaction begins. This is safe for
R2 because the integrated terminal is READ-only. Event recording failure causes the wrapper call to fail,
but it does not claim rollback of an already completed provider observation.

This design MUST NOT be copied to a mutating terminal without a dedicated effect/evidence transaction or
reconciliation contract. WRITE runtime binding is therefore intentionally out of scope for R2.

## Scope

R2 includes:

- `CorrelationContext` propagation into the existing canonical READ runtime;
- fail-closed returned-lineage verification;
- causal prepared -> verified control-plane events;
- canonical AuditLedger recording;
- tests proving correlation propagation, tamper rejection, database-bound ledger composition and
  non-mutation of existing authority digests.

R2 does not include:

- a new Event Log database;
- schema changes to AuthorizationSnapshot, ExecutionGrantV2, DispatchOutboxEntry or DispatchEnvelope;
- provider WRITE execution;
- distributed shared-state persistence;
- connector/MCP registry persistence;
- Slack/Drive workflows.

## Promotion criteria

R2 may be promoted only after:

- exact-head lint and compile PASS;
- existing governance/evidence gates PASS;
- full test suite PASS;
- product readiness and dependency audit PASS;
- product image build and smoke test PASS;
- relevant specialized workflows PASS when triggered;
- unresolved blocking review threads = 0;
- canonical base/head rechecked immediately before merge.
