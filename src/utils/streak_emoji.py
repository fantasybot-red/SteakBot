"""
Builds the list of emoji reactions used to display a streak count on a message,
TikTok-style: a fire emoji followed by the number as keycap digit emojis.

Example: streak of 12 -> ["🔥", "1️⃣", "2️⃣"]

Note: Discord adds reactions in the order given, and a message can hold at most
20 distinct reactions, which is far more than we need.
"""


class StreakEmoji:
    """Renders a streak count as an ordered list of Discord emoji reactions."""

    FIRE = "🔥"

    _DIGITS = {
        "0": "0️⃣",
        "1": "1️⃣",
        "2": "2️⃣",
        "3": "3️⃣",
        "4": "4️⃣",
        "5": "5️⃣",
        "6": "6️⃣",
        "7": "7️⃣",
        "8": "8️⃣",
        "9": "9️⃣",
    }

    def number_emojis(self, n: int) -> list[str]:
        """Return keycap-digit emojis for a non-negative integer."""
        return [self._DIGITS[d] for d in str(max(0, n))]

    def reactions(self, streak: int) -> list[str]:
        """🔥 followed by the streak number as digit emojis."""
        return [self.FIRE, *self.number_emojis(streak)]


# Module-level singleton used across the bot.
streak_emoji = StreakEmoji()
