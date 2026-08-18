# F4a Write Runtime Activation and Pre-Effect Preflight R1

## Status

**IMPLEMENTED CONTRACT SLICE — NO LIVE MUTATION**

F4a defines the write-specific runtime metadata and the final fail-closed pre-effect validation required before a future `github.create-ref/v1` provider call. It does not implement or invoke the GitHub create-ref transport.

Canonical base for this slice:

`main@10ab6ef6e4979149fc0f7f1953739d533681bc13`

## Purpose

F1 froze the first bounded write capability and its create-only provider condition. F2 introduced `runner-boundary/v2` and `credential-access-decision/v2` for one staging-only, reversible, single-mutation execution. F3 bound the exact GitHub ref target and defined a create-only request/response transport contract.

F4a connects those contracts to a write-specific runtime boundary without creating a provider effect.

The governing rule remains:

> No provider effect may occur unless the already-consumed authority, durable dispatch, current lease, write Runner boundary, credential decision, exact target/request and runtime activation all resolve to one exact lineage immediately before the effect.

## `ephemeral-write-credential-delivery/v1`

Serializable provider/channel-reported metadata for one scoped out-of-band credential delivery. It binds the exact runtime provider instance, Runner and `runner-boundary/v2`, `credential-access-decision/v2`, GitHub audience and credential class, `WRITE_BOUNDED` / `CREATE_REF`, the credential validity window, delivery time and trusted clock witness digest, and `secret_material_exposed=false`.

The contract contains no token, secret bytes or secret handle. Constructing or parsing the value does **not** perform credential delivery and does not prove secret possession. A future live adapter must perform the actual out-of-band delivery while keeping secret material outside the evidence path.

## `write-runtime-activation/v1`

This is a new write-specific contract and does not reinterpret `read-only-runtime-activation/v1`.

It requires the exact runtime provider instance to equal `RunnerIdentity`; exact `runner-boundary/v2`, credential decision and delivery digests; exact C4 lease/execution epoch/capsule/capability identity; staging-only `github-actions.docker-isolated-write/v1`; workspace mount `READ_ONLY`; network default `DENY_ALL`; `WRITE_BOUNDED`; operation `CREATE_REF`; `provider_mutation_allowed=true`; and `max_provider_mutations=1`.

The write allowance is only the ceiling already established by F1/F2. It is not an ExecutionGrant, does not dispatch work and does not itself call a provider.

## `write-effect-preflight/v1`

Content-addressed readiness evidence for the complete authority/execution lineage immediately before a future provider effect:

```text
ExecutionGrant/v2
  -> GrantConsumptionWitness/v1
  -> DispatchOutboxEntry/v1
  -> DispatchEnvelope/v1
  -> DispatchInboxAdmission/v1
  -> ExecutionLease/v1
  -> RunnerIdentity/v1
  -> RunnerBoundary/v2
  -> CredentialBrokerPolicy/v2
  -> CredentialAccessDecision/v2
  -> EphemeralWriteCredentialDelivery/v1
  -> WriteRuntimeActivation/v1
  -> GitHubCreateRefRequest/v1
  -> CURRENT EFFECT FENCE
```

F4a revalidates exact grant-consumption identity, revocation epoch at consumption, consumption time inside the Grant validity window, outbox/envelope/inbox lineage, lease/admission lineage, Runner/credential/runtime bindings, exact target digest and the F3 request binding. A trusted clock rejects not-yet-valid or expired credential metadata.

`CurrentExecutionFence.assert_current(lease=...)` is intentionally the **last control-plane check**. F4b must rerun this preflight immediately before crossing the `GitHubCreateRefTransport.create_ref()` boundary. A previously produced preflight must never be treated as reusable write authority.

## Security invariants

1. `CREATE_REF` only.
2. `CREATE_ONLY` semantics remain owned by F1/F3.
3. Exact namespace remains `refs/heads/vone-canary/`.
4. Exactly one provider mutation maximum.
5. No update-ref, force-update or overwrite fallback.
6. Staging only; no production eligibility.
7. Workspace remains read-only.
8. Network posture remains deny-all by default.
9. Secret material never enters serialized evidence.
10. Activation/preflight is not an ExecutionReceipt and is not VerificationResult.

## NO LIVE MUTATION

This slice intentionally contains no concrete `GitHubCreateRefTransport`, no HTTP client, no GitHub provider WRITE, no ref creation/update/deletion, no actual credential/token material, no secret-channel implementation, no `ExecutionReceipt/v2`, no mutation `VerificationResult`, no `OperationProof`, and no release/deploy/production effect.

The existing D4b/E3/E4b live workflows remain READ/verification regression evidence only. They are not provider-write evidence for Phase F.

## F4b boundary

The first real provider mutation is a separate consequential gate. Before F4b may call create-ref it must provide a concrete reviewed runtime/credential adapter, obtain an exact scoped ephemeral credential out of band, run the F4a preflight against current durable state, and cross the provider boundary only once for the exact canary request. Independent provider readback and rollback evidence remain required after that effect; execution success alone must not be reported as `VERIFIED`.
