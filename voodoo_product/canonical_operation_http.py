from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field

from .canonical_operation_runtime import CanonicalOperationRuntime
from .canonical_read_terminal import CanonicalReadTerminalResult
from .identity import IdentityProvider
from .security import Principal

CANONICAL_OPERATION_READ_RESPONSE = "vone.canonical-operation-read/v1"
CANONICAL_OPERATION_API_STATUS = "vone.canonical-operation-api-status/v1"
SAFE_OPERATION_ID_PATTERN = r"^[A-Za-z0-9._:-]+$"


class CanonicalReadOperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(
        min_length=8,
        max_length=128,
        pattern=SAFE_OPERATION_ID_PATTERN,
    )


class CanonicalOperationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    execution_id: str
    capability: str
    environment: str
    target_digest: str
    terminal_profile: str


class CanonicalExecutionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    execution_epoch: int
    runner_observation_digest: str
    lease_digest: str
    execution_capsule_digest: str


class CanonicalVerificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str
    reason: str
    strength_class: str
    result_digest: str
    observed_post_state_digest: str
    verifier_identity_digest: str
    checked_at: str


class CanonicalReadOperationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: Literal["vone.canonical-operation-read/v1"] = Field(
        default=CANONICAL_OPERATION_READ_RESPONSE,
        alias="schema",
    )
    operation: CanonicalOperationSummary
    execution: CanonicalExecutionSummary
    verification: CanonicalVerificationSummary


class CanonicalOperationApiStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: Literal["vone.canonical-operation-api-status/v1"] = Field(
        default=CANONICAL_OPERATION_API_STATUS,
        alias="schema",
    )
    configured: bool
    read_terminal_configured: bool
    write_routes_exposed: Literal[False] = False
    provider_write_effects_exposed: Literal[False] = False


def _response_from_read_result(result: CanonicalReadTerminalResult) -> CanonicalReadOperationResponse:
    prepared = result.prepared
    verification = result.verification_result
    return CanonicalReadOperationResponse(
        operation=CanonicalOperationSummary(
            request_id=prepared.request_id,
            execution_id=prepared.execution_id,
            capability=prepared.capability,
            environment=prepared.environment,
            target_digest=prepared.target_digest,
            terminal_profile=prepared.terminal_profile,
        ),
        execution=CanonicalExecutionSummary(
            execution_epoch=prepared.execution_epoch,
            runner_observation_digest=result.runner_observation.observation_digest,
            lease_digest=prepared.lease_digest,
            execution_capsule_digest=prepared.execution_capsule_digest,
        ),
        verification=CanonicalVerificationSummary(
            verdict=verification.verdict,
            reason=verification.reason,
            strength_class=verification.verification_strength_class,
            result_digest=verification.result_digest,
            observed_post_state_digest=verification.observed_post_state_digest,
            verifier_identity_digest=verification.verifier_identity_digest,
            checked_at=verification.checked_at,
        ),
    )


def _translate_runtime_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="canonical operation denied",
        )
    if isinstance(exc, LookupError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="canonical operation resource not found",
        )
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="canonical operation rejected",
        )
    if isinstance(exc, RuntimeError):
        if str(exc) == "CANONICAL_READ_TERMINAL_NOT_CONFIGURED":
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="canonical READ runtime is not configured",
            )
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="canonical operation conflict",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="canonical operation failed",
    )


def create_canonical_operation_router(
    *,
    identity_provider: IdentityProvider,
    runtime: CanonicalOperationRuntime | None,
) -> APIRouter:
    """Expose the canonical READ operation surface without widening provider authority.

    Authentication uses the same product IdentityProvider. The HTTP permission check is only an outer
    product boundary; the canonical runtime still performs the authoritative database-backed
    permission/membership revalidation inside the trust-plane pipeline. Internal runtime/provider
    exception text is not part of the public API contract.
    """

    router = APIRouter(prefix="/api/v1/operations", tags=["VOODOO One Canonical Operations"])

    def bearer_token(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="authentication required",
            )
        if len(authorization) > 4096:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid authentication token",
            )
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid authentication token",
            )
        return token

    def current_principal(token: str = Depends(bearer_token)) -> Principal:
        try:
            return identity_provider.authenticate_bearer(token)
        except (PermissionError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid authentication token",
            ) from exc

    def require_permission(permission: str):
        def dependency(principal: Principal = Depends(current_principal)) -> Principal:
            if not principal.can(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"permission required: {permission}",
                )
            return principal

        return dependency

    @router.get("/status", response_model=CanonicalOperationApiStatus)
    def operation_status(
        _: Principal = Depends(require_permission("read")),
    ) -> CanonicalOperationApiStatus:
        return CanonicalOperationApiStatus(
            configured=runtime is not None,
            read_terminal_configured=runtime is not None and runtime.read_terminal is not None,
        )

    @router.post(
        "/{request_id}/read",
        response_model=CanonicalReadOperationResponse,
        status_code=status.HTTP_200_OK,
    )
    def run_read_operation(
        body: CanonicalReadOperationRequest,
        request_id: str = Path(
            min_length=5,
            max_length=80,
            pattern=SAFE_OPERATION_ID_PATTERN,
        ),
        principal: Principal = Depends(require_permission("execution.run")),
        idempotency_key: str = Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=SAFE_OPERATION_ID_PATTERN,
        ),
    ) -> CanonicalReadOperationResponse:
        if runtime is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="canonical operation runtime is not configured",
            )
        try:
            result = runtime.run_read_only(
                actor_id=principal.user_id,
                request_id=request_id,
                idempotency_key=idempotency_key,
                correlation_id=body.correlation_id,
            )
            return _response_from_read_result(result)
        except HTTPException:
            raise
        except Exception as exc:
            raise _translate_runtime_error(exc) from exc

    return router
