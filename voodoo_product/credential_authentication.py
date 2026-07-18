from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any

from . import statements as sql
from .persistence import ProductDatabaseAdapter
from .security import hash_password, verify_password

PasswordHasher = Callable[[str], str]
PasswordVerifier = Callable[[str, str], bool]
SecretFactory = Callable[[], str]


def _new_dummy_secret() -> str:
    return secrets.token_urlsafe(32)


class CredentialAuthenticationService:
    """Own local password lookup and constant-work credential verification."""

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        password_hasher: PasswordHasher = hash_password,
        password_verifier: PasswordVerifier = verify_password,
        secret_factory: SecretFactory = _new_dummy_secret,
    ) -> None:
        self.db = database
        self._password_verifier = password_verifier
        self._dummy_password_hash = password_hasher(
            f"VOODOO-invalid-account-{secret_factory()}"
        )

    def authenticate(self, *, username: str, password: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                sql.SELECT_USER_FOR_AUTH,
                (username.strip(),),
            ).fetchone()
        encoded_password = (
            str(row["password_hash"]) if row is not None else self._dummy_password_hash
        )
        password_valid = self._password_verifier(password, encoded_password)
        if row is None or not int(row["active"]) or not password_valid:
            raise PermissionError("invalid credentials")
        return {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
        }
