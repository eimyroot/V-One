from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Protocol, Self, runtime_checkable

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json
from .security import Principal

PERMISSION_DECISION_TYPE: Final = "permission-decision/v1"
CURRENT_PERMISSION_SCOPE_MODEL: Final = "current-global-role/v1"


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_text(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{field} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class PermissionQuery:
    actor_id: str
    workspace_id: str
    environment: str
    permission: str

    def __post_init__(self) -> None:
        _require_text(self.actor_id, field="actor_id")
        _require_text(self.workspace_id, field="workspace_id")
        _require_text(self.permission, field="permission")
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    actor_id: str
    workspace_id: str
    environment: str
    permission: str
    granted: bool
    reason: str
    authority_revision: str
    scope_model: str
    decision_digest: str

    def __post_init__(self) -> None:
        for field in (
            "actor_id",
            "workspace_id",
            "permission",
            "reason",
            "authority_revision",
            "scope_model",
        ):
            _require_text(getattr(self, field), field=field)
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("environment is invalid")
        if type(self.granted) is not bool:
            raise ValueError("granted must be boolean")
        _require_digest(self.decision_digest, field="decision_digest")
        if self.decision_digest != _digest(self._claims_without_digest()):
            raise ValueError("decision_digest does not match permission decision")

    @classmethod
    def create(
        cls,
        *,
        query: PermissionQuery,
        granted: bool,
        reason: str,
        authority_revision: str,
        scope_model: str,
    ) -> Self:
        if not isinstance(query, PermissionQuery):
            raise ValueError("query must be PermissionQuery")
        claims = {
            "decision_type": PERMISSION_DECISION_TYPE,
            "actor_id": query.actor_id,
            "workspace_id": query.workspace_id,
            "environment": query.environment,
            "permission": query.permission,
            "granted": granted,
            "reason": reason,
            "authority_revision": authority_revision,
            "scope_model": scope_model,
        }
        return cls(
            actor_id=query.actor_id,
            workspace_id=query.workspace_id,
            environment=query.environment,
            permission=query.permission,
            granted=granted,
            reason=reason,
            authority_revision=authority_revision,
            scope_model=scope_model,
            decision_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "decision_type": PERMISSION_DECISION_TYPE,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "permission": self.permission,
            "granted": self.granted,
            "reason": self.reason,
            "authority_revision": self.authority_revision,
            "scope_model": self.scope_model,
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["decision_digest"] = self.decision_digest
        return value


@runtime_checkable
class PermissionAuthority(Protocol):
    def decide(self, query: PermissionQuery) -> PermissionDecision: ...


class CurrentPrincipalPermissionAuthority:
    """Adapter over the current authenticated Principal role model.

    This is server-side current-behavior authority only. It deliberately records the
    current global-role scope model so future workspace-scoped authorization cannot be
    inferred from this decision.
    """

    def __init__(self, *, principal: Principal, authority_revision: str) -> None:
        if not isinstance(principal, Principal):
            raise ValueError("principal is invalid")
        _require_text(authority_revision, field="authority_revision")
        self._principal = principal
        self._authority_revision = authority_revision

    def decide(self, query: PermissionQuery) -> PermissionDecision:
        if not isinstance(query, PermissionQuery):
            raise ValueError("query must be PermissionQuery")
        if query.actor_id != self._principal.user_id:
            return PermissionDecision.create(
                query=query,
                granted=False,
                reason="ACTOR_MISMATCH",
                authority_revision=self._authority_revision,
                scope_model=CURRENT_PERMISSION_SCOPE_MODEL,
            )
        granted = self._principal.can(query.permission)
        return PermissionDecision.create(
            query=query,
            granted=granted,
            reason="CURRENT_ROLE_PERMISSION_GRANTED" if granted else "CURRENT_ROLE_PERMISSION_DENIED",
            authority_revision=self._authority_revision,
            scope_model=CURRENT_PERMISSION_SCOPE_MODEL,
        )
