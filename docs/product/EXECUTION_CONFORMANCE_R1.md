# Execution Conformance R1

Status: IMPLEMENTATION CANDIDATE / REVIEW REQUIRED  
Runtime wiring: NONE  
Baseline: `main@cb0a97729c0c80ae91824f61d8904107a9ecf23c`  
Phase: B3 — Grant ↔ Capsule ↔ Handler/Runner-Class Conformance  
Owner adoption: NOT IMPLIED BY MERGE OR CI

## 1. Purpose

B3 proves that one authoritative `execution-grant/v2` still points to the exact
execution contract that repository-owned authorities consider active and eligible.

The invariant is:

```text
ExecutionGrant/v2
        ↓
ExecutionConformanceAuthority
        ↓
active ExecutionCapsule/v1
        ↓
HandlerConformanceEvidence/v1
        ↓
exact runner/precondition/handler/credential/verifier checks
        ↓
ExecutionConformanceWitness/v1
```

B3 does not execute code and does not consume a grant.

## 2. Why B3 exists

B1 content-binds an execution capsule digest, runner class and precondition enforcement
class into the grant.

B2 defines the actual `ExecutionCapsule/v1`, capsule activation and immutable capsule
registry.

Those two facts are necessary but not sufficient for a runtime handoff. A separate
conformance boundary is required so downstream code cannot silently:

- substitute another capsule;
- choose another handler;
- broaden the runner class;
- broaden the credential class;
- downgrade atomic precondition enforcement;
- replace the verification contract;
- use a revoked or inactive execution capsule.

B3 is that boundary.

## 3. Caller boundary

The B3 public authority accepts only:

```text
ExecutionGrant/v2
```

The caller does not supply:

- an `ExecutionCapsule`;
- capsule activation;
- capability activation;
- handler conformance evidence;
- handler digest;
- credential class;
- verification contract;
- atomic provider-condition evidence;
- a conformance result.

All execution-contract facts are resolved from immutable server-owned registries.

## 4. HandlerConformanceEvidence/v1

`HandlerConformanceEvidence/v1` content-binds one exact handler to one exact capsule.

It binds:

```text
capability_definition_identity
execution_capsule_digest
handler_id
handler_digest
runner_class
credential_class
precondition_enforcement_class
verification_contract_identity
atomic_provider_condition_contract_identity
evidence_revision
evidence_digest
```

The evidence registry rejects evidence that does not exactly match the referenced capsule.

This is conformance evidence, not runtime attestation and not post-state verification.

## 5. Atomic provider condition

A boolean such as:

```text
supports_atomic_condition = true
```

is intentionally insufficient.

For a capsule whose precondition enforcement is:

```text
ATOMIC_PROVIDER_CONDITION
```

handler evidence must contain a content-addressed:

```text
atomic_provider_condition_contract_identity
```

This identity represents the exact handler/provider contract that later B4/runtime work
must enforce, for example an exact CAS, ETag, version, generation or head-SHA condition.

For:

```text
READ_THEN_COMPARE
```

an atomic-condition contract identity is forbidden. The evidence may not claim a stronger
mechanism than the capsule requires.

B3 still does not prove that a future provider effect actually used the atomic condition.
That belongs at the execution boundary and later receipt/proof chain.

## 6. ImmutableHandlerConformanceRegistry

The registry is immutable and keyed by execution capsule digest.

At construction it checks exact equality between evidence and capsule for:

- capability-definition identity;
- capsule digest;
- handler id;
- handler digest;
- runner class;
- credential class;
- precondition enforcement class;
- verification contract identity.

Missing evidence fails closed when conformance is requested.

## 7. ExecutionConformanceAuthority

For one `ExecutionGrant/v2`, the authority:

1. resolves the exact active capsule from `ImmutableExecutionCapsuleRegistry`;
2. re-checks capability and capsule activation eligibility;
3. compares Grant ↔ Capsule bindings;
4. resolves exact handler conformance evidence;
5. enforces the atomic provider-condition contract requirement when applicable;
6. emits one content-addressed `ExecutionConformanceWitness/v1`.

The Grant ↔ Capsule comparison includes:

```text
execution_capsule_digest
capability_definition_identity
target_kind
runner_class
precondition_enforcement_class
```

Mismatch is fail-closed.

## 8. ExecutionConformanceWitness/v1

The witness binds:

```text
grant_digest
execution_binding_digest
execution_capsule_digest
capability_definition_identity
capability_activation_digest
capsule_activation_digest
handler_conformance_evidence_digest
target_kind
runner_class
handler_id
handler_digest
credential_class
precondition_enforcement_class
verification_contract_identity
atomic_provider_condition_contract_identity
conformance_authority_revision
witness_digest
```

The activation digests are included so the witness identifies the exact active authority
state used during the conformance decision.

## 9. What the witness proves

A structurally valid B3 witness proves only:

> At B3 evaluation time, this exact Grant/v2 matched the exact active capsule and exact
> registered handler-conformance evidence under this conformance authority revision.

It does not prove:

- the grant is still unconsumed;
- the grant has not expired since evaluation;
- revocation state has not changed;
- emergency stop remains inactive;
- a concrete Runner identity is authorized;
- credentials were correctly minted;
- a provider effect occurred;
- an atomic provider condition was actually applied;
- post-state was independently verified.

Those are later gates.

## 10. B4 requirement

B4 must not treat a historical B3 witness as sufficient runtime permission.

At durable one-time consumption B4 must re-check or atomically bind the current B3
conformance result together with:

- JTI / one-time consumption;
- grant expiry;
- live revocation;
- emergency stop;
- current capsule/capability activation;
- replay state.

This prevents a previously conformant but subsequently revoked capsule from remaining
runtime-eligible merely because an older witness exists.

## 11. Runner boundary

B3 intentionally validates only:

```text
runner_class
```

It does not introduce concrete `RunnerIdentity`.

A later runtime layer may select a concrete runner only if:

```text
actual_runner ∈ authorized_runner_class
```

The concrete workload identity, scoped credential and execution epoch belong to later
SandCloud/durable-dispatch work.

## 12. Credential boundary

The capsule and handler evidence bind the required:

```text
credential_class
```

B3 does not mint credentials and does not contain secrets.

A later credential broker may only produce credentials whose effective authority is no
broader than the Grant and whose class matches the B3-conformant capsule.

## 13. Verification boundary

The capsule and handler evidence bind the exact:

```text
verification_contract_identity
```

This does not perform verification.

The later independent verifier must remain a separate identity/credential path and must
observe real provider post-state.

## 14. Failure classes

B3 fails closed for at least:

```text
CAPSULE_NOT_EXECUTION_ELIGIBLE
GRANT_CAPSULE_BINDING_MISMATCH
HANDLER_CONFORMANCE_EVIDENCE_MISSING
ATOMIC_PROVIDER_CONDITION_CONTRACT_MISSING
```

Registry construction also rejects:

- evidence for an unknown capsule/capability;
- handler digest mismatch;
- handler identity mismatch;
- runner-class mismatch;
- credential-class mismatch;
- verification-contract mismatch;
- precondition-enforcement mismatch;
- invalid/tampered content digest;
- duplicate handler evidence.

## 15. Non-goals

B3 does not add:

- Grant persistence;
- JTI consumption;
- replay protection;
- schema migration;
- concrete Runner identity;
- credential minting;
- secrets;
- dispatch;
- outbox/inbox;
- leases;
- execution epoch/fencing;
- handler execution;
- provider mutation;
- `ExecutionReceipt/v2`;
- independent post-state verification;
- `OperationProof`;
- ProductService/ExecutionService runtime wiring;
- release;
- deployment;
- production effect.

## 16. Next gate

After B3:

```text
B4 Durable Grant Store + Atomic ONE_TIME Consumption
        ↓
JTI / replay protection
TTL / expiry
live revocation + emergency stop
fresh B3 conformance at consume
durable issuance/consumption evidence
        ↓
PHASE B EXECUTION AUTHORITY CONSUMPTION READY
```

Only after B4 should Phase C durable dispatch begin.

## 17. Acceptance evidence

B3 is review-ready only when exact-head CI passes the repository's complete `verify` job.

System evidence must demonstrate at minimum:

- exact Grant ↔ Capsule ↔ Handler success;
- content-addressed witness round trip;
- capsule-digest mismatch denial;
- runner-class mismatch denial;
- precondition-enforcement mismatch denial;
- revoked capability/capsule denial;
- exact handler evidence binding;
- atomic provider-condition contract requirement;
- no false atomic claim for read-then-compare;
- tamper and unknown-field rejection;
- no ProductService runtime wiring.

CI success does not authorize merge, runtime adoption, release, deployment or provider
effects.
