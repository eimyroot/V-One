# ADR-0001: Portable sandbox path resolution

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-07-21 |
| Decision owner | Repository owner |
| Scope | `write_artifact` filesystem trust boundary |
| Risk class | R3 security control |

## Context

The `write_artifact` adapter writes operator-approved content beneath a configured sandbox root. The
previous implementation opened each directory component with descriptor-relative `O_NOFOLLOW`.
A Linux audit environment demonstrated that its filesystem/kernel compatibility layer could still
follow a directory symlink when `O_DIRECTORY | O_NOFOLLOW` was used. The existing regression test
therefore returned `SUCCEEDED` and wrote outside the governed workspace boundary.

The security invariant is stronger than any one platform flag: untrusted workspace and artifact path
components must never redirect a write outside the directory object that was inspected and approved.

## Decision

Sandbox directory traversal will use all of the following controls:

1. require the authoritative workspace identifier to remain one relative path component;
2. inspect every untrusted directory component with `stat(..., follow_symlinks=False)`;
3. reject symlinks and every non-directory object before opening;
4. open each component relative to its already verified parent directory descriptor;
5. inspect the path entry again without following symlinks after opening;
6. require the pre-open entry, opened descriptor, and post-open entry to share `(st_dev, st_ino)`;
7. reject any mismatch, covering replacement between inspection and open;
8. retain `O_NOFOLLOW` as defense in depth, not as the sole enforcement mechanism;
9. reject an existing destination that is a symlink or any non-regular file;
10. retain same-directory temporary-file creation, `fsync`, and atomic `replace` for committed writes.

The configured sandbox-root path is an operator-owned configuration boundary. Its final path entry is
also inspected and identity-verified. Workspace IDs and all artifact path components beneath that root
are treated as untrusted.

## Required platform primitives

The capability fails closed unless the runtime supports:

- descriptor-relative `open` and `mkdir`;
- descriptor-relative `stat`;
- `stat(..., follow_symlinks=False)`;
- `fstat` identity verification;
- `O_NOFOLLOW` defense in depth.

No fallback to path-string containment checks is permitted.

## Consequences

- Existing legitimate directory trees continue to work without a public API or database change.
- Symlinked workspace directories, nested directory components, sandbox roots, and destination files
  are rejected.
- A concurrent directory replacement either fails during open or fails the device/inode comparison.
- The implementation remains POSIX-specific and intentionally fails closed on unsupported platforms.
- A hostile process with the same operating-system identity could still rename an already opened directory after verification; preventing that class of local-host attack requires the planned isolated runner and service-owned filesystem permissions.

## Verification

The security gate must cover:

- the existing end-to-end nested-directory symlink regression;
- direct workspace-directory and sandbox-root symlinks;
- existing destination symlinks;
- a simulated inspect/open race that moves the original directory outside the sandbox and replaces its path with a symlink to the same inode;
- a normal nested write;
- full system regression, lint, syntax checks, and product readiness.

Release verification additionally requires the same tests on supported macOS and Linux/Docker
filesystems. A green result on one platform is not universal evidence.

## Rollback

Revert the implementation, regression tests, readiness entries, and documentation as one focused
security change. Production effects remain disabled throughout. Rolling back reopens the known
cross-platform sandbox risk and therefore must not be used for a release candidate.
