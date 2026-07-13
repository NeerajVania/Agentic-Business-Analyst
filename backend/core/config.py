"""
backend/core/config.py
======================
Re-exports the centralised settings from config/settings.py.
All backend services should import from here for convenience.
"""

from config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]