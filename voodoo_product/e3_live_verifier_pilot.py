from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from .credential_broker import CredentialAccessDecision
from .evidence_primitives import canonical_json
from .execution_contract import ExecutionTarget
from .execution_lease import ExecutionLease
from .github_actions_runtime import GitHubApiRefReadTransport
from .github_read_provider import GitHubRefObservation
from .isolated_runner import IsolatedRuntimeBootstrap, ReadOnlyRuntimeActivation
from .runner_identity import (
    DENY_ALL_NETWORK_DEFAULT,
    READ_ONLY_EFFECT_CLASS,
    RUNNER_BOUNDARY_TYPE,
    RunnerBoundary,
    RunnerIdentity,
)
from .trusted_clock import TrustedClockAuthority
from .verifier_credential import VerifierCredentialDecision, VerifierCredentialPolicy
from .verifier_identity import IndependentVerificationBoundary, VerifierIdentity
from .verifier_observation import VerifierGitHubRefReadHandler

ENVIRONMENT = "staging"
VERIFIER_CLASS = "github-actions.docker-isolated-verifier/v1"
VERIFIER_CREDENTIAL_CLASS = "github.actions-token.verifier-read/v1"
RUNNER_IDENTITY_REVISION = "runner-identity/d4b-live-pilot-r1"
RUNNER_BOUNDARY_REVISION = "runner-boundary/d4b-live-pilot-r1"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value.strip()


def _require_digest(value: str, *, field: str) -> str:
    if (
        len(value) != 64
        or value.casefold() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{field} must be an object")
    return value


def _decode_runner_result(encoded: str) -> Mapping[str, Any]:
    try:
        raw = base64.b64decode(encoded, validate=True)
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("VONE_RUNNER_RESULT_B64 is invalid") from exc
    result = _require_mapping(value, field="runner_result")
    if result.get("pilot") != "d4b-live-governed-read/v1" or result.get("status") != "PASS":
        raise RuntimeError("runner result is not a successful D4b pilot result")
    if result.get("phase_d_effect_ceiling") != READ_ONLY_EFFECT_CLASS:
        raise RuntimeError("runner result is not READ_ONLY")
    if result.get("provider_mutation_allowed") is not False:
        raise RuntimeError("runner result allows provider mutation")
    return result


def _rehydrate_runner_evidence(
    result: Mapping[str, Any],
) -> tuple[ExecutionTarget, RunnerIdentity, RunnerBoundary, GitHubRefObservation]:
    target = ExecutionTarget.from_dict(_require_mapping(result.get("target"), field="target"))
    lease = ExecutionLease.from_dict(_require_mapping(result.get("lease"), field="lease"))
    bootstrap = IsolatedRuntimeBootstrap.from_dict(
        _require_mapping(result.get("runtime_bootstrap"), field="runtime_bootstrap")
    )
    activation = ReadOnlyRuntimeActivation.from_dict(
        _require_mapping(result.get("runtime_activation"), field="runtime_activation")
    )
    runner_decision = CredentialAccessDecision.from_dict(
        _require_mapping(result.get("credential_decision"), field="credential_decision")
    )
    observation = GitHubRefObservation.from_dict(
        _require_mapping(result.get("observation"), field="observation")
    )

    runner = RunnerIdentity.create(
        runner_class=bootstrap.runner_class,
        provider=bootstrap.provider,
        provider_instance_id=bootstrap.provider_instance_id,
        environment=bootstrap.environment,
        rootfs_digest=bootstrap.rootfs_digest,
        resource_limit_profile_digest=bootstrap.resource_limit_profile_digest,
        network_policy_digest=bootstrap.network_policy_digest,
        identity_revision=RUNNER_IDENTITY_REVISION,
    )
    if runner.runner_id != activation.runner_id:
        raise RuntimeError("rehydrated RunnerIdentity does not match runtime activation")
    if runner.identity_digest != activation.runner_identity_digest:
        raise RuntimeError("rehydrated RunnerIdentity digest does not match runtime activation")

    boundary_payload: dict[str, Any] = {
        "schema_version": 1,
        "boundary_type": RUNNER_BOUNDARY_TYPE,
        "runner_id": runner.runner_id,
        "runner_identity_digest": runner.identity_digest,
        "lease_id": lease.lease_id,
        "lease_digest": lease.lease_digest,
        "admission_id": lease.admission_id,
        "execution_id": lease.execution_id,
        "execution_epoch": lease.execution_epoch,
        "execution_capsule_digest": activation.execution_capsule_digest,
        "capability_definition_identity": activation.capability_definition_identity,
        "environment": lease.environment,
        "runner_class": lease.runner_class,
        "credential_class": runner_decision.credential_class,
        "effect_ceiling": READ_ONLY_EFFECT_CLASS,
        "network_egress_default": DENY_ALL_NETWORK_DEFAULT,
        "provider_mutation_allowed": False,
        "boundary_revision": RUNNER_BOUNDARY_REVISION,
        "boundary_digest": activation.runner_boundary_digest,
    }
    runner_boundary = RunnerBoundary.from_dict(boundary_payload)

    if runner_decision.runner_boundary_digest != runner_boundary.boundary_digest:
        raise RuntimeError("runner credential decision does not match RunnerBoundary")
    if observation.runner_id != runner.runner_id:
        raise RuntimeError("runner observation does not match RunnerIdentity")
    if observation.runner_boundary_digest != runner_boundary.boundary_digest:
        raise RuntimeError("runner observation does not match RunnerBoundary")
    if observation.target_digest != target.target_digest:
        raise RuntimeError("runner observation does not match target")
    if observation.execution_id != runner_boundary.execution_id:
        raise RuntimeError("runner observation execution does not match RunnerBoundary")
    if observation.execution_epoch != runner_boundary.execution_epoch:
        raise RuntimeError("runner observation epoch does not match RunnerBoundary")

    return target, runner, runner_boundary, observation


def _canonical_after(value: str, *, seconds: int) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("trusted clock witness is not timezone-aware")
    return (parsed.astimezone(UTC) + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def run_live_verifier_pilot() -> dict[str, Any]:
    token = _require_env("GITHUB_TOKEN")
    verifier_provider_instance_id = _require_env("VONE_VERIFIER_PROVIDER_INSTANCE_ID")
    rootfs_digest = _require_digest(
        _require_env("VONE_VERIFIER_ROOTFS_DIGEST"),
        field="VONE_VERIFIER_ROOTFS_DIGEST",
    )
    resource_digest = _require_digest(
        _require_env("VONE_VERIFIER_RESOURCE_LIMIT_PROFILE_DIGEST"),
        field="VONE_VERIFIER_RESOURCE_LIMIT_PROFILE_DIGEST",
    )
    network_digest = _require_digest(
        _require_env("VONE_VERIFIER_NETWORK_POLICY_DIGEST"),
        field="VONE_VERIFIER_NETWORK_POLICY_DIGEST",
    )
    runner_result = _decode_runner_result(_require_env("VONE_RUNNER_RESULT_B64"))
    target, runner_identity, runner_boundary, runner_observation = _rehydrate_runner_evidence(
        runner_result
    )

    trusted_clock = TrustedClockAuthority(
        source_identity="github-actions-system-utc/e3-r1",
        authority_revision="trusted-clock/e3-live-verifier-r1",
        allowed_environments=frozenset({ENVIRONMENT}),
    )
    issuance_clock = trusted_clock.witness(environment=ENVIRONMENT)

    verifier = VerifierIdentity.create(
        verifier_class=VERIFIER_CLASS,
        provider="github-actions",
        provider_instance_id=verifier_provider_instance_id,
        environment=ENVIRONMENT,
        credential_class=VERIFIER_CREDENTIAL_CLASS,
        rootfs_digest=rootfs_digest,
        resource_limit_profile_digest=resource_digest,
        network_policy_digest=network_digest,
        identity_revision="verifier-identity/e3-live-pilot-r1",
    )
    boundary = IndependentVerificationBoundary.create(
        verifier=verifier,
        runner_identity=runner_identity,
        runner_boundary=runner_boundary,
        runner_observation=runner_observation,
        boundary_revision="independent-verification-boundary/e3-live-pilot-r1",
    )
    policy = VerifierCredentialPolicy.create(
        credential_class=VERIFIER_CREDENTIAL_CLASS,
        provider="github-actions",
        audience="api.github.com",
        enabled_environments=(ENVIRONMENT,),
        max_ttl_seconds=300,
        policy_revision="verifier-credential-policy/e3-live-pilot-r1",
    )
    decision = VerifierCredentialDecision.create(
        verifier=verifier,
        boundary=boundary,
        policy=policy,
        valid_from=issuance_clock.observed_at,
        expires_at=_canonical_after(issuance_clock.observed_at, seconds=300),
        decision_revision="verifier-credential-decision/e3-live-pilot-r1",
    )

    transport = GitHubApiRefReadTransport(token=token)
    handler = VerifierGitHubRefReadHandler(
        transport=transport,
        trusted_clock=trusted_clock,
        observation_revision="verifier-github-ref-observation/e3-live-pilot-r1",
    )
    observation = handler.observe_ref(
        verifier=verifier,
        boundary=boundary,
        decision=decision,
        target=target,
    )

    return {
        "pilot": "e3-live-independent-verifier-observation/v1",
        "status": "PASS",
        "phase_e_effect_ceiling": READ_ONLY_EFFECT_CLASS,
        "provider_mutation_allowed": False,
        "runner_observation_digest": runner_observation.observation_digest,
        "target": target.to_dict(),
        "verifier_identity": verifier.to_dict(),
        "verification_boundary": boundary.to_dict(),
        "verifier_credential_decision": decision.to_dict(),
        "verifier_observation": observation.to_dict(),
    }


def main() -> None:
    result = run_live_verifier_pilot()
    print("E3_LIVE_INDEPENDENT_VERIFIER_OBSERVATION=PASS")
    print(canonical_json(result))


if __name__ == "__main__":
    main()
