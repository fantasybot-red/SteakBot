"""
Debug cog: preview every message/embed the bot can send.

Previews are produced by the very same ``ResponseService`` builders the live bot
uses, so what you see here is exactly what users get — no duplicated wording or
embed construction. Owner-only.

Commands
--------
``/debug_templates [here]``  - send every template (DM by default, or in the
                               current channel with ``here: True``).
``/debug_template <name>``   - send a single template by name.
"""

from datetime import date

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

from utils import messages, response_service

# Sample values used to render the previews.
SAMPLE_GUILD = "Server Mẫu"
SAMPLE_STREAK = 12
SAMPLE_BEST = 30
SAMPLE_REVIVES_LEFT = 2
SAMPLE_DAY = date(2026, 5, 10)
SAMPLE_ROWS = [("Người A", 30), ("Người B", 21), ("Người C", 12), ("Người D", 4)]

TEMPLATE_NAMES = [
    "reminder",
    "offer_revive",
    "streak_lost",
    "revive_used",
    "revive_none_left",
    "revive_expired",
    "revive_not_yours",
    "streak_card",
    "leaderboard",
    "voice_join",
    "reaction",
]


class _SampleStreak:
    """Stand-in for a UserStreak document, just for rendering previews."""

    def __init__(self, streak: int, best: int) -> None:
        self.streak = streak
        self.best = best


class Debug(commands.Cog, name="debug"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="debug_templates",
        description="[Chủ bot] Gửi thử TẤT CẢ mẫu tin nhắn của bot.",
    )
    @commands.is_owner()
    @app_commands.describe(here="Gửi ngay trong kênh này thay vì DM.")
    async def debug_templates(self, context: Context, here: bool = False) -> None:
        target = context.channel if here else context.author
        await context.send(
            f"📨 Đang gửi {len(TEMPLATE_NAMES)} mẫu tin nhắn "
            f"{'vào kênh này' if here else 'qua DM'}...",
            ephemeral=not here,
        )
        try:
            for name in TEMPLATE_NAMES:
                await self._send_template(target, name, context)
        except discord.Forbidden:
            await context.send(
                "❌ Không gửi được DM cho bạn. Hãy bật DM từ thành viên server, "
                "hoặc dùng `here: True`."
            )

    @commands.hybrid_command(
        name="debug_template",
        description="[Chủ bot] Gửi thử MỘT mẫu tin nhắn theo tên.",
    )
    @commands.is_owner()
    @app_commands.describe(name="Tên mẫu tin nhắn cần xem.")
    @app_commands.choices(
        name=[app_commands.Choice(name=n, value=n) for n in TEMPLATE_NAMES[:25]]
    )
    async def debug_template(self, context: Context, name: str) -> None:
        if name not in TEMPLATE_NAMES:
            await context.send(
                f"❌ Không có mẫu `{name}`.\nCó sẵn: "
                + ", ".join(f"`{n}`" for n in TEMPLATE_NAMES)
            )
            return
        await self._send_template(context.channel, name, context)

    async def _send_template(self, target, name: str, context: Context) -> None:
        """Preview one template by driving the real ResponseService methods."""
        user = context.author
        guild_name = context.guild.name if context.guild else SAMPLE_GUILD
        guild_id = context.guild.id if context.guild else 0
        rs = response_service

        # Label the preview, then let the service send the real thing below.
        await target.send(f"── `{name}` ──")

        if name == "reminder":
            await rs.reminder(target, user, guild_name, SAMPLE_STREAK, SAMPLE_DAY)
        elif name == "offer_revive":
            await rs.offer_revive(
                target,
                guild_id,
                user.id,
                guild_name,
                SAMPLE_STREAK,
                SAMPLE_DAY,
            )
        elif name == "streak_lost":
            await rs.streak_lost(target, user, guild_name, SAMPLE_STREAK)
        elif name == "streak_card":
            await rs.streak(target, user, _SampleStreak(SAMPLE_STREAK, SAMPLE_BEST))
        elif name == "leaderboard":
            await rs.leaderboard(target, guild_name, SAMPLE_ROWS)
        elif name == "voice_join":
            await rs.voice_join(target, user, SAMPLE_STREAK)
        elif name == "revive_used":
            await rs.send(
                target,
                content=rs.revive_text(True, SAMPLE_REVIVES_LEFT, SAMPLE_STREAK),
            )
        elif name == "revive_none_left":
            await rs.send(target, content=rs.revive_text(False, 0, 0))
        elif name == "revive_expired":
            await rs.send(
                target,
                content=rs.revive_text(False, SAMPLE_REVIVES_LEFT, SAMPLE_STREAK),
            )
        elif name == "revive_not_yours":
            # Bare catalog string with no service method of its own.
            await rs.send(target, content=messages.get("revive.not_yours"))
        elif name == "reaction":
            sent = await target.send(
                "Đây là tin nhắn đầu tiên trong ngày — "
                f"bot sẽ thả cảm xúc chuỗi **{SAMPLE_STREAK}** lên tin nhắn này:"
            )
            await rs.react_streak(sent, SAMPLE_STREAK)


async def setup(bot) -> None:
    await bot.add_cog(Debug(bot))
