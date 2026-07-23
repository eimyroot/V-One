# Contribution and patch policy

## Required flow

1. Create a focused branch from `main`.
2. Keep production effects disabled.
3. Add or update tests for every behavior change.
4. Open a pull request using the repository template.
5. Require green CI and owner review before merge.

## Risk classes

| Class | Examples | Merge requirement |
| --- | --- | --- |
| R0 | Documentation, comments | Green CI + owner oversight |
| R1 | Tests, internal refactor without behavior change | Green CI + owner oversight |
| R2 | API behavior, adapters, dependency updates | Green CI + explicit owner approval |
| R3 | Authentication, authorization, persistence, audit, CI/release | Green CI + explicit owner approval + rollback evidence |
| R4 | Production effects, destructive migration, public API break | Separate design review and explicit release authorization |

Automation may classify and verify a patch. It must not approve its own R2–R4 change or bypass
branch protection.

## Documentation changes

- Use only the capability states `VERIFIED`, `IMPLEMENTED`, `PROPOSED`, `INFERRED`, `UNKNOWN`, and
  `BLOCKED`.
- Update `docs/product/CURRENT_CAPABILITIES.md` when current behavior or evidence changes.
- Update `ROADMAP.md` and `docs/product/TARGET_CAPABILITIES.md` when accepted future scope changes.
- Record material architecture or trust-boundary changes in an ADR.
- Keep runtime logs, databases, secrets, and generated evidence outside the Git worktree.
- Follow `docs/governance/DOCUMENTATION_POLICY.md`; roadmap and vision text are not implementation
  evidence.
