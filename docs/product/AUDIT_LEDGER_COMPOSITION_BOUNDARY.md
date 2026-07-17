# Audit Ledger and Product Composition Boundary

## Status

Implemented as the production runtime composition boundary. This change does not add public identity-management routes.

## Purpose

`LedgerBackedProductService` preserves the existing product service interface while delegating audit append, list, and verification operations to one reusable `AuditLedger` instance.

## Runtime composition

`install_composed_product_platform` creates:

- one ledger-backed product service;
- one audit ledger owned by that service;
- one governed external identity service using the same database and ledger;
- one immutable `ProductComposition` containing those components.

The components are stored on `app.state` for internal dependency access. The identity lifecycle service is not attached to a router.

## Delegation contract

The production service overrides only the audit surface:

- `_append_audit` delegates to `AuditLedger.append` inside the caller transaction;
- `list_audit_events` delegates to the bounded ledger reader;
- `verify_audit_chain` delegates to the ledger verifier.

The ledger-backed service contains no direct SQL execution. All other product behavior remains inherited from `ProductService`.

## Audit guarantees

The ledger uses the canonical statement catalog, preserves the existing `GENESIS`-anchored SHA-256 chain, verifies every hash transition, and remains compatible with audit events produced by existing product operations.

External identity events continue to exclude the raw provider subject. Only its SHA-256 digest appears in responses and audit payloads.

## Compatibility boundary

The older installer and base service remain available for compatibility and focused tests. The production ASGI entrypoint uses the composed installer. System tests enforce route and middleware parity between both installers.

The duplicate audit implementation in the base class is not used by production composition. Its later removal requires a neutral-helper refactor that avoids circular imports and preserves existing consumers.

## Explicitly disabled

This boundary does not enable external sign-in, network issuer discovery, public identity-binding management, automatic provisioning, release, deployment, or production effects.
