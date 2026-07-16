# External Identity Binding Boundary

## Status

This boundary is **released only as a persistence and authorization contract**.

External OIDC login, token verification, JWKS retrieval, automatic account provisioning, and public binding management remain disabled. Selecting `VOODOO_IDENTITY_PROVIDER=oidc` still aborts startup before database initialization.

## Identity key

An external identity is identified by the exact tuple:

- provider: `oidc`
- issuer: canonical absolute HTTPS issuer URL
- subject: the stable issuer-local subject claim

The tuple is bound to one immutable internal `users.id`. For a given provider and issuer, one internal user can have at most one external subject.

Display names, email addresses, usernames, and group names are not identity keys and must never be used to relink an account.

## Persistence invariants

Migration `0006_external_identity_bindings.sql` provides:

- unique `(provider, issuer, subject)` identity binding,
- unique `(provider, issuer, user_id)` reverse binding,
- foreign-key ownership by an existing internal user,
- immutable provider, issuer, subject, and user identifier,
- non-destructive one-way disablement,
- deletion and reactivation denial,
- lifecycle consistency between `active` and `disabled_at`.

A disabled binding remains as durable security evidence. Rebinding requires a new governed recovery process; it cannot be accomplished by updating or deleting the original record.

## Role mapping invariants

External groups may grant only explicitly allowlisted internal roles.

- `administrator` cannot be granted by an external group.
- Unknown groups grant no role.
- Multiple matched groups that resolve to different roles fail closed as ambiguous.
- Duplicate group mapping definitions are rejected.
- No arbitrary external claim value may be interpreted as an internal role.

## Not yet released

A future OIDC integration must separately implement and gate:

1. signature, issuer, audience, algorithm, and time-claim verification,
2. bounded TLS-only JWKS retrieval, caching, and rotation,
3. explicit binding creation and recovery approvals,
4. provisioning and deprovisioning workflows,
5. state, nonce, and PKCE validation where applicable,
6. logout, revocation, incident response, and audit receipts,
7. controlled integration tests against supported identity providers.

Until those controls are released, this boundary stores no external login state and exposes no public management API.
