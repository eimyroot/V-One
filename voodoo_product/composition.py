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
from .config import ProductConfig
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
from .receipt import ReceiptLedger
from .service import ProductService


@dataclass(frozen=True, slots=True)
class ProductComposition:
    service: ProductService
    audit_ledger: AuditLedger
    receipt_ledger: ReceiptLedger
    operational_safety_service: OperationalSafetyService
    execution_service: ExecutionService
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
    audit_ledger = service.audit_ledger
    receipt_ledger = service.receipt_ledger
    operational_safety_service = service.operational_safety_service
    execution_service = service.execution_service
    resolved_identity_provider = identity_provider or create_identity_provider(
        config=resolved_config,
        service=service,
    )
    external_identity_service = GovernedExternalIdentityService(
        database=service.db,
        audit_ledger=audit_ledger,
    )
    composition = ProductComposition(
        service=service,
        audit_ledger=audit_ledger,
        receipt_ledger=receipt_ledger,
        operational_safety_service=operational_safety_service,
        execution_service=execution_service,
        external_identity_service=external_identity_service,
    )

    app.state.voodoo_product_service = service
    app.state.voodoo_identity_provider = resolved_identity_provider
    app.state.voodoo_audit_ledger = audit_ledger
    app.state.voodoo_receipt_ledger = receipt_ledger
    app.state.voodoo_operational_safety_service = operational_safety_service
    app.state.voodoo_execution_service = execution_service
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
