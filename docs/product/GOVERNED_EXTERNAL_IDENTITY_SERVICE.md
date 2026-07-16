# Governed External Identity Service

## Status

This component is released for internal identity-binding lifecycle operations only. It creates, resolves, and disables records in the immutable external identity binding boundary.

It exposes no HTTP route and does not activate the unreleased external identity provider.

## Authorization

Each mutation validates current database state inside the same transaction as the mutation and audit event.

- The actor must be active and currently hold the `administrator` role.
- The target user must exist, be active, and hold a recognized internal role.
- An administrator cannot create or disable their own binding.
- Administrator binding lifecycle therefore requires a different active administrator.
- Route-layer permissions are not accepted as the only authorization control.

## Creation

Creation validates the exact provider, issuer, and subject identity key, then writes the binding through the dedicated statement catalog.

The transaction also appends a tamper-evident audit event. Service responses and audit payloads contain a subject digest rather than the raw external subject.

Database constraints prevent reassignment of an existing subject and prevent multiple subjects for the same internal user at one issuer.

## Resolution

Resolution succeeds only when the exact binding exists, the binding is active, the internal user remains active, and the current role is recognized. Every other state fails closed.

Resolution does not authenticate an external credential. A future provider must complete its own cryptographic validation before using the issuer and subject lookup.

## Disablement

Disablement is non-destructive and one-way.

- Identity fields and internal ownership remain immutable.
- The disabled timestamp and audit event are committed atomically.
- Repeated disablement fails closed.
- Database triggers continue to prohibit deletion and reactivation.

Disabled records remain durable security evidence.

## Not released

- public binding-management endpoints,
- external authentication routes,
- automatic account creation,
- external assignment of the administrator role,
- binding reassignment or recovery,
- network communication with an external identity system,
- release or deployment changes.
