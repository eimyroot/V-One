# F3 GitHub Create-Ref Contract R1

Status: IMPLEMENTATION CANDIDATE / NO LIVE MUTATION

Baseline: `main@d584a99386b0a5e75b263d0c4d0e1a4153b64af9`

Phase: F3 — exact `github.create-ref/v1` target binder + handler/transport contracts

## Purpose

F3 makes the first Phase-F mutation mechanically exact without activating a write runtime or crossing a provider boundary.

The slice adds only pure contracts and contract tests for the already-canonical F1/F2 mutation candidate:

```text
github.create-ref/v1
refs/heads/vone-canary/*
CREATE_ONLY
max provider mutations = 1
staging only
```

No live GitHub mutation is performed by F3.

## Canonical F3 chain

```text
approved target payload
        ↓
GitHubCreateRefTargetBinder
        ↓
ExecutionTarget/v1
        ↓
TargetBinding/v1
        +
RunnerBoundary/v2
        +
CredentialAccessDecision/v2
        ↓
GitHubCreateRefRequest/v1
        ↓
[future F4 provider transport invocation]
        ↓
GitHubCreateRefProviderResponse/v1
        ↓
F3 response interpretation
```

F3 intentionally stops before the transport invocation.

## Exact target binder

Binder identity:

```text
github-create-ref-target/v1
```

The approved payload must contain exactly:

```json
{
  "repository": "owner/repo",
  "ref": "refs/heads/vone-canary/<name>",
  "commit_sha": "<40 lowercase hex Git SHA-1>"
}
```

Unknown fields fail closed. In particular `force`, update semantics, alternate target namespaces and missing commit identity are rejected.

The binder reuses the existing generic `TargetBinder` / `TargetBinding` infrastructure. F3 does not create a parallel target model.

## Canary namespace

F3 accepts only:

```text
refs/heads/vone-canary/*
```

The suffix must be a valid bounded Git ref suffix. Main branches, tags and arbitrary head refs are outside the F3 capability.

## Provider contract

The provider operation remains exactly GitHub Create a reference:

```text
POST /repos/{owner}/{repo}/git/refs
body: { ref, sha }
```

GitHub documents `201 Created` as the success status and `409` / `422` as rejection classes for this endpoint.

F3 does not infer that one specific rejection status always means "ref already exists". Provider error details can vary. The fail-closed rule is stronger:

```text
status != 201
    ⇒ NO CREATED-REF CLAIM
    ⇒ FAIL
    ⇒ NO UPDATE FALLBACK
```

## Request contract

`github-create-ref-request/v1` binds:

- exact repository;
- exact canary ref;
- exact commit SHA;
- ExecutionTarget digest;
- TargetBinding digest;
- CapabilityDefinition identity;
- `RunnerBoundary/v2` digest;
- `CredentialAccessDecision/v2` digest;
- F1 `ControlledWriteRequirement` digest;
- atomic provider-condition contract identity;
- operation `CREATE_REF`;
- semantics `CREATE_ONLY`;
- maximum provider mutations = 1.

The request is content-addressed. It is not a credential, ExecutionGrant, runtime activation, ExecutionReceipt or VerificationResult.

## Transport boundary

`GitHubCreateRefTransport` exposes one method only:

```text
create_ref(request)
```

The F3 protocol contains no:

```text
update_ref
force_update
patch_ref
delete_ref
```

F3 ships no concrete HTTP implementation. There is therefore no F3 code path that can cross the GitHub provider boundary.

## Handler boundary

`GitHubCreateRefHandlerContract` has only pure contract operations:

```text
prepare_request(...)
interpret_response(...)
```

It does not invoke `GitHubCreateRefTransport`.

Before preparing a request it checks that the target binding and F2 write metadata agree on the exact capability, boundary, credential decision, controlled-write requirement and provider-condition lineage.

A later F4 slice must additionally prove the full current A→B→C authority/dispatch/fence lineage immediately before the real provider effect.

## Provider response contract

`github-create-ref-provider-response/v1` deliberately narrows provider output.

For `201`, it may claim only:

```text
exact created ref
object type = commit
exact object SHA
source identity
```

For every non-201 response, created-ref fields must be null. A rejected response cannot be serialized as if a ref had been created.

The handler accepts success only when the provider response exactly echoes the requested ref and exact commit SHA.

## Negative overwrite tests

F3 contract tests prove:

- a non-canary ref cannot be bound;
- extra `force` data cannot enter the approved target;
- malformed/non-exact target input fails closed;
- provider `409` fails closed;
- provider `422` fails closed;
- no provider rejection triggers an update-ref fallback;
- a `201` response for a different ref fails closed;
- a `201` response for a different object SHA fails closed;
- the transport Protocol exposes `create_ref` only;
- the handler has no execute/provider-call method;
- the F3 module imports no HTTP/network client and contains no token delivery path.

## Provider-condition semantics

F3 does not use READ-then-compare to manufacture atomicity.

The exact F1 provider-condition remains `ATOMIC_PROVIDER_CONDITION`: the future live effect uses the provider's create-reference operation itself as the create-only state transition. A pre-read may be useful as diagnostic evidence in a later slice, but it cannot turn an existing ref into an overwritable target.

## Existing READ path non-regression

F3 does not modify:

- `github_read_provider.py`;
- `read-only-runtime-activation/v1`;
- `runner-boundary/v1`;
- verifier identity or credential contracts;
- `VerificationResult/v1` semantics.

D4b, E3 and E4b remain acceptance regressions for every F3 candidate head.

## Schema identities

F3 uses or adds registry parity for:

```text
target-binding/v1                         historical existing contract identity
github-create-ref-request/v1              F3 request contract
github-create-ref-provider-response/v1    F3 narrowed provider response contract
```

Registry presence does not create runtime authority or provider access.

## Phase F continuation

```text
F1  controlled-write requirement + provider condition      COMPLETE
F2  write boundary + credential decision                   COMPLETE
F3  target binder + handler/transport contracts            ← this slice
 ↓
F4  write runtime/credential/effect preflight and explicit live gate
    REAL provider mutation remains separately authorized
 ↓
F5  independent provider readback + VerificationResult
 ↓
PHASE F COMPLETE
```

If F4 reality-check shows that a new write-runtime activation or concrete scoped-credential delivery contract is still missing, it must be implemented as a separate fail-closed slice before the live mutation. F3 does not silently reuse READ-only runtime activation semantics.

## Non-goals

No live GitHub call. No ref creation. No ref deletion. No update-ref. No force update. No write credential delivery. No secret material. No write runtime activation. No Grant issuance or consumption. No dispatch behavior change. No ExecutionReceipt/v2. No OperationProof. No release. No deploy. No production effect.
