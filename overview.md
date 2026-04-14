# MC-Bot — Open Issues & Feature Roadmap

> Last updated: April 2026 — All critical and most significant bugs resolved. Remaining open issues and feature roadmap below.
> Previously resolved bugs are documented in `docs/information.md` section 10.

---

## Open Issues

### 1. `/logs` Command Requires Unmounted Docker Socket — `cogs/admin.py`

The `/logs` command runs `docker logs --tail N mc-bot` as a subprocess from *inside the container*. This requires `/var/run/docker.sock` to be mounted into the container — which it isn't in `docker-compose.yml`. The command silently falls back to reading `latest.log`, which only contains bot logs, not server logs.

```yaml
# Fix option A — mount the Docker socket (gives the container Docker access, security tradeoff)
volumes:
  - /var/run/docker.sock:/var/run/docker.sock

# Fix option B — remove the docker logs attempt entirely, always use LogDispatcher queue
# The LogDispatcher already has all lines in memory — query it directly
```

---

### 2. `WORLD_FOLDER` Hardcoded — `src/config.py`

```python
self.WORLD_FOLDER = "world"  # hardcoded
```

In Minecraft, the world folder name is set by `level-name` in `server.properties` and can be changed by the server admin. If someone sets `level-name=survival`, the bot will try to back up `/app/mc-server/world/` which doesn't exist, silently creating empty zips.

```python
# Fix — read from server.properties at runtime
def get_world_folder(self) -> str:
    props = get_server_properties()
    if props:
        return props.get('level-name', 'world')
    return 'world'
```

---

### 3. `add_view` Called in `on_ready` Instead of `setup_hook` — `cogs/control_panel.py`

Discord.py docs say persistent views should be registered in `setup_hook` (before the bot connects), not `on_ready`. If a button is clicked in the brief window between connection and `on_ready` firing, the interaction will fail with "Unknown interaction".

```python
# Current — too late
@commands.Cog.listener()
async def on_ready(self):
    self.bot.add_view(ControlPanelView(self.bot))

# Fix — register in bot.py setup_hook after cogs are loaded
self.add_view(ControlPanelView(self))
```

---

## Feature Roadmap

---

## Feature 1: Bidirectional Minecraft ↔ Discord Chat Bridge

### What It Does
A dedicated `#ingame-chat` Discord channel becomes a two-way portal into the game.
Messages sent in Discord appear in-game with a `[Discord]` prefix. In-game chat appears
in Discord in real time, optionally with the player's Minecraft skin as the webhook avatar.

### Why It Matters
The `LogDispatcher` already gives you in-game → Discord for free (it parses chat lines).
The missing direction is Discord → game. This is the single most satisfying feature to
demo live because both sides update in real time and the audience immediately understands it.

### Architecture

```
Discord User types in #ingame-chat
    → on_message event (filtered to that channel, ignore bot messages)
    → rcon_cmd(f'tellraw @a {{"text":"[Discord] <{username}> {message}","color":"aqua"}}')
    → appears in-game for all players

In-game player types in chat
    → LogDispatcher picks up the line
    → console.py (or new cog) parses: regex r'<(\w+)> (.*)'
    → send message to #ingame-chat channel via Webhook (so it shows player name, not bot name)
    → Webhook avatar URL: https://crafatar.com/avatars/{uuid}?overlay
```

### Implementation Notes
- Create `cogs/chat_bridge.py` — new dedicated cog
- Add `chat_bridge_channel_id` to `bot_config.json`
- Use a Discord Webhook for the game→Discord direction so each player's name appears
  as the message author with their Minecraft skin as avatar
- Filter out server messages (lines starting with `[Server]` or containing `[Bot]`)
  to prevent echo loops
- Configurable on/off toggle via `/chatbridge toggle` (stored in `user_config.json`)
- Rate limit Discord → game direction (max 1 message per 2 seconds per user) to prevent spam

### Config Changes Needed
```json
// bot_config.json additions
{
  "chat_bridge_channel_id": null,
  "chat_bridge_webhook_url": null,
  "chat_bridge_enabled": false
}
```

```json
// user_config.json additions
{
  "chat_bridge_rate_limit_seconds": 2,
  "chat_bridge_max_message_length": 100
}
```

### Estimated Complexity
**Medium — ~120 lines in a new cog.** The LogDispatcher subscription and RCON call are
already patterns used elsewhere. The hardest part is webhook setup and the echo-loop filter.

---

## Feature 2: Player Session & Statistics Tracker

### What It Does
Every join and leave event is timestamped and stored. Commands like `/sessions <player>` and
`/leaderboard` surface historical playtime, session counts, peak activity, and let players
compare stats against each other.

### Current Limitation — No SQLite Yet
Right now the economy uses `bot_config.json` which has race condition risks under load and
loses history on every rebuild (see Critical Bug #4). **SQLite migration is the right long-term
solution** but is out of scope for the current deadline.

**Short-term approach:** Store session data in a dedicated `data/sessions.json` file.
Same FileLock pattern already used everywhere else. This is not ideal for scale but works
perfectly for a small server and can be migrated to `aiosqlite` later with zero interface
changes.

### Data Structure (sessions.json)
```json
{
  "sessions": [
    {
      "player": "Notch",
      "discord_id": "123456789",
      "joined_at": "2026-02-20T14:30:00",
      "left_at": "2026-02-20T16:45:00",
      "duration_minutes": 135
    }
  ],
  "totals": {
    "Notch": {
      "total_minutes": 4320,
      "session_count": 12,
      "first_seen": "2026-01-01T10:00:00",
      "last_seen": "2026-02-20T16:45:00"
    }
  }
}
```

### Commands
| Command | Description |
|---|---|
| `/sessions <player>` | Total playtime, sessions, first/last seen, longest session |
| `/leaderboard playtime` | Top 10 players by total hours |
| `/leaderboard sessions` | Top 10 players by session count |
| `/compare <player1> <player2>` | Side-by-side stat comparison embed |

### Where Session Data Comes From
`console.py` already detects join/leave events and updates `bot_config['online_players']`.
Add a hook there to write to `sessions.json` at the same time — no new log parsing needed.

### Future Migration Path to SQLite
```python
# The interface stays identical
# Today:
session_store.record_join("Notch", discord_id)
session_store.record_leave("Notch")
totals = session_store.get_totals("Notch")

# After SQLite migration: same method signatures, different backend
# Zero changes needed in the cogs that call these methods
```

### Estimated Complexity
**Medium — ~150 lines split between a `src/session_store.py` helper and `cogs/sessions.py`.**
The most complex part is the comparison embed and the leaderboard aggregation query. The
storage layer is straightforward given the existing FileLock pattern.

---

## Feature 3: Real-Time TPS Monitor with Platform-Aware Detection

### What It Does
A background task checks server TPS (ticks per second) every 60 seconds. If performance
degrades below a configurable threshold for 3 consecutive checks, an alert embed is sent
to the debug channel with the current TPS, a severity colour, and an auto-recovery
notification when performance returns to normal.

A `/tps` command returns the current TPS on demand.

### The Platform Problem
Different server types expose TPS differently. The monitor must adapt:

```
installed_platform (from bot_config.json)
    │
    ├── "paper"   → RCON command: "tps"
    │               Response: "§aTPS from last 1m, 5m, 15m: §a20.0, 20.0, 19.8"
    │               Parse with regex: r'[\d.]+, ([\d.]+), ([\d.]+)'
    │               Use the 1-minute value as current TPS
    │
    ├── "vanilla" → No native /tps command
    │               Method: RCON "debug start" → wait 10 seconds → RCON "debug stop"
    │               Parse log output: "Average tick time: 48.23 ms"
    │               Convert: TPS = min(20.0, 1000 / avg_tick_ms)
    │               ⚠ This blocks for 10 seconds — run in background task only, not /tps
    │
    └── "fabric"  → Auto-download Spark profiler mod on first TPS check if not present
    └── "forge"   → Same Spark approach as Fabric
                    Download: https://sparkapi.lucko.me/download/fabric/{mc_version}
                              https://sparkapi.lucko.me/download/forge/{mc_version}
                    Place in: /app/mc-server/mods/spark.jar
                    Notify admin: "Spark installed — restart server to activate TPS monitoring"
                    After restart: RCON command "spark tps" or "spark health --memory"
                    Parse response for TPS value
```

### Implementation — `cogs/tps_monitor.py`

```python
class TPSMonitorCog(commands.Cog):

    async def get_tps(self) -> float | None:
        """Platform-aware TPS retrieval"""
        platform = config.load_bot_config().get('installed_platform', 'vanilla')

        if platform == 'paper':
            return await self._tps_paper()

        elif platform == 'vanilla':
            return await self._tps_vanilla_debug()

        elif platform in ('fabric', 'forge'):
            spark_installed = await self._check_spark_installed()
            if spark_installed:
                return await self._tps_spark()
            else:
                await self._offer_spark_install(platform)
                return None

    async def _tps_paper(self) -> float | None:
        response = await rcon_cmd("tps")
        match = re.search(r'([\d.]+),\s*([\d.]+),\s*([\d.]+)', response)
        if match:
            return float(match.group(1))  # 1-minute TPS
        return None

    async def _tps_vanilla_debug(self) -> float | None:
        """10-second debug profiling for vanilla"""
        await rcon_cmd("debug start")
        await asyncio.sleep(10)
        await rcon_cmd("debug stop")
        log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
        # parse log for "Average tick time: X ms"
        # Convert: TPS = min(20.0, round(1000 / avg_tick_ms, 2))

    async def _tps_spark(self) -> float | None:
        response = await rcon_cmd("spark tps")
        match = re.search(r'TPS\s*[-–]\s*([\d.]+)', response)
        if match:
            return float(match.group(1))
        return None
```

### Alert Logic

```python
@tasks.loop(seconds=60)
async def tps_check_loop(self):
    tps = await self.get_tps()
    if tps is None:
        return

    threshold = config.load_user_config().get('tps_alert_threshold', 18.0)

    if tps < threshold:
        self.consecutive_low_tps += 1
        if self.consecutive_low_tps >= 3:  # 3 minutes of bad TPS
            await self._send_tps_alert(tps, threshold)
    else:
        if self.consecutive_low_tps >= 3:
            await self._send_tps_recovery(tps)
        self.consecutive_low_tps = 0
```

### Alert Embed Colours
| TPS Range | Colour | Severity |
|---|---|---|
| 18–20 | Green | Normal |
| 15–18 | Yellow | Warning |
| 10–15 | Orange | Degraded |
| < 10 | Red | Critical |

### Config Changes Needed
```json
// user_config.json additions
{
  "tps_alert_threshold": 18.0,
  "tps_check_interval_seconds": 60,
  "tps_consecutive_alerts_before_notify": 3
}

// bot_config.json additions (already covered — installed_platform is now saved)
{
  "installed_platform": null
}
```

### Commands
| Command | Description |
|---|---|
| `/tps` | Current TPS, platform used, colour-coded embed |
| `/tps history` | Last 10 TPS readings (stored in memory ring buffer) |

### Estimated Complexity
**Medium-High — ~200 lines in `cogs/tps_monitor.py`.** The Paper path is 20 lines. Vanilla
debug parsing is the trickiest part. The Spark auto-install is straightforward but needs
careful error handling for network failures and wrong MC versions.

---

## Feature Build Order (Recommended)

| Priority | Feature | Why |
|---|---|---|
| 1st | Chat Bridge | Most visually impressive for live demo, ~1 day |
| 2nd | TPS Monitor | Platform detection shows depth, gap already documented, ~1.5 days |
| 3rd | Session Tracker | Great for comparing players, sets up future SQLite migration, ~1 day |
