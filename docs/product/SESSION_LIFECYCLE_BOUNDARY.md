# VOODOO One — Session Lifecycle Boundary

## Released behavior

Local bearer sessions are context-bound v2 tokens plus a database-backed active-session allowlist.
Cryptographic verification is necessary but no longer sufficient: every authenticated request must
also match an active row with the same user, issue time and expiry. Missing, expired, revoked or
database-inaccessible session state fails closed.

`SessionLifecycleService` owns registration, lookup and revocation. `LocalIdentityProvider` owns the
token format and composes that service with credential authentication and live user lookup. FastAPI
routes never access session tables directly.

## Stored data and evidence

The `active_sessions` table stores only:

- a purpose-derived HMAC reference to the random token nonce,
- the internal user ID,
- issue and expiry timestamps.

It never stores bearer tokens, signatures or raw nonces. Rows are immutable. Expired rows are removed
during subsequent session issuance; explicit logout deletes only the caller's current row. Session
issue and revoke operations append hash-chained audit events in the same transaction as the allowlist
change. Audit targets contain the HMAC reference, not credential material.

## Upgrade and failure semantics

Migration `0007_active_sessions.sql` creates an empty allowlist. Existing stateless v2 tokens therefore
require re-authentication after upgrade. This is intentional fail-closed behavior and does not require
a token-format change.

- failure to persist a new session means no token is returned;
- failure to read the allowlist rejects authentication;
- a cryptographically valid but unregistered token is rejected;
- logout revokes the server session before returning success;
- the browser clears its local token even if the server cannot be reached and visibly warns the
  operator that server-side revocation could not be confirmed;
- role and active-account checks still run after session validation on every request.

The initial release supports current-session logout. Administrative revoke-all, bounded session
inventory and OIDC back-channel logout remain separate release slices.

## Rollback

Migration `0007` is forward-only. Source rollback is safe only to a binary that tolerates the extra
table, but that older binary would again accept unregistered stateless sessions and is therefore not
an approved security rollback. The preferred rollback is to fix-forward while production effects
remain disabled. If a full binary rollback is unavoidable, stop all writers and restore the complete
pre-migration SQLite backup including WAL/SHM files.
