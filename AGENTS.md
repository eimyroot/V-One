# VOODOO One Agent Operating Contract

## Scope and authority

This file applies to the entire repository tree rooted at
`/Users/eimyna/00_DEV/V-ONE`. A more deeply nested `AGENTS.md` may narrow these
rules only for a demonstrated subtree-specific need. Direct system, developer,
and user instructions take precedence.

Before every technical task:

1. Verify that `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` exists.
2. Compute its SHA-256 and require
   `36d2798f377ee5e6ba05ea8a565fc053ad58182d95a3af4f466050d536285bed`.
3. Read the task-relevant sections before work.
4. Before implementation, architecture or security changes, remote writes,
   releases, or destructive operations, read the entire file.
5. For product or delivery decisions, also inspect
   `VOODOO_PRODUCT_DECISION_DELIVERY_CONSTITUTION.md`.

Stop as `BLOCKED` without modifying files if the engineering constitution is
missing, unreadable, incomplete, or has a different digest.

Use these status terms precisely:

- `VERIFIED`: directly observed in current evidence.
- `IMPLEMENTED`: changed in the current work, but not necessarily fully verified.
- `PROPOSED`: designed or recommended, not implemented.
- `INFERRED`: derived from evidence but not directly observed.
- `UNKNOWN`: evidence is unavailable.
- `BLOCKED`: safe progress cannot continue.

Do not use `COMPLETE` without verifiable evidence that every relevant completion
condition is satisfied.

## Canonical repository and evidence paths

- Repository: `/Users/eimyna/00_DEV/V-ONE`
- Durable evidence: `/Users/eimyna/00_DEV/V-ONE-EVIDENCE`

Keep generated logs, runtime data, databases, checkpoints, audit output, and
other evidence outside the repository unless the task explicitly requires a
repository-owned artifact. Use a task-specific evidence subdirectory and never
store secrets or unnecessary personal data.

## Required reality check

Before technical modifications, identify the goal, known state, primary risk,
smallest safe path, and which claims are verified versus assumed. Run:

```bash
pwd
git status --short --branch
git rev-parse --show-toplevel
git rev-parse HEAD
git remote -v
git log -5 --oneline
git diff --check
git diff --stat
```

Never claim these checks, a clean worktree, a test result, runtime behavior,
deployment, publication, or release unless it was actually observed.

## Source-of-truth hierarchy

Resolve conflicts using:

1. current repository content;
2. actual Git state and history;
3. executed tests and command output;
4. observed runtime configuration and behavior;
5. CI/CD workflow and produced artifacts;
6. accepted ADRs and technical documentation;
7. README, roadmap, vision, and declared intent.

Documentation and historical evidence do not prove current behavior. Preserve
explicit `VERIFIED`, `IMPLEMENTED`, `PROPOSED`, `INFERRED`, `UNKNOWN`, and
`BLOCKED` boundaries.

## Git and worktree safety

- Inspect existing changes before editing and preserve all user work.
- Never reset, clean, stash, checkout over, or otherwise discard unknown work.
- Keep each change focused, reviewable, reversible, and free of unrelated
  refactoring.
- Preserve the repository's local-only push protection.
- Use the repository-owned review publication mechanism documented in
  `docs/governance/REVIEW_BRANCH_PUBLICATION.md`; do not substitute a direct
  push or weaken the hook.
- Do not force-push, rewrite history, merge, release, deploy, rotate secrets,
  change licenses, break public APIs, modify production infrastructure or data,
  or disable security controls without explicit authorization.
- Remote publication, merge, release, and deployment are separate authorization
  boundaries. Authorization for one does not authorize another.

Before and after a change, run `git diff --check`, `git diff --stat`, and
`git status --short --branch`. Review the complete scoped diff before reporting.

## Change discipline

- Inspect callers, tests, configuration, documentation, and trust boundaries
  before changing an owner.
- Search for an existing capability before creating a new abstraction, service,
  registry, provider, configuration path, or dependency.
- Prefer the smallest coherent vertical slice and existing dependencies.
- Keep production and local configuration separate.
- Add behavior tests for behavior changes and a regression test for a bug fix
  where feasible.
- Update documentation only when behavior, a contract, architecture, operations,
  or evidenced capability status changes.
- State impact, verification, limitations, rollback, and a focused Conventional
  Commit message for implementation work.

## Architecture boundaries

The current implementation is a Python 3.12 FastAPI modular monolith in
`voodoo_product/`, with system tests in `tests/system/`, operational tooling in
`scripts/`, and governance/product documentation in the repository root and
`docs/`.

Preserve these evidenced boundaries:

- VOODOO One owns identity, policy, approvals, execution lifecycle, operational
  safety, persistence, audit, receipts, and checkpoint verification.
- SQLite is the current implemented and supported persistence boundary;
  unreleased backends fail closed.
- Current execution adapters are narrow local capabilities and share the
  control-plane identity; an isolated runner is target architecture, not current
  behavior.
- Checkpoint verification is read-only and must not execute checkpoint-provided
  code.
- CyberCore or other intelligence sources may propose; they do not own
  authorization, approval, execution evidence, or shared persistence.

Do not freeze incidental implementation details into governance. Material
changes to architecture, trust boundaries, security controls, persistence,
public contracts, or cross-cutting ownership require an ADR and the applicable
owner review.

## Security boundaries

- Preserve deny-by-default, least privilege, requester/approver separation, and
  fail-closed behavior.
- Keep production effects disabled unless separately authorized by actual
  released product policy and current evidence.
- Never place secrets in source, evidence, logs, command output, or Git history.
- Do not introduce arbitrary shell execution from untrusted input.
- Preserve sandbox confinement, reviewed SQL ownership, session and identity
  boundaries, evidence integrity checks, execution idempotency, leases, fencing,
  and recovery controls relevant to the touched area.
- Do not describe proposed controls as implemented or invent controls absent
  from the repository.

Authentication, authorization, persistence, execution, evidence, release, and
production-effect changes are high risk. They require targeted regression tests,
broader relevant gates, explicit rollback evidence, and independent review when
required by project policy.

## Validation and testing

Use the locked Python 3.12 development environment. Install dependencies only
when authorized:

```bash
python -m pip install --require-hashes -r requirements-dev.lock
```

Apply validation proportionally:

- Documentation or governance only: `git diff --check`; inspect links, commands,
  paths, status claims, and the complete diff. Run
  `python -m pytest -q tests/system/test_project_documentation.py` when core
  documentation, navigation, capability states, or governance authority may be
  affected.
- Python or internal tooling: run `python -m ruff check` on touched paths,
  `python -m compileall -q` on affected Python packages or scripts, and focused
  `python -m pytest -q` tests for the changed behavior.
- Cross-cutting or high-risk behavior: run the focused tests first, then the
  full relevant repository gates when blast radius warrants:

```bash
python -m ruff check .
python -m compileall -q voodoo_product scripts tests
node --check voodoo_product/static/app.js
python -m pytest -q
python scripts/product_readiness_gate.py
```

Release and supply-chain work may additionally require the locked dependency
audit, image build, and smoke commands defined in the current GitHub workflows.
Do not run release, Docker, network, or production-affecting operations merely
for appearance of completeness.

Report every command actually run, its result, and every relevant check not run
with the reason. A passing historical or focused test is not evidence that
unexecuted broader gates pass.

## Documentation

Follow `docs/governance/DOCUMENTATION_POLICY.md`. Documentation must distinguish
current from target state and must not claim unimplemented behavior, current
runtime health, production readiness, release, or deployment without direct
evidence. README and roadmap statements are not implementation evidence.

## Evidence and auditability

For important audits and security, release, publication, or destructive work,
record exact source identity, commands, exit results, limitations, and rollback
under `/Users/eimyna/00_DEV/V-ONE-EVIDENCE/<task-specific-directory>`. Preserve
Git and evidence identity. Do not commit generated evidence unless the
repository contract explicitly requires it.

## Commit and rollback requirements

Do not commit, push, create a pull request, merge, release, or deploy unless the
user explicitly authorizes that action. Before an authorized commit, confirm
that the diff is scoped and verification evidence is current. Prefer one logical
responsibility per Conventional Commit.

Rollback must be explicit and safe. Never propose destructive rollback over
unknown work. Prefer reverting the focused patch or commit; data and production
rollback require separate authorization and evidence.

## Final response contract

End every technical task with:

```text
STATUS:
VERIFIED:
NOT VERIFIED:
CHANGED:
RISKS:
NEXT SAFE STEP:
```
