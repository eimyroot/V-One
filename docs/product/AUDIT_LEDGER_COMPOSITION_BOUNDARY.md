# Audit Ledger and Product Composition Boundary

## Status

Implemented as the canonical product audit boundary. `ProductService` now owns and delegates to one reusable `AuditLedger`; the temporary ledger-backed subclass and duplicate audit implementation have been removed.

## Purpose

Every product operation, governed external identity operation, audit reader, and audit verifier must share one database-bound ledger implementation without changing the public service interface or stored evidence format.

## Runtime composition

`install_composed_product_platform` creates:

- one canonical `ProductService`;
- one audit ledger owned by that service;
- one governed external identity service using the same database and ledger;
- one immutable `ProductComposition` containing those components.

The components are stored on `app.state` for internal dependency access. The identity lifecycle service is not attached to a router.

## Delegation contract

`ProductService` preserves all existing methods while delegating its audit surface:

- `_append_audit` delegates to `AuditLedger.append` inside the caller transaction;
- `list_audit_events` delegates to the bounded ledger reader;
- `verify_audit_chain` delegates to the ledger verifier.

The service contains no direct audit SQL statements. Constructor injection is permitted only when the supplied ledger is bound to the exact same database adapter instance.

## Neutral evidence primitives

`evidence_primitives.py` owns the dependency-neutral contracts used to create and hash evidence:

- timezone-aware millisecond UTC timestamps;
- non-guessable prefixed identifiers;
- deterministic canonical JSON encoding;
- SHA-256 chaining over the previous hash and canonical payload.

`AuditLedger` imports these primitives directly. A fixed compatibility vector verifies that canonical JSON and hash output remain byte-for-byte identical to the existing stored evidence format.

## Audit guarantees

The ledger uses the canonical statement catalog, preserves the existing `GENESIS`-anchored SHA-256 chain, verifies every hash transition, and remains compatible with audit events produced before this unification.

External identity events continue to exclude the raw provider subject. Only its SHA-256 digest appears in responses and audit payloads.

## Compatibility boundary

Both the compatibility installer and the production composition installer now use the same canonical `ProductService` audit implementation. System tests enforce route and middleware parity, shared-ledger identity, database binding, and absence of legacy audit SQL from the service.

The removed `ledger_service.py` module was internal and temporary. No public route, schema, service method, or evidence field was removed.

## Explicitly disabled

This boundary does not enable external sign-in, network issuer discovery, public identity-binding management, automatic provisioning, release, deployment, or production effects.
