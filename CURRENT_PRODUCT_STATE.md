# VOODOO — CURRENT PRODUCT STATE

> Tento dokument je proměnlivý důkazní snapshot. Není náhradou živého Git stavu,
> provedených testů ani commit-bound runtime evidence.

## Identita a hranice tvrzení

```text
AS_OF: 2026-07-30
LIVE_BRANCH_AT_RECONCILIATION_PREFLIGHT: main
LIVE_HEAD_AT_RECONCILIATION_PREFLIGHT: 8a5f36b218c3aa6dce2e4cf771512875f136d839
LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@8a5f36b218c3aa6dce2e4cf771512875f136d839
RUNTIME_EVIDENCE_CLASS: DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE
PDG_V1_SOURCE_TEST_STATUS: OWNER_ACCEPTED_AND_LOCALLY_VERIFIED
PDG_V1_RUNTIME_ATTESTATION: NOT_ATTESTED_BY_LATEST_CHECKPOINT
RELEASE_STATE: BLOCKED — není release-verified
PRODUCTION_EFFECTS: DISABLED in the verified local-development runtime checkpoint
```

Tyto identity nesmějí být slučovány:

1. **Živá Git identita** je vždy autoritativně zjištěna příkazy nad aktuálním repozitářem.
2. **Runtime-attested baseline** je commit
   `8a5f36b218c3aa6dce2e4cf771512875f136d839` a pouze jeho zachycený artefakt.
3. **PDG v1 source/test evidence** je owner-accepted a lokálně VERIFIED pro read-only projection
   scope; checkpoint pro `8a5f36b...` PDG v1 ani pozdější source změny neattestuje.
4. **Release stav** zůstává `BLOCKED`; lokální development-runtime evidence není release,
   deployment ani produkční autorizace.

## Aktuální source capability

VOODOO One je nyní **development / controlled-pilot authorization and evidence control plane**.
Aktuální source tree obsahuje:

- FastAPI `/api/v1` control plane a statickou command-center konzoli;
- lokální bootstrap, login, context-bound sessions, logout a administrativní revokaci sessions;
- RBAC, workspaces, change requests, nezávislé approvals a execution lifecycle;
- emergency stop, execution idempotency, leases, fencing a explicitní indeterminate recovery;
- checksum-verified SQLite migrace a reviewovaný SQL statement catalog;
- audit a receipt ledgers s nezávislou kontrolou integrity;
- bounded local adapters a governed sandbox filesystem effects;
- lokální checkpoint verifier, deterministický ProofGraph v1 JSON a repository-owned checkpoint
  finalizer;
- **read-only Policy Decision Graph v1** jako čistou deterministickou projekci caller-supplied
  authoritative snapshotu.

Policy Decision Graph v1 vrací `ALLOW` nebo `DENY`, `execution_eligible`, reason codes,
limitations, deterministicky řazené nodes/edges a digest. Nemá autorizační pravomoc, není runtime
gate, nic nevykonává ani nepersistuje a není napojen do API, service, execution lifecycle,
databáze nebo CyberCore. Zachovává současné `ApprovalPolicyDecision.reason_codes` a nové
projekční kódy používají namespace `PDG_*`. Budoucí approval payload, policy-version a expiry
binding jsou limitations, nikoli nově vynalezená deny policy.

ADR-0006 je owner-accepted pro tento omezený projection-only slice. Přijatý corrected review
patch má SHA-256:

```text
47304e1268af92a4196e9c61d2e2576792c540abca4c26326b8eee99b61951a0
```

## Kanonický runtime checkpoint

Pro committed baseline
`main@8a5f36b218c3aa6dce2e4cf771512875f136d839` existuje kanonická evidence:

```text
EVIDENCE_DIRECTORY:
/Users/eimyna/00_DEV/V-ONE-EVIDENCE/CODEX/CANONICAL_MAIN_CLOSURE_20260730T151146Z_8a5f36b
EVIDENCE_SHA256_MANIFEST:
1cf2cc77cb10a3a2a31caa4be418448d4f0e4d7cda8a4d8fe52fb61bfa279f94
FINAL_VERIFY: valid=true, errors=[], warnings=[]
RUNTIME_CLASS: DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE
IMAGE_ID: sha256:b3d1c3e7cca161dd185cb71cf6400052426e6120222f75f456e2236774419b6d
IMAGE: voodoo-one:capture-8a5f36b218c3-97bbc4d394b3
RUNTIME_BUNDLE_SHA256:
fca9620a3a8f69f491828468ec3c2305f2e6574f5c5a7e51cd7954b5db8c4a23
PLATFORM: linux/amd64
SMOKE: PASSED
HEALTH: HEALTHY
PRODUCTION_EFFECTS: DISABLED
CHECKPOINT_OUTER_MANIFEST_SHA256:
88671ebbfa527de47f03aacbe598791bc8c46bba2c8fb206493fadc088b81e12
CHECKPOINT_FINALIZED: true
```

Evidence je omezena na lokální development runtime. Neprokazuje registry push, remote write,
signing, release, deployment ani production effects. Neattestuje PDG v1 ani source změny
následující po přesně uvedeném baseline commitu.

## Dodaný milník a další pořadí

EPIC-002 je uzavřen na committed baseline `8a5f36b...`: repository-owned checkpoint
finalization a canonical-main runtime closure mají přesnou lokální evidence identity.

ADR-0006 a read-only PDG v1 tvoří přijatý foundation slice širšího target Policy Decision Graphu.
Nejsou execution-policy integrací. Další bezpečný delivery pořadník je:

1. execution grant / receipt contract s explicitní vazbou identity, scope, freshness a evidence;
2. isolated runner contract a teprve potom jeho oddělená implementace;
3. read-only CyberCore proposal boundary;
4. mutační nebo autonomní integrace pouze po samostatném návrhu, review a autorizaci.

## Co zůstává PROPOSED nebo BLOCKED

- autoritativní runtime Policy Decision Graph a capability-policy engine;
- isolated runner capsules a signed short-lived execution grants;
- released OIDC a PostgreSQL backend;
- signed checkpoints/receipts a external evidence anchoring;
- remote byte attestation, širší SBOM/provenance a multi-arch release evidence;
- mutační CyberCore integration;
- unrestricted production release a production effects;
- public commercial distribution před vyřešením licence, EULA, privacy a support modelu.

## Důkazní stav

```text
VERIFIED:
- reconciliation preflight observed main@8a5f36b218c3aa6dce2e4cf771512875f136d839
- canonical runtime evidence manifest matches its required SHA-256
- canonical verification reports valid=true, errors=[], warnings=[]
- runtime evidence class is DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE
- verified checkpoint smoke passed, health was healthy, and production effects were disabled
- corrected PDG patch identity matches the owner-accepted SHA-256
- read-only PDG v1 is locally source/test VERIFIED for its projection-only scope

IMPLEMENTED:
- read-only Policy Decision Graph v1 exists as a pure library with no runtime integration
- ADR-0006 records owner acceptance without adding runtime authority
- documentation separates live Git, commit-bound runtime evidence, subsequent source changes, and release

NOT VERIFIED:
- runtime attestation for PDG v1 or any source change after `8a5f36b218c3aa6dce2e4cf771512875f136d839`
- release, deployment, registry publication, remote signing, or production operation

BLOCKED:
- unrestricted production release
- production effects
- public commercial distribution
```

Capability detail: [`docs/product/CURRENT_CAPABILITIES.md`](docs/product/CURRENT_CAPABILITIES.md)

Delivery order: [`ROADMAP.md`](ROADMAP.md)

Accepted decision: [`docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md`](docs/adr/ADR-0006-read-only-policy-decision-graph-v1.md)
