# ADR-0008: Isolated Runner Boundary v1

| Field | Value |
|---|---|
| Status | PROPOSED |
| Owner decision | REQUIRED |
| Date | 2026-08-02 |
| Decision owner | Repository owner |
| Required review | Independent architecture and security review |
| Scope | Target boundary between the V-One control plane and an isolated Runner v1 |
| Risk class | R3 — authorization, execution, isolation, and evidence trust boundary |
| Runtime effect | None; design only |
| Production effects | BLOCKED |

## Context

### Current state — VERIFIED at `main@e7eebf552d1849ef72ca4a89bb43043e2f5e39f6`

`ExecutionService` currently owns the database-bound execution lifecycle and invokes narrow
allowlisted adapters in process. Those adapters run under the control-plane operating-system
identity. The sandbox writer has path, symlink, file-type, and size controls, and validation uses
fixed presets, bounded output, a timeout, and a constrained environment. The current boundary has
no separate OS identity, capsule resource isolation, or network sandbox.

Current execution already has persisted idempotency, a lease and fence, emergency-stop recovery,
audit records, and local receipt-ledger records. Those controls are not a distributed Runner
protocol: there is no Runner heartbeat, remote cancellation acknowledgement, durable grant
consumption, or isolated postcondition verifier.

ADR-0007 accepts pure deterministic `execution-target/v1`, `approval-evidence-set/v1`,
`execution-grant/v1`, and `execution-receipt/v1` value contracts. They validate representation,
digests, and cross-contract bindings only. They perform no I/O, provide no authenticity, cannot be
issued authoritatively from current persisted approvals, and do not implement one-time consumption.

Production effects remain disabled. This ADR does not change that state.

### Target state — PROPOSED

V-One remains the authorization and execution-lifecycle authority. A separately identified Runner
accepts one short-lived grant, durably consumes it exactly once before any side effect, retrieves
only digest-bound inputs, executes exactly one registered capability in a rootless isolated
capsule, independently verifies the postcondition, and returns bounded evidence through the
receipt boundary.

This decision defines the boundary and required semantics. It does not select a transport,
orchestrator, capsule technology, signing algorithm, trust store, or secret broker.

## Decision drivers

- Remove execution from the control-plane OS identity and process boundary.
- Preserve V-One as the only authorization and execution-lifecycle authority.
- Make replay, duplicate delivery, stale workers, cancellation races, and uncertain outcomes fail
  closed or use a valid receipt status with outcome and postcondition `INDETERMINATE`.
- Keep capabilities narrow, versioned, reviewable, and independently verifiable.
- Prevent payload, target, secret, and evidence channels from becoming ambient authority.
- Introduce the boundary in reversible slices while production effects remain blocked.

## Authoritative ownership

| Concern | Authoritative owner | Runner responsibility | Forbidden shadow authority |
|---|---|---|---|
| Identity, session, permission, policy, and approval | V-One | Validate the exact grant binding required by the accepted protocol | Runner policy decisions or self-authorization |
| Grant issuance and cancellation intent | V-One | Reject invalid, stale, cancelled-before-consume, or unsupported work | Runner grant minting or scope expansion |
| Execution lifecycle and user-visible state | V-One | Report monotonic observations and receipts | Runner rewriting V-One lifecycle history |
| One-time consumption record | Runner-side durable claim store | Atomically claim one grant before side effects | In-memory-only replay tracking |
| Capability definition and release eligibility | Repository-owned, reviewed capability registry | Match an exact released registry entry and enforce its manifest | Handler-discovered or payload-selected commands |
| Capsule lifecycle and resource enforcement | Runner | Create, monitor, cancel, and destroy the capsule | Capability handler changing isolation policy |
| Payload and target bytes | Governed content-addressed stores selected by V-One policy | Fetch by immutable reference and verify digest before use | Grant-carried raw payloads, credentials, or mutable aliases |
| Postcondition definition | Approved capability manifest and request binding | Execute an independent verifier after the handler | Handler declaring its own success as proof |
| Receipt and execution evidence ledger | V-One | Produce bounded Runner receipt claims and evidence digests | Runner accepting its receipt as final authorization evidence |
| Knowledge and recommendations | CyberCore or another intelligence source | None | Intelligence source authorizing or executing work |

The Runner never authorizes itself. Structural validity, transport authentication, possession of a
grant, a digest match, or a successful handler exit is never sufficient authorization by itself.

## Component boundaries

```text
PROPOSED TARGET — not implemented

[V-One authorization + lifecycle authority]
          |
          | immutable execution dispatch reference
          v
[Durable dispatch/outbox boundary]
          |
          v
[Runner ingress + grant verifier]
          |
          v
[Durable one-time grant claim + lease/fence store]
          |
          +---- cancel/lease observations ---- [V-One]
          |
          v
[Content-addressed payload/target retrieval]
          |
          v
[Released capability registry]
          |
          v
[Independent precondition verifier]
          |
          v
[Target gateway with atomic expected-version / fence enforcement]
          |
          v
[Rootless isolated capsule under separate OS identity]
          |
          v
[Independent postcondition verifier]
          |
          v
[Bounded evidence + execution-receipt/v1]
          |
          v
[V-One receipt ingestion, lifecycle reconciliation, audit]
```

The dispatch channel carries immutable references and correlation identifiers, not ambient
credentials or raw secrets. Duplicate and out-of-order delivery is expected and must be safe.

## Data flow

1. V-One persists an execution intent only after authoritative identity, permission, policy,
   approval, environment, and production-effect gates succeed.
2. A future authoritative issuer binds the request, payload digest, target digest, capability,
   policy version, approval evidence, execution ID, expiry, and one-time semantics into the grant.
3. The outbox exposes an immutable dispatch reference. Transport redelivery does not create a new
   attempt or a new grant.
4. Runner ingress authenticates the protocol peer when that mechanism is defined, strictly parses
   all contracts, verifies cross-contract bindings, rejects unsupported versions, and checks
   cancellation, expiry, registry, environment, and local admission gates.
5. The Runner atomically consumes the grant and creates the attempt lease/fence in one durable
   transaction before any payload fetch that can mutate state or any capability side effect.
6. The Runner retrieves payload and target material only through approved content-addressed
   adapters, enforces size/type/depth limits, and recomputes exact digests before capsule exposure.
7. The registry resolves one exact versioned capability to a fixed handler, isolation profile,
   input schema, target kinds, network policy, resource limits, and independent precondition and
   postcondition verification plans.
8. After consume and immediately before any possible side effect, an independent precondition
   verifier observes the target and validates the authorized expected state, version, ETag, digest,
   or equivalent concurrency token.
9. The governed target gateway atomically enforces that expected state and the current fence at
   mutation time. A capability whose target cannot provide compare-and-swap, conditional mutation,
   or an independently reviewed equivalent remains blocked for mutating use.
10. The Runner creates a fresh rootless capsule with a read-only base and bounded writable
    workspace, executes one attempt, and records bounded observations.
11. After execution, cancellation, timeout, or handler failure, the independent postcondition
    verifier observes the target without executing handler- or payload-provided verification code.
12. The Runner emits one terminal receipt claim bound to the grant and evidence digests. V-One
    validates and ingests it, reconciles lifecycle state, and retains authoritative audit history.

Secrets are never fields in a grant, receipt, dispatch record, or log. If a future capability
requires a secret, a separately approved broker decision must deliver a short-lived,
capability-scoped value directly to the capsule without making it retrievable through evidence.

## Runner internal lifecycle and receipt mapping

Internal Runner lifecycle states are not `ExecutionReceipt.status` values. The Runner records its
internal state separately and maps exactly one terminal observation to the accepted
`execution-receipt/v1` status, outcome, and postcondition fields.

```text
RECEIVED
  -> REJECTED                         invalid, stale, cancelled, unknown, or unsupported
  -> CONSUMED                         durable atomic one-time claim; attempt count becomes one

CONSUMED
  -> PREPARING                        digest-bound retrieval and capsule preflight
  -> CANCELLED_BEFORE_EFFECT          consumed attempt; cancellation observed before mutation

PREPARING
  -> RUNNING                          precondition passed; current lease/fence; mutation may begin
  -> PREFLIGHT_FAILED                 determined retrieval, isolation, or precondition failure
  -> PREPARATION_UNCERTAIN            preparation or target observation cannot be established

RUNNING
  -> VERIFYING                        handler ended, failed, timed out, or cancellation was sent
  -> WORKER_INTERRUPTED               worker, lease, fence, or capsule state was lost
  -> WORKER_TIMED_OUT                 bounded execution deadline expired

VERIFYING
  -> EFFECT_VERIFIED                  independent postcondition passed
  -> EFFECT_NOT_VERIFIED              independent postcondition failed with known post-state
  -> CANCELLED_KNOWN                  cancellation with a known non-success post-state
  -> POST_STATE_UNCERTAIN             post-state cannot be established

Any internal terminal state -> RECEIPT_PENDING -> RECEIPT_RECORDED
```

Normative receipt mapping:

| Internal terminal observation | Receipt `status` | `outcome` | `postcondition_status` |
|---|---|---|---|
| Admission rejected before consume | `REJECTED` | `EXPECTED_EFFECT_NOT_VERIFIED` | `NOT_RUN` |
| Effect independently verified | `SUCCEEDED` | `EXPECTED_EFFECT_VERIFIED` | `PASSED` |
| Known failed effect or consumed preflight failure | `FAILED` | `EXPECTED_EFFECT_NOT_VERIFIED` | `FAILED` |
| Execution deadline expired with uncertain post-state | `TIMED_OUT` | `INDETERMINATE` | `INDETERMINATE` |
| Worker, lease, fence, or capsule state lost | `INTERRUPTED` | `INDETERMINATE` | `INDETERMINATE` |
| Cancellation with known non-success post-state | `CANCELLED` | `EXPECTED_EFFECT_NOT_VERIFIED` | `FAILED` |
| Cancellation with uncertain post-state | `CANCELLED` | `INDETERMINATE` | `INDETERMINATE` |

`INDETERMINATE` is never an execution receipt status. It is used only as the receipt outcome and
postcondition status permitted by ADR-0007. Terminal delivery may be retried, but it must reproduce
or reference the same terminal receipt identity. No terminal state returns to `RECEIVED`, and
recovery never creates a second attempt from the same grant.

## One-time consumption semantics

- One grant authorizes exactly one execution attempt, not one successful execution.
- `grant_id` is the sole durable uniqueness key for consumption.
- The first atomic claim stores `grant_digest` as an immutable binding of that `grant_id`.
- Every later delivery of the same `grant_id` must present the identical `grant_digest`. A different
  digest is an integrity violation and cannot create a second claim, attempt, or receipt identity.
- Lookup, digest comparison, claim insertion, and attempt creation occur in one serializable
  transaction or an equivalent atomic operation before any side effect.
- After consumption, validation, retrieval, capsule startup, handler failure, cancellation, timeout,
  or Runner crash cannot make the grant reusable.
- Duplicate delivery returns the existing rejection/attempt/terminal reference and never invokes a
  handler again.
- An unconsumed expired or pre-cancelled grant is rejected without an attempt. A consumed grant
  always consumes its single attempt even if no external mutation is observed.
- Administrative recovery may reconcile evidence or mark the outcome `INDETERMINATE`; it cannot
  reset consumption. Retrying requires a new authorization decision and a new grant.

## Cancellation, leases, and fencing

- V-One owns cancellation intent; the Runner owns best-effort capsule termination and reports what
  it observed. Cancellation is not rollback and does not prove absence of side effects.
- Admission checks cancellation before consume. After consume, the Runner records cancellation,
  prevents not-yet-started side effects where possible, revokes the capsule lease, and fences stale
  workers.
- Each consumed attempt has a monotonic fence token. Any handler-side mutating gateway and every
  Runner state transition must reject a stale fence.
- A lease is bounded and renewed only by the active Runner while its fence remains current.
  Heartbeat is evidence of liveness, not authorization extension; grant expiry still bounds attempt
  start.
- Lease expiry prevents further authorized work by the stale worker. It does not prove the external
  effect stopped. Recovery therefore verifies post-state and uses `INDETERMINATE` when uncertain.
- If a target cannot enforce fencing at its mutation boundary, that capability remains blocked for
  mutating use unless an R3 review accepts a concrete compensating design.

## Payload and target retrieval boundaries

- Grants carry digests and opaque immutable references only; they do not carry raw payloads,
  target claims, credentials, provider tokens, or unrestricted URLs.
- Retrieval is pull-by-digest through an allowlisted adapter. Mutable aliases, redirects outside an
  allowlist, local arbitrary paths, package-provided fetchers, and caller-selected protocols fail
  closed.
- The Runner validates declared and actual byte count, media type, schema, canonical form where
  required, nesting, file count, and decompression ratio before use.
- The retrieved bytes are rehashed inside the Runner boundary and must match the grant bindings.
- Target resolution yields a typed target handle constrained to the capability and workspace; it
  never yields ambient provider administration.
- Retrieval credentials, if later approved, are short-lived, audience-bound, read-only, redacted,
  and unavailable to the capability handler.

## Precondition verification and target-drift controls

- The expected pre-state, target version, ETag, digest, generation, or equivalent concurrency token
  must be derived from the authoritative request and approval evidence and bound to the execution
  authorization. It must never be invented by the Runner or handler.
- The independent precondition verifier runs after durable consume and retrieval, but immediately
  before the first possible side effect.
- The handler cannot select, implement, override, or attest its own precondition verifier.
- The governed target gateway must atomically enforce both the expected target version/state and the
  current fence at mutation time. A read-then-write check without conditional mutation is
  insufficient.
- Drift detected before mutation produces no side effect and a fail-closed terminal result.
  Missing, stale, conflicting, or unprovable pre-state is never treated as success.
- If a provider cannot enforce compare-and-swap, conditional requests, version matching, or an
  independently reviewed equivalent, the mutating capability remains blocked.
- Precondition observations are bounded, freshness-qualified evidence and must not contain secrets.

## Capability registry rules

- A capability identifier is canonical and versioned. Syntax-valid but unknown capabilities fail
  closed.
- Arbitrary shell, command strings, interpreters selected by payload, and generic script execution
  are not capabilities.
- The registry is repository-owned, reviewable, immutable per released version, and the only
  mapping from capability ID to handler and security profile.
- Each entry declares exact input schema, allowed target kinds and environments, side-effect class,
  handler artifact digest, capsule image/root filesystem identity, resource limits, filesystem
  mounts, network policy, secret requirements, timeout, idempotency/fencing expectations, and
  independent precondition and postcondition verifiers.
- The grant issuer and Runner must both recognize the exact registry version and capability. Their
  disagreement fails closed; neither may silently downgrade or select a nearest version.
- No dynamic plugin discovery, PATH lookup, payload-selected executable, or handler fallback is
  permitted in v1.
- Every mutating capability remains ineligible for production while production effects are blocked.

## Capsule isolation requirements

Each attempt receives a fresh capsule with:

- a Runner OS identity separate from the control plane and no control-plane database or Unix socket
  access;
- rootless execution, no privileged mode, no host namespaces, no device access, no privilege
  escalation, and a minimal capability set that is empty by default;
- a read-only immutable base filesystem identified by digest;
- a fresh bounded writable workspace mounted only where declared, with quota and deterministic
  teardown; no repository, home directory, container socket, or host-root mount;
- CPU, memory, PID, file-size, open-file, process, and wall-clock limits;
- network deny by default. Any exception is per-capability, destination/protocol/port constrained,
  time bounded, observable, and separately reviewed;
- a minimal fixed environment, no inherited control-plane environment, and redacted structured
  output limits;
- isolation failure, unsupported platform primitives, or cleanup uncertainty causing fail-closed
  admission or a valid terminal receipt status with outcome and postcondition `INDETERMINATE`, never
  a less isolated fallback.

These are acceptance requirements, not claims about the current runtime.

## Postcondition verification

- Handler completion, exit code, output text, and provider acknowledgement are observations, not
  proof of the expected effect.
- The verification plan is bound through the approved capability/request data and is executed by a
  verifier independent from the handler entry point.
- The verifier is read-only, has separately minimized credentials and network access, and cannot
  execute code supplied by the payload, target, handler, or produced workspace.
- Verification compares an independently observed post-state with the approved expected effect and,
  where relevant, the pre-state and fence.
- `PASSED` is the only basis for `EXPECTED_EFFECT_VERIFIED` and `SUCCEEDED`.
- A known non-matching post-state yields `FAILED` / `EXPECTED_EFFECT_NOT_VERIFIED`.
- Missing, conflicting, stale, partial, timed-out, or otherwise uncertain evidence requires a
  valid receipt status with outcome and postcondition `INDETERMINATE`; it must never be coerced to
  success or ordinary failure.

## Receipt lifecycle

1. `REJECTED` receipt: admission failed before consume; postcondition is `NOT_RUN`.
2. Attempt receipt: after consume, exactly one terminal Runner receipt identity describes the
   attempt and binds the exact grant, Runner identity, timestamps, status, outcome, output digest,
   and postcondition digest as defined by ADR-0007.
3. Delivery: receipt transport may retry. V-One deduplicates by Runner receipt identity and rejects
   conflicting bytes or cross-grant bindings.
4. Ingestion: V-One validates the full contract and, when future authenticity work is accepted, its
   envelope. A parsed or digest-valid receipt alone is not trusted evidence.
5. Reconciliation: V-One maps the accepted receipt to its authoritative lifecycle and local receipt
   ledger without conflating the Runner receipt ID with the ledger entry ID.
6. Evidence retention: raw output and postcondition observations remain bounded external evidence
   referenced by digest, with authorization, retention, redaction, and integrity controls.
7. Missing receipt: lease expiry or loss triggers investigation and independent postcondition
   verification. It never permits grant reuse; uncertainty is `INDETERMINATE`.

Signed envelopes and trust-store semantics remain an open, separately reviewed R3 decision. This
ADR does not call digest-only receipts signed or authenticated.

## Mandatory security invariants

- Runner never authorizes itself.
- Arbitrary shell is not a capability.
- Unknown capability fails closed.
- One grant equals one execution attempt.
- Grant consumption is atomic and durable before any side effect.
- Network is denied by default.
- Runner uses an OS identity separate from the control plane.
- Every capsule is rootless with a bounded writable workspace.
- Secrets are absent from grants, receipts, dispatch records, logs, and general evidence.
- Precondition verification is independent from the capability handler and runs immediately before
  mutation.
- The target gateway atomically enforces the authorized expected state/version and current fence;
  providers without an enforceable conditional mutation or approved equivalent remain blocked.
- Postcondition verification is independent from the capability handler.
- `INDETERMINATE` is used only as receipt outcome and postcondition status, never as receipt status.
- Production effects remain disabled.

## Rollout blockers

Implementation and all mutating rollout remain BLOCKED until the relevant phase has current
evidence for:

- authoritative persisted approval bindings sufficient to issue ADR-0007 grants without invented
  facts;
- a separately accepted authorization binding for expected pre-state/version, because ADR-0007 does
  not currently carry a pre-state digest or concurrency token;
- accepted transport, peer-authentication, signed-envelope, key lifecycle, and trust-policy ADRs;
- durable transactional outbox and Runner-side atomic consumption/replay store semantics;
- an accepted capability registry owner, schema, release process, and at least one non-production
  capability profile;
- demonstrated separate OS identity, rootless isolation, read-only base, bounded workspace,
  resource limits, and network deny-by-default on every supported platform;
- cancellation, heartbeat, lease-expiry, fence, duplicate-delivery, stale-worker, and crash-recovery
  tests;
- governed content-addressed retrieval and secret-broker decisions where needed;
- independent precondition verifier contracts, target-side conditional mutation/fencing, and
  target-drift adversarial tests;
- independent postcondition verifier contracts and adversarial tests;
- bounded/redacted evidence storage, receipt ingestion, reconciliation, and operator recovery;
- independent R3 architecture and security review with no unresolved critical finding;
- production effects remaining disabled through implementation and pilot verification. Enabling any
  production effect requires a separate R4 owner decision, release authorization, and evidence.

## Migration order

Each phase is a separate reviewable and reversible decision; no phase silently authorizes the next.

1. Preserve the current local execution path and production block while defining test vectors and
   lifecycle invariants for ADR-0007 contracts.
2. Add authoritative approval/payload/target/policy persistence and invalidation semantics.
3. Add a transactional outbox and no-effect dispatch consumer that can only reject or acknowledge
   test grants.
4. Add the durable atomic consumption, lease, fence, cancellation, and duplicate-delivery state
   machine with an inert capability only.
5. Add content-addressed retrieval and the reviewed capability registry with no arbitrary shell and
   no secrets.
6. Add independent precondition verification and target-side expected-version/fence enforcement;
   keep mutating capabilities blocked where atomic conditional mutation is unavailable.
7. Demonstrate rootless capsules under a separate OS identity, bounded workspace, resource limits,
   and network deny-by-default using an inert non-production capability.
8. Add independent postcondition verification and receipt ingestion/reconciliation; exercise crash,
   timeout, cancellation, lost-receipt, and uncertain post-state paths.
9. Run a default-off non-production pilot, compare Runner evidence with current lifecycle evidence,
   and complete independent R3 review.
10. Retire an equivalent in-process adapter only after the Runner path meets all acceptance gates and
    the focused rollback is demonstrated.
11. Consider production effects only as separate R4 work; they are not part of Runner boundary v1.

## Rollback

For this design-only change, remove or revert only:

- `docs/adr/ADR-0008-isolated-runner-boundary-v1.md`;
- `docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md`;
- the TB-11 and related map additions in `docs/architecture/TRUST_BOUNDARIES.md`.

There is no runtime, database, API, configuration, dependency, release, deployment, or production
rollback. Future implementation phases must each define their own non-destructive rollback while
keeping consumed grants and audit evidence immutable.

## Consequences

### Positive

- Authorization, execution, and evidence ownership remain explicit.
- Replay and redelivery have deterministic one-attempt semantics.
- Isolation, cancellation, verification, and uncertainty become acceptance gates rather than
  implied properties.
- Capability and retrieval boundaries prevent the Runner from becoming a generic remote shell.

### Negative and residual

- The target requires durable distributed state and operational recovery not present today.
- A separate OS identity and rootless capsule reduce blast radius but do not eliminate kernel,
  runtime, provider, or same-target race risk.
- End-to-end authenticity, key lifecycle, secret delivery, and target-side fencing remain open R3
  decisions.
- Some providers cannot prove exactly-once effects; the boundary guarantees one local attempt and
  requires idempotency/fencing or blocks the capability.

## Explicit non-scope

This decision does not authorize or implement:

- runtime code, a Runner service, capsule runtime, transport, or service wiring;
- database migrations, outbox tables, grant stores, APIs, or public contract changes;
- signing, envelopes, trust stores, key management, algorithms, or crypto dependencies;
- secret broker implementation or provider credential distribution;
- a concrete orchestrator, container engine, VM, namespace, or operating-system technology;
- new dependencies;
- migration of current adapters or execution traffic;
- CyberCore integration or authorization authority;
- arbitrary shell or package-provided execution;
- production effects;
- commit, push, branch creation, pull request, merge, release, deployment, or production change.
