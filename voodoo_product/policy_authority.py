from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Self

from .approval_policy import VALID_ENVIRONMENTS
from .evidence_primitives import canonical_json

POLICY_REVISION_TYPE: Final = "policy-revision/v1"


def _digest(value: Mapping[str, object]) -> str:
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
class PolicyRevision:
    """Immutable, content-addressed approval-policy revision."""

    policy_version: str
    policy_package: str
    approval_validity_seconds: int
    required_approvals: tuple[tuple[str, int], ...]
    policy_identity: str

    def __post_init__(self) -> None:
        _require_text(self.policy_version, field="policy_version")
        _require_text(self.policy_package, field="policy_package")
        if type(self.approval_validity_seconds) is not int or self.approval_validity_seconds <= 0:
            raise ValueError("approval_validity_seconds must be positive")
        environments = tuple(environment for environment, _ in self.required_approvals)
        if set(environments) != set(VALID_ENVIRONMENTS):
            raise ValueError("policy revision must define every supported environment")
        if environments != tuple(sorted(environments)):
            raise ValueError("required_approvals must be canonically ordered")
        for environment, count in self.required_approvals:
            if environment not in VALID_ENVIRONMENTS:
                raise ValueError("policy environment is invalid")
            if type(count) is not int or count < 1:
                raise ValueError("required approval count must be positive")
        _require_digest(self.policy_identity, field="policy_identity")
        if self.policy_identity != _digest(self._claims_without_identity()):
            raise ValueError("policy_identity does not match policy revision")

    @classmethod
    def create(
        cls,
        *,
        policy_version: str,
        policy_package: str,
        approval_validity_seconds: int,
        required_approvals_by_environment: Mapping[str, int],
    ) -> Self:
        _require_text(policy_version, field="policy_version")
        _require_text(policy_package, field="policy_package")
        if set(required_approvals_by_environment) != set(VALID_ENVIRONMENTS):
            raise ValueError("policy revision must define every supported environment")
        ordered = tuple(sorted(required_approvals_by_environment.items()))
        claims = {
            "revision_type": POLICY_REVISION_TYPE,
            "policy_version": policy_version,
            "policy_package": policy_package,
            "approval_validity_seconds": approval_validity_seconds,
            "required_approvals": [
                {"environment": environment, "count": count}
                for environment, count in ordered
            ],
        }
        return cls(
            policy_version=policy_version,
            policy_package=policy_package,
            approval_validity_seconds=approval_validity_seconds,
            required_approvals=ordered,
            policy_identity=_digest(claims),
        )

    def required_approvals_for(self, environment: str) -> int:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError("unknown environment")
        return dict(self.required_approvals)[environment]

    def _claims_without_identity(self) -> dict[str, object]:
        return {
            "revision_type": POLICY_REVISION_TYPE,
            "policy_version": self.policy_version,
            "policy_package": self.policy_package,
            "approval_validity_seconds": self.approval_validity_seconds,
            "required_approvals": [
                {"environment": environment, "count": count}
                for environment, count in self.required_approvals
            ],
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_identity()
        value["policy_identity"] = self.policy_identity
        return value


class ImmutablePolicyAuthority:
    """Read-only registry of exact immutable policy revisions."""

    def __init__(self, revisions: Iterable[PolicyRevision]) -> None:
        by_version: dict[str, PolicyRevision] = {}
        by_identity: dict[str, PolicyRevision] = {}
        for revision in revisions:
            if not isinstance(revision, PolicyRevision):
                raise ValueError("policy authority accepts PolicyRevision values only")
            if revision.policy_version in by_version:
                raise ValueError("duplicate policy_version")
            if revision.policy_identity in by_identity:
                raise ValueError("duplicate policy_identity")
            by_version[revision.policy_version] = revision
            by_identity[revision.policy_identity] = revision
        if not by_version:
            raise ValueError("policy authority requires at least one revision")
        self._by_version = MappingProxyType(by_version)
        self._by_identity = MappingProxyType(by_identity)

    def resolve(self, policy_version: str) -> PolicyRevision:
        _require_text(policy_version, field="policy_version")
        try:
            return self._by_version[policy_version]
        except KeyError as exc:
            raise LookupError("policy revision not found") from exc

    def resolve_identity(self, policy_identity: str) -> PolicyRevision:
        _require_text(policy_identity, field="policy_identity")
        try:
            return self._by_identity[policy_identity]
        except KeyError as exc:
            raise LookupError("policy identity not found") from exc
