# VOODOO — CURRENT PRODUCT STATE

| Pole | Hodnota |
|---|---|
| Třída dokumentu | Datovaný důkazní snapshot |
| Autorita | Dokumentovaný stav pouze k uvedenému `AS_OF` a baseline |
| Live-state autorita | Živý Git, nově spuštěné testy, CI, artefakty a runtime pozorování |
| Governance | `docs/governance/DOCUMENTATION_POLICY.md` |
| Adopce / autorita dokumentů | `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md` |

> Toto je proměnlivý důkazní snapshot. Není náhradou živého Git stavu, nově provedených testů ani
> commit-bound runtime evidence. Po jakékoli změně HEAD, worktree, CI, runtime nebo release je nutné
> snapshot obnovit nebo explicitně označit jako zastaralý.

## Identita a hranice tvrzení

```text
AS_OF: 2026-08-03
LIVE_BRANCH_AT_RECONCILIATION_PREFLIGHT: main
LIVE_HEAD_AT_RECONCILIATION_PREFLIGHT: 57c7bf2277616c4445039865ac7cf81c5fada858
LATEST_VERIFIED_GIT_BASELINE: main@57c7bf2277616c4445039865ac7cf81c5fada858
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@d57d37111b8bc9471a136b6c618aad8e920f1aff
RUNTIME_EVIDENCE_CLASS: IMPLEMENTED_VERIFIED_LOCAL_POST_MERGE_CHECKPOINT
ADR_0007_CONTRACT_LAYER: VERIFIED source/test scope; pure deterministic value contracts only
ADR_0008_DESIGN: PROPOSED
ADR_0008_OWNER_DECISION: REQUIRED
ADR_0008_REVIEW_COMMIT: 0fa69411b246c4bd80b8a2eaa989e60fd8bca663
ADR_0008_REVIEW_PUBLICATION: VERIFIED_REMOTE_BRANCH
ADR_0008_REVIEW_PR: 54 MERGED
ADR_0008_MERGE_COMMIT: 57c7bf2277616c4445039865ac7cf81c5fada858
DOCS_MVP_PATCH: VERIFIED_EVIDENCE; NOT_COMMITTED_AT_RECONCILIATION_PREFLIGHT
PORTABLE_BUNDLE: VERIFIED evidence, not runtime evidence
RELEASE_STATE: BLOCKED
PRODUCTION_EFFECTS: DISABLED in the verified local-development runtime checkpoint
```

Tyto identity nesmějí být slučovány:

1. **Živá Git identita** je autoritativně zjištěna příkazy nad aktuálním repozitářem a pro tuto
   synchronizaci je `main@57c7bf2277616c4445039865ac7cf81c5fada858`.
2. **Latest runtime-attested baseline** je post-merge checkpoint
   `d57d37111b8bc9471a136b6c618aad8e920f1aff`. Starší `8a5f36b...` capture/finalize evidence
   zůstává historickým důkazem konkrétního checkpoint workflow, nikoliv nejnovější runtime baseline.
3. **ADR-0007 contract layer** je pure deterministic representation only; authoritative issuance,
   authenticity envelopes, and isolated Runner runtime remain separate and not implemented.
4. **ADR-0008 review commit** `0fa69411b246c4bd80b8a2eaa989e60fd8bca663` byl publikován na
   exact review branch a mergnut přes PR #54 jako `57c7bf2277616c4445039865ac7cf81c5fada858`.
   Tím se ADR automaticky nestává ACCEPTED a nevzniká runtime implementace.
5. **Documentation/MVP patch** je samostatný, evidence-verified docs/test-only change. V okamžiku
   reconciliation preflight ještě nebyl commitnut ani publikován.
6. **Release stav** zůstává `BLOCKED`; lokální evidence, review merge ani dokumentační synchronizace
   samy o sobě nepředstavují release ani deployment.

## Co bylo VERIFIED při reconciliation na `main@57c7bf2277616c4445039865ac7cf81c5fada858`

- canonical checkout byl fast-forwardnut na `main@57c7bf2277616c4445039865ac7cf81c5fada858`
  a uživatelský terminálový výstup po operaci hlásil čisté `## main`;
- remote `main` ukazuje na `57c7bf2277616c4445039865ac7cf81c5fada858`;
- review commit `0fa69411b246c4bd80b8a2eaa989e60fd8bca663` byl publikován exact publisherem
  a mergnut přes PR #54;
- ADR-0007 pure deterministic execution-contract value objects jsou source/test VERIFIED;
- read-only Policy Decision Graph v1 zůstává owner-accepted a source/test VERIFIED pro svůj
  read-only slice;
- portable bundle, V2/V2.1 documentation evidence a publication evidence jsou evidence,
  nikoliv runtime evidence;
- latest runtime-attested baseline zůstává `main@d57d37111b8bc9471a136b6c618aad8e920f1aff`.

## Dokumentovaná source capability k reconciliation baseline

VOODOO One je v tomto snapshotu klasifikováno jako **development / controlled-pilot authorization and evidence control plane**.
Aktuální source tree obsahuje:

- FastAPI `/api/v1` control plane a statickou command-center konzoli;
- lokální bootstrap, login, context-bound sessions, logout a administrativní revokaci sessions;
- RBAC, workspaces, change requests, nezávislé approvals a execution lifecycle;
- emergency stop, execution idempotency, leases, fencing a explicitní indeterminate recovery;
- checksum-verified SQLite migrace a reviewovaný SQL statement catalog;
- audit a receipt ledgers s nezávislou kontrolou integrity;
- bounded local adapters a governed sandbox filesystem effects;
- lokální checkpoint verifier, deterministic ProofGraph v1 JSON a repository-owned checkpoint
  finalizer;
- read-only deterministic Policy Decision Graph v1 jako čistou deterministickou projekci;
- ADR-0007 pure execution-contract value objects jako source/test VERIFIED layer bez runtime
  authority.

Policy Decision Graph v1 vrací `ALLOW` nebo `DENY`, `execution_eligible`, reason codes,
limitations, deterministically řazené nodes/edges a digest. Nemá autorizační pravomoc, není runtime
gate, nic nevykonává ani nepersistuje a není napojen do API, service, execution lifecycle,
databáze nebo CyberCore. Zachovává současné `ApprovalPolicyDecision.reason_codes` a nové projekční
kódy používají namespace `PDG_*`.

ADR-0007 accepted pure deterministic contracts:

- `execution-target/v1`;
- `approval-evidence-set/v1`;
- `execution-grant/v1`;
- `execution-receipt/v1`.

Tyto kontrakty jsou hodnotová reprezentace, nikoliv signed envelope, issuer, runtime Runner nebo
production effect.

## Nejnovější runtime checkpoint

Pro committed baseline
`main@d57d37111b8bc9471a136b6c618aad8e920f1aff` existuje ověřená post-merge evidence:

```text
EVIDENCE_ARCHIVE:
POST_MERGE_CHECKPOINT_20260802T152505Z_d57d37111b8b.zip
EVIDENCE_ARCHIVE_SHA256:
80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2
EVIDENCE_MANIFEST_SHA256:
f2851d70523122134bef007bd589872b810326a924f9fc187e2bec1da0aed0a2
STATUS: IMPLEMENTED_VERIFIED_LOCAL_POST_MERGE_CHECKPOINT
FULL_TEST_SUITE: 433 passed
PRODUCT_READINESS: PASSED
DEPENDENCY_AUDIT: no known vulnerabilities reported
PRODUCT_IMAGE_BUILD: PASSED
PRODUCT_IMAGE_SMOKE: PASSED according to checkpoint result
PRODUCT_IMAGE_ID:
sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc
WORKTREE: CLEAN
STAGING: EMPTY
PRODUCTION_EFFECTS: DISABLED
RELEASE: NOT_PERFORMED
DEPLOYMENT: NOT_PERFORMED
```

Evidence je omezena na lokální development checkpoint. Neprokazuje registry push, vzdálené
podepisování, release, deployment ani produkční efekt. Neattestuje pozdější review commit
`0fa69411b246c4bd80b8a2eaa989e60fd8bca663`, merge commit `57c7bf2277616c4445039865ac7cf81c5fada858`
ani tento documentation/MVP patch.

Starší `main@8a5f36b218c3aa6dce2e4cf771512875f136d839` capture→finalize evidence zůstává
historicky relevantní pro checkpoint workflow, ale není nejnovější runtime-attested baseline.

## Co je v tomto snapshotu PROPOSED nebo BLOCKED a není runtime implementováno

- autoritativní runtime Policy Decision Graph a capability-policy engine;
- isolated runner capsules a signed short-lived execution grants;
- released OIDC a PostgreSQL backend;
- signed checkpoints/receipts and external evidence anchoring;
- remote byte attestation, širší SBOM/provenance a multi-arch release evidence;
- mutační CyberCore integration;
- unrestricted production release a production effects;
- public commercial distribution před vyřešením licence, EULA, privacy a support modelu.

## Důkazní stav

```text
VERIFIED:
- reconciliation preflight observed main@57c7bf2277616c4445039865ac7cf81c5fada858
- review commit 0fa69411b246c4bd80b8a2eaa989e60fd8bca663 was published and merged through PR #54
- publication evidence archive and final independent verification match their recorded SHA-256 values
- post-merge runtime checkpoint archive and internal manifest match their recorded SHA-256 values
- checkpoint result records Ruff, compile, focused gates, 433 full tests, readiness, dependency audit,
  product-image build, and recorded smoke gate as passed
- runtime evidence class is IMPLEMENTED_VERIFIED_LOCAL_POST_MERGE_CHECKPOINT
- production effects were disabled; release and deployment were not performed
- ADR-0007 pure deterministic execution-contract value objects are source/test VERIFIED
- read-only PDG v1 is locally source/test VERIFIED for its projection-only scope

IMPLEMENTED:
- read-only Policy Decision Graph v1 exists as a pure library with no runtime integration
- ADR-0006 records owner acceptance without adding runtime authority
- ADR-0008 lifecycle-semantics documentation correction is present on main but the ADR remains PROPOSED
- documentation separates live Git, commit-bound runtime evidence, subsequent source changes, and
  documentation-evidence state

NOT VERIFIED:
- runtime attestation for `0fa69411...`, merge commit `57c7bf22...`, or this documentation/MVP patch
- release, deployment, registry publication, remote signing, or production operation

BLOCKED:
- unrestricted production release
- production effects
- public commercial distribution
```

Dokumentace capability detail: [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)

Dokumentace delivery order: [`ROADMAP.md`](ROADMAP.md)

Accepted decision: [`docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md`](docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md)


## Obnovení snapshotu

Před aktualizací tohoto souboru musí být zachyceno minimálně:

```bash
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short --branch
git log -5 --oneline --decorate
```

Dále musí být uvedeny přesné příkazy a výsledky relevantních testů, CI nebo runtime evidence.
Aktualizace musí změnit `AS_OF`, svázat tvrzení s přesným commitem, uvést dirty/clean worktree a
oddělit:

- `DECLARED`;
- `ADOPTED`;
- `DOCUMENTED_CURRENT`;
- `LIVE_VERIFIED`;
- `INFERRED`;
- `UNKNOWN`.

Pouhé přepsání commitu bez nové evidence je zakázané.
