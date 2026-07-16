# Changelog

## 0.9.0-rc2-dev — unreleased

- Established a clean, review-gated repository baseline from the verified RC1 artifact.
- Pinned runtime and development dependency graphs with hashes.
- Added least-privilege CI and a manually gated release-candidate build.
- Revalidated active account and current role on every authenticated request.
- Hardened sandbox writes against symlink traversal and partial writes.
- Added change-payload, artifact, token-header and idempotency-key bounds.
- Reduced the default session lifetime from eight hours to one hour.
- Separated constant-time liveness from explicit evidence-chain verification.
- Expanded system/security coverage from 10 to 14 tests.
- Added persistent account/source login throttling and bootstrap-token throttling with bounded lockout recovery.
- Reduced account-enumeration timing differences by verifying unknown users against a dummy password hash.
- Added correlated JSON request and authentication security events with an explicit field allowlist.
- Disabled raw Uvicorn access logs in supported start commands to prevent duplicate IP/URL logging.
- Made CI and release vulnerability audits consume the fully hashed lock without implicit pip resolution.
- Replaced implicit SQLite schema creation with ordered, atomic migrations recorded with SHA-256 checksums.
- Added schema, index and integrity validation plus a fail-closed startup boundary for unreleased PostgreSQL support.
- Made database-unavailable health responses return HTTP 503 for correct orchestrator detection.
- Isolated backend connections and errors behind a tested persistence protocol without enabling PostgreSQL.
- Closed bounded database connections deterministically and hardened concurrent SQLite WAL startup.
- Centralized all application SQL in an immutable, classified statement catalog with no dynamic service SQL.
- Added fail-closed per-dialect statement selection while keeping PostgreSQL and production effects disabled.
- Added exact trusted-host enforcement and production-only HSTS at the HTTP boundary.
- Added strict CSP-compatible console actions and explicit no-store/browser security headers.
