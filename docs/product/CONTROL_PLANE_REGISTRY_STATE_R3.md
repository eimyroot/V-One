# Control Plane Registry & Shared-State Foundation R3

Status: **CANDIDATE** until merged through the canonical protected `main` workflow.

## Purpose

R3 makes the already-existing control-plane project and shared-state contracts durable and adds
observational connector/MCP registries without widening execution authority.

R3 reuses the canonical product database instead of introducing a second state store:

```text
observed registry/state input
        |
        v
canonical contract validation
        |
        v
AuditLedger append-only history
        +
materialized runtime_flags projection
        |
        v
fail-closed reload / reconciliation
```

No connector or MCP registry record grants permission to execute. Executable capability resolution
remains owned by `ImmutableCapabilityRegistry` and the existing authorization -> grant -> dispatch
pipeline.

## Existing primitives reused

R3 deliberately does not duplicate contracts already present in V-One:

- `ProjectDescriptor` and `ImmutableProjectRegistry` remain the canonical project identity model;
- `StateTransition` and `SharedStatePointer` remain the canonical shared-state contracts;
- `ControlPlaneEventLog` continues to normalize control-plane events into the canonical AuditLedger;
- `ControlPlaneReconciler` remains the deterministic state reducer;
- `ImmutableCapabilityRegistry` remains the execution capability definition/activation authority.

## Durable project registry

Project descriptors are persisted as canonical JSON materialized records under a namespaced product
state key. Registration is insert-only in R3 and is checked against all existing project ids, aliases
and canonical repositories through `ImmutableProjectRegistry` before persistence.

Every successful registration is appended to the product AuditLedger in the same database
transaction.

R3 does not support project descriptor mutation. A future descriptor lifecycle must introduce an
explicit generation contract rather than silently overwriting project identity.

## Connector Capability Registry

`ConnectorCapabilitySnapshot/v1` records observed connector state:

- connector identity and provider identity;
- monotonic generation;
- observed availability;
- optional references to existing `CapabilityDefinition.definition_identity` values;
- observed scopes;
- whether mutation requires approval;
- verification status;
- provenance source and observation time;
- content-addressed snapshot digest.

Generations advance by exactly one using compare-and-swap. History is retained in the AuditLedger;
the current materialized snapshot is a projection.

If a connector snapshot references executable capability definition identities, R3 requires an
`ImmutableCapabilityRegistry` and rejects unknown identities. The connector snapshot cannot create a
new capability definition or activate one.

## MCP Registry

`MCPServerDescriptor/v1` records an observed MCP/provider transport surface:

- server id;
- parent connector id;
- monotonic generation;
- transport kind;
- endpoint identity (never credentials);
- protocol/version label;
- advertised capability names;
- observed availability;
- verification status;
- provenance source and observation time;
- content-addressed descriptor digest.

R3 requires the referenced connector to exist before an MCP descriptor can be recorded. An available
MCP descriptor cannot bind to a connector whose current status is `REVOKED`.

The registry describes what the control plane has observed. It is not proof that a physical standalone
MCP server exists unless the descriptor's verification status and source establish that fact.

## Shared-state persistence

The current `SharedStatePointer` is materialized per project. Genesis is implicit until the first
state-changing event.

For a state-changing `ControlPlaneEvent`, R3 executes in one serialized product database transaction:

```text
load current pointer
    -> validate previous_state_hash
    -> deterministically reduce event
    -> append event to AuditLedger
    -> compare-and-swap materialized SharedStatePointer
    -> COMMIT
```

A stale previous-state hash, project mismatch, projection race or malformed stored record fails the
transaction. The AuditLedger event and shared-state projection therefore cannot commit independently
inside this boundary.

This atomicity applies to **control-plane event + materialized shared-state projection only**. It does
not retroactively make an external provider effect atomic with the event log. The R2.1 READ boundary
remains unchanged, and a WRITE path still requires an explicit effect/evidence transaction or
reconciliation design.

## Storage decision

R3 intentionally reuses two existing canonical database primitives:

- `audit_events` = append-only, hash-chained history;
- namespaced `runtime_flags` rows = current materialized registry/state projection.

This avoids a new migration and a parallel database authority for the R3 foundation. Dedicated
registry tables may be introduced later only if query scale or lifecycle requirements justify a schema
migration; their source history must still reconcile to canonical evidence.

## Verification states

Registry verification status is one of:

- `UNVERIFIED`
- `OBSERVED`
- `VERIFIED`
- `REVOKED`

`UNVERIFIED` and `OBSERVED` must never be promoted to execution permission. `REVOKED` records cannot
claim current availability.

## Authority invariant

```text
REGISTRY DISCOVERY != EXECUTION AUTHORITY
MCP ADVERTISEMENT != TOOL AUTHORIZATION
SHARED STATE != AUTHORIZATION SNAPSHOT
```

R3 does not modify:

- `AuthorizationSnapshot/v1`;
- `ExecutionGrantV2`;
- Grant consumption;
- dispatch outbox/inbox contracts;
- execution epoch/lease/fence;
- capability activation semantics;
- provider READ/WRITE credentials;
- policy or approval gates.

## Promotion criteria

R3 may be promoted only after:

- lint and compile PASS on the exact PR head;
- all existing evidence/governance/security gates PASS;
- full system test suite PASS;
- R3 registry/state tests PASS;
- product readiness and dependency audit PASS;
- image build and smoke test PASS;
- unresolved blocking review threads = 0;
- canonical `main` base/head rechecked immediately before protected merge.
