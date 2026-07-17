from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one anchor in {path}: found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


service = ROOT / "voodoo_product" / "service.py"
replace_exact(
    service,
    "from .auth_rate_limit import AuthenticationRateLimitService, AuthRateLimitExceeded\n",
    "from .auth_rate_limit import AuthenticationRateLimitService, AuthRateLimitExceeded\n"
    "from .bootstrap import BootstrapService\n",
)
replace_exact(
    service,
    "        authentication_rate_limit_service: AuthenticationRateLimitService | None = None,\n"
    "        audit_ledger: AuditLedger | None = None,\n",
    "        authentication_rate_limit_service: AuthenticationRateLimitService | None = None,\n"
    "        bootstrap_service: BootstrapService | None = None,\n"
    "        audit_ledger: AuditLedger | None = None,\n",
)
replace_exact(
    service,
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_user_account_service = user_account_service or UserAccountService(\n",
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_bootstrap_service = bootstrap_service or BootstrapService(\n"
    "            database=self.db,\n"
    "            config=self.config,\n"
    "            audit_ledger=self.audit_ledger,\n"
    "            id_factory=lambda prefix: new_id(prefix),\n"
    "            clock=lambda: utc_now(),\n"
    "            password_hasher=lambda password: hash_password(password),\n"
    "            token_comparator=lambda provided, expected: secrets.compare_digest(\n"
    "                provided, expected\n"
    "            ),\n"
    "        )\n"
    "        if resolved_bootstrap_service.db is not self.db:\n"
    "            raise ValueError(\"bootstrap service must use the product service database\")\n"
    "        if resolved_bootstrap_service.config is not self.config:\n"
    "            raise ValueError(\"bootstrap service must use the product service configuration\")\n"
    "        if resolved_bootstrap_service.audit_ledger is not self.audit_ledger:\n"
    "            raise ValueError(\"bootstrap service must use the product service audit ledger\")\n"
    "        self.bootstrap_service = resolved_bootstrap_service\n"
    "        resolved_user_account_service = user_account_service or UserAccountService(\n",
)
old_methods = '''    def has_users(self) -> bool:\n        with self.db.connect() as connection:\n            row = connection.execute(sql.COUNT_USERS).fetchone()\n            return bool(row and int(row["count"]) > 0)\n\n    def bootstrap_admin(self, *, username: str, password: str, token: str) -> dict[str, Any]:\n        if not secrets.compare_digest(token, self.config.bootstrap_token):\n            raise PermissionError("invalid bootstrap token")\n        with self.db.transaction() as connection:\n            count = connection.execute(sql.COUNT_USERS).fetchone()\n            if count and int(count["count"]) > 0:\n                raise RuntimeError("bootstrap is already closed")\n            user_id = new_id("usr")\n            workspace_id = new_id("wrk")\n            workspace_environment = (\n                self.config.environment\n                if self.config.environment in VALID_ENVIRONMENTS\n                else "local"\n            )\n            now = utc_now()\n            connection.execute(\n                sql.INSERT_USER,\n                (user_id, username.strip(), hash_password(password), "administrator", now),\n            )\n            connection.execute(\n                sql.INSERT_WORKSPACE,\n                (\n                    workspace_id,\n                    f"VOODOO {workspace_environment.title()}",\n                    workspace_environment,\n                    now,\n                ),\n            )\n            self._append_audit(\n                connection,\n                actor_id=user_id,\n                action="system.bootstrap",\n                target_type="workspace",\n                target_id=workspace_id,\n                payload={\n                    "username": username,\n                    "role": "administrator",\n                    "workspace_environment": workspace_environment,\n                },\n            )\n            return {\n                "user_id": user_id,\n                "workspace_id": workspace_id,\n                "workspace_environment": workspace_environment,\n                "role": "administrator",\n            }\n\n'''
new_methods = '''    def has_users(self) -> bool:\n        return self.bootstrap_service.has_users()\n\n    def bootstrap_admin(self, *, username: str, password: str, token: str) -> dict[str, Any]:\n        return self.bootstrap_service.bootstrap_admin(\n            username=username,\n            password=password,\n            token=token,\n        )\n\n'''
replace_exact(service, old_methods, new_methods)

composition = ROOT / "voodoo_product" / "composition.py"
replace_exact(
    composition,
    "from .auth_rate_limit import AuthenticationRateLimitService\n",
    "from .auth_rate_limit import AuthenticationRateLimitService\nfrom .bootstrap import BootstrapService\n",
)
replace_exact(
    composition,
    "    authentication_rate_limit_service: AuthenticationRateLimitService\n"
    "    audit_ledger: AuditLedger\n",
    "    authentication_rate_limit_service: AuthenticationRateLimitService\n"
    "    bootstrap_service: BootstrapService\n"
    "    audit_ledger: AuditLedger\n",
)
replace_exact(
    composition,
    "    authentication_rate_limit_service = service.authentication_rate_limit_service\n"
    "    audit_ledger = service.audit_ledger\n",
    "    authentication_rate_limit_service = service.authentication_rate_limit_service\n"
    "    bootstrap_service = service.bootstrap_service\n"
    "    audit_ledger = service.audit_ledger\n",
)
replace_exact(
    composition,
    "        authentication_rate_limit_service=authentication_rate_limit_service,\n"
    "        audit_ledger=audit_ledger,\n",
    "        authentication_rate_limit_service=authentication_rate_limit_service,\n"
    "        bootstrap_service=bootstrap_service,\n"
    "        audit_ledger=audit_ledger,\n",
)
replace_exact(
    composition,
    "    app.state.voodoo_authentication_rate_limit_service = authentication_rate_limit_service\n"
    "    app.state.voodoo_identity_provider = resolved_identity_provider\n",
    "    app.state.voodoo_authentication_rate_limit_service = authentication_rate_limit_service\n"
    "    app.state.voodoo_bootstrap_service = bootstrap_service\n"
    "    app.state.voodoo_identity_provider = resolved_identity_provider\n",
)

print("bootstrap service composition transform complete")
