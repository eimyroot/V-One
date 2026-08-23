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
6. ExecutionEpoch / current Lease / ExecutionCapsule binding;
7. isolated provider READ Runner execution;
8. durable completion;
9. independent Verifier execution with separate identity/credential decision;
10. truthful `VerificationResult/v1`;
11. process restart followed by durable resume of the same execution;
12. no second prepare, grant, grant consumption, dispatch admission, or lease acquisition during resume;
13. current-fence and authority-continuity validation after restart;
14. fail-closed behavior for missing, stale, corrupt, ambiguous, expired, revoked, or mismatched durable evidence.

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

This ADR becomes `Accepted` only after all of the following are true on one unchanged PR head:

```text
owner adoption decision recorded     = YES
exact-head ci / verify                = SUCCESS
product/documentation truth gates     = SUCCESS
fresh independent review              = CLEAN
blocking review threads               = 0
merge through protected main          = SUCCESS
```

Until that adoption gate closes, this document creates no authority. The pre-existing fail-closed state remains stronger than the proposal: provider WRITE stays disabled and blocked.

After merge, a separate documentation-only change may update the ADR status from `PROPOSED` to `Accepted` only when the merge/adoption evidence is recorded. No runtime or provider effect may depend on an unmerged ADR status.

## Non-conflation rule

Execution success is not verification success.

```text
execution.status      = SUCCEEDED
verification.verdict  = NOT_VERIFIED
```

is a valid truthful terminal state and must not be promoted to `VERIFIED` by receipts, hashes, evidence-chain integrity, or successful provider transport.

## G8 consequence

The first default provider runtime pack is READ-only. It must:

- bind to the exact ProductComposition database and permission authority;
- reuse the canonical terminal-profile registry and current execution fence;
- use explicitly configured provider identity/credentials;
- keep Runner and independent Verifier identities/credential decisions separate;
- expose no ambient credential fallback;
- expose no generic execute path;
- expose no CREATE_REF, DELETE_REF, rollback, or other provider mutation transport;
- fail closed when configuration, credentials, identity separation, or runtime binding is incomplete.

## WRITE consequence

WRITE implementation may be designed and tested pre-effect, but provider mutation activation is not eligible until the READ gate above is VERIFIED. A future WRITE activation requires its own ADR/gate, independent review, effect-specific credential scoping, post-state verification, rollback semantics, release authorization, and deployment authorization.

## Evidence and rollback

This proposed ADR creates no provider effect and no release/deployment authority. If adopted, it can be superseded only by a later explicit ADR that preserves or strengthens the safety properties above; silent weakening is forbidden.