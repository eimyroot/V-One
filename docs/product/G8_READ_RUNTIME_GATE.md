# G8 — Explicit READ-Only Provider Runtime Gate

## Purpose

G8 productizes the first default provider runtime pack without widening provider-effect authority. The first pack is READ-only and exists to prove the canonical HTTP → trust-plane → restart-safe Runner → independent Verifier → `VerificationResult/v1` lifecycle as one real operational path.

## Preconditions

```text
G0_GITHUB_GOVERNANCE = PASS
G7_CANONICAL_API = MERGED
G7_DURABLE_RESUME = MERGED
G7_RUNTIME_RESUME_WIRING = MERGED
PRODUCTION_WRITE_EFFECTS = DISABLED
```

## Required runtime bindings

The G8 runtime pack must share the exact canonical objects used by ProductComposition:

- ProductService database;
- DatabasePermissionAuthority;
- terminal-profile registry;
- envelope revision;
- DurableCurrentExecutionFence;
- canonical READ terminal contracts.

Any parallel database, permission authority, profile registry, fence, execution coordinator, or legacy fallback is rejected.

## Identity and credential separation

Runner and independent Verifier must have distinct identities and distinct credential decisions. Credential bytes are never serialized into V-One evidence objects.

The runtime must not fall back to ambient shell credentials, developer-local Git state, legacy `ExecutionService`, or a generic provider client with mutation permission.

Missing/ambiguous configuration fails closed.

## Authority ceiling

G8 R1 exposes only the exact canonical READ capability:

```text
terminal_profile = READ_ONLY_VERIFIED
capability       = github.read-ref/v1
```

The default runtime pack must contain no provider mutation transport and no callable CREATE_REF, DELETE_REF, rollback, generic execute, or arbitrary API method surface.

## Acceptance sequence

A G8 candidate is not product-ready until one exact candidate head demonstrates:

```text
1. full repository CI / verify = SUCCESS
2. product readiness = SUCCESS
3. dependency audit = SUCCESS
4. image build + smoke = SUCCESS
5. authenticated canonical HTTP admission = SUCCESS
6. durable canonical preparation/admission reaches ACTIVE epoch + current lease/capsule = VERIFIED
7. process interruption/restart occurs before Runner completion = VERIFIED
8. durable resume reconstructs the same execution while ACTIVE = SUCCESS
9. no duplicate prepare/grant/consume/outbox/envelope/inbox/epoch/lease = VERIFIED
10. resumed governed real READ Runner = SUCCESS
11. durable completion of resumed execution = SUCCESS
12. independent Verifier observation with separate identity/credential decision = SUCCESS
13. VerificationResult/v1 evaluation = SUCCESS
14. authenticated canonical HTTP READ E2E = SUCCESS
15. failure injection / corrupt or revoked durable evidence = FAIL-CLOSED
16. fresh independent R3 review = CLEAN
```

The restart gate explicitly exercises the existing `ACTIVE`-execution resume contract. It does not require or claim resumption of an already `COMPLETED` execution.

Repeated READ E2E evidence must be retained before ADR-0019 can make WRITE runtime merely `ELIGIBLE`.

## Non-scope

- no CREATE_REF provider call;
- no DELETE_REF provider call;
- no rollback effect;
- no generic provider mutation client;
- no production WRITE;
- no completed-execution recovery/reverification contract;
- no release;
- no deployment;
- no weakening of ADR-0019.

## Exit state

G8 R1 may only claim:

```text
DEFAULT_READ_PROVIDER_RUNTIME = IMPLEMENTED / VERIFIED
REAL_CANONICAL_READ_E2E       = VERIFIED
WRITE_RUNTIME_GATE            = BLOCKED or ELIGIBLE per ADR-0019 evidence
```

It must not claim release, deployment, unrestricted provider authority, or production WRITE.
