from __future__ import annotations

import json
from pathlib import Path

from voodoo_product.controlled_write import (
    CONTROLLED_WRITE_REQUIREMENT_TYPE,
    GITHUB_CREATE_REF_CONDITION_TYPE,
)
from voodoo_product.vop_vocabulary import SCHEMA_REGISTRY_IDS


def test_f1_released_contract_ids_are_reserved_in_canonical_vop_registry() -> None:
    released = {
        CONTROLLED_WRITE_REQUIREMENT_TYPE,
        GITHUB_CREATE_REF_CONDITION_TYPE,
    }
    registry = json.loads(Path("schemas/vop/registry.v1.json").read_text(encoding="utf-8"))

    assert released <= set(SCHEMA_REGISTRY_IDS)
    assert released <= set(registry["canonical_schema_ids"])
    assert registry["canonical_schema_ids"] == list(SCHEMA_REGISTRY_IDS)
