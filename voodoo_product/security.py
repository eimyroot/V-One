from __future__ import annotations

import base64
import binascii
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

_SESSION_FORMAT_VERSION = "v2"
_SESSION_ISSUER = "voodoo-one"
_SESSION_AUDIENCE = "voodoo-one-control-plane"
_SESSION_SIGNING_PURPOSE = b"session-token/v2"
_SESSION_REFERENCE_PURPOSE = b"session-reference/v1"
_KEY_DERIVATION_DOMAIN = b"voodoo-one\x00key-derivation\x00"
_MIN_TOKEN_TTL_SECONDS = 300
_MAX_TOKEN_TTL_SECONDS = 86_400
_MAX_TOKEN_LENGTH = 4_096
_CLOCK_SKEW_SECONDS = 60


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not value:
        raise ValueError("empty base64url value")
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def _derive_key(secret: str, *, purpose: bytes) -> bytes:
    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) < 32:
        raise ValueError("secret must contain at least 32 bytes")
    return hmac.new(secret_bytes, _KEY_DERIVATION_DOMAIN + purpose, hashlib.sha256).digest()


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
    except (binascii.Error, OverflowError, TypeError, ValueError):
        return False


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    username: str
    role: str

    def can(self, permission: str) -> bool:
        permissions = ROLE_PERMISSIONS.get(self.role, frozenset())
        return "*" in permissions or permission in permissions


@dataclass(frozen=True, slots=True)
class VerifiedSessionToken:
    principal: Principal
    session_id: str
    issued_at: int
    expires_at: int


def issue_token(
    *,
    secret: str,
    user_id: str,
    username: str,
    role: str,
    ttl_seconds: int,
) -> str:
    if not 1 <= len(user_id) <= 128:
        raise ValueError("user ID is invalid")
    if not 1 <= len(username) <= 80:
        raise ValueError("username is invalid")
    if role not in ROLE_PERMISSIONS:
        raise ValueError("unknown role")
    if not _MIN_TOKEN_TTL_SECONDS <= ttl_seconds <= _MAX_TOKEN_TTL_SECONDS:
        raise ValueError("token TTL is invalid")

    now = int(time.time())
    payload = {
        "aud": _SESSION_AUDIENCE,
        "exp": now + ttl_seconds,
        "iat": now,
        "iss": _SESSION_ISSUER,
        "nonce": secrets.token_urlsafe(12),
        "role": role,
        "sub": user_id,
        "username": username,
    }
    encoded_payload = _b64url_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(
        _derive_key(secret, purpose=_SESSION_SIGNING_PURPOSE),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{_SESSION_FORMAT_VERSION}.{encoded_payload}.{_b64url_encode(signature)}"


def verify_session_token(*, secret: str, token: str) -> VerifiedSessionToken:
    try:
        if not token or len(token) > _MAX_TOKEN_LENGTH:
            raise ValueError("invalid token length")
        version, encoded_payload, encoded_signature = token.split(".", 2)
        if version != _SESSION_FORMAT_VERSION:
            raise ValueError("unsupported token version")
        expected_signature = hmac.new(
            _derive_key(secret, purpose=_SESSION_SIGNING_PURPOSE),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        supplied_signature = _b64url_decode(encoded_signature)
        if len(supplied_signature) != hashlib.sha256().digest_size or not hmac.compare_digest(
            expected_signature, supplied_signature
        ):
            raise ValueError("invalid token signature")

        decoded_payload = _b64url_decode(encoded_payload)
        payload: dict[str, Any] = json.loads(decoded_payload.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid token payload")
        if payload.get("iss") != _SESSION_ISSUER or payload.get("aud") != _SESSION_AUDIENCE:
            raise ValueError("invalid token context")

        issued_at = payload.get("iat")
        expires_at = payload.get("exp")
        if type(issued_at) is not int or type(expires_at) is not int:
            raise ValueError("invalid token timestamps")
        now = int(time.time())
        if issued_at > now + _CLOCK_SKEW_SECONDS:
            raise ValueError("token issued in the future")
        if expires_at <= now or expires_at <= issued_at:
            raise ValueError("token expired")
        if expires_at - issued_at > _MAX_TOKEN_TTL_SECONDS:
            raise ValueError("token lifetime is invalid")

        user_id = payload.get("sub")
        username = payload.get("username")
        nonce = payload.get("nonce")
        role = payload.get("role")
        if not isinstance(user_id, str) or not 1 <= len(user_id) <= 128:
            raise ValueError("invalid subject")
        if not isinstance(username, str) or not 1 <= len(username) <= 80:
            raise ValueError("invalid username")
        if not isinstance(nonce, str) or not 16 <= len(nonce) <= 128:
            raise ValueError("invalid nonce")
        if not isinstance(role, str) or role not in ROLE_PERMISSIONS:
            raise ValueError("unknown role")

        return VerifiedSessionToken(
            principal=Principal(user_id=user_id, username=username, role=role),
            session_id=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
    except (
        binascii.Error,
        KeyError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError("invalid authentication token") from exc


def verify_token(*, secret: str, token: str) -> Principal:
    return verify_session_token(secret=secret, token=token).principal


def session_reference(*, secret: str, session_id: str) -> str:
    if not isinstance(session_id, str) or not 16 <= len(session_id) <= 128:
        raise ValueError("session ID is invalid")
    return hmac.new(
        _derive_key(secret, purpose=_SESSION_REFERENCE_PURPOSE),
        session_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
