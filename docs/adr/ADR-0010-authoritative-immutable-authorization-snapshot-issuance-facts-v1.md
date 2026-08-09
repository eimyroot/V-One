# Authoritative Immutable Authorization Snapshot & Issuance Facts Boundary v1 — REVISED PROPOSED

| Field | Value |
|---|---|
| Artifact class | Design / decision candidate |
| Status | PROPOSED / PREPARED |
| Runtime effect | None |
| Implementation authorization | NO |
| Runner implementation | NO |
| Production effects | NO |
| Release | NO |
| Deployment | NO |
| Design baseline | `main@459d1c81923d0460da75473a99a167ef49705e02` |
| Historical source evidence bundle SHA-256 | `71099f124d544722c1702453346b61d7c076807dffec4aa09fb836f06b664af7` |
| Risk | R3 |
| Parent constraints | ADR-0007 + adopted ADR-0008 + adopted ADR-0009 |
| Required future gate | Independent R3 architecture + security review before implementation |
| Supersedes candidate | `e6e9cbe922bb6d5f61a38f70ae92427d88afd0fbc8be0d0bd1fb14c28e3b63cf` — not adopted; reconciled to canonical `main@459d1c...` and adopted ADR-0009 |

## 1. Objective

Define the authoritative immutable control-plane evidence that must exist before V-One may construct
an ADR-0007 `execution-grant/v1`, without inventing approval, policy, payload, target, capability, or
validity facts from mutable live state.

This boundary is deliberately separate from:

- signing/JWS and key management;
- transport and peer authentication;
- durable dispatch/outbox implementation;
- Runner one-time consumption;
- capsule runtime;
- target mutation/fencing;
- production effects;
- release and deployment.

## 2. Current-state conclusion

ADR-0007 states that current persisted approval evidence is insufficient to issue an authoritative
v1 grant because required payload, target, capability, policy-version, and approval-validity
bindings are not all authoritative persisted facts.

The completed immutable-review work provides an exact reviewed-request identity, but that identity
does not by itself prove every ADR-0007 issuance field.

Adopted ADR-0009 now makes one immutable authorization snapshot a mandatory precondition for grant
construction and additionally requires an authoritative issuance timestamp source plus a fresh
server-side `execution.run` check at grant issuance. This revision reconciles the snapshot boundary
to those adopted requirements.

Therefore grant issuance remains fail-closed until the control plane can materialize and persist the
exact authorization evidence defined here and the later issuer can satisfy ADR-0009 live issuance
gates.

## 3. Architectural decision

Introduce an immutable control-plane aggregate:

```text
authorization-snapshot/v1
```

One snapshot represents one explicit execution-authorization decision for one `execution_id`.

It is not a mutable cache of a change request and it is not a Runner artifact.

V-One is the only writer.

The snapshot is created from authoritative server-side sources after all required authorization
checks succeed. After commit, its security-relevant content is immutable.

A later grant issuer must construct ADR-0007 objects from the committed snapshot and its exact bound
child objects. It must not rebuild authorization from the current request row, current UI state,
current policy defaults, caller claims, or Runner input.

## 4. Separation of records

Do not collapse authorization evidence and cryptographic issuance into one mutable row.

Use two semantic records:

```text
authorization-snapshot/v1
    |
    | exact immutable input
    v
grant-issuance-record/v1
```

### 4.1 `authorization-snapshot/v1`

Freezes the facts that establish what V-One authorized.

### 4.2 `grant-issuance-record/v1`

Later records the actual issuance event:

- snapshot identity/digest;
- grant ID/digest;
- issue and expiry timestamps;
- signer/key identity;
- signed-envelope digest;
- issuance result.

The issuance record belongs to the grant-issuer / outbox decision and is not implemented by this
design.

This separation prevents an issuance timestamp, signer key, or retry from rewriting the underlying
authorization decision.

## 5. Snapshot identity and content

The snapshot has at least:

```text
schema_version = 1
snapshot_type = authorization-snapshot/v1

snapshot_id
execution_id
request_id
review_content_sha256

actor_id
workspace_id
environment

capability
capability_definition_identity

payload_digest
payload_digest_scheme

target_kind
target_digest
execution_target_identity

policy_version
policy_identity
approval_set_digest
approval_evidence_identity
approval_valid_until

required_permission = execution.run

issuance_timestamp_source_identity

authorized_at
authorization_source_revision

snapshot_digest
```

### 5.1 Identity rules

- `snapshot_id` is unique and never recycled.
- `execution_id` identifies the single execution authorization decision.
- a new authorization decision gets a new `execution_id` and a new snapshot;
- correction/supersession never mutates an existing snapshot;
- `snapshot_digest` is SHA-256 over deterministic canonical snapshot content excluding only its own
  digest field.

### 5.2 Issuance timestamp source binding

`issuance_timestamp_source_identity` is mandatory.

It identifies the accepted server-side time-source / clock-policy generation that a later
ADR-0009 grant issuer is permitted to use when producing `issued_at`. The snapshot does not freeze a
future `issued_at` value, but it must bind the authoritative source identity and rules under which
that value may later be obtained.

The grant issuer must reject issuance when that source is unavailable, unhealthy, stale relative to
accepted policy, or no longer authorized for the snapshot's environment. A client, approver,
transport component, or Runner may never supply or override this identity or the resulting issue
time.

### 5.3 Exact reviewed-request binding

`review_content_sha256` is mandatory.

Snapshot creation fails if the current authoritative request is not exactly the reviewed content
bound to the approvals being used.

The snapshot does not treat a request ID alone as content identity.

## 6. Exact bound child objects

The snapshot must bind exact immutable instances of:

```text
execution-target/v1
approval-evidence-set/v1
```

The preferred semantic rule is:

```text
snapshot.target_digest
    == execution_target.target_digest

snapshot.approval_set_digest
    == approval_evidence_set.approval_set_digest
```

The control plane must be able to retrieve the exact canonical bytes used to obtain those digests.

Storage may be same-database immutable blobs or a later governed content-addressed store, but an
opaque mutable alias is not sufficient.

If exact bytes cannot be retrieved and revalidated, grant issuance is blocked.

## 7. Payload binding

ADR-0007 requires an exact payload digest.

Define a versioned V-One binding scheme rather than hashing an ambiguous transport representation:

```text
payload_digest =
SHA-256(canonical_json({
  "schema_version": 1,
  "binding_type": "request-payload/v1",
  "payload": <exact approved request payload in its canonical JSON domain>
}))
```

The exact approved payload must be the payload contained in the immutable reviewed request identity.

No caller may supply `payload_digest`.

If the actual repository payload type cannot satisfy the canonical JSON domain without lossy
conversion, implementation is BLOCKED until a separate versioned representation decision is made.

## 8. Target binding

`execution-target/v1` must be produced by a reviewed deterministic V-One target binder.

Input may include only authoritative immutable request content plus accepted repository-owned
capability/target policy.

The binder produces:

```text
target_kind
target_claims
target_digest
```

The target object's own ADR-0007 digest remains authoritative.

Forbidden:

- generic adapter fallback;
- payload-selected target parser;
- mutable provider alias treated as identity;
- Runner-derived target;
- handler-derived target;
- target digest supplied by a client.

A capability without an accepted target-binder rule is ineligible for grant issuance.

## 9. Capability binding

The snapshot binds an exact canonical versioned capability plus an immutable
`capability_definition_identity`.

Syntax validity is not enough.

Snapshot creation requires an accepted repository-owned capability definition whose identity is
stable for the lifetime of the authorization.

The separate ADR-0008 capability-registry decision remains required. Until that decision exists,
Runner-directed grant issuance for a capability remains BLOCKED.

No current adapter name is automatically promoted into execution authority.

## 10. Policy version and approval validity

ADR-0007 requires both policy version and approval validity.

The snapshot creator must use a policy revision that is immutable and addressable by an exact
identity.

Required semantics:

```text
policy_version
policy_identity
approval_valid_until
```

`approval_valid_until` is an output of the accepted versioned approval policy. It is not chosen by
the client and is not inferred later by the grant issuer.

If the active approval policy has no accepted versioning or validity rule, snapshot creation is
blocked.

The design does not invent a default approval TTL.

## 11. Approval evidence construction

Build `approval-evidence-set/v1` only from immutable persisted approval decisions that:

- bind the exact reviewed request content used by the snapshot;
- are `APPROVED`;
- satisfy required count and distinct-approver rules;
- satisfy independent/self-approval policy;
- occurred no later than the authorization decision;
- remain inside the accepted policy validity rules.

The policy revision used to evaluate the approval set is frozen into the snapshot.

A later mutable policy lookup cannot silently change what the snapshot claims was authorized.

## 12. Permission and live deny gates

An immutable snapshot is evidence of an authorization decision; it is not an irrevocable bearer
permission.

At snapshot creation V-One must verify the effective server-side `execution.run` permission for the
exact actor/workspace/environment.

At later grant issuance V-One must independently re-check the effective server-side
`execution.run` permission for the exact actor/workspace/environment and all mandatory live deny
gates that are intentionally outside the immutable snapshot, including at least:

- cancellation / supersession that is authoritative by then;
- emergency stop;
- environment/production-effects prohibition;
- capability revocation/ineligibility;
- security invalidation of the relevant policy/authorization generation;
- validity and health of the bound `issuance_timestamp_source_identity`.

A live deny may block issuance. It may not rewrite the snapshot.

Exact cancellation/admission linearization remains a separate ADR-0008 child decision.

## 13. Transaction and consistency boundary

Snapshot creation is one atomic control-plane operation.

Within the authoritative datastore transaction:

1. load and lock/revalidate the exact reviewed request identity;
2. load the exact approval decisions;
3. resolve the accepted immutable policy revision;
4. validate approval count/distinctness/independence;
5. validate `execution.run` and environment eligibility;
6. derive the exact payload binding;
7. derive or resolve the exact accepted capability definition;
8. derive the exact `execution-target/v1`;
9. construct and validate `approval-evidence-set/v1`;
10. construct `authorization-snapshot/v1`;
11. persist the exact immutable child objects and snapshot;
12. append bounded audit evidence;
13. commit.

No external side effect or Runner dispatch occurs inside this transaction.

If any required source changes before commit, the transaction fails/retries from authoritative
state; it must not commit a mixed snapshot.

Exact SQLite statements/isolation implementation require a repository-level implementation plan and
tests. This design does not claim an applied schema.

## 14. Immutability and invalidation

After creation, security-relevant snapshot fields are immutable.

Do not update a snapshot to:

- point at a new request digest;
- replace approvals;
- extend approval validity;
- change policy version;
- change target;
- change payload digest;
- change capability;
- change actor/workspace/environment.

Correction requires a new authorization decision and new snapshot.

Invalidation is represented outside the snapshot as monotonic authoritative state/event evidence.
A revoked/invalidated snapshot remains retained for audit but is ineligible for new grant issuance.

## 15. Idempotency

A retry with the same idempotency key and the same exact authorization inputs returns the same
snapshot identity/content.

The same idempotency key with different authorization content is a conflict and fails closed.

A retry must not silently produce a fresh approval-validity window or different policy revision.

Grant-issuance idempotency is a separate downstream concern.

## 16. Audit evidence

Record at least:

- snapshot ID/digest;
- execution ID;
- request ID;
- review-content digest;
- actor/workspace/environment;
- payload digest and scheme;
- target digest/kind;
- capability and capability-definition identity;
- policy version/identity;
- approval-set digest;
- approval validity;
- authorization timestamp;
- issuance timestamp source identity;
- decision result / bounded rejection reason;
- correlation ID.

Do not log:

- raw secrets;
- credentials;
- unnecessary raw payload;
- unnecessary raw target claims.

Audit evidence is not the source of truth for reconstructing a missing snapshot. Missing
authoritative snapshot bytes fail closed.

## 17. Fail-closed matrix

| Condition | Result |
|---|---|
| Request not in an exact approved immutable-review state | No snapshot |
| Review digest mismatch | No snapshot |
| Missing/legacy approval content binding | No snapshot |
| Approval count/distinctness/independence fails | No snapshot |
| Policy version unavailable/mutable | No snapshot |
| Approval validity rule unavailable | No snapshot |
| `execution.run` denied at snapshot creation | No snapshot |
| `execution.run` denied at later grant issuance | Retain snapshot; no issuance |
| Issuance timestamp source unavailable/unhealthy/stale | Retain snapshot; no issuance |
| Production effects blocked for requested target | No snapshot / no issuance |
| Payload representation ambiguous/lossy | No snapshot |
| Payload digest caller-supplied | Reject |
| Target binder absent/ambiguous | No snapshot |
| Capability unknown or not immutably defined | No snapshot |
| Exact target/approval contract bytes unavailable | No snapshot / no issuance |
| Source changes during snapshot transaction | Abort/re-evaluate |
| Existing idempotency key with different content | Conflict |
| Snapshot invalidated after creation | Retain snapshot; block new issuance |
| Any mandatory fact UNKNOWN | No snapshot / no issuance |

## 18. Security findings

### S-01 — Immutable review identity is necessary but not sufficient

A reviewed-request hash proves exact reviewed content identity. It does not by itself prove
ADR-0007 target, capability, policy version, approval validity, or effective execution permission.

**Control:** immutable authorization snapshot over exact derived/bound issuance facts.

### S-02 — Mutable policy reconstruction can fabricate historical authority

Re-evaluating a current mutable policy later can falsely describe what policy authorized an older
approval set.

**Control:** freeze immutable policy identity and validity semantics in the snapshot.

### S-03 — Target digest without authoritative derivation is attacker-influenceable

A syntactically valid target digest supplied or derived from a mutable alias does not establish the
approved target.

**Control:** deterministic reviewed V-One target binder + exact target object identity.

### S-04 — Snapshot immutability must not defeat revocation

Treating a historical authorization snapshot as permanently usable would bypass emergency stop,
cancellation, or later security revocation.

**Control:** snapshot is immutable evidence; grant issuance still checks authoritative live deny
gates.

### S-05 — Retry must not refresh authority

A retry that creates new timestamps, policy versions, or approval deadlines can extend authorization
without a new decision.

**Control:** idempotent snapshot creation; changed authorization inputs require a new decision.

## 19. Verification requirements for future implementation

At minimum:

- deterministic snapshot digest golden vectors;
- same inputs => same idempotent snapshot;
- changed security-relevant field => changed snapshot digest / conflict;
- stale/tampered review-content binding rejection;
- legacy approval without exact binding rejection;
- self-approval and insufficient/distinct-approver negative tests;
- policy-version and approval-validity negative tests;
- issuance timestamp source identity/health/freshness negative tests;
- `execution.run` revocation between snapshot creation and grant issuance;
- payload canonicalization vectors and Unicode/boundary cases;
- target-binder golden/adversarial vectors;
- unknown capability rejection;
- transaction race test: request/approval/policy changes during creation;
- exact child-object retrieval and digest revalidation;
- invalidation after snapshot blocks issuance without mutating snapshot;
- no Runner, adapter, or external effect is invoked;
- migration mixed-version behavior if schema is added;
- audit records contain digests/identities but no secrets.

Independent R3 architecture/security review remains required over the exact implementation design and
candidate diff.

## 20. Dependencies and open decisions

This proposal intentionally does not resolve:

1. the exact repository schema/table mapping;
2. capability-registry schema/release governance;
3. concrete target binder for any capability;
4. accepted policy-version generation mechanism if none exists today;
5. accepted approval-validity rule/TTL;
6. content-addressed target/payload storage;
7. cancellation/admission linearization;
8. grant signing/JWS implementation;
9. transactional outbox;
10. Runner durable consume store;
11. pre-state/version binding required for mutating capabilities.

Items 2–5 are prerequisites for actual authoritative Runner grant issuance. Their absence does not
authorize fabricated fallback values.

## 21. Migration / rollback principles

Implementation, if separately authorized, should follow an expand-first migration:

```text
add immutable snapshot storage
→ write snapshot only behind disabled/no-effect path
→ verify deterministic bindings and migration compatibility
→ make grant issuer depend on snapshot
→ only later connect to no-effect dispatch
```

Rollback before any dispatch integration is:

- stop creating new snapshots;
- leave immutable historical rows/evidence in place;
- continue current execution path;
- do not reinterpret snapshot rows as active execution authority.

No destructive backfill is required. Legacy approvals that lack required authoritative fields remain
ineligible rather than being upgraded with invented data.

## 22. Adoption boundary

This artifact is `PROPOSED / PREPARED`. It supersedes the unadopted snapshot candidate with
SHA-256 `e6e9cbe922bb6d5f61a38f70ae92427d88afd0fbc8be0d0bd1fb14c28e3b63cf`.

It does not modify the repository or current execution behavior.

Adoption freezes this design intent only. It does not authorize:

- database/schema implementation;
- application code;
- Runner implementation;
- signing/crypto;
- outbox/transport;
- capability execution;
- production effects;
- commit/push/PR/merge;
- release/deployment.

Any implementation requires a separate exact scoped authorization and current repository reality
check.
