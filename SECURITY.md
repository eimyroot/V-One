# Security policy

## Supported state

Only the latest commit on `main` is maintained. Production effects remain disabled until a tagged
release explicitly changes this statement and all production gates are evidenced.

The current canonical product includes authoritative snapshot/grant issuance, durable one-time grant
consumption, bounded isolated READ Runner contracts, an independent Verifier path, a merged READ HTTP
surface, and restart-safe durable resume. The default provider runtime pack remains disabled/fail-closed
until G8, and provider WRITE remains blocked.

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
- authoritative AuthorizationSnapshot and `ExecutionGrant/v2` issuance use the canonical database-backed authority path,
- `GrantConsumptionWitness/v1` is control-plane state and the Runner must never issue or re-consume a grant,
- canonical public READ requires the exact `READ_ONLY_VERIFIED + github.read-ref/v1` route; caller-selected stronger terminal authority is rejected,
- Runner and independent Verifier identities/credential decisions remain separate,
- execution success, receipt existence and evidence-chain integrity never imply `VerificationResult/v1 = VERIFIED`,
- durable resume reconstructs only the same already-authorized execution and must not perform a second prepare/grant/consume/outbox/inbox/lease acquisition,
- resume/current runtime bindings must share the canonical database, permission authority, terminal-profile registry, envelope revision and current fence,
- application SQL selected only from the reviewed statement catalog,
- unavailable database dialects fail closed without SQL fallback,
- untrusted HTTP hosts and inline browser execution denied by default,
- receipt-chain order derived only from a monotonic database sequence,
- stale/expired execution authority is fenced; restart/resume fails closed on missing, corrupt, ambiguous, expired, revoked or mismatched durable evidence,
- audit and receipt integrity verified independently of liveness probes,
- default provider runtime remains disabled unless explicitly configured through the canonical ProductComposition runtime factory,
- no ambient provider credential or legacy execution fallback may create canonical runtime authority,
- provider WRITE remains blocked until the governed READ-before-WRITE gate is adopted and its repeated real READ E2E/restart evidence is VERIFIED,
- WRITE eligibility is not WRITE authorization; provider mutation, release and deployment remain separately governed.

## G0 repository-governance evidence

GitHub main governance has retained live verifier evidence rather than being inferred from ordinary CI:

```text
workflow = g0-governance-verify
run = 32553113424
source_sha = 76d74d2ed62b6e78f027728c456c22da0b4a95bd
artifact = g0-governance-evidence-32553113424-1
artifact_digest = sha256:6e63caee23a57613471df66ef0279c0261ed8d375e4c929accdf50eff7dc4f5f
verdict = VERIFIED
```

That G0 evidence establishes repository-governance controls only. It does not authorize a provider
runtime, production effect, release or deployment.

## READ-before-WRITE boundary

ADR-0019 is currently `PROPOSED` and creates no authority before its governed adoption gate closes.
The proposed rule keeps provider WRITE blocked until repeated real canonical authenticated HTTP READ
E2E proves independent `VerificationResult/v1`, restart-safe durable resume, authority continuity, no
duplicate authority/effect state, and fail-closed failure injection. A future `ELIGIBLE` result would
still require a separate WRITE-specific authorization and review.

## Local checkpoint verification boundary

`voodoo evidence verify` treats checkpoint paths as untrusted local input. It rejects traversal,
symlinks, special files, incomplete manifest coverage and inconsistent Git/source/runtime claims.
It never executes checkpoint code, contacts Docker or a registry, changes a database, or enables
production effects. Remote byte verification and signed attestations remain outside the current
boundary.

The ADR-0008 isolated-Runner threat model remains a design/security reference. Governed pilot Runner
and Verifier isolation controls now exist in their named evidence scopes, but that does not imply the
default G8 provider runtime is active or that unrestricted production execution is released.
