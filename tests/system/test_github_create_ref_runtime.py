from __future__ import annotations

import io
import urllib.error

import pytest

from voodoo_product.github_create_ref_provider import GitHubCreateRefRequest
from voodoo_product.github_create_ref_runtime import (
    GitHubApiCreateRefTransport,
    GitHubCreateRefTransportAmbiguous,
)


def request() -> GitHubCreateRefRequest:
    return GitHubCreateRefRequest(
        repository="nulleimy/V-One",
        ref="refs/heads/vone-canary/f4b-test",
        sha="a" * 40,
        target_digest="1" * 64,
        target_binding_digest="2" * 64,
        capability_definition_identity="3" * 64,
        runner_boundary_digest="4" * 64,
        credential_decision_digest="5" * 64,
        controlled_write_requirement_digest="6" * 64,
        atomic_provider_condition_contract_identity="7" * 64,
        operation="CREATE_REF",
        create_semantics="CREATE_ONLY",
        max_provider_mutations=1,
        request_revision="github-create-ref-request/f4b-test-r1",
        request_digest="8" * 64,
    )


class Response:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self) -> bytes:
        return (
            b'{"ref":"refs/heads/vone-canary/f4b-test",'
            b'"object":{"type":"commit","sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}'
        )


def test_transport_is_one_shot_and_parses_exact_201(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    transport = GitHubApiCreateRefTransport(token="secret-in-memory")
    result = transport.create_ref(request=request())

    assert result.status_code == 201
    assert result.ref == "refs/heads/vone-canary/f4b-test"
    assert result.object_sha == "a" * 40
    assert "token" not in result.to_dict()

    with pytest.raises(PermissionError, match="F4B_CREATE_REF_TRANSPORT_ALREADY_USED"):
        transport.create_ref(request=request())


def test_http_rejection_is_classified_without_retry(monkeypatch) -> None:
    calls = 0

    def reject(*args, **kwargs):
        nonlocal calls
        del args, kwargs
        calls += 1
        raise urllib.error.HTTPError(
            url="https://api.github.com/example",
            code=422,
            msg="unprocessable",
            hdrs=None,
            fp=io.BytesIO(b"{}"),
        )

    monkeypatch.setattr("urllib.request.urlopen", reject)
    result = GitHubApiCreateRefTransport(token="secret-in-memory").create_ref(
        request=request()
    )
    assert calls == 1
    assert result.status_code == 422
    assert result.ref is None
    assert result.object_sha is None


def test_network_ambiguity_is_fail_closed_and_never_retried(monkeypatch) -> None:
    calls = 0

    def ambiguous(*args, **kwargs):
        nonlocal calls
        del args, kwargs
        calls += 1
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr("urllib.request.urlopen", ambiguous)
    transport = GitHubApiCreateRefTransport(token="secret-in-memory")
    with pytest.raises(
        GitHubCreateRefTransportAmbiguous,
        match="F4B_CREATE_REF_PROVIDER_OUTCOME_AMBIGUOUS_NO_RETRY",
    ):
        transport.create_ref(request=request())
    assert calls == 1

    with pytest.raises(PermissionError, match="F4B_CREATE_REF_TRANSPORT_ALREADY_USED"):
        transport.create_ref(request=request())
