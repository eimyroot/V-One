# VOODOO Governance Map

| Pole | Hodnota |
|---|---|
| Třída dokumentu | Orientační governance mapa |
| Normativní autorita | Žádná; autorita zůstává v uvedených dokumentech a přijatých rozhodnutích |
| Účel | Udržet oddělenou deklarovanou autoritu, skutečnou adopci, důkazní stav a plánovaný stav |
| Autoritativní adopční záznam | `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md` |
| Aktualizace | Při adopci, zrušení nebo změně autority kteréhokoli governance dokumentu |

> Přítomnost dokumentu v repozitáři, jeho merge, použití v promptu nebo označení „constitution“ samo
> o sobě není adopce. Nejasný konflikt autority se řeší fail-closed jako `BLOCKED`.

## 1. Čtyři oddělené otázky

Každý governance audit musí rozlišit:

1. **DECLARED** — co dokument tvrdí o své autoritě;
2. **ADOPTED** — zda existuje explicitní owner/ADR adopční záznam;
3. **DOCUMENTED_CURRENT** — co dokument uvádí jako stav k datu nebo baseline;
4. **LIVE_VERIFIED** — co bylo ověřeno přímo z aktuálního Git stavu, testů, CI nebo runtime.

Tyto kategorie se nesmějí slučovat.

## 2. Aktuální fail-closed mapa autority

Na základě dodané sady dokumentů lze bezpečně tvrdit:

| Dokument / vrstva | Deklarovaný stav | Účinný stav z dodané evidence | Poznámka |
|---|---|---|---|
| závazná právní, smluvní, platformní a bezpečnostní pravidla | nadřazená | účinná podle svého externího zdroje | interní dokument je nesmí oslabit |
| `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` | nejvyšší projektová technická autorita | deklarovaná jako aktuální technický standard; samostatný formální adoption record není v dodané sadě | řídí způsob technické práce, nikoliv živý stav repozitáře |
| přijatá ADR | autorita pro přesný rozsah rozhodnutí | účinná jednotlivě pouze s explicitním accepted/owner záznamem | `PROPOSED` nebo mergnutá ADR není automaticky přijatá |
| mandatory policy, zejména `SECURITY.md` a `docs/governance/DOCUMENTATION_POLICY.md` | povinná pravidla | třída je deklarována; adopci je nutné doložit repozitářem nebo owner záznamem | bezpečnostní pravidla se nesmějí tiše oslabit |
| `PROJECT_CONSTITUTION.md` | cílově nejvyšší inženýrská autorita | **není účinná**; stav `Normative Draft` | po adopci vyžaduje celorepozitářovou reconciliation |
| `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md` | produktová, rozhodovací a delivery ústava | **není účinná**; stav `PROPOSED_FOR_ADOPTION` | adopční podmínky jsou v sekci 22 |
| `GOVERNANCE.md` | mapa | orientační | sama nemění hierarchii |
| architektura, capability inventář, roadmapa a snapshoty | popis a plán | autorita pouze ve svém přesném dokumentovaném rozsahu | nejsou živým Git/runtime důkazem |

Při nejasnosti se použije
`docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`; pokud záznam chybí, stav je `UNKNOWN` nebo
`BLOCKED`, nikoliv domněle `ADOPTED`.

## 3. Cílová hierarchie po adopci `PROJECT_CONSTITUTION.md`

Tato hierarchie je pouze **PROPOSED**, dokud není ústava formálně přijata:

1. závazná externí právní, smluvní, platformní a bezpečnostní pravidla;
2. adoptovaná `PROJECT_CONSTITUTION.md`;
3. přijatá ADR v jejich explicitním rozsahu;
4. adoptované normativní governance standardy;
5. adoptované mandatory policy;
6. schválené postupy a runbooky;
7. implementační a produktová dokumentace;
8. source code a runtime artefakty.

Adopce ústavy musí současně určit vztah k
`WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` a
`VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md`.

## 4. Proměnlivý důkazní stav

- `CURRENT_PRODUCT_STATE.md`
  - datovaný snapshot branch, commitu, worktree, testů, runtime evidence, rizik a dalšího bezpečného
    kroku;
  - není náhradou živých Git příkazů, nově spuštěných testů, CI nebo runtime pozorování.

- `docs/product/CURRENT_CAPABILITIES.md`
  - autoritativní lidsky čitelný capability inventář k uvedenému auditnímu datu a baseline;
  - není autoritou pro pozdější HEAD, worktree, CI, release nebo deployment.

- `ROADMAP.md` a `docs/product/MVP_DELIVERY_MAP.md`
  - plánují pořadí a exit gates;
  - status roadmapy sám nedokazuje implementaci.

## 5. Povinné governance a bezpečnostní dokumenty

- `SECURITY.md`
- `docs/governance/DOCUMENTATION_POLICY.md`
- `docs/architecture/TRUST_BOUNDARIES.md`
- přijatá ADR a verzované kontrakty
- `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md`

## 6. Provozní šablony

- `docs/governance/CHANGE_DECISION_CARD_TEMPLATE.md`
- `docs/governance/MILESTONE_REVIEW_TEMPLATE.md`
- `docs/governance/EXCEPTION_RECORD_TEMPLATE.md`

Šablona nemá normativní autoritu sama o sobě; autoritu získává konkrétní schválený záznam podle
nadřazeného pravidla.

## 7. Řízené provozní postupy

- `docs/governance/REVIEW_BRANCH_PUBLICATION.md`
  - fail-closed publikace přesně ověřeného lokálního `HEAD` do nové GitHub review větve;
  - smí být označen jako schválený mechanismus pouze tehdy, pokud jeho adoption record existuje;
  - nemění `main`, tagy, release, Git remotes ani samotný hook.

## 8. Hlavní filtr změny

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

Když některý bod nebo adopční důkaz chybí, změna se přeformuluje, rozdělí, odloží nebo označí
`BLOCKED`.
