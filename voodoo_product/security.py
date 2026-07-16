from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

ROLE_PERMISSIONS = {
    "viewer": frozenset({"read"}),
    "developer": frozenset({"read", "change.write"}),
    "operator": frozenset({"read", "approval.review", "execution.run"}),
    "security_reviewer": frozenset(
        {
            "read",
            "approval.review",
            "evidence.read",
            "emergency.control",
            "execution.recover",
        }
    ),
    "auditor": frozenset({"read", "evidence.read"}),
    "administrator": frozenset({"*"}),
}


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_value, digest_value = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = _b64url_decode(salt_value)
        expected = _b64url_decode(digest_value)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    username: str
    role: str

    def can(self, permission: str) -> bool:
        permissions = ROLE_PERMISSIONS.get(self.role, frozenset())
        return "*" in permissions or permission in permissions


def issue_token(
    *,
    secret: str,
    user_id: str,
    username: str,
    role: str,
    ttl_seconds: int,
) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded_payload = _b64url_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(
        secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    return f"v1.{encoded_payload}.{_b64url_encode(signature)}"


def verify_token(*, secret: str, token: str) -> Principal:
    try:
        version, encoded_payload, encoded_signature = token.split(".", 2)
        if version != "v1":
            raise ValueError("unsupported token version")
        expected_signature = hmac.new(
            secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        supplied_signature = _b64url_decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise ValueError("invalid token signature")
        payload: dict[str, Any] = json.loads(_b64url_decode(encoded_payload))
        now = int(time.time())
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        if issued_at > now + 60:
            raise ValueError("token issued in the future")
        if expires_at <= now or expires_at <= issued_at:
            raise ValueError("token expired")
        role = str(payload["role"])
        if role not in ROLE_PERMISSIONS:
            raise ValueError("unknown role")
        return Principal(
            user_id=str(payload["sub"]),
            username=str(payload["username"]),
            role=role,
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid authentication token") from exc
