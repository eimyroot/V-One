# VOODOO — CURRENT PRODUCT STATE

> Toto je proměnlivý důkazní snapshot. Není náhradou živého Git stavu, provedených testů ani
> commit-bound runtime evidence. Historické baseline a immutable ADR labels se zachovávají jako
> provenance; efektivní současný stav se určuje z live Git/CI a authority/adoption registru.

## Identita a hranice tvrzení

```text
AS_OF: 2026-08-16
EXACT_LIVE_GIT_IDENTITY: QUERY_LIVE_GIT_DIRECTLY
RECONCILIATION_INPUT_BRANCH: main
RECONCILIATION_INPUT_HEAD: b4d4aab7393251ffc113a3f5bf654523bdb27865
RECONCILIATION_INPUT_TREE: 61021278068a7d64b66325190c94dde6f4593b16
HISTORICAL_REVIEW_MERGE_PR54: 57c7bf2277616c4445039865ac7cf81c5fada858
PR71_MERGE_COMMIT: d8d375c61264ddad39eb53240dce9ff0c8e59818
PR71_PR_HEAD_CI: run #282 SUCCESS at 93605972bfb3f35f324183a00c7ad2f88c5f9ab2
PR71_POST_MERGE_CI: run #283 SUCCESS at d8d375c61264ddad39eb53240dce9ff0c8e59818
PR73_SOT_FIX_MERGE: b8e3b0f8d6f0ffb401138e44abe5a7d80e35a69a
PR73_PR_HEAD_CI: run #288 SUCCESS at 64da1a91d77cbd93b54580b607cbcbbe18b6ad24
PR73_POST_MERGE_CI: run #289 SUCCESS at b8e3b0f8d6f0ffb401138e44abe5a7d80e35a69a
PR74_VOP_MERGE: a9a57df270b85907ee5012895c1523ade461f06f
PR74_PR_HEAD_CI: run #292 SUCCESS at 1be3721db70433a4dc4a45c353a5d748dd4bf113
PR74_IMMEDIATE_POST_MERGE_CI: run #297 CANCELLED by subsequent main activity; not failure evidence
PR75_P0_REPO_CONTRACT_MERGE: b4d4aab7393251ffc113a3f5bf654523bdb27865
PR75_PR_HEAD_CI: run #291 SUCCESS at 329cde854a34a713ccd10ad272fbd9554d88a602
CURRENT_MAIN_CI: run #298 SUCCESS at b4d4aab7393251ffc113a3f5bf654523bdb27865
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@d57d37111b8bc9471a136b6c618aad8e920f1aff
RUNTIME_EVIDENCE_CLASS: IMPLEMENTED_VERIFIED_LOCAL_POST_MERGE_CHECKPOINT
ADR_0008_EFFECTIVE_STATUS: ADOPTED via docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md
ADR_0009_EFFECTIVE_STATUS: ADOPTED via docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md
ADR_0010_EFFECTIVE_STATUS: ADOPTED via docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md
VOP_CANONICAL_VOCABULARY: VERIFIED source/test scope on current main
VOP_SEMANTIC_TRANSLATION: VERIFIED source/test scope on current main
VOP_SEMANTIC_EQUIVALENCE: VERIFIED source/test scope on current main
VOP_ARCHITECTURE_OWNER_ADOPTION: UNKNOWN; no explicit VOP adoption record in authority/adoption register
AUTHORIZATION_SNAPSHOT_CONTRACT: IMPLEMENTED
AUTHORIZATION_SNAPSHOT_PERSISTENCE: VERIFIED by PR #71 CI and post-merge CI
AUTHORIZATION_SNAPSHOT_SCHEMA: sqlite schema version 9
AUTHORITATIVE_SNAPSHOT_CREATOR: NOT IMPLEMENTED
AUTHORITATIVE_GRANT_ISSUER: NOT IMPLEMENTED
ISOLATED_RUNNER_RUNTIME: NOT IMPLEMENTED
P0_REPO_ENFORCEMENT_CONTRACT: MERGED
BRANCH_PROTECTION_MAIN_LIVE: DISABLED
REQUIRED_STATUS_CHECKS_MAIN_LIVE: OFF
P0_GITHUB_GOVERNANCE: BLOCKED
RELEASE_STATE: BLOCKED
PRODUCTION_EFFECTS: DISABLED / NO PRODUCTION EFFECT EVIDENCE
```

Exact live Git commit je záměrně **neuložený jako statická current-value autorita**. `RECONCILIATION_INPUT_*`
zachycuje přesnou baseline použitou pro tento snapshot; skutečná současná identita se vždy dotazuje z
live Git/GitHub.

## Post-VOP / P0 reconciliation

PR #74 zavedl do současného source tree kanonický VOP slovník a jeho machine-readable/runtime
kontrakty. Současný `main` obsahuje zejména:

- `docs/architecture/VOP_CANONICAL_VOCABULARY.md`;
- `schemas/vop/registry.v1.json` se stavem `RESERVED_IDS` pro dosud neimplementovaná konkrétní schémata;
- `voodoo_product/vop_vocabulary.py` s kanonickými nouns/verbs/relations/statusy, deterministic digestem
  a fail-closed validací termínů;
- `voodoo_product/vop_translation.py` s immutable provider semantic mapping a deterministic
  semantic-equivalence assessment;
- conformance testy pro vocabulary, translation a compatibility s operation semantics.

PR-head CI #292 skončil `SUCCESS`. Bezprostřední push CI #297 na merge commit #74 byl `CANCELLED`
protože následoval další push na `main`; současný `main` po PR #75 prošel kompletním CI #298, takže
aktuální strom včetně PR #74 změn má fresh commit-bound `SUCCESS` evidence.

Toto je source/test implementační a verification evidence. **Není to samo o sobě owner adoption.**
`AUTHORITY_AND_ADOPTION_REGISTER.md` nemá explicitní VOP owner-adoption record, proto efektivní
architektonická adoption autorita zůstává `UNKNOWN` do samostatného, exact-content-bound rozhodnutí.

## GitHub governance reality

PR #75 mergnul repository-side kontrakt
`docs/governance/GITHUB_MAIN_GOVERNANCE_BASELINE_V1.md` a odpovídající machine-readable baseline.
Kontrakt požaduje PR-only `main`, required `ci / verify`, latest-head checks, zákaz force-push/delete a
conversation resolution.

Live GitHub branch metadata po merge PR #75 ale stále hlásí:

```text
main.protected = false
protection.enabled = false
required_status_checks.enforcement_level = off
required_status_checks.contexts = []
```

Proto:

```text
REPO_ENFORCEMENT_CONTRACT = MERGED
GITHUB_SETTINGS_ENFORCED = FAIL / NOT CONFIGURED
P0_GITHUB_GOVERNANCE = BLOCKED
```

Dokument, merge ani úspěšné CI nesmí být zaměněny za GitHub-side enforcement.

## Authorization Snapshot boundary

Aktuální source tree obsahuje immutable `AuthorizationSnapshot` contract a persistence-only
`AuthorizationSnapshotStore`.

Store je záměrně pouze persistence boundary pro prevalidated snapshoty. Nevyhodnocuje:

- approval policy authority;
- capability eligibility/activation;
- deterministic target binding;
- `execution.run` permission;
- authoritative Snapshot Creator transaction.

Současný `persist_prevalidated(...)` si otevírá vlastní database transaction. Pro budoucí
`AuthoritativeSnapshotCreator` je proto stále potřeba transaction-aware persistence/read API, aby
všechny authority reads, snapshot construction, persistence a audit proběhly v jedné coherent outer
authorization transaction.

## Authority reality — preliminary

```text
P1 immutable/versioned policy authority: PARTIAL
P2 authoritative server-side execution.run permission authority: UNKNOWN / audit required
P3 capability definition + activation authority: UNKNOWN / audit required
P3 deterministic target binder authority: UNKNOWN / audit required
approval evidence authority: PARTIAL / audit required
trusted clock identity: contract exists; authoritative runtime composition audit required
transaction-aware AuthorizationSnapshotStore API: MISSING
```

Toto je preliminary audit classification, nikoli implementační claim. Dedicated Authority Reality
Audit smí začít až jako samostatný bounded audit slice; vyšší-impact implementation nesmí spoléhat na
GitHub governance, dokud P0 live enforcement neprojde.

## Latest runtime-attested checkpoint

Latest runtime-attested committed baseline zůstává historický development checkpoint
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff`:

```text
EVIDENCE_ARCHIVE: POST_MERGE_CHECKPOINT_20260802T152505Z_d57d37111b8b.zip
EVIDENCE_ARCHIVE_SHA256: 80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2
EVIDENCE_MANIFEST_SHA256: f2851d70523122134bef007bd589872b810326a924f9fc187e2bec1da0aed0a2
FULL_TEST_SUITE: 433 passed
PRODUCT_READINESS: PASSED
DEPENDENCY_AUDIT: no known vulnerabilities reported
PRODUCT_IMAGE_BUILD: PASSED
PRODUCT_IMAGE_SMOKE: PASSED according to checkpoint result
PRODUCT_IMAGE_ID: sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

Tento checkpoint neattestuje pozdější source změny ani GitHub CI. Pro pozdější commity je
verification evidence GitHub Actions, nikoli tento starší runtime archive. Ani successful CI není
release, deployment nebo production verification.

## Efektivní ADR stav

Autoritativní adoption evidence je
[`docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`](docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md).

- ADR-0008: effective `ADOPTED`; isolated Runner design/safety scope only; implementation authorization
  is not implied.
- ADR-0009: effective `ADOPTED`; grant issuance/authenticity design scope only; Runner/release/deploy
  remain unauthorized by adoption alone.
- ADR-0010: effective `ADOPTED`; immutable authorization-snapshot facts boundary only; separately
  authorized PR #71 persistence slice is merged and verified; authoritative Snapshot Creator remains
  unimplemented.
- VOP canonical vocabulary / semantic translation: source/test implementation is present and verified,
  but no explicit owner-adoption record is currently present in this register; architectural adoption
  therefore remains `UNKNOWN`, not inferred from merge.

## Co zůstává NOT IMPLEMENTED / BLOCKED

- live GitHub `main` protection and required-check enforcement;
- authoritative `AuthorizationSnapshotCreator`;
- immutable/versioned runtime policy authority sufficient for snapshot creation;
- fully audited server-side `execution.run` authority;
- capability definition/activation authority and deterministic target binder required by snapshot
  creation;
- authoritative `ExecutionGrantIssuer` and authenticity envelope implementation;
- transactional outbox/dispatch;
- credential broker;
- isolated READ-ONLY Runner runtime;
- Runner-side durable one-time grant consumption;
- independent provider post-state verification;
- composed portable `OperationProof` runtime flow;
- unrestricted production release and production effects;
- public commercial distribution before licensing/EULA/privacy/support decisions.

## Next safe development sequence

```text
P0      Enforce and independently verify GitHub main protection
STEP 0R Post-VOP/P0 Source-of-Truth reconciliation
STEP 1  Authority Reality Audit
STEP 2  Implement only proven missing authority prerequisites
STEP 3  AuthoritativeSnapshotCreator in one atomic authorization transaction
STEP 4  ExecutionGrant contract/issuer + exact handler/runner authority
STEP 5  Transactional outbox/dispatch
STEP 5.5 Credential broker boundary
STEP 6  READ-ONLY isolated Runner
STEP 7  ExecutionReceipt
STEP 8  Independent Verification
STEP 9  OperationProof
```

Do not jump to Runner implementation before GitHub governance, authority foundation and Snapshot
Creator are proven.

## Historical evidence boundary

Historical review merge `57c7bf2277616c4445039865ac7cf81c5fada858` remains valid provenance in
the immutable ADR evidence index. Historical Git identities remain valid provenance; they are **not
current Git identity fields**. Effective owner adoption is read from
`AUTHORITY_AND_ADOPTION_REGISTER.md`, not inferred from repository presence, merge, CI or historical
embedded status labels.

Capability detail: [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)

Delivery order: [`ROADMAP.md`](ROADMAP.md)
