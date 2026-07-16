from __future__ import annotations

from fastapi import FastAPI

from .api import install_product_platform

app = FastAPI(
    title="VOODOO One",
    version="0.9.0-rc2-dev",
    description="Governed AI operations control plane",
)
install_product_platform(app)
