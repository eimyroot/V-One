# Operational Safety Composition Boundary

## Status

Implemented as the canonical emergency-stop state and audited transition boundary.

## Purpose

`OperationalSafetyService` owns emergency-stop reads and audited set/clear transitions. `ProductService` preserves the existing API while `ExecutionService` consumes the same safety state inside execution start and recovery transactions.

## Runtime composition

`install_composed_product_platform` exposes one shared operational safety service through `ProductComposition` and `app.state.voodoo_operational_safety_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Delegation contract

- `ProductService.set_emergency_stop` delegates to the shared safety service;
- command-center and health reads use the shared safety service;
- execution start and incident recovery check the shared safety service using their existing transaction connection;
- direct emergency-stop SQL is absent from both `service.py` and `execution.py`.

## Safety invariants

The boundary preserves:

- emergency stop blocks new executions;
- recovery requires emergency stop to be active;
- set and clear transitions append audit evidence in the same transaction;
- existing action names, response fields, error behavior and API permissions;
- read-only health and command-center behavior;
- default inactive state when no setting exists.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, enable external sign-in, release, deploy, or enable production effects.
