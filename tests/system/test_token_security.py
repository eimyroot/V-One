from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from voodoo_product.security import issue_token, verify_token

SECRET = "s" * 64


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def test_v2_token_round_trip_uses_explicit_security_context() -> None:
    token = issue_token(
        secret=SECRET,
        user_id="usr_admin",
        username="admin",
        role="administrator",
        ttl_seconds=3_600,
    )

    version, encoded_payload, _ = token.split(".", 2)
    payload = json.loads(base64.urlsafe_b64decode(encoded_payload + "=="))
    principal = verify_token(secret=SECRET, token=token)

    assert version == "v2"
    assert payload["iss"] == "voodoo-one"
    assert payload["aud"] == "voodoo-one-control-plane"
    assert principal.user_id == "usr_admin"
    assert principal.username == "admin"
    assert principal.role == "administrator"


def test_token_signature_is_not_keyed_directly_by_root_secret() -> None:
    token = issue_token(
        secret=SECRET,
        user_id="usr_admin",
        username="admin",
        role="administrator",
        ttl_seconds=3_600,
    )
    _, encoded_payload, encoded_signature = token.split(".", 2)
    supplied_signature = base64.urlsafe_b64decode(encoded_signature + "==")
    raw_root_signature = hmac.new(
        SECRET.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()

    assert not hmac.compare_digest(supplied_signature, raw_root_signature)


def test_legacy_v1_token_is_rejected_fail_closed() -> None:
    now = int(time.time())
    payload = _b64url(
        json.dumps(
            {
                "sub": "usr_admin",
                "username": "admin",
                "role": "administrator",
                "iat": now,
                "exp": now + 3_600,
                "nonce": "legacy-token-nonce",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = _b64url(
        hmac.new(SECRET.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    )

    with pytest.raises(ValueError, match="invalid authentication token"):
        verify_token(secret=SECRET, token=f"v1.{payload}.{signature}")


def test_malformed_or_wrongly_keyed_token_is_rejected() -> None:
    token = issue_token(
        secret=SECRET,
        user_id="usr_admin",
        username="admin",
        role="administrator",
        ttl_seconds=3_600,
    )

    with pytest.raises(ValueError, match="invalid authentication token"):
        verify_token(secret="x" * 64, token=token)
    with pytest.raises(ValueError, match="invalid authentication token"):
        verify_token(secret=SECRET, token="v2.not-base64!.not-base64!")


def test_token_issue_contract_rejects_invalid_lifetime_and_role() -> None:
    with pytest.raises(ValueError, match="token TTL is invalid"):
        issue_token(
            secret=SECRET,
            user_id="usr_admin",
            username="admin",
            role="administrator",
            ttl_seconds=299,
        )
    with pytest.raises(ValueError, match="unknown role"):
        issue_token(
            secret=SECRET,
            user_id="usr_admin",
            username="admin",
            role="root",
            ttl_seconds=3_600,
        )
