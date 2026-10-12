"""
Beanie document models.

A single collection, ``UserStreak`` - one document per (guild, user) holding
both streaks, the revive counters and the lifetime message total. There are no
per-day, per-session, or bot-state documents, so the database stays tiny.

The "which day" fields are ``datetime.date`` objects in the configured local
timezone.
"""

from datetime import date, datetime, timezone
from typing import Annotated

import pymongo
from beanie import Document
from pydantic import AfterValidator, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime) -> datetime:
    """
    MongoDB stores datetimes in UTC but returns them *naive* (no tzinfo).
    Re-attach UTC so arithmetic against ``now_utc()`` stays safe.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


UTCDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]


class UserStreak(Document):
    """Everything tracked for a single user in a single guild."""

    guild_id: int
    user_id: int

    # --- Unified streak ---
    # A single streak earned by *any* activity that day: sending a message OR
    # joining voice both advance it by +1 (once per day).
    streak: int = 0
    best: int = 0
    last_day: date | None = None  # local calendar date of last activity

    # --- Revives (streak freezes) ---
    # One shared pool. Counts the number of revives *used*, growing from 0 up to
    # REVIVE_MAX. Revives left = REVIVE_MAX - <used>.
    revives: int = 0
    revive_pending_day: date | None = None

    # --- Lifetime total (single running count) ---
    total_messages: int = 0

    updated_at: UTCDateTime = Field(default_factory=_utcnow)

    class Settings:
        name = "user_streaks"
        indexes = [
            pymongo.IndexModel(
                [("guild_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)],
                unique=True,
                name="guild_user_unique",
            ),
        ]
