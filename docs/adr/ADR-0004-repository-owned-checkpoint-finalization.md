# ADR-0004: Repository-owned checkpoint finalization

- Status: Accepted
- Date: 2026-07-26
- Decision owner: VOODOO project owner
- Risk class: R2
- Scope: Local development checkpoint finalization only

## Context

ADR-0002 established `voodoo_product/checkpoint_evidence.py` as the single read-only,
dependency-neutral owner of local checkpoint verification. Historical ProofGraph V6 evidence proved
that freezing runtime bytes before nested manifests eliminates post-manifest mutation warnings, but
the working producer pattern remained outside the repository.

The repository needs one small finalization boundary before it creates a fresh runtime checkpoint for
the current committed HEAD. This decision does not build a Docker image or collect runtime evidence.
It finalizes an already prepared local checkpoint candidate.

The first implementation review found a verification-to-snapshot race: candidate verification ran
before the first tree snapshot, so a candidate changed immediately after verification could be copied
and re-manifested as valid. This ADR therefore requires snapshots on both sides of candidate
verification and copying, plus an independent staging comparison.

## Decision

The repository will own checkpoint finalization in
`voodoo_product/checkpoint_producer.py`.

The local command grammar is:

```bash
export PATH="$PWD/scripts:$PATH"
voodoo evidence finalize /absolute/path/to/candidate /absolute/path/to/final-checkpoint
```

The equivalent module entry point is:

```bash
python -m voodoo_product evidence finalize \
  /absolute/path/to/candidate \
  /absolute/path/to/final-checkpoint
```

The finalizer:

1. treats the candidate as untrusted local input;
2. rejects a missing, non-directory or symlinked candidate root;
3. rejects symlinks and special files anywhere in the candidate tree;
4. requires a new destination whose parent already exists;
5. rejects a destination inside the candidate tree;
6. records a typed candidate snapshot before verification, including the candidate root and every
   descendant file and directory, permission mode, file size and file SHA-256; same-source snapshots
   also bind the root device and inode identity;
7. rejects legacy post-manifest mutation exception evidence as a prohibited policy marker;
8. runs the existing verifier against the candidate;
9. records a second candidate snapshot and rejects any verification-time change;
10. requires valid outer evidence and permits only explicit `nested_post_manifest_mutation` warnings;
11. copies the candidate into a sibling staging directory without changing the source and without
    dereferencing a symlink that appears during copying;
12. records a third candidate snapshot and rejects any copy-time source change;
13. records an independent staging snapshot and requires it to equal the verified candidate snapshot;
14. repeats the legacy-exception check against the frozen staging copy;
15. writes runtime and optional commit nested manifests only after the staging copy is frozen;
16. writes the outer `ops/SHA256SUMS` as the last payload mutation;
17. calls the existing `verify_checkpoint()` owner against staging;
18. requires staged verification with zero errors and zero warnings;
19. temporarily opens only the verified finalizer-owned staging root to mode `0700` immediately
    before promotion, without changing the sealed source candidate;
20. promotes staging to the destination with a same-filesystem rename only after verification;
21. immediately reseals the promoted destination to mode `0500`, independently verifies that
    destination and reports `finalized: true` only for `valid: true`, zero errors and zero warnings;
22. preserves a destination when resealing or promoted verification fails, reports
    `destination_published: true` and never silently repairs or removes the published evidence;
23. may restore owner write permission only on its own temporary staging root when cleanup requires
    it, and reports staging or lock cleanup failures with stable structured error codes instead of
    suppressing them.

## Authoritative ownership and reuse

- `checkpoint_producer.py` owns local candidate freezing and final promotion.
- `checkpoint_evidence.py` remains the single read-only checkpoint verifier.
- `evidence_primitives.py` remains the owner of canonical JSON and ledger hashing primitives.
- `cli.py` owns command routing without adding a CLI framework.
- Existing checkpoint, manifest, provenance and ProofGraph formats are reused.

Parallel finalizers or verifiers are prohibited unless a later ADR explicitly supersedes this
decision.

## Trust boundaries

The producer itself does not:

- execute candidate-provided code;
- directly invoke a shell, Docker, a registry or a network service;
- extract archives;
- contact Google Drive;
- mutate the product database;
- authorize a release or production effect;
- overwrite an existing destination.

The finalizer reuses the existing `verify_checkpoint()` owner. Its Git-bundle and source-tree
verification invokes the local Git executable without a shell, so local Git availability is an explicit
runtime dependency and `git_unavailable` remains a possible verifier failure.

A sibling lock prevents concurrent compliant finalizers from publishing the same destination. A
hostile process using the same operating-system identity could ignore that lock or race filesystem
objects after the last comparison. Signed immutable artifacts and descriptor-relative filesystem
operations remain future work.

## Failure behavior

Every failure returns stable JSON with `finalized: false`, a non-zero CLI exit code and a structured
error code. The prohibited legacy exception marker is classified before generic outer-evidence
verification, while all other invalid outer evidence remains fail-closed and is never re-signed by
manifest regeneration. An invalid checkpoint is never promoted. The source candidate remains
unchanged by the finalizer.

Candidate changes are distinguished as:

- `candidate_changed_during_verification`;
- `candidate_changed_during_copy`;
- `staging_differs_from_verified_candidate`.

Cleanup failures are distinguished as:

- `staging_cleanup_failed`;
- `lock_cleanup_failed`.

A lock cleanup failure discovered after atomic promotion returns `finalized: false`, includes
`destination_published: true`, and causes a non-zero CLI exit code. This prevents a partially completed
operation from being reported as fully successful while preserving the already verified destination.

The candidate source remains sealed and unchanged throughout finalization. A verified staging root
may be opened to `0700` only for the bounded atomic-promotion step. The promoted destination is
immediately resealed to `0500` before authoritative destination verification. Resealing failures use
`promoted_destination_resealing_failed`; promoted verification failures use
`promoted_destination_verification_failed`. Both preserve the destination for forensics and report
`destination_published: true`. Cleanup may reopen only the finalizer-created temporary staging root,
never the caller-controlled candidate or another caller path.

## Deferred work

This decision does not implement:

- runtime evidence capture;
- Docker build, daemon or registry verification;
- cryptographic signatures or transparency-log anchoring;
- descriptor-relative copying and final promotion;
- remote byte verification;
- release promotion;
- deployment or production effects;
- a public HTTP API.

## Verification

The change requires:

- successful finalization of a real verifier fixture;
- zero verifier warnings after finalization;
- repair of the known nested post-manifest mutation warning only;
- rejection of invalid outer evidence before manifest regeneration;
- rejection when the candidate changes during verification;
- rejection when the candidate changes during copying;
- rejection when staging differs from the verified candidate snapshot;
- detection of empty-directory and permission-mode changes;
- rejection when a candidate entry becomes a symlink or special file;
- source-candidate byte preservation;
- successful finalization of a sealed `0500` candidate while preserving its source mode;
- staged verification before the bounded `0700` promotion transition;
- destination resealing to `0500` before independent promoted verification;
- preservation and explicit publication state for post-promotion reseal or verification failures;
- successful cleanup of finalizer-owned sealed staging after a pre-promotion failure;
- visible staging-cleanup and lock-cleanup failures;
- existing-destination rejection;
- legacy exception rejection;
- CLI JSON and exit-code coverage;
- full repository lint, compile, tests and product-readiness verification.

## Rollback

Revert the finalizer module, CLI route, tests, this ADR and the three documentation updates as one
focused change. No database migration, release artifact, remote branch, deployment or production
state requires rollback.
