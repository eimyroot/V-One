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

- allowed effects;
- prohibited effects;
- evidence references;
- acceptance gates;
- deterministic digest.

Missing boundary, evidence, or gates is invalid and fails closed.
