# Phase F / F6b — First Live Governed Delete PREP R1

Status: **PREPARATION ONLY — LIVE DELETE NOT AUTHORIZED**.

## Canonical lineage

- preparation base: `main@2473a37f791c51a8a419a9eb88a78fdbd23a9bcd` (merge of PR #122)
- accepted F6 dry head: `e76b26a08a7edce369fab5617c1613f1075572d6`
- source create evidence: PR #120 F4b verified evidence checkpoint
- exact rollback target: `refs/heads/vone-canary/f4b-pr120-32185703943`
- exact expected object SHA: `83f9c43357460e49b1eba82f124a13015a8e6a88`

## Capability boundary

- capability: `github.delete-exact-created-ref/v1`
- environment: `staging`
- repository: `nulleimy/V-One`
- namespace: `refs/heads/vone-canary/`
- temporal model: `READ_THEN_DELETE_NON_ATOMIC`
- maximum provider mutations: `1`
- automatic retry after ambiguous provider outcome: forbidden

## This preparation gate MAY

1. add a PR-bound dry/static workflow;
2. prove exact branch/base/head lineage;
3. READ current `main` and the exact F4b canary;
4. require the current canary SHA to equal the F4b-created SHA;
5. run F6 rollback lint/compile/tests;
6. retain preparation evidence.

## This preparation gate MUST NOT

- grant `contents: write` to an executing job;
- deliver a rollback write credential;
- invoke GitHub provider DELETE;
- mutate, recreate, rename, or move the canary ref;
- automatically retry an ambiguous provider outcome;
- claim rollback VERIFIED;
- emit `ExecutionReceipt/v2` for a provider effect that did not occur;
- emit `OperationProof/v2` or `OperationCell/v1`;
- release, deploy, or perform a production effect.

## Hard authorization split

The preparation workflow must remain fail-closed. Any live-effect job is absent or hard-disabled and cannot become executable without a later repository change performed under a new explicit consequential authorization gate.

The next explicit gate, and only that gate, may authorize:

`F6b FIRST LIVE GOVERNED DELETE exact F4b canary -> Runner absence readback -> independent Verifier absence readback -> VerificationResult/v1 -> ExecutionReceipt/v2 -> CASER evidence -> STOP`

Before that live gate, the exact PR head, `main` drift, CI, D4b/E3/E4b regressions, review threads, target existence, and target SHA must be re-checked.

## Live exit requirements

A later live F6b execution is acceptable only when all of the following are proven:

1. final pre-delete READ resolves the exact target ref to `83f9c43357460e49b1eba82f124a13015a8e6a88`;
2. exactly one governed DELETE is attempted;
3. provider ambiguity is terminal and never automatically retried;
4. Runner separately observes exact target absence;
5. an independent READ-only Verifier separately observes the same absence;
6. `VerificationResult/v1.verdict == VERIFIED` for exact independently observed absence;
7. `ExecutionReceipt/v2` records the rollback effect without conflating receipt and verification;
8. replay is sealed/fail-closed;
9. canonical CASER evidence is retained before Phase F is declared complete.
