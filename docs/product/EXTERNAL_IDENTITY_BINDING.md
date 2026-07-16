# VOODOO One — External Identity Binding Boundary

## Purpose

This boundary prepares enterprise identity without enabling network OIDC authentication. It stores an
immutable relationship between one verified external principal and one existing internal VOODOO user:

```text
provider + exact issuer + case-sensitive subject -> internal user_id
```

A second append-only table allowlists exact external group strings to existing internal roles. External
claims never create users, change roles or grant permissions directly.

## Schema-v6 contract

Migration `0006_external_identity_bindings.sql` adds:

- `external_identity_bindings`, unique by `(provider, issuer, subject)`,
- a second uniqueness boundary on `(provider, issuer, user_id)`,
- `external_role_mappings`, unique by `(provider, issuer, external_group)`,
- explicit lookup indexes,
- insert triggers requiring an active administrator in `created_by`,
- an insert trigger requiring the bound internal user to be active,
- update and delete denial triggers for both tables.

Only provider `oidc` is accepted. Issuers are exact absolute HTTPS URLs without credentials, query
strings or fragments. Subjects and groups are bounded, reject control characters and retain their
case-sensitive identity-provider semantics.

The rows are append-only evidence. Deprovisioning currently occurs by disabling the internal user;
resolution rechecks the active flag every time. A future revocation model must be additive and audited,
not an in-place rewrite of historical identity evidence.

## Provisioning authorization

`ExternalIdentityRegistry` requires an active internal `administrator` before creating either a binding
or a role mapping. SQLite independently enforces the same creator rule so direct database writes cannot
bypass the Python boundary. A binding also requires an existing active internal user with a known role.

No HTTP route exposes these methods in this release. A future operator workflow must place provisioning
behind governed change requests, approvals and hash-chained audit evidence before customer use.

## Resolution algorithm

`ExternalIdentityClaims` is a post-verification data contract. It accepts one provider, exact issuer,
case-sensitive subject and an immutable tuple of 1–64 unique groups.

Resolution succeeds only when all of the following hold:

1. the exact provider, issuer and subject binding exists,
2. the bound internal user is still active and has a known role,
3. at least one presented group has an immutable allowlisted mapping,
4. every mapped group converges to one role,
5. that mapped role exactly equals the user's current internal database role.

Unmapped groups are ignored and grant nothing. No mapped group, a role mismatch or multiple mapped
roles fails closed. This means an external `administrator`-like claim cannot elevate a user whose
current internal role is `developer`.

## Deliberately unavailable

This slice does not implement:

- JWT signature or algorithm verification,
- discovery or JWKS retrieval and rotation,
- authorization-code flow, state, nonce or PKCE,
- user auto-provisioning,
- group synchronization,
- logout, revocation or session exchange,
- HTTP or console management endpoints.

`VOODOO_IDENTITY_PROVIDER=oidc` therefore continues to abort startup before persistence initialization.
The registry cannot be reached through the released product API.

## Rollback

Schema v6 has no down migration. Before deploying it, back up the SQLite database, WAL and SHM files as
one consistent set. Source rollback is safe only when the older binary is not started against a schema-v6
database. To return to an older release, stop all processes and restore the complete pre-v6 backup.
Never delete the new tables, rewrite migration checksums or decrement `PRAGMA user_version`.
