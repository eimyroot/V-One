# VOODOO Engineering Constitution

| Field | Value |
|---|---|
| Document ID | VES-000 |
| Version | 1.0.0-draft |
| Status | Normative Draft |
| Authority | Highest Engineering Authority |
| Owner | Chief Architecture Office |
| Applies to | Entire repository |
| Review cycle | Quarterly and after material incidents |

> The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** are normative.

## 1. Purpose

This Constitution defines the highest engineering authority for VOODOO OS and all derived VOODOO engineering projects.

Its purpose is to preserve security, architectural integrity, operational resilience, auditability, maintainability, and controlled evolution.

## 2. Order of authority

The governing order is:

1. `PROJECT_CONSTITUTION.md`
2. approved Architecture Decision Records
3. normative governance standards
4. mandatory policies
5. approved procedures
6. implementation documentation
7. source code

Lower-authority artifacts MUST NOT silently contradict higher-authority artifacts.

## 3. Core principles

Engineering decisions MUST prioritize:

1. correctness over speed,
2. security over convenience,
3. simplicity over cleverness,
4. reuse over creation,
5. explicit behavior over hidden behavior,
6. deterministic behavior over implicit magic,
7. auditability over undocumented operation,
8. recovery over irreversible mutation,
9. long-term coherence over local optimization.

## 4. Single source of truth

Every cross-cutting concern MUST have exactly one authoritative owner.

Parallel authoritative implementations are prohibited.

Before creating a service, registry, manager, provider, policy engine, configuration loader, secret loader, client factory, persistence abstraction, or equivalent platform component, the repository MUST be searched for an existing owner.

## 5. Governance before code

Material implementation MUST NOT begin before:

1. repository discovery,
2. reuse analysis,
3. architectural impact analysis,
4. security impact analysis,
5. verification planning,
6. rollback planning.

## 6. Fail-closed security

Security-sensitive failures MUST fail closed.

Production secrets MUST NOT have literal defaults.

Missing, malformed, weak, revoked, or prohibited security configuration MUST prevent the affected capability from starting or operating.

Security checks MUST NOT degrade silently into warnings when enforcement is required.

## 7. Configuration ownership

Runtime configuration MUST be resolved and validated through an authoritative configuration layer.

Security-sensitive modules MUST NOT independently invent environment-variable parsing, fallback values, validation rules, or key derivation.

## 8. Layer integrity

Dependencies MUST follow documented layer boundaries.

Circular dependencies, hidden service locators, cross-layer shortcuts, and unauthorized reverse dependencies are prohibited.

## 9. AI engineering behavior

AI contributors MUST:

1. inspect before generating,
2. search before creating,
3. reuse before duplicating,
4. disclose assumptions,
5. provide verification,
6. provide rollback,
7. distinguish performed work from proposed work.

AI contributors MUST NOT claim to have inspected, executed, modified, tested, committed, or deployed anything they did not actually access or run.

## 10. Verification

A change is not complete merely because code exists.

Applicable tests, architecture checks, security checks, documentation updates, operational evidence, and rollback instructions MUST be provided.

## 11. Observability and auditability

Production capabilities MUST expose sufficient structured evidence to reconstruct material decisions and failures without exposing protected secrets or sensitive payloads.

Silent failure paths are prohibited.

## 12. Technical debt

Technical debt MUST be visible, owned, risk-assessed, and assigned a removal or review milestone.

Temporary code MUST NOT become permanent through omission.

## 13. Architectural decisions

Material changes to architecture, trust boundaries, security controls, persistence models, public contracts, or cross-cutting platform ownership MUST be recorded in an ADR before or with implementation.

## 14. Exceptions

A constitutional exception requires:

1. an approved ADR,
2. explicit scope,
3. named owner,
4. risk assessment,
5. expiration or review date,
6. rollback or remediation plan.

Emergency action MAY precede documentation only when necessary to contain an active incident. The decision MUST be documented immediately afterward.

## 15. Definition of done

Work is complete only when all applicable conditions hold:

- implementation is complete,
- tests pass,
- security requirements pass,
- architecture remains compliant,
- documentation is updated,
- operational evidence exists,
- rollback is defined,
- CI succeeds,
- temporary exceptions are documented.

## 16. Amendment

This Constitution MAY be amended only through a reviewed ADR and repository-wide compatibility analysis.

No amendment may silently weaken an existing security or auditability guarantee.

## 17. Final rule

Every accepted change MUST leave the system at least as understandable, secure, recoverable, and governable as it was before.
