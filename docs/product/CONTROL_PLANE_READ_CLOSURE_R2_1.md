# Control Plane READ Closure R2.1

Status: **CANDIDATE** until merged through the canonical protected `main` workflow.

## Purpose

R2.1 closes the observable lifecycle of the canonical READ path without changing execution authority,
provider permissions or content-addressed authority contracts.

R2 established correlation-aware `prepared -> verified` events. R2.1 binds the intermediate durable
truth that already exists in the canonical runtime:

```text
fresh:   runtime.read.prepared
resume:  runtime.read.resumed
                    |
                    v
          runtime.read.runner_observed
                    |
                    v
          runtime.read.durably_completed
                    |
                    v
          runtime.read.verifier_observed
                    |
                    v
          runtime.read.verified
```

Every edge is represented by `CorrelationContext.causation_event_id`. All events in one invocation
carry the same `run_id` and `correlation_id`.

## Durable completion binding

The canonical READ terminal already records C4 durable completion after the Runner observation and
before independent verifier readback.

R2.1 requires:

```text
DurableExecutionCompletionResult.completion_digest
    == GitHubRefObservation.observation_digest
```

and independently verifies that the returned completion lease matches the prepared execution across:

- `execution_id`;
- `lease_id`;
- `lease_digest`;
- `execution_epoch`.

Only `COMPLETED` and `DUPLICATE_COMPLETION` are accepted completion outcomes. Any mismatch fails
closed before a control-plane event is appended.

`runtime.read.durably_completed` therefore records already-established durable truth; it does not
create completion authority.

## Resume semantics

`ControlPlaneReadRuntime.run_resumed_read_only(...)` delegates to the existing
`CanonicalOperationRuntime.run_resumed_read_only(...)`.

The canonical resume service remains authoritative. It reconstructs the pre-effect execution context
from durable snapshot, grant, consumption, outbox, inbox/admission, epoch state and the current
execution lease, while rechecking live permission, terminal profile and current fence.

A resumed invocation receives a **new** `CorrelationContext` supplied by the caller. This is deliberate:

- `run_id` and `correlation_id` are control-plane observability identities;
- the original `correlation_id` is audit metadata from snapshot persistence, not a field in
  `AuthorizationSnapshot/v1`;
- R2.1 does not add correlation data to the snapshot or any authority digest;
- the new resume context is bound to the same reconstructed durable `execution_id` and evidence
  lineage.

The resume path is valid only while the canonical resume service considers the durable execution
active and current. R2.1 does not weaken or bypass that rule.

## Independent verifier closure

After durable completion, R2.1 validates the returned independent verification lineage:

```text
Runner observation
    -> IndependentVerificationBoundary
    -> VerifierCredentialDecision
    -> Verifier observation
    -> VerificationResult
```

Bindings checked include execution id/epoch, target digest, Runner observation digest, verifier
identity, boundary digest and verifier credential decision identity/digest.

The verifier observation is emitted as `runtime.read.verifier_observed`; the final
`runtime.read.verified` event is caused by that observation.

## Transaction boundary

The canonical READ terminal performs provider observation, durable completion and independent
readback before the R2.1 control-plane event append transaction begins.

Consequences:

- control-plane event append failure fails the wrapper call;
- it does **not** roll back an already completed provider READ or C4 durable completion;
- this boundary is acceptable only because this slice is READ-only;
- this design MUST NOT be copied to a mutating terminal without an effect/evidence transaction or
  explicit reconciliation contract.

`DurableExecutionCompletionResult` exposes completion outcome, lease and completion digest but does
not expose the exact persisted `completed_at` timestamp. Therefore the normalized completion event
does not claim an exact durable completion timestamp; its event timestamp is the control-plane append
time.

## Authority invariant

```text
CONTROL-PLANE CORRELATION != EXECUTION AUTHORITY
```

R2.1 does not modify:

- `AuthorizationSnapshot/v1`;
- `ExecutionGrantV2`;
- dispatch outbox/envelope contracts;
- admission or execution lease contracts;
- durable completion schema;
- provider READ or WRITE permission models;
- capability selection;
- policy or approval gates.

## Scope

R2.1 includes:

- five-event causal READ lifecycle;
- exact Runner -> durable completion digest binding;
- verifier credential decision and observation lineage binding;
- fresh and resumed READ wrapper entry points;
- fail-closed tamper rejection before control-plane audit append;
- tests proving correlation causation, resume correlation isolation, completion binding and
  authority-digest non-mutation.

R2.1 does not include:

- provider WRITE execution;
- schema migration;
- a new event database;
- distributed shared-state persistence;
- connector/MCP registry persistence;
- Slack or Drive approval workflows.

## Promotion criteria

R2.1 may be promoted only after:

- exact-head lint and compile PASS;
- evidence/governance/security gates PASS;
- full test suite PASS;
- product readiness and dependency audit PASS;
- product image build and smoke test PASS;
- relevant specialized READ/verifier workflows PASS when triggered;
- unresolved blocking review threads = 0;
- canonical base/head rechecked immediately before protected merge.
