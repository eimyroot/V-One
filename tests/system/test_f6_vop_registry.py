from __future__ import annotations

import json
from pathlib import Path

from voodoo_product.vop_vocabulary import SCHEMA_REGISTRY_IDS

F6_IDS = {
    "rollback-write-requirement/v1",
    "github-delete-exact-created-ref-condition/v1",
    "github-delete-exact-created-ref-request/v1",
    "github-delete-ref-provider-response/v1",
    "runner-boundary/v3",
    "credential-broker-policy/v3",
    "credential-access-decision/v3",
    "ephemeral-rollback-credential-delivery/v1",
    "write-runtime-activation/v2",
    "write-effect-preflight/v2",
    "github-ref-absence-observation/v1",
    "verifier-github-ref-absence-observation/v1",
    "independent-verification-boundary/v2",
    "verifier-credential-decision/v2",
}


def test_f6_schema_ids_are_reserved_and_registry_projection_matches() -> None:
    registry = json.loads(Path("schemas/vop/registry.v1.json").read_text())
    registry_ids = tuple(registry["canonical_schema_ids"])
    assert registry_ids == SCHEMA_REGISTRY_IDS
    assert F6_IDS.issubset(set(registry_ids))
    assert "operation-proof/v2" not in registry_ids
