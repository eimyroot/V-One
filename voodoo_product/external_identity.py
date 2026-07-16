from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .service import VALID_ROLES

MAX_ISSUER_LENGTH = 2048
MAX_SUBJECT_LENGTH = 512
MAX_GROUP_LENGTH = 256
EXTERNAL_ASSIGNABLE_ROLES = frozenset(VALID_ROLES - {"administrator"})
_GROUP_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{1,256}$")


def _validate_issuer(value: str) -> str:
    issuer = value.strip()
    if not issuer or len(issuer) > MAX_ISSUER_LENGTH:
        raise ValueError("external identity issuer length is invalid")
    parsed = urlsplit(issuer)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("external identity issuer must be an absolute HTTPS URL")
    return issuer.rstrip("/")


def _validate_subject(value: str) -> str:
    subject = value.strip()
    if not subject or len(subject) > MAX_SUBJECT_LENGTH:
        raise ValueError("external identity subject length is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in subject):
        raise ValueError("external identity subject contains control characters")
    return subject


def _validate_group(value: str) -> str:
    group = value.strip()
    if not _GROUP_PATTERN.fullmatch(group):
        raise ValueError("external identity group is invalid")
    return group


@dataclass(frozen=True, slots=True)
class ExternalIdentityKey:
    provider: str
    issuer: str
    subject: str

    def __post_init__(self) -> None:
        provider = self.provider.strip().lower()
        if provider != "oidc":
            raise ValueError("only the unreleased OIDC identity provider contract is recognized")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "issuer", _validate_issuer(self.issuer))
        object.__setattr__(self, "subject", _validate_subject(self.subject))


@dataclass(frozen=True, slots=True)
class ExternalRoleMapping:
    external_group: str
    internal_role: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "external_group", _validate_group(self.external_group))
        role = self.internal_role.strip().lower()
        if role not in EXTERNAL_ASSIGNABLE_ROLES:
            raise ValueError("external identity group cannot grant this internal role")
        object.__setattr__(self, "internal_role", role)


def validate_role_mappings(
    mappings: tuple[ExternalRoleMapping, ...],
) -> tuple[ExternalRoleMapping, ...]:
    groups: set[str] = set()
    for mapping in mappings:
        if mapping.external_group in groups:
            raise ValueError("external identity group mapping is duplicated")
        groups.add(mapping.external_group)
    return mappings


def resolve_external_role(
    groups: tuple[str, ...],
    mappings: tuple[ExternalRoleMapping, ...],
) -> str:
    validated = validate_role_mappings(mappings)
    presented = {_validate_group(group) for group in groups}
    matched_roles = {
        mapping.internal_role
        for mapping in validated
        if mapping.external_group in presented
    }
    if not matched_roles:
        raise PermissionError("external identity has no allowlisted role mapping")
    if len(matched_roles) != 1:
        raise PermissionError("external identity role mapping is ambiguous")
    return next(iter(matched_roles))
