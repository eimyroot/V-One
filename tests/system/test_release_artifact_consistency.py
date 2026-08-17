from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPOSITORY_ROOT / "scripts" / "smoke_product_image.sh"


def test_product_image_smoke_requires_released_schema_version() -> None:
    script = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert 'assert data["schema_version"] == 11' in script
    assert 'assert data["schema_version"] == 10' not in script
