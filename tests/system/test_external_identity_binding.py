from __future__ import annotations

from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.external_identity import ExternalIdentityRegistry
from voodoo_product.identity import ExternalIdentityClaims
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.service import ProductService

ISSUER = "https://identity.example.com/tenant"


def build_registry(tmp_path: Path) -> tuple[ProductService, ExternalIdentityRegistry, dict[str, object]]:
    service = ProductService(
        ProductConfig(
            environment="test",
            database_path=tmp_path / "product.sqlite3",
            sandbox_root=tmp_path / "sandboxes",
            session_signing_secret="s" * 64,
            bootstrap_token="b" * 48,
        )
    )
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    return service, ExternalIdentityRegistry(service.db), bootstrap


def test_external_claim_contract_is_exact_and_bounded() -> None:
    claims = ExternalIdentityClaims(
        provider="oidc",
        issuer=ISSUER,
        subject="subject-123",
        groups=("engineering",),
    )

    assert claims.subject == "subject-123"
    with pytest.raises(ValueError, match="provider is unsupported"):
        ExternalIdentityClaims(
            provider="saml",
            issuer=ISSUER,
            subject="subject-123",
            groups=("engineering",),
        )
    with pytest.raises(ValueError, match="absolute HTTPS URL"):
        ExternalIdentityClaims(
            provider="oidc",
            issuer="http://identity.example.com",
            subject="subject-123",
            groups=("engineering",),
        )
    with pytest.raises(ValueError, match="immutable tuple"):
        ExternalIdentityClaims(  # type: ignore[arg-type]
            provider="oidc",
            issuer=ISSUER,
            subject="subject-123",
            groups=["engineering"],
        )
    with pytest.raises(ValueError, match="must be unique"):
        ExternalIdentityClaims(
            provider="oidc",
            issuer=ISSUER,
            subject="subject-123",
            groups=("engineering", "engineering"),
        )


def test_only_active_administrator_can_provision_external_identity(tmp_path: Path) -> None:
    service, registry, bootstrap = build_registry(tmp_path)
    developer = service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="developer",
        password="VeryStrongDeveloperPassword1!",
        role="developer",
    )

    with pytest.raises(PermissionError, match="requires an administrator"):
        registry.create_role_mapping(
            actor_id=developer["id"],
            provider="oidc",
            issuer=ISSUER,
            external_group="engineering",
            internal_role="developer",
        )
    with pytest.raises(PermissionError, match="requires an administrator"):
        registry.create_binding(
            actor_id=developer["id"],
            provider="oidc",
            issuer=ISSUER,
            subject="subject-developer",
            user_id=developer["id"],
        )


def test_exact_binding_and_allowlisted_group_confirm_current_internal_role(
    tmp_path: Path,
) -> None:
    service, registry, bootstrap = build_registry(tmp_path)
    developer = service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="developer",
        password="VeryStrongDeveloperPassword1!",
        role="developer",
    )
    mapping = registry.create_role_mapping(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        external_group="engineering",
        internal_role="developer",
    )
    binding = registry.create_binding(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        subject="subject-developer",
        user_id=developer["id"],
    )

    resolved = registry.resolve(
        ExternalIdentityClaims(
            provider="oidc",
            issuer=ISSUER,
            subject="subject-developer",
            groups=("unmapped-extra-group", "engineering"),
        )
    )

    assert resolved == {
        "id": developer["id"],
        "username": "developer",
        "role": "developer",
    }
    assert mapping["created_by"] == bootstrap["user_id"]
    assert binding["created_by"] == bootstrap["user_id"]

    with pytest.raises(PermissionError, match="not authorized"):
        registry.resolve(
            ExternalIdentityClaims(
                provider="oidc",
                issuer="https://identity.example.com/other",
                subject="subject-developer",
                groups=("engineering",),
            )
        )
    with pytest.raises(PermissionError, match="not authorized"):
        registry.resolve(
            ExternalIdentityClaims(
                provider="oidc",
                issuer=ISSUER,
                subject="subject-other",
                groups=("engineering",),
            )
        )


def test_external_groups_cannot_escalate_or_create_ambiguous_roles(tmp_path: Path) -> None:
    service, registry, bootstrap = build_registry(tmp_path)
    developer = service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="developer",
        password="VeryStrongDeveloperPassword1!",
        role="developer",
    )
    registry.create_binding(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        subject="subject-developer",
        user_id=developer["id"],
    )
    registry.create_role_mapping(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        external_group="engineering",
        internal_role="developer",
    )
    registry.create_role_mapping(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        external_group="production-operators",
        internal_role="operator",
    )

    with pytest.raises(PermissionError, match="role authorization failed"):
        registry.resolve(
            ExternalIdentityClaims(
                provider="oidc",
                issuer=ISSUER,
                subject="subject-developer",
                groups=("production-operators",),
            )
        )
    with pytest.raises(PermissionError, match="role authorization failed"):
        registry.resolve(
            ExternalIdentityClaims(
                provider="oidc",
                issuer=ISSUER,
                subject="subject-developer",
                groups=("engineering", "production-operators"),
            )
        )
    with pytest.raises(PermissionError, match="role authorization failed"):
        registry.resolve(
            ExternalIdentityClaims(
                provider="oidc",
                issuer=ISSUER,
                subject="subject-developer",
                groups=("unmapped",),
            )
        )


def test_bindings_and_role_mappings_are_unique_and_append_only(tmp_path: Path) -> None:
    service, registry, bootstrap = build_registry(tmp_path)
    first = service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="first",
        password="VeryStrongFirstPassword1!",
        role="developer",
    )
    second = service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="second",
        password="VeryStrongSecondPassword1!",
        role="developer",
    )
    binding = registry.create_binding(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        subject="subject-first",
        user_id=first["id"],
    )
    mapping = registry.create_role_mapping(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        external_group="engineering",
        internal_role="developer",
    )

    with pytest.raises(ValueError, match="conflicts with existing identity"):
        registry.create_binding(
            actor_id=str(bootstrap["user_id"]),
            provider="oidc",
            issuer=ISSUER,
            subject="subject-first",
            user_id=second["id"],
        )
    with pytest.raises(ValueError, match="conflicts with existing identity"):
        registry.create_binding(
            actor_id=str(bootstrap["user_id"]),
            provider="oidc",
            issuer=ISSUER,
            subject="another-subject",
            user_id=first["id"],
        )
    with pytest.raises(ValueError, match="already has an immutable role mapping"):
        registry.create_role_mapping(
            actor_id=str(bootstrap["user_id"]),
            provider="oidc",
            issuer=ISSUER,
            external_group="engineering",
            internal_role="operator",
        )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "UPDATE external_identity_bindings SET subject = ? WHERE id = ?",
            ("changed", binding["id"]),
        )
    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "DELETE FROM external_identity_bindings WHERE id = ?",
            (binding["id"],),
        )
    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "UPDATE external_role_mappings SET internal_role = ? WHERE id = ?",
            ("operator", mapping["id"]),
        )
    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "DELETE FROM external_role_mappings WHERE id = ?",
            (mapping["id"],),
        )


def test_inactive_bound_user_fails_closed(tmp_path: Path) -> None:
    service, registry, bootstrap = build_registry(tmp_path)
    developer = service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="developer",
        password="VeryStrongDeveloperPassword1!",
        role="developer",
    )
    registry.create_role_mapping(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        external_group="engineering",
        internal_role="developer",
    )
    registry.create_binding(
        actor_id=str(bootstrap["user_id"]),
        provider="oidc",
        issuer=ISSUER,
        subject="subject-developer",
        user_id=developer["id"],
    )
    with service.db.connect() as connection:
        connection.execute("UPDATE users SET active = 0 WHERE id = ?", (developer["id"],))

    with pytest.raises(PermissionError, match="not authorized"):
        registry.resolve(
            ExternalIdentityClaims(
                provider="oidc",
                issuer=ISSUER,
                subject="subject-developer",
                groups=("engineering",),
            )
        )


def test_schema_v6_contains_required_identity_objects(tmp_path: Path) -> None:
    service, _, _ = build_registry(tmp_path)

    with service.db.connect() as connection:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        indexes = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        triggers = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            ).fetchall()
        }

    assert service.db.schema_version() == 6
    assert {"external_identity_bindings", "external_role_mappings"} <= tables
    assert {"idx_external_identity_user", "idx_external_role_mapping_role"} <= indexes
    assert {
        "trg_external_identity_binding_active_user",
        "trg_external_identity_binding_immutable_update",
        "trg_external_identity_binding_immutable_delete",
        "trg_external_role_mapping_immutable_update",
        "trg_external_role_mapping_immutable_delete",
    } <= triggers
