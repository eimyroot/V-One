from __future__ import annotations

import http.client
import json
import urllib.parse
from typing import Final

from .execution_capsule import ExecutionCapsule
from .execution_lease import ExecutionLease
from .isolated_runner import (
    IsolatedRuntimeBootstrap,
    PreparedIsolatedRuntime,
    ReadOnlyRuntimeActivation,
)

GITHUB_ACTIONS_PROVIDER: Final = "github-actions"
GITHUB_API_SOURCE_IDENTITY: Final = "github-api/git-ref/v1"


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _require_digest(value: object, *, field: str) -> str:
    text = _require_text(value, field=field)
    if (
        len(text) != 64
        or text.casefold() != text
        or any(character not in "0123456789abcdef" for character in text)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


class GitHubActionsIsolatedRuntimeProvider:
    """Concrete D3 provider for a pre-hardened GitHub Actions Docker runtime.

    The workflow is responsible for enforcing read-only rootfs, no-new-privileges,
    dropped Linux capabilities, resource limits and default-deny egress before this
    provider is instantiated. The provider reports the exact content-addressed runtime
    profile into D3; it does not create credentials and does not perform provider reads.
    """

    def __init__(
        self,
        *,
        provider_instance_id: str,
        runner_class: str,
        environment: str,
        rootfs_digest: str,
        resource_limit_profile_digest: str,
        network_policy_digest: str,
        bootstrap_revision: str,
        activation_revision: str,
    ) -> None:
        self.provider_instance_id = _require_text(
            provider_instance_id,
            field="provider_instance_id",
        )
        self.runner_class = _require_text(runner_class, field="runner_class")
        self.environment = _require_text(environment, field="environment")
        self.rootfs_digest = _require_digest(rootfs_digest, field="rootfs_digest")
        self.resource_limit_profile_digest = _require_digest(
            resource_limit_profile_digest,
            field="resource_limit_profile_digest",
        )
        self.network_policy_digest = _require_digest(
            network_policy_digest,
            field="network_policy_digest",
        )
        self.bootstrap_revision = _require_text(
            bootstrap_revision,
            field="bootstrap_revision",
        )
        self.activation_revision = _require_text(
            activation_revision,
            field="activation_revision",
        )

    def bootstrap(
        self,
        *,
        lease: ExecutionLease,
        capsule: ExecutionCapsule,
    ) -> IsolatedRuntimeBootstrap:
        if not isinstance(lease, ExecutionLease):
            raise ValueError("lease must be ExecutionLease")
        if not isinstance(capsule, ExecutionCapsule):
            raise ValueError("capsule must be ExecutionCapsule")
        return IsolatedRuntimeBootstrap.create(
            provider=GITHUB_ACTIONS_PROVIDER,
            provider_instance_id=self.provider_instance_id,
            runner_class=self.runner_class,
            environment=self.environment,
            rootfs_digest=self.rootfs_digest,
            resource_limit_profile_digest=self.resource_limit_profile_digest,
            network_policy_digest=self.network_policy_digest,
            bootstrap_revision=self.bootstrap_revision,
        )

    def activate_read_only(
        self,
        *,
        prepared: PreparedIsolatedRuntime,
    ) -> ReadOnlyRuntimeActivation:
        if not isinstance(prepared, PreparedIsolatedRuntime):
            raise ValueError("prepared must be PreparedIsolatedRuntime")
        return ReadOnlyRuntimeActivation.create(
            bootstrap=prepared.bootstrap,
            identity=prepared.identity,
            boundary=prepared.boundary,
            decision=prepared.decision,
            lease=prepared.lease,
            activation_revision=self.activation_revision,
        )


class GitHubApiRefReadTransport:
    """Concrete D4 READ-only GitHub API transport.

    The bearer token is retained only in this private transport instance and is never
    copied into V-One evidence objects. The interface exposes one GET-shaped operation
    and no mutation method.
    """

    source_identity = GITHUB_API_SOURCE_IDENTITY

    def __init__(self, *, token: str, api_base_url: str = "https://api.github.com") -> None:
        self._token = _require_text(token, field="token")
        base = _require_text(api_base_url, field="api_base_url").rstrip("/")
        if base != "https://api.github.com":
            raise ValueError("D4b GitHub API base URL must be https://api.github.com")

    def read_ref(self, *, repository: str, ref: str) -> str:
        repository = _require_text(repository, field="repository")
        ref = _require_text(ref, field="ref")
        if not ref.startswith("refs/"):
            raise ValueError("ref must be fully qualified")
        ref_path = urllib.parse.quote(ref.removeprefix("refs/"), safe="/")
        repository_path = urllib.parse.quote(repository, safe="/")
        path = f"/repos/{repository_path}/git/ref/{ref_path}"
        connection = http.client.HTTPSConnection("api.github.com", 443, timeout=15)
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self._token}",
                    "User-Agent": "v-one-d4b-live-read-pilot",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError(f"GitHub READ failed with HTTP {response.status}")
            raw = json.loads(response.read().decode("utf-8"))
        except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
            raise RuntimeError("GitHub READ transport failed") from exc
        finally:
            connection.close()
        if not isinstance(raw, dict):
            raise RuntimeError("GitHub READ response is invalid")
        obj = raw.get("object")
        if not isinstance(obj, dict):
            raise RuntimeError("GitHub READ response object is invalid")
        sha = obj.get("sha")
        if not isinstance(sha, str):
            raise RuntimeError("GitHub READ response is missing object sha")
        return sha
