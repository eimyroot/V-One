# V-ONE Product Mirror Policy

## Canonical source

`eimyroot/V-One` → branch `main` → path `docs/product`

Historical references to `nulleimy/V-One` currently resolve to the same GitHub repository identity, but
new mirror metadata must record the canonical owner/name returned by GitHub: `eimyroot/V-One`.
Redirect compatibility must not be treated as a second source of truth.

## Mirror model

This CASER folder is a **live logical mirror**, not an independently editable canonical copy.

- Reads should resolve against the canonical GitHub product path whenever current truth matters.
- CASER may store mirror metadata, snapshots, evidence, indexes, and working artifacts.
- Every snapshot must record the exact Git commit SHA it represents.
- Stale snapshots must never override newer GitHub state.
- CASER-only edits do not change the canonical repository.
- Repository mutations remain explicitly scoped operations.

## Truth invariant

`GITHUB CANONICAL STATE > CASER MIRROR SNAPSHOT > HISTORICAL/HANDOFF CONTEXT`

## Safety invariant

`PROJECT IDENTITY != EXECUTION AUTHORITY`
