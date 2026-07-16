"""VOODOO One commercial product control plane."""

from .api import create_product_router, install_product_platform
from .config import ProductConfig

__all__ = ["ProductConfig", "create_product_router", "install_product_platform"]
