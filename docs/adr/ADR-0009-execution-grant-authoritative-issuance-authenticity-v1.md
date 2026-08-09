# Execution Grant Authoritative Issuance & Authenticity Boundary v1 — REVISED PROPOSED

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
| Design baseline | `main@69b152e18def66b5e410d3040081bb7dddabbc95` |
| Evidence bundle SHA-256 | `71099f124d544722c1702453346b61d7c076807dffec4aa09fb836f06b664af7` |
| Slice risk | R3 |
| Required future gate | Independent R3 architecture + security review before implementation |
| Supersedes candidate | `87ad6144ebfab8687f07e6e86f35f5c9e6898a818476ed9edb66b447ce864320` — not adopted; custom signature framing removed |

## 1. Decision objective

Define who may authoritatively issue an ADR-0007 `execution-grant/v1`, what evidence must exist before
issuance, how the exact grant bytes are authenticated across storage and transport boundaries, how a
Runner verifies issuer trust without gaining issuer authority, and how expiry, key revocation,
cancellation, replay, and audit evidence interact.

This decision does not authorize or implement a Runner, transport, durable consume store, capsule,
production effect, release, or deployment.

## 2. Current-state findings

The accepted ADR-0007 pure contracts provide deterministic representations and digest/cross-contract
validation only. A grant digest is not a signature and does not establish authoritative provenance.

ADR-0008 preserves V-One as the sole authorization and execution-lifecycle authority. The Runner
must never mint or broaden grants and must never authorize itself. ADR-0008 also requires signed
envelope/trust work as a separate R3 decision and explicitly states that replay resistance belongs
to a durable Runner-side one-time claim store rather than to the grant digest or signature.

MVP-2 strengthened the change-request review boundary by binding approvals to immutable reviewed
request content. That improvement is necessary but is not by itself sufficient evidence for all
ADR-0007 `approval-evidence-set/v1` fields. In particular, this design run has no direct evidence of
an authoritative persisted target digest, capability binding, immutable policy version, and approval
validity deadline suitable for grant issuance. Those values must not be invented from live mutable
state.

## 3. Decision

### 3.1 Authoritative issuer

V-One is the only grant-issuance authority.

A dedicated control-plane `GrantIssuer` boundary may construct an `execution-grant/v1` only after
authoritative server-side checks have succeeded. Clients, approvers, PDG/CyberCore, dispatch,
transport, Runner ingress, capability handlers, and receipt ingestion have no minting authority.

The issuer acts on an already-authorized execution intent. Approval of a change request is not
equivalent to permission to execute it. The issuer must separately verify the effective
`execution.run` permission and all environment / production-effect gates.

### 3.2 Mandatory issuance evidence

Before grant construction, the issuer must possess one immutable authorization snapshot that binds
at least:

- `request_id`;
- immutable reviewed-request identity;
- `execution_id`;
- `actor_id`;
- `workspace_id`;
- environment;
- canonical versioned capability;
- exact `payload_digest`;
- exact `target_kind` and `target_digest`;
- immutable policy version;
- exact immutable approval records and distinct approver identities;
- approval validity deadline;
- required permission `execution.run`;
- authoritative issuance timestamp source.

Every field used to construct ADR-0007 target, approval-evidence, or grant claims must be either
persisted immutably or deterministically derivable from persisted immutable bytes under a versioned
algorithm. The issuer must not reconstruct authorization from mutable live policy, mutable aliases,
client claims, Runner observations, or current UI state.

If any required binding is missing, ambiguous, stale, or cannot be derived under an accepted
versioned rule, issuance fails closed.

### 3.3 Target and capability binding

No generic adapter/payload fallback is permitted.

A grant may be issued only for a capability whose reviewed binding logic can produce the exact
ADR-0007 capability and `execution-target/v1` identity from approved immutable request data. Unknown
or syntax-valid-but-unregistered capability values fail closed.

Mutating execution remains blocked until the separate ADR-0008 pre-state / conditional-mutation
authorization requirement is accepted. This design does not smuggle pre-state authority into the
existing ADR-0007 grant.

### 3.4 Grant identity and idempotent issuance

`grant_id` is a unique issuance identity; `grant_digest` remains the ADR-0007 deterministic content
identity.

A retry of the same committed issuance operation must return the same immutable grant/envelope
bytes. It must not silently create a new `grant_id`, new `issued_at`, new expiry, or a different
signature envelope.

A genuinely new authorization decision may create a new grant. It must not mutate or recycle an
existing grant identity.

The exact persistence/outbox transaction mechanism remains a separate implementation decision, but
implementation must make grant identity and the exact signed envelope durable before dispatch can
expose it.

## 4. Authenticity envelope

### 4.1 Envelope profile

Use a standards-based **JWS Compact Serialization** profile rather than a project-specific signature
framing.

The JWS payload is the exact UTF-8 bytes of the existing deterministic `canonical_json` encoding of:

```json
{
  "schema_version": 1,
  "envelope_type": "execution-grant-envelope/v1",
  "issuer_id": "v-one/control-plane",
  "audience": "voodoo-runner/v1",
  "grant": { "<exact execution-grant/v1 object>": "..." }
}
```

The JWS Protected Header is restricted to:

```json
{
  "alg": "Ed25519",
  "kid": "<opaque versioned key id>",
  "typ": "voodoo-execution-grant+jws"
}
```

The profile permits no unprotected JWS header.

The profile forbids remote or grant-controlled key discovery fields such as `jku`, embedded `jwk`,
`x5u`, or `x5c`. `kid` is only a lookup hint into the Runner's independently configured trust
policy; it is never authority by itself.

The Runner accepts only the exact fully specified algorithm identifier `Ed25519`. Algorithm
selection from untrusted input is not negotiation. `none`, polymorphic `EdDSA`, HMAC algorithms,
RSA algorithms, ECDSA algorithms, and every unknown algorithm fail closed in v1.

`issuer_id`, `audience`, `envelope_type`, and the embedded grant are integrity protected because
they are carried inside the signed JWS payload. `alg`, `kid`, and `typ` are integrity protected
because they are carried only in the JWS Protected Header.

### 4.2 Signature input and canonical payload

No project-specific cryptographic signing preimage is defined.

JWS itself defines the cryptographic signing input. The application supplies only:

1. the exact protected-header JSON for this profile;
2. the exact canonical UTF-8 payload bytes above;
3. the issuer private key identified by the locally authorized `kid`.

The deterministic `canonical_json` payload encoding is retained only to preserve stable project
content identity and reproducible bytes. It does not replace JWS and does not alter the
standard-defined JWS signing operation.

The Runner must still perform ADR-0007 structural validation, self-digest validation, and exact
cross-contract binding validation after successful JWS verification. A valid JWS over structurally
invalid or cross-contract-inconsistent claims is rejected.

### 4.3 Why asymmetric JWS / Ed25519

Symmetric HMAC is rejected for this boundary because a Runner holding the verifier secret would also
possess minting capability. That conflicts with the invariant that the Runner never authorizes
itself.

Transport-only authentication is also insufficient. Peer authentication can authenticate a live
connection but does not provide durable authenticity for grant bytes stored in an outbox,
redelivered later, or retained as evidence.

Signing only `grant_digest` is rejected because issuer, audience, envelope type, key identity, and
the complete exact grant must participate in the authenticated context.

JWS is selected instead of a custom signature envelope because the project security standard
forbids inventing a custom cryptographic protocol when an established standard satisfies the
boundary. The v1 algorithm profile uses the fully specified JOSE algorithm identifier `Ed25519`.

Crypto provider/library selection remains implementation work and requires dependency,
interoperability, test-vector, and supply-chain review.

## 5. Key ownership and trust policy

### 5.1 Separation

- Issuer private keys exist only inside the V-One signing boundary / approved keystore.
- Runner nodes receive public verification material only.
- Capability handlers receive neither issuer private keys nor trust-policy write authority.
- Dispatch and transport receive no signing authority.
- The Runner cannot add a trusted issuer or key from grant-controlled data.

### 5.2 Trust record

Each trusted `key_id` binds exactly:

- issuer identity;
- Ed25519 public key;
- exact allowed JWS algorithm (`Ed25519` in v1);
- allowed audience;
- allowed environments;
- key state;
- activation time;
- optional retirement time;
- trust-policy generation.

JWS protected-header or payload claims never override the local trust record. The local trust record must independently authorize the exact issuer, audience, key identity, environment, and `Ed25519` algorithm.

### 5.3 Key states

Use these semantic states:

- `ACTIVE_FOR_ISSUE` — may sign new grants and verify existing grants;
- `VERIFY_ONLY` — must not sign new grants; may verify grants that were issued while the key was
  authorized and remain within their grant lifetime;
- `REVOKED` — no unconsumed grant signed by the key is admissible.

A revoked key is never restored to an issuing state. Recovery uses a new key identity.

### 5.4 Rotation

Planned rotation:

1. distribute and verify trust for a new public key;
2. mark the new key `ACTIVE_FOR_ISSUE`;
3. stop new issuance on the old key and mark it `VERIFY_ONLY`;
4. retain verification until every legitimately issued grant under the old key is beyond its
   ADR-0007 expiry plus accepted clock-skew allowance;
5. retire/remove the old key only after audit confirms no valid unconsumed grant can remain.

### 5.5 Compromise and emergency revocation

On suspected issuer-key compromise:

1. stop grant issuance and dispatch;
2. activate the project emergency-stop path;
3. publish a higher-generation trust policy marking the compromised key `REVOKED`;
4. block admission when Runner trust state is stale or cannot establish that revocation generation;
5. inventory all grants signed by the compromised key from the suspected compromise point;
6. reconcile already-consumed attempts and post-state evidence;
7. issue a new key identity only after trust propagation is verified.

Key revocation does not erase history and cannot prove that already-consumed work had no effect.

## 6. Expiry, cancellation, and replay

### 6.1 Expiry

ADR-0007 remains authoritative:

- expiry is strictly after issue time;
- grant TTL is positive and no more than 300 seconds;
- grant expiry is no later than approval validity.

The issuer computes expiry only from accepted server-side policy:

```text
expires_at =
  min(
    issued_at + configured_grant_ttl,
    approval_valid_until
  )
```

A client cannot choose or extend TTL.

Exact tolerated clock skew remains a separately reviewed operational parameter. If clock health or
the required trust-policy freshness cannot be established, admission fails closed.

### 6.2 Cancellation is not cryptographic revocation

Work-level cancellation remains V-One lifecycle authority under ADR-0008. It is not represented by
editing or re-signing an issued grant.

Runner admission must consume against the exact authoritative cancellation/admission decision
identity or generation defined by the future cancellation/transport decision.

### 6.3 Signature does not prevent replay

A correctly signed grant is replayable bytes. Authenticity proves who signed the bytes; it does not
provide one-time use.

`ONE_TIME` is enforced only by the ADR-0008 durable atomic Runner claim store keyed by `grant_id`
with immutable `grant_digest`. Duplicate delivery must resolve to the existing claim/attempt/receipt
identity and must never invoke a handler twice.

This authenticity decision therefore does not satisfy the durable-consumption blocker.

## 7. Verification procedure at Runner ingress

For every received envelope, in this order:

1. enforce bounded transport/message size before parsing;
2. parse JWS Compact Serialization under the exact v1 profile;
3. reject any unsupported protected-header member, missing required member, or forbidden algorithm/key-discovery behavior;
4. require `typ=voodoo-execution-grant+jws` and `alg=Ed25519` exactly;
5. resolve `kid` only from local trusted policy and require an allowed key state;
6. require sufficiently fresh trust-policy generation;
7. verify the JWS signature before trusting payload claims;
8. strict-parse the signed payload; require exact schema, envelope type, issuer, and audience;
9. require the local trust record to authorize that issuer/audience/environment binding;
10. strict-parse ADR-0007 grant and verify its self-digest;
11. obtain exact target and approval-evidence objects through the governed dispatch/content boundary;
12. run ADR-0007 `validate_bindings`;
13. verify environment, capability registry, expiry, cancellation/admission, and local admission
    gates;
14. only then proceed to the separate durable one-time consumption boundary.

Failure before a valid grant can be authoritatively bound is a protocol rejection and produces no
execution receipt. A valid bound grant that fails an admission gate may follow ADR-0008 `REJECTED`
receipt semantics.

## 8. Audit and evidence contract

### 8.1 Issuer audit record

Persist an immutable issuance evidence record containing at least:

- `grant_id`;
- `grant_digest`;
- `execution_id`;
- `request_id`;
- immutable review-content identity;
- `approval_set_digest`;
- policy version;
- target digest;
- payload digest;
- capability;
- actor/workspace/environment;
- issuer identity;
- `key_id`;
- algorithm;
- issued/expiry timestamps;
- envelope digest;
- authorization-snapshot digest;
- issuance result.

Do not record raw request payload, raw target claims, private keys, secrets, or provider credentials.

### 8.2 Runner verification evidence

Record bounded verification evidence:

- envelope digest;
- grant ID and grant digest;
- issuer ID;
- key ID;
- algorithm;
- trust-policy generation/digest;
- verification timestamp;
- decision (`VERIFIED` / bounded rejection reason);
- observed clock-health state.

Signature bytes may be retained only where evidence policy requires them; they are not secret, but
retention remains bounded.

### 8.3 Evidence semantics

A successful signature verification means only:

> the exact envelope bytes were signed by a key that the Runner's current trust policy accepted for
> this issuer/audience at verification time.

It does not prove that approvals were semantically correct, that the target is safe, that the grant
was not replayed, that the capability succeeded, or that a production effect is authorized.

## 9. Fail-closed matrix

| Condition | Result |
|---|---|
| Unknown issuer or key | Reject |
| Algorithm mismatch | Reject |
| Unknown envelope field | Reject |
| Audience mismatch | Reject |
| Signature invalid | Reject |
| Trust policy stale/unavailable | Reject |
| Key revoked | Reject |
| Grant self-digest invalid | Reject |
| Missing target/approval evidence | Reject |
| Cross-contract binding mismatch | Reject |
| Missing immutable policy version | Do not issue / reject |
| Missing approval validity | Do not issue / reject |
| Missing target digest/capability authority | Do not issue / reject |
| Expired / not-yet-valid grant | Reject |
| Cancellation precedes authoritative admission | Reject without consume |
| Duplicate valid delivery | Resolve through durable claim store; never execute twice |
| Production-like target while production effects blocked | Reject |
| Uncertain authorization fact | Do not issue / reject |

## 10. Security review findings

### S-01 — Current digests are not authenticity

ADR-0007 digest validation detects content changes but does not authenticate provenance.

**Treatment:** mandatory asymmetric JWS profile with a locally pinned trust policy.

### S-02 — Symmetric verification would create shadow minting authority

A Runner with a shared MAC secret could mint bytes indistinguishable from V-One-issued grants.

**Treatment:** asymmetric issuer signing; Runner holds public verification material only.

### S-03 — Current authorization persistence is not yet proven sufficient for ADR-0007 issuance

The reviewed source bundle does not prove authoritative persisted values for every required
ADR-0007 approval/target/capability/policy-validity binding.

**Treatment:** fail closed. Implementation requires a separately reviewed immutable authorization
snapshot / derivation boundary. No values may be invented from mutable live state.

### S-04 — Authenticity is independent from replay resistance

A valid signature does not make the grant one-time.

**Treatment:** preserve ADR-0008 durable atomic claim-store blocker.

### S-05 — Key revocation and work cancellation are distinct authorities

Conflating them can create false assumptions about side effects.

**Treatment:** key revocation controls cryptographic trust; V-One cancellation controls work
admission/stop intent.

### S-06 — Stale trust state can defeat emergency revocation

A Runner with indefinitely cached trust could continue accepting a compromised key.

**Treatment:** versioned/fresh trust policy; admission fails closed when required freshness cannot be
established. Exact transport/distribution and skew budgets require a separate implementation-ready
decision.

## 11. Architecture review

The proposed boundary is coherent with ADR-0007 and the owner-adopted ADR-0008 design:

- V-One remains the sole authorization/lifecycle authority;
- the Runner gains verification capability but no minting authority;
- authentication is layered on top of, not substituted for, ADR-0007 binding validation;
- signature semantics do not claim replay resistance;
- cancellation and one-time consumption remain separate state-machine concerns;
- no raw payload, target claims, or secrets are added to the grant;
- production effects remain blocked.

No architecture reason was found to prefer HMAC, transport-only authentication, or digest-only
authenticity over the asymmetric envelope.

## 12. Implementation blockers that remain after this design

This design does **not** make Runner implementation ready. At minimum, the following remain required
before runtime work:

1. authoritative immutable authorization snapshot / derivation for all ADR-0007 issuance facts;
2. accepted capability/target binding rules and capability-registry governance;
3. accepted pre-state/version binding for mutating work;
4. concrete trust-policy distribution, freshness, root-key, key-storage, and compromise-recovery
   implementation design;
5. transport and peer-authentication design;
6. durable outbox / issuance persistence transaction;
7. durable Runner one-time consumption / lease / fence store;
8. independent R3 architecture and security review over exact proposed implementation;
9. production effects remain blocked under a separate R4 boundary.

## 13. Alternatives rejected

### HMAC/shared secret

Rejected because the verifier would possess minting capability.

### mTLS only

Rejected because transport authentication does not authenticate persisted/redelivered grant bytes
as durable evidence.

### Digest only

Rejected because a digest has no issuer authenticity.

### Signature over only `grant_digest`

Rejected because issuer/key/audience context must also be bound.

### Custom project-specific signature framing

Rejected because an established JOSE/JWS standard can provide the signing container and verification semantics without inventing a project-specific cryptographic protocol.

### Runner-generated or Runner-refreshed grants

Rejected because the Runner must never authorize itself or broaden V-One authority.


## 14. Standards profile

This design profile is based on:

- JWS Compact Serialization / JWS protected-header semantics;
- a fully specified `Ed25519` JOSE algorithm identifier;
- strict application-side algorithm allowlisting, issuer/audience validation, and explicit typing.

The project profile is intentionally narrower than the underlying JOSE feature set. Unsupported
algorithms, unprotected headers, remote key-discovery fields, and cross-protocol substitution are
rejected.

## 15. Adoption and implementation boundary

This artifact is `PROPOSED / PREPARED`.

It does not alter ADR-0007 or ADR-0008, does not modify the repository, and does not create runtime
authority.

Adoption requires an explicit owner decision over exact reviewed bytes. Implementation requires a
separate scoped implementation authorization after the required independent R3 review and all
relevant child decisions.

No commit, push, PR, merge, release, deployment, production effect, Runner service, or crypto
dependency is authorized by this design artifact.
