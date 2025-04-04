"""Store clustering analysis package."""

__version__ = "0.1.0"

# Basic utility functions that don't have complex dependencies
from clustering.utils import ensure_directory, get_project_root, timer

__all__ = [
    "__version__",
    "ensure_directory",
    "get_project_root",
    "timer",
]

# More complex imports are done within the modules where they're needed
