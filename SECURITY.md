# Security policy

## Supported state

Only the latest commit on `main` is maintained. Production effects remain disabled until a tagged
release explicitly changes this statement and all production gates are evidenced.

## Reporting

Do not open public issues for suspected vulnerabilities or include secrets, customer data or exploit
details in logs. Repository security advisories must be used once enabled by the repository owner.

## Security invariants

- deny by default and least privilege,
- no requester self-approval,
- request environment must match its authoritative workspace environment,
- two distinct approvers for production requests,
- no shell execution from user input,
- filesystem effects confined to a governed sandbox,
- secrets supplied at runtime and never committed,
- production effects disabled unless explicitly released,
- application SQL selected only from the reviewed statement catalog,
- unavailable database dialects fail closed without SQL fallback,
- untrusted HTTP hosts and inline browser execution denied by default,
- receipt-chain order derived only from a monotonic database sequence,
- expired executions recover only under emergency stop and fence every late completion,
- audit and receipt integrity verified independently of liveness probes.
