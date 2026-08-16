# V-One Verifiable Operations Trust Plane

Status: TARGET ARCHITECTURE / NOT A RUNTIME CLAIM
Scope: V-One / VOODOO One
Source basis: competitive architecture research, current V-One governance model, and the accepted implementation direction after Authorization Snapshot persistence.

## 1. Product position

V-One is not a generic agent platform, workflow engine, cloud provider, chatbot dashboard, or remote shell.

V-One is a provider-neutral control plane for proof-carrying operations.

Its job is to transform consequential human, AI, or system intent into an operation that is:

1. semantically exact;
2. reviewed where required;
3. authorized against authoritative state;
4. narrowed into a short-lived execution grant;
5. dispatched after durable commit;
6. executed by an isolated runner;
7. checked by an independent verifier;
8. represented by portable evidence and proof.

Canonical phrase:

```text
INTELLIGENCE MAY PROPOSE.
AUTHORITY MAY AUTHORIZE.
EVERY DOWNSTREAM LAYER MAY ONLY NARROW THAT AUTHORITY.
RUNNER MAY EXECUTE.
ONLY AN INDEPENDENT VERIFIER MAY PROVE THE RESULT.
```

## 2. Core invariant

```text
V-ONE
=
CANONICAL OPERATION LANGUAGE
+
SMALL IMMUTABLE TRUST KERNEL
+
VERSIONED OPERATION SEMANTICS
+
MASSIVELY SCALABLE CAPABILITY CATALOG
+
CONFORMANCE-TESTED MODULE ECOSYSTEM
+
DISTRIBUTED EXECUTION FABRIC
+
INDEPENDENT VERIFICATION
+
PORTABLE PROOF
```

Scaling invariant:

> The number of providers, services, modules, and capabilities may grow massively. The trusted core must not grow proportionally with them.

## 3. Main architectural flow

```text
HUMAN / AI / SYSTEM
        |
        v
EDGE / INTEROPERABILITY
API | CLI | MCP | A2A | AI frameworks | Webhooks
        |
        v
SEMANTIC PLANE
Intent -> VOP -> ReviewedOperation -> CapabilityDefinition -> ExpectedPostState
        |
        v
AUTHORITY PLANE
Permission Authority
Immutable Policy Authority
Capability Activation
Target Binder
Approval Certificate
Trusted Clock
Emergency / Revocation Authority
        |
        v
AuthorityWitnessSet
        |
        v
AuthorizationSnapshot
        |
        v
Monotonic Commit Guard
        |
        v
ExecutionGrant
        |
        v
EXECUTION PLANE
Transactional Outbox -> Dispatch -> Dispatch Inbox / Dedup / Epoch Fence
-> RunnerIdentity -> Credential Broker -> ExecutionCapsule
-> Isolated Runner -> Exact Handler
        |
        v
REAL EFFECT
        |
        v
VERIFICATION PLANE
Separate VerifierIdentity
Separate read credentials
ExpectedPostState + ObservedPostState -> VerificationResult
        |
        v
PROOF PLANE
Content-addressed Evidence Graph -> Attestation -> OperationProof -> Operation Passport
        |
        v
ADAPTIVE PLANE
CyberCore: observe -> compare -> propose -> sandbox -> benchmark -> semantic equivalence -> conformance -> adoption candidate
```

## 4. Monotonic Authority

After an authorization decision exists, every downstream layer may only:

```text
KEEP
NARROW
EXPIRE
REVOKE
DENY
```

It may never:

```text
WIDEN
```

Formal intuition:

```text
S0 = authorized scope
S1 subset-of S0
S2 subset-of S1
S3 subset-of S2
...
or DENY
```

A grant may narrow a snapshot. A runner may enforce a grant. A verifier may fail a result. No downstream component may add privilege that was not present upstream.

## 5. AuthorityWitnessSet

`AuthorityWitnessSet` is an explicit digest-bearing set of the authority facts used to produce an `AuthorizationSnapshot`.

Purpose:

- make snapshot provenance externally understandable;
- keep snapshot construction auditable;
- allow portable proof without exposing internal SQL tables;
- make drift and TOCTOU risks visible.

Conceptual fields:

```json
{
  "permission_decision": "sha256:...",
  "capability_activation": "sha256:...",
  "target_binding": "sha256:...",
  "policy_revision": "sha256:...",
  "approval_certificate": "sha256:...",
  "clock_witness": "sha256:...",
  "revocation_epoch": 481
}
```

Rule:

```text
AuthorityWitnessSet -> AuthorizationSnapshot
```

A snapshot is authorization evidence, not execution permission.

## 6. ExecutionCapsule

`ExecutionCapsule` binds the executable implementation and execution environment to the grant.

Handler identity alone is not enough. The capsule must eventually describe the exact implementation environment:

```text
handler_digest
module_manifest_digest
container/rootfs digest
dependency lock digest
SBOM identity
network policy digest
resource limit profile
credential requirement
runner class
verification contract identity
```

`ExecutionGrant` should bind `execution_capsule_digest`.

This prevents an operation from being approved for handler X while being executed under altered dependencies, image, network policy, or verifier contract.

## 7. Dispatch Inbox and Epoch Fencing

Transactional Outbox is necessary but incomplete for robust execution. V-One should also model a dispatch inbox with leases and execution epochs.

```text
Outbox -> Dispatch -> Inbox -> Claim -> Lease -> Execute
```

A dispatch envelope should preserve:

```text
dispatch_id
execution_id
grant_id
execution_epoch
capsule_digest
correlation_id
causation_id
```

Invariant:

```text
A stale execution attempt may not complete an operation after a newer epoch has been issued.
```

This protects against split-brain execution, late worker completion, retry races, and failover artifacts.

## 8. Runner and Verifier separation

Runner and verifier must be logically and credential-wise separate.

```text
RunnerIdentity != VerifierIdentity
RunnerCredential != VerifierCredential
```

Runner credential:

```text
minimum permission required to cause the approved effect
```

Verifier credential:

```text
read-only permission required to observe the effect
```

A compromised runner must not be able to manipulate the verification channel.

## 9. CapabilityDefinition must include verifiability

A capability is not production-eligible just because a handler exists.

A serious capability definition must describe:

```text
logical identity
version
semantic description
effect class
idempotency class
reversibility class
verification class
credential class
evidence class
supported environments
required permissions
approval class
policy class
target kind
deterministic binder
handler identity requirements
credential requirements
receipt semantics
verification strategy
compensation semantics
production eligibility
```

Rule:

```text
HIGH-RISK MUTATION + NO INDEPENDENT VERIFIER = NOT PRODUCTION ELIGIBLE
```

## 10. VerificationStrength

Not all verification is equal.

Canonical levels:

```text
V0  NONE
V1  EXECUTOR_ASSERTION
V2  INDEPENDENT_CODE_PATH
V3  INDEPENDENT_IDENTITY + PROVIDER READ
V4  EXTERNAL / CRYPTOGRAPHIC ATTESTATION
```

`OperationProof` must state verification strength rather than pretending all PASS results are equivalent.

## 11. Semantic AI policy is deny-only

A probabilistic semantic/LLM guard may reduce risk by escalating or denying an operation.

It must never turn deterministic denial into allow.

```text
DETERMINISTIC AUTHORITY -> candidate ALLOW
SEMANTIC SAFETY GUARD -> ALLOW_UNCHANGED | ESCALATE | DENY
```

Forbidden:

```text
DETERMINISTIC DENY -> LLM SAYS OK -> ALLOW
```

## 12. Durable orchestration direction

Do not rewrite V-One to Temporal, Restate, DBOS, or Zeebe now.

Current preferred implementation:

```text
SQLite/Postgres
+
explicit transactions
+
append-only evidence
+
transactional outbox
+
dispatch inbox
+
leases
+
idempotency
```

Add an internal port:

```python
class DurableCoordinator(Protocol):
    ...
```

Potential future implementations:

```text
Native DB coordinator
DBOS
Restate
Temporal
```

The Authority Kernel must remain independent of orchestration technology.

## 13. Event model direction

Do not perform a full event-sourcing rewrite now.

Preferred current model:

```text
RELATIONAL CURRENT STATE
+
APPEND-ONLY SECURITY / EVIDENCE EVENTS
```

Relational tables own current operational state. Append-only evidence owns history, proof, audit, and lineage.

## 14. OperationProof standards direction

Do not invent custom cryptography.

Preferred future direction:

```text
in-toto Statement
-> V-One OperationProof Predicate
-> DSSE-compatible Envelope
-> Sigstore-style identity signing
```

Possible predicate type:

```text
https://v-one.dev/attestation/operation-proof/v1
```

## 15. MCP/A2A/agent frameworks boundary

MCP, A2A, OpenAI Agents SDK, Google agents, AWS agents, Microsoft agents, Claude agents, and custom agents are edge or interop inputs.

They are not V-One authority primitives.

```text
MCP / A2A / Agents
        |
        v
EDGE
        |
        v
VOP
        |
        v
V-One authority model
```

Forbidden equivalence:

```text
MCP permission = V-One authorization
```

## 16. Current-code implementation direction

Current repository shape is still a reasonable modular monolith.

Do not perform a mass rename into `vone_kernel`, `vone_framework`, etc. until boundaries have stabilized through behavior.

Near-term additions should remain inside the current package and be extracted later only when responsibilities are proven.

Conceptual target files:

```text
voodoo_product/
├── vop_vocabulary.py
├── authority_witness.py
├── policy_authority.py
├── permission_authority.py
├── capability_registry.py
├── target_binding.py
├── authorization_snapshot_creator.py
├── execution_grant.py
├── grant_issuer.py
├── grant_replay_store.py
├── revocation.py
├── execution_capsule.py
├── handler_registry.py
├── runner_registry.py
├── verifier_registry.py
├── outbox.py
├── dispatch.py
├── dispatch_inbox.py
├── execution_lease.py
├── runner_protocol.py
├── credential_broker.py
├── execution_receipt.py
├── verification.py
├── evidence_graph.py
└── operation_proof.py
```

Future extraction:

```text
vone_contracts
vone_kernel
vone_framework
vone_module_sdk
vone_modules
```

## 17. Implementation roadmap

### Phase 0 — Truth and repository governance

```text
current state reconciliation
post-merge CI verification
CASER refresh
branch protection / required CI
```

Gate:

```text
CURRENT STATE TRUSTWORTHY
```

### Phase 1 — Authority Kernel completeness

```text
PolicyRevision authority
Permission authority
CapabilityDefinition
CapabilityActivation
TargetBinder
ApprovalCertificate
TrustedClock
AuthorityWitnessSet
```

Gate:

```text
NO SNAPSHOT FROM CALLBACKS, PLACEHOLDERS, OR MUTABLE CURRENT STATE
```

### Phase 2 — Snapshot Creator

```text
ONE SQL TRANSACTION

authority reads
+
snapshot construction
+
persistence
+
audit
```

Negative cases:

```text
stale approval
wrong workspace
inactive capability
missing permission
target mismatch
policy drift
clock expiry
transaction rollback
```

### Phase 3 — Grant / execution contract

```text
ExecutionGrant
ExecutionCapsule
HandlerRegistry
RunnerRegistry
ReplayStore
Revocation / EmergencyStop
```

Grant binds:

```text
snapshot
execution
capability
target
payload
runner
capsule
TTL
jti
```

### Phase 4 — Durable dispatch

```text
Transactional Outbox
-> Dispatch
-> Inbox
-> execution lease
-> epoch fencing
```

Gates:

```text
NO PROVIDER CALL BEFORE COMMIT
NO STALE ATTEMPT MAY COMPLETE
```

### Phase 5 — READ-ONLY isolated Runner

Start only with:

```text
filesystem.inspect
git.inspect
repository.inspect
python.test
node.test
static_analysis
provider.read
```

Default restrictions:

```text
network deny-by-default
no global secret vault
no generic shell fallback
no production mutation
```

### Phase 6 — Independent verification

```text
RunnerIdentity != VerifierIdentity
Runner credentials != Verifier read-only credentials
VerificationStrength included
```

Critical negative case:

```text
Receipt SUCCESS + Verifier FAIL = VERIFICATION_FAILED
```

### Phase 7 — Proof

```text
Evidence Graph
-> content identities
-> OperationProof
-> in-toto predicate
-> optional Sigstore-compatible envelope
```

### Phase 8 — Freeze OperationCell/v1

```text
ReviewedOperation
-> AuthorityWitness
-> Snapshot
-> Grant
-> Capsule
-> Dispatch
-> Runner
-> Receipt
-> Verification
-> Proof
```

### Phase 9 — Operation Graph

```text
OperationCell[] -> bounded DAG
```

Invariant:

```text
Parent authority != child authority
```

### Phase 10 — Module ecosystem

Each module must provide:

```text
CapabilityDefinition
Binder
Handler
Verifier
CredentialContract
EvidenceContract
ConformanceEvidence
ExecutionCapsule
```

### Phase 11 — CyberCore

CyberCore starts after trusted execution substrate exists.

```text
observe
-> discover patterns
-> generate candidate
-> sandbox
-> benchmark
-> semantic equivalence
-> conformance
-> human/policy adoption
```

CyberCore cannot activate its own candidate.

## 18. Forbidden shortcuts

Do not allow:

1. generic shell as core capability;
2. provider SDK imports in the kernel;
3. LLM-based ALLOW;
4. runtime credential broader than grant;
5. runner selecting handler;
6. handler without verification contract;
7. receipt treated as verified;
8. auto-activation of CyberCore candidates;
9. parent-to-child authority inheritance;
10. microservices solely for enterprise aesthetics;
11. SandCloud artifact becoming project truth without promotion gate;
12. simulated result presented as real provider state.

## 19. Final position

Preferred product positioning:

```text
VOODOO ONE
Verifiable Operations Trust Plane
```

Technical positioning:

```text
Provider-neutral control plane for proof-carrying operations.
```

## 20. Next safe implementation move

Do not build Runner next.

Immediate sequence:

```text
1. adopt this architecture as target documentation;
2. add canonical vocabulary and schema direction;
3. harden repository governance;
4. implement AuthorityWitnessSet as contract;
5. audit/implement policy, permission, capability activation, target binding, trusted clock, and approval certificate prerequisites;
6. implement AuthoritativeSnapshotCreator in one transaction.
```
