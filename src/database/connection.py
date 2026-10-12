"""
MongoDB connection + Beanie initialization.

Beanie 2.x uses PyMongo's native async client (AsyncMongoClient) rather than
Motor.
"""

from pymongo import AsyncMongoClient

from beanie import init_beanie

from core.config import config

from .models import UserStreak

_client: AsyncMongoClient | None = None


async def init_db() -> AsyncMongoClient:
    """Create the async Mongo client and register Beanie document models."""
    global _client
    _client = AsyncMongoClient(config.MONGO_URI)
    await init_beanie(
        database=_client[config.MONGO_DB],
        document_models=[UserStreak],
    )
    return _client


def get_client() -> AsyncMongoClient | None:
    return _client
