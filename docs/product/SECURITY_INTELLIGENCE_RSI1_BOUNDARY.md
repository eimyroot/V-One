# Security Intelligence R-SI1.1 Boundary

| Field | Value |
|---|---|
| Status | IMPLEMENTED descriptive contract / integration not activated |
| Source | `voodoo_product/security_intelligence.py` |
| Tests | `tests/system/test_security_intelligence_rsi1.py` |
| Introduced | PR #126 |
| Runtime authority | NONE |
| Provider-effect authority | NONE |
| OperationProof binding | NOT YET COMPOSED |
| CyberCore integration | BLOCKED pending V-One reconciliation |

## Purpose

R-SI1.1 provides governed descriptive security-intelligence metadata for skills/techniques/risk
classification. It allows V-One to carry security context without creating a parallel authorization
system.

## Authority ceiling

Security Intelligence may:

- describe a skill/capability or security technique;
- attach bounded classification/risk metadata;
- preserve source/provenance-oriented context;
- feed policy/review inputs after explicit semantic mapping;
- provide recommendations or deny-oriented safety metadata.

Security Intelligence may **not**:

- create or approve a ReviewedOperation;
- issue AuthorizationSnapshot;
- issue or consume ExecutionGrant;
- dispatch execution;
- become Runner or Verifier;
- deliver credentials;
- perform provider mutation;
- turn metadata into `VerificationResult`;
- automatically become `OperationProof`/`OperationCell` evidence;
- bypass human/policy/release gates.

Unknown classifications fail closed. Existing CRITICAL/WRITE/EXECUTE safety semantics remain bounded
by the canonical V-One authority path and do not create an alternative capability authority.

## Canonical VOP mapping

```text
Security Intelligence observation/classification
        ↓
explicit semantic mapping / policy-review input
        ↓
ReviewedOperation
        ↓
normal V-One authority lifecycle
        ↓
AuthorizationSnapshot
→ ExecutionGrant/v2
→ control-plane consumption
→ Dispatch
→ Runner
→ ExecutionReceipt/v2
→ independent Verifier
→ VerificationResult/v1
→ OperationProof/v2
→ OperationCell/v1
```

The metadata layer is upstream context. It does not skip any lifecycle stage.

## CyberCore relationship

CyberCore may later produce observations, learning signals and security context that can be normalized
into this intelligence boundary.

```text
CyberCore = intelligence_only
Security Intelligence = descriptive/context layer
neither = Authorization
neither = ExecutionGrant issuer
neither = Runner
neither = Verifier
```

No direct CyberCore runtime integration is activated by this document.

## Evidence / proof relationship

An RSI1 object becomes proof-relevant only if a future separately reviewed contract defines:

1. exact schema/version identity;
2. immutable source/provenance binding;
3. where the intelligence fact enters policy/review/authorization;
4. its exact digest relationship to downstream evidence;
5. fail-closed freshness/staleness behavior;
6. adversarial tests proving it cannot self-authorize or manufacture verification.

Until then:

```text
R-SI1.1 IMPLEMENTED = metadata/test capability
R-SI1.1 PRODUCT_COMPOSED = NO
R-SI1.1 OPERATION_PROOF_BOUND = NO
```

## Integration gate

CyberCore/Security Intelligence runtime binding remains blocked until:

- reconciliation P0/P1 truth gates pass;
- canonical vocabulary/registry are current;
- one canonical ProductComposition lifecycle exists;
- Security Intelligence input/output contracts are explicitly bound to that lifecycle;
- tests prove no parallel authority path;
- any provider effect remains separately authorized.

## Release boundary

This descriptive contract does not authorize merge of unrelated work, deployment, release or
provider mutation. Production effects remain disabled by default.
