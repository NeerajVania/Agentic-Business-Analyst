"""
backend/core/dependencies.py
=============================
Dependency injection helpers shared across routes.
"""

from database.session import get_db  # re-export for convenience

__all__ = ["get_db"]