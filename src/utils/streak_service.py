"""
Core streak logic.

Design
------
* Tiny database: one ``UserStreak`` document per user. No per-day/per-session
  rows. ``total_messages`` is a single running counter.
* Few writes: message counts are buffered in memory and flushed in bulk; the
  first activity of a day (which advances the streak) writes immediately so the
  🔥 reaction shows the right number.
* One unified streak, "2-level": only a streak greater than ``STREAK_THRESHOLD``
  (3) is a real, displayed streak. Any activity (chat or voice) advances it.

Day values are ``datetime.date`` objects in the configured local timezone.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from pymongo import UpdateOne

from core.config import config
from database import UserStreak
from utils.timezone import clock


@dataclass(slots=True)
class BrokenStreak:
    """A streak that was missed, carried to the scheduler for a DM."""

    streak: UserStreak
    count: int
    revives_left: int
    #: Date the pending-revive window started.
    missed_day: date
    #: Whole days still left in the fixed grace window to use a revive.
    days_left: int = 0


class StreakService:
    """
    Owns all streak reads/writes. Message counts are buffered in memory and
    flushed in bulk; streak advancement writes immediately.
    """

    def __init__(self) -> None:
        # Buffered, not-yet-persisted message counts: {(guild_id, user_id): count}
        self._pending_messages: dict[tuple[int, int], int] = defaultdict(int)

    # --------------------------------------------------------------- helpers --
    @staticmethod
    def is_real_streak(streak: int) -> bool:
        """A streak only counts for display/notifications once it exceeds the threshold."""
        return streak > config.STREAK_THRESHOLD

    @staticmethod
    def revives_used(streak: UserStreak) -> int:
        """Number of revives already used (shared pool)."""
        return streak.revives

    def revives_left(self, streak: UserStreak) -> int:
        """Remaining revives: REVIVE_MAX minus the number used."""
        return max(0, config.REVIVE_MAX - self.revives_used(streak))

    @staticmethod
    def _advance(previous_day: date | None, current_day: date, current_streak: int) -> int:
        if previous_day == current_day:
            return current_streak
        if clock.is_consecutive(previous_day, current_day):
            return current_streak + 1
        return 1

    @staticmethod
    def _grace_days_left(pending_day: date, current_day: date) -> int:
        """
        How many days remain in the fixed grace window, counting from the day the
        streak was first missed. On the day it's missed (pending == current) the
        full window is left; each elapsed day burns one. 0 means the window has
        closed and the streak should reset.
        """
        elapsed = (current_day - pending_day).days
        return max(0, config.REVIVE_GRACE_DAYS - elapsed)

    # ----------------------------------------------------------------- reads --
    async def get_or_create_streak(self, guild_id: int, user_id: int) -> UserStreak:
        doc = await UserStreak.find_one(
            UserStreak.guild_id == guild_id, UserStreak.user_id == user_id
        )
        if doc is None:
            doc = UserStreak(guild_id=guild_id, user_id=user_id)
            await doc.insert()
        return doc

    # ---------------------------------------------------------------- delete --
    async def forget_user(self, guild_id: int, user_id: int) -> None:
        """
        Erase a user's streak in a guild (used when they leave the server).

        Any buffered message counts are dropped first, otherwise the next flush
        would re-create the document we just deleted.
        """
        self._pending_messages.pop((guild_id, user_id), None)
        await UserStreak.find(
            UserStreak.guild_id == guild_id, UserStreak.user_id == user_id
        ).delete()

    async def forget_guild(self, guild_id: int) -> None:
        """Erase every streak in a guild (used when the bot is removed from it)."""
        for key in [k for k in self._pending_messages if k[0] == guild_id]:
            del self._pending_messages[key]
        await UserStreak.find(UserStreak.guild_id == guild_id).delete()

    # -------------------------------------------------------------- activity --
    async def _register_activity(
        self, guild_id: int, user_id: int, day: date
    ) -> tuple[UserStreak, bool]:
        """
        Credit today's activity to the single unified streak (once per day).
        Returns (streak_doc, first_activity_today).
        """
        streak = await self.get_or_create_streak(guild_id, user_id)
        first_today = streak.last_day != day
        if first_today:
            streak.streak = self._advance(streak.last_day, day, streak.streak)
            streak.last_day = day
            streak.best = max(streak.best, streak.streak)
            streak.updated_at = clock.now_utc()
            await streak.save()
        return streak, first_today

    async def register_message(
        self, guild_id: int, user_id: int, day: date
    ) -> tuple[UserStreak, bool]:
        """
        Record a chat message. Returns (streak_doc, first_activity_today).

        The running total is buffered (flushed later). The streak is only advanced
        on the first activity of the day, written immediately so the reaction
        shows the correct count.
        """
        self._pending_messages[(guild_id, user_id)] += 1
        return await self._register_activity(guild_id, user_id, day)

    async def register_voice_join(
        self, guild_id: int, user_id: int, day: date
    ) -> UserStreak | None:
        """
        Joining voice credits +1 to the unified streak for ``day`` (once per day).
        Returns the streak doc if it advanced, else None.
        """
        streak, first_today = await self._register_activity(guild_id, user_id, day)
        return streak if first_today else None

    # ----------------------------------------------------------------- flush --
    async def flush_pending(self) -> None:
        """Bulk-write buffered message totals, then clear the buffer."""
        if not self._pending_messages:
            return

        bulk = [
            UpdateOne(
                {"guild_id": g, "user_id": u},
                {"$inc": {"total_messages": count}},
                upsert=True,
            )
            for (g, u), count in self._pending_messages.items()
        ]
        if bulk:
            await UserStreak.get_pymongo_collection().bulk_write(bulk, ordered=False)
        self._pending_messages.clear()

    # ----------------------------------------------------------- revive logic --
    async def reset_broken_streaks(self, day_just_ended: date) -> list[BrokenStreak]:
        """
        End-of-day check. For each user who was not active on the day that just
        ended:

        * real streak **with revives left** -> enters the pending-revive grace
          window and is returned so the user gets a revive-offer DM;
        * real streak **with no revives left** -> resets to 0 immediately (no
          grace window) and is returned so the user gets a "streak lost" DM;
        * building-up (non-real) streak -> resets silently, no DM.
        """
        broken: list[BrokenStreak] = []

        async for s in UserStreak.find_all():
            if s.streak <= 0 or s.last_day == day_just_ended:
                continue

            real = self.is_real_streak(s.streak)
            left = self.revives_left(s)

            if real and left > 0:
                s.revive_pending_day = day_just_ended
                broken.append(
                    BrokenStreak(
                        s,
                        s.streak,
                        left,
                        day_just_ended,
                        days_left=config.REVIVE_GRACE_DAYS,
                    )
                )
            else:
                # No revives left (or not a real streak): the streak resets now.
                # A real streak still gets a "streak lost" DM (revives_left=0
                # routes _dm_offer_revive straight to _dm_streak_lost); a non-real
                # streak resets silently.
                if real:
                    broken.append(BrokenStreak(s, s.streak, 0, day_just_ended))
                s.streak = 0
                s.revive_pending_day = None

            s.updated_at = clock.now_utc()
            await s.save()

        return broken

    async def use_revive(
        self, guild_id: int, user_id: int, missed_day: date
    ) -> tuple[bool, int, int]:
        """Spend one revive. Returns (success, revives_left, streak_value)."""
        s = await self.get_or_create_streak(guild_id, user_id)

        if s.revive_pending_day != missed_day:
            return False, self.revives_left(s), s.streak
        if self.revives_left(s) <= 0:
            return False, 0, 0

        # Freeze the streak: the missed day is credited, the value is preserved.
        s.revives += 1  # one more revive used
        s.last_day = missed_day
        s.revive_pending_day = None
        s.updated_at = clock.now_utc()
        await s.save()
        return True, self.revives_left(s), s.streak

    async def expire_pending_revives(self, current_day: date) -> list[BrokenStreak]:
        """
        Resolve pending revives whose fixed grace window has closed without a
        revive being used -> streak is truly lost (reset to 0). Pending revives
        still inside the window are left untouched here (see
        ``pending_revive_reminders``).
        """
        lost: list[BrokenStreak] = []

        async for s in UserStreak.find_all():
            if (
                s.revive_pending_day is not None
                and s.last_day != current_day
                and self._grace_days_left(s.revive_pending_day, current_day) <= 0
            ):
                lost.append(
                    BrokenStreak(
                        s, s.streak, self.revives_left(s), s.revive_pending_day
                    )
                )
                s.streak = 0
                s.revive_pending_day = None
                s.updated_at = clock.now_utc()
                await s.save()

        return lost

    async def pending_revive_reminders(self, current_day: date) -> list[BrokenStreak]:
        """
        Pending revives still inside the grace window (not used yet) -> daily
        reminder with how many days are left before the streak resets. Excludes
        the day the streak was first missed (that initial DM comes from the
        rollover's ``reset_broken_streaks`` path).
        """
        reminders: list[BrokenStreak] = []

        async for s in UserStreak.find_all():
            if (
                s.revive_pending_day is not None
                and s.revive_pending_day != current_day
                and s.last_day != current_day
            ):
                days_left = self._grace_days_left(s.revive_pending_day, current_day)
                if days_left > 0:
                    reminders.append(
                        BrokenStreak(
                            s,
                            s.streak,
                            self.revives_left(s),
                            s.revive_pending_day,
                            days_left=days_left,
                        )
                    )

        return reminders

    async def users_at_risk(self, today: date) -> list[UserStreak]:
        """Users with a real streak alive who haven't been active today."""
        return [
            s
            async for s in UserStreak.find_all()
            if self.is_real_streak(s.streak) and s.last_day != today
        ]


# Module-level singleton used across the bot.
streak_service = StreakService()
