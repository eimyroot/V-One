# Changelog

## Unreleased

### 2026-08-20 — Reconciliation candidate

- Reconciled the top-level product truth model after the trust-plane implementation advanced beyond
  the older roadmap/state documents.
- Corrected the Evidence UI so receipt/hash-chain integrity is shown as `PASS/FAIL` and a receipt no
  longer manufactures an independent `VERIFIED` outcome; independent verification fails closed to
  `UNKNOWN` until a VerificationResult binding is actually exposed.
- Corrected common-language Runner semantics: one-time ExecutionGrant consumption belongs to the
  control plane before Dispatch; Runner authority is bounded execution only.
- Registered `operation-proof/v2` and `operation-cell/v1` in the canonical VOP schema registry,
  added the canonical `OperationCell` noun/stage, and recorded the historical proof v1→v2 lineage.
- Added the canonical ProductComposition runtime seam with one shared ProductService database and
  `DatabasePermissionAuthority`; the explicit provider runtime pack remains absent/fail-closed by
  default and no canonical public operation endpoint is inferred.
- Added SQLite schema 14 workspace memberships so global role defines what an actor may do while exact
  current membership defines in which workspace that permission may be considered. Historical
  schema-13 workspaces are not silently backfilled.
- Revalidated current actor/global-role/workspace/environment/membership state inside the durable
  Grant store/one-time-consume serialization boundary so membership removal before consumption fails
  closed instead of surviving through a stale AuthorizationSnapshot.
- Extended the named VOP CI gate with reconciliation truth invariants and expanded product readiness
  to require the current authority/dispatch/Runner/verification/proof/cell contract set plus SQLite
  migrations through schema 14.
- Reconciled `CURRENT_PRODUCT_STATE.md`, `CURRENT_CAPABILITIES.md`, `ROADMAP.md`, `ARCHITECTURE.md`,
  `TRUST_BOUNDARIES.md`, VOP canonical vocabulary and this security overview around the distinction
  between component implementation, ProductComposition, live evidence, public truth surface and
  release/deployment state.
- Reconciled ADR-0015 and ADR-0017 from candidate-era `PROPOSED/unmerged` wording to their actual
  accepted/merged technical state while retaining review-independence and historical governance
  boundaries.
- Kept GitHub main enforcement `UNKNOWN/BLOCKED`: repository policy requires PR-only main and latest
  `ci/verify`, but current connector evidence does not prove the complete modern ruleset and classic
  required-status enforcement is observed off.
- Kept production effects disabled and made no release/deployment claim.

### 2026-08-17–19 — Authority, execution, verification and stable operation atom

- Added authoritative AuthorizationSnapshot creation prerequisites and durable Snapshot persistence.
- Added current `ExecutionGrant/v2`, durable grant persistence and one-time control-plane consumption
  evidence.
- Added transactional Dispatch Outbox, Dispatch Envelope, durable Inbox/dedup, ExecutionEpoch/Lease
  and durable current-fence/coordination contracts; SQLite schema advanced through migration `0013`.
- Added RunnerIdentity/RunnerBoundary, credential-broker decisions and isolated-runtime activation
  boundaries without making them an alternative authorization authority.
- Added live governed GitHub READ pilots (D4b), independent Verifier observation (E3) and canonical
  VerificationResult (E4b).
- Added bounded GitHub write controls and historical F4b CREATE_REF pilot evidence.
- Added historical F6b exact DELETE_REF rollback evidence: one provider mutation, no automatic retry,
  Runner+independent Verifier readback and `VERIFIED / OBSERVED_STATE_MATCH` outcome.
- Added `ExecutionReceipt/v2` while preserving `Receipt != VerificationResult` semantics.
- Added and accepted `OperationProof/v2`, including rollback-absence compatibility and canonical
  verification-lineage recomputation.
- Created the historical F6b `OperationProof/v2` instance with digest
  `40248a675287785778e1b0a8cc9ae9fd8fff12e869e820413f6fcea0ffcd1718`.
- Added and accepted minimal provider/lineage-neutral `OperationCell/v1`.
- Created the historical F6b `OperationCell/v1` instance with digest
  `2fc7de767018bdab8e08dcbfeffba988f16a4bc95694d2bf94b7854408e0a7b5`.
- Added Security Intelligence R-SI1.1 as an intelligence-only metadata/test layer; it does not issue
  authorization or bypass the canonical VOP lifecycle.
- Preserved historical PR #125 separate pre-merge merge-authorization provenance as `NOT VERIFIED`;
  later proof/cell evidence does not rewrite that governance fact.

### Earlier governance/runtime history retained

- Recorded explicit owner adoption of the exact ADR-0008 isolated Runner boundary design and bound
  threat model on 2026-08-08; design adoption did not itself authorize implementation or production
  effects.
- Recorded PR #54 / merge `57c7bf2277616c4445039865ac7cf81c5fada858` as a historical
  lifecycle-semantics documentation checkpoint.
- Retained `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` as the latest full local
  runtime-attested development checkpoint; it does not attest later source trees.

## 0.9.0-rc2-dev — unreleased

- Established a clean, review-gated repository baseline from the verified RC1 artifact.
- Pinned runtime and development dependency graphs with hashes.
- Made the product-image smoke gate parse health JSON with the built image Python runtime instead of
  an unqualified host `python` command.
- Added a truth-scoped project vision, architecture, roadmap, capability inventory, terminology,
  trust-boundary map and automated documentation consistency gate.
- Added a fail-closed local checkpoint verifier and deterministic ProofGraph v1 JSON projection.
- Proposed organization-scoped Solo, Team and Regulated approval profiles with a non-bypassable
  platform safety floor; no runtime activation was implied.
- Added a pure deterministic approval-policy decision model and a default-off compatibility path;
  Solo, Team and Regulated enforcement remain separately gated.
- Added least-privilege CI and a manually gated release-candidate build.
- Revalidated active account and current role on authenticated requests.
- Hardened sandbox writes with descriptor-relative/no-follow identity checks and bounded artifacts.
- Added request/payload/token/idempotency bounds and persistent authentication throttling.
- Replaced legacy bearer tokens with context-bound v2 sessions and a database-backed active-session
  allowlist with audited revocation.
- Separated constant-time liveness from explicit evidence-chain verification.
- Added structured allowlisted request/authentication events and suppressed raw Uvicorn access logs.
- Made CI/release vulnerability audits consume fully hashed dependency locks.
- Replaced implicit SQLite schema creation with ordered atomic checksum-recorded migrations.
- Added fail-closed unreleased PostgreSQL selection and a tested persistence boundary.
- Centralized application SQL in a classified statement catalog.
- Added trusted-host enforcement, CSP/no-store/browser security headers and production-only HSTS.
- Added execution idempotency, receipt sequencing, legacy execution leases/fencing and
  workspace-environment invariants.
- Bound release-candidate artifact names to source version, pinned workflow actions, smoke-tested the
  image and emitted source/SBOM checksums without overstating signer provenance.

This version remains **unreleased**. Changelog entries record implemented/history facts; they do not
constitute release, deployment or provider-effect authorization.
