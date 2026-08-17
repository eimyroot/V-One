# Isolated Runner Adapter R1

Status: IMPLEMENTED candidate

Phase: D3

## Purpose

D3 introduces the first provider-neutral isolated-runner orchestration boundary over the already-merged D1 RunnerIdentity/RunnerBoundary and D2 CredentialBroker contracts.

This slice deliberately does **not** perform a provider read or provider mutation. It prepares and activates a runtime that is structurally limited to READ-only execution. D4 is the first phase allowed to observe real provider state.

## Source-of-truth correction

CASER SandCloud is a persistent governed staging, review, validation, handoff, and evidence layer. It is not project truth, authorization authority, execution authority, or production.

Therefore D3 is implemented as an **Isolated Runner / CASTER-MINAL execution boundary**, not as a SandCloud execution engine. SandCloud may stage and validate D3 evidence, but it does not execute or authorize the runtime.

Historical architecture text that placed grant consumption inside the Runner is superseded by the current merged Phase-C model:

```text
ExecutionGrant/v2
  -> durable consumption + outbox
  -> DispatchEnvelope
  -> Inbox/Dedup
  -> ExecutionEpoch + Lease
  -> DurableCoordinator
  -> D1 RunnerBoundary
  -> D2 CredentialAccessDecision
  -> D3 Isolated Runner Adapter
```

The Runner does not re-consume the grant and does not manufacture authority.

## Two-phase runtime lifecycle

D1 RunnerIdentity contains a concrete provider instance identifier. That identifier cannot exist before a provider session exists, while D2 CredentialAccessDecision cannot be created until RunnerBoundary exists.

D3 therefore uses a two-phase lifecycle:

```text
C4 current lease + ExecutionCapsule
        |
        v
credential-free bootstrap
        |
        | exact observed runtime profile
        v
RunnerIdentity/v1
        |
        v
RunnerBoundary/v1
        |
        v
CredentialBroker D2 authorization
        |
        v
PreparedIsolatedRuntime
        |
        | immediate CurrentExecutionFence recheck
        v
READ-only activation
```

## Bootstrap invariants

`IsolatedRuntimeBootstrap/v1` is descriptive provider evidence and must bind:

- concrete provider and provider instance ID;
- exact `runner_class`;
- exact environment;
- exact rootfs digest from ExecutionCapsule;
- exact resource-limit profile digest from ExecutionCapsule;
- exact network-policy digest from ExecutionCapsule;
- `workspace_mount_mode = READ_ONLY`;
- `network_egress_default = DENY_ALL`;
- `inherited_credentials = false`;
- `provider_mutation_allowed = false`.

Any profile drift fails closed before RunnerIdentity, RunnerBoundary, or credential authorization is accepted.

## Credential boundary

The core D3 adapter receives only D2 `CredentialAccessDecision/v1`. It never receives or emits usable secret material.

A concrete runtime provider may later deliver a short-lived credential through an out-of-band provider-specific secret channel, but the D3 core contract must not contain:

- token bytes;
- bearer headers;
- credential handles usable outside the provider adapter;
- environment-variable secret values;
- long-lived provider credentials.

## Current epoch fence

The exact C4 lease must be rechecked immediately before provider runtime activation through `CurrentExecutionFence`.

Required ordering:

```text
prepare runtime
credential decision
CURRENT C4 LEASE RECHECK
provider READ-only activation
```

If the lease was superseded, expired, or otherwise non-current, activation must not occur.

The provider-specific durable implementation of `CurrentExecutionFence` remains a required composition dependency. D3 never trusts a caller-supplied epoch integer as current truth.

## Activation evidence

`ReadOnlyRuntimeActivation/v1` binds:

- provider instance;
- RunnerIdentity;
- RunnerBoundary;
- CredentialAccessDecision;
- exact lease ID/digest and execution epoch;
- execution capsule;
- capability definition;
- READ-only access mode;
- READ-only workspace mount;
- DENY_ALL network default;
- `provider_mutation_allowed = false`.

It does not contain provider output or secret material and is not independent verification.

## Phase-D safety ceiling

D3 rejects any capability whose effect class is not `READ_ONLY` before runtime bootstrap.

The slice does not permit:

- repository or provider mutation;
- workspace persistent write;
- deploy/release;
- production mutation;
- generic shell fallback;
- arbitrary network access;
- long-lived credentials;
- handler execution;
- provider observation;
- ExecutionReceipt or OperationProof issuance.

## Integration status

The new adapter is intentionally **not wired into the legacy `service.py` or `execution.py` runtime paths** in D3 R1.

There is currently no connected external isolated-runner provider available to this ChatGPT session. GitHub Actions is used only as exact-head CI/COMPUTE evidence for the code candidate; it is not claimed as a live D3 provider runtime.

## Acceptance gates

D3 R1 requires tests proving:

1. credential-free deny-all bootstrap binds exact capsule profile;
2. D1 RunnerIdentity and RunnerBoundary are derived only after exact bootstrap validation;
3. D2 decision binds the exact runtime/lease context;
4. mutating capability fails before bootstrap;
5. stale C4 fence prevents provider activation;
6. fence occurs immediately before provider activation;
7. activation claim drift fails closed;
8. secret fields are rejected from runtime evidence;
9. legacy execution paths remain unwired.

## Next gate

After D3 merge, the next bounded slice is **D4 — first real provider READ** using one explicitly selected provider adapter and one reversible/non-mutating capability.

D4 must first establish a real connected isolated-runner backend and a durable `CurrentExecutionFence` implementation. Until then, real provider observation remains BLOCKED rather than simulated as VERIFIED.
