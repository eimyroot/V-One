# D4b Live Governed READ Pilot R1

Status: IMPLEMENTED candidate

Phase: D4b

## Purpose

D4b closes the remaining Phase-D runtime gap by executing the already-defined
`github.read-ref/v1` capability through a real isolated runtime and a real GitHub
provider READ while preserving the D1-D4 fail-closed chain.

The only external provider effect in this slice is a GET-shaped observation of one
exact Git ref. Provider mutation remains forbidden.

## Canonical chain

```text
pilot-scoped durable Phase-C admission
  -> DurableExecutionLeaseService (C4 current epoch)
  -> DurableCurrentExecutionFence
  -> GitHub Actions isolated Docker runtime
  -> RunnerIdentity/v1
  -> RunnerBoundary/v1
  -> CredentialAccessDecision/v1
  -> ReadOnlyRuntimeActivation/v1
  -> DurableCurrentExecutionFence recheck
  -> GitHubReadTransport.read_ref(...)
  -> GitHubRefObservation/v1
  -> durable coordinator completion
```

The pilot-scoped Phase-C seed exists only to establish an ephemeral, durable current
lease inside the isolated runner. It does not claim that the pilot re-executed the
full live A/B authority issuance path. Phase C already owns and tests those semantics.

## Concrete isolated runtime

The live pilot uses a GitHub-hosted Actions runner only as a host for a separately
hardened Docker execution cell.

The container is created with:

- read-only root filesystem;
- no persistent workspace mount;
- writable tmpfs only for `/tmp` and product ephemeral storage;
- all Linux capabilities dropped;
- `no-new-privileges`;
- one CPU;
- 512 MiB memory ceiling;
- PID limit 256;
- explicit provider instance identity derived from the Actions run/job/attempt and
  concrete container ID.

The image ID is used as the content-addressed runtime rootfs identity supplied to the
D3 capsule/runtime binding.

## Network boundary

The runtime starts under a host-enforced `DOCKER-USER` policy:

```text
default: DROP
allow: tcp -> api.github.com resolved IPv4 -> 443
```

The workflow also performs a negative egress probe against `https://example.com` and
fails if that arbitrary network request succeeds.

The exact network profile is SHA-256 bound into the ExecutionCapsule and D3 runtime
bootstrap evidence.

## Credential boundary

The workflow declares only:

```yaml
permissions:
  contents: read
```

`actions/checkout` uses `persist-credentials: false`.

The ephemeral GitHub Actions token is injected only into the concrete
`GitHubApiRefReadTransport` process through `docker exec`. Token bytes are never copied
into RunnerIdentity, RunnerBoundary, CredentialAccessDecision, activation evidence,
GitHubRefObservation, logs intentionally emitted by V-One, or durable SQLite rows.

D2 still represents credential authorization only; the token remains an out-of-band
secret.

## Durable current fence

`DurableCurrentExecutionFence` is the public SQLite composition adapter required by D3.
It:

1. reads the exact `execution_epoch_state_v1` row;
2. requires `status = ACTIVE`;
3. requires exact lease ID/digest/epoch/environment/capsule/runner binding;
4. loads and reconstructs the immutable persisted lease row;
5. requires exact canonical row equality;
6. obtains a fresh trusted clock witness;
7. delegates stale/expiry semantics to `ExecutionLease.assert_completion_fence()`.

The fence performs no durable mutation.

D3 activation checks the fence once, and the D4 GitHub handler checks it again
immediately before crossing the provider READ port.

## TOCTOU statement

D4 performs READ-only effects, so this SQLite read-side fence is sufficient for the
Phase-D safety ceiling. It does not claim atomic provider-side fencing for future
mutations.

Any Phase-F provider mutation must additionally consume a provider-native atomic
condition such as head SHA, ETag, version, CAS token, or equivalent effect-boundary
primitive.

## Provider READ

The exact capability is:

```text
github.read-ref/v1
```

The target is restricted to:

```text
repository = owner/name
ref        = refs/heads/* | refs/tags/*
```

The concrete transport exposes only `read_ref(...)` and uses GitHub's GET ref API.
There is no mutation method on the port.

Successful execution emits `GitHubRefObservation/v1`, content-binding:

- exact repository/ref target;
- observed Git object ID;
- RunnerIdentity and RunnerBoundary lineage;
- CredentialAccessDecision;
- runtime activation;
- exact C4 lease and execution epoch;
- capsule and capability identity;
- provider source identity;
- trusted observation clock witness.

The observation is execution evidence, not independent verification and not
OperationProof.

## Fail-closed workflow gate

The live workflow must fail if any of the following occurs:

- product image cannot be built;
- content-addressed rootfs identity cannot be derived;
- GitHub API address cannot be resolved;
- hardened container cannot start;
- firewall rules cannot be installed or confirmed;
- arbitrary egress unexpectedly succeeds;
- D3 bootstrap/profile binding fails;
- credential policy or runtime activation binding fails;
- durable current fence fails;
- GitHub READ fails;
- provider response is malformed;
- durable completion fails;
- the final marker `D4B_LIVE_GOVERNED_READ=PASS` is absent.

## Explicit non-goals

D4b does not provide:

- repository mutation;
- GitHub issue/PR mutation;
- deployment or release;
- production mutation;
- generic shell authority;
- arbitrary HTTP capability;
- persistent credentials;
- independent VerifierIdentity;
- VerificationResult;
- ExecutionReceipt/v2;
- OperationProof.

## Phase-D gate

Phase D can be marked COMPLETE only after both exact-head standard CI and the
`d4b-live-governed-read` workflow succeed on the same PR head and the live workflow
shows a real `GitHubRefObservation/v1` produced through the D3 -> D4 path.

After D4b merge, the next phase is **E — Independent Verification** with a distinct
VerifierIdentity and separate READ credential.
