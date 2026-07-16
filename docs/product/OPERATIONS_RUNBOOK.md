# VOODOO One 0.9.0-rc2-dev — Operations Runbook

## Start

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/python -m uvicorn voodoo_product.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-server-header
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

## Session token compatibility

The current runtime issues only context-bound `v2` bearer tokens. Deploying this build invalidates all
legacy `v1` sessions by design; users must authenticate again after the upgrade. Do not add a silent
`v1` verification fallback. The token signing key is derived from
`VOODOO_SESSION_SIGNING_SECRET`, so rotating that secret also invalidates every current token and must
be coordinated with operator access, emergency-stop state and the encrypted secret backup.

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

## HTTP trust boundary

`VOODOO_TRUSTED_HOSTS` is a comma-separated allowlist of exact lowercase hostnames or IPv4
addresses. Schemes, ports, wildcards, duplicates and empty lists are rejected at startup. The
application ignores the request port during matching. For a container behind
`control.example.com`, retain the internal healthcheck address explicitly:

```text
VOODOO_TRUSTED_HOSTS=control.example.com,127.0.0.1
```

Requests with any other `Host` receive HTTP `400` before routing. Do not use a catch-all host to make
a deployment pass. Configure DNS and the reverse proxy first, then add only the intended public and
internal healthcheck names.

All responses disable storage and add no-sniff, frame, referrer, permissions and cross-origin
isolation headers. The console and API use a strict Content Security Policy without inline scripts,
inline styles or eval. `VOODOO_ENV=production` additionally enables one-year HSTS; use that environment
only behind correctly terminated HTTPS. Supported Uvicorn commands disable both access and server
headers.

## Readiness gate

```bash
set -a
. ./.env.product.local
set +a
.venv/bin/python scripts/product_readiness_gate.py
```

## Release-candidate build

The `release-candidate` workflow runs only for `main`, accepts only the release candidate encoded in
the source tree and requires the exact `BUILD_RC` confirmation. It does not deploy, publish an image
or enable production effects. From any authenticated GitHub CLI working directory, dispatch the
current candidate with:

```bash
gh workflow run release-candidate.yml --repo nulleimy/V-One --ref main \
  -f version=0.9.0-rc2 -f confirmation=BUILD_RC
```

After the gated run succeeds, download and verify its archive and CycloneDX SBOM in a new temporary
directory. Replace `RUN_ID` with the successful workflow run ID:

```bash
mkdir -p /tmp/v-one-rc-verify
cd /tmp/v-one-rc-verify
gh run download RUN_ID --repo nulleimy/V-One --name v-one-0.9.0-rc2 --dir .
sha256sum --check SHA256SUMS.txt
```

The checksum proves internal bundle integrity after download; it is not an authenticity signature.
Do not promote this candidate as an enterprise release until signed SBOM and build-provenance
attestations are generated and independently verified.

## Database migrations

SQLite migrations run automatically and atomically before the application starts accepting traffic.
The health response must report `database_backend: sqlite` and `schema_version: 5`. Never edit an
applied migration: its SHA-256 checksum is part of the database history and drift blocks startup.
Database unavailability or migration-history drift returns HTTP `503`, which makes the container
healthcheck fail instead of reporting a false-positive HTTP success.

For an upgrade:

1. Activate emergency stop.
2. Verify `/api/v1/evidence/verify` reports valid receipt and audit chains; stop the upgrade and
   investigate if either chain is invalid.
3. Stop every application process so that no writer remains.
4. Copy the database, `-wal` and `-shm` files as one consistent backup set.
5. Deploy the new immutable application artifact while keeping production effects disabled.
6. Start exactly one instance and wait for migration completion.
7. Verify `/api/v1/health` reports `HEALTHY`, `sqlite`, schema version `5`, and production effects
   `DISABLED`.
8. Run the authenticated `/api/v1/evidence/verify` operation again, then start the remaining
   instances.

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

## Interrupted execution recovery

Never retry an expired `RUNNING` execution automatically: its adapter may already have produced a
side effect. First investigate the worker and target system. Then activate emergency stop and use a
current security-reviewer or administrator token from the operator workstation.

The default adapter timeout is 120 seconds and the lease is 180 seconds. Keep
`VOODOO_EXECUTION_LEASE_SECONDS` at least 30 seconds above
`VOODOO_EXECUTION_TIMEOUT_SECONDS`, and configure the orchestrator termination grace above the
execution timeout. The supplied Compose deployment waits 150 seconds before a forced stop.

After confirming those preconditions, run:

```bash
export VOODOO_URL=http://127.0.0.1:8000
export EXECUTION_ID=exec_REPLACE_ME
curl --fail-with-body --silent --show-error \
  --request POST "$VOODOO_URL/api/v1/executions/$EXECUTION_ID/recover" \
  --header "Authorization: Bearer $VOODOO_RECOVERY_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"reason":"worker terminated after durable execution start; outcome investigated"}'
```

The endpoint rejects an active lease, inactive emergency stop, non-running execution or unauthorized
role. A successful recovery returns `INTERRUPTED`, records `INDETERMINATE` evidence and permanently
fences the late worker. Verify both evidence chains and inspect the target system before clearing
emergency stop. If the operation must be attempted again, create and approve a new change request
with a new idempotency key; never edit the recovered row.

## Emergency stop

Use the System Health screen or:

```text
POST /api/v1/system/emergency-stop
```

with an authorized security reviewer or administrator token and a mandatory reason.
