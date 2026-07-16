"""FastAPI backend for the World Cup Analytics web experience."""

# Bump alongside CHANGELOG.md and the matching git tag — the production container
# runs without .git mounted, so this can't be derived from git at runtime.
__version__ = "1.0.1"

from .main import app, create_app

__all__ = ["app", "create_app", "__version__"]
