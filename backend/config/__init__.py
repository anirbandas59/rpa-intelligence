"""Configuration module for RPA Intelligence Platform.

Exports settings and logging configuration.
All imports should use: from config import get_settings
"""

from config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
