# Change Request Service Composition Boundary

## Status

Implemented as the canonical change-request and approval lifecycle boundary.

## Purpose

`ChangeRequestService` owns creation, bounded listing, retrieval, submission, approval decisions, approval listing and their audit evidence. `ProductService` preserves the existing public method surface while delegating the complete domain.

## Runtime composition

`install_composed_product_platform` exposes one shared change-request service through `ProductComposition` and `app.state.voodoo_change_request_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Preserved governance invariants

- risk, environment and adapter validation;
- governed payload-size limit;
- workspace and request environment equality;
- draft-only submission;
- requester/approver separation of duties;
- one decision per approver;
- two approvals for production and one elsewhere;
- denial terminal state;
- audit evidence in the same transaction as each lifecycle transition;
- existing method signatures, response fields, ordering and error behavior.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, alter execution semantics, enable external sign-in, release, deploy or enable production effects.
