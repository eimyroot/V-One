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
