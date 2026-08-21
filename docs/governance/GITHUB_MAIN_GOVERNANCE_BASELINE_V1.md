# GitHub Main Governance Baseline v1

Status: PREPARED — repository-side contract with fail-closed live verifier

## Purpose

Define the minimum GitHub repository enforcement required before higher-impact V-One authority, Grant Issuer, Runner, release, or production-capable work may rely on GitHub as a governance boundary.

This document does not claim that GitHub Settings are already enforced. Remote enforcement must be verified independently against the live repository configuration.

## Canonical protected branch

`main`

## Required GitHub-side enforcement

The live repository must enforce all of the following on `main`:

1. changes reach `main` through a pull request;
2. the required GitHub check-run context is `verify` and must pass before merge;
3. the required `verify` context is pinned to the GitHub Actions App rather than allowing any source;
4. live evidence must additionally prove that the current `verify` check is produced by workflow `ci` at `.github/workflows/ci.yml` on the exact current `main` SHA;
5. required checks apply to the latest PR head before merge;
6. force pushes are disabled;
7. branch deletion is disabled;
8. conversation resolution is required before merge when review threads exist;
9. administrators do not silently bypass the baseline for ordinary development;
10. direct production/release authority is not implied by merge permission.

GitHub required status checks bind a check context and optional GitHub App source; they do not encode the workflow identity itself. V-One therefore treats workflow name/path as a separate live evidence property rather than falsely claiming the ruleset natively binds `ci`. If another GitHub Actions workflow emits the same required `verify` context on the observed current `main` SHA, G0 fails closed.

## Review-count policy

This repository currently has a single canonical CODEOWNER (`@nulleimy`). The baseline therefore does not invent a mandatory second human approval that the current organization cannot satisfy. PR-only flow plus required CI is mandatory. A future multi-maintainer organization may raise the approval threshold without weakening any existing control.

Product/runtime rule `no requester self-approval` remains a separate V-One authorization invariant and is not weakened by this repository-maintenance exception.

## Repository-side controls already present

- `.github/workflows/ci.yml` runs on every pull request and pushes to `main`;
- workflow `ci`, job/check context `verify`, executes lint, compile, focused security/governance gates, full pytest, product readiness, dependency audit, image build and smoke test;
- `.github/CODEOWNERS` assigns canonical ownership;
- `.github/pull_request_template.md` requires purpose, boundary, evidence, tests, rollback, non-scope and acceptance gates;
- `scripts/verify_github_main_governance.py` evaluates complete paginated live branch rules against `.github/governance/main-branch-baseline.v1.json` and independently resolves the observed Actions workflow identity for the required check;
- `.github/workflows/g0-governance-verify.yml` provides a read-only manual live-evidence run and retains JSON + SHA-256 evidence even when the verdict is fail-closed.

## Required verification evidence

P0 is complete only when live GitHub configuration evidence proves the desired state. Acceptable evidence must include:

```text
repository = nulleimy/V-One
branch = main
branch_head_sha = <exact current main sha>
pull_request_required = true
required_status_check = verify
required_check_provider = GitHub Actions
required_check_source_is_pinned = true
observed_required_workflow = ci
observed_required_workflow_path = .github/workflows/ci.yml
required_workflow_identity = true
latest_head_checks = true
force_push = false
delete_branch = false
conversation_resolution = true
ordinary_admin_bypass = false
bypass_evidence_complete = true
active_rule_pagination_complete = true
verified_at = <timestamp>
source = GitHub live repository settings/API
```

A repository document, CI pass, issue, PR description or previous observation is not sufficient evidence of GitHub-side enforcement.

## Machine verification

Canonical local/manual verification:

```bash
GITHUB_TOKEN=<governance-evidence-token> \
python scripts/verify_github_main_governance.py \
  --output g0-governance-evidence.json
```

The verifier:

1. resolves the exact live `main` SHA;
2. reads **all pages** of active rules applying to `main`;
3. follows every referenced repository/organization ruleset detail endpoint;
4. rejects incomplete `bypass_actors` evidence;
5. resolves all current `verify` GitHub Actions check runs on the exact `main` SHA;
6. follows their Actions run metadata and requires workflow `ci` at `.github/workflows/ci.yml`;
7. rejects required-check workflow collisions, stale workflow observations, any-source status checks and wrong integration bindings;
8. evaluates the machine baseline without mutating GitHub settings or serializing credential material.

The manual Actions workflow is:

```text
g0-governance-verify
```

For the workflow to prove the no-bypass requirement, repository secret
`VONE_GITHUB_GOVERNANCE_TOKEN` must contain a narrowly scoped governance-evidence credential that is
allowed to read complete ruleset details including `bypass_actors`. A normal public read or a token
whose API response omits `bypass_actors` is deliberately insufficient evidence.

The workflow always retains:

```text
g0-governance-evidence.json
g0-governance-evidence.sha256
```

The live verifier has three terminal states:

```text
VERIFIED = live evidence is complete and every required control is present
BLOCKED  = complete live evidence is readable but one or more required controls are absent
UNKNOWN  = live evidence is unavailable, incomplete or cannot prove a required property
```

Examples that MUST remain `UNKNOWN` rather than being silently promoted to PASS:

- GitHub API is unavailable;
- active-rule or check-run pagination cannot be completed;
- required `verify` provider or workflow identity cannot be independently resolved;
- ruleset detail omits `bypass_actors` because the evidence credential lacks sufficient access;
- a ruleset source cannot be resolved to its authoritative detail endpoint;
- exact current `main` SHA cannot be established.

Examples that are `BLOCKED` when evidence is otherwise complete:

- `verify` is not a required check;
- `verify` accepts any source or a non-GitHub-Actions integration;
- the observed current `verify` comes from a workflow other than `ci`, from another workflow path, or collides with another workflow emitting the same context;
- latest-head/strict checks are disabled;
- PR-only flow, force-push blocking, deletion blocking or thread resolution is absent;
- any bypass actor is configured.

Only `VERIFIED` exits successfully. `BLOCKED` and `UNKNOWN` fail closed. A historical PASS is not reusable proof after GitHub ruleset/settings configuration changes.

## Credential boundary

The governance-evidence token is read-only from the workflow's perspective: the verifier performs GET requests only. The token is not printed, written to the evidence JSON, persisted in artifacts or made available to repository checkout credentials.

The dedicated token exists only because GitHub may omit sensitive `bypass_actors` from ruleset detail responses unless the caller has sufficient access. Missing sensitive fields are evidence incompleteness, never proof of an empty bypass list.

## Failure semantics

If live protection cannot be read or completely verified:

```text
GITHUB_SETTINGS_ENFORCED = UNKNOWN
P0 = BLOCKED
```

If complete live protection evidence is readable but weaker than this baseline:

```text
GITHUB_SETTINGS_ENFORCED = BLOCKED
P0 = BLOCKED
```

Never convert `UNKNOWN` or `BLOCKED` into `PASS` from documentation intent, CI success or branch metadata alone.

## Change path

Changes to this baseline use a PR and must not reduce the controls above without explicit owner authorization, documented rationale, risk analysis and replacement controls.

## Exit gate

```text
REPO_ENFORCEMENT_CONTRACT = VERIFIED
GITHUB_SETTINGS_ENFORCED = VERIFIED
MAIN_PR_ONLY = VERIFIED
REQUIRED_CI = VERIFIED
REQUIRED_CI_PROVIDER = VERIFIED
REQUIRED_CI_WORKFLOW_IDENTITY = VERIFIED
LATEST_HEAD_CHECKS = VERIFIED
FORCE_PUSH_DISABLED = VERIFIED
BRANCH_DELETE_DISABLED = VERIFIED
CONVERSATION_RESOLUTION = VERIFIED
BYPASS_EVIDENCE_COMPLETE = VERIFIED
ORDINARY_ADMIN_BYPASS_DISABLED = VERIFIED
P0_GITHUB_GOVERNANCE = PASS
```

Until all fields are proven, authority/Runner work may be designed or prepared but must not treat GitHub enforcement as a trusted completed boundary.
