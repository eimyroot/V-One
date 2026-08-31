from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Self

from .evidence_primitives import canonical_json, utc_now

CONNECTOR_CAPABILITY_SNAPSHOT_TYPE: Final = "connector-capability-snapshot/v1"
MCP_SERVER_DESCRIPTOR_TYPE: Final = "mcp-server-descriptor/v1"

REGISTRY_VERIFICATION_STATUSES: Final = frozenset(
    {"UNVERIFIED", "OBSERVED", "VERIFIED", "REVOKED"}
)
MCP_TRANSPORT_KINDS: Final = frozenset(
    {"stdio", "http", "sse", "streamable-http", "connector-native"}
)


def _digest(value: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(dict(value)).encode("utf-8")).hexdigest()


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
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _canonical_text_tuple(values: Iterable[str], *, field: str) -> tuple[str, ...]:
    normalized = tuple(sorted(set(values)))
    for value in normalized:
        _require_text(value, field=field)
    return normalized


def _verification_status(value: object) -> str:
    status = _require_text(value, field="verification_status").upper()
    if status not in REGISTRY_VERIFICATION_STATUSES:
        raise ValueError("verification_status is invalid")
    return status


@dataclass(frozen=True, slots=True)
class ConnectorCapabilitySnapshot:
    """Observed connector capability state; never an execution authorization grant."""

    connector_id: str
    provider_id: str
    generation: int
    observed_at: str
    available: bool
    capability_definition_identities: tuple[str, ...]
    scopes: tuple[str, ...]
    mutation_requires_approval: bool
    verification_status: str
    source: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        _require_text(self.connector_id, field="connector_id")
        _require_text(self.provider_id, field="provider_id")
        _require_text(self.observed_at, field="observed_at")
        _require_text(self.source, field="source")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be positive")
        if type(self.available) is not bool:
            raise ValueError("available must be boolean")
        if type(self.mutation_requires_approval) is not bool:
            raise ValueError("mutation_requires_approval must be boolean")

        identities = _canonical_text_tuple(
            self.capability_definition_identities,
            field="capability_definition_identity",
        )
        for identity in identities:
            _require_digest(identity, field="capability_definition_identity")
        scopes = _canonical_text_tuple(self.scopes, field="scope")
        status = _verification_status(self.verification_status)
        if status == "REVOKED" and self.available:
            raise ValueError("revoked connector snapshot cannot be available")

        object.__setattr__(self, "capability_definition_identities", identities)
        object.__setattr__(self, "scopes", scopes)
        object.__setattr__(self, "verification_status", status)
        _require_digest(self.snapshot_digest, field="snapshot_digest")
        if self.snapshot_digest != _digest(self._claims_without_digest()):
            raise ValueError("snapshot_digest does not match connector snapshot")

    @classmethod
    def create(
        cls,
        *,
        connector_id: str,
        provider_id: str,
        generation: int,
        available: bool,
        capability_definition_identities: Iterable[str] = (),
        scopes: Iterable[str] = (),
        mutation_requires_approval: bool = True,
        verification_status: str = "UNVERIFIED",
        source: str,
        observed_at: str | None = None,
    ) -> Self:
        identities = _canonical_text_tuple(
            capability_definition_identities,
            field="capability_definition_identity",
        )
        normalized_scopes = _canonical_text_tuple(scopes, field="scope")
        normalized_status = _verification_status(verification_status)
        timestamp = observed_at or utc_now()
        claims: dict[str, object] = {
            "snapshot_type": CONNECTOR_CAPABILITY_SNAPSHOT_TYPE,
            "connector_id": connector_id,
            "provider_id": provider_id,
            "generation": generation,
            "observed_at": timestamp,
            "available": available,
            "capability_definition_identities": list(identities),
            "scopes": list(normalized_scopes),
            "mutation_requires_approval": mutation_requires_approval,
            "verification_status": normalized_status,
            "source": source,
        }
        return cls(
            connector_id=connector_id,
            provider_id=provider_id,
            generation=generation,
            observed_at=timestamp,
            available=available,
            capability_definition_identities=identities,
            scopes=normalized_scopes,
            mutation_requires_approval=mutation_requires_approval,
            verification_status=normalized_status,
            source=source,
            snapshot_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "snapshot_type": CONNECTOR_CAPABILITY_SNAPSHOT_TYPE,
            "connector_id": self.connector_id,
            "provider_id": self.provider_id,
            "generation": self.generation,
            "observed_at": self.observed_at,
            "available": self.available,
            "capability_definition_identities": list(
                self.capability_definition_identities
            ),
            "scopes": list(self.scopes),
            "mutation_requires_approval": self.mutation_requires_approval,
            "verification_status": self.verification_status,
            "source": self.source,
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["snapshot_digest"] = self.snapshot_digest
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Self:
        if value.get("snapshot_type") != CONNECTOR_CAPABILITY_SNAPSHOT_TYPE:
            raise ValueError("connector snapshot type is invalid")
        identities = value.get("capability_definition_identities")
        scopes = value.get("scopes")
        if not isinstance(identities, list) or not all(
            isinstance(item, str) for item in identities
        ):
            raise ValueError("capability_definition_identities are invalid")
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
            raise ValueError("scopes are invalid")
        return cls(
            connector_id=str(value.get("connector_id", "")),
            provider_id=str(value.get("provider_id", "")),
            generation=value.get("generation") if isinstance(value.get("generation"), int) else 0,
            observed_at=str(value.get("observed_at", "")),
            available=value.get("available") if type(value.get("available")) is bool else False,
            capability_definition_identities=tuple(identities),
            scopes=tuple(scopes),
            mutation_requires_approval=(
                value.get("mutation_requires_approval")
                if type(value.get("mutation_requires_approval")) is bool
                else False
            ),
            verification_status=str(value.get("verification_status", "")),
            source=str(value.get("source", "")),
            snapshot_digest=str(value.get("snapshot_digest", "")),
        )


@dataclass(frozen=True, slots=True)
class MCPServerDescriptor:
    """Observed MCP endpoint identity and advertised surface; never a credential container."""

    server_id: str
    connector_id: str
    generation: int
    transport_kind: str
    endpoint_identity: str
    protocol_version: str
    advertised_capabilities: tuple[str, ...]
    available: bool
    verification_status: str
    source: str
    observed_at: str
    descriptor_digest: str

    def __post_init__(self) -> None:
        for field in (
            "server_id",
            "connector_id",
            "endpoint_identity",
            "protocol_version",
            "source",
            "observed_at",
        ):
            _require_text(getattr(self, field), field=field)
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be positive")
        if self.transport_kind not in MCP_TRANSPORT_KINDS:
            raise ValueError("transport_kind is invalid")
        if type(self.available) is not bool:
            raise ValueError("available must be boolean")
        capabilities = _canonical_text_tuple(
            self.advertised_capabilities,
            field="advertised_capability",
        )
        status = _verification_status(self.verification_status)
        if status == "REVOKED" and self.available:
            raise ValueError("revoked MCP descriptor cannot be available")
        object.__setattr__(self, "advertised_capabilities", capabilities)
        object.__setattr__(self, "verification_status", status)
        _require_digest(self.descriptor_digest, field="descriptor_digest")
        if self.descriptor_digest != _digest(self._claims_without_digest()):
            raise ValueError("descriptor_digest does not match MCP descriptor")

    @classmethod
    def create(
        cls,
        *,
        server_id: str,
        connector_id: str,
        generation: int,
        transport_kind: str,
        endpoint_identity: str,
        protocol_version: str,
        advertised_capabilities: Iterable[str] = (),
        available: bool,
        verification_status: str = "UNVERIFIED",
        source: str,
        observed_at: str | None = None,
    ) -> Self:
        capabilities = _canonical_text_tuple(
            advertised_capabilities,
            field="advertised_capability",
        )
        normalized_status = _verification_status(verification_status)
        timestamp = observed_at or utc_now()
        claims: dict[str, object] = {
            "descriptor_type": MCP_SERVER_DESCRIPTOR_TYPE,
            "server_id": server_id,
            "connector_id": connector_id,
            "generation": generation,
            "transport_kind": transport_kind,
            "endpoint_identity": endpoint_identity,
            "protocol_version": protocol_version,
            "advertised_capabilities": list(capabilities),
            "available": available,
            "verification_status": normalized_status,
            "source": source,
            "observed_at": timestamp,
        }
        return cls(
            server_id=server_id,
            connector_id=connector_id,
            generation=generation,
            transport_kind=transport_kind,
            endpoint_identity=endpoint_identity,
            protocol_version=protocol_version,
            advertised_capabilities=capabilities,
            available=available,
            verification_status=normalized_status,
            source=source,
            observed_at=timestamp,
            descriptor_digest=_digest(claims),
        )

    def _claims_without_digest(self) -> dict[str, object]:
        return {
            "descriptor_type": MCP_SERVER_DESCRIPTOR_TYPE,
            "server_id": self.server_id,
            "connector_id": self.connector_id,
            "generation": self.generation,
            "transport_kind": self.transport_kind,
            "endpoint_identity": self.endpoint_identity,
            "protocol_version": self.protocol_version,
            "advertised_capabilities": list(self.advertised_capabilities),
            "available": self.available,
            "verification_status": self.verification_status,
            "source": self.source,
            "observed_at": self.observed_at,
        }

    def to_dict(self) -> dict[str, object]:
        value = self._claims_without_digest()
        value["descriptor_digest"] = self.descriptor_digest
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Self:
        if value.get("descriptor_type") != MCP_SERVER_DESCRIPTOR_TYPE:
            raise ValueError("MCP descriptor type is invalid")
        capabilities = value.get("advertised_capabilities")
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) for item in capabilities
        ):
            raise ValueError("advertised_capabilities are invalid")
        return cls(
            server_id=str(value.get("server_id", "")),
            connector_id=str(value.get("connector_id", "")),
            generation=value.get("generation") if isinstance(value.get("generation"), int) else 0,
            transport_kind=str(value.get("transport_kind", "")),
            endpoint_identity=str(value.get("endpoint_identity", "")),
            protocol_version=str(value.get("protocol_version", "")),
            advertised_capabilities=tuple(capabilities),
            available=value.get("available") if type(value.get("available")) is bool else False,
            verification_status=str(value.get("verification_status", "")),
            source=str(value.get("source", "")),
            observed_at=str(value.get("observed_at", "")),
            descriptor_digest=str(value.get("descriptor_digest", "")),
        )
