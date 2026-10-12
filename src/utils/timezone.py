"""
Time helpers. All streak logic uses a configurable local timezone (UTC+7 by
default) to decide when a "day" begins and ends, while timestamps are stored in
UTC internally.

The "which day" value is a ``datetime.date`` in the configured local timezone.
"""

from datetime import date, datetime, time, timedelta, timezone

from core.config import config


class Clock:
    """Timezone-aware clock and day helpers for streak boundaries."""

    def __init__(self, tz=None) -> None:
        self.tz = tz or config.TIMEZONE

    def now_utc(self) -> datetime:
        """Current time as a tz-aware UTC datetime."""
        return datetime.now(timezone.utc)

    def now_local(self) -> datetime:
        """Current time in the configured local timezone."""
        return datetime.now(self.tz)

    def to_local(self, dt: datetime) -> datetime:
        """Convert a datetime to the local timezone (assume UTC if naive)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self.tz)

    def local_day(self, dt: datetime | None = None) -> date:
        """The local calendar ``date`` for the given moment (default: now)."""
        if dt is None:
            dt = self.now_local()
        else:
            dt = self.to_local(dt)
        return dt.date()

    def previous_day(self, day: date) -> date:
        """The ``date`` before the given one."""
        return day - timedelta(days=1)

    def is_consecutive(self, previous: date | None, current: date) -> bool:
        """True if `current` is exactly the day after `previous`."""
        if previous is None:
            return False
        return (current - previous).days == 1

    def day_label(self, day: date) -> str:
        """Human-readable 'YYYY-MM-DD' label for a date (for messages/logs)."""
        return day.isoformat()

    # ------------------------------------------------- Discord timestamps --
    @staticmethod
    def discord_time(dt: datetime, style: str = "R") -> str:
        """
        Render a datetime as a Discord timestamp markdown token, which each
        client displays in the viewer's own timezone and locale.

        Format: ``<t:UNIX_SECONDS:STYLE>``. Styles:
        ``t`` short time, ``T`` medium time, ``d`` short date, ``D`` long date,
        ``f`` long date + short time, ``F`` full date + short time,
        ``R`` relative (e.g. "in 2 hours").
        """
        return f"<t:{int(dt.timestamp())}:{style}>"

    def end_of_day(self, day: date | None = None) -> datetime:
        """
        The moment the given local day ends (midnight at the start of the next
        day), as a tz-aware datetime in the local timezone.
        """
        if day is None:
            day = self.local_day()
        return datetime.combine(
            day + timedelta(days=1), time.min, tzinfo=self.tz
        )

    def deadline_after(self, day: date, days: int) -> datetime:
        """
        End of the local day that is ``days`` days after ``day``. Used for the
        revive grace-window deadline.
        """
        return self.end_of_day(day + timedelta(days=days))


# Module-level singleton used across the bot.
clock = Clock()
