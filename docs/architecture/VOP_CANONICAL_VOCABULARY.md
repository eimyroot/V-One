# VOP Canonical Vocabulary v1

Status: PREPARED / PROPOSED FOR ADOPTION

## Architectural invariant

```text
ONE SYSTEM
=
ONE SEMANTIC LANGUAGE
```

> One meaning → one term → one contract → one authoritative definition.

VOP is the canonical semantic language inside V-One. It is not a second protocol beside V-One and it is not provider transport syntax.

External systems may use their own vocabulary. Provider-specific language remains behind the Module boundary and is translated into canonical VOP semantics before governance.

```text
external provider semantics
        ↓
      Module
        ↓
canonical VOP semantics
```

## Canonical operation chain

```text
ACTOR
↓
INTENT
↓
OPERATION
↓
CAPABILITY
↓
TARGET
↓
INPUT
↓
EXPECTED POST-STATE
↓
POLICY
↓
APPROVAL
↓
AUTHORIZATION
↓
GRANT
↓
EXECUTION
↓
RECEIPT
↓
VERIFICATION
↓
EVIDENCE
↓
PROOF
```

## Canonical nouns

| Term | Single meaning |
|---|---|
| Actor | who initiates or performs a role in the process |
| Intent | desired outcome before precise operationalization |
| Operation | governed unit of work |
| ReviewedOperation | exact content submitted to governance |
| Capability | what the system can semantically do |
| Input | operation data |
| Target | authoritatively identified object of effect |
| ExpectedPostState | state that must exist after successful execution |
| Permission | whether an Actor may request a Capability in context |
| PolicyRevision | immutable decision rules |
| Approval | human/system approval of exact reviewed content |
| ApprovalCertificate | evidence that approval requirements were satisfied |
| AuthorityWitnessSet | exact authority facts used by authorization |
| AuthorizationSnapshot | immutable evidence of an authorization decision |
| ExecutionGrant | actual narrow permission to execute |
| ExecutionCapsule | exact executable implementation/runtime identity |
| Dispatch | durable handoff of execution intent to a Runner |
| Runner | isolated executor |
| Handler | concrete implementation of a Capability |
| ExecutionReceipt | execution subsystem claim about execution |
| VerificationResult | independent observation of actual post-state |
| Evidence | auditable evidence artifact |
| OperationProof | portable proof of the governed operation chain |
| Module | provider/domain translator and implementation package |
| Candidate | proposed but inactive definition or implementation |
| Activation | explicit acceptance of a concrete definition/implementation |

## Canonical verbs

```text
PROPOSE
NORMALIZE
VALIDATE
REVIEW
APPROVE
AUTHORIZE
ISSUE
DISPATCH
EXECUTE
VERIFY
ATTEST
ADOPT
ACTIVATE
RELEASE
DEPLOY
REVOKE
SUPERSEDE
```

These verbs are not synonyms and must not be collapsed:

```text
APPROVE   != AUTHORIZE
AUTHORIZE != ISSUE
ISSUE     != EXECUTE
EXECUTE   != VERIFY
VERIFY    != RELEASE
RELEASE   != DEPLOY
```

## Canonical relations

```text
REQUESTED_BY
PARENT_OF
CHILD_OF
DEPENDS_ON
DERIVED_FROM
BOUND_TO
AUTHORIZED_BY
ISSUED_FROM
DISPATCHED_TO
EXECUTED_BY
VERIFIED_BY
PRODUCED
PROVES
SUPERSEDES
ACTIVATES
CAUSES
CORRELATES_WITH
```

These relations are shared across Operation, Authority, Execution, Evidence and Module graphs.

## Canonical identity grammar

Every significant governed artifact should converge on the same identity grammar where applicable:

```text
logical_identity
content_identity
instance_id
schema_version
producer
created_at
causation_id
correlation_id
```

Meaning:

- `logical_identity` — what the thing is;
- `content_identity` — exact content/version identity;
- `instance_id` — concrete occurrence.

Example:

```text
logical_identity = github.pull-request.merge/v1
content_identity = sha256:...
instance_id       = grant_...
```

## Canonical state language

Do not create a second parallel status taxonomy.

### RunState

```text
RECEIVED
CLASSIFIED
PLANNED
IN_PROGRESS
WAITING_DEPENDENCY
WAITING_APPROVAL
REVIEW
COMPLETED
CANCELLED
```

### GateStatus

```text
PASS
FAIL
BLOCKED
UNKNOWN
NOT_APPLICABLE
```

### TaskOutcome

```text
COMPLETE
PARTIAL
FAILED
BLOCKED
CANCELLED
```

### Artifact / execution lifecycle

```text
PREPARED
APPLIED
VERIFIED
PUBLISHED
DEPLOYED
```

## Forbidden semantic shortcuts

The following claims are invalid unless their exact downstream state is proven:

- do not say `approved and authorized` when only Approval exists;
- do not say `successful operation` when only `ExecutionReceipt.SUCCESS` exists;
- prefer `execution succeeded; verification pending` until independent verification passes;
- do not use an ambiguous `target` when `RequestedTarget` and authoritative `Target` differ;
- do not say `deployed` when only merge or release evidence exists.

Core invariant:

```text
NO EVIDENCE != PASS
EXECUTION SUCCESS != OPERATION VERIFIED
```

## VOP Schema Registry

The vocabulary is machine-readable in:

`schemas/vop/registry.v1.json`

The registry defines canonical nouns, verbs, relations, identity fields, status vocabularies and schema identifiers. CI must verify the registry contract so this vocabulary cannot drift silently.

Target schema identifiers:

```text
operation-request/v1
reviewed-operation/v1
capability-definition/v1
execution-target/v1
policy-revision/v1
approval-certificate/v1
authority-witness-set/v1
authorization-snapshot/v1
execution-grant/v1
execution-capsule/v1
dispatch-envelope/v1
execution-receipt/v1
verification-result/v1
operation-proof/v1
```

A future full schema implementation should bind each type to:

```text
JSON Schema
+ semantic invariants
+ canonical JSON
+ version
+ conformance tests
```

This slice establishes the registry and conformance gate only. It does not pretend that all full JSON Schemas or package extractions already exist.

## Semantic translation boundary

Provider operations are transport implementations, not V-One capabilities.

Example:

```text
GitHub transport:
PUT /pulls/71/merge

VOP semantics:
Capability = github.pull-request.merge/v1
Target = github://nulleimy/V-One/pull/71
ExpectedPostState.state = merged
ExpectedPostState.merge_commit_sha = expected
```

Transport may later change between REST, GraphQL, GitHub App or another provider mechanism while the semantic Capability remains stable.

Modules translate external semantics into VOP and back out toward execution. Modules do not create authorization truth.

## Semantic equivalence foundation

Two implementations may be considered candidates for the same Capability only after comparing at least:

```text
same semantic input?
same authoritative target?
same side effect?
same permission?
same approval?
same idempotency?
same receipt semantics?
same verification semantics?
same evidence semantics?
```

If all required semantics are equivalent or stronger, the candidate may be classified as semantically equivalent. Otherwise it is a different Capability.

Discovery or semantic equivalence does not imply adoption or activation.

```text
DISCOVERED != ADOPTED != ACTIVATED
```

## One vocabulary across surfaces

Where the same concept is meant, UI, API, database model, audit event, CLI, AI tool, documentation and OperationProof should use the same canonical term.

Do not create parallel synonyms such as `Action`, `Task`, `Job`, `Command`, `Event`, or `Tool call` when the governed concept is actually an `Operation`.

## Package evolution boundary

The target may eventually include a dedicated `vone_contracts` package, but package extraction must follow proven architectural boundaries. Do not perform a broad package rewrite merely to make the vocabulary look complete.

First sequence:

```text
canonical vocabulary
→ machine-readable registry
→ conformance gate
→ adoption evidence
→ incremental schema/contracts
→ package extraction only when justified
```

## Expanded V-One invariant

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

Short form:

> One language. One authority model. One proof model. Many providers.
