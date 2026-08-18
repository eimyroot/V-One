from __future__ import annotations

import json
from pathlib import Path

from voodoo_product.github_create_ref_provider import (
    GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE,
    GITHUB_CREATE_REF_REQUEST_TYPE,
)
from voodoo_product.target_binding import TARGET_BINDING_TYPE
from voodoo_product.vop_vocabulary import SCHEMA_REGISTRY_IDS


def test_f3_contract_ids_and_historical_target_binding_are_in_canonical_registry() -> None:
    required = {
        TARGET_BINDING_TYPE,
        GITHUB_CREATE_REF_REQUEST_TYPE,
        GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE,
    }
    registry = json.loads(Path("schemas/vop/registry.v1.json").read_text(encoding="utf-8"))

    assert required <= set(SCHEMA_REGISTRY_IDS)
    assert required <= set(registry["canonical_schema_ids"])
    assert registry["canonical_schema_ids"] == list(SCHEMA_REGISTRY_IDS)
