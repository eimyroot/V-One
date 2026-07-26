# VOODOO One Foundations

| Field | Value |
|---|---|
| Document status | Stable descriptive foundation |
| Authority | Subordinate to `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` and `PROJECT_CONSTITUTION.md` |
| Change policy | Explicit review; no incidental edits inside unrelated implementation work |

## Identity

VOODOO One is a governed change authorization and evidence control plane.

Its core responsibility is not to invent operational truth or execute arbitrary commands. Its
responsibility is to decide whether a precisely described change may proceed, under which conditions,
and with what evidence.

## Human principle

Technology serves people. Automation and AI remain tools, not authorities.

## Foundations

1. **Reality before claims**
   Repository content, Git state, executed tests, runtime evidence, and artifacts outrank prose.

2. **Evidence before confidence**
   Important claims require reproducible evidence and an explicit scope.

3. **Authorization is separate from proposal**
   The proposer, AI system, package publisher, approver, and runner are distinct identities.

4. **Capabilities before shell**
   Execution interfaces describe allowed operations, not arbitrary command strings.

5. **Fail closed**
   Missing identity, policy, evidence, backend support, or release authorization blocks the affected
   operation.

6. **Exact binding**
   Approval and execution grants bind to exact content, target, environment, policy, and time.

7. **Independent verification**
   Liveness, data integrity, evidence integrity, and observed outcome are different checks.

8. **Reversible evolution**
   Small vertical slices, rollback, checkpointing, and recovery are preferred over broad rewrites.

9. **One authoritative owner**
   Cross-cutting capabilities such as checkpoint verification, configuration, persistence, and policy
   must not acquire competing implementations.

10. **Visible limitations**
    Unreleased, proposed, indeterminate, and blocked capabilities remain explicitly labeled.

11. **Public framework, private runtime data**
    Source, contracts, examples, and sanitized documentation may be versioned. Secrets, customer data,
    runtime databases, and environment-specific evidence remain outside Git.

12. **Production is a release state**
    A local success or configuration switch is not production authorization.

## Decision loop

```text
observation or intent
  -> evidence
  -> structured proposal
  -> policy decision
  -> independent approval
  -> bounded execution
  -> verification
  -> receipt and audit
  -> new observation
```

## Source-of-truth rules

For actual technical state, use:

1. current repository content;
2. Git status and history;
3. executed tests and terminal output;
4. runtime configuration and observed state;
5. CI and produced artifacts;
6. technical documentation;
7. roadmap, vision, and README claims.

For normative authority, use the order defined by repository governance and accepted ADRs.

When capability documentation conflicts with executed evidence, the capability document must be
corrected. Documentation never upgrades a capability from PROPOSED or BLOCKED to VERIFIED.

## Product boundaries

VOODOO One owns:

- human and service identity;
- authorization and policy;
- approvals;
- execution lifecycle;
- operational safety;
- audit and receipts;
- ProofGraph and governed evidence.

VOODOO One does not own:

- unrestricted infrastructure discovery;
- broad knowledge modeling;
- vendor-specific intelligence;
- arbitrary shell execution;
- autonomous production authority.

## Engineering posture

- inspect before creating;
- reuse before adding another owner;
- stabilize interfaces before extracting services;
- document architecture changes in ADRs;
- include tests for behavior changes;
- preserve production effects disabled until released;
- keep temporary evidence outside the Git worktree and checkpoint it explicitly.
