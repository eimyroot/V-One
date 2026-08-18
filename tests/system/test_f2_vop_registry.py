from __future__ import annotations

import json
from pathlib import Path

from voodoo_product.credential_broker import CREDENTIAL_BROKER_POLICY_TYPE
from voodoo_product.vop_vocabulary import SCHEMA_REGISTRY_IDS
from voodoo_product.write_boundary import (
    CREDENTIAL_ACCESS_DECISION_V2_TYPE,
    CREDENTIAL_BROKER_POLICY_V2_TYPE,
    RUNNER_BOUNDARY_V2_TYPE,
)


def test_f2_contract_ids_and_historical_policy_v1_are_in_canonical_registry() -> None:
    required = {
        CREDENTIAL_BROKER_POLICY_TYPE,
        CREDENTIAL_BROKER_POLICY_V2_TYPE,
        CREDENTIAL_ACCESS_DECISION_V2_TYPE,
        RUNNER_BOUNDARY_V2_TYPE,
    }
    registry = json.loads(Path("schemas/vop/registry.v1.json").read_text(encoding="utf-8"))

    assert required <= set(SCHEMA_REGISTRY_IDS)
    assert required <= set(registry["canonical_schema_ids"])
    assert registry["canonical_schema_ids"] == list(SCHEMA_REGISTRY_IDS)
