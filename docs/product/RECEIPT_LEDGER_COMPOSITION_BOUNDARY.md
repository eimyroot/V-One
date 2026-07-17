# Receipt Ledger Composition Boundary

## Status

Implemented as the canonical execution-receipt evidence boundary.

## Purpose

`ReceiptLedger` owns receipt append, bounded listing, and full chain verification. `ProductService` preserves its existing public methods while delegating the complete receipt surface to one database-bound ledger.

## Runtime composition

`install_composed_product_platform` creates one `ProductService` with:

- one shared `AuditLedger`;
- one shared `ReceiptLedger`;
- one governed external identity service using the same database and audit ledger;
- one immutable `ProductComposition` exposing both evidence ledgers.

The receipt ledger is stored on `app.state.voodoo_receipt_ledger` for internal dependency access. No public route is added.

## Delegation contract

- `_append_receipt` delegates to `ReceiptLedger.append` inside the caller transaction;
- `list_receipts` delegates to the bounded ledger reader;
- `verify_receipt_chain` delegates to the ledger verifier.

`ProductService` contains no direct receipt SQL. The four canonical receipt statements are executed only by `receipt.py`.

## Evidence compatibility

The ledger preserves:

- prefixed non-guessable receipt identifiers;
- canonical JSON payload serialization;
- the existing `GENESIS` chain anchor;
- SHA-256 chaining over the prior hash and payload;
- monotonic receipt sequence verification;
- existing response fields and list ordering.

No schema migration or stored-data transformation is required.

## Failure model

An injected receipt ledger must use the exact same database adapter instance as the product service. A mismatch is rejected during construction. Invalid sequence, previous-hash, or receipt-hash transitions fail verification closed and identify the first broken receipt.

## Explicitly disabled

This boundary does not add routes, enable external sign-in, alter execution authorization, release, deploy, or enable production effects.
