from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .control_plane import ControlPlaneDecisionError, VOneControlPlaneDecision


def parse_control_plane_decision(value: Mapping[str, Any]) -> VOneControlPlaneDecision:
    return VOneControlPlaneDecision.from_dict(value)


def control_plane_decision_report(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        decision = parse_control_plane_decision(value)
    except ControlPlaneDecisionError as exc:
        return {
            "status": "FAILED",
            "valid": False,
            "errors": [str(exc)],
            "decision_digest": None,
        }
    return {
        "status": decision.status,
        "valid": True,
        "errors": [],
        "decision_digest": decision.decision_digest,
        "purpose": decision.purpose,
        "system_benefit": decision.system_benefit,
    }
