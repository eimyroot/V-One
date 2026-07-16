from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from .api import install_product_platform
from .audit import AuditLedger
from .config import ProductConfig
from .external_identity_service import GovernedExternalIdentityService
from .identity import IdentityProvider
from .service import ProductService


@dataclass(frozen=True, slots=True)
class ProductComposition:
    service: ProductService
    audit_ledger: AuditLedger
    external_identity_service: GovernedExternalIdentityService


def install_composed_product_platform(
    app: FastAPI,
    *,
    config: ProductConfig | None = None,
    repository_root: Path | None = None,
    identity_provider: IdentityProvider | None = None,
) -> ProductComposition:
    """Install the product and compose internal-only bounded services."""

    service = install_product_platform(
        app,
        config=config,
        repository_root=repository_root,
        identity_provider=identity_provider,
    )
    audit_ledger = AuditLedger(service.db)
    external_identity_service = GovernedExternalIdentityService(
        database=service.db,
        audit_ledger=audit_ledger,
    )
    composition = ProductComposition(
        service=service,
        audit_ledger=audit_ledger,
        external_identity_service=external_identity_service,
    )
    app.state.voodoo_audit_ledger = audit_ledger
    app.state.voodoo_external_identity_service = external_identity_service
    app.state.voodoo_product_composition = composition
    return composition
