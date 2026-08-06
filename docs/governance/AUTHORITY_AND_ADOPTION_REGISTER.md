# Authority and Adoption Register

| Field | Value |
|---|---|
| Document class | Governance authority and adoption register |
| Candidate preparation date | `2026-08-06` |
| Scope | VOODOO One governance documents and technical operating-standard succession |
| Live repository authority | None; live Git, tests, CI, artifacts and runtime remain separate evidence sources |
| Owner adoption effect | Only an explicit owner decision over an exact content SHA-256 and candidate commit can create adoption |
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

## 2. Effective technical operating standard

```text
DOCUMENT: WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
VERSION: predecessor-effective
DECLARED_STATUS: CANONICAL_TECHNICAL_STANDARD
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit project instruction naming the document normative, binding, canonical, and hash-bound
ADOPTION_DATE: externally recorded in project instruction; repository backfill prepared by this register
CONTENT_SHA256: ed44c6147049887d941b7497f1bce3b817f22b6ae00a5136a27365a2f688d918
SUPERSEDES: none recorded here
SUPERSEDED_BY: none while the v3 candidate remains PROPOSED
```

The predecessor's authority must not be downgraded to merely `DECLARED` or `UNKNOWN` solely because
its original owner instruction was external to the repository.

## 3. Proposed successor candidate

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
```

The candidate does not become effective through commit, push, pull request, merge, or documentation
publication. Until a later owner-adoption record exists, the effective technical standard remains the
predecessor with SHA-256 `ed44c614...`.

## 4. Non-self-referential adoption protocol

1. Candidate commit A contains the immutable candidate document, its sidecar, this proposed register,
   governance navigation, and integrity tests.
2. The project owner reviews and explicitly approves both the exact candidate SHA-256 and commit A.
3. A later adoption commit B updates only the external governance record needed to mark the exact
   candidate as `ADOPTED` and records `ADOPTED_CONTENT_COMMIT=<commit A>`.
4. Commit B does not embed its own Git hash. Git history proves the identity of the adoption-record
   commit without creating a content/hash cycle.
5. Any change to the candidate after commit A creates a new candidate and requires a new owner decision.

## 5. Other constitutional documents

| Document | Current effective status | Boundary |
|---|---|---|
| `PROJECT_CONSTITUTION.md` | `PROPOSED` / `Normative Draft` | Not effective until separately adopted by the owner. |
| `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md` | `PROPOSED_FOR_ADOPTION` | Not effective until its adoption conditions are satisfied. |
| `GOVERNANCE.md` | Descriptive navigation map | Does not create authority by itself. |
| `SECURITY.md` | Mandatory security policy in its documented scope | Must not be weakened by unclear governance. |
| Accepted ADRs | Effective only in their explicitly accepted scope | A merged `PROPOSED` ADR is not automatically accepted. |

## 6. Required later owner-adoption record

A later adoption change must add a record with all of the following fields:

```text
DOCUMENT:
CANDIDATE_VERSION:
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
