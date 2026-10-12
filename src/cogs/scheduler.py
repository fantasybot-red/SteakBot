"""
Scheduler cog: time-based streak maintenance.

Two scheduled jobs (both aligned to the configured local timezone):

1. End-of-day reminder (a bit before midnight): DM users who have a *real*
   streak alive but have not been active today, warning them they're about to
   lose it. If they've used a revive before, the DM includes a revive button.

2. Day rollover (just after midnight): resolve the day that just ended.
   * Missed real streaks go into a "pending revive" state and get a DM with a
     revive button.
   * Pending revives from earlier that were never used expire -> streak lost DM.
   * Missed building-up (non-real) streaks reset silently.
"""

import datetime

import discord
from discord.ext import commands, tasks

from core.config import config
from utils import clock, messages, response_service, streak_service


def _reminder_times() -> list[datetime.time]:
    """Local times to send 'at risk' reminders, derived from hours-before-midnight."""
    times = []
    for hours in config.REMINDER_HOURS_BEFORE:
        hour = (24 - hours) % 24  # e.g. 2h before midnight -> 22:00
        times.append(datetime.time(hour=hour, minute=0, tzinfo=config.TIMEZONE))
    # Fall back to a single 23:00 reminder if nothing was configured.
    return times or [datetime.time(hour=23, minute=0, tzinfo=config.TIMEZONE)]


# Reminders fire N hours before midnight; rollover just after midnight.
REMINDER_TIMES = _reminder_times()
ROLLOVER_TIME = datetime.time(hour=0, minute=5, tzinfo=config.TIMEZONE)


class Scheduler(commands.Cog, name="scheduler"):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.end_of_day_reminder.start()
        self.day_rollover.start()

    async def cog_unload(self) -> None:
        self.end_of_day_reminder.cancel()
        self.day_rollover.cancel()

    # ---------------------------------------------------------- reminder job --
    @tasks.loop(time=REMINDER_TIMES)
    async def end_of_day_reminder(self) -> None:
        today = clock.local_day()
        for streak in await streak_service.users_at_risk(today):
            user = await self._resolve_user(streak.user_id)
            if user is None:
                continue
            await response_service.reminder(
                user, user, self._guild_name(streak.guild_id), streak.streak, today
            )

    # ---------------------------------------------------------- rollover job --
    @tasks.loop(time=ROLLOVER_TIME)
    async def day_rollover(self) -> None:
        today = clock.local_day()
        day_ended = clock.previous_day(today)

        # Make sure buffered counters are persisted before we evaluate streaks.
        await streak_service.flush_pending()

        # 1. Expire revives whose grace window has fully closed -> streak lost.
        for lost in await streak_service.expire_pending_revives(today):
            await self._dm_streak_lost(lost)

        # 2. Handle streaks missed on the day that just ended (new pending).
        for broken in await streak_service.reset_broken_streaks(day_ended):
            await self._dm_offer_revive(broken)

        # 3. Remind users with a revive still pending inside the grace window.
        for pending in await streak_service.pending_revive_reminders(today):
            await self._dm_offer_revive(pending)

    async def _dm_offer_revive(self, broken) -> None:
        """Offer a revive, or announce the loss when no revives are left."""
        user = await self._resolve_user(broken.streak.user_id)
        if user is None:
            return
        await response_service.broken_streak(
            user, broken, self._guild_name(broken.streak.guild_id)
        )

    async def _dm_streak_lost(self, broken) -> None:
        user = await self._resolve_user(broken.streak.user_id)
        if user is None:
            return
        await response_service.streak_lost(
            user, user, self._guild_name(broken.streak.guild_id), broken.count
        )

    def _guild_name(self, guild_id: int) -> str:
        guild = self.bot.get_guild(guild_id)
        return guild.name if guild else messages.get("common.guild_fallback")

    async def _resolve_user(self, user_id: int):
        user = self.bot.get_user(user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except discord.HTTPException:
                return None
        return user

    @end_of_day_reminder.before_loop
    async def _before_reminder(self) -> None:
        await self.bot.wait_until_ready()

    @day_rollover.before_loop
    async def _before_rollover(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot) -> None:
    await bot.add_cog(Scheduler(bot))
