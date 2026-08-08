# VOODOO One 0.9.0-rc2-dev — Security Overview

## Controls implemented

- no hardcoded authentication secret,
- generated local secrets stored outside Git,
- `scrypt` password hashing with per-user salt,
- context-bound v2 sessions signed with a purpose-derived HMAC key,
- database-backed active-session allowlisting with server-side current-session logout,
- HMAC-referenced session storage that excludes bearer tokens and raw nonces,
- explicit identity-provider boundary for password, session and bearer authentication,
- fail-closed startup for configured but unreleased OIDC identity,
- HMAC-keyed, database-backed rate limits for login accounts, login sources and bootstrap attempts,
- ordered, atomic SQLite migrations with immutable SHA-256 history and post-migration integrity checks,
- immutable named application statements with explicit read/write modes and no dynamic service SQL,
- fail-closed statement resolution when a backend dialect is absent or unknown,
- normalized persistence errors that exclude SQL, schema names, credentials and driver diagnostics,
- generic authentication failures with `Retry-After` on temporary lockout,
- structured request/authentication events that exclude bodies, headers, query strings, raw paths, IP addresses and account identifiers,
- validated request correlation IDs returned through `X-Request-ID`,
- exact trusted-host allowlisting with wildcard and scheme rejection,
- strict console/API CSP plus no-store, no-sniff, anti-frame and browser capability headers,
- production-only HSTS and suppressed Uvicorn server headers,
- live account and role validation on every authenticated request,
- permission-based RBAC,
- separation of requester and approver,
- workspace-authoritative environment classification enforced by service checks and database triggers,
- two distinct approvers for production requests,
- production effects disabled by default,
- allowlisted adapters only,
- descriptor-relative sandbox writes with no-follow metadata checks, opened-directory identity verification and bounded artifact size,
- subprocess execution without a shell,
- bounded subprocess output and timeout,
- execution idempotency,
- bounded execution leases with monotonic completion fencing,
- recovery restricted to security reviewers or administrators while emergency stop is active,
- emergency stop,
- hash-chained receipts and audit events,
- database-sequenced receipt ordering independent of timestamps and random IDs,
- non-root read-only Docker runtime with dropped capabilities.

ADR-0007 accepts the pure deterministic execution-contract value objects as representation only.
ADR-0008 and [`../security/ISOLATED_RUNNER_THREAT_MODEL_V1.md`](../security/ISOLATED_RUNNER_THREAT_MODEL_V1.md)
are owner-adopted for the exact isolated Runner design and safety-invariant scope; runtime isolation
controls remain not implemented.

`VOODOO_DATABASE_BACKEND=sqlite` is the only released database mode. Selecting `postgresql` aborts
startup before the service accepts traffic. This prevents a SQLite-specific service layer from being
misrepresented as production-ready PostgreSQL support. The statement catalog has no cross-dialect
fallback, and a future adapter must preserve global write serialization until narrower locking has
independent concurrency proofs.

Sandbox directory traversal does not rely on `O_NOFOLLOW` alone. Every attacker-controlled directory component is inspected without following symlinks, opened descriptor-relatively, inspected again, and then matched by device and inode across all three views. Existing destination symlinks and non-regular files fail closed. The configured sandbox-root path and mutation by other local processes remain operator-owned boundaries; workspace and artifact path components beneath the root are treated as untrusted.

The liveness endpoint performs only constant-time runtime checks. Full audit and receipt-chain
verification is an authenticated evidence operation, preventing chain growth from degrading the
container health probe.

Bearer tokens use version `v2`, fixed issuer and audience claims, bounded claim types and lifetime,
and a signing key derived from the runtime root secret under a session-token-specific context. The
raw root secret is not used directly as the token signing key. Legacy `v1` tokens fail closed after
upgrade, so operators must expect all existing console and API sessions to authenticate again. The
runtime also requires an exact active-session allowlist match, then revalidates active account state
and the current database role on every request. Migration `0007` intentionally invalidates previously
issued stateless sessions.

FastAPI authentication routes now depend on an explicit identity-provider contract. The released
`local` provider owns session issuance and bearer verification while depending on separate canonical
credential-authentication, active-user lookup and session-lifecycle ports. Production composition does not inject the
broad product compatibility facade. OIDC configuration requires exact HTTPS issuer and JWKS
endpoints, audience and distinct identity claim names, but OIDC execution remains unavailable.
Selecting it aborts startup before persistence initialization and never falls back to local
passwords. External groups must not become internal roles until a separate allowlisted mapping and
integration gate are released.

The application derives the authentication source from the ASGI server's client address and does
not parse forwarding headers itself. A production reverse proxy must therefore be configured as a
trusted proxy at the ASGI server boundary; arbitrary client-supplied forwarding headers must not be
trusted.

Supported runtime commands disable Uvicorn's raw access log. The product middleware records only a
route template, method, response status, bounded duration, correlation ID and allowlisted security
metadata. Unexpected exception messages and tracebacks are not emitted by the request logger.

The HTTP boundary rejects unlisted `Host` values before routing. Console actions are registered by
external JavaScript event listeners, so the CSP does not require `unsafe-inline` or `unsafe-eval`.
Production operators must allowlist both the external hostname and any separate internal healthcheck
hostname or address.

The environment stored on a workspace is authoritative. A change request must match it exactly; the
console derives the value instead of accepting a second operator choice. The service revalidates the
join before submit, review and execution, while SQLite triggers prevent direct-write bypass and block
execution of preserved legacy mismatches. This prevents a production workspace from being relabeled
`local` to bypass dual approval or the production-effects gate.

An execution start commits a lease before the adapter runs. Normal completion succeeds only while
the execution remains `RUNNING` with its original fence. After the lease expires, a security reviewer
or administrator may recover it only while emergency stop is active. Recovery records one
`INTERRUPTED` receipt with an `INDETERMINATE` outcome, increments the fence and marks the change
request failed. A late worker may finish its external call, but it cannot overwrite the recovered
database state or append a second receipt. Operators must investigate possible side effects before
creating a new change request; the original idempotency key never triggers an automatic retry.

The manual release-candidate workflow validates its version against the source tree, reruns the full
verification suite, builds and smoke-tests the hardened product image, and emits checksums for both
the source archive and CycloneDX SBOM. These checksums provide integrity, not signer identity. GitHub
artifact attestations for private repositories require GitHub Enterprise Cloud; this private,
user-owned repository must prove that eligibility (or move to an eligible organization) before
`actions/attest@v4` can be made a mandatory fail-closed gate. Until then, no signed-SBOM or provenance
claim is made.

## Required security gates before enterprise release

- external penetration test,
- dependency and container scanning,
- released OIDC/SAML integration with explicit role mapping,
- tenant-specific key management,
- PostgreSQL row-level tenant isolation,
- signed SBOM and artifact provenance,
- security incident and vulnerability disclosure contacts.
