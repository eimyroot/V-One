from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp with millisecond precision."""

    return datetime.now(UTC).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    """Create a non-guessable identifier while preserving the public prefix format."""

    return f"{prefix}_{secrets.token_hex(8)}"


def canonical_json(value: Any) -> str:
    """Serialize evidence payloads deterministically for storage and hashing."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chained_hash(previous_hash: str, payload: dict[str, Any]) -> str:
    """Hash one canonical payload against the preceding evidence hash."""

    encoded = f"{previous_hash}\n{canonical_json(payload)}".encode()
    return hashlib.sha256(encoded).hexdigest()
