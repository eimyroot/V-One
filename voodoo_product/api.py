from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ProductConfig
from .security import Principal, issue_token, verify_token
from .service import ProductService


class BootstrapRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    bootstrap_token: str = Field(min_length=24)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(min_length=3, max_length=40)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    environment: str = Field(min_length=4, max_length=20)


class ChangeRequestCreate(BaseModel):
    workspace_id: str = Field(min_length=5, max_length=80)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10_000)
    risk: str = "R1"
    environment: str = "local"
    adapter: str = "echo"
    payload: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    decision: str
    reason: str = Field(min_length=3, max_length=2000)


class EmergencyStopRequest(BaseModel):
    active: bool
    reason: str = Field(min_length=3, max_length=2000)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="internal product platform error")


def create_product_router(
    *,
    config: ProductConfig,
    service: ProductService,
    repository_root: Path,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["VOODOO One Product"])

    def current_principal(
        authorization: str | None = Header(default=None),
    ) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="authentication required")
        if len(authorization) > 4096:
            raise HTTPException(status_code=401, detail="invalid authentication token")
        try:
            token_principal = verify_token(
                secret=config.session_signing_secret,
                token=authorization.removeprefix("Bearer ").strip(),
            )
            active_user = service.get_active_user(token_principal.user_id)
            return Principal(
                user_id=active_user["id"],
                username=active_user["username"],
                role=active_user["role"],
            )
        except (PermissionError, ValueError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    def require_permission(permission: str) -> Callable[[Principal], Principal]:
        def dependency(principal: Principal = Depends(current_principal)) -> Principal:
            if not principal.can(permission):
                raise HTTPException(status_code=403, detail=f"permission required: {permission}")
            return principal

        return dependency

    @router.get("/health")
    def health() -> dict[str, Any]:
        return service.health()

    @router.get("/bootstrap/status")
    def bootstrap_status() -> dict[str, Any]:
        return {"required": not service.has_users()}

    @router.post("/auth/bootstrap", status_code=status.HTTP_201_CREATED)
    def bootstrap(body: BootstrapRequest) -> dict[str, Any]:
        try:
            result = service.bootstrap_admin(
                username=body.username,
                password=body.password,
                token=body.bootstrap_token,
            )
            token = issue_token(
                secret=config.session_signing_secret,
                user_id=result["user_id"],
                username=body.username,
                role=result["role"],
                ttl_seconds=config.token_ttl_seconds,
            )
            return {"token": token, **result}
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.post("/auth/login")
    def login(body: LoginRequest) -> dict[str, Any]:
        try:
            user = service.authenticate(username=body.username, password=body.password)
            token = issue_token(
                secret=config.session_signing_secret,
                user_id=user["id"],
                username=user["username"],
                role=user["role"],
                ttl_seconds=config.token_ttl_seconds,
            )
            return {"token": token, "user": user}
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.get("/me")
    def me(principal: Principal = Depends(current_principal)) -> dict[str, Any]:
        return {"id": principal.user_id, "username": principal.username, "role": principal.role}

    @router.post("/users", status_code=status.HTTP_201_CREATED)
    def create_user(
        body: UserCreateRequest,
        principal: Principal = Depends(require_permission("*")),
    ) -> dict[str, Any]:
        try:
            return service.create_user(
                actor_id=principal.user_id,
                username=body.username,
                password=body.password,
                role=body.role,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.get("/workspaces")
    def workspaces(
        _: Principal = Depends(require_permission("read")),
    ) -> list[dict[str, Any]]:
        return service.list_workspaces()

    @router.post("/workspaces", status_code=status.HTTP_201_CREATED)
    def create_workspace(
        body: WorkspaceCreateRequest,
        principal: Principal = Depends(require_permission("*")),
    ) -> dict[str, Any]:
        try:
            return service.create_workspace(
                actor_id=principal.user_id,
                name=body.name,
                environment=body.environment,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.get("/command-center")
    def command_center(
        _: Principal = Depends(require_permission("read")),
    ) -> dict[str, Any]:
        return service.command_center()

    @router.get("/change-requests")
    def change_requests(
        _: Principal = Depends(require_permission("read")),
    ) -> list[dict[str, Any]]:
        return service.list_change_requests()

    @router.post("/change-requests", status_code=status.HTTP_201_CREATED)
    def create_change_request(
        body: ChangeRequestCreate,
        principal: Principal = Depends(require_permission("change.write")),
    ) -> dict[str, Any]:
        try:
            return service.create_change_request(
                actor_id=principal.user_id,
                workspace_id=body.workspace_id,
                title=body.title,
                description=body.description,
                risk=body.risk,
                environment=body.environment,
                adapter=body.adapter,
                payload=body.payload,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.get("/change-requests/{request_id}")
    def change_request(
        request_id: str,
        _: Principal = Depends(require_permission("read")),
    ) -> dict[str, Any]:
        try:
            return service.get_change_request(request_id)
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.post("/change-requests/{request_id}/submit")
    def submit_change_request(
        request_id: str,
        principal: Principal = Depends(require_permission("change.write")),
    ) -> dict[str, Any]:
        try:
            return service.submit_change_request(actor_id=principal.user_id, request_id=request_id)
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.get("/approvals")
    def approvals(
        pending_only: bool = False,
        _: Principal = Depends(require_permission("approval.review")),
    ) -> list[dict[str, Any]]:
        return service.list_approvals(pending_only=pending_only)

    @router.post("/change-requests/{request_id}/decision")
    def decide_change_request(
        request_id: str,
        body: ApprovalRequest,
        principal: Principal = Depends(require_permission("approval.review")),
    ) -> dict[str, Any]:
        try:
            return service.approve_change_request(
                actor_id=principal.user_id,
                request_id=request_id,
                decision=body.decision,
                reason=body.reason,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.post("/change-requests/{request_id}/execute")
    def execute_change_request(
        request_id: str,
        principal: Principal = Depends(require_permission("execution.run")),
        idempotency_key: str | None = Header(
            default=None,
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ) -> dict[str, Any]:
        try:
            return service.execute_change_request(
                actor_id=principal.user_id,
                request_id=request_id,
                idempotency_key=idempotency_key,
                repository_root=repository_root,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.get("/executions")
    def executions(
        _: Principal = Depends(require_permission("read")),
    ) -> list[dict[str, Any]]:
        return service.list_executions()

    @router.get("/executions/{execution_id}")
    def execution(
        execution_id: str,
        _: Principal = Depends(require_permission("read")),
    ) -> dict[str, Any]:
        try:
            return service.get_execution(execution_id)
        except Exception as exc:
            raise _translate_error(exc) from exc

    @router.get("/evidence/receipts")
    def receipts(
        _: Principal = Depends(require_permission("evidence.read")),
    ) -> list[dict[str, Any]]:
        return service.list_receipts()

    @router.get("/evidence/verify")
    def verify_evidence(
        _: Principal = Depends(require_permission("evidence.read")),
    ) -> dict[str, Any]:
        return {
            "receipts": service.verify_receipt_chain(),
            "audit": service.verify_audit_chain(),
        }

    @router.get("/audit")
    def audit(
        _: Principal = Depends(require_permission("evidence.read")),
    ) -> list[dict[str, Any]]:
        return service.list_audit_events()

    @router.post("/system/emergency-stop")
    def emergency_stop(
        body: EmergencyStopRequest,
        principal: Principal = Depends(require_permission("emergency.control")),
    ) -> dict[str, Any]:
        try:
            return service.set_emergency_stop(
                actor_id=principal.user_id,
                active=body.active,
                reason=body.reason,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    return router


def install_product_platform(
    app: FastAPI,
    *,
    config: ProductConfig | None = None,
    repository_root: Path | None = None,
) -> ProductService:
    resolved_config = config or ProductConfig.from_env()
    root = (repository_root or Path.cwd()).resolve()
    service = ProductService(resolved_config)
    app.state.voodoo_product_service = service
    app.include_router(
        create_product_router(
            config=resolved_config,
            service=service,
            repository_root=root,
        )
    )

    if resolved_config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_config.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    static_dir = Path(__file__).with_name("static")
    app.mount("/console/assets", StaticFiles(directory=static_dir), name="voodoo-product-assets")

    @app.get("/console", include_in_schema=False)
    def console() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/", include_in_schema=False)
    def product_root() -> RedirectResponse:
        return RedirectResponse(url="/console")

    return service
