"""
Database package: Beanie (MongoDB) models and initialization.
"""

from .connection import init_db
from .models import UserStreak

__all__ = ["init_db", "UserStreak"]
