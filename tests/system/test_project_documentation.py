from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CORE_DOCUMENTS = {
    "README.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "CURRENT_PRODUCT_STATE.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "VISION.md",
    "foundation/FOUNDATIONS.md",
    "foundation/TERMINOLOGY.md",
    "docs/README.md",
    "docs/architecture/TRUST_BOUNDARIES.md",
    "docs/product/CURRENT_CAPABILITIES.md",
    "docs/product/TARGET_CAPABILITIES.md",
    "docs/product/SECURITY_OVERVIEW.md",
    "docs/product/MVP_DELIVERY_MAP.md",
    "docs/governance/ADR0008_R3_EVIDENCE_INDEX.md",
    "docs/governance/DOCUMENTATION_POLICY.md",
    "docs/adr/ADR-0007-execution-grant-receipt-contract-v1.md",
    "docs/adr/ADR-0008-isolated-runner-boundary-v1.md",
    "docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md",
    "tests/system/test_project_documentation.py",
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


def _markdown_links(text: str) -> set[str]:
    return set(match.group(1) for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text))


def _is_relative_link(target: str) -> bool:
    return not (
        target.startswith("http://")
        or target.startswith("https://")
        or target.startswith("mailto:")
        or target.startswith("#")
    )


def _git_blob(relative: str) -> str:
    return subprocess.run(
        ("git", "hash-object", str(ROOT / relative)),
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def test_core_documentation_foundation_exists() -> None:
    missing = sorted(relative for relative in CORE_DOCUMENTS if not (ROOT / relative).is_file())

    assert missing == []


def test_readme_links_every_core_document() -> None:
    readme = _read("README.md")

    for relative in sorted(
        {
            "ARCHITECTURE.md",
            "ROADMAP.md",
            "CURRENT_PRODUCT_STATE.md",
            "CHANGELOG.md",
            "SECURITY.md",
            "VISION.md",
            "foundation/FOUNDATIONS.md",
            "foundation/TERMINOLOGY.md",
            "docs/product/CURRENT_CAPABILITIES.md",
            "docs/product/TARGET_CAPABILITIES.md",
            "docs/product/SECURITY_OVERVIEW.md",
            "docs/product/MVP_DELIVERY_MAP.md",
            "docs/architecture/TRUST_BOUNDARIES.md",
            "docs/governance/DOCUMENTATION_POLICY.md",
            "docs/governance/ADR0008_R3_EVIDENCE_INDEX.md",
            "docs/README.md",
        }
    ):
        assert f"({relative})" in readme

    assert "(docs/README.md)" in readme
    assert "(docs/governance/ADR0008_R3_EVIDENCE_INDEX.md)" in readme
    assert "(docs/product/MVP_DELIVERY_MAP.md)" in readme


def test_documentation_index_links_core_navigation() -> None:
    index = _read("docs/README.md")

    required_links = {
        "../VISION.md",
        "../ARCHITECTURE.md",
        "../ROADMAP.md",
        "../foundation/TERMINOLOGY.md",
        "product/CURRENT_CAPABILITIES.md",
        "product/TARGET_CAPABILITIES.md",
        "product/MVP_DELIVERY_MAP.md",
        "architecture/TRUST_BOUNDARIES.md",
        "governance/ADR0008_R3_EVIDENCE_INDEX.md",
        "governance/DOCUMENTATION_POLICY.md",
        "adr/ADR-0007-execution-grant-receipt-contract-v1.md",
        "adr/ADR-0008-isolated-runner-boundary-v1.md",
        "security/ISOLATED_RUNNER_THREAT_MODEL_V1.md",
    }

    for target in sorted(required_links):
        assert f"({target})" in index


def test_relative_links_resolve_in_critical_docs() -> None:
    critical_documents = {
        "README.md",
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "CURRENT_PRODUCT_STATE.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "foundation/TERMINOLOGY.md",
        "docs/README.md",
        "docs/architecture/TRUST_BOUNDARIES.md",
        "docs/product/CURRENT_CAPABILITIES.md",
        "docs/product/TARGET_CAPABILITIES.md",
        "docs/product/SECURITY_OVERVIEW.md",
        "docs/product/MVP_DELIVERY_MAP.md",
        "docs/governance/ADR0008_R3_EVIDENCE_INDEX.md",
    }

    for relative in sorted(critical_documents):
        document = _read(relative)
        source_dir = (ROOT / relative).parent
        for target in sorted(link for link in _markdown_links(document) if _is_relative_link(link)):
            resolved = (source_dir / target).resolve()
            assert resolved.exists(), f"{relative} -> {target}"
            assert ROOT in resolved.parents or resolved == ROOT


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


def test_mvp_delivery_map_and_evidence_index_state_boundaries() -> None:
    mvp = _read("docs/product/MVP_DELIVERY_MAP.md")
    evidence_index = _read("docs/governance/ADR0008_R3_EVIDENCE_INDEX.md")

    for label in (
        "MVP-0 VERIFIED",
        "MVP-1 PARTIALLY VERIFIED",
        "MVP-2 PROPOSED",
        "MVP-3 PROPOSED",
        "MVP-4 BLOCKED",
        "MVP-5 PROPOSED",
    ):
        assert label in mvp

    assert "operator requests one concrete capability" in mvp
    assert "PROPOSED" in _read("docs/product/MVP_DELIVERY_MAP.md").split("## Proposed first customer profile", 1)[1]
    assert "Primary pilot customer - PROPOSED" in mvp
    assert "generic shell or arbitrary script execution" in mvp
    assert "shared VOODOO/CyberCore database" in mvp

    for digest in (
        "INITIAL_R3_REVIEW_SHA256=10dedce29d8743a1dac03fbfd30f64caac5764c15d393709365436489354b950",
        "R3_FIX_ARCHIVE_SHA256=5ddb28abbab4748925c04a0c1a081946d77d81f28b653df47bdd8a7a56553743",
        "PATCH_SHA256=a39a8febd258b27e3b756e1df6b6fa2b795614642b5874dff66a5990d6c2ac02",
        "FOCUSED_REREVIEW_SHA256=3153180c1a263f190afcff92e339caf656567000129b9acfbb282c363d97308e",
        "COMMIT=0fa69411b246c4bd80b8a2eaa989e60fd8bca663",
        "PARENT=d57d37111b8bc9471a136b6c618aad8e920f1aff",
        "TREE=362d9d1dfd8dec6f4c7a3aa5a4fa5e1633aeaff5",
        "COMMIT_EVIDENCE_ZIP_SHA256=119354e1238a0aa7d07764a64f77c4ed385e91e87adfc2b1160d9b961d7da764",
        "COMMIT_VERIFICATION_REPORT_SHA256=060f78a38b364cf9071efad307e99b6fa49337f2c9faed32e784e36766a15812",
        "BUNDLE_SHA256=64a6c2a77fd61a05be86189df73b0dbed361ae877ee088ac0dc45954fcf71a6b",
        "BUNDLE_EVIDENCE_ZIP_SHA256=143cb7031bdf44ef3a495a584b6473a5bf20d349e8da588674d70b71a5ae2ee2",
        "BUNDLE_VERIFICATION_REPORT_SHA256=66734caf1b079244375d1d2ad1ece78617b338357bfee153a4daa4cbf79b16b1",
        "ADR_BLOB=384e7e80e974cc5c2d83a85edd4f93eb9f8cd7a9",
        "THREAT_MODEL_BLOB=e01c96a7c5bdcd3641852bd4a0eddcc062148516",
        "POST_MERGE_CHECKPOINT_HEAD=d57d37111b8bc9471a136b6c618aad8e920f1aff",
        "POST_MERGE_CHECKPOINT_ZIP_SHA256=80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2",
        "POST_MERGE_CHECKPOINT_MANIFEST_SHA256=f2851d70523122134bef007bd589872b810326a924f9fc187e2bec1da0aed0a2",
        "POST_MERGE_CHECKPOINT_TESTS=433",
        "POST_MERGE_CHECKPOINT_IMAGE_ID=sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc",
        "DOC_MVP_V2_PATCH_SHA256=328d72a9e710a1787553cd0f5854b0e2652fc9e4825426ddde42386f4f2eeda9",
        "DOC_MVP_V2_RESULT_TREE=bc3b2c6270ea4f10a6461776e3a0ed5250ad07a6",
        "DOC_MVP_V2_ARCHIVE_SHA256=a4ee73dfb8774ae854a9e0b40aecdbded63e6754275a3ef761a70d939f461559",
        "DOC_MVP_V2_1_ARCHIVE_SHA256=5048f1033c824a3f8a274e5c039184812f409a5c0d5207a65f8b4896e8312ae2",
        "PUBLICATION_EVIDENCE_ZIP_SHA256=80aea553018c33763b85909f6591b981167555300cd67eed278c0f4b18707c34",
        "PUBLICATION_EVIDENCE_REPORT_SHA256=71c461fd041227fa10141cf2d5a9e26d4b6572c109d5252bd0376750effbeb98",
        "PR_NUMBER=54",
        "MERGE_COMMIT=57c7bf2277616c4445039865ac7cf81c5fada858",
        "MERGE_VERIFICATION_REPORT_SHA256=93bf10f7499bfa6259b82dbf525ac8f2052ff38bceb4d91c0b76eb40dbe97c9e",
    ):
        assert digest in evidence_index

    assert "ADR-0008 remains PROPOSED." in evidence_index
    assert "Owner decision remains REQUIRED." in evidence_index
    assert "Raw evidence remains outside Git" in evidence_index
    assert "Bundle verification does not prove runtime implementation." in evidence_index


def test_reviewed_adr_and_threat_model_remain_byte_identical() -> None:
    assert _git_blob("docs/adr/ADR-0008-isolated-runner-boundary-v1.md") == (
        "384e7e80e974cc5c2d83a85edd4f93eb9f8cd7a9"
    )
    assert _git_blob("docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md") == (
        "e01c96a7c5bdcd3641852bd4a0eddcc062148516"
    )


def test_runner_controls_are_not_described_as_runtime_implemented() -> None:
    documents = {
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "SECURITY.md",
        "docs/architecture/TRUST_BOUNDARIES.md",
        "docs/product/TARGET_CAPABILITIES.md",
        "docs/product/SECURITY_OVERVIEW.md",
        "docs/product/MVP_DELIVERY_MAP.md",
        "docs/security/ISOLATED_RUNNER_THREAT_MODEL_V1.md",
    }
    text = "\n".join(_read(relative).lower() for relative in sorted(documents))

    forbidden_phrases = {
        "runner runtime is implemented",
        "isolated runner runtime is implemented",
        "governed mutation gateway is implemented",
        "signed execution grants are implemented",
        "authenticity envelope is implemented",
        "runner controls are implemented",
    }

    for phrase in forbidden_phrases:
        assert phrase not in text



def test_current_git_and_runtime_evidence_baselines_remain_distinct() -> None:
    current = "57c7bf2277616c4445039865ac7cf81c5fada858"
    runtime = "d57d37111b8bc9471a136b6c618aad8e920f1aff"

    state = _read("CURRENT_PRODUCT_STATE.md")
    readme = _read("README.md")
    capabilities = _read("docs/product/CURRENT_CAPABILITIES.md")
    mvp = _read("docs/product/MVP_DELIVERY_MAP.md")

    assert f"LATEST_VERIFIED_GIT_BASELINE: main@{current}" in state
    assert f"LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: main@{runtime}" in state
    assert f"main@{current}" in readme
    assert f"| Latest verified Git baseline | `main@{current}` |" in capabilities
    assert f"| Current verified Git baseline | `main@{current}` |" in mvp
    assert f"| Latest runtime-attested baseline | `main@{runtime}` |" in mvp
    assert "ADR_0008_REVIEW_PR: 54 MERGED" in state
    assert "ADR_0008_DESIGN: PROPOSED" in state


def test_latest_runtime_checkpoint_identity_is_consistent() -> None:
    documents = {
        "README.md",
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "CURRENT_PRODUCT_STATE.md",
        "docs/product/CURRENT_CAPABILITIES.md",
        "docs/governance/ADR0008_R3_EVIDENCE_INDEX.md",
    }
    text = "\n".join(_read(relative) for relative in sorted(documents))

    latest = "d57d37111b8bc9471a136b6c618aad8e920f1aff"
    archive = "80e53da665fe122375900ac888fef3562b0182018c4f7492f355d3d3401f4df2"
    image = "sha256:8342c2ac978343a59ef13d90bda5d89f3d06be2c3d25875665026f039eb99abc"

    assert latest in text
    assert archive in text
    assert image in text
    assert (
        "LATEST_RUNTIME_ATTESTED_COMMITTED_BASELINE: "
        f"main@{latest}"
    ) in _read("CURRENT_PRODUCT_STATE.md")
    assert (
        f"| Latest runtime-attested committed baseline | `main@{latest}` |"
    ) in _read("docs/product/CURRENT_CAPABILITIES.md")
    assert "latest runtime checkpoint attests exactly\n`main@8a5f36b" not in text
    assert "latest canonical runtime checkpoint remains\nthe historical `main@8a5f36b" not in text


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
    assert "default-off runtime compatibility path only" in capabilities
    assert "Solo, Team, Regulated enforcement is not implemented" in capabilities
    assert "| Policy Decision Graph | PROPOSED | ADR-0003" in capabilities
