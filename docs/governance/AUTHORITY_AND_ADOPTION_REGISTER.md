# Authority and Adoption Register

| Field | Value |
|---|---|
| Document class | Governance authority and adoption register |
| Candidate preparation date | `2026-08-06` |
| Latest recorded owner adoption date | `2026-08-08` |
| Scope | VOODOO One governance documents, accepted ADRs, and technical operating-standard succession |
| Live repository authority | None; live Git, tests, CI, artifacts and runtime remain separate evidence sources |
| Owner adoption effect | An explicit owner decision over an exact content SHA-256 and candidate commit creates adoption when recorded here without modifying the adopted content |
| Governing rule | Missing or conflicting adoption evidence fails closed as `UNKNOWN` or `BLOCKED` |

> Repository presence, commit, push, pull request, merge, project upload, or a document's self-declared
> authority does not by itself create adoption.

## 1. Claim dimensions

| Label | Meaning |
|---|---|
| `DECLARED` | The artifact states the claim. |
| `ADOPTED` | Explicit owner or accepted-ADR evidence makes the artifact effective. |
| `DOCUMENTED_CURRENT` | State is described at a dated baseline. |
| `LIVE_VERIFIED` | State was checked directly from current Git, tests, CI, artifacts, or runtime. |
| `INFERRED` | Conclusion derived from available evidence. |
| `UNKNOWN` | Evidence is missing or conflicting. |
| `BLOCKED` | The project cannot safely proceed until the conflict or missing evidence is resolved. |

## 2. Predecessor adoption record — historical

```text
DOCUMENT: WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
VERSION: predecessor-effective
DECLARED_STATUS: CANONICAL_TECHNICAL_STANDARD
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit project instruction naming the document normative, binding, canonical, and hash-bound
ADOPTION_DATE: externally recorded in project instruction; repository backfill prepared by candidate commit A
CONTENT_SHA256: ed44c6147049887d941b7497f1bce3b817f22b6ae00a5136a27365a2f688d918
SUPERSEDES: none recorded here
CURRENT_STATUS: SUPERSEDED_BY_EXACT_OWNER_ADOPTED_SUCCESSOR
SUPERSEDED_BY_CONTENT_COMMIT: 46793950622ece6f02d7495bcfc72d04af20c155
SUPERSEDED_BY_CONTENT_SHA256: 36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed
```

The predecessor's adoption remains historically valid. It is not downgraded to merely `DECLARED` or
`UNKNOWN`; it is superseded only by the exact successor recorded in section 4.

## 3. Candidate preparation record — historical state at commit A

```text
DOCUMENT: WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
CANDIDATE_VERSION: 2026-08-06-v3-candidate
DECLARED_STATUS: PROPOSED_SUCCESSOR_REVISION
EFFECTIVE_STATUS: PROPOSED
OWNER: project owner VOODOO — ENGINEERING
CANDIDATE_CONTENT_SHA256: 36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed
CANDIDATE_CONTENT_COMMIT: REQUIRED_IN_LATER_OWNER_ADOPTION_RECORD
ADOPTION_DECISION: REQUIRED
ADOPTION_DATE: REQUIRED
SUPERSEDES_IF_ADOPTED: ed44c6147049887d941b7497f1bce3b817f22b6ae00a5136a27365a2f688d918
CURRENT_STATUS: ADOPTED_BY_EXACT_OWNER_RECORD_IN_SECTION_4
```

This block preserves the candidate-preparation state that existed in commit A. It is historical and
must be read together with the later owner-adoption record below.

## 4. Owner adoption record — effective successor

```text
DOCUMENT: WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
CANDIDATE_VERSION: 2026-08-06-v3-candidate
DECLARED_STATUS: PROPOSED_SUCCESSOR_REVISION
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit owner decision over exact candidate SHA-256 and candidate commit A
ADOPTION_DATE: 2026-08-06
ADOPTED_CONTENT_COMMIT: 46793950622ece6f02d7495bcfc72d04af20c155
CONTENT_SHA256: 36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed
SUPERSEDES: ed44c6147049887d941b7497f1bce3b817f22b6ae00a5136a27365a2f688d918
CONFLICTS_RESOLVED: predecessor authority preserved; self-referential adoption cycle removed; PROJECT_CONSTITUTION remains PROPOSED / Normative Draft; VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION remains PROPOSED_FOR_ADOPTION
NEXT_REVIEW: 2026-11-04 or after a material governance or security incident, hierarchy change, or standard revision, whichever occurs first
```

The adopted content is exactly the immutable document in candidate commit A and its matching sidecar.
The adoption-record commit must not modify that document or its sidecar. Any later content change
creates a new candidate SHA-256 and requires a new explicit owner decision.

This owner decision establishes the successor's normative authority. Publication, pull request, merge,
and synchronization into `main` remain separate technical operations and evidence states.

## 5. Non-self-referential adoption protocol

1. Candidate commit A contains the immutable candidate document, its sidecar, the candidate register,
   governance navigation, and integrity tests.
2. The project owner explicitly approved the exact candidate SHA-256 and candidate commit A.
3. Adoption commit B updates only this external governance record and records
   `ADOPTED_CONTENT_COMMIT=<commit A>`.
4. Commit B does not embed its own Git hash. Git history proves the identity of the adoption-record
   commit without creating a content/hash cycle.
5. Any change to the adopted content after commit A creates a new candidate and requires a new owner
   decision.

## 6. Other constitutional documents

| Document | Current effective status | Boundary |
|---|---|---|
| `PROJECT_CONSTITUTION.md` | `PROPOSED` / `Normative Draft` | Not effective until separately adopted by the owner. |
| `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md` | `PROPOSED_FOR_ADOPTION` | Not effective until its adoption conditions are satisfied. |
| `GOVERNANCE.md` | Descriptive navigation map | Reconciled after owner adoption to reflect the effective successor status; this register remains authoritative for the owner adoption recorded here. |
| `SECURITY.md` | Mandatory security policy in its documented scope | Must not be weakened by unclear governance. |
| Accepted ADRs | Effective only in their explicitly accepted scope | A merged `PROPOSED` ADR is not automatically accepted. |

## 7. ADR-0008 owner adoption record — isolated Runner boundary v1

```text
DOCUMENT: docs/adr/ADR-0008-isolated-runner-boundary-v1.md
VERSION_OR_CANDIDATE_VERSION: ADR-0008-isolated-runner-boundary-v1
DECLARED_STATUS: PROPOSED
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit owner decision over exact ADR SHA-256, content commit, and bound threat-model SHA-256
ADOPTION_DATE: 2026-08-08
ADOPTED_CONTENT_COMMIT: 8834abd5fe7b5a6f2ee7cf266997334fb26b7e8a
CONTENT_SHA256: 97180eef53c1798c0c2bac3fac73dc7e143561e6eb71709a5057d5ce936e202b
SUPERSEDES: none; resolves the owner-decision-required state for these exact reviewed bytes
CONFLICTS_RESOLVED: immutable reviewed bytes preserved; design and safety invariants adopted; isolated Runner runtime remains unimplemented; production effects remain BLOCKED; implementation authorization is not implied
NEXT_REVIEW: before first isolated Runner runtime implementation or any material change to the adopted boundary
BOUND_THREAT_MODEL: docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md
BOUND_THREAT_MODEL_SHA256: 71d2c5feceb71291e5919d8cfb37d099186c24648622573bba6e8b49a75bf06b
PRODUCTION_EFFECTS: BLOCKED
IMPLEMENTATION_AUTHORIZATION: NOT_IMPLIED
```

The adopted ADR and bound threat-model bytes remain unchanged. Their embedded `PROPOSED` labels are
the historical declared status of those immutable reviewed bytes; this external record is the
effective owner-adoption evidence. No runtime code, release, deployment, or production effect is
authorized by this record.

## 8. Adoption-record integrity requirements

Every later normative, mandatory, constitutional, or accepted artifact must have a non-self-referential
record containing:

```text
DOCUMENT:
VERSION_OR_CANDIDATE_VERSION:
DECLARED_STATUS:
EFFECTIVE_STATUS:
OWNER:
ADOPTION_METHOD:
ADOPTION_DATE:
ADOPTED_CONTENT_COMMIT:
CONTENT_SHA256:
SUPERSEDES:
CONFLICTS_RESOLVED:
NEXT_REVIEW:
```

The record must not contain the hash of the commit that stores the record itself.
