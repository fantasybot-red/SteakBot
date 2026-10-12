"""
Persistent button View used in the "you're about to lose your streak" DM.

The custom_id encodes everything needed to resolve the action after a restart:
    revive:<guild_id>:<user_id>:<missed_day>

A single ReviveView instance with a dynamic item is registered on the bot at
startup via `bot.add_view(ReviveView())` so the buttons keep working across
restarts.
"""

from datetime import date

import discord

from utils.streak_service import streak_service

CUSTOM_ID_PREFIX = "revive"

#: Fallback label for a button rebuilt after a restart (its original label is
#: not stored in the custom_id). Cosmetic only — the first click disables it.
DEFAULT_BUTTON_LABEL = "🧊 Dùng hồi sinh"


def make_custom_id(guild_id: int, user_id: int, missed_day: date) -> str:
    # missed_day is encoded as an ISO date string "YYYY-MM-DD".
    return f"{CUSTOM_ID_PREFIX}:{guild_id}:{user_id}:{missed_day.isoformat()}"


class ReviveButton(discord.ui.DynamicItem[discord.ui.Button], template=r"revive:(?P<gid>\d+):(?P<uid>\d+):(?P<day>[\d-]+)"):
    """A persistent, self-describing revive button."""

    def __init__(
        self,
        guild_id: int,
        user_id: int,
        missed_day: date,
        label: str | None = None,
    ) -> None:
        self.guild_id = guild_id
        self.user_id = user_id
        self.missed_day = missed_day
        super().__init__(
            discord.ui.Button(
                # The label is chosen alongside the offer_revive message so the
                # two stay paired; on a rebuilt (restart) button it is cosmetic
                # only, since the first click disables it anyway.
                label=label or DEFAULT_BUTTON_LABEL,
                style=discord.ButtonStyle.success,
                custom_id=make_custom_id(guild_id, user_id, missed_day),
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(
            guild_id=int(match["gid"]),
            user_id=int(match["uid"]),
            missed_day=date.fromisoformat(match["day"]),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        # Interactions must be acknowledged within 3 seconds, and the revive
        # below hits the database — so answer FIRST, then do the slow work.
        #
        # The button is one-shot: whatever the outcome, this missed day is
        # resolved and there is nothing left to click. That lets us disable it
        # up front as the acknowledgement.
        self.item.disabled = True
        try:
            await interaction.response.edit_message(view=self.view)
        except discord.HTTPException:
            # Interaction expired or already answered; carry on with the revive.
            pass

        # The revive DM is sent to a single user's DMs, so only that user can
        # ever click this button — no ownership check is needed here.
        success, revives_left, value = await streak_service.use_revive(
            self.guild_id, self.user_id, self.missed_day
        )

        # Delegate the reply to the response service (imported lazily to avoid
        # a circular import: response_service imports this module for the view).
        from utils.response_service import response_service

        await response_service.revive_result(
            interaction, success, revives_left, value
        )


class ReviveView(discord.ui.View):
    """Container view; the dynamic item is registered separately on the bot."""

    def __init__(self) -> None:
        super().__init__(timeout=None)


def build_revive_view(
    guild_id: int, user_id: int, missed_day: date, label: str | None = None
) -> discord.ui.View:
    """Build a fresh view carrying a revive button for a specific DM."""
    view = discord.ui.View(timeout=None)
    view.add_item(ReviveButton(guild_id, user_id, missed_day, label))
    return view
