# VOODOO One RC1 — Security Overview

## Controls implemented

- no hardcoded authentication secret,
- generated local secrets stored outside Git,
- `scrypt` password hashing with per-user salt,
- HMAC-signed expiring sessions,
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

The liveness endpoint performs only constant-time runtime checks. Full audit and receipt-chain
verification is an authenticated evidence operation, preventing chain growth from degrading the
container health probe.

## Required security gates before enterprise release

- external penetration test,
- dependency and container scanning,
- OIDC/SAML integration,
- tenant-specific key management,
- PostgreSQL row-level tenant isolation,
- signed SBOM and artifact provenance,
- security incident and vulnerability disclosure contacts.
