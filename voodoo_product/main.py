from __future__ import annotations

from fastapi import FastAPI

from .api import install_product_platform
from .version import __version__

app = FastAPI(
    title="VOODOO One",
    version=__version__,
    description="Governed AI operations control plane",
)
install_product_platform(app)
