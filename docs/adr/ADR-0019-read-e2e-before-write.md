# ADR-0019 — Canonical READ E2E Before Provider WRITE

- Status: PROPOSED — governed adoption pending
- Date: 2026-08-24
- Scope: V-One provider-effect eligibility
- Decision class: Security / authority / release governance

## Context

V-One now has a merged canonical READ API, canonical trust-plane composition, independent verification contracts, and restart-safe durable resume. The next productization step is an explicit G8 provider runtime pack.

Activating provider WRITE before the same canonical route has repeatedly demonstrated real READ execution and recovery would create an unjustified authority asymmetry: the system would be allowed to mutate external state before its end-to-end read, continuity, and independent verification path had been proven as one operational unit.

## Proposed decision

Provider WRITE remains disabled until a canonical READ acceptance gate proves all of the following on the same product path:

1. authenticated HTTP admission;
2. current database-backed permission and workspace membership revalidation;
3. AuthorizationSnapshot and `ExecutionGrant/v2` issuance;
4. exactly-once `GrantConsumptionWitness/v1` consumption;
5. durable Outbox, DispatchEnvelope and Inbox admission;
6. an `ACTIVE` ExecutionEpoch with current Lease / ExecutionCapsule binding;
7. process interruption/restart while that durable execution is still `ACTIVE`, before Runner completion;
8. durable resume of the same execution from the persisted snapshot/grant/consumption/outbox/envelope/inbox/lease/capsule chain;
9. no second prepare, grant, grant consumption, outbox/envelope/inbox admission, epoch allocation, or lease acquisition during resume;
10. current-fence and authority-continuity validation after restart;
11. resumed isolated provider READ Runner execution;
12. durable completion of that resumed execution;
13. independent Verifier execution with separate identity/credential decision;
14. truthful `VerificationResult/v1`;
15. fail-closed behavior for missing, stale, corrupt, ambiguous, expired, revoked, or mismatched durable evidence.

The gate does **not** require resuming an already `COMPLETED` execution. Completed-execution recovery or reverification would be a separate future contract and is outside this ADR.

The proposed gate is:

```text
READ_E2E             = VERIFIED
RESTART_RESUME       = VERIFIED
NO_DUPLICATE_EFFECT  = VERIFIED
AUTHORITY_CONTINUITY = VERIFIED
INDEPENDENT_VERIFY   = VERIFIED
FAIL_CLOSED          = VERIFIED

WRITE_RUNTIME_GATE   = ELIGIBLE
```

Anything less keeps `WRITE_RUNTIME_GATE = BLOCKED`.

## Adoption gate

This candidate becomes effective only after all of the following are true for its exact immutable bytes:

```text
owner adoption decision recorded     = YES
exact-head ci / verify                = SUCCESS
product/documentation truth gates     = SUCCESS
fresh independent review              = CLEAN
blocking review threads               = 0
merge through protected main          = SUCCESS
external adoption record              = RECORDED
```

Until that adoption gate closes, this document creates no authority. The pre-existing fail-closed state remains stronger than the proposal: provider WRITE stays disabled and blocked.

V-One uses the non-self-referential adoption protocol in `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`. Therefore the exact reviewed ADR bytes remain `PROPOSED`; after merge, a separate governance-only adoption record must bind the exact candidate content commit and SHA-256 as `EFFECTIVE_STATUS: ADOPTED`. The adoption-record change must not modify this ADR. Repository presence, merge, or this document's self-declared status does not create adoption by itself.

No runtime or provider effect may depend on this candidate before that external adoption record is merged and effective.

## Non-conflation rule

Execution success is not verification success.

```text
execution.status      = SUCCEEDED
verification.verdict  = NOT_VERIFIED
```

is a valid truthful terminal state and must not be promoted to `VERIFIED` by receipts, hashes, evidence-chain integrity, or successful provider transport.

## G8 consequence

Once the decision is effectively adopted, the first default provider runtime pack is READ-only. It must:

- bind to the exact ProductComposition database and permission authority;
- reuse the canonical terminal-profile registry and current execution fence;
- use explicitly configured provider identity/credentials;
- keep Runner and independent Verifier identities/credential decisions separate;
- expose no ambient credential fallback;
- expose no generic execute path;
- expose no CREATE_REF, DELETE_REF, rollback, or other provider mutation transport;
- fail closed when configuration, credentials, identity separation, or runtime binding is incomplete.

## WRITE consequence

WRITE implementation may be designed and tested pre-effect, but provider mutation activation is not eligible until this decision is effectively adopted and the READ gate above is VERIFIED. A future WRITE activation requires its own ADR/gate, independent review, effect-specific credential scoping, post-state verification, rollback semantics, release authorization, and deployment authorization.

## Evidence and rollback

This proposed ADR creates no provider effect and no release/deployment authority. If adopted, it can be superseded only by a later explicit ADR that preserves or strengthens the safety properties above; silent weakening is forbidden.
