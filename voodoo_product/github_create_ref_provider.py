from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol, Self, runtime_checkable

from .controlled_write import (
    CREATE_ONLY_SEMANTICS,
    CREATE_REF_OPERATION,
    GITHUB_CREATE_REF_CAPABILITY,
    GITHUB_CREATE_REF_HANDLER,
    MAX_PROVIDER_MUTATIONS_R1,
    STAGING_ENVIRONMENT,
    VONE_CANARY_REF_PREFIX,
)
from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget
from .github_read_provider import GITHUB_REF_TARGET_KIND
from .target_binding import TargetBinding
from .write_boundary import (
    GITHUB_CREATE_REF_CREDENTIAL_CLASS,
    WRITE_BOUNDED_ACCESS_MODE,
    CredentialAccessDecisionV2,
    RunnerBoundaryV2,
)

GITHUB_CREATE_REF_BINDER_ID: Final = "github-create-ref-target/v1"
GITHUB_CREATE_REF_REQUEST_TYPE: Final = "github-create-ref-request/v1"
GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE: Final = "github-create-ref-provider-response/v1"
GITHUB_CREATE_REF_SOURCE_IDENTITY: Final = "github-rest/git-create-ref/v1"

_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}")
_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "request_type",
        "repository",
        "ref",
        "sha",
        "target_digest",
        "target_binding_digest",
        "capability_definition_identity",
        "runner_boundary_digest",
        "credential_decision_digest",
        "controlled_write_requirement_digest",
        "atomic_provider_condition_contract_identity",
        "operation",
        "create_semantics",
        "max_provider_mutations",
        "request_revision",
        "request_digest",
    }
)
_RESPONSE_FIELDS = frozenset(
    {
        "schema_version",
        "response_type",
        "status_code",
        "ref",
        "object_type",
        "object_sha",
        "source_identity",
        "response_revision",
        "response_digest",
    }
)


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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


def _require_repository(value: object) -> str:
    repository = _require_text(value, field="repository")
    if _REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise ValueError("repository must use owner/name form")
    return repository


def _require_sha1(value: object, *, field: str = "sha") -> str:
    sha = _require_text(value, field=field)
    if _SHA1_PATTERN.fullmatch(sha) is None:
        raise ValueError(f"{field} must be a lowercase 40-character Git SHA-1")
    return sha


def _require_canary_ref(value: object) -> str:
    ref = _require_text(value, field="ref")
    if not ref.startswith(VONE_CANARY_REF_PREFIX):
        raise ValueError("ref must be inside the V-One canary namespace")
    suffix = ref[len(VONE_CANARY_REF_PREFIX) :]
    if (
        not suffix
        or suffix.startswith("/")
        or suffix.endswith("/")
        or "//" in suffix
        or ".." in suffix
        or "@{" in suffix
        or "\\" in suffix
        or any(character.isspace() or ord(character) < 32 for character in suffix)
        or any(character in "~^:?*[" for character in suffix)
    ):
        raise ValueError("ref is invalid")
    return ref


def _require_exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], *, contract: str
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{contract} must be an object")
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{contract} fields are invalid; missing={missing}, unknown={unknown}"
        )


class GitHubCreateRefDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class GitHubCreateRefTargetBinder:
    """Deterministically binds the exact approved create-ref target.

    The binder performs no provider lookup. Existence of the ref is intentionally resolved only by
    the provider's create-only operation; a pre-read cannot manufacture overwrite authority.
    """

    binder_id: Final = GITHUB_CREATE_REF_BINDER_ID
    target_kind: Final = GITHUB_REF_TARGET_KIND

    def bind(self, *, approved_payload: Mapping[str, Any]) -> ExecutionTarget:
        if not isinstance(approved_payload, Mapping):
            raise ValueError("approved_payload must be a mapping")
        if frozenset(approved_payload) != {"repository", "ref", "commit_sha"}:
            raise GitHubCreateRefDenied("F3_CREATE_REF_TARGET_FIELDS_INVALID")
        try:
            repository = _require_repository(approved_payload["repository"])
            ref = _require_canary_ref(approved_payload["ref"])
            commit_sha = _require_sha1(approved_payload["commit_sha"], field="commit_sha")
        except ValueError as exc:
            raise GitHubCreateRefDenied("F3_CREATE_REF_TARGET_INVALID") from exc
        return ExecutionTarget.create(
            target_kind=self.target_kind,
            target_claims={
                "repository": repository,
                "ref": ref,
                "commit_sha": commit_sha,
            },
        )


@dataclass(frozen=True, slots=True)
class GitHubCreateRefRequest:
    """Content-addressed provider request contract; not a credential or execution receipt."""

    repository: str
    ref: str
    sha: str
    target_digest: str
    target_binding_digest: str
    capability_definition_identity: str
    runner_boundary_digest: str
    credential_decision_digest: str
    controlled_write_requirement_digest: str
    atomic_provider_condition_contract_identity: str
    operation: str
    create_semantics: str
    max_provider_mutations: int
    request_revision: str
    request_digest: str

    def __post_init__(self) -> None:
        _require_repository(self.repository)
        _require_canary_ref(self.ref)
        _require_sha1(self.sha)
        for field in (
            "target_digest",
            "target_binding_digest",
            "capability_definition_identity",
            "runner_boundary_digest",
            "credential_decision_digest",
            "controlled_write_requirement_digest",
            "atomic_provider_condition_contract_identity",
            "request_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        _require_text(self.request_revision, field="request_revision")
        if self.operation != CREATE_REF_OPERATION:
            raise ValueError("F3 request operation must be CREATE_REF")
        if self.create_semantics != CREATE_ONLY_SEMANTICS:
            raise ValueError("F3 request semantics must be CREATE_ONLY")
        if self.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise ValueError("F3 request allows exactly one provider mutation")
        if self.request_digest != _digest(self._claims_without_digest()):
            raise ValueError("request_digest does not match github-create-ref-request/v1")

    @classmethod
    def create(
        cls,
        *,
        target_binding: TargetBinding,
        boundary: RunnerBoundaryV2,
        decision: CredentialAccessDecisionV2,
        request_revision: str,
    ) -> Self:
        if not isinstance(target_binding, TargetBinding):
            raise ValueError("target_binding must be TargetBinding")
        if not isinstance(boundary, RunnerBoundaryV2):
            raise ValueError("boundary must be RunnerBoundaryV2")
        if not isinstance(decision, CredentialAccessDecisionV2):
            raise ValueError("decision must be CredentialAccessDecisionV2")
        _require_text(request_revision, field="request_revision")

        if target_binding.binder_id != GITHUB_CREATE_REF_BINDER_ID:
            raise GitHubCreateRefDenied("F3_TARGET_BINDER_MISMATCH")
        if target_binding.target.target_kind != GITHUB_REF_TARGET_KIND:
            raise GitHubCreateRefDenied("F3_TARGET_KIND_MISMATCH")
        if target_binding.capability_definition_identity != boundary.capability_definition_identity:
            raise GitHubCreateRefDenied("F3_TARGET_CAPABILITY_BINDING_MISMATCH")
        if decision.runner_boundary_digest != boundary.boundary_digest:
            raise GitHubCreateRefDenied("F3_CREDENTIAL_BOUNDARY_MISMATCH")
        if decision.capability_definition_identity != boundary.capability_definition_identity:
            raise GitHubCreateRefDenied("F3_CREDENTIAL_CAPABILITY_MISMATCH")
        if (
            decision.controlled_write_requirement_digest
            != boundary.controlled_write_requirement_digest
        ):
            raise GitHubCreateRefDenied("F3_CONTROLLED_WRITE_REQUIREMENT_MISMATCH")
        if (
            decision.atomic_provider_condition_contract_identity
            != boundary.atomic_provider_condition_contract_identity
        ):
            raise GitHubCreateRefDenied("F3_PROVIDER_CONDITION_MISMATCH")
        if decision.credential_class != GITHUB_CREATE_REF_CREDENTIAL_CLASS:
            raise GitHubCreateRefDenied("F3_CREDENTIAL_CLASS_MISMATCH")
        if decision.environment != STAGING_ENVIRONMENT:
            raise GitHubCreateRefDenied("F3_ENVIRONMENT_NOT_STAGING")
        if decision.access_mode != WRITE_BOUNDED_ACCESS_MODE:
            raise GitHubCreateRefDenied("F3_ACCESS_MODE_NOT_WRITE_BOUNDED")
        if decision.provider_operation != CREATE_REF_OPERATION:
            raise GitHubCreateRefDenied("F3_PROVIDER_OPERATION_MISMATCH")
        if decision.provider_mutation_allowed is not True:
            raise GitHubCreateRefDenied("F3_PROVIDER_MUTATION_NOT_ALLOWED")
        if decision.max_provider_mutations != MAX_PROVIDER_MUTATIONS_R1:
            raise GitHubCreateRefDenied("F3_PROVIDER_MUTATION_LIMIT_MISMATCH")

        claims = target_binding.target.target_claims
        if frozenset(claims) != {"repository", "ref", "commit_sha"}:
            raise GitHubCreateRefDenied("F3_TARGET_CLAIMS_INVALID")
        try:
            repository = _require_repository(claims["repository"])
            ref = _require_canary_ref(claims["ref"])
            sha = _require_sha1(claims["commit_sha"], field="commit_sha")
        except ValueError as exc:
            raise GitHubCreateRefDenied("F3_TARGET_CLAIMS_INVALID") from exc

        request_claims = {
            "schema_version": 1,
            "request_type": GITHUB_CREATE_REF_REQUEST_TYPE,
            "repository": repository,
            "ref": ref,
            "sha": sha,
            "target_digest": target_binding.target.target_digest,
            "target_binding_digest": target_binding.binding_digest,
            "capability_definition_identity": boundary.capability_definition_identity,
            "runner_boundary_digest": boundary.boundary_digest,
            "credential_decision_digest": decision.decision_digest,
            "controlled_write_requirement_digest": boundary.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": boundary.atomic_provider_condition_contract_identity,
            "operation": CREATE_REF_OPERATION,
            "create_semantics": CREATE_ONLY_SEMANTICS,
            "max_provider_mutations": MAX_PROVIDER_MUTATIONS_R1,
            "request_revision": request_revision,
        }
        values = {
            key: item
            for key, item in request_claims.items()
            if key not in {"schema_version", "request_type"}
        }
        return cls(**values, request_digest=_digest(request_claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(value, _REQUEST_FIELDS, contract=GITHUB_CREATE_REF_REQUEST_TYPE)
        if value["schema_version"] != 1 or value["request_type"] != GITHUB_CREATE_REF_REQUEST_TYPE:
            raise ValueError("github-create-ref-request/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _REQUEST_FIELDS
                if key not in {"schema_version", "request_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request_type": GITHUB_CREATE_REF_REQUEST_TYPE,
            "repository": self.repository,
            "ref": self.ref,
            "sha": self.sha,
            "target_digest": self.target_digest,
            "target_binding_digest": self.target_binding_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "runner_boundary_digest": self.runner_boundary_digest,
            "credential_decision_digest": self.credential_decision_digest,
            "controlled_write_requirement_digest": self.controlled_write_requirement_digest,
            "atomic_provider_condition_contract_identity": self.atomic_provider_condition_contract_identity,
            "operation": self.operation,
            "create_semantics": self.create_semantics,
            "max_provider_mutations": self.max_provider_mutations,
            "request_revision": self.request_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "request_digest": self.request_digest}


@dataclass(frozen=True, slots=True)
class GitHubCreateRefProviderResponse:
    """Narrow provider response contract. A non-201 response carries no trusted created-ref claims."""

    status_code: int
    ref: str | None
    object_type: str | None
    object_sha: str | None
    source_identity: str
    response_revision: str
    response_digest: str

    def __post_init__(self) -> None:
        if isinstance(self.status_code, bool) or not isinstance(self.status_code, int):
            raise ValueError("status_code must be an integer")
        if self.status_code < 100 or self.status_code > 599:
            raise ValueError("status_code is invalid")
        _require_text(self.source_identity, field="source_identity")
        _require_text(self.response_revision, field="response_revision")
        if self.status_code == 201:
            _require_canary_ref(self.ref)
            if self.object_type != "commit":
                raise ValueError("created Git reference must point to a commit")
            _require_sha1(self.object_sha, field="object_sha")
        elif any(item is not None for item in (self.ref, self.object_type, self.object_sha)):
            raise ValueError("rejected provider responses cannot claim a created ref")
        if self.response_digest != _digest(self._claims_without_digest()):
            raise ValueError("response_digest does not match github-create-ref-provider-response/v1")

    @classmethod
    def created(
        cls,
        *,
        ref: str,
        object_sha: str,
        source_identity: str,
        response_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "response_type": GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE,
            "status_code": 201,
            "ref": _require_canary_ref(ref),
            "object_type": "commit",
            "object_sha": _require_sha1(object_sha, field="object_sha"),
            "source_identity": _require_text(source_identity, field="source_identity"),
            "response_revision": _require_text(response_revision, field="response_revision"),
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "response_type"}
        }
        return cls(**values, response_digest=_digest(claims))

    @classmethod
    def rejected(
        cls,
        *,
        status_code: int,
        source_identity: str,
        response_revision: str,
    ) -> Self:
        if status_code == 201:
            raise ValueError("use created() for a 201 response")
        claims = {
            "schema_version": 1,
            "response_type": GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE,
            "status_code": status_code,
            "ref": None,
            "object_type": None,
            "object_sha": None,
            "source_identity": _require_text(source_identity, field="source_identity"),
            "response_revision": _require_text(response_revision, field="response_revision"),
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "response_type"}
        }
        return cls(**values, response_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _RESPONSE_FIELDS,
            contract=GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["response_type"] != GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE
        ):
            raise ValueError("github-create-ref-provider-response/v1 schema or type is unsupported")
        return cls(
            **{
                key: value[key]
                for key in _RESPONSE_FIELDS
                if key not in {"schema_version", "response_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "response_type": GITHUB_CREATE_REF_PROVIDER_RESPONSE_TYPE,
            "status_code": self.status_code,
            "ref": self.ref,
            "object_type": self.object_type,
            "object_sha": self.object_sha,
            "source_identity": self.source_identity,
            "response_revision": self.response_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "response_digest": self.response_digest}


@runtime_checkable
class GitHubCreateRefTransport(Protocol):
    """F3 provider port exposing exactly one create-only operation.

    F3 provides no concrete implementation. In particular this protocol has no update, force-update
    or delete operation and therefore cannot express overwrite fallback authority.
    """

    source_identity: str

    def create_ref(self, *, request: GitHubCreateRefRequest) -> GitHubCreateRefProviderResponse:
        ...


class GitHubCreateRefHandlerContract:
    """Pure F3 request/response contract logic; it never invokes the transport itself."""

    def __init__(self, *, request_revision: str) -> None:
        self.request_revision = _require_text(request_revision, field="request_revision")

    def prepare_request(
        self,
        *,
        target_binding: TargetBinding,
        boundary: RunnerBoundaryV2,
        decision: CredentialAccessDecisionV2,
    ) -> GitHubCreateRefRequest:
        return GitHubCreateRefRequest.create(
            target_binding=target_binding,
            boundary=boundary,
            decision=decision,
            request_revision=self.request_revision,
        )

    def interpret_response(
        self,
        *,
        request: GitHubCreateRefRequest,
        response: GitHubCreateRefProviderResponse,
    ) -> GitHubCreateRefProviderResponse:
        if not isinstance(request, GitHubCreateRefRequest):
            raise ValueError("request must be GitHubCreateRefRequest")
        if not isinstance(response, GitHubCreateRefProviderResponse):
            raise ValueError("response must be GitHubCreateRefProviderResponse")
        if response.status_code != 201:
            raise GitHubCreateRefDenied("F3_CREATE_REF_PROVIDER_REJECTED_CREATE_ONLY")
        if response.source_identity != GITHUB_CREATE_REF_SOURCE_IDENTITY:
            raise GitHubCreateRefDenied("F3_CREATE_REF_SOURCE_IDENTITY_MISMATCH")
        if response.ref != request.ref:
            raise GitHubCreateRefDenied("F3_CREATE_REF_RESPONSE_REF_MISMATCH")
        if response.object_type != "commit" or response.object_sha != request.sha:
            raise GitHubCreateRefDenied("F3_CREATE_REF_RESPONSE_OBJECT_MISMATCH")
        return response


def assert_f3_definition_identity(*, capability: str, handler_id: str) -> None:
    """Small fail-closed guard used by composition code in a later live slice."""

    if capability != GITHUB_CREATE_REF_CAPABILITY:
        raise GitHubCreateRefDenied("F3_CAPABILITY_MISMATCH")
    if handler_id != GITHUB_CREATE_REF_HANDLER:
        raise GitHubCreateRefDenied("F3_HANDLER_ID_MISMATCH")
