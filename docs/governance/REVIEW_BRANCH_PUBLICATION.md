# Governed GitHub Review Branch Publication

## Účel

Tento postup publikuje přesně ověřený lokální `HEAD` jako **novou review větev** na povoleném GitHub repozitáři. Nemění `main`, tagy, release, Git remotes ani lokální `pre-push` hook.

Standardní local-only ochrana zůstává aktivní. Jednorázové obejití hooku pomocí `--no-verify` je povoleno pouze uvnitř auditovaného skriptu `scripts/publish_review_branch.py` po splnění všech fail-closed kontrol.

## Bezpečnostní invarianty

Skript odmítne pokračovat, pokud:

- pracovní strom není čistý,
- `HEAD` neodpovídá explicitnímu úplnému SHA,
- neprojde SHA-256 kontrola obou kanonických ústav,
- `origin` fetch URL není přesně `https://github.com/nulleimy/V-One.git`,
- cílová větev nezačíná `review/`,
- cílová větev je chráněná nebo má neplatný Git ref,
- `HEAD` není potomkem zadaného base refu,
- počet commitů neodpovídá explicitnímu očekávání,
- rozsah obsahuje merge commit,
- `git diff --check` selže,
- cílová vzdálená větev již existuje,
- dry-run push selže,
- chybí přesná autorizační věta,
- vzdálené SHA po publikaci neodpovídá publikovanému `HEAD`.

Skript nepoužívá force push a nemění konfiguraci repozitáře.

## Fáze 1 — ověřený plán bez vzdálené změny

```bash
set -euo pipefail
cd /Users/eimyna/V-ONE

git fetch --prune origin

EXPECTED_HEAD="$(git rev-parse HEAD)"
EXPECTED_COMMIT_COUNT="$(git rev-list --count origin/main..HEAD)"
TARGET_BRANCH="review/admin-session-revocation-v1-20260719-051330"

printf 'EXPECTED_HEAD=%s\n' "$EXPECTED_HEAD"
printf 'EXPECTED_COMMIT_COUNT=%s\n' "$EXPECTED_COMMIT_COUNT"

.venv/bin/python scripts/publish_review_branch.py \
  --expected-head "$EXPECTED_HEAD" \
  --expected-commit-count "$EXPECTED_COMMIT_COUNT" \
  --target-branch "$TARGET_BRANCH"
```

Očekávaný stav:

```text
PUBLICATION_STATUS=VERIFIED_PLAN
REQUIRED_APPROVAL=PUBLISH_REVIEW HEAD=... REPOSITORY=... BRANCH=... COMMITS=...
```

Tato fáze provede fetch, lokální kontroly, kontrolu kolize a `git push --dry-run --no-verify`. Nevytvoří vzdálenou větev.

## Fáze 2 — explicitně autorizovaná publikace

Použij přesnou hodnotu vypsanou jako `REQUIRED_APPROVAL`:

```bash
set -euo pipefail
cd /Users/eimyna/V-ONE

EXPECTED_HEAD='<exact HEAD from the verified plan>'
EXPECTED_COMMIT_COUNT='<exact commit count from the verified plan>'
TARGET_BRANCH='review/admin-session-revocation-v1-20260719-051330'
APPROVAL='<exact REQUIRED_APPROVAL value from the verified plan>'

.venv/bin/python scripts/publish_review_branch.py \
  --expected-head "$EXPECTED_HEAD" \
  --expected-commit-count "$EXPECTED_COMMIT_COUNT" \
  --target-branch "$TARGET_BRANCH" \
  --execute \
  --approval "$APPROVAL"
```

Úspěch musí skončit:

```text
PUBLICATION_STATUS=IMPLEMENTED_VERIFIED_REMOTE_BRANCH
REMOTE_SHA=<stejné SHA jako expected-head>
```

## Evidence

Každý plán i pokus o publikaci vytvoří lokální JSON evidence soubor a SHA-256 sidecar v:

```text
~/Downloads/voodoo-review-publication-evidence
```

Evidence nesmí obsahovat přístupové tokeny ani jiné secrets.

## Rollback

Publikace nemění lokální historii. Odstranění vzdálené review větve je samostatná destruktivní operace a vyžaduje explicitní povolení vlastníka, kontrolu přesného vzdáleného SHA a samostatný auditní záznam.
