from __future__ import annotations

from tests.system.test_control_plane_contract import decision
from voodoo_product.control_plane_service import control_plane_decision_report


def test_control_plane_report_validates_decision_payload() -> None:
    control_plane_decision = decision()

    report = control_plane_decision_report(control_plane_decision.to_dict())

    assert report["valid"] is True
    assert report["status"] == "IMPLEMENTED"
    assert report["decision_digest"] == control_plane_decision.decision_digest


def test_control_plane_report_fails_closed_for_invalid_payload() -> None:
    report = control_plane_decision_report({"status": "VERIFIED"})

    assert report["valid"] is False
    assert report["status"] == "FAILED"
    assert report["decision_digest"] is None
    assert report["errors"]
