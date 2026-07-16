# VOODOO One — Controlled Pilot Scope

## Recommended pilot

- one customer workspace,
- local, development or staging environment,
- up to three governed workflows,
- two operator roles plus one auditor,
- one allowlisted effect adapter,
- audit and receipt export,
- deployment and recovery runbook,
- acceptance test report.

## Acceptance criteria

1. A developer creates and submits a change request.
2. The requester cannot self-approve.
3. An authorized operator approves the request.
4. Execution is idempotent and restricted to an allowlisted adapter.
5. An evidence receipt is generated.
6. Receipt and audit chains verify successfully.
7. Emergency stop blocks new execution.
8. Backup and restore are demonstrated.

## Out of scope until separately contracted

- unrestricted production mutation,
- arbitrary shell execution,
- raw secret display,
- customer-wide SSO federation,
- multi-region high availability,
- regulated-industry certification claims.
