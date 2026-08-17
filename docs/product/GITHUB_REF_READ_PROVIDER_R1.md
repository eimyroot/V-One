# GitHub Ref READ Provider R1

Status: IMPLEMENTED candidate

Phase: D4a

## Purpose

D4a introduces the first provider-specific READ handler above the merged D3 isolated-runtime boundary.

The bounded capability is:

```text
github.read-ref/v1
```

It observes one exact GitHub ref and returns the provider-observed Git object ID as content-addressed evidence.

D4a does not authorize or expose any provider mutation method.

## Source-of-truth status

Canonical `main` after D3 merge:

```text
6d5ef2230ac8492e6cbef3d6840fb7920f261d36
```

A real GitHub provider READ is available through the connected GitHub source in this ChatGPT session, but that connector is not the V-One D3 isolated-runner backend.

Therefore:

```text
REAL GITHUB READ AVAILABLE          = YES
D3->D4 LIVE V-ONE RUNTIME CONNECTED = NO
D4 COMPLETE                         = NO
```

External connector reads may be retained as provider evidence, but must not be presented as V-One execution proof.

## Exact target

The handler accepts only `ExecutionTarget` with:

```json
{
  "target_kind": "git_ref",
  "target_claims": {
    "repository": "owner/name",
    "ref": "refs/heads/<name> | refs/tags/<name>"
  }
}
```

Unknown target fields fail closed. The ref must be fully qualified. The handler does not accept a URL, arbitrary API route, HTTP method, body, GraphQL query, shell command, or caller-selected provider operation.

## Runtime input

The provider READ requires both:

- exact D3 `PreparedIsolatedRuntime`;
- exact D3 `ReadOnlyRuntimeActivation/v1`.

The handler revalidates binding to:

- provider and concrete provider instance;
- RunnerIdentity;
- RunnerBoundary;
- CredentialAccessDecision;
- lease ID and digest;
- execution epoch;
- execution capsule;
- capability definition.

The D2 decision must identify provider `github`, `READ_ONLY` access, and `provider_mutation_allowed = false`.

## Stale-attempt boundary

D4a performs another `CurrentExecutionFence` check immediately before crossing the GitHub provider READ port:

```text
D3 activation
    |
    v
exact target validation
    |
    v
CURRENT C4 LEASE RECHECK
    |
    v
GitHubReadTransport.read_ref(...)
```

A stale or expired attempt cannot perform the provider READ through this handler.

This does not weaken the D3 requirement to fence before runtime activation. D4 repeats the check because provider observation is a later boundary crossing.

## Provider port

`GitHubReadTransport` exposes exactly one provider operation:

```text
read_ref(repository, ref) -> commit object id
```

It exposes no create/update/delete/merge/push/deploy method.

Provider SDK or HTTP details remain outside the trust kernel. Concrete runtime implementations must map only this exact method to the GitHub READ endpoint.

## Observation evidence

`GitHubRefObservation/v1` binds:

- exact repository;
- exact fully-qualified ref;
- provider-observed Git object ID;
- ExecutionTarget digest;
- provider/runtime instance;
- Runner and boundary;
- CredentialAccessDecision;
- runtime activation;
- lease and execution epoch;
- execution capsule;
- capability definition;
- provider source identity;
- trusted clock witness identity/digest/time;
- observation revision.

The observation is content addressed.

It contains no:

- token;
- secret;
- authorization header;
- credential handle;
- provider mutation request;
- arbitrary response body.

## Evidence semantics

A `GitHubRefObservation/v1` means only:

> the D4 provider-read subsystem reports that it observed this exact Git ref at this execution boundary.

It is not:

- an ExecutionReceipt for a provider mutation;
- independent verification;
- proof that an expected post-state is correct;
- OperationProof.

Phase E remains responsible for independent verification using separate VerifierIdentity and credentials.

## External pilot evidence

During D4a authoring, the connected GitHub source independently reported canonical `main` as:

```text
6d5ef2230ac8492e6cbef3d6840fb7920f261d36
```

That is a real provider observation, but it occurred outside the V-One D3 runtime path. It is useful as target/pilot evidence only.

## Non-goals

D4a does not:

- connect a real isolated runner backend;
- inject a real credential;
- perform a V-One-governed live provider READ;
- mutate GitHub;
- execute arbitrary HTTP;
- execute shell commands;
- persist provider secrets;
- issue ExecutionReceipt/v2;
- perform independent verification;
- issue OperationProof;
- deploy or release.

## Acceptance

D4a requires tests proving:

1. exact GitHub ref target parsing;
2. current C4 fence immediately precedes provider READ;
3. stale fence prevents provider READ;
4. D3 runtime/activation bindings remain exact;
5. non-GitHub credential decisions fail closed;
6. provider result must be a valid Git object ID;
7. observation is content addressed and round-trips;
8. secret/mutation fields are rejected;
9. no provider mutation operation exists on the handler or transport contract.

## Next gate

After D4a merge, D4b must connect one real isolated runtime backend and one durable `CurrentExecutionFence` implementation, then execute the same `github.read-ref/v1` operation through the D3->D4 path.

Only that successful governed pilot may close Phase D.
