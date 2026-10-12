"""
Tracking cog.

Chat
----
``on_message`` -> buffer the message count and, on the first message of the day,
advance the chat streak and add the 🔥 + number reaction.

Voice
-----
``on_voice_state_update`` -> when a user **joins** a countable voice channel,
credit +1 to their voice streak for today (once per day). That's it: no
sessions, no minute tracking.

Cleanup
-------
``on_member_remove`` / ``on_guild_remove`` -> erase stored streaks once a user
leaves a server (or the bot is removed from one), so the database only holds
data for people the bot can still see.
"""

import discord
from discord.ext import commands, tasks

from core.config import config
from utils import clock, response_service, streak_service


def is_countable_voice(state: discord.VoiceState) -> bool:
    """Counts only if actually present: in a channel, not AFK, not deafened."""
    if state is None or state.channel is None:
        return False
    guild = state.channel.guild
    if guild.afk_channel is not None and state.channel.id == guild.afk_channel.id:
        return False
    if state.self_deaf or state.deaf:
        return False
    return True


class Tracking(commands.Cog, name="tracking"):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.flusher.start()

    async def cog_unload(self) -> None:
        self.flusher.cancel()
        await streak_service.flush_pending()

    # ------------------------------------------------------------------ chat --
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if not message.content and not message.attachments:
            return

        streak, first_today = await streak_service.register_message(
            message.guild.id, message.author.id, clock.local_day()
        )
        # React only on the first activity of the day AND only once the streak is
        # a real streak (count > STREAK_THRESHOLD). Build-up days get no reaction.
        if first_today and streak_service.is_real_streak(streak.streak):
            await response_service.react_streak(message, streak.streak)

    # ----------------------------------------------------------------- voice --
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot or member.guild is None:
            return

        # Only on a transition INTO a countable voice channel.
        if is_countable_voice(before) or not is_countable_voice(after):
            return

        # register_voice_join returns the streak doc only when the streak
        # actually advanced today (first activity of the day), else None.
        streak = await streak_service.register_voice_join(
            member.guild.id, member.id, clock.local_day()
        )
        if streak is None or not streak_service.is_real_streak(streak.streak):
            return

        # Announce in the voice channel's built-in text chat (mentions suppressed).
        await response_service.voice_join(after.channel, member, streak.streak)

    # ---------------------------------------------------------------- leave --
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Drop a member's streak when they leave (or are kicked/banned)."""
        if member.bot:
            return
        await streak_service.forget_user(member.guild.id, member.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Drop every streak in a guild the bot was removed from."""
        await streak_service.forget_guild(guild.id)

    # ----------------------------------------------------------------- flush --
    @tasks.loop(minutes=config.FLUSH_INTERVAL_MINUTES)
    async def flusher(self) -> None:
        """Persist buffered message counters."""
        await streak_service.flush_pending()

    @flusher.before_loop
    async def _before_flusher(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot) -> None:
    await bot.add_cog(Tracking(bot))
