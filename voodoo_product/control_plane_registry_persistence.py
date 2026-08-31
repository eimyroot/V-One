from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final

from .audit import AuditLedger, AuditLedgerWriter
from .capability_registry import ImmutableCapabilityRegistry
from .control_plane_contracts import (
    PROJECT_SCHEMA,
    SHARED_STATE_SCHEMA,
    ControlPlaneEvent,
    ImmutableProjectRegistry,
    ProjectDescriptor,
    SharedStatePointer,
)
from .control_plane_foundation import ControlPlaneEventLog, ControlPlaneReconciler
from .control_plane_registry import ConnectorCapabilitySnapshot, MCPServerDescriptor
from .evidence_primitives import canonical_json, utc_now
from .persistence import (
    DatabaseIntegrityError,
    DatabaseStatement,
    ProductDatabaseAdapter,
)

PROJECT_KEY_PREFIX: Final = "control_plane.project.v1:"
CONNECTOR_KEY_PREFIX: Final = "control_plane.connector.v1:"
MCP_KEY_PREFIX: Final = "control_plane.mcp.v1:"
SHARED_STATE_KEY_PREFIX: Final = "control_plane.shared_state.v1:"

_SELECT_KEY = DatabaseStatement(
    name="control_plane_registry.select_key",
    mode="read",
    sqlite_sql="SELECT value FROM runtime_flags WHERE key = ?",
)
_LIST_PREFIX = DatabaseStatement(
    name="control_plane_registry.list_prefix",
    mode="read",
    sqlite_sql="SELECT key, value FROM runtime_flags WHERE key LIKE ? ORDER BY key",
)
_INSERT_KEY = DatabaseStatement(
    name="control_plane_registry.insert_key",
    mode="write",
    sqlite_sql="""
        INSERT INTO runtime_flags(key, value, updated_by, updated_at)
        VALUES (?, ?, ?, ?)
    """,
)
_UPDATE_KEY_CAS = DatabaseStatement(
    name="control_plane_registry.update_key_cas",
    mode="write",
    sqlite_sql="""
        UPDATE runtime_flags
        SET value = ?, updated_by = ?, updated_at = ?
        WHERE key = ? AND value = ?
    """,
)


class ControlPlaneRegistryError(RuntimeError):
    pass


class RegistryConflict(ControlPlaneRegistryError):
    pass


class RegistryIntegrityError(ControlPlaneRegistryError):
    pass


def _record_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(dict(value)).encode("utf-8")).hexdigest()


def _decode_object(raw: str, *, field: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegistryIntegrityError(f"{field} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise RegistryIntegrityError(f"{field} must decode to an object")
    if canonical_json(value) != raw:
        raise RegistryIntegrityError(f"{field} is not canonical JSON")
    return value


def _project_from_dict(value: Mapping[str, Any]) -> ProjectDescriptor:
    if value.get("schema") != PROJECT_SCHEMA:
        raise RegistryIntegrityError("stored project schema is invalid")
    aliases = value.get("aliases")
    if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
        raise RegistryIntegrityError("stored project aliases are invalid")
    try:
        return ProjectDescriptor(
            project_id=str(value.get("project_id", "")),
            canonical_repository=str(value.get("canonical_repository", "")),
            canonical_ref=str(value.get("canonical_ref", "")),
            aliases=tuple(aliases),
        )
    except ValueError as exc:
        raise RegistryIntegrityError("stored project descriptor is invalid") from exc


def _shared_state_from_dict(value: Mapping[str, Any]) -> SharedStatePointer:
    if value.get("schema") != SHARED_STATE_SCHEMA:
        raise RegistryIntegrityError("stored shared-state schema is invalid")
    state = value.get("state")
    if not isinstance(state, dict):
        raise RegistryIntegrityError("stored shared-state value is invalid")
    try:
        return SharedStatePointer(
            project_id=str(value.get("project_id", "")),
            revision=value.get("revision") if isinstance(value.get("revision"), int) else -1,
            state_hash=str(value.get("state_hash", "")),
            state_json=canonical_json(state),
            last_event_id=(
                str(value["last_event_id"]) if value.get("last_event_id") is not None else None
            ),
            last_correlation_id=(
                str(value["last_correlation_id"])
                if value.get("last_correlation_id") is not None
                else None
            ),
            updated_at=(str(value["updated_at"]) if value.get("updated_at") is not None else None),
        )
    except ValueError as exc:
        raise RegistryIntegrityError("stored shared-state pointer is invalid") from exc


class DurableControlPlaneRegistry:
    """Durable materialized registries backed by runtime_flags plus the audit hash chain.

    The materialized values are discoverability/state projections. They do not grant execution
    permission. Executable capability resolution remains exclusively owned by
    ImmutableCapabilityRegistry and the existing authorization/grant pipeline.
    """

    def __init__(
        self,
        *,
        database: ProductDatabaseAdapter,
        capability_registry: ImmutableCapabilityRegistry | None = None,
        audit_ledger: AuditLedgerWriter | None = None,
    ) -> None:
        self.db = database
        self.capability_registry = capability_registry
        self.audit_ledger = audit_ledger or AuditLedger(database)
        self.event_log = ControlPlaneEventLog(self.audit_ledger)

    def project_registry(self) -> ImmutableProjectRegistry:
        projects: list[ProjectDescriptor] = []
        with self.db.connect() as connection:
            rows = connection.execute(_LIST_PREFIX, (f"{PROJECT_KEY_PREFIX}%",)).fetchall()
        for row in rows:
            projects.append(
                _project_from_dict(
                    _decode_object(str(row["value"]), field="project registry record")
                )
            )
        return ImmutableProjectRegistry(projects)

    def register_project(self, *, actor_id: str, project: ProjectDescriptor) -> ProjectDescriptor:
        if not isinstance(project, ProjectDescriptor):
            raise ValueError("project must be a ProjectDescriptor")
        key = f"{PROJECT_KEY_PREFIX}{project.project_id}"
        value = canonical_json(project.as_dict())
        now = utc_now()

        with self.db.transaction() as connection:
            rows = connection.execute(_LIST_PREFIX, (f"{PROJECT_KEY_PREFIX}%",)).fetchall()
            existing = [
                _project_from_dict(
                    _decode_object(str(row["value"]), field="project registry record")
                )
                for row in rows
            ]
            try:
                ImmutableProjectRegistry((*existing, project))
            except ValueError as exc:
                raise RegistryConflict(str(exc)) from exc
            try:
                connection.execute(_INSERT_KEY, (key, value, actor_id, now))
            except DatabaseIntegrityError as exc:
                raise RegistryConflict("project is already registered") from exc
            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action="control_plane.registry.project.registered",
                target_type="control_plane_project",
                target_id=project.project_id,
                payload={
                    "project": project.as_dict(),
                    "record_digest": _record_digest(project.as_dict()),
                },
            )
        return project

    def connector_snapshot(self, connector_id: str) -> ConnectorCapabilitySnapshot:
        raw = self._read_current(f"{CONNECTOR_KEY_PREFIX}{connector_id}")
        try:
            return ConnectorCapabilitySnapshot.from_dict(
                _decode_object(raw, field="connector snapshot")
            )
        except ValueError as exc:
            raise RegistryIntegrityError("stored connector snapshot is invalid") from exc

    def record_connector_snapshot(
        self,
        *,
        actor_id: str,
        snapshot: ConnectorCapabilitySnapshot,
    ) -> ConnectorCapabilitySnapshot:
        if not isinstance(snapshot, ConnectorCapabilitySnapshot):
            raise ValueError("snapshot must be a ConnectorCapabilitySnapshot")
        if snapshot.capability_definition_identities:
            if self.capability_registry is None:
                raise RegistryIntegrityError(
                    "capability registry is required for executable capability references"
                )
            for identity in snapshot.capability_definition_identities:
                try:
                    self.capability_registry.definition_by_identity(identity)
                except LookupError as exc:
                    raise RegistryIntegrityError(
                        "connector snapshot references an unknown capability definition"
                    ) from exc
        key = f"{CONNECTOR_KEY_PREFIX}{snapshot.connector_id}"
        self._record_generation(
            actor_id=actor_id,
            key=key,
            generation=snapshot.generation,
            value=snapshot.to_dict(),
            target_type="control_plane_connector",
            target_id=snapshot.connector_id,
            action="control_plane.registry.connector.observed",
            digest=snapshot.snapshot_digest,
        )
        return snapshot

    def mcp_server(self, server_id: str) -> MCPServerDescriptor:
        raw = self._read_current(f"{MCP_KEY_PREFIX}{server_id}")
        try:
            return MCPServerDescriptor.from_dict(_decode_object(raw, field="MCP descriptor"))
        except ValueError as exc:
            raise RegistryIntegrityError("stored MCP descriptor is invalid") from exc

    def record_mcp_server(
        self,
        *,
        actor_id: str,
        descriptor: MCPServerDescriptor,
    ) -> MCPServerDescriptor:
        if not isinstance(descriptor, MCPServerDescriptor):
            raise ValueError("descriptor must be an MCPServerDescriptor")
        connector = self.connector_snapshot(descriptor.connector_id)
        if connector.verification_status == "REVOKED" and descriptor.available:
            raise RegistryIntegrityError("available MCP server cannot bind to revoked connector")
        key = f"{MCP_KEY_PREFIX}{descriptor.server_id}"
        self._record_generation(
            actor_id=actor_id,
            key=key,
            generation=descriptor.generation,
            value=descriptor.to_dict(),
            target_type="control_plane_mcp_server",
            target_id=descriptor.server_id,
            action="control_plane.registry.mcp.observed",
            digest=descriptor.descriptor_digest,
        )
        return descriptor

    def shared_state(self, project_id: str) -> SharedStatePointer:
        self.project_registry().resolve(project_id)
        key = f"{SHARED_STATE_KEY_PREFIX}{project_id}"
        with self.db.connect() as connection:
            row = connection.execute(_SELECT_KEY, (key,)).fetchone()
        if row is None:
            return SharedStatePointer.genesis(project_id)
        return _shared_state_from_dict(
            _decode_object(str(row["value"]), field="shared-state pointer")
        )

    def append_and_reconcile(
        self,
        *,
        event: ControlPlaneEvent,
    ) -> SharedStatePointer:
        if not isinstance(event, ControlPlaneEvent):
            raise ValueError("event must be a ControlPlaneEvent")
        registered = self.project_registry().resolve(event.project.project_id)
        if registered.as_dict() != event.project.as_dict():
            raise RegistryIntegrityError("event project does not match registered project descriptor")

        key = f"{SHARED_STATE_KEY_PREFIX}{event.project.project_id}"
        with self.db.transaction() as connection:
            row = connection.execute(_SELECT_KEY, (key,)).fetchone()
            raw_current = str(row["value"]) if row is not None else None
            current = (
                _shared_state_from_dict(
                    _decode_object(raw_current, field="shared-state pointer")
                )
                if raw_current is not None
                else SharedStatePointer.genesis(event.project.project_id)
            )
            try:
                next_pointer = ControlPlaneReconciler.apply(current, event=event)
            except ValueError as exc:
                raise RegistryConflict(str(exc)) from exc

            self.event_log.append(connection, event=event)
            if next_pointer == current:
                return current

            next_json = canonical_json(next_pointer.as_dict())
            now = utc_now()
            if raw_current is None:
                try:
                    connection.execute(
                        _INSERT_KEY,
                        (key, next_json, event.actor_id, now),
                    )
                except DatabaseIntegrityError as exc:
                    raise RegistryConflict("shared-state genesis race detected") from exc
            else:
                cursor = connection.execute(
                    _UPDATE_KEY_CAS,
                    (next_json, event.actor_id, now, key, raw_current),
                )
                if cursor.rowcount != 1:
                    raise RegistryConflict("shared-state compare-and-swap failed")
            return next_pointer

    def _read_current(self, key: str) -> str:
        with self.db.connect() as connection:
            row = connection.execute(_SELECT_KEY, (key,)).fetchone()
        if row is None:
            raise LookupError("registry entry not found")
        return str(row["value"])

    def _record_generation(
        self,
        *,
        actor_id: str,
        key: str,
        generation: int,
        value: Mapping[str, Any],
        target_type: str,
        target_id: str,
        action: str,
        digest: str,
    ) -> None:
        next_json = canonical_json(dict(value))
        now = utc_now()
        with self.db.transaction() as connection:
            row = connection.execute(_SELECT_KEY, (key,)).fetchone()
            raw_current = str(row["value"]) if row is not None else None
            if raw_current is None:
                if generation != 1:
                    raise RegistryConflict("first registry generation must be 1")
                try:
                    connection.execute(_INSERT_KEY, (key, next_json, actor_id, now))
                except DatabaseIntegrityError as exc:
                    raise RegistryConflict("registry generation race detected") from exc
            else:
                current = _decode_object(raw_current, field="registry generation")
                current_generation = current.get("generation")
                if not isinstance(current_generation, int) or current_generation < 1:
                    raise RegistryIntegrityError("stored registry generation is invalid")
                if generation != current_generation + 1:
                    raise RegistryConflict("registry generation must advance by exactly one")
                cursor = connection.execute(
                    _UPDATE_KEY_CAS,
                    (next_json, actor_id, now, key, raw_current),
                )
                if cursor.rowcount != 1:
                    raise RegistryConflict("registry compare-and-swap failed")

            self.audit_ledger.append(
                connection,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                payload={
                    "generation": generation,
                    "record_digest": digest,
                    "record": dict(value),
                },
            )
