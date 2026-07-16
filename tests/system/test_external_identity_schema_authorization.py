from __future__ import annotations

from pathlib import Path

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.service import ProductService

ISSUER = "https://identity.example.com/tenant"


def test_direct_database_writes_cannot_bypass_identity_administrator_boundary(
    tmp_path: Path,
) -> None:
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
    developer = service.create_user(
        actor_id=str(bootstrap["user_id"]),
        username="developer",
        password="VeryStrongDeveloperPassword1!",
        role="developer",
    )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            """
            INSERT INTO external_identity_bindings(
                id, provider, issuer, subject, user_id, created_by, created_at
            ) VALUES (?, 'oidc', ?, ?, ?, ?, ?)
            """,
            (
                "xid_bypass",
                ISSUER,
                "subject-bypass",
                developer["id"],
                developer["id"],
                "2026-07-16T20:00:00.000+00:00",
            ),
        )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            """
            INSERT INTO external_role_mappings(
                id, provider, issuer, external_group, internal_role, created_by, created_at
            ) VALUES (?, 'oidc', ?, ?, 'administrator', ?, ?)
            """,
            (
                "xrm_bypass",
                ISSUER,
                "unauthorized-admins",
                developer["id"],
                "2026-07-16T20:00:00.000+00:00",
            ),
        )
