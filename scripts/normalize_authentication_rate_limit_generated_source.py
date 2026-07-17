from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / "voodoo_product" / "service.py",
    ROOT / "voodoo_product" / "auth_rate_limit.py",
)

for target in TARGETS:
    data = target.read_bytes()
    if b"\x00" not in data:
        continue
    target.write_bytes(data.replace(b"\x00", b"\\0"))
