# ADR-0013: Read-Only Runner Boundary (historical SandCloud naming)

| Field | Value |
|---|---|
| Status | ACCEPTED / PARTIALLY SUPERSEDED |
| Date | 2026-08-17 |
| Scope | Phase D read-only isolated Runner boundary after Phase C durable dispatch completion |
| Base | `main@724dd783e0c5f8dca64ea47d9171e98334fff8d6` |
| Supersedes | ADR-0008 target-state assumptions where they conflict with the released Phase C authority chain |
| Superseded by | ADR-0014 for SandCloud terminology; all execution/authority semantics below remain unless explicitly corrected |
| Production effects | BLOCKED |
| Provider mutation | BLOCKED |

> Historical note: the original ADR title and one provider-abstraction section used `SandCloud` as
> a name for the isolated execution boundary. ADR-0014 freezes the canonical meanings:
> `SandCloud = governed non-canonical staging/review/validation/evidence`; `Runner = isolated
> execution principal`; `CASTER-MINAL = governed execution control surface`. The historical naming
> must not be used as current VOP semantics.

## Decision

Phase D starts from the released Phase C chain, not from the older pre-Phase-C Runner model.

The authoritative order is now:

```text
AuthorizationSnapshot
  -> ExecutionGrant/v2
  -> GrantConsumptionWitness/v1
  -> DispatchOutboxEntry/v1
  -> DispatchEnvelope/v1
  -> DispatchInboxAdmission/v1
  -> durable ExecutionEpoch + ExecutionLease/v1
  -> DurableCoordinator
  -> Phase-D Runner boundary
```

V-One owns grant issuance, ONE_TIME consumption, durable dispatch truth, inbox deduplication,
ExecutionEpoch allocation, lease persistence and completion fencing. A Phase-D Runner MUST NOT
re-consume the Grant, mint a new attempt, allocate its own authority epoch, reinterpret target or
payload scope, or create a second authorization lineage.

This corrects the older ADR-0008 target assumption that a future Runner-side claim store would own
one-time Grant consumption. That assumption was valid only before B4/C1-C5 were implemented.

## D1 contracts

D1 introduces two descriptive, non-authoritative contracts:

### `RunnerIdentity/v1`

A concrete Runner instance identity bound to:

- exact `runner_class`;
- provider and opaque provider instance ID;
- environment;
- exact rootfs digest;
- exact resource-limit profile digest;
- exact network-policy digest;
- versioned identity revision.

`runner_id` is the logical identity of one provider instance under one runner class/environment.
`identity_digest` is the content identity of the complete profile claim.

Possession of a valid `RunnerIdentity/v1` is **not authorization**, authentication, runtime
attestation, credential proof or proof that the provider actually enforced the claimed profile.
Those are separate Phase-D responsibilities.

### `RunnerBoundary/v1`

A safety-ceiling binding of one exact C4 lease, one exact `ExecutionCapsule`, one immutable
`CapabilityDefinition`, and one `RunnerIdentity`.

The D1 boundary fails closed unless:

- Runner class and environment match the current lease;
- lease `execution_capsule_digest` matches the exact capsule;
- Runner rootfs/resource/network profile digests match the capsule;
- capability definition identity, handler and target kind match the capsule;
- capability `effect_class == READ_ONLY`.

The contract hard-codes:

```text
effect_ceiling = READ_ONLY
network_egress_default = DENY_ALL
provider_mutation_allowed = false
```

These are required safety ceilings. They do not by themselves prove runtime enforcement.

## Phase D authority boundary

The Runner is an execution principal, not an authorization authority.

It MAY only act when an existing, current C4 lease and exact capsule are presented through the
released coordinator lineage. Any later runtime adapter must re-check the durable current epoch at
the worker/effect boundary. A stale worker cannot recover authority from a cached lease,
RunnerIdentity, credential, transport message or provider session.

`RunnerIdentity != VerifierIdentity` remains a hard architectural rule. Phase E introduces the
independent verifier and separate read credential.

## Read-only gate

Phase D is intentionally narrower than the eventual isolated Runner design.

Allowed:

- isolated process or microVM startup;
- bounded, immutable input retrieval;
- deterministic/local computation;
- provider READ calls for explicitly registered read-only capabilities;
- bounded observation evidence;
- completion through the current C4 epoch fence.

Forbidden:

- provider mutation;
- repository write, ref update, issue/PR mutation, deployment or release;
- filesystem writes outside an ephemeral Runner workspace;
- capability-selected shell or arbitrary interpreter execution;
- ambient credentials;
- unrestricted network egress;
- production effects;
- Runner-side authorization or authority widening.

The Phase-D gate is:

```text
NO PROVIDER MUTATION
```

## Network policy

The default egress posture is `DENY_ALL`.

A later read-only provider adapter may replace deny-all with an exact reviewed allowlist only when:

1. the allowed destination set is represented by an immutable network-policy artifact;
2. its digest is bound into the `ExecutionCapsule`;
3. the concrete Runner identity is bound to that exact digest;
4. the adapter exposes no general-purpose URL supplied by payload or model output;
5. credentials remain capability-scoped and read-only.

A network allowlist widens connectivity, not operation authority; it therefore still cannot make a
mutating capability Phase-D eligible.

## CredentialBroker handoff

D1 does not deliver credentials.

The next bounded slice is a `CredentialBroker` contract with these required properties:

- secret bytes never enter Grant, Dispatch, RunnerIdentity, RunnerBoundary, receipt or logs;
- credential scope is derived from the exact capability and target binding;
- Phase-D credentials are read-only;
- credentials are short-lived and bound to one current Runner/lease context;
- stale or superseded execution epochs cannot obtain or reuse credentials;
- no ambient environment credential fallback.

## Execution-provider abstraction — terminology supersession

The execution-provider abstraction remains provider-neutral, but **its canonical VOP name is the
isolated `Runner` boundary, not SandCloud**.

A provider adapter may use an implementation such as an isolated sandbox/microVM/container service,
but the V-One kernel depends only on versioned Runner contracts and their conformance tests. Changing
provider must not change authority semantics.

Canonical separation after ADR-0014:

```text
SandCloud    = governed non-canonical staging/review/validation/evidence
CASTER-MINAL = governed execution control surface
Runner       = isolated execution principal
V-One        = authority/governance semantics
```

None of these layers may silently inherit the authority of another.

At D1, no external isolated execution provider was activated by this ADR and no remote command was
executed.

## Crash and recovery semantics

Phase C durable truth remains authoritative across Runner failure:

- crash before Runner start: the lease may later expire and C4 may allocate a successor epoch;
- crash after Runner start but before observation: no provider mutation is possible in Phase D;
- stale Runner after successor epoch: any completion/effect boundary must reject the old epoch;
- duplicate transport: C3 dedup and C4 current-epoch state remain authoritative;
- provider session recovery never creates a new V-One attempt by itself.

## Consequences

Positive:

- Phase D begins from the actual released authority model;
- Runner identity cannot become hidden authority;
- read-only work can be introduced before any external mutation risk;
- runtime-provider selection stays replaceable;
- D2/D3 can be tested against a stable binding contract.

Costs:

- D1 is intentionally contract-first and does not yet execute remote work;
- concrete provider identity attestation remains unresolved until the provider adapter slice;
- CredentialBroker and network-policy enforcement are still required before a real provider READ.

## Historical next-slice sequence

At the time of this ADR the planned sequence was:

```text
D1 RunnerIdentity + READ-ONLY RunnerBoundary
  -> D2 CredentialBroker READ credential contract
  -> D3 isolated Runner runtime adapter
  -> D4 first real read-only capability
  -> Phase D gate: NO PROVIDER MUTATION
  -> Phase E independent verification
```

This sequence is historical decision context. Current product state is determined by canonical
`main`, not by this historical roadmap block.
