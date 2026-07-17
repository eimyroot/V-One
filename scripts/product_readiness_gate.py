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

REQUIRED = [
    "voodoo_product/api.py",
    "voodoo_product/audit.py",
    "voodoo_product/change_request.py",
    "voodoo_product/composition.py",
    "voodoo_product/db.py",
    "voodoo_product/evidence_primitives.py",
    "voodoo_product/execution.py",
    "voodoo_product/external_identity.py",
    "voodoo_product/external_identity_service.py",
    "voodoo_product/external_identity_statements.py",
    "voodoo_product/http_security.py",
    "voodoo_product/identity.py",
    "voodoo_product/main.py",
    "voodoo_product/migrations/sqlite/0001_core_schema.sql",
    "voodoo_product/migrations/sqlite/0002_auth_rate_limits.sql",
    "voodoo_product/migrations/sqlite/0003_receipt_sequence.sql",
    "voodoo_product/migrations/sqlite/0004_execution_leases.sql",
    "voodoo_product/migrations/sqlite/0005_workspace_environment_boundary.sql",
    "voodoo_product/migrations/sqlite/0006_external_identity_bindings.sql",
    "voodoo_product/observability.py",
    "voodoo_product/operational_safety.py",
    "voodoo_product/persistence.py",
    "voodoo_product/receipt.py",
    "voodoo_product/service.py",
    "voodoo_product/statements.py",
    "voodoo_product/security.py",
    "voodoo_product/user_account.py",
    "voodoo_product/version.py",
    "voodoo_product/workspace.py",
    "voodoo_product/static/index.html",
    "tests/system/test_auth_rate_limiting.py",
    "tests/system/test_change_request_service.py",
    "tests/system/test_database_migrations.py",
    "tests/system/test_evidence_primitives.py",
    "tests/system/test_execution_idempotency.py",
    "tests/system/test_execution_recovery.py",
    "tests/system/test_execution_service.py",
    "tests/system/test_external_identity_binding.py",
    "tests/system/test_governed_external_identity_service.py",
    "tests/system/test_http_security.py",
    "tests/system/test_identity_provider.py",
    "tests/system/test_observability.py",
    "tests/system/test_operational_safety.py",
    "tests/system/test_persistence_boundary.py",
    "tests/system/test_product_composition.py",
    "tests/system/test_product_platform_rc1.py",
    "tests/system/test_receipt_ledger.py",
    "tests/system/test_release_supply_chain.py",
    "tests/system/test_statement_catalog.py",
    "tests/system/test_token_security.py",
    "tests/system/test_user_account_service.py",
    "tests/system/test_workspace_service.py",
    "scripts/smoke_product_image.sh",
    "scripts/validate_release_candidate.py",
    ".env.product.example",
    "Dockerfile.product",
    "docker-compose.product.yml",
    "requirements-product.lock",
    "requirements-dev.lock",
    ".github/workflows/ci.yml",
    ".github/workflows/release-candidate.yml",
    "SECURITY.md",
    "docs/product/AUDIT_LEDGER_COMPOSITION_BOUNDARY.md",
    "docs/product/CHANGE_REQUEST_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/DATABASE_MIGRATIONS.md",
    "docs/product/EXECUTION_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/EXTERNAL_IDENTITY_BINDING_BOUNDARY.md",
    "docs/product/GOVERNED_EXTERNAL_IDENTITY_SERVICE.md",
    "docs/product/IDENTITY_PROVIDER_BOUNDARY.md",
    "docs/product/OPERATIONAL_SAFETY_COMPOSITION_BOUNDARY.md",
    "docs/product/PERSISTENCE_BOUNDARY.md",
    "docs/product/RECEIPT_LEDGER_COMPOSITION_BOUNDARY.md",
    "docs/product/STATEMENT_CATALOG.md",
    "docs/product/USER_ACCOUNT_SERVICE_COMPOSITION_BOUNDARY.md",
    "docs/product/WORKSPACE_SERVICE_COMPOSITION_BOUNDARY.md",
]


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


def main() -> int:
    checks: dict[str, object] = {}
    missing = [item for item in REQUIRED if not (ROOT / item).is_file()]
    checks["required_files"] = {"ok": not missing, "missing": missing}

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
        "note": "Production effects must remain disabled until external adapters pass a separate governed release gate.",
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
