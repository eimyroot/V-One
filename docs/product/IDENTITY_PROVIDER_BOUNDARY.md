# VOODOO One — Identity Provider Boundary

## Released mode

`VOODOO_IDENTITY_PROVIDER=local` is the only released identity mode. The local provider owns v2
session issuance and bearer-token verification. It depends on three least-privilege ports:
`CredentialAuthenticationService` for password decisions and `UserAccountService` for live account
and role revalidation, plus `SessionLifecycleService` for persistent allowlisting and revocation.
Production composition never injects the broad `ProductService` compatibility facade. FastAPI routes
depend on the provider contract and do not directly sign, verify or persist sessions.

The previous combined `IdentityService` input remains accepted only as a compatibility path. Mixing
that input with either explicit port, or configuring only one explicit port, fails closed.

Authentication throttling remains an HTTP/service concern because it is bound to both the submitted
account name and the trusted ASGI client source. Successful and failed authentication events continue
to use the existing privacy-preserving observability contract.

## OIDC contract

The configuration model reserves an explicit `oidc` provider with:

- exact HTTPS issuer,
- exact audience,
- exact HTTPS JWKS URL,
- distinct subject, username and groups claim names.

URLs containing credentials, query strings or fragments are rejected. Partial OIDC configuration is
rejected, and OIDC settings are forbidden while the selected provider remains `local`.

OIDC verification, JWKS retrieval, cache policy, key rotation, nonce/state handling, authorization-code
flow, logout and external-group-to-internal-role mapping are not released. Selecting `oidc` therefore
aborts startup before the database or product service is initialized. There is no fallback to local
password authentication.

## Future release requirements

A future OIDC adapter must add a separate dependency and security review and prove:

1. issuer, audience, signature, algorithm and time-claim validation,
2. bounded JWKS retrieval with TLS verification, cache expiry and rotation behavior,
3. explicit allowlisted mapping from external groups to existing internal roles,
4. account provisioning/deprovisioning and immutable external subject binding,
5. CSRF-safe authorization flow with state, nonce and PKCE,
6. session revocation, logout and incident recovery behavior,
7. integration tests against a controlled identity-provider environment.

No external claim may directly grant an arbitrary VOODOO role. Production effects remain disabled
independently of identity-provider selection.

## Rollback

The token format and signing context remain v2-compatible, but migration `0007` deliberately starts
with an empty active-session allowlist. Operators must sign in again after upgrade. The migration is
forward-only; the approved rollback is fix-forward or restoration of the complete pre-migration
SQLite backup as described in `SESSION_LIFECYCLE_BOUNDARY.md`.
