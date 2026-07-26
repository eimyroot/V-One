# ADR-0003: Organization roles and configurable approval policy

| Field | Value |
|---|---|
| Status | PROPOSED |
| Date | 2026-07-24 |
| Decision owner | Repository owner with architecture and security review |
| Scope | Organization authorization, scoped roles, and approval-policy evaluation |
| Risk class | R3 authorization design |
| Runtime effect | None; this ADR does not change current approval behavior |

## Context

VOODOO One currently enforces global roles, requester/approver separation, and stronger approval
requirements for production requests. Those controls are secure defaults, but one fixed rule does not
fit every deployment.

A solo owner, a small team, and a regulated organization need different authorization and approval
policies. Requiring two accounts for every low-risk local operation creates friction without meaningful
independence when one person controls both accounts. Allowing unrestricted self-approval for
production or destructive operations would weaken the product's safety model.

The product therefore needs two distinct policy layers:

1. **Customer-owned organizational policy** — the organization decides which principals receive
   which roles and capabilities within explicit scopes.
2. **Platform-enforced safety floor** — VOODOO One rejects configurations and decisions that would
   make critical operations unsafe, misleading, or unauditable.

This decision extends the proposed Policy Decision Graph. It does not claim that organizations,
workspace-scoped roles, configurable profiles, or a policy evaluator are currently implemented.

## Decision

VOODOO One will support organization-scoped authorization and configurable approval policies with
three built-in profiles:

- **Solo**;
- **Team**;
- **Regulated**.

An organization may assign users, groups, service accounts, and AI principals to scoped roles and
capabilities. It may tighten any built-in rule. It may relax a rule only down to the platform safety
floor.

The eventual approval requirement will be computed by a deterministic, versioned policy evaluator
from governed inputs. Environment alone will not be the complete policy input.

Until a separately reviewed implementation enables this design, current approval behavior remains
authoritative.

## Customer-owned authorization

An organization owner may eventually configure:

- members and groups;
- workspace membership;
- role assignments per workspace;
- capability grants;
- target and environment restrictions;
- approval thresholds;
- financial or resource limits;
- time windows;
- step-up authentication requirements;
- a built-in profile and organization-specific overrides.

Authorization grants are scoped. A role name without its organization, workspace, target,
environment, and capability scope is insufficient for an operational decision.

## Platform safety floor

The following controls cannot be disabled by an organization profile or override:

1. AI, service, and runner principals cannot authorize their own proposals or executions.
2. Authorization is bound to the exact request payload or immutable artifact digest.
3. A relevant request, target, pre-state, or policy change invalidates prior authorization.
4. Multiple required approvals must come from distinct eligible identities.
5. Accounts mapped to the same verified human subject do not satisfy a two-person requirement.
6. Mutating production operations cannot run with zero human authorization.
7. Destructive or broad-impact operations cannot be reduced below the platform minimum.
8. Role, membership, profile, and policy changes are audited.
9. A principal cannot authorize a privilege escalation or policy relaxation in the same transaction
   that grants the principal the required authority.
10. Expired, revoked, stale, or drifted authorization cannot permit execution.
11. Production effects remain fail-closed until a separate governed release enables them.
12. Every decision is reproducible from canonical inputs and a versioned policy.

The safety floor is product behavior, not a UI convention.

## Principal model

The policy model distinguishes principal type from assigned role.

Initial principal types:

- `human`;
- `service`;
- `ai_agent`;
- `runner`;
- `organization_owner`;
- `platform_administrator`.

Examples:

- an `ai_agent` may receive `change_request.create`;
- it cannot receive authority to approve its own request;
- a `runner` may consume a short-lived execution grant;
- a `runner` cannot create or approve requests;
- an `organization_owner` manages organization policy but remains subject to the safety floor;
- a `platform_administrator` manages the VOODOO One instance and is not automatically an operator
  in every customer workspace.

## Scope model

Authorization is evaluated against:

- organization;
- workspace;
- target;
- environment;
- capability;
- risk level;
- blast radius;
- reversibility;
- data sensitivity;
- optional monetary or resource limit;
- time window;
- request or artifact digest;
- policy version.

Global roles remain only for instance-level platform administration. Operational roles become
organization- and workspace-scoped.

## Authorization modes

The product distinguishes these outcomes:

- `AUTOMATIC_POLICY_ALLOW` — no human action is required because the operation is read-only and
  satisfies the safety floor;
- `OWNER_CONFIRMATION` — one owner confirms a low-risk operation without claiming independent
  review;
- `INDEPENDENT_APPROVAL` — an eligible principal other than the requester authorizes the operation;
- `MULTI_PARTY_APPROVAL` — multiple distinct eligible human identities are required;
- `DENY` — execution is not eligible under the effective policy.

Calling owner confirmation an independent approval is prohibited. Evidence and UI must preserve the
difference.

## Built-in profiles

Profiles are safe defaults, not unrestricted policy languages.

### Solo

Intended for one owner-operated organization.

| Risk | Default policy |
|---|---|
| R0 | Automatic policy allow for read-only operations |
| R1 | Owner confirmation for local, bounded, and reversible operations |
| R2 | Owner confirmation plus successful preflight and optional step-up authentication |
| R3 | Denied until an independent eligible approver is configured |
| R4 | Denied |

Solo mode never represents two accounts controlled by one verified human as independent authority.
Production effects remain disabled unless a separate release gate is satisfied.

### Team

Intended for small and medium organizations.

| Risk | Default policy |
|---|---|
| R0 | Automatic policy allow for read-only operations |
| R1 | One eligible human; organization policy chooses owner confirmation or independent approval |
| R2 | One eligible human plus successful preflight |
| R3 | Operator plus security reviewer, distinct identities |
| R4 | Two distinct eligible humans, step-up authentication, rollback plan, and change window |

A Team organization may tighten R0-R2. It cannot weaken R3-R4 below the safety floor.

### Regulated

Intended for high-assurance or regulated operations.

Defaults include:

- strict separation of duties;
- mandatory MFA or step-up authentication;
- approval expiration;
- restricted change windows;
- stronger evidence-retention requirements;
- minimum two-person authorization for high-risk changes;
- explicit data classification and target ownership checks;
- no owner confirmation for mutating operations.

## Canonical policy input

A future evaluator uses a canonical, versioned input. The following example is illustrative and does
not establish the final wire schema:

```json
{
  "principal": {
    "id": "usr_...",
    "type": "human",
    "organization_id": "org_...",
    "workspace_roles": ["operator"]
  },
  "request": {
    "id": "cr_...",
    "requester_id": "usr_...",
    "workspace_id": "ws_...",
    "target_id": "target_...",
    "environment": "local",
    "risk": "R1",
    "capability": "echo.execute",
    "blast_radius": "single_workspace",
    "reversibility": "fully_reversible",
    "payload_digest": "sha256:...",
    "artifact_digest": null
  },
  "context": {
    "profile": "solo",
    "policy_version": "approval-policy/v1",
    "preflight_status": "passed",
    "production_effects_enabled": false
  }
}
```

An explainable result may contain:

```json
{
  "decision": "ALLOW_AFTER_AUTHORIZATION",
  "authorization_mode": "OWNER_CONFIRMATION",
  "required_approvals": 1,
  "required_roles": ["organization_owner"],
  "distinct_identities": 1,
  "requester_may_confirm": true,
  "step_up_required": false,
  "expires_in_seconds": 900,
  "reason_codes": [
    "PROFILE_SOLO",
    "LOCAL_ENVIRONMENT",
    "RISK_R1",
    "FULLY_REVERSIBLE"
  ]
}
```

The final contract requires a separate specification with canonical serialization, compatibility,
and digest test vectors.

## Policy precedence

Evaluation order, from highest authority to lowest:

1. platform safety floor;
2. regulatory or deployment constraints;
3. organization profile;
4. organization overrides;
5. workspace overrides;
6. target-specific restrictions;
7. request-specific facts;
8. explicit deny rules;
9. explicit allow rules.

`DENY` wins over `ALLOW` at the same or lower authority level.

## Approval and confirmation binding

Every human authorization must bind to:

- request ID;
- payload digest;
- artifact digest when present;
- workspace and target;
- environment;
- capability;
- risk;
- effective policy version;
- pre-state digest when available;
- authorization mode;
- expiration time;
- actor identity;
- authentication assurance level.

Changing any governed field invalidates the authorization.

## Proposed data model

Potential entities include:

- `organizations`;
- `organization_memberships`;
- `groups`;
- `group_memberships`;
- `workspace_memberships`;
- `role_definitions`;
- `role_assignments`;
- `capability_grants`;
- `approval_profiles`;
- `approval_policy_versions`;
- `approval_policy_rules`;
- `policy_decisions`;
- `approval_requirements`;
- `identity_assurance_events`.

This ADR does not approve a database migration. The first implementation slice introduces only a
pure policy contract and evaluator that reproduces current behavior.

## Proposed API and UI

Future API surfaces may include:

- organization membership management;
- workspace role assignment;
- capability-grant management;
- profile selection;
- policy preview or simulation;
- approval-requirement explanation;
- policy-decision audit lookup.

The console should eventually show:

- the selected profile;
- the effective role and scope;
- why authorization is required;
- who may authorize;
- whether owner confirmation is permitted;
- which safety-floor rule prevents a weaker configuration;
- which input change would invalidate authorization.

Policy preview is read-only and cannot grant authority or mutate policy state.

## Migration plan

### Phase 0 — specification only

- review and accept or reject this ADR;
- define canonical policy input and output;
- define safety-floor reason codes;
- make no runtime behavior change.

### Phase 1 — deterministic evaluator preserving current behavior

- implement a pure policy evaluator;
- map current behavior to an implicit Team-compatible policy;
- preserve current database and API outcomes;
- emit decision explanations;
- keep new enforcement behind a default-off feature flag.

### Phase 2 — Solo profile for local R0 and R1

- permit owner confirmation only for local, bounded, and reversible operations;
- keep production effects disabled;
- prove R3 and R4 remain denied without independent authority;
- audit every profile and policy change.

### Phase 3 — organization and workspace scopes

- add organizations and memberships;
- migrate operational roles to scoped assignments;
- keep platform administration separate;
- require backward-compatible migration and rollback evidence.

### Phase 4 — Team and Regulated enforcement

- add step-up authentication hooks;
- add approval expiration and change windows;
- add target- and capability-specific policies;
- retain immutable policy-decision evidence.

## Verification strategy

### Unit tests

- identical canonical input produces identical output;
- the safety floor overrides weaker organization settings;
- payload-digest change invalidates authorization;
- AI and service self-authorization is denied;
- distinct-identity requirements are enforced;
- policy precedence and explicit deny behavior are stable;
- reason codes are deterministic.

### Contract tests

- canonical input and output schemas;
- policy-version compatibility;
- serialization and digest test vectors.

### Integration tests

- Solo R1 local echo can use owner confirmation;
- Solo R3 remains denied without an independent approver;
- Team R3 requires operator and security reviewer identities;
- Regulated R4 requires two distinct humans and step-up authentication;
- policy change creates an audit event;
- request mutation or target drift invalidates authorization.

### Security tests

- two accounts mapped to one verified human cannot satisfy two-person control;
- service and AI principals cannot grant human authorization;
- role escalation cannot authorize its own policy change;
- stale or revoked membership cannot authorize;
- policy simulation cannot mutate state.

## Rollback strategy

- keep current approval behavior as the fallback implementation;
- guard future evaluation with a feature flag during migration;
- do not delete legacy role fields until migration is verified;
- make schema migrations additive before any removal;
- preserve policy-decision records and audit events;
- rollback by disabling the evaluator and restoring current implicit behavior.

## Consequences

### Positive

- organizations control who receives which operational authority;
- low-risk owner-operated workflows avoid fake two-account security;
- higher-risk operations retain meaningful independent authorization;
- authorization strength aligns with risk and context;
- scoped capability grants improve least privilege;
- decisions become explainable and reproducible.

### Negative and residual

- policy complexity can create configuration mistakes;
- detecting common human control requires identity-assurance data;
- organization owners may misunderstand the safety floor;
- scoped authorization and migration add significant test burden;
- step-up authentication is unavailable until the identity layer is extended.

## Non-goals

This ADR does not authorize:

- enabling production effects;
- unrestricted customer-supplied policy code;
- arbitrary shell execution;
- replacing the current identity provider;
- adding PostgreSQL or multi-region operation;
- treating AI as an approval authority;
- weakening audit, receipt, emergency-stop, lease, or fencing controls;
- claiming organization tenancy is implemented.

## Alternatives considered

### Keep one fixed approval rule

Rejected because it is too restrictive for solo and local use and too inflexible for regulated
organizations.

### Let customers disable every safeguard

Rejected because unsafe configurations would undermine the product's purpose and create misleading
security claims.

### Require two users for every mutation

Rejected because it creates friction and false separation in owner-operated environments.

### Encode profiles only in the UI

Rejected because authorization must be enforced in backend policy and persistence boundaries.

## Acceptance criteria

This ADR may move from `PROPOSED` to `Accepted` only when:

- the safety floor is explicitly approved;
- Solo, Team, and Regulated semantics are accepted;
- the principal and scope models are accepted;
- migration from current behavior is documented;
- the first implementation slice remains limited to a pure evaluator and tests;
- production effects remain disabled;
- no claim is made that organization tenancy is already implemented.

## First implementation slice

Add a pure, deterministic approval-policy evaluator that reproduces current behavior and emits an
explainable decision object.

Suggested commit:

```text
feat(policy): add deterministic approval policy decision model
```

This slice must not change current approval outcomes. Enabling Solo, Team, or Regulated behavior
requires a separate reviewed change.
