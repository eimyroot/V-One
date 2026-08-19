from __future__ import annotations

import http.client
import urllib.parse
from typing import Final

from .rollback_control import (
    GitHubDeleteRefProviderResponse,
    GitHubDeleteRefRequest,
)
from .rollback_runtime import RollbackWriteEffectPreflight

GITHUB_API_HOST: Final = "api.github.com"
GITHUB_API_VERSION: Final = "2022-11-28"
GITHUB_ACCEPT: Final = "application/vnd.github+json"
USER_AGENT: Final = "v-one-f6-delete-ref/1"
SOURCE_IDENTITY: Final = "github-rest/git-delete-ref/v1"
RESPONSE_REVISION: Final = "github-delete-ref-provider-response/f6-r1"


class GitHubDeleteRefTransportAmbiguous(RuntimeError):
    """Provider outcome is uncertain; automatic retry is forbidden."""


class GitHubDeleteRefRejected(PermissionError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"F6_DELETE_REF_PROVIDER_REJECTED:{status_code}")


class GitHubApiDeleteRefTransport:
    """One-shot fixed-host transport for the governed rollback DELETE.

    This class is mutation-capable code, but it carries no authority by itself. It requires an
    already-bound request plus a matching write-effect-preflight/v2. The credential remains
    process-local, the host is fixed to api.github.com, the operation is one-shot, and ambiguous
    outcomes are never retried automatically.
    """

    source_identity = SOURCE_IDENTITY

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

    def delete_ref(
        self,
        *,
        request: GitHubDeleteRefRequest,
        preflight: RollbackWriteEffectPreflight,
    ) -> GitHubDeleteRefProviderResponse:
        if not isinstance(request, GitHubDeleteRefRequest):
            raise ValueError("request must be GitHubDeleteRefRequest")
        if not isinstance(preflight, RollbackWriteEffectPreflight):
            raise ValueError("preflight must be RollbackWriteEffectPreflight")
        if self._used:
            raise PermissionError("F6_DELETE_REF_TRANSPORT_ALREADY_USED")
        if preflight.request_digest != request.request_digest:
            raise PermissionError("F6_DELETE_REF_PREFLIGHT_REQUEST_MISMATCH")
        if preflight.observed_ref_sha != request.expected_sha:
            raise PermissionError("F6_DELETE_REF_PREFLIGHT_SHA_MISMATCH")
        self._used = True

        owner, repository = request.repository.split("/", 1)
        relative_ref = request.ref.removeprefix("refs/")
        path = (
            f"/repos/{urllib.parse.quote(owner, safe='')}"
            f"/{urllib.parse.quote(repository, safe='')}/git/refs/"
            f"{urllib.parse.quote(relative_ref, safe='/')}"
        )
        headers = {
            "Accept": GITHUB_ACCEPT,
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": USER_AGENT,
        }
        connection = http.client.HTTPSConnection(
            GITHUB_API_HOST,
            timeout=self._timeout_seconds,
        )
        try:
            connection.request("DELETE", path, headers=headers)
            response = connection.getresponse()
            status_code = int(response.status)
            response.read()
        except (http.client.HTTPException, TimeoutError, OSError) as exc:
            raise GitHubDeleteRefTransportAmbiguous(
                "F6_DELETE_REF_PROVIDER_OUTCOME_AMBIGUOUS_NO_RETRY"
            ) from exc
        finally:
            connection.close()

        if status_code != 204:
            raise GitHubDeleteRefRejected(status_code)
        return GitHubDeleteRefProviderResponse.deleted(
            ref=request.ref,
            expected_sha=request.expected_sha,
            source_identity=self.source_identity,
            response_revision=RESPONSE_REVISION,
        )
