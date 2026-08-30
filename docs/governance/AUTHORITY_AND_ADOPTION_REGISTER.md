# Authority and Adoption Register

| Field | Value |
|---|---|
| Document class | Governance authority and adoption register |
| Candidate preparation date | `2026-08-06` |
| Latest recorded owner adoption date | `2026-08-24` |
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

## 9. Execution Grant authoritative issuance/authenticity v1 owner adoption record

```text
DOCUMENT: docs/adr/ADR-0009-execution-grant-authoritative-issuance-authenticity-v1.md
OWNER_ADOPTED_SOURCE_ARTIFACT: EXECUTION_GRANT_AUTHORITATIVE_ISSUANCE_AUTHENTICITY_V1_REVISED_PROPOSED.md
VERSION_OR_CANDIDATE_VERSION: Execution Grant Authoritative Issuance & Authenticity Boundary v1 — REVISED PROPOSED
DECLARED_STATUS: PROPOSED / PREPARED
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit owner decision over exact SHA-256 cf23368fa96303bfd32bf825ddca2f30a9772408c0301a8390fadd758eb654d9 with exact bytes preserved in candidate content commit A
ADOPTION_DATE: 2026-08-09
ADOPTED_CONTENT_COMMIT: 42424df108973da042836dd22ccd0e4883939b18
CONTENT_SHA256: cf23368fa96303bfd32bf825ddca2f30a9772408c0301a8390fadd758eb654d9
SUPERSEDES: no previously adopted design; replaces unadopted bespoke-signature candidate SHA-256 87ad6144ebfab8687f07e6e86f35f5c9e6898a818476ed9edb66b447ce864320
CONFLICTS_RESOLVED: custom signature framing rejected; standards-based JWS Compact Serialization profile with fully specified Ed25519 algorithm adopted; ADR-0007 value-contract authority preserved; ADR-0008 isolated Runner boundary preserved; authenticity does not imply authorization or replay resistance; Runner runtime remains unimplemented; production effects remain BLOCKED; implementation authorization is not implied
NEXT_REVIEW: before any grant-issuance/authenticity implementation or any material change to this boundary
RUNNER_IMPLEMENTATION: NOT_AUTHORIZED
PRODUCTION_EFFECTS: BLOCKED
RELEASE: NOT_AUTHORIZED
DEPLOYMENT: NOT_AUTHORIZED
```

The owner-adopted bytes are exactly the content in the recorded candidate commit and remain unchanged
despite their embedded `REVISED PROPOSED` / `PROPOSED / PREPARED` labels. This external record is the
effective adoption evidence. The adoption-record commit does not embed its own Git hash and does not
authorize implementation, Runner runtime, release, deployment, or production effects.

## 10. Authorization Snapshot issuance facts v1 owner adoption record

```text
DOCUMENT: docs/adr/ADR-0010-authoritative-immutable-authorization-snapshot-issuance-facts-v1.md
OWNER_ADOPTED_SOURCE_ARTIFACT: AUTHORITATIVE_IMMUTABLE_AUTHORIZATION_SNAPSHOT_ISSUANCE_FACTS_V1_REVISED_PROPOSED.md
VERSION_OR_CANDIDATE_VERSION: Authoritative Immutable Authorization Snapshot & Issuance Facts Boundary v1 — REVISED PROPOSED
DECLARED_STATUS: PROPOSED / PREPARED
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit owner decision over exact SHA-256 3dee4f84ab9e94bf748c4d8ba20faebf3eb73670e92c64cdd10293ef8b9d736f, exact bytes preserved in candidate content commit A, and subsequent explicit owner binding of that commit identity
ADOPTION_DATE: 2026-08-10
ADOPTED_CONTENT_COMMIT: b8870f22c2fad45bfb14781b215e12dbd762351f
CONTENT_SHA256: 3dee4f84ab9e94bf748c4d8ba20faebf3eb73670e92c64cdd10293ef8b9d736f
SUPERSEDES: unadopted authorization-snapshot candidate SHA-256 e6e9cbe922bb6d5f61a38f70ae92427d88afd0fbc8be0d0bd1fb14c28e3b63cf
CONFLICTS_RESOLVED: reconciled to canonical main@459d1c81923d0460da75473a99a167ef49705e02 and adopted ADR-0009; immutable authorization-snapshot facts remain separate from grant-issuance records; authoritative issuance timestamp-source identity is bound; grant issuance must independently re-check execution.run and environment/production-effect live deny gates; no legacy facts may be fabricated; Runner runtime remains unimplemented; production effects remain BLOCKED; implementation authorization is not implied
NEXT_REVIEW: before any authorization-snapshot/grant-issuance implementation or any material change to this boundary
RUNNER_IMPLEMENTATION: NOT_AUTHORIZED
PRODUCTION_EFFECTS: BLOCKED
RELEASE: NOT_AUTHORIZED
DEPLOYMENT: NOT_AUTHORIZED
```

The owner-adopted bytes are exactly the content in the recorded candidate commit and remain unchanged
despite their embedded `REVISED PROPOSED` / `PROPOSED / PREPARED` labels. This external record is the
effective adoption evidence. The adoption-record commit does not embed its own Git hash and does not
authorize implementation, Runner runtime, release, deployment, or production effects.

## 11. V-One Product & Architecture Thesis R2 owner adoption record

```text
DOCUMENT: docs/architecture/VONE_PRODUCT_ARCHITECTURE_THESIS_R2.md
VERSION_OR_CANDIDATE_VERSION: V-One Product & Architecture Thesis R2
DECLARED_STATUS: PROPOSED / REVIEW REQUIRED
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit owner decision over exact candidate commit 5f4b752c46914a88c90e01c8e4993584441233f9 and exact content SHA-256 599365f369450754d09b61ca30d5ef813bc0297f8715e02f7631e0ed2e5cd37d after confirming the merged main document retains the same immutable Git blob
ADOPTION_DATE: 2026-08-17
ADOPTED_CONTENT_COMMIT: 5f4b752c46914a88c90e01c8e4993584441233f9
CONTENT_SHA256: 599365f369450754d09b61ca30d5ef813bc0297f8715e02f7631e0ed2e5cd37d
SUPERSEDES: none; establishes the owner-adopted Product & Architecture Thesis R2 baseline
CONFLICTS_RESOLVED: merge and CI are explicitly not treated as adoption; the exact candidate bytes are adopted without modifying their embedded PROPOSED / REVIEW REQUIRED label; V-One is positioned as a Verifiable Operations Trust Plane with OperationCell/v1, Monotonic Authority, ExecutionCapsule, PreconditionWitness, Runner/Verifier separation and portable proof as target invariants; CASER, CASER-SOURCER, CASTER-MINAL and SandCloud responsibility boundaries are adopted as target boundaries, not claims of deployed completeness; commercial PMF/pricing remains UNPROVEN and requires customer validation; implementation, release, deployment, provider mutation and production effects remain separate authority decisions
NEXT_REVIEW: before any material change to the product position, OperationCell/v1 trust chain, ecosystem responsibility boundaries, Monotonic Authority invariant, or after material contradictory implementation/market evidence
IMPLEMENTATION_AUTHORIZATION: NOT_CREATED_BY_THIS_RECORD; any implementation authority must exist separately
RELEASE: NOT_AUTHORIZED
DEPLOYMENT: NOT_AUTHORIZED
PROVIDER_MUTATION: NOT_AUTHORIZED
PRODUCTION_EFFECTS: NOT_AUTHORIZED
```

The owner-adopted bytes are exactly those in candidate commit
`5f4b752c46914a88c90e01c8e4993584441233f9` with the recorded SHA-256. The adoption-record commit
modifies only this external governance register and does not modify the adopted Thesis R2 content.
The embedded `PROPOSED / REVIEW REQUIRED` label is therefore preserved as historical declared status;
this record establishes the effective `ADOPTED` status. This record does not itself authorize A8 or
any later implementation, release, deployment, provider mutation, or production effect.

## 12. ADR-0019 owner adoption record — canonical READ E2E before provider WRITE

```text
DOCUMENT: docs/adr/ADR-0019-read-e2e-before-write.md
VERSION_OR_CANDIDATE_VERSION: ADR-0019 — Canonical READ E2E Before Provider WRITE
DECLARED_STATUS: PROPOSED — governed adoption pending
EFFECTIVE_STATUS: ADOPTED
OWNER: project owner VOODOO — ENGINEERING
ADOPTION_METHOD: explicit owner decision over exact candidate commit 39f6743c239876b2d532d6fd7e7b8b74714d3c0d and exact content SHA-256 464f9fde473edd01df37ab86f3b08661da00cb9c4023830c1792b0de65d12df0 after exact-head CI #1060, fresh independent Codex review with no major findings, zero unresolved blocking review threads, protected-main merge PR #142, and confirmation that merged main retains Git blob 18595723171cfa00fba8cfa5231863ef7c2f5bc2
ADOPTION_DATE: 2026-08-24
ADOPTED_CONTENT_COMMIT: 39f6743c239876b2d532d6fd7e7b8b74714d3c0d
CONTENT_SHA256: 464f9fde473edd01df37ab86f3b08661da00cb9c4023830c1792b0de65d12df0
SUPERSEDES: none; establishes the READ-before-WRITE eligibility boundary for provider effects
CONFLICTS_RESOLVED: exact candidate bytes remain PROPOSED and immutable while this external record establishes effective adoption; restart/resume is constrained to the same ACTIVE execution before Runner completion; completed-execution resume/reverification is not claimed; G8 is READ-only; execution success remains distinct from independent VerificationResult/v1; provider WRITE remains blocked until the adopted READ evidence gate is VERIFIED and a later effect-specific authorization exists
NEXT_REVIEW: before any weakening of the READ-before-WRITE gate, before provider WRITE activation, or after material contradictory runtime/security evidence
IMPLEMENTATION_AUTHORIZATION: NOT_CREATED_BY_THIS_RECORD; the separate owner instruction to proceed with a conforming READ-only G8 candidate remains distinct
G8_READ_ONLY_RUNTIME: MAY_PROCEED_ONLY_WITHIN_ADOPTED_BOUNDARY_AND_NORMAL_REVIEW_GATES
PROVIDER_WRITE: NOT_AUTHORIZED
CREATE_REF_DELETE_REF_EFFECTS: NOT_AUTHORIZED
RELEASE: NOT_AUTHORIZED
DEPLOYMENT: NOT_AUTHORIZED
PRODUCTION_EFFECTS: BLOCKED
```

The adopted bytes are exactly those in candidate commit
`39f6743c239876b2d532d6fd7e7b8b74714d3c0d` with the recorded SHA-256 and Git blob identity. PR #142
merged those bytes without modifying the ADR. This external record establishes effective adoption and
does not itself authorize G8 implementation beyond the separately recorded owner instruction, any
provider mutation, release, deployment, or production effect.
