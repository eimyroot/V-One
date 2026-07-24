from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CORE_DOCUMENTS = {
    "VISION.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "foundation/FOUNDATIONS.md",
    "foundation/TERMINOLOGY.md",
    "docs/README.md",
    "docs/product/CURRENT_CAPABILITIES.md",
    "docs/product/TARGET_CAPABILITIES.md",
    "docs/architecture/TRUST_BOUNDARIES.md",
    "docs/governance/DOCUMENTATION_POLICY.md",
}

ALLOWED_STATES = {
    "VERIFIED",
    "IMPLEMENTED",
    "PROPOSED",
    "INFERRED",
    "UNKNOWN",
    "BLOCKED",
}


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_core_documentation_foundation_exists() -> None:
    missing = sorted(relative for relative in CORE_DOCUMENTS if not (ROOT / relative).is_file())

    assert missing == []


def test_readme_links_every_core_document() -> None:
    readme = _read("README.md")

    for relative in sorted(CORE_DOCUMENTS - {"docs/README.md"}):
        assert f"({relative})" in readme

    assert "(docs/README.md)" in readme


def test_documentation_index_links_core_navigation() -> None:
    index = _read("docs/README.md")

    required_links = {
        "../VISION.md",
        "../ARCHITECTURE.md",
        "../ROADMAP.md",
        "../foundation/TERMINOLOGY.md",
        "product/CURRENT_CAPABILITIES.md",
        "product/TARGET_CAPABILITIES.md",
        "architecture/TRUST_BOUNDARIES.md",
        "governance/DOCUMENTATION_POLICY.md",
    }

    for target in sorted(required_links):
        assert f"({target})" in index


def test_current_capability_table_uses_only_allowed_states() -> None:
    document = _read("docs/product/CURRENT_CAPABILITIES.md")
    table = document.split("## Capability matrix", 1)[1].split(
        "## Verified command surfaces",
        1,
    )[0]
    rows = [
        line for line in table.splitlines() if line.startswith("| ") and not line.startswith("|---")
    ]
    capability_rows = rows[1:]

    assert capability_rows

    for row in capability_rows:
        columns = [column.strip() for column in row.strip("|").split("|")]
        assert len(columns) == 4
        assert columns[1] in ALLOWED_STATES


def test_roadmap_and_terminology_define_truthful_status_taxonomy() -> None:
    roadmap = _read("ROADMAP.md")
    terminology = _read("foundation/TERMINOLOGY.md")
    policy = _read("docs/governance/DOCUMENTATION_POLICY.md")

    for state in sorted(ALLOWED_STATES):
        assert re.search(rf"\b{state}\b", roadmap)
        assert re.search(rf"\b{state}\b", terminology)
        assert re.search(rf"\b{state}\b", policy)

    assert "`COMPLETE` is not a VOODOO capability status." in terminology
    assert "Roadmap status does not prove implementation." in policy


def test_foundation_preserves_governance_authority() -> None:
    foundations = _read("foundation/FOUNDATIONS.md")

    assert "Subordinate to `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`" in foundations
    assert "`PROJECT_CONSTITUTION.md`" in foundations
    assert "Documentation never upgrades a capability" in foundations


def test_current_capabilities_preserve_release_and_production_boundaries() -> None:
    document = _read("docs/product/CURRENT_CAPABILITIES.md")

    assert "RELEASE_VERIFIED=NO" in document
    assert "VOODOO_ALLOW_PRODUCTION_EFFECTS=false" in document
    assert "| Unrestricted production release | BLOCKED |" in document
    assert "| Public commercial distribution | BLOCKED |" in document


def test_proposed_organization_approval_adr_preserves_current_safety_boundary() -> None:
    relative = "docs/adr/ADR-0003-organization-roles-and-configurable-approval-policy.md"
    adr = _read(relative)
    index = _read("docs/README.md")
    roadmap = _read("ROADMAP.md")
    capabilities = _read("docs/product/CURRENT_CAPABILITIES.md")
    normalized_adr = " ".join(adr.split())

    assert f"({relative.removeprefix('docs/')})" in index
    assert f"({relative})" in roadmap
    assert "| Status | PROPOSED |" in adr
    assert "Runtime effect | None" in adr
    assert "current approval behavior remains authoritative" in normalized_adr
    assert "AI, service, and runner principals cannot authorize their own proposals" in adr
    assert "Mutating production operations cannot run with zero human authorization" in adr
    assert "Production effects remain fail-closed" in adr
    assert "claiming organization tenancy is implemented." in adr
    assert "| Approval policy decision model | VERIFIED |" in capabilities
    assert "pure compatibility evaluator only; not integrated" in capabilities
    assert "| Policy Decision Graph | PROPOSED | ADR-0003" in capabilities
