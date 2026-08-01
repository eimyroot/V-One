# ADR-0007: Pure Execution Grant and Runner Receipt Contract v1

| Field | Value |
|---|---|
| Status | ACCEPTED |
| Owner decision | ACCEPTED |
| Date | 2026-07-31 |
| Decision owner | Repository owner |
| Scope | Pure canonical contracts between V-One authorization and a future isolated Runner |
| Risk class | R3 — authorization, execution, and evidence trust boundary |
| Runtime effect | None |

## Context

V-One currently owns identity, permission checks, change requests, approvals, execution lifecycle,
audit, and receipt-ledger evidence. Current execution uses narrow in-process adapters under the
control-plane operating-system identity. The isolated Runner remains target architecture.

The current approval persistence records an approval identifier, request identifier, approver,
decision, reason, and timestamp. It does not bind an approval to the request payload digest,
target digest, capability, policy version, or approval expiry. V-One therefore cannot yet issue an
authoritative v1 grant from current persisted approvals without inventing facts.

ADR-0006's Policy Decision Graph remains an unsigned, caller-supplied informational projection. A
PDG decision, graph digest, or permission observation is not authorization and cannot be used as
an execution grant.

## Decision

The repository accepts four pure deterministic internal contracts in
`voodoo_product/execution_contract.py`:

- `execution-target/v1`;
- `approval-evidence-set/v1`;
- `execution-grant/v1`;
- `execution-receipt/v1`.

The module performs validation, canonical serialization, digest calculation, and cross-contract
binding checks only. It performs no I/O and has no persistence, API, service, execution-adapter,
Runner, signing, PDG, or CyberCore authority.

This contract slice creates no runtime authorization. Current execution behavior is unchanged.

## Canonical representation and digest rules

Contracts use the existing deterministic `canonical_json` evidence primitive over a constrained
JSON domain. Every contract has `schema_version: 1` and its own versioned type field. Top-level
parsing rejects missing and unknown fields. Identifiers, capability syntax, timestamps, enums, and
digests are validated fail closed.

Each digest is:

```text
SHA-256(canonical_json(contract_without_its_own_digest_field))
```

SHA-256 values are exactly 64 lowercase hexadecimal characters. Timestamps are timezone-aware,
normalized UTC ISO 8601 values with millisecond precision. Hashing provides deterministic identity
and change detection; it is not a signature or proof that supplied facts are authoritative.

## Execution target

`execution-target/v1` contains:

- `target_kind`;
- opaque canonical JSON `target_claims`;
- `target_digest`.

The raw target claims are never embedded in a grant. The issuer and future Runner own semantic
target-kind and target-claims allowlisting. This pure contract validates representation and digest
identity only.

Target claims must not contain secrets, credentials, raw request payloads, or unnecessary personal
data.

## Approval evidence set

`approval-evidence-set/v1` binds:

- request ID;
- payload digest;
- target digest;
- canonical versioned capability;
- policy version;
- immutable approved records and distinct approver identities;
- approval validity deadline;
- approval-set digest.

Approval records are deterministically ordered by approval ID, approver ID, and approval timestamp.
Only `APPROVED` records are accepted. Approval and approver identifiers must be distinct. Approval
timestamps cannot be later than the set's validity deadline.

This is a contract for evidence that a future authoritative issuer must possess. It does not
retroactively add these bindings to current persisted approval rows.

## Execution grant

`execution-grant/v1` binds:

- grant, execution, request, actor, and workspace identities;
- environment;
- canonical versioned capability;
- target kind and target digest;
- payload digest;
- approval-set digest and policy version;
- required permission `execution.run`;
- issue and expiry timestamps;
- `ONE_TIME` use semantics;
- grant digest.

Grant construction and explicit cross-contract validation require exact agreement with the supplied
target and approval evidence. Grant expiry must be later than issue time, no more than 300 seconds
after issue, and no later than approval validity. Every bound approval must already exist when the
grant is issued: the latest `approved_at` must be no later than `issued_at`.

`ExecutionGrant.from_dict` performs strict structural and self-digest validation only. It cannot
establish approval causality or provenance from grant claims alone. Authoritative acceptance must
also call `validate_bindings` with the exact `execution-target/v1` and
`approval-evidence-set/v1` objects.

Capability validation checks canonical identifier syntax only. Capability and adapter allowlisting
remain issuer and Runner responsibilities; this module does not introduce a shadow capability
registry.

`ONE_TIME` is a normative use constraint. Atomic consumption and durable replay prevention belong
to the future isolated Runner boundary and are not implemented by this pure value contract.

The raw request payload and raw target claims never appear in the grant. Payload delivery and
content-addressed retrieval remain future integration work.

## Runner receipt

`execution-receipt/v1` binds:

- a distinct `runner_receipt_id`;
- grant ID and grant digest;
- execution ID;
- Runner identity;
- execution status and outcome;
- start and completion timestamps;
- output digest;
- postcondition status and digest;
- receipt digest.

Completion cannot precede start. Output and postcondition digests bind external bounded evidence;
raw output, raw payload, secrets, and target claims do not belong in this receipt.

Every receipt requires explicit cross-contract validation against the exact grant. Grant ID, grant
digest, and execution ID must match. For `SUCCEEDED`, `FAILED`, `INTERRUPTED`, `TIMED_OUT`, and
`CANCELLED`, `started_at` represents an attempted or performed execution and must fall inclusively
within the grant's issue and expiry timestamps.

`REJECTED` means the Runner did not attempt the capability. Its timestamps record rejection
evaluation and may fall outside the grant validity window, including rejection of a not-yet-valid
or expired grant. It must use `EXPECTED_EFFECT_NOT_VERIFIED` with `NOT_RUN`.

Result semantics are fail closed:

- `EXPECTED_EFFECT_VERIFIED` and `PASSED` are equivalent evidence claims and require
  `status=SUCCEEDED`;
- `EXPECTED_EFFECT_NOT_VERIFIED` with `FAILED` records a determined failure to verify the expected
  effect;
- `INDETERMINATE` outcome and postcondition status must appear together when available evidence
  cannot establish the post-state;
- `NOT_RUN` is reserved for `REJECTED`; it cannot describe an attempted execution.

`ExecutionReceipt.from_dict` performs structural and self-digest validation only. Authoritative
acceptance must additionally call `validate_bindings` with the exact `ExecutionGrant`.

`runner_receipt_id` identifies the future Runner's claims. It is intentionally distinct from the
current V-One `ReceiptLedger` entry ID, which identifies a local ledger record and chain link.
Future ingestion may reference both identities but must not conflate them.

## Signed envelope semantics

A signed envelope, trust store, key identity format, algorithm selection, rotation, revocation, and
verification policy remain **PROPOSED** future R3 work.

This ADR does not select or freeze an algorithm, key format, envelope representation, or crypto
dependency. It implements no signing or verification. A digest alone must never be described as a
signature or authentication.

## Security invariants

- malformed, missing, unknown, stale, or cross-boundary-inconsistent claims fail closed;
- digest fields exclude only their own digest field;
- grants require `execution.run`, `ONE_TIME`, positive TTL, at most 300 seconds, and approval
  freshness;
- all approvals precede or equal grant issuance;
- grant target, request, payload, capability, policy, and approval-set bindings are immutable;
- attempted execution starts within the grant validity window; `REJECTED` records no attempt;
- receipt status, outcome, and postcondition claims cannot contradict each other;
- authoritative receipt acceptance binds grant ID, grant digest, execution ID, and temporal scope;
- structural parsing alone never establishes cross-contract authorization;
- grant and receipt contain no raw request payload, raw target claims, raw output, or secrets;
- arbitrary shell is not a capability supplied or authorized by this contract;
- semantic capability and target allowlisting remains outside the pure representation module;
- PDG and CyberCore remain informational/proposal sources with no authorization authority;
- production effects remain disabled and are not enabled by this decision.

## Verification

Focused tests cover deterministic target, approval-set, grant, and receipt digests; digest changes
for security-relevant bindings; strict parsing; malformed digests; timestamp ordering; grant TTL;
approval freshness; permission and one-time invariants; canonical capability syntax without runtime
allowlisting; approval ordering and causality; grant and receipt cross-contract mismatches; receipt
grant-window enforcement; result consistency; raw-payload exclusion; and distinct Runner receipt
identity.

The full repository gates remain required because this is an R3 contract even though the module is
not wired into runtime behavior.

## Consequences

### Positive

- V-One and a future Runner receive one reviewable versioned claims vocabulary;
- deterministic test vectors can be shared without adding a dependency;
- missing current authoritative approval bindings remain explicit;
- the contract is independently reversible and cannot affect current execution.

### Negative and residual

- current persistence cannot issue an authoritative grant;
- signature authenticity, trust, replay prevention, payload transport, and Runner isolation remain
  unimplemented;
- constrained syntax does not establish semantic capability or target safety;
- a caller can construct internally consistent claims from false inputs.

## Rollback

Remove or revert only:

- `voodoo_product/execution_contract.py`;
- `tests/system/test_execution_contract.py`;
- this ADR.

There is no migration, persisted state, configuration, API, runtime, release, or deployment
rollback.

## Non-scope

This decision does not authorize:

- database migrations or persistence changes;
- API, service, composition, or execution-runtime wiring;
- isolated Runner implementation;
- signing, envelope, trust-store, key, or crypto implementation;
- dependency changes;
- production effects;
- CyberCore integration;
- public API changes;
- commit, publication, pull request, merge, release, or deployment.
