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
+ exact capability/capsule registries
+ exact DurableCurrentExecutionFence
+ READ-only Runner runtime + GitHubReadTransport
+ separate READ-only Verifier identity/policy/transport
+ CanonicalGitHubReadTerminal
+ CanonicalOperationResumeService
→ CanonicalOperationRuntime
```

## R1 hard ceiling

```text
terminal profile = READ_ONLY_VERIFIED
capability       = github.read-ref/v1
provider WRITE   = NOT CONFIGURED
A09 preparers    = NOT CONFIGURED
production       = REJECTED
ambient token    = NOT LOADED BY ASSEMBLER
```

R1 rejects parallel product DBs, parallel permission authority, capsule-registry forks from Grant/conformance authority, a foreign current fence, shared Runner/Verifier transport instances, mutation-shaped provider transports, collapsed Runner/Verifier credential classes, and production widening.

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
