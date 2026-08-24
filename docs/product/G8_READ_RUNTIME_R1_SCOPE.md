# G8 READ Runtime R1 — Candidate Scope

> Candidate implementation boundary only. This document does not mark G8 VERIFIED or authorize WRITE, release, deployment, or production effects.

## Base

```text
canonical base main = 79582e0d66120c2c8587d131edd2f990ec40488d
ADR-0019 effective adoption = VERIFIED by external adoption register
```

## R1 purpose

R1 adds a fail-closed, server-owned READ runtime assembler over the already-canonical G1-G7 authority and durable-dispatch graph. It does not create another snapshot/grant/outbox/inbox/lease authority path.

The assembler may create only:

```text
existing CanonicalOperationPipeline
+ exact canonical ProductService DB / DatabasePermissionAuthority
+ exact capability/capsule registry identity shared with Grant/conformance authority
+ exact DurableCurrentExecutionFence implementation
+ exact G8-owned Runner credential source
+ separately credentialed exact G8-owned Verifier credential source
+ immutable independently pinned credential-pair READ transports
+ role-bound G8 Runner / Verifier READ handlers
+ exact pinned GET-only GitHub provider effect implementation
+ CanonicalGitHubReadTerminal
+ CanonicalOperationResumeService
→ CanonicalOperationRuntime
```

## Credential-independence boundary

Runner and Verifier credential provenance is not accepted from caller labels.

`G8BoundGitHubReadTransport` does not retain the token, fingerprint, credential class, or provider attestation in caller-mutable instance slots. Those values are retained in a private closure-owned binding registry outside the transport instance. A successfully initialized credential source is write-once: a second `__init__` call is rejected before any replacement credential can be observed or stored. Initial construction derives the non-secret principal identity by performing an authenticated GitHub `GET /user` with the exact credential material; R1 fails closed when that provider observation cannot produce a valid principal identity.

The closure registry is **not** treated as a sufficient trust anchor. The raw credential-source object is intentionally unable to perform a provider READ directly. During canonical runtime construction, G8 revalidates both sources and pins each source's token fingerprint, credential class, and provider-attested principal into an immutable tuple-backed Runner/Verifier pair transport. Both effect transports carry the same independently pinned pair.

The runtime also pins the exact credential-source unbound `_pin_snapshot` / `_read_ref_with_pin` implementations and the exact released `GitHubApiRefReadTransport` type, initializer, `read_ref` method, and source identity. Provider effect execution therefore uses the runtime-retained GET-only implementation rather than resolving a mutable module-global transport symbol at effect time.

The immutable pair transports are retained only behind G8 role-bound Runner and Verifier handler subclasses. A normal post-build reassignment of either handler's `transport` is rejected. Immediately before delegating to the canonical observation handler, the Runner path requires the exact G8 pair transport with literal `runner` role and binds the current `CredentialAccessDecision` credential class to the immutable Runner pin. The Verifier path similarly requires literal `verifier` role and binds both current Verifier identity and `VerifierCredentialDecision` credential classes to the immutable Verifier pin. A forced `object.__setattr__` Runner↔Verifier transport swap therefore fails closed before the provider READ.

Before every provider READ the immutable pair transport:

1. revalidates the current Runner binding and performs a fresh GitHub `/user` principal observation through the pinned source implementation;
2. revalidates the current Verifier binding and performs a fresh GitHub `/user` principal observation through the pinned source implementation;
3. requires each current fingerprint/class/principal to equal its independently pinned runtime value;
4. requires Runner and Verifier fingerprints, credential classes, and provider principals to remain distinct;
5. invokes only the selected source through the pinned unbound source method with its immutable pin; and
6. the selected source captures one binding snapshot, re-attests that exact local token, compares it to the runtime pin, and passes that same local token to the pinned GET-only provider implementation.

Therefore changing an introspectable closure-registry entry after composition cannot silently replace the Verifier with the Runner credential; reinvoking `__init__` cannot replace a successful binding; post-build rebinding of the module-global provider transport cannot widen the effect implementation; post-build handler transport rebinding cannot change the credential role; and validation/provider use cannot diverge through a post-check instance-state change or check/use race.

The pack rejects:

- the same transport instance;
- the same underlying credential material;
- two different credential strings that authenticate as the same provider principal;
- transport subclasses or structural/generic provider clients;
- Runner/Verifier credential-class collapse;
- changed credential-source implementations at runtime assembly;
- changed provider transport type, initializer, READ implementation, or source identity at runtime assembly.

The provider-observed principal checks are composition/use-time security evidence only. They do not replace the later live independent Verifier readback required by the G8 exit gate.

## R1 hard ceiling

```text
terminal profile = READ_ONLY_VERIFIED
capability       = github.read-ref/v1
provider WRITE   = NOT CONFIGURED
A09 preparers    = NOT CONFIGURED
production       = REJECTED
ambient token    = NOT LOADED BY ASSEMBLER
```

R1 rejects parallel product DBs, parallel permission authority, capsule-registry forks from Grant/conformance authority, foreign current fences, subclasses or instance-level overrides that can replace the durable current-fence implementation, shared Runner/Verifier provider authority, mutation-capable/generic provider transports, collapsed Runner/Verifier credential classes, post-build Runner/Verifier handler-role swaps, product↔Runner environment mismatch, and production widening.

The caller-supplied fence is validated only as canonical provenance. The runtime retains a newly constructed exact `DurableCurrentExecutionFence` over the canonical ProductService DB and Runner trusted clock, shared by resume, activation, and the final pre-READ check.

## R1 evidence required before merge

- exact-head CI / verify SUCCESS;
- documentation/VOP truth gates SUCCESS;
- full pytest SUCCESS;
- product readiness SUCCESS;
- dependency audit SUCCESS;
- image build + smoke SUCCESS;
- fresh independent Codex review on exact head CLEAN;
- zero unresolved blocking review threads;
- unchanged main/head immediately before guarded merge.

## Not proven by R1 merge

Even after a successful R1 merge, the following remain NOT VERIFIED until separate live evidence exists:

- authenticated canonical HTTP READ E2E using the G8 pack;
- process interruption while the durable execution is ACTIVE;
- restart/resume of that same execution without duplicate prepare/grant/consume/outbox/inbox/epoch/lease;
- resumed real provider READ followed by durable completion;
- independent live Verifier readback and `VerificationResult/v1`;
- failure-injected corrupt/revoked/stale durable evidence behavior in the live E2E path.

Provider WRITE remains BLOCKED until the complete adopted READ-before-WRITE gate is independently VERIFIED.
