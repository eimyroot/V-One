# Control Plane Foundation R1

Status: **candidate implementation on `feat/control-plane-foundation-r1`**.

This document does not mark the control plane VERIFIED and does not authorize provider WRITE,
deployment, release, or production effects.

## Purpose

R1 introduces one normalized cross-system contract layer over primitives that already exist in V-One.
It deliberately reuses the canonical product `AuditLedger` rather than creating a parallel event store.

The candidate provides:

- globally scoped `run_id` and `correlation_id` identities;
- optional event causation identity;
- canonical project descriptors and a collision-detecting project registry;
- an immutable control-plane event envelope;
- evidence and decision references carried by each event;
- a full-state transition contract with deterministic state hashing;
- a shared-state pointer projection;
- deterministic event-to-state reconciliation;
- an `AuditLedger`-backed event log adapter.

## Existing primitives reused

R1 does not replace the existing V-One authority/execution graph. It sits above and correlates it.
Existing authorization snapshots, grants, consumption witnesses, dispatch lineage, execution epochs,
leases, receipts, proofs, operation cells, control-plane decisions, and independent verification remain
authoritative in their current domains.

The existing `AuditLedger` remains the persistent hash-chained audit surface. A control-plane event is
stored as a normalized audit payload, so event provenance inherits the existing ledger hash chain
instead of creating another competing audit history.

## Candidate flow

```text
INTENT / OBSERVATION
        |
        v
CorrelationContext/v1
 run_id + correlation_id
        |
        v
ProjectDescriptor/v1
        |
        v
ControlPlaneEvent/v1
        |
        +----> evidence_refs
        +----> decision_refs
        +----> optional StateTransition/v1
        |
        v
canonical AuditLedger
        |
        v
ControlPlaneReconciler
        |
        v
SharedStatePointer/v1
```

## Reconciliation rules

State changes are full-state transitions in R1. Patches and implicit merges are intentionally not
supported.

A state-changing event must bind:

```text
previous_state_hash == current.state_hash
```

The reconciler independently reconstructs the next pointer from the canonical next-state JSON and its
SHA-256 digest. Stale or cross-project transitions fail closed.

Events without a state transition remain valid audit events but do not mutate the shared-state
projection.

## Security boundary

R1 is contract-only/local-control-plane work. It adds no provider credential, mutation transport,
permission widening, authority issuance path, automatic retry, deployment path, or production effect.

The project registry is currently an immutable in-process resolver. Persistent registry storage,
registry authorization, connector/MCP capability discovery, and multi-writer locking remain later
work and must not be inferred from R1.

The shared-state pointer is a deterministic projection contract. R1 does not yet claim a globally
available distributed state service.

## Acceptance evidence required

Before R1 can be promoted beyond candidate status:

- exact-head repository CI must pass;
- the new control-plane tests must pass;
- existing system tests must remain green;
- lint/static gates must remain green;
- review must confirm no duplicate authority, audit, or state ownership was introduced;
- branch/head identity must be rechecked immediately before merge.

## Follow-on slices

After R1 is verified, the next slices should bind existing execution primitives into the envelope and
then add persistent registries incrementally:

1. propagate correlation context through canonical operation preparation/runtime/resume;
2. project selected durable execution events into the normalized event envelope;
3. persist project registry records through one approved authority boundary;
4. add connector/MCP capability and permission descriptors;
5. add Evidence Ledger and ADR/Decision registry indexes over existing canonical artifacts;
6. add Slack approval and Drive synchronization adapters only after the common contracts are stable.
