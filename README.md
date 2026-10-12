# 🔥 StreakBot

A Discord bot that tracks **TikTok-style streaks** for chatting and talking in
voice — two independent streaks, daily fire-emoji reactions, DM reminders, and a
button-based **revive** (streak freeze) system.

Built with [discord.py](https://discordpy.readthedocs.io/) and
[Beanie](https://beanie-odm.dev/) (MongoDB), following the project structure of
[kkrypt0nn/Python-Discord-Bot-Template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template).

## Features

- **Two separate streaks per user** (they are *not* the same):
  - 💬 **Chat streak** — days with at least one message.
  - 🔊 **Voice streak** — +1 per day whenever you join a voice channel.
- **2-level streaks** — a streak only becomes a "real" 🔥 streak once it passes
  **3 consecutive days** (`STREAK_THRESHOLD`). Below that it's a 🌱 building-up
  streak.
- **Fire + number reaction** — the first message you send each day gets reacted
  with 🔥 followed by your streak count as digit emojis (e.g. 🔥1️⃣2️⃣ for a 12-day
  streak), TikTok-style.
- **End-of-day DM reminder** — if you have a real streak alive but haven't been
  active today, the bot DMs you before midnight so you don't lose it.
- **Revives / streak freezes** — every user has **3 revives** per streak type.
  Miss a day on a real streak and the bot DMs you a **button** to spend a revive
  and save it. Run out of revives → the streak resets and you start over.
- **Always-on / 24-7 voice handled correctly** — a per-minute ticker credits
  connected users and splits long sessions across the day boundary, so never
  leaving voice still correctly counts each day (AFK channel and self-deafened
  users are ignored).
- **Hybrid commands** — every command works as **both a slash command and a
  prefix command**.

## Commands

| Command | Description |
| --- | --- |
| `/streak [member]` or `!streak` | Show chat & voice streaks, best streaks, and revives. |
| `/revives` or `!revives` | Check your remaining revives. |
| `/leaderboard` or `!leaderboard` | Top chat & voice streaks in the server. |

## Project structure

```
StreakBot/
├── main.py                 # Entrypoint: builds and runs the bot
├── .env.example            # Copy to .env and fill in
└── src/
    ├── core/
    │   ├── bot.py          # Bot subclass, intents, logging, cog loader
    │   └── config.py       # Env-based configuration
    ├── database/
    │   ├── connection.py   # AsyncMongoClient + Beanie init (Beanie 2.x)
    │   └── models.py       # UserStreak document (only 1 collection!)
    ├── cogs/
    │   ├── tracking.py     # Message + voice-join listeners, buffered flusher
    │   ├── scheduler.py    # Reminders + midnight rollover
    │   └── streaks.py      # Hybrid commands (streak/revives/leaderboard)
    └── utils/
        ├── timezone.py        # Local-day (datetime.date) math, UTC+7 default
        ├── streak_emoji.py    # 🔥 + digit-emoji builder
        ├── streak_service.py  # Core streak + revive logic, write buffering
        └── revive_view.py     # Persistent revive button (DynamicItem)
```

## Setup

1. **Enable privileged intents** in the
   [Discord Developer Portal](https://discord.com/developers/applications). The
   bot requests all intents, so turn on all three:
   - ✅ Presence Intent
   - ✅ Server Members Intent
   - ✅ Message Content Intent

2. **Configure**
   ```bash
   cp .env.example .env   # on Windows: copy .env.example .env
   ```
   Fill in `TOKEN`. Set `MONGO_URI` (or let Docker provide it). Adjust
   `TIMEZONE` (default `Asia/Bangkok`, i.e. UTC+7), `STREAK_THRESHOLD`,
   `REVIVE_MAX`, `REMINDER_HOURS_BEFORE` and `FLUSH_INTERVAL_MINUTES` to taste.

### Run with Docker (recommended)

Brings up the bot **and** a database together. See **[`docker/README.md`](docker/README.md)**
for details (including Raspberry Pi notes):

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

Only `TOKEN` is required in your `.env`; the compose file wires the bot to the
bundled database automatically.

### Run locally (without Docker)

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and a reachable
MongoDB (local install or [Atlas](https://www.mongodb.com/atlas)).

```bash
uv sync
uv run python main.py
```

## How the logic works

### Day boundaries
All "what day is it" decisions use the configured local timezone (`TIMEZONE`,
default **UTC+7**). Timestamps are stored internally in UTC.

### Chat streak
On each message the day's activity is recorded. The first counted message of the
day advances the chat streak (`+1` if yesterday counted, reset to `1` after a
gap) and triggers the 🔥 + number reaction.

### Voice streak
- Driven by the `on_voice_state_update` **event**: joining a non-AFK voice
  channel (and not self-deafened) adds **+1** to the voice streak for that day
  (once per day). No sessions, no minute tracking.

### Small database & few writes
- **One collection**: `user_streaks` (a single document per user, forever). No
  per-day or per-session rows, so size stays constant.
- The lifetime `total_messages` count is **buffered in memory** and bulk-written
  every `FLUSH_INTERVAL_MINUTES`. Only the first message of a day writes
  immediately (to keep the 🔥 reaction accurate).
- "Which day" fields are stored as `datetime.date` objects; timestamps are
  tz-aware UTC (normalized on read since MongoDB returns naive datetimes).

### Revives (streak freeze)
- At day rollover (`00:05` local), any **real** streak (`> 3`) that missed the
  previous day enters a *pending-revive* state and the user gets a DM with a
  **button**.
- Clicking the button spends one revive and keeps the streak alive.
- If the user neither revives nor becomes active again, the pending revive
  **expires** at the next rollover and the streak resets to `0`.
- When all `REVIVE_MAX` revives are gone, a missed day resets the streak
  immediately and the user must start over.
- Buttons are **persistent** (`discord.ui.DynamicItem`), so they keep working
  after a bot restart.
```
