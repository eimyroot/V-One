# VOODOO One 0.9.0-rc2-dev — Operations Runbook

## Start

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/python -m uvicorn voodoo_product.main:app --host 127.0.0.1 --port 8000
```

## Health

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
```

## Readiness gate

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/python scripts/product_readiness_gate.py
```

## Backup

Stop writes or activate emergency stop, then copy:

```text
storage/product/voodoo_one.sqlite3
storage/product/voodoo_one.sqlite3-wal
storage/product/voodoo_one.sqlite3-shm
storage/product/sandboxes/
.env.product.local
```

The secret file must be encrypted and access-controlled.

## Recovery

1. Stop the process.
2. Restore the database and WAL files as one consistent backup set.
3. Restore `.env.product.local` with mode `0600`.
4. Start the process.
5. Verify `/api/v1/health`.
6. Verify `/api/v1/evidence/verify` as an auditor.

## Emergency stop

Use the System Health screen or:

```text
POST /api/v1/system/emergency-stop
```

with an authorized security reviewer or administrator token and a mandatory reason.
