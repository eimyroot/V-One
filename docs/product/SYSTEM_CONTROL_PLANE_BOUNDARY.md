# System Control Plane Boundary

| Field | Value |
|---|---|
| Document status | Current contract boundary |
| Contract | `v-one-control-plane-decision/v1` |
| Source | `voodoo_product/control_plane.py` |
| Test inventory | `tests/system/test_control_plane_contract.py` |

## Purpose

The V-One system control plane decision contract is the single deterministic record that binds:

- operation semantics;
- skill orchestration;
- operation proof when a decision claims `VERIFIED`;
- explicit boundary;
- evidence references;
- acceptance gates.

Every decision and every decision element must also state its purpose and system benefit. A record
without a useful role is invalid even when its digest is otherwise deterministic.

## Current Boundary

This is a source-level contract only. It does not execute tools, trust plugins dynamically, approve
operations, mutate providers, dispatch runtime agents, or enable production effects.

## Decision Statuses

The only current decision statuses are:

- `VERIFIED`;
- `IMPLEMENTED`;
- `PROPOSED`;
- `BLOCKED`;
- `FAILED`;
- `UNKNOWN`.

`VERIFIED` requires an accepted operation proof and all acceptance gates set to `PASS`.
`IMPLEMENTED`, `PROPOSED`, and `UNKNOWN` require visible pending or blocked gates so the system does
not overclaim completion.

## Boundary Rule

Every control-plane decision must state:

- decision purpose;
- decision system benefit;
- allowed effects;
- prohibited effects;
- boundary purpose and system benefit;
- evidence references with purpose and system benefit;
- acceptance gates with purpose and system benefit;
- deterministic digest.

Missing boundary, evidence, gates, purpose, or system benefit is invalid and fails closed.
