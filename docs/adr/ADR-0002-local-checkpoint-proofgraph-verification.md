# ADR-0002: Local checkpoint verification as the first ProofGraph slice

- Status: Accepted
- Date: 2026-07-22
- Decision owners: VOODOO engineering owner and architecture review
- Scope: Local development checkpoints only

## Context

VOODOO One already produces source archives, Git bundles, runtime evidence, commit evidence,
provenance metadata and SHA-256 manifests. Those artifacts are useful, but verification has been
spread across one-off shell scripts and operator interpretation.

Recent checkpoint work exposed two recurring evidence defects:

1. an execution log could continue changing after a nested manifest was created;
2. a correct Git bundle could be rejected when a verifier compared a short branch name with a full
   `refs/heads/...` reference.

The product needs one authoritative, dependency-neutral verifier before it introduces persistent
ProofGraph storage, signatures, remote attestations or autonomous evidence consumers.

## Decision

The repository will own checkpoint verification in
`voodoo_product/checkpoint_evidence.py`.

The first vertical slice provides the local command grammar:

```bash
export PATH="$PWD/scripts:$PATH"
voodoo evidence verify /absolute/path/to/checkpoint
```

The equivalent module entry point is:

```bash
python -m voodoo_product evidence verify /absolute/path/to/checkpoint
```

The verifier is read-only and fail-closed. It performs these checks:

1. reject a missing, non-directory or symlinked checkpoint root;
2. parse the outer `ops/SHA256SUMS` with strict, sorted, duplicate-free POSIX paths;
3. reject path traversal, symlinks, special files, missing files and unmanifested payloads;
4. recompute every outer SHA-256 digest and require complete manifest coverage;
5. require consistency between `CHECKPOINT_COMPLETE.txt` and `repository.json`;
6. verify the Git bundle, full branch ref, commit, parent, tree and subject;
7. compare every retained source file and executable mode with the committed Git tree;
8. compare the source archive with the retained source directory without extracting it;
9. verify runtime README claims, image-inspect identity and runtime-bundle digest consistency;
10. inspect nested manifests and report post-manifest mutations as explicit warnings when the outer
    checkpoint manifest covers the retained bytes;
11. emit deterministic JSON containing verification checks, normalized claims and a ProofGraph v1
    projection.

ProofGraph v1 contains four node types:

- checkpoint;
- Git commit;
- source tree;
- container image.

It records only evidence relationships already demonstrated by the checkpoint. It does not infer
production readiness, release approval or deployment state.

## Authoritative ownership and reuse

- `evidence_primitives.py` remains the owner of canonical JSON and ledger hashing primitives.
- `checkpoint_evidence.py` becomes the single owner of local checkpoint verification.
- `cli.py` owns command routing without adding a CLI framework.
- Existing Git, SHA-256, checkpoint and runtime formats are reused without introducing a new
  persistence model or dependency.

Parallel checkpoint verifiers are prohibited. Future checkpoint checks must extend this owner or
supersede it through another ADR.

## Trust boundaries

The checkpoint is treated as untrusted local input.

The verifier:

- never executes checkpoint-provided code;
- never uses `shell=True`;
- invokes only the locally resolved `git` executable with fixed argument structure;
- disables system and global Git configuration for verification subprocesses;
- does not extract the source archive;
- rejects archive traversal, links and device entries;
- creates only a temporary bare Git repository and removes it automatically;
- does not contact a network service, Docker daemon, registry or production adapter;
- does not modify the checkpoint or product database.

A hostile process with the same operating-system identity could still race local files during a
verification run. Signed immutable artifacts and descriptor-relative snapshot verification remain
future work.

## Failure behavior

Any required check failure produces JSON with `valid: false` and a non-zero process exit code.
Warnings never convert missing or mismatched outer evidence into success. Nested manifests are
explicitly non-authoritative because the complete outer checkpoint manifest covers the retained
bytes.

## Deferred work

This decision does not implement:

- persistent ProofGraph storage;
- cryptographic signatures or transparency-log anchoring;
- remote Google Drive byte verification;
- Docker daemon or registry digest verification;
- SBOM or vulnerability-policy evaluation;
- release promotion;
- production effects;
- a public HTTP API.

Those capabilities require separate ADRs and trust-boundary reviews.

## Verification

The change requires:

- valid-checkpoint verification;
- payload-tampering regression;
- source-tree divergence regression;
- unmanifested-file rejection;
- manifest path-traversal rejection;
- CLI exit-code and JSON-output coverage;
- dependency-boundary coverage;
- launcher syntax and executable-mode coverage;
- full repository lint, compile, tests and product-readiness verification.

## Rollback

Revert the ADR, verifier, CLI entry points, tests, readiness registration, CI gate and documentation
as one focused change. No database migration, public API or production state requires rollback.

## Consequences

### Positive

- checkpoint verification becomes deterministic and reusable;
- manifest and Git-ref defects become machine-detectable;
- operators receive structured evidence instead of interpreting shell output;
- the first ProofGraph schema is created without persistence or new dependencies;
- production effects remain disabled and outside the verifier trust boundary.

### Negative

- verification requires a local Git executable;
- only regular-file source trees are supported in v1; Git symlinks and submodules fail closed;
- remote bytes and live Docker images are not independently verified;
- existing nested post-manifest log mutations remain visible as warnings until evidence producers
  freeze logs before generating their own manifests.
