from __future__ import annotations

import pytest

from voodoo_product.github_delete_ref_runtime import (
    GitHubApiDeleteRefTransport,
    GitHubDeleteRefRejected,
    GitHubDeleteRefTransportAmbiguous,
)
from voodoo_product.rollback_control import GitHubDeleteRefRequest
from voodoo_product.rollback_runtime import RollbackWriteEffectPreflight


def request() -> GitHubDeleteRefRequest:
    value = object.__new__(GitHubDeleteRefRequest)
    object.__setattr__(value, "repository", "nulleimy/V-One")
    object.__setattr__(value, "ref", "refs/heads/vone-canary/f4b-pr120-32185703943")
    object.__setattr__(value, "expected_sha", "a" * 40)
    object.__setattr__(value, "request_digest", "b" * 64)
    return value


def preflight() -> RollbackWriteEffectPreflight:
    value = object.__new__(RollbackWriteEffectPreflight)
    object.__setattr__(value, "request_digest", "b" * 64)
    object.__setattr__(value, "observed_ref_sha", "a" * 40)
    return value


class Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def read(self) -> bytes:
        return b""


class Connection:
    def __init__(self, status: int = 204, *, fail: bool = False) -> None:
        self.response = Response(status)
        self.fail = fail
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def request(self, method, path, body=None, headers=None) -> None:
        del body, headers
        self.calls.append((method, path))
        if self.fail:
            raise OSError("connection reset")

    def getresponse(self) -> Response:
        return self.response

    def close(self) -> None:
        self.closed = True


def test_delete_transport_is_one_shot_fixed_host_operation(monkeypatch) -> None:
    connection = Connection()
    monkeypatch.setattr(
        "http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    transport = GitHubApiDeleteRefTransport(token="secret-never-serialized")
    result = transport.delete_ref(request=request(), preflight=preflight())

    assert connection.calls == [
        (
            "DELETE",
            "/repos/nulleimy/V-One/git/refs/heads/vone-canary/f4b-pr120-32185703943",
        )
    ]
    assert connection.closed is True
    assert result.http_status == 204
    assert "secret-never-serialized" not in str(result.to_dict())

    with pytest.raises(PermissionError, match="F6_DELETE_REF_TRANSPORT_ALREADY_USED"):
        transport.delete_ref(request=request(), preflight=preflight())


def test_delete_transport_rejects_stale_preflight_before_network(monkeypatch) -> None:
    connection = Connection()
    monkeypatch.setattr(
        "http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    stale = preflight()
    object.__setattr__(stale, "observed_ref_sha", "c" * 40)
    with pytest.raises(PermissionError, match="F6_DELETE_REF_PREFLIGHT_SHA_MISMATCH"):
        GitHubApiDeleteRefTransport(token="secret").delete_ref(
            request=request(),
            preflight=stale,
        )
    assert connection.calls == []


def test_known_provider_rejection_is_not_retried(monkeypatch) -> None:
    connection = Connection(status=422)
    monkeypatch.setattr(
        "http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    with pytest.raises(GitHubDeleteRefRejected) as exc_info:
        GitHubApiDeleteRefTransport(token="secret").delete_ref(
            request=request(),
            preflight=preflight(),
        )
    assert exc_info.value.status_code == 422
    assert len(connection.calls) == 1


def test_network_ambiguity_is_fail_closed_without_retry(monkeypatch) -> None:
    connection = Connection(fail=True)
    monkeypatch.setattr(
        "http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    transport = GitHubApiDeleteRefTransport(token="secret")
    with pytest.raises(
        GitHubDeleteRefTransportAmbiguous,
        match="F6_DELETE_REF_PROVIDER_OUTCOME_AMBIGUOUS_NO_RETRY",
    ):
        transport.delete_ref(request=request(), preflight=preflight())
    assert len(connection.calls) == 1
    assert connection.closed is True
