# Isolated Runner Threat Model v1

| Field | Value |
|---|---|
| Status | PROPOSED |
| Date | 2026-08-02 |
| Scope | Target isolated Runner boundary defined by ADR-0008 |
| Risk class | R3 |
| Current runtime effect | None |
| Production effects | BLOCKED |
| Review requirement | Independent security and architecture review before implementation |

## Scope and security objective

This threat model covers the proposed flow from V-One dispatch through Runner admission, one-time
consumption, input retrieval, independent precondition verification, rootless capsule execution,
independent postcondition verification, and receipt ingestion. The current in-process adapters remain the VERIFIED current state described
in `TRUST_BOUNDARIES.md`; this document makes no claim that target controls are implemented.

The objective is to ensure that only one exactly bound and independently authorized attempt can
reach a narrowly defined side effect, that execution cannot inherit control-plane authority, and
that uncertainty is preserved as `INDETERMINATE` rather than reported as success.

## Assets

| Asset | Security property |
|---|---|
| V-One identity, policy, approval, and lifecycle state | Integrity, authenticity, availability, separation of duties |
| Execution grant and approval bindings | Integrity, freshness, authenticity, one-time use |
| Grant consumption, lease, and fence records | Atomicity, durability, monotonicity, replay resistance |
| Capability registry and handler artifacts | Integrity, provenance, immutability, least privilege |
| Payload and target material | Integrity, confidentiality where applicable, exact digest binding |
| Provider credentials and retrieval credentials | Confidentiality, audience restriction, short lifetime |
| Runner host, OS identity, and capsule runtime | Isolation, least privilege, availability |
| Writable workspace and output | Confinement, bounded size, safe cleanup, evidence integrity |
| Precondition observations and target concurrency tokens | Independence, freshness, integrity, atomic enforcement |
| Postcondition observations | Independence, freshness, integrity, completeness |
| Receipts, logs, and evidence references | Integrity, confidentiality, correlation, bounded retention |
| Target system and external side effects | Authorization, idempotency/fencing, recoverability |
| Production-effect block | Fail-closed integrity |

## Actors

- Authorized operator requesting or cancelling work.
- Independent approver acting through V-One.
- V-One control plane and future authoritative grant issuer.
- Runner ingress, scheduler, claim store, capsule supervisor, and verifier.
- Capability maintainer and release reviewer.
- Payload, target, and evidence storage services.
- External provider or target system.
- CyberCore or AI proposal source, treated as untrusted for authorization.
- Malicious unauthenticated client.
- Authenticated but unauthorized or compromised principal.
- Compromised transport peer, Runner worker, handler artifact, dependency, registry, storage service,
  provider, or same-host process.
- Operator or administrator making an error, replaying stale work, or misconfiguring isolation.

## Entry points

- V-One execution request, approval, cancellation, and recovery interfaces.
- Dispatch/outbox records and Runner ingress protocol.
- Grant, target, approval-evidence, and receipt parsers.
- Runner claim-store operations, heartbeat, lease renewal, and fence transitions.
- Payload, target, handler, image, and registry retrieval.
- Capsule environment, filesystem mounts, standard input/output, and network policy.
- Capability handler input and target gateway.
- Independent precondition verifier, expected-state token, and conditional mutation boundary.
- Independent postcondition verifier and its observation adapters.
- Receipt/evidence upload and V-One receipt ingestion.
- Administrative diagnostics, metrics, logs, cleanup, and recovery paths.

## Trust boundaries

| Boundary | Crossing data | Required posture |
|---|---|---|
| TB-R1: V-One to dispatch | Grant/immutable references/correlation | Authenticated, integrity protected, duplicate safe; mechanism OPEN |
| TB-R2: Dispatch to Runner ingress | Untrusted protocol bytes | Strict parse, version and size limits, fail closed |
| TB-R3: Ingress to claim store | Validated grant identity and state change | Atomic durable consume before side effect |
| TB-R4: Runner to content stores | Digest-bound payload, target, handler, image | Allowlisted pull-by-digest, rehash, no mutable alias |
| TB-R5: Runner supervisor to capsule | Inputs, limits, mounts, minimal environment | Separate OS identity, rootless, read-only base, bounded workspace |
| TB-R6: Capsule to network/target | Capability-specific requests | Deny by default; independent precondition; atomic expected-version and fence enforcement |
| TB-R7: Handler to verifier | Bounded observations only | Verifier independent; no handler/payload-provided code |
| TB-R8: Runner to evidence/receipt ingestion | Receipt and evidence digests | Bounded, redacted, deduplicated, contract-bound; authenticity OPEN |
| TB-R9: Operations to Runner | Cancel, recovery, diagnostics | Authorized, audited, monotonic, cannot reset consumption |

## Severity model

| Severity | Definition |
|---|---|
| CRITICAL | Unauthorized production or broad external mutation, control-plane compromise, arbitrary code with host authority, or systemic secret disclosure |
| HIGH | Unauthorized non-production mutation, replayed side effect, capsule escape, stale-worker write, forged success evidence, or material credential exposure |
| MEDIUM | Bounded evidence tampering/disclosure, targeted denial of service, cleanup failure without known escape, or delayed cancellation with constrained impact |
| LOW | Limited metadata leakage or noisy failure with no authorization, integrity, or isolation impact |

Production effects are blocked. Any path capable of enabling them outside a separate R4 decision is
treated as CRITICAL even if the intended v1 pilot is non-production.

## Attack paths, abuse cases, and controls

| ID | Attack path / abuse case | Severity | Preventive controls | Detective controls | Residual risk |
|---|---|---:|---|---|---|
| R-01 | Runner or compromised worker mints, broadens, or self-approves a grant | CRITICAL | V-One-only issuance; exact cross-contract binding; independent approval; Runner has no issuer authority | Audit issuer/approver identities; reject and alert on unknown issuer or scope mismatch | Authenticity and trust policy are OPEN; compromised accepted issuer remains powerful |
| R-02 | Duplicate delivery, replay, or conflicting digest invokes a capability twice | HIGH | Atomic insert-once claim uniquely keyed by `grant_id`; persist immutable `grant_digest`; compare digest and create attempt in the same serializable transaction before side effect; allocate immutable `runner_receipt_id` with claim/attempt/lease/fence; no reset | Duplicate counters; conflicting-digest alert; reconcile claim/attempt/receipt uniqueness | Provider may duplicate an effect after ambiguous network failure unless it supports idempotency/fencing |
| R-03 | Crash occurs between claim and side effect, or side effect and receipt | HIGH | Claim before effect; immutable consumed state and `runner_receipt_id`; recovery/redelivery reuse the same receipt identity; conflicting terminal bytes are rejected and audit-signalled; target idempotency/fence; independent verification | Lease-expiry alert; missing-receipt and receipt-identity reconciliation; target observation | Exactly-once external effect is not generally provable; uncertain result is `INDETERMINATE` |
| R-04 | Stale worker continues after lease expiry or cancellation | HIGH | Monotonic fence enforced on Runner transitions and mutation gateway; revoke lease; kill capsule | Heartbeat/fence mismatch alerts; post-expiry activity telemetry | Targets without fence enforcement remain blocked or need approved compensation |
| R-05 | Cancellation races admission or is presented as rollback/proof of no effect | HIGH | Atomic consume against an exact authoritative decision identity/generation; persist that binding; cancellation-before-linearization prevents consume, cancellation-after-linearization is stop intent; terminal precedence preserves independently verified success | Race-order, decision-generation, cancel latency, acknowledgement, and post-state audit | External action may complete concurrently; outcome can remain `INDETERMINATE` |
| R-06 | Payload names an unknown capability, generic shell, interpreter, executable, or fallback | CRITICAL | Exact versioned registry allowlist; arbitrary shell is not a capability; no PATH/plugin discovery; unknown fails closed | Rejection events and registry mismatch alerts | A malicious reviewed handler remains a supply-chain risk |
| R-07 | Payload/target substitution after approval or mutable-reference TOCTOU | HIGH | Immutable reference plus digest; in-boundary rehash; no mutable aliases; exact target-kind/schema allowlist | Digest mismatch events; store access audit; pre/post retrieval identity | Source store compromise can deny service; false authoritative inputs remain possible |
| R-08 | Malicious archive/object causes traversal, decompression bomb, parser exhaustion, or device/symlink exposure | HIGH | No extraction by default; strict type/count/size/depth/ratio limits; safe parser; bounded workspace | Limit rejection metrics; resource-limit and parser-failure telemetry | Parser/runtime vulnerabilities and platform differences remain |
| R-09 | Capsule escapes or reaches control-plane DB, sockets, repository, host filesystem, or container runtime | CRITICAL | Separate OS identity; rootless; no privileged mode/devices/host namespaces; read-only base; explicit mounts; empty capabilities | Host audit, denied syscall/mount/access events, capsule integrity checks | Kernel/runtime escape remains; isolation technology and assurance level are OPEN |
| R-10 | Capability exfiltrates data, reaches an unauthorized service, or bypasses the reviewed mutation path | HIGH | Network deny by default; exactly one governed gateway or constrained conditional adapter; handler has no target credentials/endpoints/sockets/mounts/SDK configuration or alternate reachability; egress allowlist cannot bypass the gateway | Egress deny/allow logs, DNS and destination anomaly alerts, direct-provider and alternate-endpoint probes, byte budgets | Allowed gateway endpoint may be compromised or used as an exfiltration channel |
| R-11 | Secrets appear in grant, receipt, payload, environment, arguments, logs, output, crash dump, or workspace | HIGH | No secret fields; separate future broker; short-lived audience-scoped delivery; no argv; redaction; disabled dumps; cleanup | Secret scanning of bounded evidence; redaction metrics; access audit | Perfect redaction is not assured; broker design remains OPEN |
| R-12 | Handler claims success without achieving the expected effect | HIGH | Independent read-only verifier; handler exit/output is non-authoritative; `PASSED` required for success | Compare action result, fresh post-state, and receipt; alert on contradictions | Observation source may be stale, compromised, or eventually consistent |
| R-13 | Handler supplies or tampers with verifier code/data | HIGH | Verifier selected by registry; separate entry point/credentials; no code from payload, target, handler, or workspace | Verify verifier identity/digest; audit observation provenance | Shared runtime or library vulnerabilities may correlate failures |
| R-14 | Missing, stale, conflicting, or partial observations are coerced into success/failure | HIGH | Fail closed; uncertain post-state = `INDETERMINATE`; freshness/completeness rules | Inconsistency and age alerts; operator reconciliation queue | Extended uncertainty may require manual provider investigation |
| R-15 | Protocol rejection is confused with a receipt, or a receipt is forged, replayed, rebound, conflicted, or confused with local ledger identity | HIGH | Invalid envelope/bytes/schema/version/self-digest/grant produce no execution receipt; only valid bindable grants may yield `REJECTED`; exact grant bindings; immutable Runner receipt ID allocated at consume; deduplicate identical receipt; reject conflicts; future authenticated envelope | Protocol-rejection counters; receipt conflict/replay alerts; ledger and identity reconciliation | Digest-only ADR-0007 contract is not authenticity; envelope/trust design is OPEN |
| R-16 | Logs/output create injection, unbounded storage, PII leakage, or forged audit lines | MEDIUM | Structured records; byte/field limits; canonical encoding; escape rendering; redaction and retention policy | Truncation/redaction counters; evidence-integrity verification | Authorized viewers may still see sensitive non-secret data |
| R-17 | Resource exhaustion starves Runner or host | MEDIUM | Admission quotas; CPU/memory/PID/file/output/time limits; bounded concurrency and workspace | Saturation, OOM, timeout, quota, queue-age metrics | Coordinated valid requests can degrade availability |
| R-18 | Cleanup race leaves writable data available to a later attempt | HIGH | Fresh per-attempt workspace; no reuse; deterministic teardown; deny admission on uncertain cleanup | Orphan workspace/capsule scan; lifecycle-to-resource reconciliation | Forensic retention conflicts with deletion need a separate policy |
| R-19 | Registry or handler/image artifact is replaced or downgraded | HIGH | Immutable version and digest; reviewed release provenance; no nearest-version fallback | Registry change audit; digest/provenance verification | Signing and supply-chain policy remain incomplete |
| R-20 | Misconfiguration silently falls back to shared identity, root, writable base, open network, or missing limits | CRITICAL | Startup/admission capability checks; secure defaults; no degraded fallback | Continuous conformance probe; configuration drift alert | Platform-specific enforcement gaps remain until tested |
| R-21 | AI/CyberCore proposal is treated as authorization or direct executable input | CRITICAL | Proposal-only boundary; V-One policy and real approvals; no package code execution | Provenance audit and authorization-chain validation | Compromised human approver can still accept a malicious proposal |
| R-22 | Production block is bypassed through mislabeled environment/target or alternate path | CRITICAL | V-One and Runner both enforce environment/target binding and production disable; no alternate handler path | Alert on production-like target, denied attempts, and config drift | Target classification correctness and inventory authority are OPEN |
| R-23 | Clock skew extends validity, breaks lease decisions, or admits stale work | HIGH | Bounded skew policy; authoritative timestamps; monotonic durations; start must be within grant window | Clock-health and skew alarms; anomalous timestamp audit | Distributed time cannot be perfect; tolerated skew is OPEN |
| R-24 | Diagnostic or recovery interface resets consumption, bypasses registry, or exposes evidence/secrets | HIGH | Separate privileged permission; immutable consume record; read-only diagnostics by default; audited recovery | High-signal admin audit and break-glass review | Administrator compromise remains high impact |
| R-25 | Target drifts between approval, precondition observation, and mutation (TOCTOU) | HIGH | Authorization-bound expected state/version; independent precondition verifier immediately before mutation; target gateway atomically enforces expected version and current fence; block providers without conditional mutation or approved equivalent | Precondition mismatch, stale-version, conditional-write rejection, and concurrent-mutation alerts | Compromised or incorrectly authoritative target metadata can still produce false observations; provider semantics remain capability-specific |

## Mandatory abuse-case outcomes

- Unknown or syntax-valid-but-unregistered capability: `REJECTED`, no consume if detected before the
  atomic claim, no handler invocation.
- Malformed bytes, unsupported schema/version, invalid self-digest, or an unparseable or otherwise
  contract-invalid grant: protocol rejection, no `execution-receipt/v1`; only a bounded transport
  negative acknowledgement or no response, with non-authoritative correlation only when safe.
- A structurally and digest-valid grant rejected before consume is exactly bound and returns only
  `REJECTED` / `EXPECTED_EFFECT_NOT_VERIFIED` / `NOT_RUN`.
- Replayed consumed grant: return the existing attempt/terminal reference; no new attempt.
- Same grant ID with different digest: reject and raise an integrity alert; do not create a second
  claim, attempt, or receipt identity.
- Cancellation before the authoritative admission linearization point: no consume and valid-grant
  `REJECTED`; cancellation after it: the consumed attempt remains and cancellation is best-effort
  stop intent. Fresh independent `PASSED` evidence always maps to `SUCCEEDED`, including after late
  cancellation. Proven cancellation cause maps to `CANCELLED`; other known non-success maps to
  `FAILED`; timeout and worker/lease/fence/capsule loss use their defined status with
  `INDETERMINATE` outcome/postcondition when post-state is unknown.
- Lease loss or stale fence during possible mutation: prevent further writes and use receipt status
  `INTERRUPTED` with outcome and postcondition `INDETERMINATE` unless fresh independent evidence
  establishes a different valid mapping.
- Missing receipt after possible side effect: never retry the grant; reconcile and independently
  verify.
- Target drift, stale ETag/version, or failed conditional mutation: no side effect is authorized;
  return a fail-closed known failure when absence of mutation is established, otherwise preserve an
  `INDETERMINATE` outcome.
- Handler exit zero with failed postcondition: receipt status `FAILED`, never `SUCCEEDED`.
- Verifier timeout, conflicting observation, or eventual-consistency window not resolved: use an
  allowed receipt status such as `INTERRUPTED`, `TIMED_OUT`, or `CANCELLED` with outcome and
  postcondition status `INDETERMINATE`; never use `INDETERMINATE` as receipt status.
- Isolation or network-deny enforcement unavailable: reject admission; never fall back.
- Any production target or effect in v1: reject because production effects remain blocked.

## Verification requirements

### Contract and authorization

- Golden and adversarial vectors for strict fields, canonical digests, cross-bindings, expiry,
  unsupported versions, malformed bytes, and size limits.
- Demonstrate the Runner cannot issue or expand authority and cannot accept PDG, CyberCore, AI, or
  transport identity as a substitute for a V-One authorization chain.
- Negative tests for environment, workspace, target, payload, capability, policy, approval-set,
  execution, and grant mismatches.

### One-time use, lease, cancellation, and recovery

- Concurrent duplicate-delivery test proving only one durable consume and one handler invocation.
- Concurrent same-`grant_id`/different-`grant_digest` test proving one uniqueness record, no second
  attempt, and an integrity alert.
- Crash injection before consume, after consume, before effect, during effect, after effect, during
  verification, before receipt persistence, and during receipt delivery.
- At every post-consume crash point, prove recovery and redelivery retain the single durably
  allocated `runner_receipt_id`, and reject/audit conflicting terminal bytes for that identity.
- Stale worker and fence tests proving old workers cannot mutate through governed gateways.
- Cancellation race tests for before dispatch, before consume, concurrent consume, after consume
  before effect, during effect, and after verified effect, including lost/delayed acknowledgements
  and an unresponsive capsule; prove decision identity/generation linearization and that late
  cancellation cannot overwrite `SUCCEEDED`.
- Lease expiry and clock-skew tests; recovery must not reset consumption or invent a known outcome.

### Retrieval, preconditions, registry, and supply chain

- Reject target drift after approval and after precondition observation; test stale ETag/version,
  generation mismatch, failed compare-and-swap, providers without conditional mutation, and two
  concurrent authorized operations against the same target.
- Prove the precondition verifier is independent from the handler and that the target gateway
  atomically enforces the authorized expected state together with the current fence.
- Negative-test direct provider access, alternate endpoints, stale fences, and expected-state
  bypass. Prove handlers lack credentials, SDK configuration, mounts, sockets, endpoints, and
  network reachability for any alternate mutation path; block mutation if non-bypassability cannot
  be demonstrated.
- Reject mutable aliases, unexpected redirects/protocols, digest mismatch, oversize/deep objects,
  traversal, symlink/special files, decompression bombs, and unregistered target kinds.
- Prove exact registry-version agreement, unknown capability rejection, no arbitrary shell, no
  dynamic plugin/PATH resolution, and immutable handler/image identity.
- Verify registry and artifact provenance requirements after their separate design is accepted.

### Capsule isolation

- On every supported platform, prove separate OS identity, rootless execution, read-only base,
  absence of host/control-plane mounts and sockets, bounded writable workspace, resource limits,
  blocked privilege escalation, and network deny by default.
- Attempt access to control-plane DB, repository, home, process namespace, devices, metadata
  services, container runtime, loopback/host services, DNS, and external network.
- Demonstrate no degraded fallback when an isolation primitive is absent and that cleanup uncertainty
  blocks workspace reuse.

### Postconditions, receipts, and evidence

- Prove verifier selection and code are independent from handler/payload/workspace.
- Test fresh passed, known failed, stale, missing, partial, conflicting, timeout, and eventually
  consistent observations; only fresh complete evidence may pass.
- Verify receipt uniqueness, exact grant binding, deduplication, conflict rejection, bounded output,
  redaction, retention, and missing-receipt reconciliation.
- Verify invalid protocol input never creates an execution receipt, while rejection of a valid
  grant creates only an exactly bound `REJECTED` receipt.
- Run secret canaries through payload, environment, output, error, crash, workspace, receipt, log,
  metric, and evidence paths and prove they are absent from forbidden surfaces.

### Operational and security assurance

- Threat-led penetration test for ingress, parser, registry, retrieval, capsule escape, egress,
  stale worker, admin recovery, and evidence ingestion.
- Failure-mode review showing fail-closed admission, valid ADR-0007 receipt-status mapping, and
  `INDETERMINATE` preservation only in outcome and postcondition fields.
- Independent R3 evidence review. Focused tests precede full repository gates; a non-production pilot
  remains default-off and production effects remain disabled.

## Residual risks

- Kernel, container/VM runtime, host administrator, and supply-chain compromise can defeat capsule
  isolation.
- One local attempt does not guarantee exactly-once external effect without provider idempotency or
  target-side fencing.
- Independent verification may still depend on a compromised, stale, or eventually consistent
  observation source.
- End-to-end authenticity, revocation, key compromise recovery, and trust-store governance are not
  defined by ADR-0008.
- Secret redaction cannot guarantee recovery after arbitrary handler compromise; secret-bearing
  capabilities require stronger containment and a separate broker decision.
- Denial of service remains possible through valid workload, provider degradation, or forced
  `INDETERMINATE` investigations.
- Target classification errors could misidentify production. Inventory authority and production
  target detection remain open.

## Open security decisions

1. Transport and peer authentication between V-One, dispatch, Runner, and receipt ingestion.
2. Signed-envelope format, algorithm, issuer/Runner key identities, trust store, rotation,
   revocation, compromise recovery, and clock-skew policy.
3. Durable consumption/lease/fence store and transaction model, including disaster recovery and
   split-brain behavior.
4. Target-side fencing and idempotency contract for providers that cannot enforce a fence token.
5. Capsule technology and required assurance per supported operating system.
6. Capability-registry schema, owner, change/release governance, handler and image provenance.
7. Content-addressed payload/target/evidence stores, immutable-reference format, retention, and
   garbage collection.
8. Secret broker, workload identity, delivery channel, revocation, redaction, and capability
   eligibility rules.
9. Network egress enforcement layer, DNS semantics, proxy ownership, destination identity, and
   observability without sensitive logging.
10. Independent verifier runtime, credential separation, observation freshness, and
    eventually-consistent target policy.
11. Receipt authenticity, evidence storage authorization, external anchoring, retention, and
    privacy policy.
12. Authoritative target inventory and rules that classify production effects across aliases and
    provider accounts.
13. Admission quotas, scheduling fairness, fleet isolation, patching, attestation, and incident
    response.
14. Forensic retention versus guaranteed workspace destruction after attempted execution.

## Non-scope

This document does not implement or authorize runtime code, persistence, APIs, service wiring,
signing, trust stores, cryptography, dependencies, production effects, publication, release, or
deployment. It does not claim that the proposed controls currently exist.
