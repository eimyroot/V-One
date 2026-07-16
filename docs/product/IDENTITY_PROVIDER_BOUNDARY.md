# VOODOO One — Identity Provider Boundary

## Released mode

`VOODOO_IDENTITY_PROVIDER=local` is the only released identity mode. The local provider owns password
verification, v2 session issuance, bearer-token verification and live database revalidation of account
status and role. FastAPI routes depend on the provider contract and do not directly sign or verify
sessions.

Authentication throttling remains an HTTP/service concern because it is bound to both the submitted
account name and the trusted ASGI client source. Successful and failed authentication events continue
to use the existing privacy-preserving observability contract.

## OIDC configuration contract

The configuration model reserves an explicit `oidc` provider with:

- exact HTTPS issuer,
- exact audience,
- exact HTTPS JWKS URL,
- distinct subject, username and groups claim names.

URLs containing credentials, query strings or fragments are rejected. Partial OIDC configuration is
rejected, and OIDC settings are forbidden while the selected provider remains `local`.

Schema v6 and `ExternalIdentityRegistry` now provide the offline binding and authorization data
boundary required by a future OIDC adapter. They enforce immutable issuer/subject-to-user bindings,
append-only exact group-to-role mappings, active-administrator provisioning and current internal-role
confirmation. They do not verify tokens or expose a login flow. The detailed contract is documented in
`docs/product/EXTERNAL_IDENTITY_BINDING.md`.

OIDC verification, discovery/JWKS retrieval, cache policy, key rotation, nonce/state handling,
authorization-code flow, session exchange and logout are not released. Selecting `oidc` therefore
continues to abort startup before the database or product service is initialized. There is no fallback
to local password authentication.

## Future release requirements

A future OIDC adapter must add a separate dependency and security review and prove:

1. issuer, audience, signature, algorithm and time-claim validation,
2. bounded JWKS retrieval with TLS verification, cache expiry and rotation behavior,
3. safe consumption of the existing immutable binding and role-confirmation registry,
4. governed provisioning, deprovisioning and additive revocation evidence,
5. CSRF-safe authorization flow with state, nonce and PKCE,
6. session revocation, logout and incident recovery behavior,
7. integration tests against a controlled identity-provider environment.

No external claim may directly grant an arbitrary VOODOO role. Production effects remain disabled
independently of identity-provider selection.

## Rollback

The provider abstraction and local v2 token format remain source-compatible. Schema v6, however, is a
forward-only migration. Reverting only application source is unsafe if an older binary cannot validate
schema v6. To return to a pre-v6 release, stop every process and restore the complete database, WAL and
SHM backup captured before migration.
