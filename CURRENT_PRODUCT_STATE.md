# VOODOO — CURRENT PRODUCT STATE

> Tento dokument je proměnlivý důkazní snapshot. Není náhradou Git stavu, testů ani runtime evidence.

## Identita snapshotu

```text
AS_OF: 2026-07-30
VERIFIED_REMOTE_BRANCH: main
VERIFIED_REMOTE_COMMIT: 81522699a9cf7c413e0d9f7c7afcc867e0df8d02
MERGED_PR: #42
MERGED_FEATURE_COMMIT: 190758e27b38a1139ff51a4e00bb3767634b19ea
LOCAL_WORKTREE_STATUS: UNKNOWN — čeká na post-merge local reality check
CURRENT_PHASE: POST-MERGE STABILIZATION + CURRENT-HEAD RUNTIME RE-ATTESTATION
RELEASE_STATE: BLOCKED — není release-verified
PRODUCTION_EFFECTS: VERIFIED DISABLED / FAIL-CLOSED
```

## Co dnes skutečně funguje

### VERIFIED

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
- Produkční efekty zůstávají vypnuté a fail-closed.

## Čeho jsme právě dosáhli

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

1. **Post-merge local reality check** — ověřit čistý lokální repo stav a synchronizovat lokální `main` na `81522699...`.
2. **Fresh runtime checkpoint pro current `main`** — vytvořit nový checkpoint přímo pro merge commit `81522699...`.
3. **Policy Decision Graph v1** — pokračovat v deterministickém a vysvětlitelném authorization modelu.
4. **Isolated Runner contracts** — signed short-lived grants, receipts, heartbeat/cancel/fencing a postcondition verification.
5. **Read-only CyberCore boundary** — až po review výše uvedených kontraktů.

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
- remote main = 81522699a9cf7c413e0d9f7c7afcc867e0df8d02
- PR #42 merged
- checkpoint verifier + repository-owned finalizer jsou na main
- feature commit 190758e... má nezávisle ověřený fresh runtime checkpoint
- production effects jsou disabled / fail-closed

PARTIALLY VERIFIED:
- runtime stav current main: source tree odpovídá ověřenému feature tree,
  ale runtime provenance zatím není znovu svázána s merge commitem 81522699...

UNKNOWN:
- aktuální lokální branch/HEAD/worktree/index do provedení post-merge reality checku
- úplný aktuální P0/P1 finding set bez nového explicitního auditu

BLOCKED:
- unrestricted production release
- public commercial distribution
```

## NEXT SAFE STEP

Provedení krátkého post-merge local reality checku a následně nový fresh runtime checkpoint přímo pro `81522699a9cf7c413e0d9f7c7afcc867e0df8d02`.

Capability-level detail: [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)  
Delivery order: [`ROADMAP.md`](ROADMAP.md)
