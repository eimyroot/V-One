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
3. `verify` is produced by the GitHub Actions workflow named `ci`; GitHub UI may display workflow/job together, but protection must bind the actual check context reported by GitHub;
4. required checks apply to the latest PR head before merge;
5. force pushes are disabled;
6. branch deletion is disabled;
7. conversation resolution is required before merge when review threads exist;
8. administrators do not silently bypass the baseline for ordinary development;
9. direct production/release authority is not implied by merge permission.

## Review-count policy

This repository currently has a single canonical CODEOWNER (`@nulleimy`). The baseline therefore does not invent a mandatory second human approval that the current organization cannot satisfy. PR-only flow plus required CI is mandatory. A future multi-maintainer organization may raise the approval threshold without weakening any existing control.

Product/runtime rule `no requester self-approval` remains a separate V-One authorization invariant and is not weakened by this repository-maintenance exception.

## Repository-side controls already present

- `.github/workflows/ci.yml` runs on every pull request and pushes to `main`;
- workflow `ci`, job/check context `verify`, executes lint, compile, focused security/governance gates, full pytest, product readiness, dependency audit, image build and smoke test;
- `.github/CODEOWNERS` assigns canonical ownership;
- `.github/pull_request_template.md` requires purpose, boundary, evidence, tests, rollback, non-scope and acceptance gates;
- `scripts/verify_github_main_governance.py` evaluates live active branch rules against `.github/governance/main-branch-baseline.v1.json`;
- `.github/workflows/g0-governance-verify.yml` provides a read-only manual live-evidence run.

## Required verification evidence

P0 is complete only when live GitHub configuration evidence proves the desired state. Acceptable evidence must include:

```text
repository = nulleimy/V-One
branch = main
pull_request_required = true
required_status_check = verify
required_check_provider = GitHub Actions / workflow ci
force_push = false
delete_branch = false
conversation_resolution = true
ordinary_admin_bypass = false
verified_at = <timestamp>
source = GitHub live repository settings/API
```

A repository document, CI pass, issue, PR description or previous observation is not sufficient evidence of GitHub-side enforcement.

## Machine verification

Canonical local/manual verification:

```bash
python scripts/verify_github_main_governance.py \
  --output g0-governance-evidence.json
```

The verifier reads the active rules applying to `main` through GitHub REST, follows the referenced rulesets and evaluates the machine baseline. It never mutates GitHub settings and never serializes credential material.

The manual Actions workflow is:

```text
g0-governance-verify
```

The live verifier has three terminal states:

```text
VERIFIED = live evidence is readable and every required control is present
BLOCKED  = live evidence is readable but one or more required controls are absent
UNKNOWN  = live evidence cannot be obtained or trusted
```

Only `VERIFIED` exits successfully. `BLOCKED` and `UNKNOWN` fail closed. A historical PASS is not reusable proof after the GitHub ruleset/settings configuration changes.

## Failure semantics

If live protection cannot be read or verified:

```text
GITHUB_SETTINGS_ENFORCED = UNKNOWN
P0 = BLOCKED
```

If live protection is readable but weaker than this baseline:

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
FORCE_PUSH_DISABLED = VERIFIED
BRANCH_DELETE_DISABLED = VERIFIED
CONVERSATION_RESOLUTION = VERIFIED
ORDINARY_ADMIN_BYPASS_DISABLED = VERIFIED
P0_GITHUB_GOVERNANCE = PASS
```

Until all fields are proven, authority/Runner work may be designed or prepared but must not treat GitHub enforcement as a trusted completed boundary.
