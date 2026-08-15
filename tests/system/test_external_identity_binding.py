from __future__ import annotations

from pathlib import Path

import pytest

from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.external_identity import (
    ExternalIdentityKey,
    ExternalRoleMapping,
    resolve_external_role,
    validate_role_mappings,
)
from voodoo_product.persistence import DatabaseIntegrityError


def initialized_database(tmp_path: Path) -> SQLiteProductDatabase:
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_one', 'one', 'unused', 'viewer', 1, '2026-07-16T12:00:00+00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO users(id, username, password_hash, role, active, created_at)
            VALUES ('usr_two', 'two', 'unused', 'viewer', 1, '2026-07-16T12:00:00+00:00')
            """
        )
    return database


def insert_binding(database: SQLiteProductDatabase) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO external_identity_bindings(
                id, provider, issuer, subject, user_id, created_at
            ) VALUES (
                'xid_one', 'oidc', 'https://identity.example.com', 'subject-one',
                'usr_one', '2026-07-16T12:00:00+00:00'
            )
            """
        )


def test_schema_v6_contains_external_identity_boundary(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)

    assert database.schema_version() == 9
    with database.connect() as connection:
        columns = {
            row["name"]
            for row in connection.execute(
                'PRAGMA table_info("external_identity_bindings")'
            ).fetchall()
        }
    assert columns == {
        "id",
        "provider",
        "issuer",
        "subject",
        "user_id",
        "active",
        "created_at",
        "disabled_at",
    }


def test_binding_identity_is_immutable_and_not_deletable(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)
    insert_binding(database)

    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            "UPDATE external_identity_bindings SET subject = 'changed' WHERE id = 'xid_one'"
        )
    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute("DELETE FROM external_identity_bindings WHERE id = 'xid_one'")


def test_binding_can_be_disabled_once_but_not_reactivated(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)
    insert_binding(database)

    with database.connect() as connection:
        connection.execute(
            """
            UPDATE external_identity_bindings
            SET active = 0, disabled_at = '2026-07-16T13:00:00+00:00'
            WHERE id = 'xid_one'
            """
        )
    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            """
            UPDATE external_identity_bindings
            SET active = 1, disabled_at = NULL
            WHERE id = 'xid_one'
            """
        )


def test_binding_uniqueness_prevents_subject_or_user_rebinding(tmp_path: Path) -> None:
    database = initialized_database(tmp_path)
    insert_binding(database)

    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            """
            INSERT INTO external_identity_bindings(
                id, provider, issuer, subject, user_id, created_at
            ) VALUES (
                'xid_duplicate_subject', 'oidc', 'https://identity.example.com',
                'subject-one', 'usr_two', '2026-07-16T12:00:00+00:00'
            )
            """
        )
    with pytest.raises(DatabaseIntegrityError), database.connect() as connection:
        connection.execute(
            """
            INSERT INTO external_identity_bindings(
                id, provider, issuer, subject, user_id, created_at
            ) VALUES (
                'xid_duplicate_user', 'oidc', 'https://identity.example.com',
                'subject-two', 'usr_one', '2026-07-16T12:00:00+00:00'
            )
            """
        )


def test_external_identity_key_requires_exact_https_issuer() -> None:
    key = ExternalIdentityKey(
        provider="OIDC",
        issuer="https://identity.example.com/",
        subject=" stable-subject ",
    )

    assert key == ExternalIdentityKey(
        provider="oidc",
        issuer="https://identity.example.com",
        subject="stable-subject",
    )
    with pytest.raises(ValueError, match="absolute HTTPS"):
        ExternalIdentityKey(
            provider="oidc",
            issuer="http://identity.example.com",
            subject="subject",
        )


def test_role_mapping_is_explicit_non_admin_and_fail_closed() -> None:
    mappings = validate_role_mappings(
        (
            ExternalRoleMapping("voodoo-viewers", "viewer"),
            ExternalRoleMapping("voodoo-operators", "operator"),
        )
    )

    assert resolve_external_role(("voodoo-operators",), mappings) == "operator"
    with pytest.raises(PermissionError, match="no allowlisted"):
        resolve_external_role(("unknown",), mappings)
    with pytest.raises(PermissionError, match="ambiguous"):
        resolve_external_role(("voodoo-viewers", "voodoo-operators"), mappings)
    with pytest.raises(ValueError, match="cannot grant"):
        ExternalRoleMapping("voodoo-admins", "administrator")
    with pytest.raises(ValueError, match="duplicated"):
        validate_role_mappings(
            (
                ExternalRoleMapping("same-group", "viewer"),
                ExternalRoleMapping("same-group", "operator"),
            )
        )
