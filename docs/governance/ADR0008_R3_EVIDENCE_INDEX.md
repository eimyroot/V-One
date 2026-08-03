# ADR-0008 R3 Evidence Index

| Field | Value |
|---|---|
| Document status | Current evidence index |
| ADR-0008 status | PROPOSED |
| Owner decision | REQUIRED |
| Runtime effect | None |
| Raw evidence | Remains outside Git under the external evidence root |
| Portability rule | Machine-local paths are non-portable metadata |

## Purpose

This index connects the immutable digests for the ADR-0008 R3 review chain, the exact reviewed
commit, the portable bundle, the evidence-hardened documentation/MVP patch, the exact remote
publication, and the PR #54 merge into `main`.

It distinguishes:

- review inputs;
- patch and commit evidence;
- bundle evidence;
- documentation synchronization evidence;
- repository-owned publication evidence;
- PR and merge evidence.

It does not claim runtime implementation, release authorization, or production activation.

## Source package integrity

| Artifact | SHA-256 | What it proves | What it does not prove |
|---|---:|---|---|
| `00_MASTER_CODEX_HANDOFF.md` | `267d702e49ba5bd37f7b2a483c72d26ffeb64ed06899487af7fa202e8ca5b639` | The authoritative orchestration and fail-closed rules for this task | Runtime behavior, publication, or implementation |
| `01_DETAILED_TASK_REFERENCE.md` | `ff1b746107e1bd50f351e8d5da0d4a813e2bb4b37b377a54dbf8ef5638d609fb` | The normative task paths, commands, evidence inputs, and prohibitions | Repository state or runtime evidence |
| `02_MVP_DELIVERY_MAP_SOURCE.md` | `23925bbfb0d49ab986a78de62bfa08abcae28db4b685117c21d295c564bb7692` | The product-delivery map source for the MVP patch | Any runtime implementation claim |
| `03_DOCUMENTATION_SYNC_AUDIT_SOURCE.md` | `319ce432d087462df4c573be118fa39fbde2d54612a52267b2fa0b33f6fd2a1d` | The documentation gap audit and synchronization rationale | Publication, release, or deployment |
| `MANIFEST.json` | `69e6bc84c5a295c88cff4badd810f915c1c0233a951421ae49bc15343c46a9c0` | Package identity and immutable roles | Runtime evidence |
| `README_FIRST.md` | `bb4c6b21cfb9333791d6aeb6987f8a314227399e0900349195fa6519ff21ac8a` | Package usage guidance | Repository state |

## Latest runtime checkpoint chain

| Digest or identity | What it proves | What it does not prove |
|---|---|---|
| `POST_MERGE_CHECKPOINT_HEAD=d57d37111b8bc9471a136b6c618aad8e920f1aff` | Exact committed baseline covered by the latest development checkpoint | The later `0fa69411...` review commit or docs/MVP patch |
| `POST_MERGE_CHECKPOINT_ZIP_SHA256=80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2` | Byte identity of the independently verified post-merge checkpoint archive | Release, deployment, registry publication, or production operation |
| `POST_MERGE_CHECKPOINT_MANIFEST_SHA256=f2851d70523122134bef007bd589872b810326a924f9fc187e2bec1da0aed0a2` | Byte identity of that archive's internal `SHA256SUMS` manifest | Authenticity or non-repudiation |
| `POST_MERGE_CHECKPOINT_TESTS=433` | Recorded full-suite count for the exact checkpoint | Test coverage of later commits |
| `POST_MERGE_CHECKPOINT_IMAGE_ID=sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc` | Recorded local product-image identity built from the checkpoint tree | Registry availability, signing, release, or deployment |

The checkpoint reports Ruff, compile, focused gates, full tests, readiness, dependency audit,
product-image build, and the recorded smoke gate as passed. Production effects remained disabled.
This is development checkpoint evidence, not unrestricted production evidence.

## Review chain

| Digest | What it proves | What it does not prove |
|---|---|---|
| `INITIAL_R3_REVIEW_SHA256=10dedce29d8743a1dac03fbfd30f64caac5764c15d393709365436489354b950` | The initial R3 review artifact identity | That the reviewed patch was published or runtime-executed |
| `R3_FIX_ARCHIVE_SHA256=5ddb28abbab4748925c04a0c1a081946d77d81f28b653df47bdd8a7a56553743` | The archive containing the exact R3 fix evidence | Any later docs synchronization |
| `PATCH_SHA256=a39a8febd258b27e3b756e1df6b6fa2b795614642b5874dff66a5990d6c2ac02` | The exact authorized patch bytes for the reviewed commit | Runtime implementation beyond the reviewed diff |
| `FOCUSED_REREVIEW_SHA256=3153180c1a263f190afcff92e339caf656567000129b9acfbb282c363d97308e` | Focused rereview evidence for the review patch | Publication or deployment |
| `COMMIT=0fa69411b246c4bd80b8a2eaa989e60fd8bca663` | The exact reviewed commit object identity | A published branch or remote update |
| `PARENT=d57d37111b8bc9471a136b6c618aad8e920f1aff` | The exact parent commit identity | A runtime checkpoint or release |
| `TREE=362d9d1dfd8dec6f4c7a3aa5a4fa5e1633aeaff5` | The exact commit tree identity | Any later documentation patch |
| `COMMIT_EVIDENCE_ZIP_SHA256=119354e1238a0aa7d07764a64f77c4ed385e91e87adfc2b1160d9b961d7da764` | The exact commit-evidence ZIP identity | Runtime implementation |
| `COMMIT_VERIFICATION_REPORT_SHA256=060f78a38b364cf9071efad307e99b6fa49337f2c9faed32e784e36766a15812` | The commit verification report identity | Publication or release |
| `BUNDLE_SHA256=64a6c2a77fd61a05be86189df73b0dbed361ae877ee088ac0dc45954fcf71a6b` | The portable Git bundle identity | Runtime implementation |
| `BUNDLE_EVIDENCE_ZIP_SHA256=143cb7031bdf44ef3a495a584b6473a5bf20d349e8da588674d70b71a5ae2ee2` | The bundle evidence package identity | Publication or deployment |
| `BUNDLE_VERIFICATION_REPORT_SHA256=66734caf1b079244375d1d2ad1ece78617b338357bfee153a4daa4cbf79b16b1` | The bundle verification report identity | Runtime implementation |
| `ADR_BLOB=384e7e80e974cc5c2d83a85edd4f93eb9f8cd7a9` | The byte identity of the reviewed ADR | That the reviewed ADR is accepted or runtime-implemented |
| `THREAT_MODEL_BLOB=e01c96a7c5bdcd3641852bd4a0eddcc062148516` | The byte identity of the reviewed threat model | That the threat model is implemented runtime control |

## Documentation/MVP evidence chain

| Digest or identity | What it proves | What it does not prove |
|---|---|---|
| `DOC_MVP_V2_PATCH_SHA256=328d72a9e710a1787553cd0f5854b0e2652fc9e4825426ddde42386f4f2eeda9` | Exact reviewed V2 documentation/MVP patch bytes | That the patch remains current after later repository events |
| `DOC_MVP_V2_RESULT_TREE=bc3b2c6270ea4f10a6461776e3a0ed5250ad07a6` | Deterministic result tree for the V2 patch on the `0fa69411...` tree | A commit, publication, merge, release, or runtime attestation |
| `DOC_MVP_V2_ARCHIVE_SHA256=a4ee73dfb8774ae854a9e0b40aecdbded63e6754275a3ef761a70d939f461559` | V2 evidence archive identity | Current Git state after PR #54 |
| `DOC_MVP_V2_1_ARCHIVE_SHA256=5048f1033c824a3f8a274e5c039184812f409a5c0d5207a65f8b4896e8312ae2` | Command-provenance closure archive identity | Runtime implementation or release |

## Publication and merge chain

| Digest or identity | What it proves | What it does not prove |
|---|---|---|
| `PUBLICATION_EVIDENCE_ZIP_SHA256=80aea553018c33763b85909f6591b981167555300cd67eed278c0f4b18707c34` | Exact review-branch publication evidence archive | ADR acceptance, release, or deployment |
| `PUBLICATION_EVIDENCE_REPORT_SHA256=71c461fd041227fa10141cf2d5a9e26d4b6572c109d5252bd0376750effbeb98` | Final independent acceptance of the publication evidence | Runtime attestation |
| `REMOTE_REVIEW_BRANCH=review/adr0008-r3-lifecycle-semantics-0fa6941` | The governed branch used for exact review | A production release branch |
| `PR_NUMBER=54` | The pull request that reviewed the exact commit against `main` | ADR owner acceptance |
| `MERGE_COMMIT=57c7bf2277616c4445039865ac7cf81c5fada858` | The exact merge commit now on `main` | Runtime evidence for the merged tree |
| `MERGE_VERIFICATION_REPORT_SHA256=93bf10f7499bfa6259b82dbf525ac8f2052ff38bceb4d91c0b76eb40dbe97c9e` | Independent PR/merge verification report identity | Release, deployment, or production enablement |

## Evidence interpretation

The review commit, patch, bundle, documentation evidence, publication evidence, and merge evidence
prove their scoped object, archive, branch, and Git identities. They do not prove runtime execution,
production readiness, ADR acceptance, release authorization, or deployment.

The portable bundle proves that the reviewed commit can be transported independently of the source
repository prerequisites. It does not prove that the isolated Runner exists, that a release has been
authorized, or that production effects are enabled.

Bundle verification does not prove runtime implementation.

The historical repository-owned publication plan was plan-only. A later separately authorized
publisher execution created the exact review branch, and PR #54 merged the reviewed commit into
`main`. Neither event changes the ADR status or provides runtime attestation.

Raw evidence remains outside Git under the external evidence root. Machine-local paths such as the
review worktree and temporary verification repositories are non-portable metadata and must not be
used as the sole proof of repository state.

## Status boundaries

- `ADR-0008` remains `PROPOSED`.
- The owner decision remains `REQUIRED`.
- The reviewed patch `a39a8febd258b27e3b756e1df6b6fa2b795614642b5874dff66a5990d6c2ac02` is closed
  for the exact R3 findings listed in the review evidence.
- The isolated Runner runtime is not implemented.
- ADR-0008 remains PROPOSED.
- Owner decision remains REQUIRED.
- Authoritative grant issuance, authenticity envelopes, trust stores, key rotation, durable
  one-time claim stores, governed mutation gateways, and production effects remain `NOT IMPLEMENTED`
  or `BLOCKED` according to the product documents.
- Exact review publication and PR #54 merge are VERIFIED; runtime implementation, ADR acceptance,
  release, deployment, and production effects are not implied.
