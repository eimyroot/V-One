# VOP Canonical Vocabulary

> Jeden význam → jeden termín → jeden kontrakt → jedna autoritativní definice.

To přesně odpovídá principu jedné pravdy v K00: stejné pravidlo nebo význam nemá mít několik paralelních definic.

## 1. Všechny systémy mluví různě. V-One ne.

Externě může přijít:

```text
GitHub       merge pull request
AWS          update service
Kubernetes   patch deployment
Jira         transition issue
Docker       build image
MCP          call tool
A2A          create task
AI           use tool
REST         POST
GraphQL      mutation
gRPC         RPC
```

V-One je všechny přeloží do stejného modelu:

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

Provider-specific jazyk zůstane **za Module boundary**.

```text
AWS terminology
GitHub terminology
MCP terminology
        ↓
      MODULE
        ↓
CANONICAL VOP LANGUAGE
```

A opačně při execution.

---

# 2. Canonical nouns

Navrhuji definitivně rezervovat následující slova:

| Term | Jediný význam |
|---|---|
| **Actor** | kdo iniciuje/provádí roli v procesu |
| **Intent** | požadovaný outcome před přesnou operacionalizací |
| **Operation** | governovaná jednotka práce |
| **ReviewedOperation** | přesný obsah, který byl předložen governance |
| **Capability** | co systém umí významově udělat |
| **Input** | data operace |
| **Target** | autoritativně identifikovaný objekt efektu |
| **ExpectedPostState** | stav, který má po úspěchu existovat |
| **Permission** | zda actor smí požadovat danou capability/context |
| **PolicyRevision** | immutable pravidla rozhodnutí |
| **Approval** | lidské/systémové schválení konkrétního reviewed obsahu |
| **ApprovalCertificate** | důkaz, že approval requirements byly splněny |
| **AuthorityWitnessSet** | přesné authority facts použité při authorization |
| **AuthorizationSnapshot** | immutable evidence authorization decision |
| **ExecutionGrant** | skutečné úzké permission k execution |
| **ExecutionCapsule** | přesná identita executable implementation/runtime |
| **Dispatch** | durable předání execution intentu Runneru |
| **Runner** | izolovaný vykonavatel |
| **Handler** | konkrétní implementace capability |
| **ExecutionReceipt** | tvrzení execution systému o provedení |
| **VerificationResult** | nezávislé zjištění skutečného post-state |
| **Evidence** | auditovatelný důkazní artefakt |
| **OperationProof** | portable proof celého řetězce |
| **Module** | provider/domain překladač a implementation package |
| **Candidate** | něco navrženého, ale neaktivního |
| **Activation** | explicitní přijetí konkrétní definice/implementace |

---

# 3. Canonical verbs

Tady je ještě důležitější zabránit synonymům.

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

A **nikdy je neslévat**.

Například:

```text
APPROVE
!= AUTHORIZE

AUTHORIZE
!= ISSUE

ISSUE
!= EXECUTE

EXECUTE
!= VERIFY

VERIFY
!= RELEASE

RELEASE
!= DEPLOY
```

To zapadá i do existujícího ownership modelu, kde různé části systému mají rozdílnou autoritu a výsledek jednoho specialisty/komponenty nesmí automaticky získat autoritu jiné vrstvy.

---

# 4. Canonical relation language

Každý graph — Operation, Authority, Execution, Evidence i Module — bych postavil nad omezeným množstvím stejných vztahů:

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

Díky tomu lze celý systém dotazovat jednotně.

Například:

```text
op_123
AUTHORIZED_BY snapshot_55

grant_77
ISSUED_FROM snapshot_55

exec_88
EXECUTED_BY runner_2

verification_91
VERIFIED_BY verifier_4

proof_100
PROVES op_123
```

---

# 5. Jednotný identity model

Každá významná věc by měla používat stejnou identity gramatiku:

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

Rozdíl:

```text
logical_identity
= "co to je"

content_identity
= "přesně jaká verze obsahu to je"

instance_id
= "konkrétní occurrence"
```

Příklad:

```text
logical:
github.pull-request.merge/v1

content:
sha256:91ab...

instance:
grant_0192...
```

To je nesmírně důležité pro CyberCore, semantic equivalence i portable proof.

---

# 6. Jednotný jazyk stavu — bez další paralelní taxonomie

Tady bych **nevymýšlel další systém statusů**.

Použít existující canonical CORE.

### Workflow

```text
RunState:
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

### Gates

```text
GateStatus:
PASS
FAIL
BLOCKED
UNKNOWN
NOT_APPLICABLE
```

### Outcome

```text
TaskOutcome:
COMPLETE
PARTIAL
FAILED
BLOCKED
CANCELLED
```

A artifact/execution stav:

```text
PREPARED
APPLIED
VERIFIED
PUBLISHED
DEPLOYED
```

K90 už explicitně říká, že sdílený stav se nemá znovu redefinovat jinou taxonomií.

---

# 7. Několik zakázaných jazykových zkratek

Tyhle věci bych dal do lint/conformance pravidel.

### Zakázat

```text
"approved and authorized"
```

pokud vznikla pouze Approval.

---

```text
"successful operation"
```

pokud existuje jen `ExecutionReceipt.SUCCESS`.

Správně:

```text
execution succeeded
verification pending
```

QA reference už pracuje se stejným principem: **NO EVIDENCE ≠ PASS** a průchod testů neznamená automaticky kompletní produktový outcome.

---

```text
"target"
```

bez rozlišení:

```text
RequestedTarget
AuthoritativeTarget
```

---

```text
"deployed"
```

pokud máme jen merged/released artefakt.

DevOps reference explicitně odděluje release, deploy, health a business correctness.

---

# 8. VOP Schema Registry

Slovník nesmí být pouze dokumentace.

Má být **machine-enforced**.

Navrhuji:

```text
VOP Schema Registry
```

například:

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

Každý typ:

```text
JSON Schema
+
semantic invariants
+
canonical JSON
+
version
+
conformance tests
```

---

# 9. Semantic Translation Layer

Tohle může být jedna z unikátních funkcí V-One.

Provider modul nebude jen „API adapter“.

Bude provádět:

```text
EXTERNAL SEMANTICS
        ↓
SEMANTIC MAPPING
        ↓
VOP CANONICAL SEMANTICS
```

Například GitHub:

```text
PUT /pulls/71/merge
```

není V-One capability.

Je to transport implementation.

V-One vidí:

```text
Capability:
github.pull-request.merge/v1

Target:
github://nulleimy/V-One/pull/71

ExpectedPostState:
state = merged
merge_commit_sha = expected
```

Transport může být:

```text
REST
GraphQL
GitHub App
future API
```

ale semantic operation zůstává stejná.

A to je přesně základ **Semantic Equivalence Engine**.

---

# 10. CyberCore díky tomu dostane skutečný „jazyk myšlení“

Pak CyberCore neporovnává:

```text
REST call A
vs
GraphQL call B
```

ale:

```text
Implementation A
        │
implements
        ▼
Capability X

Implementation B
        │
implements
        ▼
Capability X
```

a kontroluje:

```text
same semantic input?
same authoritative target?
same side effect?
same permission?
same approval?
same idempotency?
same receipt?
same verification?
same evidence?
```

Pokud ano:

```text
SEMANTICALLY_EQUIVALENT
```

Pokud ne:

```text
NEW CAPABILITY
```

To je zásadní.

---

# 11. Jeden slovník pro člověka, API, UI, audit i AI

Cíl by měl být:

```text
UI label
API contract
database concept
audit event
CLI
AI tool
documentation
OperationProof
```

všude používá **stejný termín**.

Ne:

```text
UI: Action
API: Task
DB: Job
Runner: Command
Audit: Event
AI: Tool call
```

pokud všechny znamenají stejnou věc.

Správně:

```text
Operation
```

a ostatní jsou specifické podtypy nebo technické mechanismy.

---

# 12. Doporučená struktura canonical dictionary

V repu bych časem vytvořil něco typu:

```text
docs/architecture/
└── VOP_CANONICAL_VOCABULARY.md

schemas/vop/
├── operation-request.v1.json
├── reviewed-operation.v1.json
├── capability-definition.v1.json
├── execution-target.v1.json
├── authority-witness-set.v1.json
├── authorization-snapshot.v1.json
├── execution-grant.v1.json
├── execution-capsule.v1.json
├── execution-receipt.v1.json
├── verification-result.v1.json
└── operation-proof.v1.json
```

Později:

```text
vone_contracts/
├── vocabulary.py
├── identities.py
├── operation.py
├── authority.py
├── execution.py
├── verification.py
└── proof.py
```

Ale podle Software Engineering pravidel bych tyto package extractiony dělal až tehdy, kdy boundaries reálně dozrají; nejdřív nejmenší koherentní změny v současném codebase.

---

# Nový architektonický invariant

Přidal bych tedy:

```text
ONE SYSTEM
=
ONE SEMANTIC LANGUAGE
```

A celý V-One invariant bych rozšířil na:

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

Ještě kratší:

> **One language. One authority model. One proof model. Many providers.**

Tohle bych skutečně považoval za **součást moat V-One**, ne pouze dokumentační kosmetiku. External APIs, agent frameworks a technologie se mohou měnit, ale pokud je lze překládat do jednoho stabilního semantic vocabulary, V-One může zůstat nad nimi.
