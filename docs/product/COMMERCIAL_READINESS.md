# VOODOO One 0.9.0-rc2-dev — Commercial Readiness Contract

## Product claim

VOODOO One RC2 development baseline is a governed AI-operations control plane implementing the
canonical flow:

`change request → review → execution → evidence`

## Included

- persistent SQLite product read/write model,
- local users and role enforcement,
- multi-workspace registry,
- separation of requester and approver,
- two-person approval for production requests,
- fail-closed production effects,
- allowlisted local adapters,
- idempotent executions,
- emergency stop,
- hash-chained audit events,
- hash-chained execution receipts,
- Command Center, approvals, execution and evidence UI,
- Docker runtime and readiness gate.

## Explicit limitations

This RC is suitable for controlled pilots and commercial demonstrations. It is not yet an enterprise production release because the following remain separate release gates:

1. SSO/OIDC/SAML integration,
2. PostgreSQL high-availability backend,
3. external production effect adapters,
4. tenant-level cryptographic key separation,
5. signed SBOM and independent penetration test,
6. billing, licensing enforcement and customer support operations,
7. legal package: final EULA, DPA, SLA and privacy documentation.

Production effects remain disabled by default and must not be enabled merely to pass a demonstration.
