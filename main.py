"""
Entrypoint for StreakBot.

Run with:  python main.py   (or: uv run python main.py)
"""

import os
import sys

# Make `src` the import root so packages (core, cogs, database, utils) resolve.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from core.bot import StreakBot  # noqa: E402
from core.config import config  # noqa: E402

if __name__ == "__main__":
    if not config.TOKEN:
        raise SystemExit(
            "TOKEN chưa được thiết lập. Hãy sao chép .env.example thành .env "
            "và điền thông tin."
        )

    bot = StreakBot()
    bot.run(config.TOKEN)
