from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api import create_product_router
from .audit import AuditLedger
from .auth_rate_limit import AuthenticationRateLimitService
from .bootstrap import BootstrapService
from .canonical_operation_runtime import CanonicalOperationRuntime
from .change_request import ChangeRequestService
from .config import ProductConfig
from .credential_authentication import CredentialAuthenticationService
from .execution import ExecutionService
from .external_identity_service import GovernedExternalIdentityService
from .http_security import SecurityHeadersMiddleware
from .identity import (
    IdentityProvider,
    create_identity_provider,
    validate_identity_provider_startup,
)
from .observability import (
    StructuredRequestLoggingMiddleware,
    configure_product_logging,
)
from .operational_safety import OperationalSafetyService
from .permission_authority import DatabasePermissionAuthority
from .platform_status import PlatformStatusService
from .receipt import ReceiptLedger
from .service import ProductService
from .session_lifecycle import SessionLifecycleService
from .user_account import UserAccountService
from .workspace import WorkspaceService

CanonicalRuntimeFactory = Callable[
    [ProductService, DatabasePermissionAuthority],
    CanonicalOperationRuntime,
]


@dataclass(frozen=True, slots=True)
class ProductComposition:
    service: ProductService
    authentication_rate_limit_service: AuthenticationRateLimitService
    credential_authentication_service: CredentialAuthenticationService
    bootstrap_service: BootstrapService
    audit_ledger: AuditLedger
    user_account_service: UserAccountService
    session_lifecycle_service: SessionLifecycleService
    workspace_service: WorkspaceService
    change_request_service: ChangeRequestService
    receipt_ledger: ReceiptLedger
    operational_safety_service: OperationalSafetyService
    execution_service: ExecutionService
    platform_status_service: PlatformStatusService
    external_identity_service: GovernedExternalIdentityService
    database_permission_authority: DatabasePermissionAuthority
    canonical_operation_runtime: CanonicalOperationRuntime | None


def _validate_canonical_runtime(
    *,
    runtime: CanonicalOperationRuntime,
    service: ProductService,
    permission_authority: DatabasePermissionAuthority,
) -> None:
    if not isinstance(runtime, CanonicalOperationRuntime):
        raise ValueError("canonical runtime factory returned an invalid runtime")
    pipeline = runtime.pipeline
    snapshot_creator = pipeline.snapshot_creator
    if getattr(snapshot_creator, "db", None) is not service.db:
        raise ValueError("canonical runtime snapshot creator must use product database")
    if getattr(pipeline.grant_service, "db", None) is not service.db:
        raise ValueError("canonical runtime grant service must use product database")
    if getattr(pipeline.outbox_service, "db", None) is not service.db:
        raise ValueError("canonical runtime outbox service must use product database")
    if getattr(snapshot_creator, "permission_authority", None) is not permission_authority:
        raise ValueError(
            "canonical runtime snapshot creator must use product database permission authority"
        )


def install_composed_product_platform(
    app: FastAPI,
    *,
    config: ProductConfig | None = None,
    repository_root: Path | None = None,
    identity_provider: IdentityProvider | None = None,
    canonical_runtime_factory: CanonicalRuntimeFactory | None = None,
) -> ProductComposition:
    """Install one product composition over shared durable/evidence/authority boundaries.

    Provider-capable canonical runtime components are installed only through an explicit runtime
    factory after ProductService and its database-backed permission authority exist. No GitHub token,
    provider target or mutation-capable runtime is synthesized from default configuration.
    """

    resolved_config = config or ProductConfig.from_env()
    validate_identity_provider_startup(resolved_config)
    if identity_provider is not None and identity_provider.name != resolved_config.identity_provider:
        raise RuntimeError("injected identity provider does not match configured provider")

    root = (repository_root or Path.cwd()).resolve()
    product_logger = configure_product_logging(level=resolved_config.log_level)
    service = ProductService(resolved_config)
    authentication_rate_limit_service = service.authentication_rate_limit_service
    credential_authentication_service = service.credential_authentication_service
    bootstrap_service = service.bootstrap_service
    audit_ledger = service.audit_ledger
    user_account_service = service.user_account_service
    session_lifecycle_service = service.session_lifecycle_service
    workspace_service = service.workspace_service
    change_request_service = service.change_request_service
    receipt_ledger = service.receipt_ledger
    operational_safety_service = service.operational_safety_service
    execution_service = service.execution_service
    platform_status_service = service.platform_status_service
    database_permission_authority = DatabasePermissionAuthority(
        database=service.db,
        authority_revision="database-permission/product-composition-r1",
    )
    canonical_operation_runtime: CanonicalOperationRuntime | None = None
    if canonical_runtime_factory is not None:
        canonical_operation_runtime = canonical_runtime_factory(
            service,
            database_permission_authority,
        )
        _validate_canonical_runtime(
            runtime=canonical_operation_runtime,
            service=service,
            permission_authority=database_permission_authority,
        )

    resolved_identity_provider = identity_provider or create_identity_provider(
        config=resolved_config,
        credential_authenticator=credential_authentication_service,
        active_user_lookup=user_account_service,
        session_lifecycle=session_lifecycle_service,
    )
    external_identity_service = GovernedExternalIdentityService(
        database=service.db,
        audit_ledger=audit_ledger,
    )
    composition = ProductComposition(
        service=service,
        authentication_rate_limit_service=authentication_rate_limit_service,
        credential_authentication_service=credential_authentication_service,
        bootstrap_service=bootstrap_service,
        audit_ledger=audit_ledger,
        user_account_service=user_account_service,
        session_lifecycle_service=session_lifecycle_service,
        workspace_service=workspace_service,
        change_request_service=change_request_service,
        receipt_ledger=receipt_ledger,
        operational_safety_service=operational_safety_service,
        execution_service=execution_service,
        platform_status_service=platform_status_service,
        external_identity_service=external_identity_service,
        database_permission_authority=database_permission_authority,
        canonical_operation_runtime=canonical_operation_runtime,
    )

    app.state.voodoo_product_service = service
    app.state.voodoo_authentication_rate_limit_service = authentication_rate_limit_service
    app.state.voodoo_credential_authentication_service = credential_authentication_service
    app.state.voodoo_bootstrap_service = bootstrap_service
    app.state.voodoo_identity_provider = resolved_identity_provider
    app.state.voodoo_audit_ledger = audit_ledger
    app.state.voodoo_user_account_service = user_account_service
    app.state.voodoo_session_lifecycle_service = session_lifecycle_service
    app.state.voodoo_workspace_service = workspace_service
    app.state.voodoo_change_request_service = change_request_service
    app.state.voodoo_receipt_ledger = receipt_ledger
    app.state.voodoo_operational_safety_service = operational_safety_service
    app.state.voodoo_execution_service = execution_service
    app.state.voodoo_platform_status_service = platform_status_service
    app.state.voodoo_external_identity_service = external_identity_service
    app.state.voodoo_database_permission_authority = database_permission_authority
    app.state.voodoo_canonical_operation_runtime = canonical_operation_runtime
    app.state.voodoo_product_composition = composition
    app.include_router(
        create_product_router(
            identity_provider=resolved_identity_provider,
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
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "X-Request-ID",
            ],
            expose_headers=["X-Request-ID"],
        )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(resolved_config.trusted_hosts),
        www_redirect=False,
    )
    app.add_middleware(
        StructuredRequestLoggingMiddleware,
        logger=product_logger,
        environment=resolved_config.environment,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=resolved_config.environment == "production",
    )

    static_dir = Path(__file__).with_name("static")
    app.mount("/console/assets", StaticFiles(directory=static_dir), name="voodoo-product-assets")

    @app.get("/console", include_in_schema=False)
    def console() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/", include_in_schema=False)
    def product_root() -> RedirectResponse:
        return RedirectResponse(url="/console")

    return composition
