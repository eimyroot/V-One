# V-One / VOODOO One

Governed operations control plane for the flow:

`change request → independent approval → controlled execution → evidence`

## Current release state

The repository is a hardened development baseline derived from `VOODOO One 0.9.0-rc1`.
Production effects are disabled by default. The current code is approved for local integration,
verification and controlled pilot hardening; it is not yet an unrestricted production release.

## Local verification

Working directory: repository root.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m ruff check .
python -m compileall -q voodoo_product scripts tests
python -m pytest -q
python scripts/product_readiness_gate.py
```

## Local checkpoint evidence verification

The first ProofGraph slice verifies an existing checkpoint without changing product or runtime
state:

```bash
export PATH="$PWD/scripts:$PATH"
voodoo evidence verify /absolute/path/to/checkpoint
```

The equivalent module command is:

```bash
python -m voodoo_product evidence verify /absolute/path/to/checkpoint
```

The command emits JSON and exits non-zero when the outer manifest, provenance, Git bundle, source
tree, source archive or runtime identity is inconsistent. It does not verify a remote Drive copy,
contact Docker, publish an artifact or authorize a release.

See `docs/adr/ADR-0002-local-checkpoint-proofgraph-verification.md`.

## Local start

Create `.env.product.local` from `.env.product.example`, replace both secret placeholders with
cryptographically random values, set `VOODOO_TRUSTED_HOSTS` to the exact accepted hostnames, keep
`VOODOO_ALLOW_PRODUCTION_EFFECTS=false`, then run:

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/uvicorn voodoo_product.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-server-header
```

Console: `http://127.0.0.1:8000/console`

## Change governance

- All changes go through pull requests.
- `CODEOWNERS` assigns final review to `@nulleimy`.
- CI is read-only and must pass before merge.
- Release candidates are built only through a manually dispatched, environment-gated workflow.
- Authentication, authorization, persistence, production effects and release workflows always
  require explicit owner review; they are never self-approved by automation.

See `SECURITY.md`, `CONTRIBUTING.md` and `docs/product/COMMERCIAL_READINESS.md`.
