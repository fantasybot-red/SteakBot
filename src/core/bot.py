"""
StreakBot — a TikTok-style chat & voice streak tracker for Discord.

Based on the structure of kkrypt0nn/Python-Discord-Bot-Template, adapted to use
Beanie (MongoDB) instead of SQLite and to run the streak-tracking cogs.
"""

import os

import discord
from discord.ext import commands
from discord.ext.commands import Context

from core.config import config
from database import init_db
from utils import ReviveButton, messages, response_service

# ------------------------------------------------------------------------- bot
class StreakBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(config.PREFIX),
            intents=discord.Intents.all(),
            help_command=None,
        )

    async def load_cogs(self) -> None:
        # cogs/ is a sibling of core/ inside src/
        cogs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cogs")
        for file in os.listdir(cogs_dir):
            if file.endswith(".py") and not file.startswith("_"):
                extension = file[:-3]
                try:
                    await self.load_extension(f"cogs.{extension}")
                except Exception as e:  # noqa: BLE001
                    print(f"Failed to load extension {extension}: {type(e).__name__}: {e}")

    async def setup_hook(self) -> None:
        await init_db()
        # Persistent revive buttons (keep working across restarts)
        self.add_dynamic_items(ReviveButton)
        await self.load_cogs()

    async def on_ready(self) -> None:
        await self.tree.sync()
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="chuỗi của bạn 🔥"
            )
        )
        print(messages.get("common.ready_log", user=self.user, tz=config.TIMEZONE_NAME))

    async def on_command_error(self, context: Context, error) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, (commands.MissingPermissions, commands.NotOwner)):
            await response_service.no_permission(context)
            return
        print(f"Command error in {context.command}: {error}")
