# MC-Bot — Current Issues Overview

> Generated from senior code review · February 2026

---

## 🔴 Critical — Will Crash in Production

### 1. Wrong Tuple Unpacking in `cogs/tasks.py`
`backup_manager.create_backup()` returns **3 values** `(success, filename, filepath)` but `daily_backup` only unpacks **2**.

```python
# ❌ CURRENT — crashes with ValueError
success, result = await backup_manager.create_backup()

# ✅ FIX
success, filename, filepath = await backup_manager.create_backup()
```

---

### 2. Missing `import asyncio` in `src/setup_views.py`
`asyncio` is only imported *locally* inside `_start_installation()`, making it unavailable in `_save_config_to_file()`.

```python
# ❌ CURRENT — NameError at runtime
async def _save_config_to_file(self, updates: dict):
    await asyncio.to_thread(...)  # asyncio not in scope here

# ✅ FIX — add to top of file
import asyncio
```

---

### 3. Attribute Name Mismatch in `cogs/automation.py`
`__init__` sets `self.log_scan_task = None`, but `cog_load` assigns `self.log_task`. `cog_unload` then references `self.log_task` which doesn't exist if the cog unloads before loading — raises `AttributeError`.

```python
# ❌ CURRENT — three different names for the same thing
self.log_scan_task = None   # __init__
self.log_task = asyncio.create_task(...)  # cog_load
if self.log_task: ...        # cog_unload

# ✅ FIX — use one consistent name, init in __init__
def __init__(self, bot):
    self.log_task = None  # consistent throughout
```

---

## 🟠 Significant — Bad Behaviour or Resource Leaks

### 4. Empty `word_hunt_task` Loop in `cogs/economy.py`
The `@tasks.loop(minutes=45)` loop body is `pass` — it does nothing. The real loop is spawned separately in `before_loop`. The task wastes a heartbeat every 45 minutes for no reason.

```python
# ❌ CURRENT — pointless loop
@tasks.loop(minutes=45)
async def word_hunt_task(self):
    pass

# ✅ FIX — spawn directly in cog_load, remove the task entirely
async def cog_load(self):
    self.hunt_task = asyncio.create_task(self.random_word_hunt_loop())
```

---

### 5. Queue Memory Leak in `src/log_dispatcher.py`
`automation.py` subscribes to `log_dispatcher` but **never unsubscribes** on cog unload. Dead queues accumulate and keep receiving data forever.

```python
# ✅ FIX — add to automation.py cog_unload
def cog_unload(self):
    self.motd_loop.cancel()
    if self.log_task:
        self.stop_scan.set()
        self.log_task.cancel()
    if hasattr(self, 'log_queue'):
        from src.log_dispatcher import log_dispatcher
        log_dispatcher.unsubscribe(self.log_queue)
```

---

### 6. No Timeout on External HTTP Requests in `cogs/stats.py`
If Mojang's API goes down, `get_uuid_online()` hangs indefinitely — blocking the entire async event loop for that interaction.

```python
# ❌ CURRENT — no timeout
async with aiohttp.ClientSession() as session:
    async with session.get(f'https://api.mojang.com/...') as resp:

# ✅ FIX
timeout = aiohttp.ClientTimeout(total=5)
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.get(f'https://api.mojang.com/...') as resp:
```

---

### 7. Inconsistent `GUILD_ID` Type in `src/config.py`
`setup_helper.py` stores `guild_id` as a **string** (`str(guild.id)`), but other places call `int(config.GUILD_ID)` without a null check, which crashes if the value is `None`.

```python
# ❌ CURRENT — setup_helper stores string
updates['guild_id'] = str(guild.id)

# ❌ CURRENT — bot.py calls int() without null guard in some paths
guild = self.get_guild(int(config.GUILD_ID))

# ✅ FIX — store as int, always guard against None
updates['guild_id'] = guild.id  # store as int

if config.GUILD_ID:
    guild = self.get_guild(int(config.GUILD_ID))
```

---

## 🟡 Code Quality — Low Risk but Should Be Fixed

### 8. Duplicate Import in `cogs/console.py`
```python
from datetime import datetime  # line 6
from datetime import datetime  # line 7 — exact duplicate, remove one
```

### 9. Deprecated API in `cogs/console.py`
```python
# ❌ Deprecated in Python 3.10+
last_send = asyncio.get_event_loop().time()

# ✅ Use instead
last_send = asyncio.get_running_loop().time()
```

### 10. Conflicting RCON Libraries in `requirements.txt`
Both `aio-mc-rcon` and `mcrcon` are listed. Only `aiomcrcon` is actually imported in `utils.py`. `mcrcon` is dead weight.

```
# ✅ Remove this line from requirements.txt
mcrcon
```

### 11. Typo in `cogs/ai.py` Error Message
```python
# ❌ "efficient" makes no sense here
"❌ AI features are not enabled. efficient API key or SDK missing."

# ✅ Should be
"❌ AI features are not enabled. No valid API key or SDK found."
```

### 12. Leading Whitespace on Line 1 of `src/server_info_manager.py`
The file starts with 4 spaces before the first import. Cosmetic but flagged by every linter.

### 13. Hardcoded Command Names in `cogs/help.py`
The `categories` dictionary hardcodes command names as strings. Adding a new command to a cog requires a manual update here or it won't appear in `/help`.

```python
# Consider building this dynamically from bot.tree.get_commands()
# or adding a category attribute to each command
```

---

## 📋 Summary

| Severity | Count | Fix Time (est.) |
|---|---|---|
| 🔴 Critical | 3 | ~30 minutes |
| 🟠 Significant | 4 | ~1 hour |
| 🟡 Code Quality | 6 | ~45 minutes |
| **Total** | **13** | **~2.5 hours** |

### Fix Priority for Demo Day
1. **`cogs/tasks.py`** — tuple unpack crash (2 min fix)
2. **`src/setup_views.py`** — missing import (1 min fix)
3. **`cogs/automation.py`** — attribute name mismatch (5 min fix)

Fix those three and the bot won't hard-crash during a live demo.

---
---
---

NEW CHANGES RELATED TO THE CODE:
# MC-Bot — Complete Issue Tracker & Feature Roadmap

> Last updated: February 2026 — Comprehensive review of all cogs, src modules, config, and Docker setup

---

## Table of Contents
1. [🔴 Critical Bugs](#-critical-bugs)
2. [🟠 Significant Issues](#-significant-issues)
3. [🟡 Code Quality & Deprecations](#-code-quality--deprecations)
4. [🗑️ Dead Code — Safe to Delete](#️-dead-code--safe-to-delete)
5. [🐳 Infrastructure Issues](#-infrastructure-issues)
6. [💡 Feature Roadmap](#-feature-roadmap)

---

## 🔴 Critical Bugs

These will cause hard crashes. Fix before any demo.

---

### 1. Wrong Tuple Unpacking — `cogs/tasks.py`

`backup_manager.create_backup()` returns **3 values** `(success, filename, filepath)`.
The `daily_backup` task only unpacks **2** — this raises `ValueError` every time the backup runs.

```python
# ❌ CURRENT — crashes every scheduled backup
success, result = await backup_manager.create_backup()

# ✅ FIX
success, filename, filepath = await backup_manager.create_backup()
if success:
    await self.send_log(f"✅ Daily backup created: `{filename}`")
else:
    await self.send_log(f"❌ Daily backup failed: {filename}")
```

---

### 2. Missing `import asyncio` — `src/setup_views.py`

`asyncio` is imported *locally* inside `_start_installation()` using a bare `import asyncio`
inside the method body. This makes `asyncio` unavailable in `_save_config_to_file()` which is
a separate method — raises `NameError` at runtime when saving config after setup completes.

```python
# ❌ CURRENT — NameError when _save_config_to_file is called
async def _save_config_to_file(self, updates: dict):
    await asyncio.to_thread(...)  # asyncio not in module scope

# ✅ FIX — add to the very top of setup_views.py
import asyncio
```

---

### 3. Attribute Name Mismatch — `cogs/automation.py`

Three different names used for the same task object across `__init__`, `cog_load`, and
`cog_unload`. If `cog_unload` fires before `cog_load` (e.g. during hot reload or error),
it raises `AttributeError: 'AutomationCog' object has no attribute 'log_task'`.

```python
# ❌ CURRENT — three names, one task
self.log_scan_task = None    # __init__
self.log_task = asyncio.create_task(...)  # cog_load
if self.log_task: ...         # cog_unload — AttributeError if cog_load never ran

# ✅ FIX — one name, initialized in __init__
def __init__(self, bot):
    self.bot = bot
    self.log_task = None        # initialize here
    self.stop_scan = asyncio.Event()
    self.motd_loop.start()

async def cog_load(self):
    from src.log_dispatcher import log_dispatcher
    self.log_queue = log_dispatcher.subscribe()
    await log_dispatcher.start()
    self.log_task = asyncio.create_task(self.scan_logs_for_triggers())

def cog_unload(self):
    self.motd_loop.cancel()
    if self.log_task:
        self.stop_scan.set()
        self.log_task.cancel()
    if hasattr(self, 'log_queue'):
        from src.log_dispatcher import log_dispatcher
        log_dispatcher.unsubscribe(self.log_queue)
```

---

### 4. `data/` Directory Not Mounted as Docker Volume — `docker-compose.yml`

**This is the most dangerous issue in the entire project.** `bot_config.json` and
`user_config.json` live inside the container image at `/app/data/`. They are NOT mounted
from the host. Every time you run `docker compose build` or `docker compose up --build`,
the container is rebuilt from the image — and **all runtime state is wiped**:
channel IDs, economy balances, event schedules, player mappings, spawn coordinates.

```yaml
# ❌ CURRENT docker-compose.yml — data/ is not persisted
volumes:
  - ./mc-server:/app/mc-server
  - ./backups:/app/backups
  - ./logs:/app/logs
  - ./.env:/app/.env
  # data/ IS MISSING — configs lost on every rebuild

# ✅ FIX — add this line to volumes in docker-compose.yml
  - ./data:/app/data
```

Also create the directory and copy defaults before first run:
```bash
mkdir -p data
cp data/bot_config.json data/bot_config.json.example  # already exists in repo
```

---

## 🟠 Significant Issues

Won't crash immediately but cause wrong behaviour or resource leaks.

---

### 5. `bot.loop` Deprecated — `cogs/economy.py`

`discord.py 2.0` deprecated `bot.loop`. Using it raises `DeprecationWarning` now and will
break in a future version.

```python
# ❌ CURRENT
self.bot.loop.create_task(self.random_word_hunt_loop())

# ✅ FIX — asyncio.create_task() works fine inside an async context
# Move the spawn into cog_load entirely (see issue #8 about empty task loop)
async def cog_load(self):
    self.hunt_task = asyncio.create_task(self.random_word_hunt_loop())
```

---

### 6. `/logs` Command Requires Unmounted Docker Socket — `cogs/admin.py`

The `/logs` command runs `docker logs --tail N mc-bot` as a subprocess from *inside the
container*. This requires `/var/run/docker.sock` to be mounted into the container — which
it isn't in `docker-compose.yml`. The command will always return `returncode != 0` and fall
back to reading `latest.log`, but only the bot logs (not the server logs) are in that file.

```yaml
# ✅ FIX option A — mount the Docker socket (gives the container Docker access, security tradeoff)
volumes:
  - /var/run/docker.sock:/var/run/docker.sock

# ✅ FIX option B — remove the docker logs attempt entirely, always use LogDispatcher queue
# The LogDispatcher already has all lines in memory — query it directly
```

---

### 7. Platform Never Saved to Config — `src/setup_views.py`

During setup, `self.state.platform` (`paper`, `vanilla`, `fabric`) is used to download the
right JAR but is never written to `bot_config.json`. Only `installed_version` is saved.

This means any future feature that needs to know what server type is running (like the TPS
monitor — see Feature Roadmap) has no way to find out without parsing log files.

```python
# ❌ CURRENT — in _start_installation, only version is saved
version_update = {'installed_version': setup_config['version']}
config.update_dynamic_config(version_update)

# ✅ FIX — save platform too
version_update = {
    'installed_version': setup_config['version'],
    'installed_platform': setup_config['platform'],   # ADD THIS
}
config.update_dynamic_config(version_update)
```

Also add to `bot_config.json` default:
```json
{
  "installed_platform": null
}
```

---

### 8. No Timeout on Mojang API — `cogs/stats.py` and `src/mc_installer.py`

Both make HTTP requests to Mojang's API with no timeout set. If Mojang goes down or rate
limits the request, the coroutine hangs indefinitely, blocking that Discord interaction
slot forever.

```python
# ❌ CURRENT — no timeout anywhere in stats.py or mc_installer.py
async with aiohttp.ClientSession() as session:
    async with session.get(f'https://api.mojang.com/...') as resp:

# ✅ FIX — add a timeout to the session
timeout = aiohttp.ClientTimeout(total=5)
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.get(f'https://api.mojang.com/...') as resp:
        if resp.status == 429:  # also handle rate limiting
            return None, None
```

---

### 9. Log Queue Memory Leak — `src/log_dispatcher.py` + `cogs/automation.py`

`automation.py` subscribes to `log_dispatcher` in `cog_load` but never calls
`log_dispatcher.unsubscribe()` in `cog_unload`. The dead queue stays in
`_subscribers` list and keeps filling up. Every time `automation.py` is reloaded
(e.g. via `/sync` or hot reload) a new orphaned queue is added.

```python
# ❌ CURRENT cog_unload in automation.py
def cog_unload(self):
    self.motd_loop.cancel()
    if self.log_task:
        self.stop_scan.set()
        self.log_task.cancel()
    # no unsubscribe — queue leaks

# ✅ FIX
def cog_unload(self):
    self.motd_loop.cancel()
    if self.log_task:
        self.stop_scan.set()
        self.log_task.cancel()
    if hasattr(self, 'log_queue'):
        from src.log_dispatcher import log_dispatcher
        log_dispatcher.unsubscribe(self.log_queue)
```

---

### 10. `WORLD_FOLDER` Hardcoded — `src/config.py`

```python
self.WORLD_FOLDER = "world"  # hardcoded
```

In Minecraft, the world folder name is set by `level-name` in `server.properties` and can
be changed by the server admin. If someone sets `level-name=survival` the bot will try to
back up a folder that doesn't exist (`/app/mc-server/world/`) and silently create empty zips.

```python
# ✅ FIX — read from server.properties at runtime
from src.mc_manager import get_server_properties

def get_world_folder(self) -> str:
    props = get_server_properties()
    if props:
        return props.get('level-name', 'world')
    return 'world'
```

---

### 11. `os.execv` Bot Restart Unreliable in Docker — `cogs/management.py`

```python
# ❌ CURRENT
os.execv(sys.executable, [sys.executable] + sys.argv)
```

`os.execv` replaces the current process image. Inside Docker, the bot is typically PID 1
(or close to it). Replacing PID 1 can cause the container to exit rather than restart
cleanly. The `restart: unless-stopped` policy will bring it back but there's a gap where
the bot is completely dead.

```python
# ✅ FIX — exit with a specific code and let Docker restart the container
await interaction.response.send_message("🔄 Restarting bot...", ephemeral=True)
await bot.close()
sys.exit(0)  # Docker restart policy handles the rest
```

---

### 12. `GUILD_ID` Type Inconsistency — `src/config.py` + `src/setup_helper.py`

`setup_helper.py` saves `guild_id` as a **string**:
```python
updates['guild_id'] = str(guild.id)
```

But `bot.py` and other places call `int(config.GUILD_ID)` without a null guard in some
code paths. `int(None)` raises `TypeError`. `int("123")` works but the inconsistency is
a footgun.

```python
# ✅ FIX — store as int everywhere
updates['guild_id'] = guild.id  # remove str() wrapper in setup_helper.py

# And always null-guard before int()
if config.GUILD_ID:
    guild = self.get_guild(int(config.GUILD_ID))
```

---

## 🟡 Code Quality & Deprecations

Lower priority but worth fixing before submission.

---

### 13. Deprecated `asyncio.get_event_loop()` — `cogs/console.py` + `cogs/tasks.py`

```python
# ❌ Deprecated since Python 3.10, emits DeprecationWarning in 3.12
last_send = asyncio.get_event_loop().time()
loop = asyncio.get_event_loop()

# ✅ Inside an async function, always use:
last_send = asyncio.get_running_loop().time()
loop = asyncio.get_running_loop()
```

---

### 14. Duplicate Import — `cogs/console.py`

```python
from datetime import datetime  # line 6
from datetime import datetime  # line 7 — exact duplicate, delete one
```

---

### 15. Typo in Error Message — `cogs/ai.py`

```python
# ❌ "efficient" makes no grammatical sense
"❌ AI features are not enabled. efficient API key or SDK missing."

# ✅
"❌ AI features are not enabled. No valid API key or SDK found."
```

---

### 16. Leading Whitespace Line 1 — `src/server_info_manager.py`

The file starts with 4 spaces before the first import. Every linter and IDE will flag this.
Delete the leading whitespace on line 1.

---

### 17. Conflicting RCON Packages — `requirements.txt`

```
git+https://github.com/Iapetus-11/aio-mc-rcon.git#egg=aio-mc-rcon  # used
mcrcon   # ❌ never imported anywhere — remove this line
```

---

### 18. Hardcoded Backup Path — `src/backup_manager.py`

```python
# ❌ CURRENT — hardcoded, doesn't use config
self.backup_dir = '/app/backups'
```

If someone changes the container path structure this silently breaks. Should reference
config or the environment:

```python
# ✅ FIX
self.backup_dir = os.environ.get('BACKUP_DIR', '/app/backups')
```

---

### 19. `add_view` Called in `on_ready` Instead of `setup_hook` — `cogs/control_panel.py`

`discord.py` docs say persistent views should be registered in `setup_hook` (before the
bot connects), not `on_ready`. If a button is clicked in the brief window between connection
and `on_ready` firing, the interaction will fail with "Unknown interaction".

```python
# ❌ CURRENT — too late
@commands.Cog.listener()
async def on_ready(self):
    self.bot.add_view(ControlPanelView(self.bot))

# ✅ FIX — register in bot.py setup_hook or in Cog's __init__
# In bot.py setup_hook(), after cogs are loaded:
self.add_view(ControlPanelView(self))
```

---

## 🗑️ Dead Code — Safe to Delete

Removing these makes the codebase ~500 lines lighter with zero functional change.

---

### `src/installer_views.py` — Entire File (~400 lines)

Fully replaced by `src/setup_views.py`. Nothing in the current codebase imports it.
Safe to delete entirely.

```bash
rm src/installer_views.py
```

---

### `cogs/economy.py` — `COLORS` Constant

```python
# ❌ DELETE — defined but never referenced anywhere
COLORS = [discord.Color.blue(), discord.Color.green(), discord.Color.gold(), discord.Color.purple()]
```

---

### `cogs/economy.py` — Empty `word_hunt_task` Loop (~10 lines)

The loop body is `pass`. The real logic lives in `random_word_hunt_loop()` spawned from
`before_loop`. The 45-minute task fires every 45 minutes to do nothing.

```python
# ❌ DELETE both the task and its before_loop
@tasks.loop(minutes=45)
async def word_hunt_task(self):
    pass

@word_hunt_task.before_loop
async def before_word_hunt(self):
    await self.bot.wait_until_ready()
    self.bot.loop.create_task(self.random_word_hunt_loop())
```

---

### `cogs/tasks.py` — Disabled `daily_backup` Task + Orphaned Imports (~25 lines)

The task is permanently commented out. `backup.py` handles scheduling. The imports it
needed are now unused.

```python
# ❌ DELETE the task, its before_loop, and these imports
from datetime import time as dt_time
import pytz
import time  # also unused

# and remove:
# @tasks.loop(time=dt_time(22, 0, tzinfo=pytz.timezone(config.TIMEZONE)))
# async def daily_backup(self): ...
```

---

### `cogs/automation.py` — Unused Imports

```python
# ❌ DELETE both — neither is referenced anywhere in the file
import random
import aiofiles
```

---

### `cogs/tasks.py` — `monitor_server_log` Task + Helpers (~65 lines)

Duplicates what `console.py` already does through `LogDispatcher` — but worse (reads file
directly, no batching, fewer event types). `console.py` should be the single source of
truth for log monitoring. Remove `monitor_server_log`, `_process_log_line`, `send_log`,
and the `log_position` instance variable from `tasks.py`.

The `crash_check` task in `tasks.py` is unique and must stay.

---

### `src/config.py` — `ADMIN_ROLE_ID = None`

Set in `load()`, never read anywhere meaningful. Role tracking goes through
`bot_config.json` under `admin_role_id`.

```python
# ❌ DELETE
self.ADMIN_ROLE_ID = None
```

---

### Cleanup Summary

| Item | File | Lines Removed |
|---|---|---|
| `installer_views.py` | `src/installer_views.py` | ~400 |
| `COLORS` constant | `cogs/economy.py` | 1 |
| Empty `word_hunt_task` loop | `cogs/economy.py` | ~10 |
| Dead `daily_backup` + imports | `cogs/tasks.py` | ~25 |
| Unused imports | `cogs/automation.py` | 2 |
| `monitor_server_log` + helpers | `cogs/tasks.py` | ~65 |
| `ADMIN_ROLE_ID` | `src/config.py` | 1 |
| **Total** | | **~504 lines** |

---

## 🐳 Infrastructure Issues

---

### Docker Compose Missing Volume for `data/`

Already covered in Critical Bug #4 above — this is the most important infrastructure fix.

---

### No Memory Limit on Playit Container — `docker-compose.yml`

The `mc-bot` service has `mem_limit: 8g` but the `playit` service has none. A misbehaving
tunnel agent could consume all available host RAM.

```yaml
# ✅ Add to playit service
playit:
  image: playitcloud/playit:0.15.19
  mem_limit: 256m   # tunnel agent needs very little memory
  restart: unless-stopped
```

---

## 💡 Feature Roadmap

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
installed_platform (from bot_config.json, see Issue #7)
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
        # Parse: "TPS from last 1m, 5m, 15m: 20.0, 20.0, 19.8"
        match = re.search(r'([\d.]+),\s*([\d.]+),\s*([\d.]+)', response)
        if match:
            return float(match.group(1))  # 1-minute TPS
        return None

    async def _tps_vanilla_debug(self) -> float | None:
        """10-second debug profiling for vanilla"""
        await rcon_cmd("debug start")
        await asyncio.sleep(10)
        await rcon_cmd("debug stop")
        # Read from log — last "Average tick time" line
        # Returns None if server too busy to process debug command
        log_path = os.path.join(config.SERVER_DIR, 'logs', 'latest.log')
        # ... parse log for tick time
        # Convert: TPS = min(20.0, round(1000 / avg_tick_ms, 2))

    async def _tps_spark(self) -> float | None:
        response = await rcon_cmd("spark tps")
        # Parse Spark's TPS output format
        match = re.search(r'TPS\s*[-–]\s*([\d.]+)', response)
        if match:
            return float(match.group(1))
        return None

    async def _check_spark_installed(self) -> bool:
        mods_dir = os.path.join(config.SERVER_DIR, 'mods')
        if not os.path.exists(mods_dir):
            return False
        return any('spark' in f.lower() for f in os.listdir(mods_dir))

    async def _offer_spark_install(self, platform: str):
        """Download spark and notify admin to restart"""
        mc_version = config.load_bot_config().get('installed_version', '1.21.4')
        spark_url = f"https://sparkapi.lucko.me/download/{platform}/{mc_version}"
        mods_dir = os.path.join(config.SERVER_DIR, 'mods')
        os.makedirs(mods_dir, exist_ok=True)
        dest = os.path.join(mods_dir, 'spark.jar')

        async with aiohttp.ClientSession() as session:
            async with session.get(spark_url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(dest, 'wb') as f:
                        await f.write(await resp.read())
                    await send_debug(self.bot,
                        f"⚡ Spark profiler installed for {platform}. "
                        f"**Restart the server** to activate TPS monitoring.")
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
| 18–20 | 🟢 Green | Normal |
| 15–18 | 🟡 Yellow | Warning |
| 10–15 | 🟠 Orange | Degraded |
| < 10 | 🔴 Red | Critical |

### Config Changes Needed
```json
// user_config.json additions
{
  "tps_alert_threshold": 18.0,
  "tps_check_interval_seconds": 60,
  "tps_consecutive_alerts_before_notify": 3
}

// bot_config.json additions (already covered by Issue #7 fix)
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

## Overall Summary

### Issues by Severity

| Severity | Count | Est. Fix Time |
|---|---|---|
| 🔴 Critical | 4 | ~45 minutes |
| 🟠 Significant | 8 | ~2 hours |
| 🟡 Code Quality | 7 | ~1 hour |
| 🗑️ Dead Code | 7 | ~30 minutes |
| 🐳 Infrastructure | 2 | ~15 minutes |
| **Total** | **28** | **~5 hours** |

### Feature Build Order (Recommended)

| Priority | Feature | Why |
|---|---|---|
| 1st | Chat Bridge | Most visually impressive for live demo, ~1 day |
| 2nd | TPS Monitor | Fills documented gap, Platform detection shows depth, ~1.5 days |
| 3rd | Session Tracker | Great for comparing players, sets up future SQLite migration, ~1 day |

### Fix Before Demo — Non-Negotiable

1. **Add `./data:/app/data` volume** — without this, all config is lost on rebuild
2. **Fix tuple unpack in `tasks.py`** — scheduled backups crash every night
3. **Add `import asyncio` to `setup_views.py`** — `/setup` command fails on completion
4. **Fix `automation.py` attribute names** — hot reload crashes the bot
