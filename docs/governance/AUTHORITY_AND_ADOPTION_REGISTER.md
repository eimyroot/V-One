# Authority and Adoption Register

| Field | Value |
|---|---|
| Document class | Governance reconciliation register |
| Reconciliation date | `2026-08-05` |
| Scope | The supplied VOODOO One documentation set only |
| Live repository verification | NOT PERFORMED by this document |
| Owner adoption effect | None; this register records evidence but cannot create owner approval |
| Governing rule | Missing or conflicting adoption evidence fails closed as `UNKNOWN` or `BLOCKED` |

> This register separates what a document declares from what the supplied evidence proves. Upload,
> merge, repository presence, GPT knowledge use or a self-declared authority field does not constitute
> adoption.

## 1. Claim dimensions

| Label | Meaning |
|---|---|
| `DECLARED` | the artifact states the claim |
| `ADOPTED` | explicit owner or accepted-ADR evidence makes the artifact effective |
| `DOCUMENTED_CURRENT` | state is described at a dated baseline |
| `LIVE_VERIFIED` | state was checked directly from current Git, tests, CI, artifacts or runtime |
| `INFERRED` | conclusion derived from supplied evidence |
| `UNKNOWN` | evidence is missing or conflicting |

## 2. Document authority register

| Document | Declared status / role | Effective status proven by supplied set | Required resolution |
|---|---|---|---|
| `PROJECT_CONSTITUTION.md` | `Normative Draft`; target highest engineering authority | `PROPOSED`; not effective | owner adoption or accepted adoption ADR, adopted version/date/commit, conflict analysis |
| `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` | highest project technical operating standard according to `GOVERNANCE.md` | `DECLARED`; formal adoption record not supplied | confirm owner adoption, date, commit and version |
| `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md` | `PROPOSED_FOR_ADOPTION`; product and delivery constitution | `PROPOSED`; not effective | complete section 22 and reconcile with any adopted engineering constitution |
| `GOVERNANCE.md` | orientation map | descriptive only | keep synchronized with this register |
| `SECURITY.md` | mandatory security policy | document class declared; adoption evidence `UNKNOWN` | record owner/security approval and effective commit |
| `docs/governance/DOCUMENTATION_POLICY.md` | normative documentation policy | document class declared; adoption evidence `UNKNOWN` | record owner adoption and effective commit |
| `ARCHITECTURE.md` | accepted descriptive architecture | `DOCUMENTED_CURRENT` at cited baseline; acceptance record not supplied | link owner/ADR acceptance and refresh against live repository |
| `docs/architecture/TRUST_BOUNDARIES.md` | current and target trust-boundary inventory | `DOCUMENTED_CURRENT` at cited baseline | refresh on every material boundary change |
| `docs/product/CURRENT_CAPABILITIES.md` | current-state capability inventory | `DOCUMENTED_CURRENT` at `2026-08-03` baseline | query Git/tests/CI/runtime before using as live state |
| `CURRENT_PRODUCT_STATE.md` | dated evidence snapshot | `DOCUMENTED_CURRENT` at `2026-08-03` | regenerate after HEAD, worktree, test, CI, runtime or release change |
| `ROADMAP.md` | living delivery plan | planning authority only; no implementation proof | keep aligned with capability evidence |
| `docs/product/MVP_DELIVERY_MAP.md` | proposed product-delivery map | `PROPOSED`; phase evidence remains baseline-scoped | explicit owner adoption if this sequence is to govern delivery |

## 3. ADR status visible in the supplied set

These are document-supported claims, not a substitute for reading each ADR and current repository
history:

| Decision | Documented status | Exact boundary |
|---|---|---|
| ADR-0006 | owner-accepted and source/test `VERIFIED` | read-only deterministic PDG v1 projection; no runtime authorization authority |
| ADR-0007 | accepted and source/test `VERIFIED` | pure deterministic contract representation only |
| ADR-0008 | `PROPOSED`; review commit merged, owner decision required | target isolated Runner boundary; not runtime implementation |

A merged review commit does not change `PROPOSED` to `ACCEPTED`.

## 4. Temporary fail-closed operating interpretation

Until the project owner supplies complete adoption records:

1. binding legal, contractual, platform-security and safety requirements prevail;
2. do not weaken any security invariant from `SECURITY.md`;
3. use `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` as the declared technical operating standard;
4. apply accepted ADRs only within their exact scope;
5. treat `PROJECT_CONSTITUTION.md` and
   `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md` as proposals;
6. use architecture, capability and current-state documents only at their cited baseline;
7. treat unclear conflicts as `BLOCKED`.

This section is a reconciliation safeguard, not a substitute for owner adoption.

## 5. Canonical adoption record

Every normative, mandatory, constitutional or accepted artifact must eventually have:

```text
DOCUMENT:
VERSION:
DECLARED_STATUS:
EFFECTIVE_STATUS:
OWNER:
ADOPTION_METHOD:
ADOPTION_DATE:
ADOPTION_COMMIT:
CONTENT_SHA256:
SUPERSEDES:
CONFLICTS_RESOLVED:
NEXT_REVIEW:
```

An incomplete record cannot establish `ADOPTED`.

## 6. Required owner decisions

1. Adopt, revise or withdraw `PROJECT_CONSTITUTION.md`.
2. Confirm whether `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` is formally effective and record
   its adoption evidence.
3. Adopt, revise or withdraw `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md`.
4. Confirm adoption of `SECURITY.md` and `docs/governance/DOCUMENTATION_POLICY.md`.
5. Define the final order between the adopted engineering constitution, technical operating standard,
   mandatory policies and accepted ADRs.
6. Update `GOVERNANCE.md`, the documentation index and repository tests after each decision.
