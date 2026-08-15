# Current Capabilities

| Field | Value |
|---|---|
| Document status | Current-state inventory |
| Inventory audit date | `2026-08-03` |
| Inventory reconciliation base | `main@57c7bf2277616c4445039865ac7cf81c5fada858` |
| Exact live Git identity | See `CURRENT_PRODUCT_STATE.md` and query Git directly |
| Latest verified Git baseline | `main@57c7bf2277616c4445039865ac7cf81c5fada858` |
| Latest runtime-attested committed baseline | `main@d57d37111b8bc9471a136b6c618aad8e920f1aff` |
| Product version | `0.9.0-rc2-dev` |
| Release classification | Development baseline, not unrestricted production |
| Latest runtime evidence | `IMPLEMENTED_VERIFIED_LOCAL_POST_MERGE_CHECKPOINT`; 433 tests, readiness, dependency audit, product-image build and recorded smoke gate passed; production effects disabled |
| Latest runtime-evidence archive SHA-256 | `80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2` |
| PDG v1 evidence boundary | Owner-accepted and source/test VERIFIED; the `d57d371...` checkpoint includes its source/tests but does not provide runtime authorization authority or integration |
| ADR-0007 contract layer | Source/test VERIFIED pure deterministic execution-target, approval-evidence-set, grant, and receipt value objects |
| ADR-0008 lifecycle-semantics review | Exact commit `0fa69411...` published and merged via PR #54 as `57c7bf22...`; ADR remains PROPOSED |

## Reading this document

A capability may be VERIFIED for tests but not for unrestricted production. Evidence scope and
limitations are therefore part of every claim.

## Capability matrix

| Capability | Status | Current evidence | Current limitation |
|---|---|---|---|
| FastAPI `/api/v1` control plane | VERIFIED | system tests, composed application routes, and the `d57d371...` post-merge checkpoint | development-only; no release or deployment |
| Static command-center console | VERIFIED | product platform and HTTP tests | operator UX is a controlled-pilot surface |
| Local bootstrap and credential login | VERIFIED | authentication and bootstrap tests | no released external identity provider |
| Context-bound bearer sessions | VERIFIED | token, identity, and session lifecycle tests | local session model; enterprise OIDC is blocked |
| Active-session allowlist and revocation | VERIFIED | session lifecycle and user-account tests | instance-scoped administration |
| RBAC and independent approval | VERIFIED | service, composition, and product tests | roles are not workspace-scoped multi-tenant assignments |
| Workspace environment invariants | VERIFIED | service and migration tests | current backend is SQLite |
| Change-request lifecycle | VERIFIED | change-request tests | policy matrix is currently simpler than the target decision graph |
| Production dual-approval rule | VERIFIED | governance tests | production execution remains blocked |
| Execution idempotency | VERIFIED | idempotency tests | provider-level external idempotency is capability-specific and not generalized |
| Execution leases and fencing | VERIFIED | execution and recovery tests | no separate worker heartbeat |
| Indeterminate recovery under emergency stop | VERIFIED | recovery and operational-safety tests | requires operator investigation and explicit recovery |
| Emergency stop | VERIFIED | operational-safety and API tests | does not yet provide distributed runner cancellation |
| Sandbox file capability | VERIFIED | portable symlink and sandbox security tests | local control-plane host identity |
| Allowlisted validation presets | VERIFIED | adapter and execution tests | repository content still executes under the control-plane identity |
| Audit ledger | VERIFIED | audit and composition tests | no external signed anchor |
| Receipt ledger | VERIFIED | receipt and evidence tests | hash chaining is integrity evidence, not non-repudiation |
| Health and evidence separation | VERIFIED | platform-status tests | health does not prove historical evidence integrity |
| SQLite migrations and integrity gates | VERIFIED | migration tests | single-node pilot backend |
| Statement catalog | VERIFIED | statement-catalog tests | PostgreSQL statements are not released |
| PostgreSQL backend | BLOCKED | fail-closed startup and migration tests | implementation is intentionally unreleased |
| OIDC identity provider | BLOCKED | fail-closed identity-provider tests | no released OIDC login path |
| Local checkpoint verifier | VERIFIED | 8 targeted tests; real checkpoint verification | local filesystem only |
| ProofGraph v1 JSON | VERIFIED | deterministic module and launcher output | four node types; no persistent graph store |
| Nested manifest mutation detection | VERIFIED | verifier regression tests plus canonical `8a5f36b218c3aa6dce2e4cf771512875f136d839` checkpoint with zero warnings and zero nested mismatches | local checkpoint scope only |
| Repository-owned checkpoint finalizer | VERIFIED | targeted finalizer, verifier, filesystem-safety, and CLI tests | finalization remains explicit and separate from capture; release and remote publication remain separate |
| Repository-owned runtime candidate capture | VERIFIED | canonical `main@8a5f36b218c3aa6dce2e4cf771512875f136d839` capture→finalize→independent verify closure | local development runtime evidence; not release or deployment |
| ADR-0007 pure execution-contract value objects | VERIFIED | deterministic contract and binding tests; source/test evidence | no runtime authority, signing, issuer, or Runner consumption |
| V-One common language and operation semantics | IMPLEMENTED | deterministic `voodoo_product/operation_semantics.py`, canonical digest smoke, and system test inventory in `tests/system/test_operation_semantics.py` | semantic contract only; not API-integrated and not a runtime authorization gate |
| V-One operation proof contract | IMPLEMENTED | deterministic `voodoo_product/operation_proof.py`, isolated proof smoke, and invariant tests in `tests/system/test_operation_proof.py` | pure contract only; no persistent proof store, API endpoint, signer, or external verifier adapter |
| V-One skill orchestration contract | IMPLEMENTED | deterministic `voodoo_product/skill_orchestration.py`, local contract harness, and system test inventory in `tests/system/test_skill_orchestration.py` | planning contract only; no dynamic plugin trust, tool execution, approval, or runtime agent dispatch |
| V-One system control-plane decision contract | IMPLEMENTED | deterministic `voodoo_product/control_plane.py`, boundary document, and system test inventory in `tests/system/test_control_plane_contract.py` | contract layer only; no API endpoint, runtime dispatcher, production effect, or approval authority |
| Remote Drive byte verification | PROPOSED | none in product runtime | connector visibility is not byte-for-byte attestation |
| Signed checkpoints and receipts | PROPOSED | no production signing implementation | key identity, rotation, and trust policy required |
| Isolated runner capsules | PROPOSED | target architecture only | execution currently shares control-plane host identity |
| Signed execution grants | PROPOSED | target contract only | no grant issuer or verifier exists |
| Approval policy decision model | VERIFIED | focused policy and change-request tests | default-off runtime compatibility path only; current outcomes remain authoritative and Solo, Team, Regulated enforcement is not implemented |
| Read-only Policy Decision Graph v1 projection | VERIFIED | accepted ADR-0006; deterministic canonical graph/digest, focused/full tests, and inclusion in the `d57d371...` checkpoint source tree | caller-supplied unsigned snapshot; no persistence, API, runtime authorization authority, or execution gate |
| Policy Decision Graph | PROPOSED | ADR-0003 plus verified compatibility decision model | Solo, Team, Regulated, scoped roles, and runtime enforcement are not implemented |
| CyberCore read-only intake | PROPOSED | architectural boundary only | no integration endpoint or persistence |
| AI Change Copilot | PROPOSED | vision only | AI has no authorization authority |
| Multi-arch signed supply chain | PROPOSED | current Docker build is narrower | signing, provenance, and `linux/arm64` verification absent |
| Unrestricted production release | BLOCKED | production fail-closed gate | release, legal, runner, signing, and operations prerequisites missing |
| Public commercial distribution | BLOCKED | `LICENSE_DECISION_REQUIRED.md` | license, EULA, privacy, and support terms unresolved |

## Verified command surfaces

```text
HTTP:
  /api/v1/health
  /api/v1/bootstrap/status
  /api/v1/auth/bootstrap
  /api/v1/auth/login
  /api/v1/auth/logout
  /api/v1/me
  /api/v1/users
  /api/v1/workspaces
  /api/v1/command-center
  /api/v1/change-requests
  /api/v1/approvals
  /api/v1/executions
  /api/v1/evidence/receipts
  /api/v1/evidence/verify
  /api/v1/audit
  /api/v1/system/emergency-stop

Local CLI:
  voodoo evidence verify <checkpoint>
  voodoo evidence capture-runtime <new-candidate>
  voodoo evidence finalize <candidate> <destination>
  python -m voodoo_product evidence verify <checkpoint>
  python -m voodoo_product evidence capture-runtime <new-candidate>
  python -m voodoo_product evidence finalize <candidate> <destination>
```

## Current release boundary

The following remains true regardless of local test success:

```text
VOODOO_ALLOW_PRODUCTION_EFFECTS=false
RELEASE_VERIFIED=NO
```

A documentation update, local checkpoint, or successful smoke test cannot independently change that
state.

## Evidence update rule

Update this document whenever:

- a capability is added, removed, blocked, or released;
- the evidence scope changes;
- an ADR changes a trust boundary;
- a new checkpoint supersedes the stated repository baseline;
- a known limitation is removed or discovered.
