from __future__ import annotations

import dataclasses

import pytest

from voodoo_product.audit import AuditLedger
from voodoo_product.capability_registry import (
    CapabilityActivation,
    CapabilityDefinition,
    ImmutableCapabilityRegistry,
)
from voodoo_product.control_plane_contracts import (
    GENESIS_STATE_HASH,
    ControlPlaneEvent,
    CorrelationContext,
    ProjectDescriptor,
    StateTransition,
)
from voodoo_product.control_plane_registry import (
    ConnectorCapabilitySnapshot,
    MCPServerDescriptor,
)
from voodoo_product.control_plane_registry_persistence import (
    CONNECTOR_KEY_PREFIX,
    DurableControlPlaneRegistry,
    RegistryConflict,
    RegistryIntegrityError,
)
from voodoo_product.db import SQLiteProductDatabase
from voodoo_product.execution_contract import REQUIRED_EXECUTION_PERMISSION


def _database(tmp_path):
    database = SQLiteProductDatabase(tmp_path / "product.sqlite3")
    database.initialize()
    return database


def _project() -> ProjectDescriptor:
    return ProjectDescriptor(
        project_id="v-one",
        canonical_repository="eimyroot/V-One",
        aliases=("voodoo-one",),
    )


def _capability_registry() -> tuple[ImmutableCapabilityRegistry, CapabilityDefinition]:
    definition = CapabilityDefinition.create(
        capability="github.ref.read/v1",
        target_kind="github_ref",
        binder_id="github-ref-binder/v1",
        handler_id="github-ref-read/v1",
        effect_class="read-only",
        verification_class="independent-readback",
        supported_environments=("local", "test"),
        required_permissions=(REQUIRED_EXECUTION_PERMISSION,),
        production_eligible=False,
    )
    activation = CapabilityActivation.create(
        capability_definition_identity=definition.definition_identity,
        activation_generation=1,
        enabled_environments=("local", "test"),
    )
    return (
        ImmutableCapabilityRegistry(
            definitions=(definition,),
            activations=(activation,),
        ),
        definition,
    )


def test_connector_and_mcp_contracts_are_content_addressed() -> None:
    snapshot = ConnectorCapabilitySnapshot.create(
        connector_id="github-primary",
        provider_id="github",
        generation=1,
        available=True,
        scopes=("repo:read",),
        verification_status="VERIFIED",
        source="connector-runtime",
    )
    with pytest.raises(ValueError, match="snapshot_digest"):
        dataclasses.replace(snapshot, provider_id="tampered")

    descriptor = MCPServerDescriptor.create(
        server_id="mcp-github-primary",
        connector_id="github-primary",
        generation=1,
        transport_kind="connector-native",
        endpoint_identity="github-connector-runtime",
        protocol_version="abstracted-by-product",
        advertised_capabilities=("repo.read",),
        available=True,
        verification_status="OBSERVED",
        source="connector-runtime",
    )
    with pytest.raises(ValueError, match="descriptor_digest"):
        dataclasses.replace(descriptor, endpoint_identity="tampered")


def test_project_registry_persists_and_rejects_identity_collisions(tmp_path) -> None:
    database = _database(tmp_path)
    store = DurableControlPlaneRegistry(database=database)
    project = store.register_project(actor_id="system", project=_project())

    reloaded = DurableControlPlaneRegistry(database=database).project_registry()
    assert reloaded.resolve("v-one") == project
    assert reloaded.resolve("voodoo-one") == project
    assert reloaded.resolve_repository("EIMYROOT/v-one") == project

    with pytest.raises(RegistryConflict, match="duplicate project identity"):
        store.register_project(
            actor_id="system",
            project=ProjectDescriptor(
                project_id="other",
                canonical_repository="eimyroot/Other",
                aliases=("voodoo-one",),
            ),
        )


def test_connector_registry_binds_known_capabilities_and_advances_exact_generation(
    tmp_path,
) -> None:
    database = _database(tmp_path)
    capability_registry, definition = _capability_registry()
    store = DurableControlPlaneRegistry(
        database=database,
        capability_registry=capability_registry,
    )

    first = ConnectorCapabilitySnapshot.create(
        connector_id="github-primary",
        provider_id="github",
        generation=1,
        available=True,
        capability_definition_identities=(definition.definition_identity,),
        scopes=("repo:read",),
        mutation_requires_approval=True,
        verification_status="VERIFIED",
        source="connector-runtime",
    )
    store.record_connector_snapshot(actor_id="system", snapshot=first)
    assert store.connector_snapshot("github-primary") == first

    skipped = ConnectorCapabilitySnapshot.create(
        connector_id="github-primary",
        provider_id="github",
        generation=3,
        available=True,
        capability_definition_identities=(definition.definition_identity,),
        scopes=("repo:read",),
        verification_status="VERIFIED",
        source="connector-runtime",
    )
    with pytest.raises(RegistryConflict, match="exactly one"):
        store.record_connector_snapshot(actor_id="system", snapshot=skipped)

    second = ConnectorCapabilitySnapshot.create(
        connector_id="github-primary",
        provider_id="github",
        generation=2,
        available=False,
        capability_definition_identities=(definition.definition_identity,),
        scopes=("repo:read",),
        verification_status="OBSERVED",
        source="connector-runtime",
    )
    store.record_connector_snapshot(actor_id="system", snapshot=second)
    assert store.connector_snapshot("github-primary") == second

    unknown = ConnectorCapabilitySnapshot.create(
        connector_id="unknown",
        provider_id="unknown",
        generation=1,
        available=True,
        capability_definition_identities=("0" * 64,),
        source="test",
    )
    with pytest.raises(RegistryIntegrityError, match="unknown capability"):
        store.record_connector_snapshot(actor_id="system", snapshot=unknown)


def test_mcp_registry_requires_registered_connector_and_is_observational(tmp_path) -> None:
    database = _database(tmp_path)
    store = DurableControlPlaneRegistry(database=database)
    descriptor = MCPServerDescriptor.create(
        server_id="mcp-github-primary",
        connector_id="github-primary",
        generation=1,
        transport_kind="connector-native",
        endpoint_identity="github-connector-runtime",
        protocol_version="abstracted-by-product",
        advertised_capabilities=("repo.read",),
        available=True,
        verification_status="OBSERVED",
        source="connector-runtime",
    )

    with pytest.raises(LookupError, match="registry entry not found"):
        store.record_mcp_server(actor_id="system", descriptor=descriptor)

    store.record_connector_snapshot(
        actor_id="system",
        snapshot=ConnectorCapabilitySnapshot.create(
            connector_id="github-primary",
            provider_id="github",
            generation=1,
            available=True,
            source="connector-runtime",
        ),
    )
    store.record_mcp_server(actor_id="system", descriptor=descriptor)
    assert store.mcp_server("mcp-github-primary") == descriptor


def test_event_and_shared_state_projection_commit_atomically(tmp_path) -> None:
    database = _database(tmp_path)
    store = DurableControlPlaneRegistry(database=database)
    project = store.register_project(actor_id="system", project=_project())
    correlation = CorrelationContext.create(
        run_id="run_registry_r3",
        correlation_id="corr_registry_r3",
    )
    transition = StateTransition.create(
        previous_state_hash=GENESIS_STATE_HASH,
        next_state={"phase": "READY", "registry_generation": 1},
    )
    event = ControlPlaneEvent.create(
        event_id="evt_registry_r3_ready",
        occurred_at="2026-08-31T20:00:00+00:00",
        event_type="control_plane.registry.ready",
        actor_id="system",
        component="control-plane-registry",
        action="reconcile",
        resource="project:v-one",
        status="VERIFIED",
        correlation=correlation,
        project=project,
        payload={"reason": "R3 foundation"},
        state_transition=transition,
    )

    pointer = store.append_and_reconcile(event=event)
    assert pointer.revision == 1
    assert pointer.state() == {"phase": "READY", "registry_generation": 1}
    assert store.shared_state("v-one") == pointer
    audit_after_success = AuditLedger(database).verify()
    assert audit_after_success["valid"] is True
    assert audit_after_success["count"] == 2

    stale = ControlPlaneEvent.create(
        event_id="evt_registry_r3_stale",
        occurred_at="2026-08-31T20:01:00+00:00",
        event_type="control_plane.registry.stale",
        actor_id="system",
        component="control-plane-registry",
        action="reconcile",
        resource="project:v-one",
        status="FAILED",
        correlation=CorrelationContext.create(
            run_id="run_registry_stale",
            correlation_id="corr_registry_stale",
        ),
        project=project,
        payload={"reason": "stale transition must fail closed"},
        state_transition=StateTransition.create(
            previous_state_hash=GENESIS_STATE_HASH,
            next_state={"phase": "BROKEN"},
        ),
    )
    with pytest.raises(RegistryConflict, match="does not extend"):
        store.append_and_reconcile(event=stale)

    assert store.shared_state("v-one") == pointer
    assert AuditLedger(database).verify()["count"] == 2


def test_tampered_materialized_connector_projection_fails_closed(tmp_path) -> None:
    database = _database(tmp_path)
    store = DurableControlPlaneRegistry(database=database)
    snapshot = ConnectorCapabilitySnapshot.create(
        connector_id="github-primary",
        provider_id="github",
        generation=1,
        available=True,
        source="connector-runtime",
    )
    store.record_connector_snapshot(actor_id="system", snapshot=snapshot)

    with database.connect() as connection:
        connection.execute(
            "UPDATE runtime_flags SET value = ? WHERE key = ?",
            ('{"tampered":true}', f"{CONNECTOR_KEY_PREFIX}github-primary"),
        )

    with pytest.raises(RegistryIntegrityError, match="stored connector snapshot"):
        store.connector_snapshot("github-primary")
