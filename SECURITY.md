# Security policy

| Field | Value |
|---|---|
| Document class | Mandatory security policy |
| Adoption evidence | Must be confirmed from repository history or explicit owner record; file presence alone is not adoption |
| Applies to | VOODOO One source, runtime, operations, evidence and release decisions |
| Security posture | Deny by default, least privilege and fail closed |
| Live-state boundary | This document defines policy; it does not prove the current `main`, runtime configuration, release or deployment state |
| Related authority record | `docs/governance/AUTHORITY_AND_ADOPTION_REGISTER.md` |

## Supported state

The support policy applies only to the latest commit on `main` **after that commit is identified
directly from the live repository**. A commit recorded in documentation is a dated snapshot, not proof
of the current remote or local `main`.

Production effects remain disabled until a tagged governed release explicitly changes this statement,
all production gates are evidenced, and the release decision is recorded. A tag, merge, documentation
change, local test run or environment-variable drift cannot independently enable production effects.

## Reporting

Do not open public issues for suspected vulnerabilities or include secrets, customer data or exploit
details in logs. Repository security advisories must be used once enabled by the repository owner.

If no private reporting channel is enabled, disclose only that private reporting is `BLOCKED`; do not
move sensitive details into a public issue, chat transcript, CI log or evidence archive.

## Security invariants

These are policy invariants. Capability-level claims such as `VERIFIED` remain limited to the exact
test, commit, CI or runtime evidence cited by `CURRENT_PRODUCT_STATE.md` and
`docs/product/CURRENT_CAPABILITIES.md`.

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
- ADR-0007 execution-contract value objects are accepted as representation only; authoritative
  issuance and isolated Runner runtime remain proposed,
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
boundary. The proposed isolated Runner threat model is documented in
[`docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md`](docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md)
and is not implemented runtime control.
