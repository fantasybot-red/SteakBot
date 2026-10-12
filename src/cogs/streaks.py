"""
Streaks cog: hybrid commands (work as both slash and prefix) for users to view
their streak and the server leaderboard.

This cog only gathers data; all presentation/sending is delegated to
``response_service``.
"""

import discord
from discord.ext import commands
from discord.ext.commands import Context

from core.config import config
from database import UserStreak
from utils import response_service, streak_service


class Streaks(commands.Cog, name="streaks"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="streak",
        description="Xem chuỗi hoạt động của bạn hoặc người khác.",
    )
    async def streak(self, context: Context, member: discord.Member = None) -> None:
        """Hiển thị chuỗi hoạt động của bạn hoặc thành viên khác."""
        member = member or context.author
        streak = await streak_service.get_or_create_streak(
            context.guild.id, member.id
        )
        await response_service.streak(context, member, streak)

    @commands.hybrid_command(
        name="leaderboard",
        description="Bảng xếp hạng chuỗi hoạt động trong server.",
    )
    async def leaderboard(self, context: Context) -> None:
        """Hiển thị bảng xếp hạng chuỗi của server."""
        # Only real streaks (count > STREAK_THRESHOLD) appear on the leaderboard.
        rows = (
            await UserStreak.find(
                UserStreak.guild_id == context.guild.id,
                UserStreak.streak > config.STREAK_THRESHOLD,
            )
            .sort(-UserStreak.streak)
            .limit(10)
            .to_list()
        )
        await response_service.leaderboard(
            context,
            context.guild.name,
            response_service.rank_entries(context.guild, rows),
        )


async def setup(bot) -> None:
    await bot.add_cog(Streaks(bot))
