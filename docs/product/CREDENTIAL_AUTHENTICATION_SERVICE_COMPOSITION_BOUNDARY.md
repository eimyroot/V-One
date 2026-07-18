# Credential Authentication Service Composition Boundary

## Status

Implemented as the canonical database-bound local password authentication boundary.

## Purpose

`CredentialAuthenticationService` owns local username lookup, constant-work dummy-hash protection, password verification and the generic credential decision. `ProductService` preserves the existing public `authenticate` surface while delegating the operation.

## Runtime composition

`install_composed_product_platform` exposes one shared credential authentication service through `ProductComposition` and `app.state.voodoo_credential_authentication_service`.

The service uses the exact product database instance. A mismatched injected service fails closed during construction.

## Preserved invariants

- usernames are trimmed before lookup;
- missing accounts still execute password verification against a process-local dummy hash;
- missing, inactive and invalid-password accounts return the same `invalid credentials` error;
- password hashes and raw passwords are never returned;
- the established `ProductService.authenticate` signature and response fields remain compatible;
- the dynamic password-verifier monkeypatch bridge remains compatible;
- all database operations use the central statement catalog;
- `ProductService` no longer executes database statements directly.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not issue sessions, validate bearer tokens, own roles or permissions, apply rate limits, authorize bootstrap, enable OIDC, add routes, release, deploy or enable production effects.
