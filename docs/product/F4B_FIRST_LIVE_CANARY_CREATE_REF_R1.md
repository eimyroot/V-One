# F4b First Live Canary Create-Ref R1

## Status

**AUTHORIZED LIVE PILOT — WORKFLOW NOT YET ENABLED IN THE DRY CANDIDATE**

F4b is the first V-One provider WRITE gate. The only allowed provider mutation is one GitHub
`CREATE_REF` operation in the namespace `refs/heads/vone-canary/*` pointing at one exact commit.
There is no update, force-update, delete or automatic retry fallback.

The initial PR candidate intentionally contains the concrete transport, full-chain live pilot and
system tests but no write-capable GitHub Actions workflow. This allows exact-head CI to validate the
write path before any commit can receive a write token or call the provider. The live workflow may
be added only after this dry candidate is green.

## Mutation lineage

The writer must execute the released authority and durable execution chain rather than the D4b
pilot-seed shortcut:

```text
Reviewed ChangeRequest
  -> AuthoritativeSnapshotCreator
  -> AuthorizationSnapshot
  -> Monotonic Authority + atomic-condition PreconditionWitness
  -> AuthoritativeGrantIssuer
  -> ExecutionGrant/v2
  -> DurableGrantService.issue_and_store
  -> DurableDispatchOutboxService.consume_and_enqueue
  -> DispatchEnvelope
  -> DurableDispatchInboxService
  -> DurableExecutionLeaseService
  -> RunnerIdentity
  -> RunnerBoundary/v2
  -> CredentialAccessDecision/v2
  -> EphemeralWriteCredentialDelivery/v1
  -> WriteRuntimeActivation/v1
  -> WriteEffectPreflight/v1
  -> CURRENT EFFECT FENCE
  -> one GitHub create-ref POST
  -> github-create-ref-provider-response/v1
  -> durable C4 completion
```

The staging revocation authority used by this first isolated pilot is local to the ephemeral pilot
control-plane database and is explicitly not production authority.

## Provider condition

The Grant precondition uses `ATOMIC_PROVIDER_CONDITION`. The control-plane witness verifies that the
exact create-only condition contract has not changed. It does **not** claim that a prior READ proves
ref absence. Atomic absence/uniqueness is enforced at the GitHub create-reference endpoint itself.
An existing ref therefore produces provider rejection and no update fallback.

## Transport safety

`GitHubApiCreateRefTransport`:

- keeps the token only in process memory;
- exposes only `create_ref`;
- permits one invocation per transport instance;
- issues one POST with exact `{ref, sha}`;
- treats an HTTP rejection as a terminal classified rejection;
- performs no automatic retry;
- treats network/timeout ambiguity as UNKNOWN/ambiguous and stops, because a request might have
  reached the provider before the transport error.

A network error must never cause a second POST automatically.

## Verification separation

The writer result is **not VERIFIED**. A successful `201` and durable completion prove execution
lineage/effect response only.

After the write, a separate READ-only D4b operation must observe the exact created canary ref. Its
result is passed to the existing independent E3 verifier, and only the existing E4
`VerificationResult/v1` path may produce `VERIFIED`.

This preserves:

`Execution success != Verification success`.

The write execution and the post-state verification are separate lineages until a future
OperationProof composes them.

## Rollback boundary

No delete is authorized by F4b. The canary ref remains present after the live pilot. A future exact
`DELETE_EXACT_CREATED_REF` rollback requires a separate explicit gate and separate evidence.

## Live acceptance

The final live gate is valid only if:

1. dry exact-head CI passes before the write workflow is added;
2. the final workflow candidate passes its static pre-effect checks before the mutation step;
3. canonical `main` still equals the exact target commit expected by the pilot;
4. the deterministic canary ref is inside `refs/heads/vone-canary/*`;
5. exactly one provider POST is attempted;
6. no automatic retry, overwrite fallback or rollback occurs;
7. a subsequent independent READ-only Runner + Verifier path produces canonical E4 evidence;
8. the result is recorded as execution evidence first and `VERIFIED` only after E4 succeeds.

F4b is staging-only and does not authorize release, deploy, production mutation, OperationProof or
any broader GitHub WRITE capability.
