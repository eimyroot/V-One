# Platform Status Service Composition Boundary

## Status

Implemented as the canonical read-only command-center and liveness projection boundary.

## Purpose

`PlatformStatusService` owns operational aggregate reads for the command center and the lightweight database liveness projection. `ProductService` preserves the existing public method surface while delegating `command_center` and `health`.

## Runtime composition

`install_composed_product_platform` exposes one shared platform status service through `ProductComposition` and `app.state.voodoo_platform_status_service`.

The service uses the exact product database, configuration, audit ledger, receipt ledger and operational-safety service instances. Composition mismatches fail closed.

## Preserved invariants

- command-center change-request, execution and risk aggregates use the central statement catalog;
- emergency-stop state is read through the shared operational-safety boundary;
- command-center trust state remains incident-driven by emergency stop or invalid evidence chains;
- receipt and audit verification continue through the shared canonical ledgers;
- liveness performs only the existing lightweight database probe and emergency-stop read;
- liveness continues to report evidence integrity as not checked;
- database failures preserve the existing `UNAVAILABLE` response shape;
- existing method signatures, routes, status codes, fields and ordering remain unchanged.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, modify bootstrap, authentication, change-request or execution behavior, enable external sign-in, release, deploy or enable production effects.
