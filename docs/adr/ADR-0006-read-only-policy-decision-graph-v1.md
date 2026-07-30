# ADR-0006: Read-only Policy Decision Graph v1

| Field | Value |
|---|---|
| Status | ACCEPTED |
| Date | 2026-07-30 |
| Owner acceptance | 2026-07-30 |
| Decision owner | Repository owner |
| Scope | Deterministic read-only projection of current authorization facts |
| Risk class | R3 authorization and evidence contract |
| Runtime effect | None |
| Accepted corrected patch SHA-256 | `47304e1268af92a4196e9c61d2e2576792c540abca4c26326b8eee99b61951a0` |

## Context

VOODOO One already owns identity, permission checks, approval-policy evaluation, approval
lifecycle, execution gates, audit events, and receipts. Those decisions and evidence relationships
are distributed across their authoritative owners:

- `security.py` owns current role permissions;
- `approval_policy.py` owns the current approval-policy decision;
- `change_request.py` owns request and approval lifecycle transitions;
- `operational_safety.py` owns emergency-stop state;
- `execution.py` owns execution gates and adapter invocation;
- `audit.py` and `receipt.py` own their evidence ledgers.

ADR-0003 proposes a broader configurable policy model. Its first implemented foundation is the pure
`ApprovalPolicyDecision` compatibility evaluator, which explains current approval counts without
changing current runtime outcomes. There is not yet one deterministic representation that relates
the current request, policy decision, approvals, execution-gate facts, and optional evidence
references.

Adding such a representation directly to execution would create a second authorization path and a
high-risk migration. The smallest safe slice is instead a pure projection that has no runtime
authority and is not wired into the product service, database, API, CLI, or execution lifecycle.

## Decision: projection-only ownership and no shadow authorization

The repository introduces `policy-decision-graph/v1` in
`voodoo_product/policy_decision_graph.py`.

The module accepts one immutable `PolicyDecisionSnapshot` containing facts already observed by a
caller. It returns deterministic JSON-compatible data that describes what the current-compatible
gates imply for that snapshot.

The projection:

- performs no I/O;
- reads no database, files, environment variables, network service, or runtime singleton;
- writes no database, files, audit events, receipts, or lifecycle state;
- executes no adapter;
- imports no service, persistence, API, CLI, runner, or CyberCore owner;
- cannot grant permission, approve a request, or authorize execution;
- is not called by the current authorization or execution path.

An `ALLOW` result is an informational projection only. `ExecutionService` remains the authoritative
runtime gate. Consumers must not use the graph as an execution grant or substitute it for current
permission, lifecycle, safety, and production-effect checks.

The graph owns only deterministic representation. It owns no authorization decision and must not
become shadow authorization through a caller treating `decision`, `execution_eligible`, or
`graph_digest` as an execution grant.

## Input contract

`PolicyDecisionSnapshot` contains deterministic current facts:

- request, requester, and workspace identifiers;
- workspace and request environments;
- risk;
- adapter and a descriptive requested capability;
- SHA-256 of the canonical request payload, never the raw payload;
- one immutable permission observation binding the execution actor identity, evaluated permission
  name, and outcome supplied by the authoritative permission gate;
- the current `ApprovalPolicyDecision`;
- immutable approval evidence identifiers, approver identities, and decisions;
- request status;
- emergency-stop state;
- production-effects state;
- optional execution, receipt, and audit-event references.

The projection does not fetch missing facts. Required facts that are absent or invalid produce a
deny-by-default projection.

## Output contract

The returned mapping contains:

- `schema_version: 1`;
- `graph_type: policy-decision-graph/v1`;
- `decision: ALLOW | DENY`;
- `execution_eligible: bool`;
- deterministically sorted `reason_codes`;
- deterministically sorted `limitations`;
- deterministically sorted `nodes`;
- deterministically sorted `edges`;
- `graph_digest`.

Node types in this slice are:

- subject;
- workspace;
- request;
- policy;
- permission observation;
- approval;
- runtime context;
- projection;
- optional execution, receipt, and audit references.

Edges express only supplied relationships such as requesting, targeting, policy evaluation,
review, projection, and optional evidence references. They do not create authority.

## Determinism and digest

The projection uses `evidence_primitives.canonical_json`.

Nodes are sorted by type, identifier, and canonical claims. Every node ID is globally unique,
including graphs containing duplicate or malformed supplied references. Duplicate malformed
approval evidence remains represented under deterministic disambiguated node IDs and still causes
denial. Edges are sorted by source, relation, and destination. Top-level reason codes and
limitations are sorted.

`graph_digest` is:

```text
SHA-256(canonical_json(graph_without_graph_digest))
```

The digest binds the complete returned graph representation except the digest field itself. The
same snapshot produces the same graph and digest. A change to an authoritative represented fact
changes the digest. Hashing supplies identity and change detection; it is not a signature,
authorization, attestation, or proof that the supplied facts were truthful or current.

The embedded policy node uses `ApprovalPolicyDecision.to_dict()`. Its existing policy
`reason_codes` values and order are preserved verbatim. Projection-owned reason codes use only the
`PDG_*` namespace.

## Current-compatible projection rules

The projection is `DENY` and `execution_eligible` is false when any current authoritative
requirement is missing or fails, including:

- required request, requester, workspace, adapter, execution-actor identities, or payload digest
  are absent or invalid;
- workspace or request environment is invalid;
- workspace and request environments differ;
- the permission observation is missing or malformed, is not bound to `execution.run`, or reports a
  denied outcome;
- the policy decision is missing, invalid, or does not express the current
  `ALLOW_AFTER_AUTHORIZATION` result;
- the policy decision does not exactly match the current compatibility decision for the supplied
  request environment and risk;
- approval evidence is invalid or contains a denial;
- the requester appears as an approver;
- approved or distinct approver counts do not satisfy the current `ApprovalPolicyDecision`;
- request status is not `APPROVED`;
- emergency-stop state is missing or active;
- production-effects state is missing;
- a production request has production effects disabled.

Only a snapshot satisfying all represented current-compatible gates projects `ALLOW`. This rule
does not change or replace any runtime gate.

The permission observation is a caller-supplied projection fact. PDG does not inspect a role,
resolve a permission, or perform authorization. The authoritative permission owner must evaluate
`execution.run` for the stated execution actor before constructing the snapshot.

## Capability semantics

`requested_capability` is descriptive in PDG v1. It is represented and digest-bound, but it is not
an authoritative current runtime enforcement input. Registered-adapter and capability validity are
assumed to have been established by the authoritative request lifecycle snapshot.

PDG v1 does not query an adapter registry, infer capabilities, or create a second capability policy
engine. Missing future capability-policy assurance is a limitation of what the projection can
prove, not a new denial rule.

## Limitations versus denial semantics

The current persistence model does not bind approvals to:

- the request payload digest;
- the approval policy version;
- an approval expiry.

Those are future assurance requirements from ADR-0003. They are emitted as `limitations`, not as
new denial policy, because the current authoritative runtime permits execution without those
bindings. Turning them into denial rules would silently change current authorization semantics and
is outside this slice.

Limitations therefore describe what the projection cannot prove. They must not be interpreted as
successful assurance, and they do not weaken current gates.

## Trust boundaries

The snapshot is caller-supplied and may be stale, incomplete, inconsistent, or fabricated. The
projection validates represented facts and denies when required facts are unavailable, but it does
not independently establish their provenance.

A digest authenticates nothing. A process controlling the snapshot can produce a digest for false
facts. Persistent decision evidence, approval binding, signatures, replay protection, and
independent state acquisition remain future work.

CyberCore and other intelligence sources remain proposal and context sources only. They do not own
this projection, identity, policy, approval, authorization, execution, audit, or receipt evidence.

## No persistence, API, or runtime effects

This slice adds:

- no database table, migration, query, or persistence adapter;
- no product-service or composition wiring;
- no HTTP endpoint or public API contract;
- no CLI command;
- no configuration or feature flag;
- no execution integration;
- no production enablement;
- no CyberCore integration.

## Verification

Focused tests cover:

- canonical determinism and digest recomputation;
- digest changes from changed authoritative input;
- deny-by-default incomplete input;
- permission, separation, approval-count, environment, lifecycle, emergency-stop, and production
  gates;
- one current-compatible `ALLOW` projection;
- limitations that do not introduce new denial policy;
- stable sorting and verbatim policy reason codes;
- input immutability;
- optional execution, receipt, and audit references;
- absence of runtime and CyberCore authority dependencies.

Relevant existing approval, change-request, operational-safety, execution, and documentation tests
must continue to pass.

## Consequences

### Positive

- current facts receive one deterministic, reviewable graph representation;
- the graph has stable identity without adding persistence or dependencies;
- policy explanations are reused instead of reimplemented;
- missing current facts fail closed;
- future assurance gaps remain explicit without silently changing runtime policy.

### Negative and residual

- callers can supply stale or false snapshots;
- the graph duplicates current gate outcomes for explanation and can drift until future integration
  is separately designed;
- no persistent or signed decision evidence exists;
- an `ALLOW` projection has no runtime authority;
- approval binding and expiry remain unimplemented.

## Rollback

Remove:

- `voodoo_product/policy_decision_graph.py`;
- `tests/system/test_policy_decision_graph.py`;
- this ADR.

No migration, configuration, API, persisted state, runtime authorization, release, or deployment
rollback is required.

## Non-goals

This decision does not authorize:

- wiring the graph into execution;
- treating the graph as an authorization or execution gate;
- changing current approval or permission outcomes;
- storing policy decisions;
- adding an API or CLI;
- implementing organization policy profiles;
- enabling production effects;
- issuing execution grants;
- integrating CyberCore or a runner;
- release or deployment.
