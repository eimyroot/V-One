# User Account Service Composition Boundary

## Status

Implemented as the canonical active-user lookup and ordinary user creation boundary.

## Purpose

`UserAccountService` owns active-account lookup, ordinary administrator-driven user creation, governed role validation, password hashing and creation audit evidence. `ProductService` preserves the existing public method surface while delegating those operations.

## Runtime composition

`install_composed_product_platform` exposes one shared user account service through `ProductComposition` and `app.state.voodoo_user_account_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Preserved invariants

- only governed roles are accepted;
- stored usernames remain trimmed while the immediate create response remains compatible;
- duplicate usernames fail with the existing error;
- inactive, missing or invalid-role accounts fail closed during bearer revalidation;
- user creation, password hashing and audit evidence remain in the same governed operation;
- existing method signatures, response fields and error behavior remain unchanged;
- `new_id` and password-hasher monkeypatch bridges remain compatible.

Bootstrap user creation and authentication rate limiting remain separate composition boundaries. Password lookup, verification and dummy-hash timing protection belong to `CredentialAuthenticationService`.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, alter bootstrap or login semantics, enable external sign-in, release, deploy or enable production effects.
