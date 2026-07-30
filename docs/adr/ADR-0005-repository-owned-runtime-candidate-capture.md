# ADR-0005: Repository-owned runtime checkpoint candidate capture

| Field | Value |
|---|---|
| Status | PROPOSED — owner review required |
| Date | 2026-07-30 |
| Decision owner | Repository owner with independent architecture and security review |
| Scope | Local development runtime checkpoint candidate capture only |
| Risk class | R3 evidence and runtime trust-boundary change |
| Runtime effect | Local task-owned Docker resources only; production effects remain disabled |

## Decision card

```text
TITLE: Repository-owned runtime checkpoint candidate capture
DATE: 2026-07-30
OWNER: Repository owner
IMPLEMENTER: Codex working under explicit owner task authorization
REVIEWER: Independent R3 reviewer required; not yet evidenced
RISK_CLASS: R3
MODE: AUDIT → DESIGN → IMPLEMENT → VERIFY

USER: Local VOODOO operator or release engineer
PROBLEM: The verifier and finalizer cannot create the runtime evidence candidate they consume.
EXPECTED_OUTCOME: One fail-closed command creates a verifier-compatible local candidate.
SMALLEST_SAFE_SLICE: Separate capture owner reusing existing Git, Docker, smoke and checkpoint formats.
SOURCE_OF_TRUTH: Current repository, Git identity, Docker observations and existing verifier.

IN_SCOPE: Local source/runtime capture, candidate manifest, provenance and existing verification.
OUT_OF_SCOPE: Finalization, release, publication, signing, deployment, registry and production effects.
AFFECTED_DATA: New candidate directory outside the repository and task-owned local Docker resources.
AFFECTED_PERMISSIONS: Local Git read, Docker daemon access and writes to one caller-selected new directory.
TRUST_BOUNDARIES: Repository, Git executable, Docker daemon, smoke script and external evidence filesystem.

JEDNODUCHÁ: ANO
ÚČELNÁ: ANO
AUTOMATIZOVANÁ: ANO
BEZPEČNÁ: ANO
MĚŘITELNÁ: ANO
VRATNÁ: ANO
DŮKAZNĚ OVĚŘITELNÁ: ANO

TEST_PLAN: Deterministic Git fixtures and fake Docker subprocess boundary, then full repository gates.
SUCCESS_EVIDENCE: Candidate passes the existing verifier and then finalizer with zero final warnings.
FAILURE_SIGNAL: Stable captured=false JSON, non-zero CLI exit and no promoted partial candidate.
ROLLBACK: Revert capture module, CLI route, smoke evidence mode, tests and this documentation.
POST_STATE_VERIFICATION: Repository identity unchanged; task-owned Docker resources removed.

OWNER_DECISION: DEFERRED
DECISION_REASON: Implementation is prepared for explicit owner and independent R3 review.
EXPIRY_OR_REVIEW_DATE: Before commit or any commit-bound runtime checkpoint.
```

## Context

ADR-0002 owns read-only checkpoint verification in
`voodoo_product/checkpoint_evidence.py`. ADR-0004 owns freezing and final promotion in
`voodoo_product/checkpoint_producer.py`, but explicitly excludes Docker execution and runtime
evidence capture. The current verifier-compatible candidate schema is already sufficient: it binds
Git source, a source archive, a branch bundle, runtime evidence, image identity, provenance and a
complete outer manifest.

Without a repository-owned capture command, operators must use an ungoverned one-off producer.
That prevents a repeatable fresh checkpoint for the current committed source and creates an
unreviewed second owner for evidence format and runtime claims.

## Decision

The repository will add one capture owner:

```text
voodoo_product/checkpoint_capture.py
```

The local command grammar is:

```bash
export PATH="$PWD/scripts:$PATH"
voodoo evidence capture-runtime /absolute/path/to/new-candidate
```

The equivalent module entry point is:

```bash
python -m voodoo_product evidence capture-runtime /absolute/path/to/new-candidate
```

Capture, finalization and verification remain explicit boundaries:

```text
capture-runtime
    ↓
finalize
    ↓
verify
```

The capture command never calls `finalize_checkpoint()`.

## Ownership

- `checkpoint_capture.py` owns current-repository observation, exact committed-source
  materialization, local Docker build/smoke observation and creation of one candidate.
- `checkpoint_evidence.py` remains the only read-only verifier and retains all schema semantics.
- `checkpoint_producer.py` remains the only candidate freezer/finalizer.
- `cli.py` owns command routing without a new CLI framework.
- `scripts/smoke_product_image.sh` remains the canonical product image smoke owner.

No verifier or finalizer behavior changes under this decision.

## Capture contract

Before creating a staging directory, capture requires:

- execution from the resolved Git repository root;
- an attached branch;
- a clean index, tracked worktree and untracked-file set;
- directly observed HEAD, tree, parent, subject and tracked file inventory;
- a new absolute destination with an existing real parent outside the repository;
- locally available Git, Docker and Bash executables.

The observed origin relation is recorded without fetching and is not an authorization gate.

Source bytes come from committed Git blobs for the observed HEAD. Only regular `100644` and
`100755` blob entries are supported. Git symlinks, submodules, special entries, unsafe paths and
non-UTF-8 paths fail closed. Git creates the exact source archive and full local branch bundle.

The command re-observes the complete repository identity and cleanliness after source capture,
after runtime capture and after candidate verification. Drift fails as
`repository_changed_during_capture`.

## Runtime evidence

The capture owner reuses:

```text
docker build --file Dockerfile.product ...
scripts/smoke_product_image.sh
```

The smoke script keeps its existing two-argument interface. An optional third absolute evidence
directory enables capture mode. Capture mode records only bounded, relevant evidence:

- Docker version;
- Docker build log and exit code;
- image inspect JSON;
- application health JSON;
- sanitized Docker health JSON;
- running container image ID;
- bounded application runtime log;
- smoke log and exit code.

Full container inspect output is prohibited because it contains runtime environment values,
including smoke credentials. Docker health is claimed only after `.State.Health.Status` is directly
observed as `healthy`. Application health must independently report `HEALTHY`, SQLite schema `7` and
`production_effects=DISABLED`.

The image tag, container and volume are unique to the invocation and are removed before successful
candidate promotion. No image is pushed or labeled as released.

## Candidate and provenance

The candidate reuses the existing format and contains:

```text
source/
ops/artifacts/
ops/evidence/runtime/
ops/provenance/
ops/SHA256SUMS
```

The capture owner writes the required candidate outer manifest because ADR-0004 requires the
candidate to pass verification before freezing. It does not write pre-finalization nested runtime
or commit manifests. The finalizer remains responsible for frozen nested manifests and the final
outer manifest.

Provenance is limited to directly observed local facts:

```text
CHECKPOINT_CLASS=DEVELOPMENT_RUNTIME_VERIFIED_NOT_RELEASE
RELEASE_VERIFIED=NO
WORKTREE=CLEAN
GITHUB_PUSH=NOT_PERFORMED
PRODUCTION_EFFECT=NONE
```

`captured=true` is returned only after the existing `verify_checkpoint()` reports `valid=true` with
no errors and repository identity remains unchanged.

## Failure and cleanup

Failures return schema-versioned JSON with `captured=false`, a non-zero CLI exit and stable codes.
The implementation distinguishes repository, destination, Git, Docker build, smoke, Docker health,
production-effect, image-identity, verifier, repository-drift, I/O and cleanup failures.

Candidate bytes are first written to a task-created sibling staging directory. A handled failure
removes only that staging directory and task-owned Docker resources. The caller-selected destination
is never recursively removed or overwritten. A cleanup failure is explicit and prevents a success
claim.

## Security properties and limitations

- subprocess commands use fixed argument arrays and never `shell=True`;
- Git verification and capture disable system/global configuration and interactive prompting;
- no checkpoint-provided code is executed;
- no dependency, database, persistence model or remote service is added;
- production effects remain explicitly disabled;
- no registry push, fetch, publication, signing, release or deployment occurs;
- same-operating-system-identity races remain possible and are bounded by repeated repository
  observations plus the finalizer snapshot protocol;
- Docker daemon control remains a privileged local trust boundary;
- this proposal is not independently approved and cannot authorize its own R3 acceptance.

## Verification

Required evidence includes:

- successful verifier-compatible candidate capture from a clean fixture repository;
- exact source HEAD/tree/parent/branch binding;
- successful existing finalization and zero-warning independent verification;
- dirty, untracked, detached, destination, unsupported-entry and repository-drift rejection;
- Docker unavailable/build/smoke/health/production-effect/image-identity rejection;
- candidate-verifier and cleanup-failure rejection;
- CLI JSON and exit-code coverage;
- existing two-argument smoke compatibility;
- lint, compile, JavaScript syntax, full tests, readiness and locked dependency audit.

A commit-bound fresh runtime checkpoint is prohibited until this R3 patch is reviewed, explicitly
authorized for commit and committed. Uncommitted fixture validation is not current-HEAD attestation.

## Rollback

Revert this ADR, `checkpoint_capture.py`, the CLI route, optional smoke evidence mode, capture tests,
readiness inventory and related documentation as one focused patch. No database, remote reference,
registry, deployment or production state requires rollback. Remove only any task-specific external
fixture evidence created during authorized local verification.
