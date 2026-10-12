"""
Presentation layer.

``ResponseService`` is the single place that turns data into Discord output:
embeds, content strings, views, reactions, Discord timestamps, and the actual
``send`` call. Cogs and the scheduler pass plain data (a streak doc, a list of
rows, a user) and let this service decide how it looks and goes out.

Every method takes the *target* to send to as its first argument. Anything with
an ``async send()`` works — a command ``Context``, a ``User``'s DM channel, or a
``TextChannel`` — which is how the debug cog previews real messages in another
channel without duplicating any wording or embed construction.
"""

from datetime import date

import discord

from database import UserStreak
from utils.messages import messages
from utils.revive_view import build_revive_view
from utils.streak_emoji import streak_emoji
from utils.streak_service import BrokenStreak, streak_service
from utils.timezone import clock

#: Ranked leaderboard medals by position.
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

#: For the public voice-join announcement: render the mention as a name but
#: don't actually ping the whole channel. DMs intentionally ping the recipient.
NO_PING = discord.AllowedMentions.none()


class ResponseService:
    """Builds and sends every user-facing response the bot produces."""

    # --------------------------------------------------------- user commands --
    async def streak(self, target, member: discord.Member, streak: UserStreak) -> None:
        """Send the streak card for ``member``."""
        # A streak only "spawns" (is shown) once it passes STREAK_THRESHOLD.
        if streak_service.is_real_streak(streak.streak):
            description = messages.get(
                "streak_card.value",
                status="🔥",
                count=streak.streak,
                best=streak.best,
            )
        else:
            description = messages.get("streak_card.building")

        embed = discord.Embed(
            title=messages.get("streak_card.title", name=self.display_name(member)),
            description=description,
            color=discord.Color.orange(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send(target, embed=embed)

    async def leaderboard(
        self, target, guild_name: str, entries: list[tuple[str, int]]
    ) -> None:
        """Send the leaderboard built from ranked ``(name, count)`` entries."""
        lines = [
            messages.get(
                "leaderboard.row",
                medal=MEDALS.get(rank, f"`{rank}.`"),
                name=name,
                count=count,
            )
            for rank, (name, count) in enumerate(entries, start=1)
        ]
        embed = discord.Embed(
            title=messages.get("leaderboard.title", guild=guild_name),
            description="\n".join(lines) or messages.get("leaderboard.empty"),
            color=discord.Color.gold(),
        )
        await self.send(target, embed=embed)

    async def no_permission(self, target) -> None:
        """Reply that the invoker lacks permission for a command."""
        await self.send(target, content=messages.get("common.no_permission"))

    # -------------------------------------------------------------- tracking --
    async def react_streak(self, message: discord.Message, count: int) -> None:
        """Add the 🔥 + digit reactions for ``count`` to ``message``."""
        try:
            for emoji in streak_emoji.reactions(count):
                await message.add_reaction(emoji)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def voice_join(self, target, member: discord.Member, count: int) -> None:
        """Announce a voice-join streak advance in the channel's chat."""
        await self.send(
            target,
            content=messages.get("voice_join", user=member.mention, count=count),
            allowed_mentions=NO_PING,
        )

    # --------------------------------------------------------- scheduler DMs --
    async def reminder(
        self, target, member, guild_name: str, count: int, day: date
    ) -> None:
        """Tell ``member`` (plain text) their real streak is at risk before midnight."""
        await self.send(
            target,
            content=messages.get(
                "reminder",
                user=member.mention,
                guild=guild_name,
                count=count,
                deadline=clock.discord_time(clock.end_of_day(day), "R"),
            ),
        )

    async def offer_revive(
        self,
        target,
        guild_id: int,
        user_id: int,
        guild_name: str,
        count: int,
        revives_left: int,
        missed_day: date,
    ) -> None:
        """Send the revive offer embed together with its revive button."""
        text = messages.group("offer_revive", guild=guild_name, count=count)
        await self.send(
            target,
            embed=discord.Embed(
                title=text["title"],
                description=text["body"],
                color=discord.Color.red(),
            ),
            view=build_revive_view(guild_id, user_id, missed_day, revives_left),
        )

    async def streak_lost(
        self, target, member, guild_name: str, count: int
    ) -> None:
        """Tell ``member`` (plain text) their streak was lost for good."""
        await self.send(
            target,
            content=messages.get(
                "streak_lost",
                user=member.mention,
                count=count,
                guild=guild_name,
            ),
        )

    async def broken_streak(self, user, broken: BrokenStreak, guild_name: str) -> None:
        """
        DM the outcome of a broken streak: a revive offer while the user still
        has revives left, otherwise a "streak lost" notice.
        """
        if broken.revives_left <= 0:
            await self.streak_lost(user, user, guild_name, broken.count)
            return

        await self.offer_revive(
            user,
            broken.streak.guild_id,
            broken.streak.user_id,
            guild_name,
            broken.count,
            broken.revives_left,
            broken.missed_day,
        )

    # -------------------------------------------------------- revive button --
    def revive_text(self, success: bool, revives_left: int, value: int) -> str:
        """The wording shown after a revive button is clicked."""
        if success:
            return messages.get("revive.used", count=value, revives=revives_left)
        if revives_left <= 0:
            return messages.get("revive.none_left")
        return messages.get("revive.expired")

    async def revive_result(
        self,
        interaction: discord.Interaction,
        success: bool,
        revives_left: int,
        value: int,
    ) -> None:
        """
        Respond to a revive-button click with a follow-up message. A successful
        revive is public; failures stay ephemeral.

        The interaction response is already consumed by the button disabling
        itself (``edit_message``), so this only sends a follow-up. If the
        interaction token has expired, fall back to a plain DM so the user
        still learns the outcome.
        """
        content = self.revive_text(success, revives_left, value)
        try:
            await interaction.followup.send(content, ephemeral=not success)
        except discord.HTTPException:
            await self.send(interaction.user, content=content)

    # --------------------------------------------------------------- helpers --
    @staticmethod
    def display_name(member) -> str:
        """Server nickname when set, otherwise the member's display name."""
        return getattr(member, "nick", None) or member.display_name

    def resolve_name(self, guild: discord.Guild, user_id: int) -> str:
        """
        A mention for a user id. ``<@id>`` renders as the user's name whether or
        not they are still in the guild, and inside an embed description it never
        pings. The ``guild`` argument is kept for signature symmetry with the
        rest of the service.
        """
        return f"<@{user_id}>"

    def rank_entries(
        self, guild: discord.Guild, rows: list[UserStreak]
    ) -> list[tuple[str, int]]:
        """Turn ranked streak documents into ``(name, count)`` entries."""
        return [(self.resolve_name(guild, row.user_id), row.streak) for row in rows]

    @staticmethod
    async def send(target, **kwargs) -> None:
        """Best-effort send; silently ignores closed DMs and missing permissions."""
        try:
            await target.send(**kwargs)
        except (discord.Forbidden, discord.HTTPException):
            pass


# Module-level singleton used across the bot.
response_service = ResponseService()
