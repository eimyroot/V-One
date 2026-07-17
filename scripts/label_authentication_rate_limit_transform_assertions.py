from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "apply_authentication_rate_limit_service_composition.py"
text = TARGET.read_text(encoding="utf-8")
old = '        raise SystemExit(f"expected one match in {path}, found {count}")\n'
new = '        raise SystemExit(\n            f"expected one match in {path}, found {count}: {old[:120]!r}"\n        )\n'
if text.count(old) != 1:
    raise SystemExit(f"transform assertion raise anchor count={text.count(old)}")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
