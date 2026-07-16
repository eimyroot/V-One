"""VOODOO One commercial product control plane."""

from .api import create_product_router, install_product_platform
from .config import ProductConfig
from .version import __version__

__all__ = ["ProductConfig", "__version__", "create_product_router", "install_product_platform"]
