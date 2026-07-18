# Authentication Rate-Limit Service Composition Boundary

## Status

Implemented as the canonical database-bound authentication throttling state boundary.

## Purpose

`AuthenticationRateLimitService` owns login and bootstrap rate-limit key derivation, persistent counters, expiry cleanup, lockout calculation and clearing. `ProductService` preserves the existing public method surface while delegating all six rate-limit operations.

Password lookup, dummy-hash timing protection and password verification belong to `CredentialAuthenticationService`. Bootstrap authorization and session identity remain separate boundaries.

## Runtime composition

`install_composed_product_platform` exposes one shared authentication rate-limit service through `ProductComposition` and `app.state.voodoo_authentication_rate_limit_service`.

The service uses the exact product database and configuration instances. Composition mismatches fail closed.

## Preserved invariants

- account and source throttles remain separate;
- bootstrap throttling remains source-bound;
- normalized identities are HMAC-SHA256 hashed before storage;
- raw usernames and client sources are not persisted in rate-limit keys;
- counters, lockouts and cleanup remain transactionally consistent;
- concurrent failures remain atomically counted;
- successful authentication clears both account and source state;
- expired windows and lockouts are removed during enforcement;
- `AuthRateLimitExceeded` identity, message and `retry_after` behavior remain compatible;
- existing routes, HTTP 429 responses and `Retry-After` headers remain unchanged;
- dynamic `time.time` monkeypatch compatibility is preserved.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not change passwords, identity-provider behavior, bootstrap authorization, permissions, routes, external sign-in, release, deployment or production effects.
