from __future__ import annotations

import json
from pathlib import Path

from voodoo_product.vop_vocabulary import SCHEMA_REGISTRY_IDS
from voodoo_product.write_runtime import (
    EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE,
    WRITE_EFFECT_PREFLIGHT_TYPE,
    WRITE_RUNTIME_ACTIVATION_TYPE,
)


def test_f4a_serialized_contracts_are_canonical_vop_ids() -> None:
    expected = {
        EPHEMERAL_WRITE_CREDENTIAL_DELIVERY_TYPE,
        WRITE_RUNTIME_ACTIVATION_TYPE,
        WRITE_EFFECT_PREFLIGHT_TYPE,
    }
    registry = json.loads(
        Path("schemas/vop/registry.v1.json").read_text(encoding="utf-8")
    )

    assert expected.issubset(SCHEMA_REGISTRY_IDS)
    assert expected.issubset(set(registry["canonical_schema_ids"]))
    assert tuple(registry["canonical_schema_ids"]) == SCHEMA_REGISTRY_IDS
