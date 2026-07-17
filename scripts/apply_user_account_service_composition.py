from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} matches, found {actual}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


account = ROOT / "voodoo_product" / "user_account.py"
if account.exists():
    raise SystemExit("user account boundary already exists")
account.write_text(
    '''from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import statements as sql
from .audit import AuditLedger
from .evidence_primitives import new_id, utc_now
from .persistence import DatabaseIntegrityError, ProductDatabaseAdapter
from .security import hash_password

IdFactory = Callable[[str], str]
Clock = Callable[[], str]
PasswordHasher = Callable[[str], str]

VALID_ROLES = {
    "viewer",
    "developer",
    "operator",
    "security_reviewer",
    "auditor",
    "administrator",
}


class UserAccountService:
    """Database-bound active-user lookup and ordinary user creation boundary."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        audit_ledger: AuditLedger,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
        password_hasher: PasswordHasher = hash_password,
    ) -> None:
        if audit_ledger.db is not database:
            raise ValueError("user account audit ledger must use its database")
        self.db = database
        self.audit_ledger = audit_ledger
        self._id_factory = id_factory
        self._clock = clock
        self._password_hasher = password_hasher

    def get_active_user(self, user_id: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_ACTIVE_USER,
                (user_id,),
            ).fetchone()
        if row is None or not int(row["active"]):
            raise PermissionError("account is inactive")
        if str(row["role"]) not in VALID_ROLES:
            raise PermissionError("account role is invalid")
        return {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
        }

    def create_user(
        self,
        *,
        actor_id: str,
        username: str,
        password: str,
        role: str,
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise ValueError("unknown role")
        user_id = self._id_factory("usr")
        now = self._clock()
        with self.db.transaction() as connection:
            try:
                connection.execute(
                    sql.INSERT_USER,
                    (
                        user_id,
                        username.strip(),
                        self._password_hasher(password),
                        role,
                        now,
                    ),
                )
            except DatabaseIntegrityError as exc:
                raise ValueError("username already exists") from exc
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="user.create",
                target_type="user",
                target_id=user_id,
                payload={"username": username, "role": role},
            )
        return {
            "id": user_id,
            "username": username,
            "role": role,
            "active": True,
        }
''',
    encoding="utf-8",
)

service = ROOT / "voodoo_product" / "service.py"
replace_exact(
    service,
    "from .security import hash_password, verify_password\nfrom .workspace import WorkspaceService\n",
    "from .security import hash_password, verify_password\n"
    "from .user_account import UserAccountService\n"
    "from .workspace import WorkspaceService\n",
)
replace_exact(
    service,
    "    DatabaseError,\n    DatabaseIntegrityError,\n    DatabaseRow,\n",
    "    DatabaseError,\n    DatabaseRow,\n",
)
replace_exact(
    service,
    "        audit_ledger: AuditLedger | None = None,\n"
    "        workspace_service: WorkspaceService | None = None,\n",
    "        audit_ledger: AuditLedger | None = None,\n"
    "        user_account_service: UserAccountService | None = None,\n"
    "        workspace_service: WorkspaceService | None = None,\n",
)
replace_exact(
    service,
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_workspace_service = workspace_service or WorkspaceService(\n",
    "        self.audit_ledger = resolved_audit_ledger\n"
    "        resolved_user_account_service = user_account_service or UserAccountService(\n"
    "            database=self.db,\n"
    "            audit_ledger=self.audit_ledger,\n"
    "            id_factory=lambda prefix: new_id(prefix),\n"
    "            clock=lambda: utc_now(),\n"
    "            password_hasher=lambda password: hash_password(password),\n"
    "        )\n"
    "        if resolved_user_account_service.db is not self.db:\n"
    "            raise ValueError(\n"
    "                \"user account service must use the product service database\"\n"
    "            )\n"
    "        if resolved_user_account_service.audit_ledger is not self.audit_ledger:\n"
    "            raise ValueError(\n"
    "                \"user account service must use the product service audit ledger\"\n"
    "            )\n"
    "        self.user_account_service = resolved_user_account_service\n"
    "        resolved_workspace_service = workspace_service or WorkspaceService(\n",
)
replace_exact(
    service,
    '''    def get_active_user(self, user_id: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_ACTIVE_USER,
                (user_id,),
            ).fetchone()
        if row is None or not int(row["active"]):
            raise PermissionError("account is inactive")
        if str(row["role"]) not in VALID_ROLES:
            raise PermissionError("account role is invalid")
        return {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
        }

    def create_user(
        self, *, actor_id: str, username: str, password: str, role: str
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise ValueError("unknown role")
        user_id = new_id("usr")
        now = utc_now()
        with self.db.transaction() as connection:
            try:
                connection.execute(
                    sql.INSERT_USER,
                    (user_id, username.strip(), hash_password(password), role, now),
                )
            except DatabaseIntegrityError as exc:
                raise ValueError("username already exists") from exc
            self._append_audit(
                connection,
                actor_id=actor_id,
                action="user.create",
                target_type="user",
                target_id=user_id,
                payload={"username": username, "role": role},
            )
        return {"id": user_id, "username": username, "role": role, "active": True}

''',
    '''    def get_active_user(self, user_id: str) -> dict[str, Any]:
        return self.user_account_service.get_active_user(user_id)

    def create_user(
        self, *, actor_id: str, username: str, password: str, role: str
    ) -> dict[str, Any]:
        return self.user_account_service.create_user(
            actor_id=actor_id,
            username=username,
            password=password,
            role=role,
        )

''',
)

composition = ROOT / "voodoo_product" / "composition.py"
replace_exact(
    composition,
    "from .service import ProductService\nfrom .workspace import WorkspaceService\n",
    "from .service import ProductService\n"
    "from .user_account import UserAccountService\n"
    "from .workspace import WorkspaceService\n",
)
replace_exact(
    composition,
    "    audit_ledger: AuditLedger\n    workspace_service: WorkspaceService\n",
    "    audit_ledger: AuditLedger\n    user_account_service: UserAccountService\n"
    "    workspace_service: WorkspaceService\n",
)
replace_exact(
    composition,
    "    audit_ledger = service.audit_ledger\n    workspace_service = service.workspace_service\n",
    "    audit_ledger = service.audit_ledger\n"
    "    user_account_service = service.user_account_service\n"
    "    workspace_service = service.workspace_service\n",
)
replace_exact(
    composition,
    "        audit_ledger=audit_ledger,\n        workspace_service=workspace_service,\n",
    "        audit_ledger=audit_ledger,\n"
    "        user_account_service=user_account_service,\n"
    "        workspace_service=workspace_service,\n",
)
replace_exact(
    composition,
    "    app.state.voodoo_audit_ledger = audit_ledger\n"
    "    app.state.voodoo_workspace_service = workspace_service\n",
    "    app.state.voodoo_audit_ledger = audit_ledger\n"
    "    app.state.voodoo_user_account_service = user_account_service\n"
    "    app.state.voodoo_workspace_service = workspace_service\n",
)

statement_test = ROOT / "tests" / "system" / "test_statement_catalog.py"
replace_exact(statement_test, "assert len(execute_calls) == 17", "assert len(execute_calls) == 15")

readiness = ROOT / "scripts" / "product_readiness_gate.py"
replace_exact(
    readiness,
    '    "voodoo_product/version.py",\n',
    '    "voodoo_product/user_account.py",\n    "voodoo_product/version.py",\n',
)
replace_exact(
    readiness,
    '    "tests/system/test_token_security.py",\n',
    '    "tests/system/test_token_security.py",\n'
    '    "tests/system/test_user_account_service.py",\n',
)
replace_exact(
    readiness,
    '    "docs/product/WORKSPACE_SERVICE_COMPOSITION_BOUNDARY.md",\n',
    '    "docs/product/USER_ACCOUNT_SERVICE_COMPOSITION_BOUNDARY.md",\n'
    '    "docs/product/WORKSPACE_SERVICE_COMPOSITION_BOUNDARY.md",\n',
)

test = ROOT / "tests" / "system" / "test_user_account_service.py"
if test.exists():
    raise SystemExit("user account service test already exists")
test.write_text(
    '''from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI

import voodoo_product.service as service_module
from voodoo_product.composition import install_composed_product_platform
from voodoo_product.config import ProductConfig
from voodoo_product.service import ProductService
from voodoo_product.user_account import UserAccountService

ROOT = Path(__file__).resolve().parents[2]


def product_config(tmp_path: Path, *, name: str = "product") -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / f"{name}.sqlite3",
        sandbox_root=tmp_path / f"{name}-sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def test_user_account_service_uses_only_central_statement_catalog() -> None:
    source = ROOT / "voodoo_product" / "user_account.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]

    assert len(execute_calls) == 2
    assert all(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].value.id == "sql"
        for call in execute_calls
    )


def test_product_service_delegates_user_account_surface() -> None:
    source = ROOT / "voodoo_product" / "service.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(source))
    product_service = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProductService"
    )
    methods = {
        node.name: node
        for node in product_service.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"get_active_user", "create_user"}
    }

    assert set(methods) == {"get_active_user", "create_user"}
    for method in methods.values():
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            for node in ast.walk(method)
        )
    assert "self.user_account_service.get_active_user" in source_text
    assert "self.user_account_service.create_user" in source_text
    assert "sql.SELECT_ACTIVE_USER" not in source_text
    assert "sql.INSERT_USER" in source_text


def test_user_account_service_rejects_audit_ledger_from_another_database(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(ValueError, match="user account audit ledger must use its database"):
        UserAccountService(database=first.db, audit_ledger=second.audit_ledger)


def test_product_service_rejects_user_account_service_from_another_composition(
    tmp_path: Path,
) -> None:
    first = ProductService(product_config(tmp_path, name="first"))
    second = ProductService(product_config(tmp_path, name="second"))

    with pytest.raises(
        ValueError,
        match="user account service must use the product service database",
    ):
        ProductService(
            product_config(tmp_path, name="mismatch"),
            database=first.db,
            audit_ledger=first.audit_ledger,
            user_account_service=second.user_account_service,
        )


def test_user_account_service_preserves_product_service_contract(tmp_path: Path) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    created = service.create_user(
        actor_id=bootstrap["user_id"],
        username="  developer  ",
        password="VeryStrongDeveloperPassword1!",
        role="developer",
    )

    assert created["username"] == "  developer  "
    assert created["role"] == "developer"
    active = service.get_active_user(created["id"])
    assert active == {
        "id": created["id"],
        "username": "developer",
        "role": "developer",
    }
    assert service.authenticate(
        username="developer",
        password="VeryStrongDeveloperPassword1!",
    ) == active
    with pytest.raises(ValueError, match="username already exists"):
        service.create_user(
            actor_id=bootstrap["user_id"],
            username="developer",
            password="AnotherStrongDeveloperPassword1!",
            role="developer",
        )
    with pytest.raises(ValueError, match="unknown role"):
        service.create_user(
            actor_id=bootstrap["user_id"],
            username="invalid-role",
            password="AnotherStrongDeveloperPassword1!",
            role="owner",
        )
    with pytest.raises(PermissionError, match="account is inactive"):
        service.get_active_user("usr_missing")
    actions = [event["action"] for event in service.list_audit_events(limit=100)]
    assert "user.create" in actions
    assert service.verify_audit_chain()["valid"] is True


def test_user_account_service_preserves_service_monkeypatch_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    original_new_id = service_module.new_id
    original_hash_password = service_module.hash_password
    hashed_passwords: list[str] = []

    def controlled_new_id(prefix: str) -> str:
        return "usr_controlled" if prefix == "usr" else original_new_id(prefix)

    def controlled_hash_password(password: str) -> str:
        hashed_passwords.append(password)
        return original_hash_password(password)

    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "hash_password", controlled_hash_password)
    created = service.create_user(
        actor_id=bootstrap["user_id"],
        username="controlled",
        password="VeryStrongControlledPassword1!",
        role="auditor",
    )

    assert created["id"] == "usr_controlled"
    assert hashed_passwords == ["VeryStrongControlledPassword1!"]
    assert service.authenticate(
        username="controlled",
        password="VeryStrongControlledPassword1!",
    )["id"] == "usr_controlled"


def test_composition_exposes_shared_user_account_service(tmp_path: Path) -> None:
    app = FastAPI()
    composition = install_composed_product_platform(
        app,
        config=product_config(tmp_path),
        repository_root=tmp_path,
    )

    assert app.state.voodoo_user_account_service is composition.user_account_service
    assert composition.service.user_account_service is composition.user_account_service
    assert composition.user_account_service.db is composition.service.db
    assert composition.user_account_service.audit_ledger is composition.audit_ledger
''',
    encoding="utf-8",
)

doc = ROOT / "docs" / "product" / "USER_ACCOUNT_SERVICE_COMPOSITION_BOUNDARY.md"
if doc.exists():
    raise SystemExit("user account service document already exists")
doc.write_text(
    '''# User Account Service Composition Boundary

## Status

Implemented as the canonical active-user lookup and ordinary user creation boundary.

## Purpose

`UserAccountService` owns active-account lookup, ordinary administrator-driven user creation, governed role validation, password hashing and creation audit evidence. `ProductService` preserves the existing public method surface while delegating those operations.

## Runtime composition

`install_composed_product_platform` exposes one shared user account service through `ProductComposition` and `app.state.voodoo_user_account_service`.

The service uses the exact product database and audit ledger instances. Mismatches fail closed during construction.

## Preserved invariants

- only governed roles are accepted;
- stored usernames remain trimmed while the immediate create response remains compatible;
- duplicate usernames fail with the existing error;
- inactive, missing or invalid-role accounts fail closed during bearer revalidation;
- user creation, password hashing and audit evidence remain in the same governed operation;
- existing method signatures, response fields and error behavior remain unchanged;
- `new_id` and password-hasher monkeypatch bridges remain compatible.

Bootstrap user creation, password authentication, dummy-hash timing protection and authentication rate limiting intentionally remain in `ProductService`.

No database migration or stored-data transformation is required.

## Explicitly disabled

This boundary does not add routes, change permissions, alter bootstrap or login semantics, enable external sign-in, release, deploy or enable production effects.
''',
    encoding="utf-8",
)

for path in (
    account,
    service,
    composition,
    statement_test,
    readiness,
    test,
    doc,
):
    text = path.read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).rstrip() + "\n"
    path.write_text(normalized, encoding="utf-8")
