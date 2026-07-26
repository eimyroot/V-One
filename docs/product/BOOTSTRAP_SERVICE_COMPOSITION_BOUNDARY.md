# Bootstrap Service Composition Boundary

## Status

Design boundary opened from exact `main` commit `b763507802394394cc110edd07e2ce5dccbec695`.

## Goal

Extract the atomic first-administrator provisioning workflow from `ProductService` into a canonical, database-bound `BootstrapService` without changing observable product behavior.

## Canonical ownership

`BootstrapService` will own:

- determining whether any user exists;
- validating the bootstrap token with constant-time comparison;
- the single database transaction that creates the first administrator;
- creation of the initial workspace;
- append-only bootstrap audit evidence;
- bootstrap result projection.

## Required invariants

The following must remain unchanged:

- bootstrap closes permanently after the first user exists;
- user, workspace and audit evidence commit or roll back together;
- username trimming;
- password hashing implementation;
- administrator role assignment;
- workspace naming and environment fallback;
- current exception types and messages;
- current `ProductService` public API;
- route, HTTP and authorization behavior.

## Composition rules

An injected `BootstrapService` must use the exact same:

- product database adapter;
- `ProductConfig` instance;
- `AuditLedger` instance.

Any mismatch fails closed during composition.

## Explicit exclusions

This boundary does not own credential lookup, dummy-password timing protection, password verification, login rate limiting, external identity, release, deployment or production activation.

## Verification plan

The implementation must add focused tests for:

- statement ownership;
- delegation compatibility;
- exact dependency identity enforcement;
- complete transaction rollback on user, workspace or audit failure;
- concurrent bootstrap attempts allowing at most one successful administrator;
- token and closed-bootstrap error compatibility;
- readiness and full product CI.
