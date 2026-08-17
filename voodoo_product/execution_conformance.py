from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Self

from .authoritative_grant import ExecutionGrantV2
from .evidence_primitives import canonical_json
from .execution_capsule import ExecutionCapsule, ImmutableExecutionCapsuleRegistry
from .precondition_witness import ATOMIC_PROVIDER_CONDITION, READ_THEN_COMPARE

HANDLER_CONFORMANCE_EVIDENCE_TYPE: Final = "handler-conformance-evidence/v1"
EXECUTION_CONFORMANCE_WITNESS_TYPE: Final = "execution-conformance-witness/v1"

_HANDLER_EVIDENCE_FIELDS = frozenset(
    {
        "schema_version",
        "evidence_type",
        "capability_definition_identity",
        "execution_capsule_digest",
        "handler_id",
        "handler_digest",
        "runner_class",
        "credential_class",
        "precondition_enforcement_class",
        "verification_contract_identity",
        "atomic_provider_condition_contract_identity",
        "evidence_revision",
        "evidence_digest",
    }
)

_CONFORMANCE_WITNESS_FIELDS = frozenset(
    {
        "schema_version",
        "witness_type",
        "grant_digest",
        "execution_binding_digest",
        "execution_capsule_digest",
        "capability_definition_identity",
        "capability_activation_digest",
        "capsule_activation_digest",
        "handler_conformance_evidence_digest",
        "target_kind",
        "runner_class",
        "handler_id",
        "handler_digest",
        "credential_class",
        "precondition_enforcement_class",
        "verification_contract_identity",
        "atomic_provider_condition_contract_identity",
        "conformance_authority_revision",
        "witness_digest",
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


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    contract: str,
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


@dataclass(frozen=True, slots=True)
class HandlerConformanceEvidence:
    """Content-addressed evidence that one exact handler satisfies one exact capsule."""

    capability_definition_identity: str
    execution_capsule_digest: str
    handler_id: str
    handler_digest: str
    runner_class: str
    credential_class: str
    precondition_enforcement_class: str
    verification_contract_identity: str
    atomic_provider_condition_contract_identity: str | None
    evidence_revision: str
    evidence_digest: str

    def __post_init__(self) -> None:
        for field in (
            "capability_definition_identity",
            "execution_capsule_digest",
            "handler_digest",
            "verification_contract_identity",
            "evidence_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "handler_id",
            "runner_class",
            "credential_class",
            "evidence_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.precondition_enforcement_class not in {
            READ_THEN_COMPARE,
            ATOMIC_PROVIDER_CONDITION,
        }:
            raise ValueError("precondition_enforcement_class is unsupported")
        if self.precondition_enforcement_class == ATOMIC_PROVIDER_CONDITION:
            _require_digest(
                self.atomic_provider_condition_contract_identity,
                field="atomic_provider_condition_contract_identity",
            )
        elif self.atomic_provider_condition_contract_identity is not None:
            raise ValueError(
                "atomic provider condition contract is forbidden for read-then-compare"
            )
        if self.evidence_digest != _digest(self._claims_without_digest()):
            raise ValueError(
                "evidence_digest does not match handler conformance evidence"
            )

    @classmethod
    def create(
        cls,
        *,
        capability_definition_identity: str,
        execution_capsule_digest: str,
        handler_id: str,
        handler_digest: str,
        runner_class: str,
        credential_class: str,
        precondition_enforcement_class: str,
        verification_contract_identity: str,
        atomic_provider_condition_contract_identity: str | None,
        evidence_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "evidence_type": HANDLER_CONFORMANCE_EVIDENCE_TYPE,
            "capability_definition_identity": capability_definition_identity,
            "execution_capsule_digest": execution_capsule_digest,
            "handler_id": handler_id,
            "handler_digest": handler_digest,
            "runner_class": runner_class,
            "credential_class": credential_class,
            "precondition_enforcement_class": precondition_enforcement_class,
            "verification_contract_identity": verification_contract_identity,
            "atomic_provider_condition_contract_identity": (
                atomic_provider_condition_contract_identity
            ),
            "evidence_revision": evidence_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "evidence_type"}
        }
        return cls(**values, evidence_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _HANDLER_EVIDENCE_FIELDS,
            contract=HANDLER_CONFORMANCE_EVIDENCE_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["evidence_type"] != HANDLER_CONFORMANCE_EVIDENCE_TYPE
        ):
            raise ValueError(
                "handler conformance evidence schema or type is unsupported"
            )
        return cls(
            **{
                key: value[key]
                for key in _HANDLER_EVIDENCE_FIELDS
                if key not in {"schema_version", "evidence_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "evidence_type": HANDLER_CONFORMANCE_EVIDENCE_TYPE,
            "capability_definition_identity": self.capability_definition_identity,
            "execution_capsule_digest": self.execution_capsule_digest,
            "handler_id": self.handler_id,
            "handler_digest": self.handler_digest,
            "runner_class": self.runner_class,
            "credential_class": self.credential_class,
            "precondition_enforcement_class": self.precondition_enforcement_class,
            "verification_contract_identity": self.verification_contract_identity,
            "atomic_provider_condition_contract_identity": (
                self.atomic_provider_condition_contract_identity
            ),
            "evidence_revision": self.evidence_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._claims_without_digest(),
            "evidence_digest": self.evidence_digest,
        }


class ImmutableHandlerConformanceRegistry:
    """Immutable exact handler evidence keyed by execution capsule digest."""

    def __init__(
        self,
        *,
        capsule_registry: ImmutableExecutionCapsuleRegistry,
        evidence: Iterable[HandlerConformanceEvidence],
    ) -> None:
        if not isinstance(capsule_registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("capsule_registry is invalid")

        by_capsule: dict[str, HandlerConformanceEvidence] = {}
        for item in evidence:
            if not isinstance(item, HandlerConformanceEvidence):
                raise ValueError("handler conformance evidence is invalid")
            try:
                capsule = capsule_registry.capsule_for_definition(
                    item.capability_definition_identity
                )
            except LookupError as exc:
                raise ValueError(
                    "handler evidence references unknown capability definition"
                ) from exc
            self._assert_exact_capsule_binding(item=item, capsule=capsule)
            if item.execution_capsule_digest in by_capsule:
                raise ValueError("duplicate handler conformance evidence for capsule")
            by_capsule[item.execution_capsule_digest] = item

        if not by_capsule:
            raise ValueError(
                "handler conformance registry requires at least one evidence"
            )
        self.capsule_registry = capsule_registry
        self._by_capsule = MappingProxyType(by_capsule)

    @staticmethod
    def _assert_exact_capsule_binding(
        *,
        item: HandlerConformanceEvidence,
        capsule: ExecutionCapsule,
    ) -> None:
        expected = {
            "capability_definition_identity": capsule.capability_definition_identity,
            "execution_capsule_digest": capsule.capsule_digest,
            "handler_id": capsule.handler_id,
            "handler_digest": capsule.handler_digest,
            "runner_class": capsule.runner_class,
            "credential_class": capsule.credential_class,
            "precondition_enforcement_class": capsule.precondition_enforcement_class,
            "verification_contract_identity": capsule.verification_contract_identity,
        }
        actual = {
            "capability_definition_identity": item.capability_definition_identity,
            "execution_capsule_digest": item.execution_capsule_digest,
            "handler_id": item.handler_id,
            "handler_digest": item.handler_digest,
            "runner_class": item.runner_class,
            "credential_class": item.credential_class,
            "precondition_enforcement_class": item.precondition_enforcement_class,
            "verification_contract_identity": item.verification_contract_identity,
        }
        if actual != expected:
            raise ValueError("handler conformance evidence does not match capsule")
        if (
            capsule.precondition_enforcement_class == ATOMIC_PROVIDER_CONDITION
            and item.atomic_provider_condition_contract_identity is None
        ):
            raise ValueError(
                "atomic provider condition requires a content-addressed "
                "handler contract"
            )
        if (
            capsule.precondition_enforcement_class == READ_THEN_COMPARE
            and item.atomic_provider_condition_contract_identity is not None
        ):
            raise ValueError(
                "read-then-compare handler evidence cannot claim atomic enforcement"
            )

    def resolve(self, capsule_digest: str) -> HandlerConformanceEvidence:
        _require_digest(capsule_digest, field="capsule_digest")
        try:
            return self._by_capsule[capsule_digest]
        except KeyError as exc:
            raise PermissionError(
                "handler conformance evidence is not registered for capsule"
            ) from exc


@dataclass(frozen=True, slots=True)
class ExecutionConformanceWitness:
    grant_digest: str
    execution_binding_digest: str
    execution_capsule_digest: str
    capability_definition_identity: str
    capability_activation_digest: str
    capsule_activation_digest: str
    handler_conformance_evidence_digest: str
    target_kind: str
    runner_class: str
    handler_id: str
    handler_digest: str
    credential_class: str
    precondition_enforcement_class: str
    verification_contract_identity: str
    atomic_provider_condition_contract_identity: str | None
    conformance_authority_revision: str
    witness_digest: str

    def __post_init__(self) -> None:
        for field in (
            "grant_digest",
            "execution_binding_digest",
            "execution_capsule_digest",
            "capability_definition_identity",
            "capability_activation_digest",
            "capsule_activation_digest",
            "handler_conformance_evidence_digest",
            "handler_digest",
            "verification_contract_identity",
            "witness_digest",
        ):
            _require_digest(getattr(self, field), field=field)
        for field in (
            "target_kind",
            "runner_class",
            "handler_id",
            "credential_class",
            "conformance_authority_revision",
        ):
            _require_text(getattr(self, field), field=field)
        if self.precondition_enforcement_class not in {
            READ_THEN_COMPARE,
            ATOMIC_PROVIDER_CONDITION,
        }:
            raise ValueError("precondition_enforcement_class is unsupported")
        if self.precondition_enforcement_class == ATOMIC_PROVIDER_CONDITION:
            _require_digest(
                self.atomic_provider_condition_contract_identity,
                field="atomic_provider_condition_contract_identity",
            )
        elif self.atomic_provider_condition_contract_identity is not None:
            raise ValueError(
                "read-then-compare witness cannot claim atomic provider condition"
            )
        if self.witness_digest != _digest(self._claims_without_digest()):
            raise ValueError(
                "witness_digest does not match execution conformance witness"
            )

    @classmethod
    def create(
        cls,
        *,
        grant: ExecutionGrantV2,
        capability_activation_digest: str,
        capsule_activation_digest: str,
        capsule: ExecutionCapsule,
        handler_evidence: HandlerConformanceEvidence,
        conformance_authority_revision: str,
    ) -> Self:
        claims = {
            "schema_version": 1,
            "witness_type": EXECUTION_CONFORMANCE_WITNESS_TYPE,
            "grant_digest": grant.grant_digest,
            "execution_binding_digest": grant.execution_binding_digest,
            "execution_capsule_digest": capsule.capsule_digest,
            "capability_definition_identity": capsule.capability_definition_identity,
            "capability_activation_digest": capability_activation_digest,
            "capsule_activation_digest": capsule_activation_digest,
            "handler_conformance_evidence_digest": handler_evidence.evidence_digest,
            "target_kind": capsule.target_kind,
            "runner_class": capsule.runner_class,
            "handler_id": capsule.handler_id,
            "handler_digest": capsule.handler_digest,
            "credential_class": capsule.credential_class,
            "precondition_enforcement_class": (
                capsule.precondition_enforcement_class
            ),
            "verification_contract_identity": capsule.verification_contract_identity,
            "atomic_provider_condition_contract_identity": (
                handler_evidence.atomic_provider_condition_contract_identity
            ),
            "conformance_authority_revision": conformance_authority_revision,
        }
        values = {
            key: item
            for key, item in claims.items()
            if key not in {"schema_version", "witness_type"}
        }
        return cls(**values, witness_digest=_digest(claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        _require_exact_fields(
            value,
            _CONFORMANCE_WITNESS_FIELDS,
            contract=EXECUTION_CONFORMANCE_WITNESS_TYPE,
        )
        if (
            value["schema_version"] != 1
            or value["witness_type"] != EXECUTION_CONFORMANCE_WITNESS_TYPE
        ):
            raise ValueError(
                "execution conformance witness schema or type is unsupported"
            )
        return cls(
            **{
                key: value[key]
                for key in _CONFORMANCE_WITNESS_FIELDS
                if key not in {"schema_version", "witness_type"}
            }
        )

    def _claims_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "witness_type": EXECUTION_CONFORMANCE_WITNESS_TYPE,
            "grant_digest": self.grant_digest,
            "execution_binding_digest": self.execution_binding_digest,
            "execution_capsule_digest": self.execution_capsule_digest,
            "capability_definition_identity": self.capability_definition_identity,
            "capability_activation_digest": self.capability_activation_digest,
            "capsule_activation_digest": self.capsule_activation_digest,
            "handler_conformance_evidence_digest": (
                self.handler_conformance_evidence_digest
            ),
            "target_kind": self.target_kind,
            "runner_class": self.runner_class,
            "handler_id": self.handler_id,
            "handler_digest": self.handler_digest,
            "credential_class": self.credential_class,
            "precondition_enforcement_class": self.precondition_enforcement_class,
            "verification_contract_identity": self.verification_contract_identity,
            "atomic_provider_condition_contract_identity": (
                self.atomic_provider_condition_contract_identity
            ),
            "conformance_authority_revision": self.conformance_authority_revision,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._claims_without_digest(), "witness_digest": self.witness_digest}


class ExecutionConformanceDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ExecutionConformanceAuthority:
    """Fail closed unless Grant/v2 exactly conforms to active execution contracts."""

    def __init__(
        self,
        *,
        capsule_registry: ImmutableExecutionCapsuleRegistry,
        handler_registry: ImmutableHandlerConformanceRegistry,
        authority_revision: str,
    ) -> None:
        if not isinstance(capsule_registry, ImmutableExecutionCapsuleRegistry):
            raise ValueError("capsule_registry is invalid")
        if not isinstance(handler_registry, ImmutableHandlerConformanceRegistry):
            raise ValueError("handler_registry is invalid")
        if handler_registry.capsule_registry is not capsule_registry:
            raise ValueError(
                "handler registry and conformance authority must share capsule registry"
            )
        self.capsule_registry = capsule_registry
        self.handler_registry = handler_registry
        self.authority_revision = _require_text(
            authority_revision,
            field="authority_revision",
        )

    def evaluate(self, *, grant: ExecutionGrantV2) -> ExecutionConformanceWitness:
        if not isinstance(grant, ExecutionGrantV2):
            raise ValueError("grant is invalid")

        try:
            capsule, capsule_activation = self.capsule_registry.resolve_for_binding(
                capability_definition_identity=grant.capability_definition_identity,
                environment=grant.environment,
                target_kind=grant.target_kind,
            )
            capability_activation = (
                self.capsule_registry.capability_registry.activation(
                    grant.capability_definition_identity
                )
            )
        except (LookupError, PermissionError, ValueError) as exc:
            raise ExecutionConformanceDenied("CAPSULE_NOT_EXECUTION_ELIGIBLE") from exc

        expected = {
            "execution_capsule_digest": capsule.capsule_digest,
            "capability_definition_identity": capsule.capability_definition_identity,
            "target_kind": capsule.target_kind,
            "runner_class": capsule.runner_class,
            "precondition_enforcement_class": (
                capsule.precondition_enforcement_class
            ),
        }
        actual = {
            "execution_capsule_digest": grant.execution_capsule_digest,
            "capability_definition_identity": grant.capability_definition_identity,
            "target_kind": grant.target_kind,
            "runner_class": grant.runner_class,
            "precondition_enforcement_class": grant.precondition_enforcement_class,
        }
        if actual != expected:
            raise ExecutionConformanceDenied("GRANT_CAPSULE_BINDING_MISMATCH")

        try:
            handler_evidence = self.handler_registry.resolve(capsule.capsule_digest)
        except PermissionError as exc:
            raise ExecutionConformanceDenied(
                "HANDLER_CONFORMANCE_EVIDENCE_MISSING"
            ) from exc

        if (
            capsule.precondition_enforcement_class == ATOMIC_PROVIDER_CONDITION
            and handler_evidence.atomic_provider_condition_contract_identity is None
        ):
            raise ExecutionConformanceDenied(
                "ATOMIC_PROVIDER_CONDITION_CONTRACT_MISSING"
            )

        return ExecutionConformanceWitness.create(
            grant=grant,
            capability_activation_digest=capability_activation.activation_digest,
            capsule_activation_digest=capsule_activation.activation_digest,
            capsule=capsule,
            handler_evidence=handler_evidence,
            conformance_authority_revision=self.authority_revision,
        )
