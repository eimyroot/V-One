# VOODOO One 0.9.0-rc2-dev — Security Overview

## Controls implemented

- no hardcoded authentication secret,
- generated local secrets stored outside Git,
- `scrypt` password hashing with per-user salt,
- HMAC-signed expiring sessions,
- HMAC-keyed, database-backed rate limits for login accounts, login sources and bootstrap attempts,
- ordered, atomic SQLite migrations with immutable SHA-256 history and post-migration integrity checks,
- generic authentication failures with `Retry-After` on temporary lockout,
- structured request/authentication events that exclude bodies, headers, query strings, raw paths, IP addresses and account identifiers,
- validated request correlation IDs returned through `X-Request-ID`,
- live account and role validation on every authenticated request,
- permission-based RBAC,
- separation of requester and approver,
- two distinct approvers for production requests,
- production effects disabled by default,
- allowlisted adapters only,
- descriptor-relative, no-symlink sandbox writes with bounded artifact size,
- subprocess execution without a shell,
- bounded subprocess output and timeout,
- execution idempotency,
- emergency stop,
- hash-chained receipts and audit events,
- non-root read-only Docker runtime with dropped capabilities.

`VOODOO_DATABASE_BACKEND=sqlite` is the only released database mode. Selecting `postgresql` aborts
startup before the service accepts traffic. This prevents a SQLite-specific service layer from being
misrepresented as production-ready PostgreSQL support.

The liveness endpoint performs only constant-time runtime checks. Full audit and receipt-chain
verification is an authenticated evidence operation, preventing chain growth from degrading the
container health probe.

The application derives the authentication source from the ASGI server's client address and does
not parse forwarding headers itself. A production reverse proxy must therefore be configured as a
trusted proxy at the ASGI server boundary; arbitrary client-supplied forwarding headers must not be
trusted.

Supported runtime commands disable Uvicorn's raw access log. The product middleware records only a
route template, method, response status, bounded duration, correlation ID and allowlisted security
metadata. Unexpected exception messages and tracebacks are not emitted by the request logger.

## Required security gates before enterprise release

- external penetration test,
- dependency and container scanning,
- OIDC/SAML integration,
- tenant-specific key management,
- PostgreSQL row-level tenant isolation,
- signed SBOM and artifact provenance,
- security incident and vulnerability disclosure contacts.
