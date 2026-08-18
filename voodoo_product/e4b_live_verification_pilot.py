from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping
from typing import Any

from .evidence_primitives import canonical_json
from .github_read_provider import GitHubRefObservation
from .runner_identity import READ_ONLY_EFFECT_CLASS
from .verification_result import VERIFIED, verify_github_ref_readback
from .verifier_identity import IndependentVerificationBoundary
from .verifier_observation import VerifierGitHubRefObservation

E4B_PILOT_TYPE = "e4b-live-verification-result/v1"
E4B_OBSERVED_POST_STATE_REVISION = "observed-post-state/e4b-live-pilot-r1"
E4B_STRENGTH_REVISION = "verification-strength/e4b-live-pilot-r1"
E4B_RESULT_REVISION = "verification-result/e4b-live-pilot-r1"


def _require_mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{field} must be an object")
    return value


def _decode_base64_json(encoded: str, *, field: str) -> Mapping[str, Any]:
    try:
        raw = base64.b64decode(encoded, validate=True)
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{field} is invalid") from exc
    return _require_mapping(value, field=field)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value.strip()


def evaluate_live_evidence(
    *,
    runner_result: Mapping[str, Any],
    verifier_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate already-produced live READ evidence without another provider call."""

    if runner_result.get("pilot") != "d4b-live-governed-read/v1":
        raise RuntimeError("runner evidence is not a D4b live pilot result")
    if runner_result.get("status") != "PASS":
        raise RuntimeError("runner evidence is not successful")
    if runner_result.get("phase_d_effect_ceiling") != READ_ONLY_EFFECT_CLASS:
        raise RuntimeError("runner evidence is not READ_ONLY")
    if runner_result.get("provider_mutation_allowed") is not False:
        raise RuntimeError("runner evidence allows provider mutation")

    if verifier_result.get("pilot") != "e3-live-independent-verifier-observation/v1":
        raise RuntimeError("verifier evidence is not an E3 live verifier result")
    if verifier_result.get("status") != "PASS":
        raise RuntimeError("verifier evidence is not successful")
    if verifier_result.get("phase_e_effect_ceiling") != READ_ONLY_EFFECT_CLASS:
        raise RuntimeError("verifier evidence is not READ_ONLY")
    if verifier_result.get("provider_mutation_allowed") is not False:
        raise RuntimeError("verifier evidence allows provider mutation")

    runner_observation = GitHubRefObservation.from_dict(
        _require_mapping(runner_result.get("observation"), field="runner_observation")
    )
    boundary = IndependentVerificationBoundary.from_dict(
        _require_mapping(
            verifier_result.get("verification_boundary"),
            field="verification_boundary",
        )
    )
    verifier_observation = VerifierGitHubRefObservation.from_dict(
        _require_mapping(
            verifier_result.get("verifier_observation"),
            field="verifier_observation",
        )
    )

    if verifier_result.get("runner_observation_digest") != runner_observation.observation_digest:
        raise RuntimeError("E3 runner observation digest does not match supplied Runner evidence")

    observed_post_state, strength, result = verify_github_ref_readback(
        runner_observation=runner_observation,
        verifier_observation=verifier_observation,
        boundary=boundary,
        observed_post_state_revision=E4B_OBSERVED_POST_STATE_REVISION,
        strength_revision=E4B_STRENGTH_REVISION,
        result_revision=E4B_RESULT_REVISION,
    )

    return {
        "pilot": E4B_PILOT_TYPE,
        "phase_e_effect_ceiling": READ_ONLY_EFFECT_CLASS,
        "provider_mutation_allowed": False,
        "runner_observation": runner_observation.to_dict(),
        "verifier_observation": verifier_observation.to_dict(),
        "observed_post_state": observed_post_state.to_dict(),
        "verification_strength": strength.to_dict(),
        "verification_result": result.to_dict(),
    }


def run_live_verification_pilot() -> dict[str, Any]:
    runner_result = _decode_base64_json(
        _require_env("VONE_RUNNER_RESULT_B64"),
        field="VONE_RUNNER_RESULT_B64",
    )
    verifier_result = _decode_base64_json(
        _require_env("VONE_E3_RESULT_B64"),
        field="VONE_E3_RESULT_B64",
    )
    return evaluate_live_evidence(
        runner_result=runner_result,
        verifier_result=verifier_result,
    )


def main() -> None:
    evidence = run_live_verification_pilot()
    result = _require_mapping(evidence["verification_result"], field="verification_result")
    verdict = result.get("verdict")
    print(f"E4B_LIVE_VERIFICATION_RESULT={verdict}")
    print(canonical_json(evidence))
    if verdict != VERIFIED:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
