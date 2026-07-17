# Workspace Service Composition Boundary

## Status

Implemented as the canonical ordinary workspace lifecycle boundary.

## Purpose

`WorkspaceService` owns workspace listing, ordinary workspace creation, environment validation and creation audit evidence. `ProductService` preserves the existing public method surface while delegating those operations.

## Runtime composition

`install_composed_product_platform` exposes one shared workspace service through `ProductComposition` and `app.state.voodoo_workspace_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Preserved invariants

- only governed environments are accepted;
- stored workspace names remain trimmed while the immediate create response remains compatible;
- workspace creation and audit evidence remain in the same transaction;
- existing method signatures, response fields, ordering and error behavior remain unchanged;
- `new_id` and `utc_now` monkeypatch bridges remain compatible.

Bootstrap workspace creation intentionally remains in `ProductService` because bootstrap atomically creates the first administrator, initial workspace and `system.bootstrap` audit evidence.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, alter change-request or execution semantics, enable external sign-in, release, deploy or enable production effects.
