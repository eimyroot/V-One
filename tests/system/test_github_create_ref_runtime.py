from __future__ import annotations

import pytest

from voodoo_product.github_create_ref_provider import GitHubCreateRefRequest
from voodoo_product.github_create_ref_runtime import (
    GitHubApiCreateRefTransport,
    GitHubCreateRefTransportAmbiguous,
)


def request() -> GitHubCreateRefRequest:
    # The transport consumes an already-validated F3 request. Build a minimal instance without
    # re-testing F3 digest construction here; F3 owns that contract and its system tests.
    value = object.__new__(GitHubCreateRefRequest)
    object.__setattr__(value, "repository", "nulleimy/V-One")
    object.__setattr__(value, "ref", "refs/heads/vone-canary/f4b-test")
    object.__setattr__(value, "sha", "a" * 40)
    return value


class Response:
    def __init__(self, status: int, body: bytes = b"{}") -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body


class Connection:
    def __init__(self, response: Response | None = None, *, fail: bool = False) -> None:
        self.response = response or Response(500)
        self.fail = fail
        self.calls = 0
        self.closed = False

    def request(self, method, path, body=None, headers=None) -> None:
        del method, path, body, headers
        self.calls += 1
        if self.fail:
            raise OSError("connection reset")

    def getresponse(self) -> Response:
        return self.response

    def close(self) -> None:
        self.closed = True


def test_transport_is_one_shot_and_parses_exact_201(monkeypatch) -> None:
    connection = Connection(
        Response(
            201,
            b'{"ref":"refs/heads/vone-canary/f4b-test",'
            b'"object":{"type":"commit","sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}',
        )
    )
    monkeypatch.setattr(
        "http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    transport = GitHubApiCreateRefTransport(token="secret-in-memory")
    result = transport.create_ref(request=request())

    assert connection.calls == 1
    assert connection.closed is True
    assert result.status_code == 201
    assert result.ref == "refs/heads/vone-canary/f4b-test"
    assert result.object_sha == "a" * 40
    assert "token" not in result.to_dict()

    with pytest.raises(PermissionError, match="F4B_CREATE_REF_TRANSPORT_ALREADY_USED"):
        transport.create_ref(request=request())


def test_http_rejection_is_classified_without_retry(monkeypatch) -> None:
    connection = Connection(Response(422))
    monkeypatch.setattr(
        "http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    result = GitHubApiCreateRefTransport(token="secret-in-memory").create_ref(
        request=request()
    )
    assert connection.calls == 1
    assert result.status_code == 422
    assert result.ref is None
    assert result.object_sha is None


def test_network_ambiguity_is_fail_closed_and_never_retried(monkeypatch) -> None:
    connection = Connection(fail=True)
    monkeypatch.setattr(
        "http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    transport = GitHubApiCreateRefTransport(token="secret-in-memory")
    with pytest.raises(
        GitHubCreateRefTransportAmbiguous,
        match="F4B_CREATE_REF_PROVIDER_OUTCOME_AMBIGUOUS_NO_RETRY",
    ):
        transport.create_ref(request=request())
    assert connection.calls == 1
    assert connection.closed is True

    with pytest.raises(PermissionError, match="F4B_CREATE_REF_TRANSPORT_ALREADY_USED"):
        transport.create_ref(request=request())
