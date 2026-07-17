from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests/system/test_operational_safety.py"
text = TARGET.read_text(encoding="utf-8")
old = '''def test_product_and_execution_services_delegate_emergency_stop_sql() -> None:
    product_source = (ROOT / "voodoo_product" / "service.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "voodoo_product" / "execution.py").read_text(
        encoding="utf-8"
    )

    assert "sql.SELECT_EMERGENCY_STOP" not in product_source
    assert "sql.UPSERT_EMERGENCY_STOP" not in product_source
    assert "sql.SELECT_EMERGENCY_STOP" not in execution_source
    assert "self.operational_safety_service.set_emergency_stop" in product_source
    assert "self.operational_safety_service.is_active" in product_source
    assert "self.operational_safety_service.is_active" in execution_source
'''
new = '''def test_product_and_execution_services_delegate_emergency_stop_sql() -> None:
    product_source = (ROOT / "voodoo_product" / "service.py").read_text(encoding="utf-8")
    execution_source = (ROOT / "voodoo_product" / "execution.py").read_text(
        encoding="utf-8"
    )
    platform_status_source = (ROOT / "voodoo_product" / "platform_status.py").read_text(
        encoding="utf-8"
    )

    assert "sql.SELECT_EMERGENCY_STOP" not in product_source
    assert "sql.UPSERT_EMERGENCY_STOP" not in product_source
    assert "sql.SELECT_EMERGENCY_STOP" not in execution_source
    assert "self.operational_safety_service.set_emergency_stop" in product_source
    assert "self.operational_safety_service.is_active" not in product_source
    assert "self.operational_safety_service.is_active" in platform_status_source
    assert "self.operational_safety_service.is_active" in execution_source
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one operational safety ownership block, found {text.count(old)}")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
