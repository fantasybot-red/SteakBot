# Docker deployment

This directory contains the Docker Compose stack for StreakBot: the **bot** plus
a **MongoDB-compatible database**.

## Usage

From the **project root**:

```bash
# Build and start in the background
docker compose -f docker/docker-compose.yml up -d --build

# View logs
docker compose -f docker/docker-compose.yml logs -f bot

# Stop
docker compose -f docker/docker-compose.yml down
```

Only `TOKEN` is required in the project-root `.env` file. Everything else has
sensible defaults; override any of them in `.env` if you like:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TOKEN` | *(required)* | Discord bot token |
| `MONGO_DB` | `streakbot` | Database name |
| `PREFIX` | `!` | Prefix-command prefix |
| `TIMEZONE` | `Asia/Bangkok` | Day-boundary timezone (UTC+7) |
| `STREAK_THRESHOLD` | `3` | Streak must exceed this to be "real" |
| `REVIVE_MAX` | `3` | Max revives per user per streak |
| `REMINDER_HOURS_BEFORE` | `2,1` | Hours before midnight to DM reminders |
| `FLUSH_INTERVAL_MINUTES` | `5` | How often buffered counts are written |

The build context is the project root, so the `Dockerfile` and source are picked
up correctly even though the compose file lives in `docker/`.

## 🍓 Raspberry Pi / ARM notes

### Raspberry Pi 4B — read this

**Official MongoDB 5.0+ does NOT run on a Raspberry Pi 4B.** The Pi 4B's
Broadcom BCM2711 / Cortex-A72 CPU is **ARMv8.0-A**, while MongoDB requires
**ARMv8.2-A or later** (MongoDB explicitly dropped Raspberry Pi 4 support). Only
the long-since **end-of-life MongoDB 4.4** runs on it officially.

This stack therefore uses **[Percona Server for MongoDB](https://www.percona.com/software/mongodb/percona-server-for-mongodb)**
(`percona/percona-server-mongodb:7.0`) instead of the official `mongo` image.
Percona Server is a **drop-in, fully MongoDB-compatible** database that publishes
ARM64 (aarch64) builds which run on the Pi 4B. PyMongo/Beanie talk to it with
**no code changes**.

### Other options for a Pi 4B

- **MongoDB Atlas (cloud):** skip the `mongo` service entirely. Set `MONGO_URI`
  to your Atlas connection string in `.env` and remove the `mongo` service (and
  the `depends_on` block) from the compose file so only the bot runs locally.
- **Old MongoDB 4.4:** works but is end-of-life and gets no security fixes — not
  recommended.

### Raspberry Pi 5 and newer

A **Raspberry Pi 5** (Cortex-A76 = ARMv8.2-A) and most modern ARM64 servers
support current MongoDB natively. If you prefer the official image on those, swap
the `mongo` service image back to `mongo:7`:

```yaml
  mongo:
    image: mongo:7
    # ...
```
