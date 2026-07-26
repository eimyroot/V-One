# VOODOO — PRODUKTOVÁ, ROZHODOVACÍ A REALIZAČNÍ ÚSTAVA

## Metadata

| Položka | Hodnota |
|---|---|
| Soubor | `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md` |
| Verze | `1.0.0` |
| Stav | `PROPOSED_FOR_ADOPTION` |
| Vlastník | vlastník projektu VOODOO |
| Nadřazený dokument | `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` |
| Očekávaný SHA-256 nadřazeného dokumentu | `ed44c6147049887d941b7497f1bce3b817f22b6ae00a5136a27365a2f688d918` |
| Účel | určit, co VOODOO staví, proč, v jakém pořadí, kdo rozhoduje a jak se prokazuje skutečná hodnota |
| Revize | po významném milníku nebo nejméně jednou za 90 dní |

---

# 0. JEDNA STRÁNKA PRO ORIENTACI

## Co řeší který dokument

```text
WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
= jak se technická práce bezpečně provádí a ověřuje

TENTO DOKUMENT
= co stavíme, proč to stavíme, kdo rozhoduje a v jakém pořadí postupujeme
```

## Hlavní zásada

> Nejsilnější vývojový model spojuje produktovou čistotu, unixovou jednoduchost, DevOps automatizaci, SRE spolehlivost, nulovou implicitní důvěru a úplnou auditovatelnost celého životního cyklu systému — nejen jeho Git historie.

Každá významná změna musí být:

```text
JEDNODUCHÁ
ÚČELNÁ
AUTOMATIZOVANÁ
BEZPEČNÁ
MĚŘITELNÁ
VRATNÁ
DŮKAZNĚ OVĚŘITELNÁ
```

Pokud některý bod chybí, změna se přeformuluje, rozdělí, odloží nebo dostane časově omezenou výjimku.

## Co VOODOO staví

```text
CyberCore  = chápe realitu, kontext, riziko a navrhuje práci
V-One      = rozhoduje, co je povoleno, kdo to smí schválit a eviduje důkazy
Runner     = provede pouze přesně povolený plán v izolovaném prostředí
```

AI je poradce a navrhovatel. Není sama schvalovatel ani neomezený vykonavatel.

## Jednoduchý produktový tok

```text
ZÁMĚR
→ PLÁN
→ RIZIKO
→ SCHVÁLENÍ
→ PROVEDENÍ
→ OVĚŘENÍ SKUTEČNÉHO VÝSLEDKU
→ DŮKAZ
→ POUČENÍ
```

## Jednoduché role v aplikaci

```text
LIDÉ:   ADMIN · OPERATOR · APPROVER · AUDITOR
SYSTÉM: AGENT · RUNNER
```

Další role se nepřidávají, dokud konkrétní problém neprokáže jejich potřebu.

## Co dělat při každém úkolu

```text
1. Kdo to použije?
2. Jaký problém to řeší?
3. Jaký nejmenší výsledek dodáme?
4. Jaké je riziko?
5. Jak výsledek ověříme?
6. Jak změnu vrátíme?
7. Jaký důkaz zůstane po celém životním cyklu?
```

---

# 1. NORMATIVNÍ POSTAVENÍ

Při konfliktu platí toto pořadí:

1. systémová, bezpečnostní a právní pravidla platformy,
2. `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`,
3. explicitní aktuální zadání vlastníka projektu,
4. tento dokument,
5. schválené ADR a verzované kontrakty,
6. roadmapa, README a ostatní dokumentace,
7. osobní preference implementátora.

Tento dokument neduplikuje technické prováděcí podrobnosti nadřazené ústavy. Doplňuje ji v oblastech produktu, priorit, rozhodování, dodávky hodnoty a řízení životního cyklu.

Pokud není nadřazený dokument dostupný nebo jeho integrita nebyla ověřena, významná technická implementace je `BLOCKED` nebo `PARTIALLY VERIFIED`.

---

# 2. POSLÁNÍ A PRODUKTOVÁ HRANICE

VOODOO je systém pro bezpečné řízení člověkem nebo AI iniciované práce nad digitálními systémy.

Musí umět:

1. přijmout konkrétní záměr,
2. pochopit kontext a očekávaný výsledek,
3. určit oprávnění a riziko,
4. vyžádat nezávislé schválení tam, kde je nutné,
5. provést pouze povolenou schopnost,
6. zobrazit průběh, chybu a stav,
7. zastavit, obnovit nebo bezpečně ukončit běh,
8. ověřit skutečný post-state,
9. vytvořit důkaz od rozhodnutí až po provozní výsledek.

VOODOO není:

- obecný shell zabalený do UI,
- autonomní agent bez limitů,
- katalog náhodných skriptů,
- sada dokumentů vydávaná za produkt,
- systém, kde `exit 0`, HTTP `200` nebo text „hotovo“ dokazují dosažený výsledek,
- nekonečný architektonický projekt bez pravidelně dodávané použitelné schopnosti.

---

# 3. TŘI SYSTÉMOVÉ ODPOVĚDNOSTI

## 3.1 CyberCore — systém porozumění

Vlastní:

- observations a inventory,
- kontext a provenance,
- Knowledge Blocks,
- confidence a rizikové vstupy,
- návrhy a Work Blocks,
- vyhodnocení post-state a driftu.

CyberCore nesmí být druhým zdrojem pravdy pro identity, approvals nebo execution evidence.

## 3.2 V-One — systém autorizace

Vlastní:

- lidské identity a session,
- role, policy a scopes,
- change request,
- approval lifecycle,
- execution lifecycle,
- emergency stop a recovery,
- audit a receipts,
- vydání jednorázového execution grantu.

V-One je autoritativní pro otázku: **kdo směl co povolit a za jakých podmínek**.

## 3.3 Runner — systém akce

Vlastní pouze:

- kontrolu podpisu artefaktu a execution grantu,
- preflight,
- izolované provedení povolených capabilities,
- timeout, heartbeat, cancel a resource limity,
- postcondition verification,
- strukturovaný a podepsaný receipt.

Runner nesmí rozhodovat o vlastní autorizaci ani přebírat administrátorská oprávnění V-One.

## 3.4 Zakázané zkratky

- žádný plný merge V-One, CyberCore a legacy stromu,
- žádná sdílená databáze mezi systémem porozumění a systémem autorizace,
- žádný package-provided kód během deklarativního `verify`,
- žádný obecný shell jako veřejná capability,
- žádné přímé produkční mutace před izolovaným runnerem a přesným grantem,
- žádné kopírování legacy kódu bez auditu licence, původu a kontraktu.

---

# 4. UŽIVATELÉ A ROLE BEZ ZMATKU

## 4.1 Role v aplikaci

Role znamená pouze to, co smí účet provést v runtime.

| Role | Smí | Nesmí |
|---|---|---|
| `ADMIN` | spravovat uživatele, workspaces a konfiguraci | neviditelně obejít policy, audit nebo schválit vlastní požadavek |
| `OPERATOR` | vytvořit požadavek, připravit změnu, spustit schválený běh, sledovat a zastavit jej | změnit již schválený obsah nebo schválit vlastní požadavek |
| `APPROVER` | schválit nebo zamítnout přesný obsah, target, riziko a dobu platnosti | schválit vlastní požadavek nebo změnit payload po schválení |
| `AUDITOR` | read-only kontrola historie, běhů, rozhodnutí a důkazů | měnit konfiguraci, schvalovat nebo spouštět práci |

## 4.2 Strojové identity

| Identita | Účel | Hranice |
|---|---|---|
| `AGENT` | analyzuje, plánuje, připravuje návrh | nemůže sám schválit, rozšířit oprávnění nebo tvrdit provedení bez důkazu |
| `RUNNER` | provede jeden přesně autorizovaný plán | nemá trvalé široké oprávnění a nesmí změnit schválený obsah |

## 4.3 Projektové odpovědnosti nejsou runtime role

Pro vývoj stačí tři odpovědnosti:

| Odpovědnost | Význam |
|---|---|
| `OWNER` | rozhoduje o produktu, prioritě, licenci a release autorizaci |
| `IMPLEMENTER` | navrhne a provede změnu, testy a důkazy |
| `REVIEWER` | nezávisle kontroluje rizikové změny a jejich důkazy |

Jedna osoba může v malém projektu zastávat více odpovědností, ale nesmí předstírat nezávislé ověření. U změn R3–R4 musí být jasně uvedeno, co bylo skutečně nezávisle zkontrolováno a co nikoli.

---

# 5. SEDM POVINNÝCH VLASTNOSTÍ KAŽDÉ ZMĚNY

## 5.1 Jednoduchá

- řeší jeden hlavní problém,
- má malý a čitelný diff,
- nepřidává vrstvu, službu ani framework bez důkazu potřeby,
- preferuje stabilní kontrakt před množstvím abstrakcí.

## 5.2 Účelná

- má jasného uživatele,
- řeší potvrzený problém,
- má měřitelný očekávaný outcome,
- neexistuje jednodušší cesta se stejnou hodnotou.

## 5.3 Automatizovaná

- opakované kroky mají jeden kanonický příkaz nebo skript,
- lokální ověření je reprodukovatelné,
- vzdálená automatizace pouze opakuje nebo rozšiřuje stejný gate,
- automatizace má guardrails, limity a auditní výstup.

## 5.4 Bezpečná

- deny-by-default,
- least privilege,
- vstupy a kontrakty jsou validované,
- trust boundary je explicitní,
- secrets nejsou v kódu, logu ani artefaktu,
- kritická pravidla nejsou pouze v UI.

## 5.5 Měřitelná

- před změnou existuje baseline nebo je uvedeno `UNKNOWN`,
- je definován signál úspěchu a selhání,
- měření vede ke konkrétnímu rozhodnutí,
- metrika se nesmí stát cílem, který lze snadno obcházet.

## 5.6 Vratná

- rollback je známý a realistický,
- data změny mají zálohu nebo bezpečnou migrační cestu,
- capability lze vypnout feature flagem, konfigurací nebo revertem,
- nevratná změna vyžaduje samostatné rozhodnutí R4.

## 5.7 Důkazně ověřitelná

- výsledek je svázán s konkrétním zdrojem, commitem nebo artefaktem,
- je známo, kdo rozhodl, co bylo schváleno a co se provedlo,
- build a release mají digest a provenance přiměřenou riziku,
- runtime post-state je ověřen nezávisle na tvrzení vykonavatele.

## 5.8 Povinný gate `7×ANO`

Před přijetím významné změny musí být vyplněno:

```text
JEDNODUCHÁ: ANO | NE | NEOVĚŘENO
ÚČELNÁ: ANO | NE | NEOVĚŘENO
AUTOMATIZOVANÁ: ANO | NE | NEOVĚŘENO
BEZPEČNÁ: ANO | NE | NEOVĚŘENO
MĚŘITELNÁ: ANO | NE | NEOVĚŘENO
VRATNÁ: ANO | NE | NEOVĚŘENO
DŮKAZNĚ OVĚŘITELNÁ: ANO | NE | NEOVĚŘENO
```

`NE` nebo `NEOVĚŘENO` musí mít zdůvodnění, kompenzační kontrolu a případně expirující výjimku.

---

# 6. ŽIVOTNÍ CYKLUS ZMĚNY A DŮKAZŮ

Git historie je pouze jedna vrstva evidence. Každá významná změna má následující životní cyklus:

```text
1. ZÁMĚR
2. ROZHODNUTÍ
3. PLÁN
4. IMPLEMENTACE
5. VERIFIKACE
6. AUTORIZACE
7. ARTEFAKT / RELEASE
8. NASAZENÍ NEBO PROVEDENÍ
9. POZOROVÁNÍ
10. OVĚŘENÝ OUTCOME
11. POUČENÍ
```

## 6.1 Povinné důkazní vrstvy

| Vrstva | Minimální důkaz |
|---|---|
| záměr | uživatel, problém, očekávaný outcome |
| rozhodnutí | owner, datum, risk class, ADR pokud je potřeba |
| plán | scope, non-scope, testy, rollback |
| implementace | omezený diff a identita zdroje |
| verifikace | skutečné příkazy, exit code, výsledky a neprovedené kontroly |
| autorizace | kdo povolil přesný digest, target, policy a expiry |
| artefakt | digest, verze, build metadata, SBOM/provenance podle rizika |
| nasazení/provedení | execution ID, runner identity, začátek, konec, stav |
| pozorování | logy, metriky, health/readiness, correlation ID |
| outcome | pre-state vs post-state a splnění cíle |
| poučení | incident, postmortem, změna priority nebo pravidel |

Důkaz nesmí obsahovat raw secrets, osobní data bez potřeby ani celé citlivé provider responses.

---

# 7. ROZHODOVACÍ MODEL

## 7.1 Rizikové třídy

| Třída | Příklad | Povinné rozhodnutí |
|---|---|---|
| `R0` | dokumentace, komentář | lokální kontrola a owner awareness |
| `R1` | test, malý interní refaktor bez změny chování | relevantní testy a omezený diff |
| `R2` | API chování, adapter, dependency, UI workflow | explicitní owner approval a rollback |
| `R3` | identity, autorizace, persistence, audit, security, release | design review, nezávislá kontrola důkazů, rollback evidence |
| `R4` | produkční efekt, destruktivní migrace, veřejný breaking change | samostatné rozhodnutí, záloha/dry-run, explicitní release autorizace |

Automatizace, agent ani implementátor nesmí sám schválit vlastní R2–R4 změnu jako nezávislý důkaz.

## 7.2 Kdy je povinné ADR

ADR je povinné, když změna:

- mění produktovou hranici,
- mění trust boundary,
- zavádí databázi, broker, nový runtime nebo významný framework,
- mění veřejné API nebo datový formát,
- mění identity, role, policy nebo approval semantics,
- vytváří draze vratnou závislost,
- rozhoduje o integraci V-One, CyberCore, Runneru nebo legacy komponenty.

ADR není povinné pro každou drobnou implementaci.

## 7.3 Rozhodovací karta

Před R2–R4 změnou musí existovat krátký záznam:

```text
NÁZEV:
UŽIVATEL:
PROBLÉM:
OČEKÁVANÝ OUTCOME:
RISK CLASS:
NEJMENŠÍ BEZPEČNÝ SLICE:
ZDROJ PRAVDY:
DOTČENÁ DATA A OPRÁVNĚNÍ:
DŮKAZ ÚSPĚCHU:
ROLLBACK:
MIMO ROZSAH:
OWNER DECISION:
```

---

# 8. REALIZAČNÍ MODEL

## 8.1 Jeden hlavní vertikální řez

Každý sprint nebo pracovní blok má dodat jeden viditelný outcome:

```text
uživatelský záměr
→ UI/API
→ doménová logika
→ oprávnění a policy
→ provedení
→ persistence/evidence
→ observabilita
→ test
```

Není nutné měnit všechny vrstvy. Musí však vzniknout použitelný a ověřitelný celek.

## 8.2 WIP limit

Současně mohou běžet nejvýše:

- jedna hlavní produktová capability,
- jedna bezpečnostní nebo spolehlivostní náprava P0/P1.

Třetí významný proud se nezačíná, dokud jeden z předchozích není uzavřen, pozastaven nebo výslovně přehodnocen.

## 8.3 Local-first a provider-neutral automation

Kanonický gate musí být spustitelný lokálně jedním zdokumentovaným příkazem nebo malou sadou příkazů.

Vzdálené CI je doplňkové ověření. Nesmí být jediným místem, kde existuje důležitá kontrola, ani podmínkou pro běžný lokální commit nebo push.

## 8.4 Povinný cyklus dodávky

```text
AUDIT
→ ROZHODNUTÍ
→ NEJMENŠÍ SLICE
→ IMPLEMENTACE
→ CÍLENÉ TESTY
→ PLNÝ RELEVANTNÍ GATE
→ EVIDENCE
→ COMMIT
→ RELEASE AUTORIZACE, POKUD JE POTŘEBA
→ OBSERVACE
→ OUTCOME REVIEW
```

## 8.5 Stop pravidlo proti nekonečné přípravě

Další proces, dokument, framework nebo abstrakce se nepřidává, pokud:

- neodstraňuje konkrétní P0/P1 riziko,
- nezkracuje čas k ověřenému outcome,
- nezabraňuje opakované chybě,
- není nutný pro nejbližší vertikální řez.

---

# 9. PRODUKTOVÁ PRIORITIZACE

## 9.1 Pořadí priorit

```text
P0 — bezpečnost, integrita, ztráta dat, právní nebo nevratné riziko
P1 — blokující produktový outcome nebo kritická spolehlivost
P2 — významná capability nebo dluh s prokázaným dopadem
P3 — optimalizace, komfort a lokální zjednodušení
P4 — experiment, kosmetika nebo hypotetická budoucí potřeba
```

## 9.2 Test hodnoty 0–10

Každá oblast má 0 až 2 body:

| Oblast | 0 | 1 | 2 |
|---|---|---|---|
| uživatel | není znám | nepřímý | konkrétní a oprávněný |
| problém | hypotetický | reálný, ale neblokující | potvrzený a důležitý |
| outcome | pouze interní změna | částečně použitelný | úplný vertikální výsledek |
| důkaz | nelze ověřit | částečný | předem jasný a nezávislý |
| dlouhodobý dopad | zvyšuje složitost | neutrální | zjednodušuje další rozvoj |

```text
0–3  = nízká hodnota
4–6  = přeformulovat nebo odložit
7–8  = vysoká hodnota
9–10 = velmi vysoká hodnota
```

P0 bezpečnostní náprava může mít nižší produktové skóre, protože chrání integritu celého systému.

---

# 10. DEFINICE PŘIPRAVENÉ PRÁCE

Práce je připravena k zahájení, když:

- je znám uživatel a problém,
- je definován nejmenší bezpečný outcome,
- je znám risk class,
- jsou známé zdroje pravdy,
- scope a non-scope jsou explicitní,
- jsou předem definované testy a evidence,
- je znám rollback nebo je nevratnost schválena jako R4,
- změna prošla gate `7×ANO`,
- nevytváří neřízený druhý zdroj pravdy.

Bez těchto bodů je práce `PROPOSED`, nikoli připravená implementace.

---

# 11. DEFINICE HODNOTNĚ DOKONČENÉ PRÁCE

Technická Definition of Done z nadřazené ústavy zůstává povinná.

Navíc je outcome hodnotně dokončený, když:

- oprávněný uživatel jej umí skutečně použít,
- výsledek řeší původní problém,
- pre-state a post-state jsou porovnány tam, kde to dává smysl,
- oprávnění a policy byly skutečně vynuceny,
- chyba, stav a recovery jsou srozumitelné,
- byly provedeny a uvedeny relevantní testy,
- existuje důkaz celého životního cyklu,
- rollback je ověřený nebo realisticky proveditelný,
- dokumentace odpovídá implementaci,
- známá omezení jsou zapsaná,
- další krok nevzniká automaticky jen proto, aby pokračoval refaktor.

Funkce není dokončená jen proto, že existuje commit, endpoint, tlačítko, zelený happy path nebo dokumentace.

---

# 12. SPOLEHLIVOST, SLO A ERROR BUDGET

Každá produkční nebo pilotní služba musí mít několik uživatelsky významných SLI/SLO, nikoli desítky kosmetických metrik.

Minimálně podle relevance:

- dostupnost,
- úspěšnost ověřených outcomes,
- latency klíčového workflow,
- chybovost execution,
- doba recovery,
- integrita evidence.

Error budget řídí prioritu:

- pokud je služba v rámci SLO, vývoj může pokračovat,
- pokud je error budget vyčerpán chybou projektu, priorita se přesouvá na spolehlivost,
- bezpečnostní P0 se řeší bez ohledu na error budget,
- SLO není marketingový slib, ale rozhodovací nástroj.

Monitoring má být co nejjednodušší, ale dostatečný pro rozhodnutí, diagnostiku a audit. Nepoužívané signály jsou kandidáti na odstranění.

---

# 13. METRIKY BEZ SEBEKLAMU

Metriky se používají pro trend a rozhodnutí, ne pro soutěž nebo obcházení cíle.

## 13.1 Hlavní produktové metriky

- `Governed Verified Outcome Rate` — podíl požadavků zakončených ověřeným výsledkem bez policy bypassu,
- čas od záměru k ověřenému outcome,
- podíl běhů vyžadujících ruční recovery,
- podíl outcomes s úplnou evidencí,
- čas potřebný k bezpečnému přidání nové capability.

## 13.2 Delivery metriky

Sledují se jako sada, nikoli jedna absolutní hodnota:

- change lead time,
- deployment frequency,
- failed deployment recovery time,
- change fail rate,
- deployment rework rate.

Speed a stability se neřídí jako protiklady. Menší změny typicky zlepšují obojí.

## 13.3 Bezpečnostní metriky

- otevřené P0/P1 nálezy podle stáří,
- počet zamítnutých neoprávněných pokusů,
- doba od nálezu k mitigaci,
- pokrytí artefaktů provenance a podpisy,
- počet výjimek po expiraci.

---

# 14. AI A ŘÍZENÁ AUTONOMIE

## 14.1 Povolená role AI

AI může:

- analyzovat,
- navrhovat plán,
- připravit change request,
- vysvětlit riziko,
- navrhnout testy a rollback,
- hodnotit výsledek z dostupných důkazů.

AI nesmí:

- schválit vlastní rizikovou změnu,
- rozšířit vlastní oprávnění,
- obejít policy,
- změnit schválený digest nebo target,
- spustit obecný shell bez explicitního design rozhodnutí,
- tvrdit úspěch bez runtime a outcome evidence.

## 14.2 Úrovně autonomie

| Úroveň | Chování |
|---|---|
| `A0` | návrh a vysvětlení |
| `A1` | read-only observation a plán |
| `A2` | vratná capability s předem omezeným oprávněním |
| `A3` | více kroků s průběžným dohledem a stop podmínkami |
| `A4` | delší autonomie jen s policy, rozpočtem, recovery a úplnými důkazy |

Projekt nesmí přejít na vyšší úroveň, dokud nižší úroveň nemá stabilní evidence, limity a recovery.

---

# 15. INTEGRACE V-ONE × CYBERCORE × RUNNER

## 15.1 Povolené pořadí

```text
FÁZE 0 — ověřit aktuální baseline a uzavřít otevřená P0 rizika
FÁZE 1 — stabilizovat V-One jako autoritativní control plane
FÁZE 2 — read-only intake, observations a Knowledge Blocks
FÁZE 3 — jeden kanonický podepsaný CXP kontrakt
FÁZE 4 — isolated runner a short-lived execution grant
FÁZE 5 — governed provider capabilities a postcondition verification
FÁZE 6 — agentní plánování a řízená autonomie
```

## 15.2 První bezpečný integrační slice

První integrace má být read-only:

- metadata artefaktu,
- digest,
- schema a signature status,
- target reference,
- risk,
- expected effect,
- verification plan,
- bez shell execution,
- bez secrets,
- bez mutation,
- feature flag off-by-default,
- audit event povinný.

## 15.3 Podmínky před mutační integrací

- žádný executable verify,
- jeden kanonický CXP formát a parser,
- full-package inventory a reject unknown files,
- publisher signature a trust store,
- approval svázaný s přesným digestem, targetem, policy a expiry,
- isolated runner,
- idempotence, lease, fence, heartbeat a cancel,
- postcondition verification,
- strukturovaný receipt,
- vyjasněná licence a provenance kódu.

---

# 16. AKTUÁLNÍ ORIENTACE PODLE DODANÝCH AUDITŮ

Tato sekce je orientační baseline, nikoli náhrada kontroly aktivního repozitáře.

| Oblast | Důkazní stav z dodaných podkladů |
|---|---|
| VOODOO One / V-One | primární produktový základ a autoritativní control plane |
| CyberCore | silný model porozumění a artefaktů, ale mutační runtime vyžaduje hardening |
| Legacy `voodoo-os 2.zip` | zdroj konceptů; ne přímý merge ani release |
| Isolated Runner | cílová samostatná execution vrstva; aktuální implementace musí být ověřena v aktivním repo |
| Produkční efekty | nesmí být považovány za povolené bez aktuálního evidence gate a explicitní release autorizace |

Před dalším technickým rozhodnutím se musí proti skutečnému aktivnímu repozitáři ověřit:

```text
CURRENT_COMMIT
CURRENT_BRANCH
WORKTREE_STATUS
OPEN_P0_RISKS
OPEN_P1_BLOCKERS
CURRENT_TEST_EVIDENCE
CURRENT_RUNTIME_EVIDENCE
CURRENT_RELEASE_STATE
```

Historický audit nebo zelený checkpoint není automaticky důkaz současného stavu.

---

# 17. CANONICKÁ MAPA DOKUMENTŮ

Projekt má mít minimum kanonických zdrojů:

| Dokument | Jediná odpovědnost |
|---|---|
| `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` | jak se technická práce provádí, testuje, ověřuje a reportuje |
| tento dokument | co se staví, proč, kdo rozhoduje a jak probíhá dodávka hodnoty |
| `CURRENT_PRODUCT_STATE.md` | aktuální důkazní snapshot svázaný s konkrétním commitem |
| `README.md` | aktuální účel a bezpečný start |
| `ARCHITECTURE.md` | skutečná současná architektura |
| `SECURITY.md` | podporovaný bezpečnostní stav a reporting |
| `CONTRIBUTING.md` | praktický workflow změn |
| `CHANGELOG.md` | skutečně provedené změny |
| ADR | jednotlivá významná rozhodnutí |
| runbook/postmortem | provoz a poučení z incidentů |

Stejná informace nesmí mít dva nezávislé kanonické zdroje.

---

# 18. POVINNÝ CURRENT PRODUCT STATE

Proměnlivý stav se neukládá do ústavy. Udržuje se v `CURRENT_PRODUCT_STATE.md`:

```text
AS_OF:
VERIFIED_COMMIT:
VERIFIED_BRANCH:
WORKTREE_STATUS:
CURRENT_PHASE:
VERIFIED_CAPABILITIES:
PARTIALLY_VERIFIED_CAPABILITIES:
OPEN_P0_RISKS:
OPEN_P1_BLOCKERS:
CURRENT_VERTICAL_SLICE:
TEST_EVIDENCE:
RUNTIME_EVIDENCE:
RELEASE_STATE:
NEXT_SAFE_STEP:
```

Každá položka musí být `VERIFIED`, `PARTIALLY VERIFIED`, `INFERRED`, `UNKNOWN` nebo `BLOCKED` podle skutečných důkazů.

---

# 19. VÝJIMKY A NOUZOVÉ ZMĚNY

Výjimka musí obsahovat:

- pravidlo, ze kterého se uděluje,
- důvod,
- scope,
- risk class,
- kompenzační kontrolu,
- ownera,
- datum expirace,
- podmínku uzavření,
- následný review nebo postmortem.

Výjimka bez expirace je neplatná.

Nouzová změna může zkrátit běžný proces, ale nesmí odstranit audit, minimální autorizaci, evidenci skutečného dopadu ani následný review.

---

# 20. REVIZE SMĚRU

Po každém významném milníku se odpoví:

1. Co je nově skutečně použitelné?
2. Kdo to použil nebo může použít?
3. Jaký outcome byl ověřen?
4. Jaké důkazy existují mimo Git historii?
5. Co selhalo a proč?
6. Co lze odstranit nebo zjednodušit?
7. Kde vznikl druhý zdroj pravdy?
8. Jaký předpoklad se ukázal jako chybný?
9. Jaký je nejlepší další vertikální slice?
10. Neinvestujeme více do procesu než do produktu?

Roadmapa je hypotéza. Důkazy ji mohou změnit.

---

# 21. ZMĚNA TÉTO ÚSTAVY

Změna musí:

- zvýšit verzi,
- uvést důvod a dopad,
- uvést, zda mění autoritu, role nebo produktovou hranici,
- být schválena vlastníkem projektu,
- aktualizovat SHA-256 manifest,
- zachovat historickou verzi nebo jasný Git záznam.

```text
PATCH = zpřesnění bez změny významu
MINOR = nové pravidlo nebo proces
MAJOR = změna poslání, autority nebo systémového rozdělení
```

---

# 22. ADOPČNÍ CHECKLIST

Dokument je účinný teprve, když:

- je uložen vedle nadřazené technické ústavy v kanonickém repozitáři,
- jeho SHA-256 je skutečně vypočítán a uložen,
- je uveden v README nebo governance mapě,
- je schválen vlastníkem,
- existuje `CURRENT_PRODUCT_STATE.md`,
- R2–R4 změny používají rozhodovací kartu,
- sprinty respektují WIP limit a vertikální outcome,
- milestone review používá sekci 20,
- dokument není v konfliktu s nadřazenou ústavou.

Do té doby je stav `PROPOSED_FOR_ADOPTION`.

---

# 23. VÝZKUMNÝ ZÁKLAD

Tato ústava syntetizuje následující veřejné primární zdroje a zavedené principy:

- NIST SP 800-207 — nulová implicitní důvěra, ochrana zdrojů a průběžné ověřování,
- NIST SP 800-218 SSDF — bezpečnost integrovaná do celého SDLC,
- Google SRE — SLO, error budget, jednoduchý monitoring, postmortem a řízení spolehlivosti,
- DORA — společné měření throughputu a stability; malé změny jako cesta k lepšímu delivery,
- AWS Well-Architected Operational Excellence — časté malé vratné změny a operations as code,
- SLSA v1.2 — ověřitelná provenance artefaktů a důvěryhodnost supply chain,
- unixový princip malých komponent, jasných rozhraní a omezené odpovědnosti.

Tyto zdroje jsou inspirace a validační rámec. Skutečným zdrojem pravdy pro stav VOODOO zůstává aktivní repozitář, runtime a ověřené důkazy.

---

# 24. ZÁVĚREČNÝ FILTR

Před každou významnou změnou musí být možné odpovědět `ANO`:

```text
Je to skutečně potřebné?
Je to nejjednodušší bezpečná cesta?
Přináší to jasný uživatelský outcome?
Je změna malá a omezená?
Je automatizovatelná a reprodukovatelná?
Je bezpečná podle zero-trust a least-privilege principů?
Je měřitelná?
Je vratná?
Existuje důkaz celého životního cyklu, nejen commit?
```

Když odpověď není `ANO`, změna se nemá vydávat za připravenou.
