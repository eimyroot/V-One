# Execution Service Composition Boundary

## Status

Implemented as the canonical execution lifecycle and recovery boundary.

## Purpose

`ExecutionService` owns durable execution start, idempotency binding, lease and fence handling, adapter invocation, completion, receipt evidence, audit evidence, incident recovery, and execution reads.

`ProductService` preserves the existing public method surface and delegates the complete execution domain to one database-bound service.

## Runtime composition

`install_composed_product_platform` creates one `ProductService` with:

- one shared database adapter;
- one shared `AuditLedger`;
- one shared `ReceiptLedger`;
- one shared `ExecutionService`;
- one governed external identity service.

The execution service is exposed internally through `ProductComposition` and `app.state.voodoo_execution_service`. No public route is added or changed.

## Delegation contract

- `execute_change_request` delegates to `ExecutionService.execute_change_request`;
- `recover_execution` delegates to `ExecutionService.recover_execution`;
- `list_executions` delegates to `ExecutionService.list_executions`;
- `get_execution` delegates to `ExecutionService.get_execution`.

`ProductService` contains no direct execution lifecycle SQL after composition.

## Safety invariants

The boundary preserves:

- idempotency keys bound to exactly one change request;
- emergency-stop enforcement before new execution;
- workspace and request environment equality;
- production effects disabled unless explicitly configured;
- durable start before adapter invocation;
- lease expiry and fence checks during recovery;
- late-worker completion rejection;
- receipt and audit append in the completion or recovery transaction;
- indeterminate interrupted outcome semantics;
- existing response fields and error behavior.

An injected execution service must use the exact product database, configuration, audit ledger, and receipt ledger instances. Mismatches fail closed during construction.

## Compatibility

The product service continues to expose the same API methods. Existing adapter monkeypatch behavior remains supported through an injected adapter executor bridge. No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, enable external sign-in, release, deploy, or enable production effects.
