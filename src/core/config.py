"""
Centralized configuration loaded from environment variables (.env).
"""

import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# True when running inside the Docker image (set in the Dockerfile).
# In Docker, env vars are injected by compose, so there is no .env file to load.
# Locally we load .env; in Docker we skip it and read the real environment.
IS_DOCKER = os.getenv("IS_DOCKER") == "1"

if not IS_DOCKER:
    load_dotenv()

# In Docker, default to the "mongo" compose service host; locally use localhost.
_DEFAULT_MONGO = (
    "mongodb://mongo:27017" if IS_DOCKER else "mongodb://localhost:27017"
)


class Config:
    # --- Discord ---
    TOKEN: str = os.getenv("TOKEN", "")
    PREFIX: str = os.getenv("PREFIX", "!")

    # --- Database ---
    MONGO_URI: str = os.getenv("MONGO_URI", _DEFAULT_MONGO)
    MONGO_DB: str = os.getenv("MONGO_DB", "streakbot")

    # --- Streak logic ---
    # IANA timezone name used to decide when a "day" starts/ends.
    TIMEZONE_NAME: str = os.getenv("TIMEZONE", "Asia/Bangkok")
    TIMEZONE = ZoneInfo(TIMEZONE_NAME)

    # A streak must be strictly greater than this to count as a real streak
    # (shown on the card/leaderboard, reacted to, and eligible for reminders).
    STREAK_THRESHOLD: int = int(os.getenv("STREAK_THRESHOLD", "3"))

    # Maximum number of revives (streak freezes) each user may use. The per-user
    # counters count *up* from 0 to this limit; once the limit is reached and a
    # day is missed, the streak resets to 0.
    REVIVE_MAX: int = int(os.getenv("REVIVE_MAX", "3"))

    # Fixed grace window (in days) to use a revive after missing a day on a real
    # streak. While a revive is pending, each day sends a reminder showing how
    # many days are left. When the window closes with no revive used (or no
    # revives left), the streak resets to 0.
    REVIVE_GRACE_DAYS: int = int(os.getenv("REVIVE_GRACE_DAYS", "2"))

    # How often (minutes) buffered counters are flushed to the database.
    FLUSH_INTERVAL_MINUTES: int = int(os.getenv("FLUSH_INTERVAL_MINUTES", "5"))

    # Hours before local midnight to send reminders to users at risk of losing a
    # streak. Each value is its own reminder (e.g. "2,1" => a nudge 2h and 1h
    # before midnight).
    REMINDER_HOURS_BEFORE: list[int] = sorted(
        {
            int(h.strip())
            for h in os.getenv("REMINDER_HOURS_BEFORE", "2,1").split(",")
            if h.strip()
        },
        reverse=True,
    )


config = Config()
