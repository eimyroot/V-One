# VOODOO Governance Map

| Pole | Hodnota |
|---|---|
| Třída dokumentu | Orientační governance mapa |
| Normativní autorita | Žádná; autorita zůstává v účinných dokumentech a explicitně přijatých rozhodnutích |
| Autoritativní adopční záznam | `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md` |
| Aktualizace | Při adopci, zrušení nebo změně autority kteréhokoli governance dokumentu |

> Přítomnost dokumentu v repozitáři, commit, push, pull request nebo merge samy o sobě nejsou adopce.
> Nejasný konflikt autority se řeší fail-closed jako `BLOCKED`.

## Účinný technický standard

1. `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`
   - účinný předchůdce je explicitně owner-adoptovaný a hash-bound;
   - účinný SHA-256 zůstává
     `ed44c6147049887d941b7497f1bce3b817f22b6ae00a5136a27365a2f688d918`;
   - určuje způsob technické práce, ověření, bezpečnosti, DevOps, release a reportování.

## Navržený nástupce technického standardu

- kandidátní revize: `2026-08-06-v3-candidate`;
- stav: `PROPOSED_SUCCESSOR_REVISION`;
- content SHA-256: `36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed`;
- commit ani merge kandidáta nemění jeho stav na `ADOPTED`;
- adopce vyžaduje samostatné owner rozhodnutí nad přesným SHA-256 a kandidátním commitem A;
- pozdější adopční commit B aktualizuje pouze externí register a nevkládá do něj vlastní Git hash.

## Ostatní ústavní dokumenty

- `PROJECT_CONSTITUTION.md`
  - `Normative Draft` / `PROPOSED`;
  - není účinný bez samostatné owner adopce a reconciliation hierarchie.

- `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md`
  - `PROPOSED_FOR_ADOPTION`;
  - není účinný bez splnění vlastních adopčních podmínek.

## Proměnlivý důkazní stav

- `CURRENT_PRODUCT_STATE.md`
  - datovaný snapshot branch, commitu, worktree, testů, runtime evidence, rizik a dalšího bezpečného kroku;
  - není náhradou živého Git stavu, nových testů nebo runtime pozorování.

- `docs/product/CURRENT_CAPABILITIES.md`
  - capability inventář pouze k uvedené baseline;
  - není autoritou pro pozdější HEAD, CI, release nebo deployment.

## Provozní šablony

- `docs/governance/CHANGE_DECISION_CARD_TEMPLATE.md`
- `docs/governance/MILESTONE_REVIEW_TEMPLATE.md`
- `docs/governance/EXCEPTION_RECORD_TEMPLATE.md`

## Řízené provozní postupy

- `docs/governance/REVIEW_BRANCH_PUBLICATION.md`
  - fail-closed publikace přesně ověřeného lokálního `HEAD` do nové GitHub review větve;
  - nemění `main`, tagy, release, Git remotes ani samotný hook.

## Hlavní filtr změny

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
