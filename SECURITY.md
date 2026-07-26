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
- session tokens use an explicit v2 issuer/audience context and a purpose-derived signing key,
- authentication routes depend on the configured identity-provider boundary,
- unreleased identity providers abort startup without local-authentication fallback,
- production effects disabled unless explicitly released,
- application SQL selected only from the reviewed statement catalog,
- unavailable database dialects fail closed without SQL fallback,
- untrusted HTTP hosts and inline browser execution denied by default,
- receipt-chain order derived only from a monotonic database sequence,
- expired executions recover only under emergency stop and fence every late completion,
- audit and receipt integrity verified independently of liveness probes.

## Local checkpoint verification boundary

`voodoo evidence verify` treats checkpoint paths as untrusted local input. It rejects traversal,
symlinks, special files, incomplete manifest coverage and inconsistent Git/source/runtime claims.
It never executes checkpoint code, contacts Docker or a registry, changes a database, or enables
production effects. Remote byte verification and signed attestations remain outside the current
boundary.
