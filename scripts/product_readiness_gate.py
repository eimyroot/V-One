from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Canonical product/readiness inventory. New trust-plane composition code must be added here so a
# readiness PASS cannot silently ignore a newly introduced authority, runtime, verifier or effect seam.
REQUIRED = [
    "voodoo_product/__main__.py",
    "voodoo_product/a09_rollback_orchestration.py",
    "voodoo_product/a09_write_orchestration.py",
    "voodoo_product/api.py",
    "voodoo_product/audit.py",
    "voodoo_product/authoritative_grant.py",
    "voodoo_product/authorization_snapshot.py",
    "voodoo_product/authorization_snapshot_creator.py",
    "voodoo_product/auth_rate_limit.py",
    "voodoo_product/canonical_operation_http.py",
    "voodoo_product/canonical_operation_runtime.py",
    "voodoo_product/canonical_pipeline.py",
    "voodoo_product/canonical_read_terminal.py",
    "voodoo_product/capability_registry.py",
    "voodoo_product/change_request.py",
    "voodoo_product/checkpoint_evidence.py",
    "voodoo_product/cli.py",
    "voodoo_product/composition.py",
    "voodoo_product/control_plane.py",
    "voodoo_product/control_plane_service.py",
    "voodoo_product/controlled_write.py",
    "voodoo_product/credential_broker.py",
    "voodoo_product/db.py",
    "voodoo_product/development_decision.py",
    "voodoo_product/dispatch_envelope.py",
    "voodoo_product/dispatch_inbox.py",
    "voodoo_product/dispatch_inbox_persistence.py",
    "voodoo_product/dispatch_outbox.py",
    "voodoo_product/dispatch_outbox_persistence.py",
    "voodoo_product/durable_coordinator.py",
    "voodoo_product/durable_current_fence.py",
    "voodoo_product/evidence_primitives.py",
    "voodoo_product/execution.py",
    "voodoo_product/execution_capsule.py",
    "voodoo_product/execution_conformance.py",
    "voodoo_product/execution_lease.py",
    "voodoo_product/execution_lease_persistence.py",
    "voodoo_product/execution_receipt_v2.py",
    "voodoo_product/external_identity.py",
    "voodoo_product/external_identity_service.py",
    "voodoo_product/external_identity_statements.py",
    "voodoo_product/github_create_ref_provider.py",
    "voodoo_product/github_create_ref_runtime.py",
    "voodoo_product/github_delete_ref_runtime.py",
    "voodoo_product/github_read_provider.py",
    "voodoo_product/grant_consumption.py",
    "voodoo_product/http_security.py",
    "voodoo_product/identity.py",
    "voodoo_product/isolated_runner.py",
    "voodoo_product/main.py",
    "voodoo_product/observability.py",
    "voodoo_product/operation_cell_v1.py",
    "voodoo_product/operation_proof.py",
    "voodoo_product/operation_proof_v2.py",
    "voodoo_product/operation_proof_v2_absence.py",
    "voodoo_product/operation_semantics.py",
    "voodoo_product/operational_safety.py",
    "voodoo_product/permission_authority.py",
    "voodoo_product/persistence.py",
    "voodoo_product/platform_status.py",
    "voodoo_product/policy_decision.py",
    "voodoo_product/receipt.py",
    "voodoo_product/release_promotion.py",
    "voodoo_product/rollback_control.py",
    "voodoo_product/rollback_runtime.py",
    "voodoo_product/runner_identity.py",
    "voodoo_product/security.py",
    "voodoo_product/security_intelligence.py",
    "voodoo_product/service.py",
    "voodoo_product/session_lifecycle.py",
    "voodoo_product/skill_orchestration.py",
    "voodoo_product/statements.py",
    "voodoo_product/target_binding.py",
    "voodoo_product/terminal_profile.py",
    "voodoo_product/user_account.py",
    "voodoo_product/verification_result.py",
    "voodoo_product/verifier_credential.py",
    "voodoo_product/verifier_identity.py",
    "voodoo_product/verifier_observation.py",
    "voodoo_product/version.py",
    "voodoo_product/vop_vocabulary.py",
    "voodoo_product/workspace.py",
    "voodoo_product/workspace_membership_statements.py",
    "voodoo_product/write_boundary.py",
    "voodoo_product/write_runtime.py",
    "voodoo_product/static/index.html",
    "voodoo_product/static/app.js",
    "voodoo_product/migrations/sqlite/0001_core_schema.sql",
    "voodoo_product/migrations/sqlite/0002_auth_rate_limits.sql",
    "voodoo_product/migrations/sqlite/0003_receipt_sequence.sql",
    "voodoo_product/migrations/sqlite/0004_execution_leases.sql",
    "voodoo_product/migrations/sqlite/0005_workspace_environment_boundary.sql",
    "voodoo_product/migrations/sqlite/0006_external_identity_bindings.sql",
    "voodoo_product/migrations/sqlite/0007_active_sessions.sql",
    "voodoo_product/migrations/sqlite/0008_immutable_review_binding.sql",
    "voodoo_product/migrations/sqlite/0009_authorization_snapshots.sql",
    "voodoo_product/migrations/sqlite/0010_durable_execution_grants.sql",
    "voodoo_product/migrations/sqlite/0011_dispatch_outbox.sql",
    "voodoo_product/migrations/sqlite/0012_dispatch_inbox.sql",
    "voodoo_product/migrations/sqlite/0013_execution_epoch_leases.sql",
    "voodoo_product/migrations/sqlite/0014_workspace_memberships.sql",
    "schemas/vop/registry.v1.json",
    "tests/system/test_a09_write_orchestration.py",
    "tests/system/test_adapter_sandbox_security.py",
    "tests/system/test_auth_rate_limiting.py",
    "tests/system/test_authentication_rate_limit_service.py",
    "tests/system/test_canonical_operation_http.py",
    "tests/system/test_canonical_operation_pipeline.py",
    "tests/system/test_canonical_product_composition.py",
    "tests/system/test_canonical_read_terminal.py",
    "tests/system/test_canonical_route_constraints.py",
    "tests/system/test_change_request_service.py",
    "tests/system/test_checkpoint_evidence_verifier.py",
    "tests/system/test_control_plane_contract.py",
    "tests/system/test_control_plane_service.py",
    "tests/system/test_database_migrations.py",
    "tests/system/test_database_permission_authority.py",
    "tests/system/test_development_decision_contract.py",
    "tests/system/test_evidence_primitives.py",
    "tests/system/test_execution_capsule.py",
    "tests/system/test_execution_conformance.py",
    "tests/system/test_execution_idempotency.py",
    "tests/system/test_execution_recovery.py",
    "tests/system/test_execution_service.py",
    "tests/system/test_external_identity_binding.py",
    "tests/system/test_github_main_governance_verifier.py",
    "tests/system/test_governed_external_identity_service.py",
    "tests/system/test_http_security.py",
    "tests/system/test_identity_provider.py",
    "tests/system/test_observability.py",
    "tests/system/test_operational_safety.py",
    "tests/system/test_operation_cell_v1.py",
    "tests/system/test_operation_proof.py",
    "tests/system/test_operation_proof_v2.py",
    "tests/system/test_operation_proof_v2_absence.py",
    "tests/system/test_operation_semantics.py",
    "tests/system/test_persistence_boundary.py",
    "tests/system/test_platform_status_service.py",
    "tests/system/test_policy_decision_contract.py",
    "tests/system/test_product_composition.py",
    "tests/system/test_product_platform_rc1.py",
    "tests/system/test_receipt_ledger.py",
    "tests/system/test_reconciliation_truth_invariants.py",
    "tests/system/test_release_promotion_contract.py",
    "tests/system/test_release_supply_chain.py",
    "tests/system/test_rollback_control.py",
    "tests/system/test_security_intelligence_rsi1.py",
    "tests/system/test_session_lifecycle.py",
    "tests/system/test_skill_orchestration.py",
    "tests/system/test_statement_catalog.py",
    "tests/system/test_terminal_profile_registry.py",
    "tests/system/test_token_security.py",
    "tests/system/test_user_account_service.py",
    "tests/system/test_verification_result.py",
    "tests/system/test_verifier_credential.py",
    "tests/system/test_verifier_identity.py",
    "tests/system/test_verifier_observation.py",
    "tests/system/test_vop_canonical_vocabulary.py",
    "tests/system/test_workspace_service.py",
    "tests/system/test_write_boundary.py",
    "tests/system/test_write_runtime.py",
    "scripts/smoke_product_image.sh",
    "scripts/validate_release_candidate.py",
    "scripts/verify_github_main_governance.py",
    "scripts/voodoo",
    ".env.product.example",
    "Dockerfile.product",
    "docker-compose.product.yml",
    "requirements-product.lock",
    "requirements-dev.lock",
    ".github/governance/main-branch-baseline.v1.json",
    ".github/workflows/ci.yml",
    ".github/workflows/g0-governance-verify.yml",
    ".github/pull_request_template.md",
    ".github/workflows/release-candidate.yml",
    "SECURITY.md",
    "VISION.md",
    "ARCHITECTURE.md",
    "CURRENT_PRODUCT_STATE.md",
    "ROADMAP.md",
    "foundation/FOUNDATIONS.md",
    "foundation/TERMINOLOGY.md",
    "docs/README.md",
    "docs/architecture/TRUST_BOUNDARIES.md",
    "docs/architecture/VOP_CANONICAL_VOCABULARY.md",
    "docs/governance/DOCUMENTATION_POLICY.md",
    "docs/governance/GITHUB_MAIN_GOVERNANCE_BASELINE_V1.md",
    "docs/product/CURRENT_CAPABILITIES.md",
    "docs/product/DATABASE_MIGRATIONS.md",
    "docs/product/TARGET_CAPABILITIES.md",
    "tests/system/test_project_documentation.py",
    "docs/adr/ADR-0001-portable-sandbox-path-resolution.md",
    "docs/adr/ADR-0002-local-checkpoint-proofgraph-verification.md",
    "docs/adr/ADR-0015-operation-proof-v2-current-lineage-r1.md",
    "docs/adr/ADR-0017-operation-cell-v1-r1.md",
    "docs/adr/ADR-0018-vop-terminal-profiles-and-lineage-r2.md",
    "docs/product/AUDIT_LEDGER_COMPOSITION_BOUNDARY.md",
    "docs/product/AUTHENTICATION_RATE_LIMIT_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/CHANGE_REQUEST_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/SYSTEM_CONTROL_PLANE_BOUNDARY.md",
    "docs/product/EXECUTION_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/EXTERNAL_IDENTITY_BINDING_BOUNDARY.md",
    "docs/product/GOVERNED_EXTERNAL_IDENTITY_SERVICE.md",
    "docs/product/IDENTITY_PROVIDER_BOUNDARY.md",
    "docs/product/OPERATIONAL_SAFETY_COMPOSITION_BOUNDARY.md",
    "docs/product/PERSISTENCE_BOUNDARY.md",
    "docs/product/POLICY_DECISION_BOUNDARY.md",
    "docs/product/PLATFORM_STATUS_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/RECEIPT_LEDGER_COMPOSITION_BOUNDARY.md",
    "docs/product/RELEASE_PROMOTION_BOUNDARY.md",
    "docs/product/SESSION_LIFECYCLE_BOUNDARY.md",
    "docs/product/STATEMENT_CATALOG.md",
    "docs/product/USER_ACCOUNT_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/WORKSPACE_SERVICE_COMPOSITION_BOUNDARY.md",
]

FORBIDDEN_REPOSITORY_ARTIFACTS = (
    ".DS_Store",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
)

FORBIDDEN_REPOSITORY_SUFFIXES = (".pyc", ".pyo")
GENERATED_CACHE_DIRECTORIES = (".pytest_cache", ".ruff_cache", "__pycache__")


def product_version() -> str:
    from voodoo_product.version import __version__

    return __version__


def run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
    }


def repository_paths() -> list[str]:
    git_dir = ROOT / ".git"
    if git_dir.exists():
        completed = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, text=True, capture_output=True, check=False
        )
        if completed.returncode == 0:
            return [line for line in completed.stdout.splitlines() if line]

    paths: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in GENERATED_CACHE_DIRECTORIES for part in relative.parts):
            continue
        paths.append(str(relative))
    return paths


def is_forbidden_repository_artifact(path: str) -> bool:
    relative = Path(path)
    if relative.name.startswith("._"):
        return True
    if relative.name in FORBIDDEN_REPOSITORY_ARTIFACTS:
        return True
    if any(part in FORBIDDEN_REPOSITORY_ARTIFACTS for part in relative.parts):
        return True
    return relative.suffix in FORBIDDEN_REPOSITORY_SUFFIXES


def current_vop_registry_check() -> dict[str, object]:
    from voodoo_product.authoritative_grant import EXECUTION_GRANT_V2_TYPE
    from voodoo_product.operation_cell_v1 import OPERATION_CELL_V1_TYPE
    from voodoo_product.operation_proof_v2 import OPERATION_PROOF_V2_TYPE
    from voodoo_product.verification_result import VERIFICATION_RESULT_TYPE
    from voodoo_product.vop_vocabulary import (
        OPERATION_STAGE_RULE,
        OPERATION_TERMINAL_PROFILES,
        SCHEMA_COMPATIBILITY,
        SCHEMA_REGISTRY_IDS,
        SCHEMA_SUPERSESSIONS,
        VOCABULARY_REVISION,
    )

    registry = json.loads(
        (ROOT / "schemas" / "vop" / "registry.v1.json").read_text(encoding="utf-8")
    )
    machine_ids = list(SCHEMA_REGISTRY_IDS)
    manifest_ids = registry.get("canonical_schema_ids")
    manifest_supersessions = registry.get("schema_supersessions")
    manifest_compatibility = registry.get("schema_compatibility")
    manifest_profiles = registry.get("operation_terminal_profiles")
    expected_profiles = {
        key: list(value) for key, value in sorted(OPERATION_TERMINAL_PROFILES.items())
    }
    required_current = {
        EXECUTION_GRANT_V2_TYPE,
        VERIFICATION_RESULT_TYPE,
        OPERATION_PROOF_V2_TYPE,
        OPERATION_CELL_V1_TYPE,
    }
    missing_current = sorted(required_current - set(machine_ids))
    semantic_invariants = {
        "grant_v1_superseded_by_v2": (
            SCHEMA_SUPERSESSIONS.get("execution-grant/v1") == EXECUTION_GRANT_V2_TYPE
        ),
        "receipt_v2_not_universal_supersession": (
            "execution-receipt/v1" not in SCHEMA_SUPERSESSIONS
        ),
        "proof_v2_not_universal_supersession": (
            "operation-proof/v1" not in SCHEMA_SUPERSESSIONS
        ),
        "read_only_terminal_is_verification_result": (
            OPERATION_TERMINAL_PROFILES.get("READ_ONLY_VERIFIED")
            == ("independent_verification", "verification_result")
        ),
        "bounded_mutation_terminal_has_proof_cell": (
            OPERATION_TERMINAL_PROFILES.get("BOUNDED_MUTATION_VERIFIED")
            == (
                "execution_receipt",
                "independent_verification",
                "verification_result",
                "operation_proof",
                "operation_cell",
            )
        ),
        "receipt_v2_compatibility_is_narrow": (
            SCHEMA_COMPATIBILITY.get("execution-receipt/v2")
            == "CURRENT_BOUNDED_MUTATION_EFFECT_RECEIPT_NOT_UNIVERSAL_REPLACEMENT"
        ),
        "proof_v2_compatibility_is_narrow": (
            SCHEMA_COMPATIBILITY.get("operation-proof/v2")
            == "CURRENT_BOUNDED_MUTATION_PROOF_NOT_UNIVERSAL_REPLACEMENT"
        ),
    }
    matches = {
        "manifest_matches_machine_registry": manifest_ids == machine_ids,
        "supersessions_match": manifest_supersessions == dict(SCHEMA_SUPERSESSIONS),
        "compatibility_matches": manifest_compatibility == dict(SCHEMA_COMPATIBILITY),
        "terminal_profiles_match": manifest_profiles == expected_profiles,
        "stage_rule_matches": registry.get("operation_stage_rule") == OPERATION_STAGE_RULE,
        "vocabulary_revision_matches": registry.get("vocabulary_revision") == VOCABULARY_REVISION,
    }
    return {
        "ok": not missing_current and all(matches.values()) and all(semantic_invariants.values()),
        "required_current_contracts": sorted(required_current),
        "missing_current_contracts": missing_current,
        **matches,
        "semantic_invariants": semantic_invariants,
    }


def main() -> int:
    checks: dict[str, object] = {}
    missing = [item for item in REQUIRED if not (ROOT / item).is_file()]
    checks["required_files"] = {"ok": not missing, "missing": missing}
    checks["current_vop_contract_registry"] = current_vop_registry_check()

    hygiene_findings = [
        path for path in repository_paths() if is_forbidden_repository_artifact(path)
    ]
    checks["repository_hygiene"] = {
        "ok": not hygiene_findings,
        "findings": sorted(hygiene_findings)[:200],
        "finding_count": len(hygiene_findings),
        "scope": "versioned repository paths when git metadata is present; source files otherwise",
    }

    syntax_errors: list[str] = []
    for path in (ROOT / "voodoo_product").rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            syntax_errors.append(f"{path}: {exc}")
    checks["python_syntax"] = {"ok": not syntax_errors, "errors": syntax_errors}

    secret_findings: list[str] = []
    forbidden = {
        "default development secret": re.compile(r"local-dev-secret-change-me"),
        "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
        "GitHub personal access token": re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
        "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "private key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    }
    for path in ROOT.rglob("*"):
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.is_file() and path.suffix in {".py", ".md", ".yml", ".yaml", ".example"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in forbidden.items():
                if pattern.search(text):
                    secret_findings.append(f"{path.relative_to(ROOT)} contains {label}")
    checks["secret_scan"] = {"ok": not secret_findings, "findings": secret_findings}

    tests = run([sys.executable, "-m", "pytest", "tests/system", "-q"])
    checks["system_tests"] = {"ok": tests["returncode"] == 0, **tests}

    compile_result = run([sys.executable, "-m", "compileall", "-q", "voodoo_product"])
    checks["compileall"] = {"ok": compile_result["returncode"] == 0, **compile_result}

    checks["production_fail_closed"] = {
        "ok": os.getenv("VOODOO_ALLOW_PRODUCTION_EFFECTS", "false").lower()
        not in {"1", "true", "yes", "on"},
        "note": (
            "Production effects must remain disabled until external adapters pass a separate "
            "governed release gate."
        ),
    }

    passed = all(bool(value.get("ok")) for value in checks.values() if isinstance(value, dict))
    report = {
        "product": "VOODOO One",
        "version": product_version(),
        "passed": passed,
        "checks": checks,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
