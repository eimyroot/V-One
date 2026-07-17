# Audit Ledger and Product Composition Boundary

## Status

Implemented as the production runtime composition boundary. The audit ledger is now dependency-cycle-free, but the compatibility `ProductService` still contains its legacy audit methods until the next governed removal step.

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

## Neutral evidence primitives

`evidence_primitives.py` owns the dependency-neutral contracts used to create and hash evidence:

- timezone-aware millisecond UTC timestamps;
- non-guessable prefixed identifiers;
- deterministic canonical JSON encoding;
- SHA-256 chaining over the previous hash and canonical payload.

`AuditLedger` imports these primitives directly and no longer imports `ProductService`. A fixed compatibility vector verifies that canonical JSON and hash output are byte-for-byte identical to the existing stored evidence format.

## Audit guarantees

The ledger uses the canonical statement catalog, preserves the existing `GENESIS`-anchored SHA-256 chain, verifies every hash transition, and remains compatible with audit events produced by existing product operations.

External identity events continue to exclude the raw provider subject. Only its SHA-256 digest appears in responses and audit payloads.

## Compatibility boundary

The older installer and base service remain available for compatibility and focused tests. The production ASGI entrypoint uses the composed installer. System tests enforce route and middleware parity between both installers.

The next governed step may import the neutral primitives and `AuditLedger` into the base service, delegate its audit surface, remove the temporary ledger-backed subclass, and delete the legacy duplicate audit implementation. That step must preserve all public service methods and the stored hash-chain format.

## Explicitly disabled

This boundary does not enable external sign-in, network issuer discovery, public identity-binding management, automatic provisioning, release, deployment, or production effects.
