# Audit Ledger and Product Composition Boundary

## Status

Implemented as an internal runtime composition boundary. No public identity-management or external-authentication API is released by this change.

## Purpose

The governed external identity lifecycle previously depended on a private audit callback owned by `ProductService`. The composition boundary replaces that dependency with a typed, reusable `AuditLedger` component and installs the identity lifecycle service explicitly at application startup.

## Runtime composition

`install_composed_product_platform` first installs the existing product platform, then creates:

- one `AuditLedger` bound to the product database adapter;
- one `GovernedExternalIdentityService` bound to the same database adapter;
- one immutable `ProductComposition` containing those components.

The composed components are stored on `app.state` for internal dependency access. No router receives the identity lifecycle service and no new OpenAPI path is registered.

## Audit guarantees

The ledger:

- appends events inside the caller's existing database transaction;
- uses the canonical audit statement catalog;
- preserves the existing `GENESIS`-anchored SHA-256 chain format;
- verifies every previous-hash and event-hash transition;
- returns decoded audit payloads through a bounded list method;
- remains interoperable with audit events already written by `ProductService`.

External identity events continue to exclude the raw provider subject. Only its SHA-256 digest is included in responses and audit payloads.

## Entrypoint rule

The production ASGI entrypoint uses `install_composed_product_platform`. The older `install_product_platform` function remains available for compatibility and focused tests, but it does not construct internal identity components.

## Explicitly disabled

This boundary does not enable:

- OIDC login or token acceptance;
- issuer discovery or JWKS network access;
- public identity-binding creation or disablement;
- automatic user provisioning;
- external role administration;
- release, deployment, or production effects.

## Follow-up boundary

A later governed change may migrate the remaining legacy `ProductService` audit helper methods to delegate directly to `AuditLedger`. That refactor must preserve the existing audit-chain format and all public product service methods.
