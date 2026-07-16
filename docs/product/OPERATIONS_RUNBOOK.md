# VOODOO One 0.9.0-rc2-dev — Operations Runbook

## Start

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/python -m uvicorn voodoo_product.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

## Health

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
```

## Authentication throttling

The default policy allows five failures per account and twenty failures per source within five
minutes, followed by a fifteen-minute lockout. Bootstrap-token failures use the account threshold.
Configure the policy only through:

```text
VOODOO_AUTH_MAX_FAILURES
VOODOO_AUTH_SOURCE_MAX_FAILURES
VOODOO_AUTH_WINDOW_SECONDS
VOODOO_AUTH_LOCKOUT_SECONDS
```

Rate-limit identifiers are HMAC-keyed before persistence. Do not delete `auth_rate_limits` during an
incident or routine restart. Emergency recovery requires an audited database change while writes are
stopped; changing the session-signing secret also changes identifier derivation and must follow the
secret-rotation runbook once that procedure is released.

## Structured request logs

Application request and authentication-security events are emitted as one-line JSON to stdout. Set
the minimum application level with `VOODOO_LOG_LEVEL`; accepted values are `DEBUG`, `INFO`,
`WARNING`, `ERROR` and `CRITICAL`.

Every HTTP response includes `X-Request-ID`. A caller-provided value is accepted only when it contains
8–128 allowlisted ASCII characters; otherwise the server generates a 32-character identifier. Logs
contain the matched route template and never the raw path or query string.

Do not remove `--no-access-log` from supported Uvicorn start commands. Log retention, transport,
access control and alerting belong to the deployment platform and must preserve the JSON record
without enriching it with raw authorization headers, request bodies or client addresses.

## Readiness gate

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/python scripts/product_readiness_gate.py
```

## Database migrations

SQLite migrations run automatically and atomically before the application starts accepting traffic.
The health response must report `database_backend: sqlite` and `schema_version: 2`. Never edit an
applied migration: its SHA-256 checksum is part of the database history and drift blocks startup.
Database unavailability or migration-history drift returns HTTP `503`, which makes the container
healthcheck fail instead of reporting a false-positive HTTP success.

For an upgrade:

1. Activate emergency stop and stop every application process so that no writer remains.
2. Copy the database, `-wal` and `-shm` files as one consistent backup set.
3. Deploy the new immutable application artifact while keeping production effects disabled.
4. Start exactly one instance and wait for migration completion.
5. Verify `/api/v1/health` reports `HEALTHY`, `sqlite`, schema version `2`, and production effects
   `DISABLED`.
6. Run the authenticated `/api/v1/evidence/verify` operation, then start the remaining instances.

Migrations are forward-only. Rolling back application code does not downgrade the database. Use the
pre-migration backup if the previous binary cannot operate against the new schema. The complete
contract and failure handling are documented in `docs/product/DATABASE_MIGRATIONS.md`.

## Backup

Stop every application process after activating emergency stop, then copy:

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
