from __future__ import annotations

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
from .platform_status import PlatformStatusService
from .receipt import ReceiptLedger
from .service import ProductService
from .user_account import UserAccountService
from .workspace import WorkspaceService


@dataclass(frozen=True, slots=True)
class ProductComposition:
    service: ProductService
    authentication_rate_limit_service: AuthenticationRateLimitService
    credential_authentication_service: CredentialAuthenticationService
    bootstrap_service: BootstrapService
    audit_ledger: AuditLedger
    user_account_service: UserAccountService
    workspace_service: WorkspaceService
    change_request_service: ChangeRequestService
    receipt_ledger: ReceiptLedger
    operational_safety_service: OperationalSafetyService
    execution_service: ExecutionService
    platform_status_service: PlatformStatusService
    external_identity_service: GovernedExternalIdentityService


def install_composed_product_platform(
    app: FastAPI,
    *,
    config: ProductConfig | None = None,
    repository_root: Path | None = None,
    identity_provider: IdentityProvider | None = None,
) -> ProductComposition:
    """Install the production platform with shared evidence ledgers."""

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
    workspace_service = service.workspace_service
    change_request_service = service.change_request_service
    receipt_ledger = service.receipt_ledger
    operational_safety_service = service.operational_safety_service
    execution_service = service.execution_service
    platform_status_service = service.platform_status_service
    resolved_identity_provider = identity_provider or create_identity_provider(
        config=resolved_config,
        credential_authenticator=credential_authentication_service,
        active_user_lookup=user_account_service,
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
        workspace_service=workspace_service,
        change_request_service=change_request_service,
        receipt_ledger=receipt_ledger,
        operational_safety_service=operational_safety_service,
        execution_service=execution_service,
        platform_status_service=platform_status_service,
        external_identity_service=external_identity_service,
    )

    app.state.voodoo_product_service = service
    app.state.voodoo_authentication_rate_limit_service = authentication_rate_limit_service
    app.state.voodoo_credential_authentication_service = credential_authentication_service
    app.state.voodoo_bootstrap_service = bootstrap_service
    app.state.voodoo_identity_provider = resolved_identity_provider
    app.state.voodoo_audit_ledger = audit_ledger
    app.state.voodoo_user_account_service = user_account_service
    app.state.voodoo_workspace_service = workspace_service
    app.state.voodoo_change_request_service = change_request_service
    app.state.voodoo_receipt_ledger = receipt_ledger
    app.state.voodoo_operational_safety_service = operational_safety_service
    app.state.voodoo_execution_service = execution_service
    app.state.voodoo_platform_status_service = platform_status_service
    app.state.voodoo_external_identity_service = external_identity_service
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
