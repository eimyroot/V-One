# VOODOO — CURRENT PRODUCT STATE

> Toto je proměnlivý důkazní snapshot. Není náhradou živého Git stavu, provedených testů ani
> commit-bound runtime evidence. Historické baseline a immutable ADR labels se zachovávají jako
> provenance; efektivní současný stav se určuje z live Git/CI a authority/adoption registru.

## Identita a hranice tvrzení

```text
AS_OF: 2026-08-16
EXACT_LIVE_GIT_IDENTITY: QUERY_LIVE_GIT_DIRECTLY
RECONCILIATION_INPUT_BRANCH: main
RECONCILIATION_INPUT_HEAD: f1b5b8a5c0a31f75c10f1acc5153874b84248e1b
RECONCILIATION_INPUT_TREE: 61f03f49577bab1ac03cdd40be74a077649bf38b
PR71_MERGE_COMMIT: d8d375c61264ddad39eb53240dce9ff0c8e59818
PR71_PR_HEAD_CI: run #282 SUCCESS at 93605972bfb3f35f324183a00c7ad2f88c5f9ab2
PR71_POST_MERGE_CI: run #283 SUCCESS at d8d375c61264ddad39eb53240dce9ff0c8e59818
PR72_SOT_RECONCILIATION_MERGE: 2ce33ca7dfe4169affb59c001ed63fc7145c9743
PR72_PR_HEAD_CI: run #286 SUCCESS at f9f0f7cb2fa769e46510bcd7387d7e4158d1eb64
PR72_POST_MERGE_CI: run #287 SUCCESS at 2ce33ca7dfe4169affb59c001ed63fc7145c9743
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@d57d37111b8bc9471a136b6c618aad8e920f1aff
RUNTIME_EVIDENCE_CLASS: IMPLEMENTED_VERIFIED_LOCAL_POST_MERGE_CHECKPOINT
ADR_0007_CONTRACT_LAYER: VERIFIED source/test scope; pure deterministic value contracts only
ADR_0008_EFFECTIVE_STATUS: ADOPTED via docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md
ADR_0009_EFFECTIVE_STATUS: ADOPTED via docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md
ADR_0010_EFFECTIVE_STATUS: ADOPTED via docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md
AUTHORIZATION_SNAPSHOT_CONTRACT: IMPLEMENTED
AUTHORIZATION_SNAPSHOT_PERSISTENCE: VERIFIED by PR #71 CI and post-merge CI
AUTHORIZATION_SNAPSHOT_SCHEMA: sqlite schema version 9
AUTHORITATIVE_SNAPSHOT_CREATOR: NOT IMPLEMENTED
AUTHORITATIVE_GRANT_ISSUER: NOT IMPLEMENTED
ISOLATED_RUNNER_RUNTIME: NOT IMPLEMENTED
BRANCH_PROTECTION_MAIN: DISABLED at reconciliation preflight
RELEASE_STATE: BLOCKED
PRODUCTION_EFFECTS: DISABLED / NO PRODUCTION EFFECT EVIDENCE
```

Exact live Git commit is deliberately **not embedded as a static current-value field**. A commit that
contains such a value would immediately supersede it. `RECONCILIATION_INPUT_*` records the evidence
baseline used to prepare this snapshot; current identity must always be queried from live Git/GitHub.

## Live Git reconciliation incident

Během tohoto CASER-SOURCER reconciliation vznikl na nechráněném `main` omylem jeden marker commit
`a4a46cc2b5ddf50f519148af60e4cb720e714d5e` a okamžitý revert
`f1b5b8a5c0a31f75c10f1acc5153874b84248e1b`. Revert obnovil přesně strom
`61f03f49577bab1ac03cdd40be74a077649bf38b`, tedy stejný tree jako PR #71 merge commit
`d8d375c61264ddad39eb53240dce9ff0c8e59818`. Nezůstala žádná netto změna source tree; Git historie
incident zachovává. Main CI #285 pro revert skončil `SUCCESS`. Tato událost je důkazem, že `main`
bez branch protection / required checks je materiální governance gap.

## Co je aktuálně VERIFIED

- PR #71 přidal append-only SQLite persistence pro existující immutable `AuthorizationSnapshot`
  contract, migration `0009_authorization_snapshots.sql`, statement catalog/schema validation,
  idempotency binding, immutable update/delete triggers a persistence/contract regression testy;
- PR-head CI #282 skončil `SUCCESS` pro exact head
  `93605972bfb3f35f324183a00c7ad2f88c5f9ab2`;
- post-merge CI #283 skončil `SUCCESS` pro exact PR #71 merge commit
  `d8d375c61264ddad39eb53240dce9ff0c8e59818`;
- SOT reconciliation PR #72 měl CI #286 `SUCCESS` pro exact head
  `f9f0f7cb2fa769e46510bcd7387d7e4158d1eb64`, byl squash-merged jako
  `2ce33ca7dfe4169affb59c001ed63fc7145c9743` a post-merge CI #287 skončil `SUCCESS`;
- authoritative adoption register eviduje ADR-0008, ADR-0009 a ADR-0010 jako efektivně `ADOPTED` v
  jejich přesném hash-bound scope; jejich embedded `PROPOSED` / `PROPOSED / PREPARED` labels jsou
  historické deklarované statusy immutable reviewed bytes, ne současný efektivní adoption status;
- production effects, release a deployment tím nejsou autorizovány ani prokázány.

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

Toto je preliminary audit classification, nikoli implementační claim.

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
- ADR-0010: effective `ADOPTED`; immutable authorization-snapshot facts boundary only; adoption alone
  did not authorize implementation. The separately user-authorized PR #71 persistence slice is merged
  and verified, while authoritative Snapshot Creator remains unimplemented.

## Co zůstává NOT IMPLEMENTED / BLOCKED

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
STEP 0  Source-of-Truth reconciliation and CI
STEP 1  Authority Reality Audit
STEP 2  Implement only missing authority prerequisites
STEP 3  AuthoritativeSnapshotCreator in one atomic authorization transaction
STEP 4  ExecutionGrant contract/issuer + exact handler/runner authority
STEP 5  Transactional outbox/dispatch
STEP 5.5 Credential broker boundary
STEP 6  READ-ONLY isolated Runner
STEP 7  ExecutionReceipt
STEP 8  Independent Verification
STEP 9  OperationProof
```

Do not jump to Runner implementation before the authority foundation and Snapshot Creator are proven.

## Historical evidence boundary

Historical Git identities such as PR #54 merge commit
`57c7bf2277616c4445039865ac7cf81c5fada858` remain valid provenance in the immutable ADR evidence
index. They are **not current Git identity fields**. Effective ADR adoption is read from
`AUTHORITY_AND_ADOPTION_REGISTER.md`, not from historical embedded status labels.

Capability detail: [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)

Delivery order: [`ROADMAP.md`](ROADMAP.md)
