from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RELEASE_CANDIDATE_PATTERN = re.compile(
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)-rc(?:0|[1-9][0-9]*)"
)


def source_release_candidate_version() -> str:
    from voodoo_product.version import RELEASE_CANDIDATE_VERSION

    return RELEASE_CANDIDATE_VERSION


def validate_release_candidate_version(value: str) -> str:
    if RELEASE_CANDIDATE_PATTERN.fullmatch(value) is None:
        raise ValueError("version must be canonical SemVer with an -rcN suffix")
    expected = source_release_candidate_version()
    if value != expected:
        raise ValueError(
            f"version must match the source release candidate {expected}"
        )
    return value


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("usage: validate_release_candidate.py VERSION", file=sys.stderr)
        return 2
    try:
        version = validate_release_candidate_version(arguments[0])
    except ValueError as exc:
        print(f"release candidate rejected: {exc}", file=sys.stderr)
        return 2
    print(f"release candidate validated: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
