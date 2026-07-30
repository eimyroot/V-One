# VOODOO — CURRENT PRODUCT STATE

> Tento dokument je proměnlivý důkazní snapshot. Není náhradou Git stavu, testů ani runtime evidence.

## Identita snapshotu

```text
AS_OF: 2026-07-30
AUDIT_BASE_BRANCH: main
AUDIT_BASE_COMMIT: afd03c5653278c98fb3ca5494ae3c14355f08655
OBSERVED_REMOTE_TRACKING_BRANCH: origin/main
OBSERVED_REMOTE_TRACKING_COMMIT: eb47933a36592418842397df3d8f7ac655c238d6
OBSERVED_LOCAL_REMOTE_RELATION: local main was one unpublished AGENTS commit ahead at audit preflight
AUDIT_PREFLIGHT_WORKTREE: clean before this documentation patch
CURRENT_PHASE: LOCAL AGENT GOVERNANCE COMMITTED + CURRENT-HEAD RUNTIME RE-ATTESTATION PENDING
CURRENT_HEAD_CI: UNKNOWN — NOT VERIFIED after the latest source/governance changes
CURRENT_HEAD_RUNTIME_ATTESTATION: UNKNOWN — NOT VERIFIED after the latest source/governance changes
RELEASE_STATE: BLOCKED — není release-verified
PRODUCTION_EFFECTS: source policy remains fail-closed; current-HEAD runtime state was not re-attested
```

Exact current repository identity is authoritative from live Git state (`git rev-parse HEAD`, current
branch, worktree status, and tracking refs), not from this version-controlled snapshot.

## Aktuální zdrojový a důkazní stav

Následující capability jsou přítomné v aktuálním source tree a mají dřívější cílené testovací
důkazy. Tento audit neprovedl runtime re-attestaci po nejnovějších source/governance změnách.

- FastAPI `/api/v1` control plane a statická command-center konzole.
- Lokální bootstrap, login, context-bound sessions, logout a administrativní revokace sessions.
- RBAC, workspaces, change requests, nezávislé approvals a execution lifecycle.
- Emergency stop, execution idempotency, leases, fencing a explicitní indeterminate recovery.
- Checksum-verified SQLite migrace a reviewovaný SQL statement catalog.
- Audit a receipt ledgers s nezávislou kontrolou integrity.
- Bounded local adapters a governed sandbox filesystem effects.
- Lokální checkpoint verifier a deterministický ProofGraph v1 JSON.
- Repository-owned checkpoint finalizer s fail-closed snapshot/copy/staging verification a atomickým publish krokem.
- Hash-locked dependencies, lokální lint/compile/test/readiness gates a Docker build/smoke workflow.
- Source policy drží produkční efekty vypnuté a fail-closed; current-HEAD runtime stav je `UNKNOWN`.

## Auditované source milníky

- Při auditním preflightu obsahoval pozorovaný
  `origin/main@eb47933a36592418842397df3d8f7ac655c238d6` publisher hardening a
  repository-owned publication guardrails.
- Auditní base `main@afd03c5653278c98fb3ca5494ae3c14355f08655` přidal root `AGENTS.md` jako
  repository-wide agent governance contract.
- Při auditním preflightu nebyl AGENTS commit publikován na `origin/main` a lokální `main` byl
  o jeden commit napřed.
- Pro source/governance změny po historickém runtime checkpointu nebyly v tomto úkolu spuštěny CI,
  runtime, Docker, release ani deployment gates.

## Historický runtime checkpoint

PR #42 byl mergnut do `main` jako merge commit:

```text
81522699a9cf7c413e0d9f7c7afcc867e0df8d02
```

Milník přidal repository-owned checkpoint finalization. Finalizer nyní:

- zachytí a porovná candidate snapshot před/po verification a po copy;
- odmítne symlinky, special files, candidate races, neplatný manifest a unsafe destination;
- vytvoří frozen staging kopii;
- zapisuje nested/outer manifests až po zmrazení stagingu;
- vyžaduje canonical verification s nulou errors a warnings;
- publikuje checkpoint pouze same-filesystem atomickým rename;
- zachovává strukturovanou failure evidence a nikdy tím neautorizuje release nebo production effect.

Pro feature commit `190758e27b38a1139ff51a4e00bb3767634b19ea` existuje fresh native Docker runtime checkpoint s těmito ověřenými výsledky:

```text
FULL_PYTEST: 298 passed
READINESS_TESTS: 298 passed
RUFF: passed
COMPILEALL: passed
PRODUCT_IMAGE_SMOKE: passed
DOCKER_HEALTHCHECK: healthy
PRODUCTION_EFFECTS: disabled
INDEPENDENT_CANONICAL_VERIFY: valid=true, errors=[], warnings=[]
EVIDENCE_ARCHIVE_SHA256: cfd89bfa59cef58508993a95753d06894147402447bb6eac7a2e7451dcb3ffab
CHECKPOINT_OUTER_MANIFEST_SHA256: d00c8600737e3a0b92412fd02315d33d05c1c591ca9cc52f791735ec77986776
RUNTIME_BUNDLE_SHA256: e7b5cc9096571d874882ed3529747f768a557d42bbddffa7b367157be871a968
```

GitHub comparison potvrdil, že merge commit `81522699...` nepřidal proti feature commitu `190758e...` žádnou další file-level změnu. Přesto je runtime provenance commit-bound, takže starý checkpoint nelze vydávat za fresh checkpoint pro nový `main` commit.

## Co lze od platformy očekávat dnes

Tato očekávání vycházejí z aktuálního source inventory a historických scoped testů, nikoli z fresh
runtime attestace pro current HEAD.

VOODOO One je nyní **development / controlled-pilot authorization and evidence control plane**.

Lze od něj očekávat:

- řízené change requests a approvals;
- explicitní identity/policy/execution lifecycle;
- auditovatelné evidence a receipts;
- bounded lokální execution capabilities;
- fail-closed recovery a production-effect controls;
- lokální verification/finalization evidence checkpointů.

Nelze od něj zatím očekávat unrestricted production automation, autonomní produkční execution nebo release-grade supply chain.

## Co zbývá

### Nejbližší práce

1. **Review a commit current-state patch** — po schválení zachovat přesnou source identitu.
2. **Samostatně autorizovat publikaci** — pokud má být lokální AGENTS governance dostupná vzdáleně.
3. **Fresh runtime checkpoint pro budoucí publikovaný canonical HEAD** — provést až po přesném
   source/remote srovnání; historický checkpoint nerecyklovat jako current-HEAD evidence.
4. **Policy Decision Graph v1** — pokračovat v deterministickém a vysvětlitelném authorization modelu.
5. **Isolated Runner contracts** — signed short-lived grants, receipts, heartbeat/cancel/fencing a postcondition verification.
6. **Read-only CyberCore boundary** — až po review výše uvedených kontraktů.

### Stále BLOCKED / PROPOSED

- unrestricted production release;
- production effects;
- isolated runner capsules a signed execution grants;
- released OIDC a PostgreSQL backend;
- signed checkpoints/receipts a external evidence anchoring;
- remote byte attestation, širší SBOM/provenance a multi-arch release evidence;
- mutační CyberCore integration;
- public commercial distribution před vyřešením licence, EULA, privacy a support modelu.

## Důkazní stav

```text
VERIFIED:
- audit base = main@afd03c5653278c98fb3ca5494ae3c14355f08655
- observed remote = origin/main@eb47933a36592418842397df3d8f7ac655c238d6
- lokální main byl při auditním preflightu o jeden nepublikovaný AGENTS commit před origin/main
- publisher hardening byl pozorován v origin/main
- root AGENTS.md byl přítomný v auditním base; vzdálená publikace nebyla pozorována
- checkpoint verifier + repository-owned finalizer jsou přítomné v source tree
- feature commit 190758e... má nezávisle ověřený fresh runtime checkpoint

IMPLEMENTED:
- current-state dokumentace odděluje auditní pozorování, verzovanou product truth a live Git identitu

UNKNOWN:
- CI a runtime stav po nejnovějších source/governance změnách
- current-HEAD production-effects runtime stav; source policy zůstává fail-closed
- úplný aktuální P0/P1 finding set bez nového explicitního auditu

BLOCKED:
- unrestricted production release
- public commercial distribution
```

## NEXT SAFE STEP

Zkontrolovat a samostatně commitnout tento omezený documentation-only patch. Publikace,
current-HEAD runtime re-attestace a release zůstávají oddělené, neautorizované kroky.

Capability-level detail: [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)  
Delivery order: [`ROADMAP.md`](ROADMAP.md)
