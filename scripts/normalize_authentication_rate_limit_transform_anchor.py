from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "voodoo_product" / "service.py"
text = TARGET.read_text(encoding="utf-8")
start_marker = "\n\nclass AuthRateLimitExceeded(Exception):\n"
end_marker = "def row_dict(row: DatabaseRow | None) -> dict[str, Any] | None:\n"
start = text.find(start_marker)
end = text.find(end_marker, start + 1)
if start < 0 or end < 0:
    raise SystemExit("authentication rate-limit exception anchor not found")
expected = '''

class AuthRateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__("authentication temporarily rate limited")





'''
TARGET.write_text(text[:start] + expected + text[end:], encoding="utf-8")
