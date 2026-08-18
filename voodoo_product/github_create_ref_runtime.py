from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any, Final

from .github_create_ref_provider import (
    GITHUB_CREATE_REF_SOURCE_IDENTITY,
    GitHubCreateRefDenied,
    GitHubCreateRefProviderResponse,
    GitHubCreateRefRequest,
)

GITHUB_API_BASE: Final = "https://api.github.com"
GITHUB_API_VERSION: Final = "2022-11-28"
GITHUB_ACCEPT: Final = "application/vnd.github+json"
USER_AGENT: Final = "v-one-f4b-create-ref/1"
RESPONSE_REVISION: Final = "github-create-ref-provider-response/f4b-live-r1"


class GitHubCreateRefTransportAmbiguous(RuntimeError):
    """The provider outcome cannot be classified safely; automatic retry is forbidden."""


class GitHubApiCreateRefTransport:
    """One-shot concrete F4b transport for GitHub's create-reference endpoint.

    The token is process-local secret material and is never serialized. This adapter intentionally
    exposes only ``create_ref`` and refuses a second invocation even after a provider rejection.
    Network/transport ambiguity is fail-closed and never retried automatically.
    """

    source_identity = GITHUB_CREATE_REF_SOURCE_IDENTITY

    def __init__(self, *, token: str, timeout_seconds: float = 20.0) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token is required")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be numeric")
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("timeout_seconds must be between 0 and 60")
        self._token = token.strip()
        self._timeout_seconds = float(timeout_seconds)
        self._used = False

    def create_ref(
        self,
        *,
        request: GitHubCreateRefRequest,
    ) -> GitHubCreateRefProviderResponse:
        if not isinstance(request, GitHubCreateRefRequest):
            raise ValueError("request must be GitHubCreateRefRequest")
        if self._used:
            raise GitHubCreateRefDenied("F4B_CREATE_REF_TRANSPORT_ALREADY_USED")
        self._used = True

        owner, repository = request.repository.split("/", 1)
        endpoint = (
            f"{GITHUB_API_BASE}/repos/{urllib.parse.quote(owner, safe='')}"
            f"/{urllib.parse.quote(repository, safe='')}/git/refs"
        )
        payload = json.dumps(
            {"ref": request.ref, "sha": request.sha},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        provider_request = urllib.request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={
                "Accept": GITHUB_ACCEPT,
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                provider_request,
                timeout=self._timeout_seconds,
            ) as response:
                status_code = int(response.status)
                body = response.read()
        except urllib.error.HTTPError as exc:
            # HTTPError proves that GitHub returned a classified HTTP response. Never retry here.
            return GitHubCreateRefProviderResponse.rejected(
                status_code=int(exc.code),
                source_identity=self.source_identity,
                response_revision=RESPONSE_REVISION,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # The request may have crossed the network boundary before failure. Retrying could
            # create a second ambiguous effect, so expose UNKNOWN/ambiguous outcome instead.
            raise GitHubCreateRefTransportAmbiguous(
                "F4B_CREATE_REF_PROVIDER_OUTCOME_AMBIGUOUS_NO_RETRY"
            ) from exc

        if status_code != 201:
            return GitHubCreateRefProviderResponse.rejected(
                status_code=status_code,
                source_identity=self.source_identity,
                response_revision=RESPONSE_REVISION,
            )

        parsed = self._parse_json_object(body)
        ref = parsed.get("ref")
        object_value = parsed.get("object")
        if not isinstance(object_value, Mapping):
            raise GitHubCreateRefTransportAmbiguous(
                "F4B_CREATE_REF_201_RESPONSE_OBJECT_INVALID"
            )
        object_type = object_value.get("type")
        object_sha = object_value.get("sha")
        if not isinstance(ref, str) or object_type != "commit" or not isinstance(object_sha, str):
            raise GitHubCreateRefTransportAmbiguous(
                "F4B_CREATE_REF_201_RESPONSE_INVALID"
            )
        return GitHubCreateRefProviderResponse.created(
            ref=ref,
            object_sha=object_sha,
            source_identity=self.source_identity,
            response_revision=RESPONSE_REVISION,
        )

    @staticmethod
    def _parse_json_object(body: bytes) -> Mapping[str, Any]:
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubCreateRefTransportAmbiguous(
                "F4B_CREATE_REF_PROVIDER_RESPONSE_INVALID_JSON"
            ) from exc
        if not isinstance(value, Mapping):
            raise GitHubCreateRefTransportAmbiguous(
                "F4B_CREATE_REF_PROVIDER_RESPONSE_NOT_OBJECT"
            )
        return value
